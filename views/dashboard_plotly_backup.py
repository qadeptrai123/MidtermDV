"""
views/dashboard.py — Upgraded Crypto Futures Analytics Dashboard.

Changes:
  - 1-hour candle data (no 5-min)
  - Global sticky date-range + timeframe bar (date/timeframe only)
  - Each panel has its own coin multiselect
  - Liquidation panel: streamlit-echarts stacked bars + price line
  - January 2024 default range
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from streamlit_echarts import st_echarts
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data_loader import (
    load_candles, load_liquidations, load_metrics,
    load_all_candles, load_all_liquidations, load_all_metrics,
    resample_candles, resample_metrics, aggregate_liquidations,
    compute_ma, compute_price_change_pct, compute_candle_body_pct,
    detect_large_red_candles, compute_taker_buy_ratio, compute_oi_change_pct,
    compute_liquidation_imbalance, compute_rolling_correlation,
    filter_by_date, filter_by_coins,
    COINS, TIMEFRAME_MAP, FREQ_MAP,
    BULL_COLOR, BEAR_COLOR, ACCENT_COLOR, WARNING_COLOR,
    BG_COLOR, CARD_BG, TEXT_PRIMARY, TEXT_SECONDARY,
    COIN_COLORS, DEFAULT_START, DEFAULT_END,
)

# ──────────────────────────────────────────────────────────────
# CHART DEFAULTS
# ──────────────────────────────────────────────────────────────
CHART_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#0b1120",
    font=dict(family="'JetBrains Mono', 'Fira Code', monospace", color=TEXT_PRIMARY, size=12),
    margin=dict(l=12, r=12, t=48, b=12),
    hovermode="x unified",
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        bordercolor="rgba(255,255,255,0.08)",
        borderwidth=1,
        font=dict(size=11),
    ),
    xaxis=dict(gridcolor="rgba(255,255,255,0.05)", zerolinecolor="rgba(255,255,255,0.06)"),
    yaxis=dict(gridcolor="rgba(255,255,255,0.05)", zerolinecolor="rgba(255,255,255,0.06)"),
)

CHART_CONFIG = {
    "displayModeBar": True,
    "scrollZoom": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    "displaylogo": False,
}


def _apply_layout(fig, title="", height=550, **kwargs):
    layout = {**CHART_LAYOUT, "title": dict(text=title, font=dict(size=14, color=TEXT_PRIMARY)), "height": height}
    layout.update(kwargs)
    fig.update_layout(**layout)
    return fig


# ──────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────
def _coin_selector(label: str, key: str, default=None) -> list:
    """Small inline coin multiselect."""
    return st.multiselect(
        label,
        options=COINS,
        default=default or COINS,
        key=key,
        label_visibility="visible",
    )


def _fmt_val(val: float, unit="$") -> str:
    if val >= 1e9:
        return f"{unit}{val/1e9:.2f}B"
    if val >= 1e6:
        return f"{unit}{val/1e6:.2f}M"
    if val >= 1e3:
        return f"{unit}{val/1e3:.2f}K"
    return f"{unit}{val:.2f}"


# ──────────────────────────────────────────────────────────────
# PANEL 0 – KPI STRIP
# ──────────────────────────────────────────────────────────────
def _render_kpi_strip(all_candles, all_metrics, all_liq, start_date, end_date, selected_coins):
    st.markdown("### 📈 Tổng Quan Thị Trường")
    candles_f = filter_by_date(filter_by_coins(all_candles, selected_coins), start_date, end_date, "open_time")
    metrics_f = filter_by_date(filter_by_coins(all_metrics, selected_coins), start_date, end_date, "create_time")
    liq_f     = filter_by_date(filter_by_coins(all_liq, selected_coins), start_date, end_date, "time")

    cols = st.columns(len(selected_coins) * 2 or 1)
    for i, coin in enumerate(selected_coins):
        cc = candles_f[candles_f["coin"] == coin]
        if cc.empty:
            continue
        last_price  = cc.sort_values("open_time").iloc[-1]["close"]
        first_price = cc.sort_values("open_time").iloc[0]["open"]
        pct_change  = ((last_price - first_price) / first_price) * 100

        cm = metrics_f[metrics_f["coin"] == coin]
        last_oi = cm.sort_values("create_time").iloc[-1]["sum_open_interest_value"] if not cm.empty else 0

        cl = liq_f[liq_f["coin"] == coin]
        total_liq = cl["liq_value"].sum() if not cl.empty else 0

        col_idx = i * 2
        with cols[col_idx]:
            st.metric(
                label=f"💰 {coin}",
                value=f"${last_price:,.2f}",
                delta=f"{pct_change:+.2f}%",
                delta_color="normal" if pct_change >= 0 else "inverse",
            )
        with cols[col_idx + 1]:
            st.metric(label=f"📊 {coin} Tổng thanh lý", value=_fmt_val(total_liq))


# ──────────────────────────────────────────────────────────────
# PANEL 1 – CANDLESTICK + MA + VOLUME
# ──────────────────────────────────────────────────────────────
def _render_candlestick_panel(all_candles, start_date, end_date, freq):
    st.markdown("### 🕯️ Biểu Đồ Nến & Khối Lượng")

    p1c1, p1c2 = st.columns([3, 1])
    with p1c2:
        coin = st.selectbox("Coin", COINS, key="cs_coin")

    coin_df = filter_by_date(
        filter_by_coins(all_candles, [coin]), start_date, end_date, "open_time"
    ).sort_values("open_time")

    if coin_df.empty:
        st.warning("Không có dữ liệu.")
        return

    resampled = resample_candles(coin_df[coin_df["coin"] == coin].assign(coin=coin), freq)
    resampled = resampled.sort_values("open_time")
    resampled["ma7"]  = compute_ma(resampled, 7)
    resampled["ma25"] = compute_ma(resampled, 25)

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
    )

    fig.add_trace(go.Candlestick(
        x=resampled["open_time"],
        open=resampled["open"], high=resampled["high"],
        low=resampled["low"], close=resampled["close"],
        increasing_line_color=BULL_COLOR, decreasing_line_color=BEAR_COLOR,
        increasing_fillcolor=BULL_COLOR, decreasing_fillcolor=BEAR_COLOR,
        name="Giá", showlegend=False,
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=resampled["open_time"], y=resampled["ma7"],
        line=dict(color=WARNING_COLOR, width=1.5), name="MA(7)",
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=resampled["open_time"], y=resampled["ma25"],
        line=dict(color=ACCENT_COLOR, width=1.5), name="MA(25)",
    ), row=1, col=1)

    colors = [BULL_COLOR if c >= o else BEAR_COLOR
              for o, c in zip(resampled["open"], resampled["close"])]
    fig.add_trace(go.Bar(
        x=resampled["open_time"], y=resampled["volume"],
        marker_color=colors, opacity=0.8, name="Khối lượng", showlegend=False,
    ), row=2, col=1)

    fig.update_layout(
        **CHART_LAYOUT,
        title=dict(text=f"{coin}/USD — Biểu đồ Nến ({freq})", font=dict(size=14)),
        height=650,
        xaxis_rangeslider_visible=False,
    )
    fig.update_yaxes(title_text="Giá (USD)", row=1, col=1)
    fig.update_yaxes(title_text="KL", row=2, col=1)
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


# ──────────────────────────────────────────────────────────────
# PANEL 2 – OPEN INTEREST
# ──────────────────────────────────────────────────────────────
def _render_oi_panel(all_metrics, start_date, end_date, freq):
    st.markdown("### 📊 Open Interest")

    p2c1, p2c2 = st.columns([3, 1])
    with p2c2:
        coins = _coin_selector("Coins", "oi_coins")

    metrics_f = filter_by_date(filter_by_coins(all_metrics, coins), start_date, end_date, "create_time")
    resampled  = resample_metrics(metrics_f, freq)

    fig = go.Figure()
    for coin in coins:
        df = resampled[resampled["coin"] == coin].sort_values("create_time")
        if df.empty:
            continue
        fig.add_trace(go.Scatter(
            x=df["create_time"], y=df["sum_open_interest_value"],
            mode="lines", name=f"{coin}",
            line=dict(color=COIN_COLORS.get(coin, ACCENT_COLOR), width=2),
            fill="tozeroy" if len(coins) == 1 else None,
            fillcolor=f"rgba({','.join(str(int(COIN_COLORS.get(coin, '#666')[i:i+2], 16)) for i in (1,3,5))},0.08)" if len(coins) == 1 else None,
        ))

    _apply_layout(fig, title="Open Interest theo thời gian", height=500)
    fig.update_yaxes(title_text="OI Value (USD)")
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


# ──────────────────────────────────────────────────────────────
# PANEL 3 – LIQUIDATION (ECharts – Coinglass style)
# ──────────────────────────────────────────────────────────────
def _render_liquidation_echarts(all_liq, all_candles):
    """
    Stacked bar chart (Long Liq teal + Short Liq coral) with ETH/SOL/DOGE price line.
    Has its own date-range picker. X-axis unit: 1 day if range > 1 day, else 1 hour.
    """
    st.markdown("### 🔥 Biểu Đồ Thanh Lý (Coinglass Style)")

    # ── Controls row ──
    lc1, lc2, lc3 = st.columns([2, 3, 1])
    with lc1:
        liq_coins = _coin_selector("Coins", "liq_coins", default=["ETH"])
    with lc2:
        liq_dates = st.date_input(
            "Khoảng thời gian",
            value=(pd.Timestamp(DEFAULT_START).date(), pd.Timestamp(DEFAULT_END).date()),
            min_value=pd.Timestamp("2024-01-01").date(),
            max_value=pd.Timestamp("2024-03-31").date(),
            key="liq_dates",
        )
    with lc3:
        liq_agg_unit = st.selectbox("Đơn vị", ["1 ngày", "4 giờ", "1 giờ"], key="liq_unit")

    if len(liq_dates) != 2:
        st.info("Chọn đầy đủ ngày bắt đầu và kết thúc.")
        return

    liq_start, liq_end = pd.Timestamp(liq_dates[0]), pd.Timestamp(liq_dates[1])
    date_range_days = (liq_end - liq_start).days

    # Auto x-axis unit based on selected aggregation
    unit_map = {"1 ngày": "1D", "4 giờ": "4h", "1 giờ": "1h"}
    bucket_freq = unit_map[liq_agg_unit]

    # x-axis label format
    if date_range_days > 7:
        x_fmt = "%d/%m"
    elif date_range_days > 1:
        x_fmt = "%d/%m %Hh"
    else:
        x_fmt = "%H:%M"

    # ── Aggregate liquidations ──
    liq_raw = filter_by_date(
        filter_by_coins(all_liq, liq_coins), liq_start, liq_end, "time"
    )

    if liq_raw.empty:
        st.warning("Không có dữ liệu thanh lý trong khoảng này.")
        return

    agg = aggregate_liquidations(liq_raw, bucket_freq)

    # Build a common time axis
    all_buckets = sorted(agg["time_bucket"].unique())
    x_labels = [t.strftime(x_fmt) for t in all_buckets]
    bucket_to_idx = {t: i for i, t in enumerate(all_buckets)}

    # Aggregate across selected coins
    long_map = {}
    short_map = {}
    for _, row in agg.iterrows():
        t = row["time_bucket"]
        v = row["total_value"] if pd.notna(row["total_value"]) else 0
        if row["liq_side"] == "Long Liq":
            long_map[t] = long_map.get(t, 0) + v
        else:
            short_map[t] = short_map.get(t, 0) + v

    long_vals  = [long_map.get(t, 0) / 1e6  for t in all_buckets]   # in M USD
    short_vals = [short_map.get(t, 0) / 1e6 for t in all_buckets]   # in M USD

    # ── Price line (primary coin or first selected) ──
    price_coin = liq_coins[0] if liq_coins else "ETH"
    candles_f = filter_by_date(
        filter_by_coins(all_candles, [price_coin]), liq_start, liq_end, "open_time"
    ).sort_values("open_time")

    # Resample price to same frequency
    price_resampled = resample_candles(candles_f, bucket_freq) if not candles_f.empty else pd.DataFrame()

    # Map price to the same x buckets
    price_vals = []
    if not price_resampled.empty:
        price_times = price_resampled["open_time"].tolist()
        price_closes = price_resampled["close"].tolist()
        pt_map = {}
        for t, c in zip(price_times, price_closes):
            floored = t.floor(bucket_freq) if bucket_freq != "1D" else t.normalize()
            pt_map[floored] = c
        price_vals = [pt_map.get(t, None) for t in all_buckets]
    else:
        price_vals = [None] * len(all_buckets)

    price_vals_clean = [round(v, 2) if v is not None else "-" for v in price_vals]

    # ── Max for y-axis ──
    max_liq = max((max(long_vals) if long_vals else 0), (max(short_vals) if short_vals else 0), 1)

    price_min = min(v for v in price_vals if v is not None and v == v) if any(v for v in price_vals if v) else 0
    price_max = max(v for v in price_vals if v is not None and v == v) if any(v for v in price_vals if v) else 0
    price_pad = (price_max - price_min) * 0.05 if price_max > price_min else price_max * 0.05

    def fmt_liq(v):
        if v >= 1000:
            return f"${v/1000:.1f}B"
        return f"${v:.1f}M"

    # ── ECharts option ──
    option = {
        "backgroundColor": "#080c14",
        "grid": {"left": "6%", "right": "7%", "top": "14%", "bottom": "12%"},
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "cross", "crossStyle": {"color": "rgba(255,255,255,0.2)"}},
            "backgroundColor": "#0d1420",
            "borderColor": "rgba(255,255,255,0.1)",
            "borderWidth": 1,
            "textStyle": {"color": "#e2e8f0", "fontSize": 12},
        },
        "legend": {
            "top": 8,
            "data": ["Short", "Long", f"{price_coin} Price"],
            "textStyle": {"color": "#94a3b8"},
            "itemGap": 20,
        },
        "xAxis": {
            "type": "category",
            "data": x_labels,
            "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.1)"}},
            "axisLabel": {
                "color": "#94a3b8",
                "fontSize": 11,
                "interval": max(0, len(x_labels) // 12 - 1),
            },
            "splitLine": {"show": False},
        },
        "yAxis": [
            {
                "type": "value",
                "name": "K/l Thanh lý (USD)",
                "nameTextStyle": {"color": "#94a3b8", "fontSize": 11},
                "axisLabel": {
                    "color": "#94a3b8",
                    "formatter": "{value}M",
                },
                "axisLine": {"show": False},
                "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.05)"}},
                "max": round(max_liq * 1.15, 1),
            },
            {
                "type": "value",
                "name": f"{price_coin} (USD)",
                "nameTextStyle": {"color": "#94a3b8", "fontSize": 11},
                "position": "right",
                "axisLabel": {
                    "color": "#94a3b8",
                    "formatter": "${value}",
                },
                "axisLine": {"show": False},
                "splitLine": {"show": False},
                "min": round(price_min - price_pad, 0),
                "max": round(price_max + price_pad, 0),
            },
        ],
        "series": [
            {
                "name": "Long",
                "type": "bar",
                "stack": "liq",
                "yAxisIndex": 0,
                "data": long_vals,
                "itemStyle": {"color": "#00e5cc", "opacity": 0.88},
                "emphasis": {"itemStyle": {"opacity": 1}},
                "barMaxWidth": 20,
            },
            {
                "name": "Short",
                "type": "bar",
                "stack": "liq",
                "yAxisIndex": 0,
                "data": short_vals,
                "itemStyle": {"color": "#ff3d71", "opacity": 0.88},
                "emphasis": {"itemStyle": {"opacity": 1}},
                "barMaxWidth": 20,
            },
            {
                "name": f"{price_coin} Price",
                "type": "line",
                "yAxisIndex": 1,
                "data": price_vals_clean,
                "smooth": True,
                "symbol": "none",
                "lineStyle": {"color": "#f59e0b", "width": 2},
                "areaStyle": {
                    "color": {
                        "type": "linear",
                        "x": 0, "y": 0, "x2": 0, "y2": 1,
                        "colorStops": [
                            {"offset": 0, "color": "rgba(245,158,11,0.18)"},
                            {"offset": 1, "color": "rgba(245,158,11,0.0)"},
                        ],
                    }
                },
                "z": 10,
            },
        ],
        "dataZoom": [
            {
                "type": "slider",
                "show": True,
                "start": 0,
                "end": 100,
                "height": 20,
                "bottom": 10,
                "fillerColor": "rgba(124,92,252,0.12)",
                "borderColor": "rgba(255,255,255,0.08)",
                "handleStyle": {"color": "#7c5cfc"},
                "textStyle": {"color": "#94a3b8"},
            },
            {"type": "inside", "start": 0, "end": 100},
        ],
    }

    st_echarts(options=option, height="520px", key="liq_echarts")

    # ── Summary stats ──
    total_long  = sum(long_vals)
    total_short = sum(short_vals)
    total_all   = total_long + total_short
    s1, s2, s3 = st.columns(3)
    s1.metric("🟢 Long Liq", f"${total_long:.1f}M")
    s2.metric("🔴 Short Liq", f"${total_short:.1f}M")
    s3.metric("⚖️ Long %", f"{total_long/total_all*100:.1f}%" if total_all > 0 else "—")


# ──────────────────────────────────────────────────────────────
# PANEL 4 – VOLUME PROFILE
# ──────────────────────────────────────────────────────────────
def _render_volume_profile(all_candles, start_date, end_date, num_bins=50):
    st.markdown("### 📐 Hồ Sơ Khối Lượng (Volume Profile)")

    p4c1, p4c2 = st.columns([3, 1])
    with p4c2:
        coin = st.selectbox("Coin", COINS, key="vp_coin")

    coin_df = filter_by_date(
        filter_by_coins(all_candles, [coin]), start_date, end_date, "open_time"
    )
    if coin_df.empty:
        st.warning("Không có dữ liệu.")
        return

    price_min, price_max = coin_df["low"].min(), coin_df["high"].max()
    bins = np.linspace(price_min, price_max, num_bins + 1)
    coin_df = coin_df.copy()
    coin_df["price_bin"] = pd.cut(coin_df["close"], bins=bins, labels=False)
    vol_profile = coin_df.groupby("price_bin")["volume"].sum().reset_index()
    vol_profile["price_level"] = [(bins[int(i)] + bins[int(i) + 1]) / 2 for i in vol_profile["price_bin"]]

    poc_idx   = vol_profile["volume"].idxmax()
    poc_price = vol_profile.loc[poc_idx, "price_level"]

    total_vol  = vol_profile["volume"].sum()
    sorted_vp  = vol_profile.sort_values("volume", ascending=False)
    cumsum     = sorted_vp["volume"].cumsum()
    va_mask    = cumsum <= total_vol * 0.7
    va_prices  = sorted_vp[va_mask]["price_level"] if va_mask.any() else pd.Series([poc_price])
    va_high    = va_prices.max()
    va_low     = va_prices.min()

    bar_colors = []
    for _, row in vol_profile.iterrows():
        pl = row["price_level"]
        if abs(pl - poc_price) < (price_max - price_min) / num_bins:
            bar_colors.append(WARNING_COLOR)
        elif va_low <= pl <= va_high:
            bar_colors.append(ACCENT_COLOR)
        else:
            bar_colors.append("rgba(124, 92, 252, 0.28)")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=vol_profile["price_level"], x=vol_profile["volume"],
        orientation="h", marker_color=bar_colors, name="Khối lượng",
        hovertemplate="Giá: $%{y:,.2f}<br>KL: %{x:,.0f}<extra></extra>",
    ))
    fig.add_hline(y=poc_price, line_dash="dash", line_color=WARNING_COLOR,
                  annotation_text=f"POC: ${poc_price:,.2f}", annotation_position="top right",
                  annotation_font_color=WARNING_COLOR)
    fig.add_hrect(y0=va_low, y1=va_high, fillcolor=ACCENT_COLOR, opacity=0.07, line_width=0,
                  annotation_text="Value Area", annotation_position="top left",
                  annotation_font_color=ACCENT_COLOR)

    _apply_layout(fig, title=f"{coin} — Volume Profile", height=550)
    fig.update_yaxes(title_text="Mức Giá (USD)")
    fig.update_xaxes(title_text="Khối lượng tích lũy")
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


# ──────────────────────────────────────────────────────────────
# PANEL 5 – CORRELATION HEATMAP
# ──────────────────────────────────────────────────────────────
def _render_correlation_panel(all_candles, start_date, end_date):
    st.markdown("### 🔗 Ma Trận Tương Quan Giá")

    p5c1, p5c2 = st.columns([3, 1])
    with p5c2:
        coins = _coin_selector("Coins", "corr_coins")

    candles_f = filter_by_date(filter_by_coins(all_candles, coins), start_date, end_date, "open_time")
    pivot   = candles_f.pivot_table(index="open_time", columns="coin", values="close")
    returns = pivot.pct_change().dropna()

    if returns.empty or returns.shape[1] < 2:
        st.info("Cần ít nhất 2 coin.")
        return

    corr_matrix = returns.corr()
    fig = px.imshow(
        corr_matrix, text_auto=".3f",
        color_continuous_scale=[[0, BEAR_COLOR], [0.5, "#0b1120"], [1, BULL_COLOR]],
        zmin=-1, zmax=1, aspect="auto",
    )
    _apply_layout(fig, title="Tương quan lợi suất giữa các Coin", height=420)
    fig.update_layout(coloraxis_colorbar=dict(title="Corr"))
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


# ──────────────────────────────────────────────────────────────
# PANEL 5b – ROLLING CORRELATION
# ──────────────────────────────────────────────────────────────
def _render_rolling_correlation_panel(all_candles, start_date, end_date):
    st.markdown("### 📉 Tương Quan Động (Rolling Correlation)")

    p6c1, p6c2, p6c3 = st.columns([2, 2, 1])
    with p6c2:
        coins = _coin_selector("Coins", "rc_coins")
    with p6c3:
        window_days = st.slider("Cửa sổ (ngày)", 3, 30, 7, key="rc_window")

    candles_f = filter_by_date(filter_by_coins(all_candles, coins), start_date, end_date, "open_time")
    pivot   = candles_f.pivot_table(index="open_time", columns="coin", values="close")
    returns = pivot.pct_change().dropna()

    if returns.shape[1] < 2:
        st.info("Cần ít nhất 2 coin.")
        return

    avg_interval = (candles_f["open_time"].max() - candles_f["open_time"].min()) / max(len(candles_f), 1)
    candles_per_day = int(pd.Timedelta(days=1) / avg_interval) if avg_interval > pd.Timedelta(0) else 24
    window = max(int(window_days * candles_per_day), 24)

    fig = go.Figure()
    pair_colors = [ACCENT_COLOR, WARNING_COLOR, "#06b6d4", BULL_COLOR, BEAR_COLOR]
    ci = 0
    coins_list = returns.columns.tolist()
    for i, c1 in enumerate(coins_list):
        for j, c2 in enumerate(coins_list):
            if i < j:
                rc = returns[c1].rolling(window=window, min_periods=24).corr(returns[c2])
                fig.add_trace(go.Scatter(
                    x=returns.index, y=rc, mode="lines",
                    name=f"{c1}–{c2}",
                    line=dict(color=pair_colors[ci % len(pair_colors)], width=1.8),
                ))
                ci += 1

    fig.add_hline(y=0, line_dash="dot", line_color="rgba(255,255,255,0.2)")
    _apply_layout(fig, title=f"Tương quan động ({window_days} ngày)", height=420)
    fig.update_yaxes(title_text="Hệ số tương quan", range=[-1.1, 1.1])
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


# ──────────────────────────────────────────────────────────────
# PANEL 6 – LONG/SHORT RATIO
# ──────────────────────────────────────────────────────────────
def _render_ls_ratio_panel(all_metrics, start_date, end_date):
    st.markdown("### ⚖️ Tỷ Lệ Long/Short — Cá Voi vs Tổng Thể")

    p7c1, p7c2 = st.columns([3, 1])
    with p7c2:
        coin = st.selectbox("Coin", COINS, key="ls_coin")

    coin_df = filter_by_date(
        filter_by_coins(all_metrics, [coin]), start_date, end_date, "create_time"
    ).sort_values("create_time")
    if coin_df.empty:
        st.warning("Không có dữ liệu.")
        return

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(
        x=coin_df["create_time"], y=coin_df["count_toptrader_long_short_ratio"],
        mode="lines", name="Top Trader L/S",
        line=dict(color=WARNING_COLOR, width=2),
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=coin_df["create_time"], y=coin_df["count_long_short_ratio"],
        mode="lines", name="Tổng thể L/S",
        line=dict(color=ACCENT_COLOR, width=2),
    ), secondary_y=False)
    divergence = coin_df["count_toptrader_long_short_ratio"] - coin_df["count_long_short_ratio"]
    fig.add_trace(go.Scatter(
        x=coin_df["create_time"], y=divergence,
        mode="lines", fill="tozeroy", name="Phân kỳ",
        line=dict(color="rgba(124,92,252,0.3)", width=0),
        fillcolor="rgba(124,92,252,0.12)",
    ), secondary_y=True)
    fig.add_hline(y=1.0, line_dash="dot", line_color="rgba(255,255,255,0.25)",
                  annotation_text="Cân bằng", annotation_font_color=TEXT_SECONDARY)
    _apply_layout(fig, title=f"{coin} — Long/Short Ratio", height=500)
    fig.update_yaxes(title_text="Tỷ lệ L/S", secondary_y=False)
    fig.update_yaxes(title_text="Phân kỳ", secondary_y=True, showgrid=False)
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


# ──────────────────────────────────────────────────────────────
# PANEL 7 – TAKER BUY RATIO + PRICE
# ──────────────────────────────────────────────────────────────
def _render_taker_ratio_panel(all_candles, all_metrics, start_date, end_date, freq):
    st.markdown("### 💹 Tỷ Lệ Taker Mua/Bán & Giá")

    p8c1, p8c2 = st.columns([3, 1])
    with p8c2:
        coin = st.selectbox("Coin", COINS, key="taker_coin")

    coin_candles = filter_by_date(
        filter_by_coins(all_candles, [coin]), start_date, end_date, "open_time"
    ).sort_values("open_time")
    coin_metrics = filter_by_date(
        filter_by_coins(all_metrics, [coin]), start_date, end_date, "create_time"
    ).sort_values("create_time")

    if coin_candles.empty:
        st.warning("Không có dữ liệu.")
        return

    resampled = resample_candles(coin_candles, freq)
    resampled["taker_buy_ratio"] = compute_taker_buy_ratio(resampled)

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(
        x=resampled["open_time"], y=resampled["close"],
        mode="lines", name="Giá",
        line=dict(color=TEXT_PRIMARY, width=1.5),
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=resampled["open_time"], y=resampled["taker_buy_ratio"],
        mode="lines", name="Taker Buy Ratio",
        line=dict(color=BULL_COLOR, width=1), opacity=0.75,
    ), secondary_y=True)
    if not coin_metrics.empty:
        fig.add_trace(go.Scatter(
            x=coin_metrics["create_time"], y=coin_metrics["sum_taker_long_short_vol_ratio"],
            mode="lines", name="Taker L/S Vol Ratio",
            line=dict(color=WARNING_COLOR, width=1), opacity=0.75,
        ), secondary_y=True)
    fig.add_hline(y=0.5, line_dash="dot", line_color="rgba(255,255,255,0.15)", secondary_y=True)
    _apply_layout(fig, title=f"{coin} — Taker Pressure + Giá", height=500)
    fig.update_yaxes(title_text="Giá (USD)", secondary_y=False)
    fig.update_yaxes(title_text="Tỷ lệ Taker", secondary_y=True, showgrid=False)
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


# ──────────────────────────────────────────────────────────────
# PANEL 8 – SYNCED PRICE + OI + LIQUIDATION
# ──────────────────────────────────────────────────────────────
def _render_synced_panel(all_candles, all_metrics, all_liq, start_date, end_date, freq):
    st.markdown("### 📊 Giá — Open Interest — Thanh Lý (Đồng Bộ)")

    ps1, ps2 = st.columns([3, 1])
    with ps2:
        coin = st.selectbox("Coin", COINS, key="sync_coin")

    coin_candles = resample_candles(
        filter_by_date(filter_by_coins(all_candles, [coin]), start_date, end_date, "open_time"), freq
    ).sort_values("open_time")
    coin_metrics = filter_by_date(
        filter_by_coins(all_metrics, [coin]), start_date, end_date, "create_time"
    ).sort_values("create_time")
    liq_agg = aggregate_liquidations(
        filter_by_date(filter_by_coins(all_liq, [coin]), start_date, end_date, "time"), freq
    )

    if coin_candles.empty:
        st.warning("Không có dữ liệu.")
        return

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.5, 0.25, 0.25],
        subplot_titles=["Giá", "Open Interest", "Thanh lý"],
    )

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=coin_candles["open_time"],
        open=coin_candles["open"], high=coin_candles["high"],
        low=coin_candles["low"], close=coin_candles["close"],
        increasing_line_color=BULL_COLOR, decreasing_line_color=BEAR_COLOR,
        increasing_fillcolor=BULL_COLOR, decreasing_fillcolor=BEAR_COLOR,
        name="Giá", showlegend=False,
    ), row=1, col=1)

    coin_candles["body_pct"] = compute_candle_body_pct(coin_candles)
    big_red = coin_candles[coin_candles["body_pct"] < -1.5]
    if not big_red.empty:
        fig.add_trace(go.Scatter(
            x=big_red["open_time"], y=big_red["low"],
            mode="markers",
            marker=dict(color=BEAR_COLOR, size=8, symbol="triangle-down"),
            name="Nến đỏ lớn",
        ), row=1, col=1)

    # OI
    if not coin_metrics.empty:
        fig.add_trace(go.Scatter(
            x=coin_metrics["create_time"], y=coin_metrics["sum_open_interest_value"],
            mode="lines", name="OI",
            line=dict(color=ACCENT_COLOR, width=1.5),
            fill="tozeroy", fillcolor="rgba(124,92,252,0.08)",
        ), row=2, col=1)

    # Liquidation bars
    if not liq_agg.empty:
        coin_liq = liq_agg[liq_agg["coin"] == coin]
        long_liq  = coin_liq[coin_liq["liq_side"] == "Long Liq"]
        short_liq = coin_liq[coin_liq["liq_side"] == "Short Liq"]
        fig.add_trace(go.Bar(
            x=long_liq["time_bucket"], y=long_liq["total_value"],
            name="Long Liq", marker_color=BEAR_COLOR,
        ), row=3, col=1)
        fig.add_trace(go.Bar(
            x=short_liq["time_bucket"], y=-short_liq["total_value"],
            name="Short Liq", marker_color=BULL_COLOR,
        ), row=3, col=1)

    fig.update_layout(
        **CHART_LAYOUT,
        height=900,
        title=dict(text=f"{coin} — Phân tích đồng bộ Giá / OI / Thanh lý", font=dict(size=14)),
        barmode="relative",
        xaxis3_rangeslider_visible=True,
        xaxis3_rangeslider_thickness=0.03,
    )
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


# ──────────────────────────────────────────────────────────────
# PANEL 9 – MARKET STATE SIGNALS
# ──────────────────────────────────────────────────────────────
def _render_market_signals_panel(all_candles, all_metrics, all_liq, start_date, end_date):
    st.markdown("### 🧠 Tín Hiệu Trạng Thái Thị Trường")

    pm1, pm2 = st.columns([3, 1])
    with pm2:
        coin = st.selectbox("Coin", COINS, key="ms_coin")

    coin_candles = filter_by_date(filter_by_coins(all_candles, [coin]), start_date, end_date, "open_time").sort_values("open_time")
    coin_metrics = filter_by_date(filter_by_coins(all_metrics, [coin]), start_date, end_date, "create_time").sort_values("create_time")

    if coin_candles.empty or coin_metrics.empty:
        st.warning("Không đủ dữ liệu.")
        return

    daily_candles = coin_candles.set_index("open_time").resample("1D").agg({
        "open": "first", "high": "max", "low": "min", "close": "last",
        "volume": "sum", "taker_buy_volume": "sum",
    }).dropna(subset=["close"]).reset_index()

    daily_metrics = coin_metrics.set_index("create_time").resample("1D").agg({
        "sum_open_interest_value": "last",
        "sum_taker_long_short_vol_ratio": "mean",
        "count_long_short_ratio": "mean",
    }).reset_index()
    daily_metrics["sum_taker_long_short_vol_ratio"] = daily_metrics["sum_taker_long_short_vol_ratio"].ffill()
    daily_metrics["count_long_short_ratio"] = daily_metrics["count_long_short_ratio"].ffill()
    daily_metrics = daily_metrics.dropna(subset=["sum_open_interest_value"])

    daily_candles["price_change_pct"] = daily_candles["close"].pct_change() * 100
    daily_candles["taker_buy_ratio"]  = daily_candles["taker_buy_volume"] / daily_candles["volume"].replace(0, np.nan)
    daily_metrics["oi_change_pct"]    = daily_metrics["sum_open_interest_value"].pct_change() * 100

    daily_candles["date"] = daily_candles["open_time"].dt.date
    daily_metrics["date"] = daily_metrics["create_time"].dt.date
    merged = pd.merge(daily_candles, daily_metrics, on="date", how="inner")

    liq_agg = aggregate_liquidations(
        filter_by_date(filter_by_coins(all_liq, [coin]), start_date, end_date, "time"), "1D"
    )
    coin_liq = liq_agg[liq_agg["coin"] == coin] if not liq_agg.empty else pd.DataFrame()
    if not coin_liq.empty:
        coin_liq = coin_liq.copy()
        coin_liq["date"] = coin_liq["time_bucket"].dt.date
        liq_pivot = coin_liq.pivot_table(index="date", columns="liq_side", values="total_value", aggfunc="sum", fill_value=0).reset_index()
        for side in ["Long Liq", "Short Liq"]:
            if side not in liq_pivot.columns:
                liq_pivot[side] = 0
        liq_total = liq_pivot["Long Liq"] + liq_pivot["Short Liq"]
        liq_pivot["liq_imbalance"] = (liq_pivot["Long Liq"] - liq_pivot["Short Liq"]) / liq_total.replace(0, np.nan)
        merged = pd.merge(merged, liq_pivot[["date", "liq_imbalance"]], on="date", how="left")
    else:
        merged["liq_imbalance"] = 0

    for col in ["oi_change_pct", "liq_imbalance"]:
        merged[col] = merged[col].fillna(0)
    merged["taker_buy_ratio"] = merged["taker_buy_ratio"].fillna(0.5)
    merged = merged.dropna(subset=["price_change_pct"])
    if merged.empty:
        st.info("Không đủ dữ liệu sau khi tính toán.")
        return

    def normalize(s):
        s_min, s_max = s.min(), s.max()
        return 2 * (s - s_min) / (s_max - s_min) - 1 if s_max != s_min else s * 0

    signal_cols   = ["price_change_pct", "oi_change_pct", "liq_imbalance", "taker_buy_ratio"]
    signal_labels = ["Biến động giá %", "Biến động OI %", "Mất cân bằng thanh lý", "Tỷ lệ Taker Mua"]
    signal_matrix = pd.DataFrame({col: normalize(merged[col].fillna(0)) for col in signal_cols})

    def classify_state(row):
        score = row["price_change_pct"] + row["oi_change_pct"] * 0.5
        if score > 0.8:   return "🟢 Hưng phấn"
        elif score < -0.8: return "🔴 Hoảng loạn"
        else:              return "🟡 Bình thường"

    merged["market_state"] = signal_matrix.apply(classify_state, axis=1)

    fig = px.imshow(
        signal_matrix.T,
        x=[str(d) for d in merged["date"]], y=signal_labels,
        color_continuous_scale=[[0, BEAR_COLOR], [0.5, "#0b1120"], [1, BULL_COLOR]],
        zmin=-1, zmax=1, aspect="auto",
    )
    _apply_layout(fig, title=f"{coin} — Tín hiệu trạng thái thị trường", height=320)
    fig.update_layout(coloraxis_colorbar=dict(
        title="Tín hiệu", tickvals=[-1, 0, 1], ticktext=["Bearish", "Trung lập", "Bullish"]
    ), xaxis=dict(tickangle=-45, dtick=5))
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)

    state_colors = {"🟢 Hưng phấn": BULL_COLOR, "🔴 Hoảng loạn": BEAR_COLOR, "🟡 Bình thường": WARNING_COLOR}
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=[str(d) for d in merged["date"]], y=[1] * len(merged),
        marker_color=[state_colors.get(s, WARNING_COLOR) for s in merged["market_state"]],
        text=merged["market_state"], textposition="inside",
        hovertemplate="Ngày: %{x}<br>Trạng thái: %{text}<extra></extra>",
        showlegend=False,
    ))
    _apply_layout(fig2, title="Trạng thái thị trường theo ngày", height=150)
    fig2.update_layout(plot_bgcolor="#0b1120")
    fig2.update_yaxes(visible=False)
    fig2.update_xaxes(tickangle=-45, dtick=5)
    st.plotly_chart(fig2, use_container_width=True, config=CHART_CONFIG)


# ──────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ──────────────────────────────────────────────────────────────
def render_dashboard(_df=None):
    """Main entry point for the Dashboard tab."""

    # ── Header ──
    st.markdown(
        """
        <div style="text-align:center; padding: 0.5rem 0 0.8rem 0;">
            <h1 style="
                background: linear-gradient(90deg, #7c5cfc, #00e5cc, #f59e0b);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-size: 2rem;
                font-weight: 800;
                margin-bottom: 0.15rem;
                letter-spacing: -0.5px;
            ">CRYPTO FUTURES DASHBOARD</h1>
            <p style="color: #94a3b8; font-size: 0.85rem; margin:0;">
                ETH · SOL · DOGE &nbsp;|&nbsp; Hợp đồng Vĩnh Cửu &nbsp;|&nbsp; Q1/2024 &nbsp;|&nbsp; Dữ liệu 1H
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Global sticky controls (date range + timeframe only) ──
    st.markdown(
        """
        <div style="
            position: sticky; top: 0; z-index: 999;
            background: rgba(8,12,20,0.92);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid rgba(255,255,255,0.06);
            padding: 0.55rem 0.75rem;
            margin-bottom: 0.8rem;
        ">
        """,
        unsafe_allow_html=True,
    )

    gc1, gc2, gc3 = st.columns([3, 2, 1])
    with gc1:
        date_range = st.date_input(
            "📅 Khoảng thời gian (global)",
            value=(pd.Timestamp(DEFAULT_START).date(), pd.Timestamp(DEFAULT_END).date()),
            min_value=pd.Timestamp("2024-01-01").date(),
            max_value=pd.Timestamp("2024-03-31").date(),
            key="global_dates",
        )
    with gc2:
        timeframe = st.selectbox(
            "⏱ Khung thời gian (global)",
            options=list(TIMEFRAME_MAP.keys()),
            index=0,   # default 1h
            key="global_tf",
        )
    with gc3:
        kpi_coins = _coin_selector("KPI Coins", "kpi_coins_top")

    st.markdown("</div>", unsafe_allow_html=True)

    if len(date_range) != 2:
        st.warning("Chọn đầy đủ ngày bắt đầu và kết thúc.")
        return

    start_date = pd.Timestamp(date_range[0])
    end_date   = pd.Timestamp(date_range[1])
    freq       = TIMEFRAME_MAP[timeframe]

    # ── Load All Data (cached) ──
    with st.spinner("Đang tải dữ liệu…"):
        all_candles = load_all_candles()
        all_liq     = load_all_liquidations()
        all_metrics = load_all_metrics()

    # ── KPI Strip ──
    _render_kpi_strip(all_candles, all_metrics, all_liq, start_date, end_date, kpi_coins)
    st.markdown("---")

    # ── Panel 1: Candlestick ──
    _render_candlestick_panel(all_candles, start_date, end_date, freq)
    st.markdown("---")

    # ── Panel 2: OI ──
    _render_oi_panel(all_metrics, start_date, end_date, freq)
    st.markdown("---")

    # ── Panel 3: LIQUIDATION (ECharts) ──
    _render_liquidation_echarts(all_liq, all_candles)
    st.markdown("---")

    # ── Panel 4–5: Volume Profile + Correlation ──
    col_vp, col_corr = st.columns(2)
    with col_vp:
        _render_volume_profile(all_candles, start_date, end_date)
    with col_corr:
        _render_correlation_panel(all_candles, start_date, end_date)
    st.markdown("---")

    # ── Panel 5b: Rolling Correlation ──
    _render_rolling_correlation_panel(all_candles, start_date, end_date)
    st.markdown("---")

    # ── Panel 6–7: L/S Ratio + Taker ──
    col_ls, col_taker = st.columns(2)
    with col_ls:
        _render_ls_ratio_panel(all_metrics, start_date, end_date)
    with col_taker:
        _render_taker_ratio_panel(all_candles, all_metrics, start_date, end_date, freq)
    st.markdown("---")

    # ── Panel 8: Synced multi-panel ──
    _render_synced_panel(all_candles, all_metrics, all_liq, start_date, end_date, freq)
    st.markdown("---")

    # ── Panel 9: Market State ──
    _render_market_signals_panel(all_candles, all_metrics, all_liq, start_date, end_date)

    st.markdown(
        """<div style="text-align:center; padding:2rem 0 1rem 0; opacity:0.35; font-size:0.7rem;">
        Dữ liệu từ Binance · Coin-Margined Futures · Q1/2024
        </div>""",
        unsafe_allow_html=True,
    )
