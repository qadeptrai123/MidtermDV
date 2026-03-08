"""
views/dashboard.py — Unified Crypto Futures Analytics Dashboard.

Professional dark-theme dashboard inspired by Coinglass, TradingView, Binance.
All charts are organized by data type, collectively answering all 8 analysis questions.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
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
)


# ============================================================
# CHART DEFAULTS
# ============================================================
CHART_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#0d1117",
    font=dict(family="Inter, sans-serif", color=TEXT_PRIMARY, size=12),
    margin=dict(l=10, r=10, t=45, b=10),
    hovermode="x unified",
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        bordercolor="rgba(255,255,255,0.1)",
        borderwidth=1,
        font=dict(size=11),
    ),
    xaxis=dict(
        gridcolor="rgba(255,255,255,0.06)",
        zerolinecolor="rgba(255,255,255,0.08)",
    ),
    yaxis=dict(
        gridcolor="rgba(255,255,255,0.06)",
        zerolinecolor="rgba(255,255,255,0.08)",
    ),
)

CHART_CONFIG = {
    "displayModeBar": True,
    "scrollZoom": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    "displaylogo": False,
}


def _apply_layout(fig, title="", height=450, **kwargs):
    """Apply consistent layout to a figure."""
    layout = {**CHART_LAYOUT, "title": dict(text=title, font=dict(size=14)), "height": height}
    layout.update(kwargs)
    fig.update_layout(**layout)
    return fig


# ============================================================
# KPI METRIC STRIP
# ============================================================
def _render_kpi_strip(candles_df: pd.DataFrame, metrics_df: pd.DataFrame, liq_df: pd.DataFrame, selected_coins: list):
    """Render a row of KPI metric cards."""
    st.markdown("### 📈 Tổng Quan Thị Trường")

    cols = st.columns(6)

    for i, coin in enumerate(selected_coins[:3]):
        coin_candles = candles_df[candles_df["coin"] == coin]
        if coin_candles.empty:
            continue
        last_price = coin_candles.iloc[-1]["close"]
        first_price = coin_candles.iloc[0]["close"]
        pct_change = ((last_price - first_price) / first_price) * 100

        coin_metrics = metrics_df[metrics_df["coin"] == coin]
        last_oi = coin_metrics.iloc[-1]["sum_open_interest_value"] if not coin_metrics.empty else 0

        coin_liq = liq_df[liq_df["coin"] == coin]
        total_liq = coin_liq["liq_value"].sum() if not coin_liq.empty else 0

        with cols[i * 2]:
            delta_color = "normal" if pct_change >= 0 else "inverse"
            st.metric(
                label=f"💰 {coin} Giá",
                value=f"${last_price:,.2f}",
                delta=f"{pct_change:+.2f}%",
                delta_color=delta_color,
            )
        with cols[i * 2 + 1]:
            st.metric(
                label=f"📊 {coin} OI",
                value=f"${last_oi:,.0f}",
            )


# ============================================================
# PANEL 1: CANDLESTICK + MA + VOLUME
# ============================================================
def _render_candlestick_panel(candles_df: pd.DataFrame, selected_coin: str):
    """Interactive candlestick chart with MA(7), MA(25), and volume bars."""
    st.markdown("### 🕯️ Biểu Đồ Nến & Khối Lượng")

    coin_df = candles_df[candles_df["coin"] == selected_coin].copy().sort_values("open_time")

    if coin_df.empty:
        st.warning("Không có dữ liệu cho coin được chọn.")
        return

    # Compute MAs
    coin_df["ma7"] = compute_ma(coin_df, 7)
    coin_df["ma25"] = compute_ma(coin_df, 25)

    # Create subplots: candlestick on top, volume on bottom
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
    )

    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=coin_df["open_time"],
            open=coin_df["open"],
            high=coin_df["high"],
            low=coin_df["low"],
            close=coin_df["close"],
            increasing_line_color=BULL_COLOR,
            decreasing_line_color=BEAR_COLOR,
            increasing_fillcolor=BULL_COLOR,
            decreasing_fillcolor=BEAR_COLOR,
            name="Giá",
            showlegend=False,
        ),
        row=1, col=1,
    )

    # MA 7
    fig.add_trace(
        go.Scatter(
            x=coin_df["open_time"], y=coin_df["ma7"],
            line=dict(color="#f59e0b", width=1.5),
            name="MA(7)",
        ),
        row=1, col=1,
    )

    # MA 25
    fig.add_trace(
        go.Scatter(
            x=coin_df["open_time"], y=coin_df["ma25"],
            line=dict(color="#8b5cf6", width=1.5),
            name="MA(25)",
        ),
        row=1, col=1,
    )

    # Volume bars
    colors = [BULL_COLOR if c >= o else BEAR_COLOR for o, c in zip(coin_df["open"], coin_df["close"])]
    fig.add_trace(
        go.Bar(
            x=coin_df["open_time"], y=coin_df["volume"],
            marker_color=colors, opacity=0.85,
            name="Khối lượng", showlegend=False,
        ),
        row=2, col=1,
    )

    fig.update_layout(
        **CHART_LAYOUT,
        title=dict(text=f"{selected_coin}/USD — Biểu đồ Nến", font=dict(size=14)),
        height=600,
        xaxis_rangeslider_visible=False,
        xaxis2_rangeslider_visible=True,
        xaxis2_rangeslider_thickness=0.04,
    )
    fig.update_yaxes(title_text="Giá (USD)", row=1, col=1)
    fig.update_yaxes(title_text="KL", row=2, col=1)

    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


# ============================================================
# PANEL 2: OPEN INTEREST TIMELINE
# ============================================================
def _render_oi_panel(metrics_df: pd.DataFrame, selected_coins: list):
    """Open Interest over time for selected coins."""
    st.markdown("### 📊 Open Interest")

    fig = go.Figure()
    colors = {"ETH": ACCENT_COLOR, "SOL": WARNING_COLOR, "DOGE": "#06b6d4"}

    for coin in selected_coins:
        coin_df = metrics_df[metrics_df["coin"] == coin].sort_values("create_time")
        if coin_df.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=coin_df["create_time"],
                y=coin_df["sum_open_interest_value"],
                mode="lines",
                name=f"{coin} OI",
                line=dict(color=colors.get(coin, ACCENT_COLOR), width=1.5),
                fill="tonexty" if len(selected_coins) == 1 else None,
            )
        )

    _apply_layout(fig, title="Open Interest theo thời gian", height=400)
    fig.update_yaxes(title_text="OI Value (USD)")
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


# ============================================================
# PANEL 3: LIQUIDATION CHART (Mirrored bars like Coinglass)
# ============================================================
def _render_liquidation_panel(liq_agg: pd.DataFrame, selected_coin: str):
    """Liquidation volume stacked bar chart — Long up, Short down (mirrored)."""
    st.markdown("### 🔥 Biểu Đồ Thanh Lý")

    coin_df = liq_agg[liq_agg["coin"] == selected_coin].copy()
    if coin_df.empty:
        st.warning("Không có dữ liệu thanh lý.")
        return

    fig = go.Figure()

    # Long liquidations (positive, upward)
    long_df = coin_df[coin_df["liq_side"] == "Long Liq"]
    fig.add_trace(
        go.Bar(
            x=long_df["time_bucket"],
            y=long_df["total_value"],
            name="Long Liq",
            marker_color=BEAR_COLOR,
            marker_line=dict(color="#ff6b9d", width=0.5),
        )
    )

    # Short liquidations (negative, downward)
    short_df = coin_df[coin_df["liq_side"] == "Short Liq"]
    fig.add_trace(
        go.Bar(
            x=short_df["time_bucket"],
            y=-short_df["total_value"],
            name="Short Liq",
            marker_color=BULL_COLOR,
            marker_line=dict(color="#33e6c0", width=0.5),
        )
    )

    _apply_layout(fig, title=f"{selected_coin} — Thanh lý Long/Short", height=400)
    fig.update_layout(barmode="relative")
    fig.update_yaxes(title_text="Giá trị thanh lý (USD)")
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


# ============================================================
# PANEL 4: VOLUME PROFILE (Horizontal histogram)
# ============================================================
def _render_volume_profile(candles_df: pd.DataFrame, selected_coin: str, num_bins: int = 50):
    """Volume profile — horizontal histogram showing volume at each price level."""
    st.markdown("### 📐 Hồ Sơ Khối Lượng (Volume Profile)")

    coin_df = candles_df[candles_df["coin"] == selected_coin].copy()
    if coin_df.empty:
        st.warning("Không có dữ liệu.")
        return

    # Create price bins
    price_min, price_max = coin_df["low"].min(), coin_df["high"].max()
    bins = np.linspace(price_min, price_max, num_bins + 1)
    coin_df["price_bin"] = pd.cut(coin_df["close"], bins=bins, labels=False)

    vol_profile = coin_df.groupby("price_bin")["volume"].sum().reset_index()
    vol_profile["price_level"] = [(bins[int(i)] + bins[int(i) + 1]) / 2 for i in vol_profile["price_bin"]]

    # Point of Control (highest volume level)
    poc_idx = vol_profile["volume"].idxmax()
    poc_price = vol_profile.loc[poc_idx, "price_level"]

    # Value Area (70% of volume)
    total_vol = vol_profile["volume"].sum()
    sorted_vp = vol_profile.sort_values("volume", ascending=False)
    cumsum = sorted_vp["volume"].cumsum()
    va_mask = cumsum <= total_vol * 0.7
    va_prices = sorted_vp[va_mask | (cumsum == cumsum[va_mask.idxmax() if va_mask.any() else 0])]["price_level"]
    va_high = va_prices.max() if not va_prices.empty else poc_price
    va_low = va_prices.min() if not va_prices.empty else poc_price

    # Colors based on POC / Value Area
    colors = []
    for _, row in vol_profile.iterrows():
        pl = row["price_level"]
        if abs(pl - poc_price) < (price_max - price_min) / num_bins:
            colors.append(WARNING_COLOR)
        elif va_low <= pl <= va_high:
            colors.append(ACCENT_COLOR)
        else:
            colors.append("rgba(99, 102, 241, 0.3)")

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=vol_profile["price_level"],
            x=vol_profile["volume"],
            orientation="h",
            marker_color=colors,
            name="Khối lượng",
            hovertemplate="Giá: $%{y:,.2f}<br>KL: %{x:,.0f}<extra></extra>",
        )
    )

    # POC line
    fig.add_hline(
        y=poc_price, line_dash="dash", line_color=WARNING_COLOR,
        annotation_text=f"POC: ${poc_price:,.2f}",
        annotation_position="top right",
        annotation_font_color=WARNING_COLOR,
    )

    # Value Area
    fig.add_hrect(
        y0=va_low, y1=va_high,
        fillcolor=ACCENT_COLOR, opacity=0.08,
        line_width=0,
        annotation_text="Value Area",
        annotation_position="top left",
        annotation_font_color=ACCENT_COLOR,
    )

    _apply_layout(fig, title=f"{selected_coin} — Volume Profile", height=500)
    fig.update_yaxes(title_text="Mức Giá (USD)")
    fig.update_xaxes(title_text="Khối lượng tích lũy")
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


# ============================================================
# PANEL 5: PRICE CORRELATION HEATMAP
# ============================================================
def _render_correlation_panel(candles_df: pd.DataFrame):
    """Price return correlation heatmap across all coins."""
    st.markdown("### 🔗 Ma Trận Tương Quan Giá")

    # Compute daily returns for correlation
    pivot = candles_df.pivot_table(index="open_time", columns="coin", values="close")
    returns = pivot.pct_change().dropna()

    if returns.empty or returns.shape[1] < 2:
        st.info("Cần ít nhất 2 coin để tính tương quan.")
        return

    corr_matrix = returns.corr()

    fig = px.imshow(
        corr_matrix,
        text_auto=".3f",
        color_continuous_scale=[
            [0, BEAR_COLOR],
            [0.5, "#1a1a2e"],
            [1, BULL_COLOR],
        ],
        zmin=-1, zmax=1,
        aspect="auto",
    )

    _apply_layout(fig, title="Tương quan lợi suất giữa các Coin", height=400)
    fig.update_layout(coloraxis_colorbar=dict(title="Corr"))
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


# ============================================================
# PANEL 5b: ROLLING CORRELATION TIME SERIES
# ============================================================
def _render_rolling_correlation_panel(candles_df: pd.DataFrame, window_days: int = 7):
    """Rolling correlation between coin pairs over time."""
    st.markdown("### 📉 Tương Quan Động (Rolling Correlation)")

    pivot = candles_df.pivot_table(index="open_time", columns="coin", values="close")
    returns = pivot.pct_change().dropna()

    if returns.shape[1] < 2:
        st.info("Cần ít nhất 2 coin.")
        return

    # Determine window in candle count
    # Estimate frequency from data
    if len(candles_df) > 1:
        avg_interval = (candles_df["open_time"].max() - candles_df["open_time"].min()) / len(candles_df)
        candles_per_day = pd.Timedelta(days=1) / avg_interval if avg_interval > pd.Timedelta(0) else 288
    else:
        candles_per_day = 288  # 5min default

    window = int(window_days * candles_per_day)
    window = max(window, 20)

    fig = go.Figure()
    coins = returns.columns.tolist()
    pair_colors = [ACCENT_COLOR, WARNING_COLOR, "#06b6d4", BULL_COLOR, BEAR_COLOR, "#a855f7"]

    color_idx = 0
    for i, c1 in enumerate(coins):
        for j, c2 in enumerate(coins):
            if i < j:
                rolling_corr = returns[c1].rolling(window=window, min_periods=20).corr(returns[c2])
                fig.add_trace(
                    go.Scatter(
                        x=returns.index,
                        y=rolling_corr,
                        mode="lines",
                        name=f"{c1}–{c2}",
                        line=dict(color=pair_colors[color_idx % len(pair_colors)], width=1.5),
                    )
                )
                color_idx += 1

    fig.add_hline(y=0, line_dash="dot", line_color="rgba(255,255,255,0.2)")
    _apply_layout(fig, title=f"Tương quan động ({window_days} ngày)", height=350)
    fig.update_yaxes(title_text="Hệ số tương quan", range=[-1.1, 1.1])
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


# ============================================================
# PANEL 6: LONG/SHORT RATIO (Whale vs Overall)
# ============================================================
def _render_ls_ratio_panel(metrics_df: pd.DataFrame, selected_coin: str):
    """Top-trader L/S ratio vs overall L/S ratio — divergence chart."""
    st.markdown("### ⚖️ Tỷ Lệ Long/Short — Cá Voi vs Tổng Thể")

    coin_df = metrics_df[metrics_df["coin"] == selected_coin].sort_values("create_time")
    if coin_df.empty:
        st.warning("Không có dữ liệu.")
        return

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Top trader ratio
    fig.add_trace(
        go.Scatter(
            x=coin_df["create_time"],
            y=coin_df["count_toptrader_long_short_ratio"],
            mode="lines",
            name="Top Trader L/S",
            line=dict(color=WARNING_COLOR, width=2),
        ),
        secondary_y=False,
    )

    # Overall ratio
    fig.add_trace(
        go.Scatter(
            x=coin_df["create_time"],
            y=coin_df["count_long_short_ratio"],
            mode="lines",
            name="Tổng thể L/S",
            line=dict(color=ACCENT_COLOR, width=2),
        ),
        secondary_y=False,
    )

    # Divergence fill
    fig.add_trace(
        go.Scatter(
            x=coin_df["create_time"],
            y=coin_df["count_toptrader_long_short_ratio"] - coin_df["count_long_short_ratio"],
            mode="lines",
            fill="tozeroy",
            name="Phân kỳ",
            line=dict(color="rgba(99, 102, 241, 0.3)", width=0),
            fillcolor="rgba(99, 102, 241, 0.15)",
        ),
        secondary_y=True,
    )

    # Reference line at 1.0
    fig.add_hline(y=1.0, line_dash="dot", line_color="rgba(255,255,255,0.3)",
                  annotation_text="Cân bằng", annotation_font_color=TEXT_SECONDARY)

    _apply_layout(fig, title=f"{selected_coin} — Long/Short Ratio", height=400)
    fig.update_yaxes(title_text="Tỷ lệ L/S", secondary_y=False)
    fig.update_yaxes(title_text="Phân kỳ", secondary_y=True, showgrid=False)
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


# ============================================================
# PANEL 7: TAKER BUY/SELL RATIO + PRICE
# ============================================================
def _render_taker_ratio_panel(candles_df: pd.DataFrame, metrics_df: pd.DataFrame, selected_coin: str):
    """Taker buy ratio from candles + taker L/S vol ratio from metrics, overlaid with price."""
    st.markdown("### 💹 Tỷ Lệ Taker Mua/Bán & Giá")

    coin_candles = candles_df[candles_df["coin"] == selected_coin].copy().sort_values("open_time")
    coin_metrics = metrics_df[metrics_df["coin"] == selected_coin].copy().sort_values("create_time")

    if coin_candles.empty:
        st.warning("Không có dữ liệu.")
        return

    coin_candles["taker_buy_ratio"] = compute_taker_buy_ratio(coin_candles)

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Price line
    fig.add_trace(
        go.Scatter(
            x=coin_candles["open_time"], y=coin_candles["close"],
            mode="lines", name="Giá",
            line=dict(color=TEXT_PRIMARY, width=1.5),
        ),
        secondary_y=False,
    )

    # Taker buy ratio
    fig.add_trace(
        go.Scatter(
            x=coin_candles["open_time"], y=coin_candles["taker_buy_ratio"],
            mode="lines", name="Taker Buy Ratio",
            line=dict(color=BULL_COLOR, width=1),
            opacity=0.7,
        ),
        secondary_y=True,
    )

    # Taker L/S ratio from metrics
    if not coin_metrics.empty:
        fig.add_trace(
            go.Scatter(
                x=coin_metrics["create_time"],
                y=coin_metrics["sum_taker_long_short_vol_ratio"],
                mode="lines", name="Taker L/S Vol Ratio",
                line=dict(color=WARNING_COLOR, width=1),
                opacity=0.7,
            ),
            secondary_y=True,
        )

    fig.add_hline(y=0.5, line_dash="dot", line_color="rgba(255,255,255,0.15)",
                  secondary_y=True)

    _apply_layout(fig, title=f"{selected_coin} — Taker Pressure + Giá", height=400)
    fig.update_yaxes(title_text="Giá (USD)", secondary_y=False)
    fig.update_yaxes(title_text="Tỷ lệ Taker", secondary_y=True, showgrid=False)
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


# ============================================================
# PANEL 8: MARKET STATE SIGNAL HEATMAP
# ============================================================
def _render_market_signals_panel(candles_df: pd.DataFrame, metrics_df: pd.DataFrame, liq_agg: pd.DataFrame, selected_coin: str):
    """
    Composite market-state signal heatmap.
    Signals: price change %, OI change %, liquidation imbalance, taker ratio.
    """
    st.markdown("### 🧠 Tín Hiệu Trạng Thái Thị Trường")

    coin_candles = candles_df[candles_df["coin"] == selected_coin].copy().sort_values("open_time")
    coin_metrics = metrics_df[metrics_df["coin"] == selected_coin].copy().sort_values("create_time")

    if coin_candles.empty or coin_metrics.empty:
        st.warning("Không có đủ dữ liệu.")
        return

    # Resample to daily for signal clarity
    daily_candles = coin_candles.set_index("open_time").resample("1D").agg({
        "open": "first", "high": "max", "low": "min", "close": "last",
        "volume": "sum", "taker_buy_volume": "sum",
    }).dropna(subset=["close"]).reset_index()

    daily_metrics = coin_metrics.set_index("create_time").resample("1D").agg({
        "sum_open_interest_value": "last",
        "sum_taker_long_short_vol_ratio": "mean",
        "count_long_short_ratio": "mean",
    }).reset_index()
    # Forward-fill NaN ratio columns, only require OI to exist
    daily_metrics["sum_taker_long_short_vol_ratio"] = daily_metrics["sum_taker_long_short_vol_ratio"].ffill()
    daily_metrics["count_long_short_ratio"] = daily_metrics["count_long_short_ratio"].ffill()
    daily_metrics = daily_metrics.dropna(subset=["sum_open_interest_value"])

    # Compute daily signals
    daily_candles["price_change_pct"] = daily_candles["close"].pct_change() * 100
    daily_candles["taker_buy_ratio"] = daily_candles["taker_buy_volume"] / daily_candles["volume"].replace(0, np.nan)
    daily_metrics["oi_change_pct"] = daily_metrics["sum_open_interest_value"].pct_change() * 100

    # Merge on date
    daily_candles["date"] = daily_candles["open_time"].dt.date
    daily_metrics["date"] = daily_metrics["create_time"].dt.date
    merged = pd.merge(daily_candles, daily_metrics, on="date", how="inner")

    # Compute liq imbalance daily
    coin_liq = liq_agg[liq_agg["coin"] == selected_coin].copy()
    if not coin_liq.empty:
        coin_liq["date"] = coin_liq["time_bucket"].dt.date
        liq_pivot = coin_liq.pivot_table(
            index="date", columns="liq_side", values="total_value", aggfunc="sum", fill_value=0
        ).reset_index()
        if "Long Liq" not in liq_pivot.columns:
            liq_pivot["Long Liq"] = 0
        if "Short Liq" not in liq_pivot.columns:
            liq_pivot["Short Liq"] = 0
        liq_total = liq_pivot["Long Liq"] + liq_pivot["Short Liq"]
        liq_pivot["liq_imbalance"] = (liq_pivot["Long Liq"] - liq_pivot["Short Liq"]) / liq_total.replace(0, np.nan)
        merged = pd.merge(merged, liq_pivot[["date", "liq_imbalance"]], on="date", how="left")
    else:
        merged["liq_imbalance"] = 0

    # Only require price_change_pct; fill missing oi_change_pct with 0
    merged["oi_change_pct"] = merged["oi_change_pct"].fillna(0)
    merged["liq_imbalance"] = merged["liq_imbalance"].fillna(0)
    merged["taker_buy_ratio"] = merged["taker_buy_ratio"].fillna(0.5)
    merged = merged.dropna(subset=["price_change_pct"])

    if merged.empty:
        st.info("Không đủ dữ liệu sau khi tính toán.")
        return

    # Normalize signals to [-1, 1] for heatmap
    def normalize(s):
        s_min, s_max = s.min(), s.max()
        if s_max == s_min:
            return s * 0
        return 2 * (s - s_min) / (s_max - s_min) - 1

    signal_cols = ["price_change_pct", "oi_change_pct", "liq_imbalance", "taker_buy_ratio"]
    signal_labels = ["Biến động giá %", "Biến động OI %", "Mất cân bằng thanh lý", "Tỷ lệ Taker Mua"]

    signal_matrix = pd.DataFrame()
    for col in signal_cols:
        if col in merged.columns:
            signal_matrix[col] = normalize(merged[col].fillna(0))
        else:
            signal_matrix[col] = 0

    # Classify market state
    def classify_state(row):
        score = row["price_change_pct"] + row["oi_change_pct"] * 0.5
        if score > 0.8:
            return "🟢 Hưng phấn"
        elif score < -0.8:
            return "🔴 Hoảng loạn"
        else:
            return "🟡 Bình thường"

    merged["market_state"] = signal_matrix.apply(classify_state, axis=1)

    # Plot heatmap
    fig = px.imshow(
        signal_matrix.T,
        x=[str(d) for d in merged["date"]],
        y=signal_labels,
        color_continuous_scale=[
            [0, BEAR_COLOR],
            [0.5, "#1a1a2e"],
            [1, BULL_COLOR],
        ],
        zmin=-1, zmax=1,
        aspect="auto",
    )

    _apply_layout(fig, title=f"{selected_coin} — Tín hiệu trạng thái thị trường", height=300)
    fig.update_layout(
        coloraxis_colorbar=dict(title="Tín hiệu", tickvals=[-1, 0, 1], ticktext=["Bearish", "Trung lập", "Bullish"]),
        xaxis=dict(tickangle=-45, dtick=7),
    )
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)

    # Market state timeline bar
    state_colors = {"🟢 Hưng phấn": BULL_COLOR, "🔴 Hoảng loạn": BEAR_COLOR, "🟡 Bình thường": WARNING_COLOR}
    merged["state_color"] = merged["market_state"].map(state_colors)

    fig2 = go.Figure()
    fig2.add_trace(
        go.Bar(
            x=[str(d) for d in merged["date"]],
            y=[1] * len(merged),
            marker_color=merged["state_color"],
            text=merged["market_state"],
            textposition="inside",
            hovertemplate="Ngày: %{x}<br>Trạng thái: %{text}<extra></extra>",
            showlegend=False,
        )
    )

    _apply_layout(fig2, title="Trạng thái thị trường theo ngày", height=150)
    fig2.update_layout(plot_bgcolor="#0d1117")
    fig2.update_yaxes(visible=False)
    fig2.update_xaxes(tickangle=-45, dtick=7)
    st.plotly_chart(fig2, use_container_width=True, config=CHART_CONFIG)


# ============================================================
# PANEL 9: PRICE + OI + LIQUIDATION SYNCED (Multi-panel)
# ============================================================
def _render_synced_panel(candles_df: pd.DataFrame, metrics_df: pd.DataFrame, liq_agg: pd.DataFrame, selected_coin: str):
    """3-row synced chart: Price, OI, and Liquidation — for analyzing red candles & crash dynamics."""
    st.markdown("### 📊 Giá — Open Interest — Thanh Lý (Đồng Bộ)")

    coin_candles = candles_df[candles_df["coin"] == selected_coin].copy().sort_values("open_time")
    coin_metrics = metrics_df[metrics_df["coin"] == selected_coin].copy().sort_values("create_time")
    coin_liq = liq_agg[liq_agg["coin"] == selected_coin].copy()

    if coin_candles.empty:
        st.warning("Không có dữ liệu.")
        return

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.45, 0.25, 0.30],
        subplot_titles=["Giá", "Open Interest", "Khối lượng Thanh lý"],
    )

    # Row 1: Candlestick
    fig.add_trace(
        go.Candlestick(
            x=coin_candles["open_time"],
            open=coin_candles["open"], high=coin_candles["high"],
            low=coin_candles["low"], close=coin_candles["close"],
            increasing_line_color=BULL_COLOR, decreasing_line_color=BEAR_COLOR,
            increasing_fillcolor=BULL_COLOR, decreasing_fillcolor=BEAR_COLOR,
            name="Giá", showlegend=False,
        ),
        row=1, col=1,
    )

    # Highlight large red candles
    coin_candles["body_pct"] = compute_candle_body_pct(coin_candles)
    big_red = coin_candles[coin_candles["body_pct"] < -1.5]
    if not big_red.empty:
        fig.add_trace(
            go.Scatter(
                x=big_red["open_time"], y=big_red["low"],
                mode="markers",
                marker=dict(color=BEAR_COLOR, size=8, symbol="triangle-down"),
                name="Nến đỏ lớn",
            ),
            row=1, col=1,
        )

    # Row 2: OI
    if not coin_metrics.empty:
        fig.add_trace(
            go.Scatter(
                x=coin_metrics["create_time"],
                y=coin_metrics["sum_open_interest_value"],
                mode="lines", name="OI",
                line=dict(color=ACCENT_COLOR, width=1.5),
                fill="tozeroy", fillcolor="rgba(99, 102, 241, 0.1)",
            ),
            row=2, col=1,
        )

    # Row 3: Liquidation bars
    if not coin_liq.empty:
        long_liq = coin_liq[coin_liq["liq_side"] == "Long Liq"]
        short_liq = coin_liq[coin_liq["liq_side"] == "Short Liq"]

        fig.add_trace(
            go.Bar(
                x=long_liq["time_bucket"], y=long_liq["total_value"],
                name="Long Liq", marker_color=BEAR_COLOR,
                marker_line=dict(color="#ff6b9d", width=0.5),
            ),
            row=3, col=1,
        )
        fig.add_trace(
            go.Bar(
                x=short_liq["time_bucket"], y=-short_liq["total_value"],
                name="Short Liq", marker_color=BULL_COLOR,
                marker_line=dict(color="#33e6c0", width=0.5),
            ),
            row=3, col=1,
        )

    fig.update_layout(
        **CHART_LAYOUT,
        height=800,
        title=dict(text=f"{selected_coin} — Phân tích đồng bộ Giá / OI / Thanh lý", font=dict(size=14)),
        xaxis3_rangeslider_visible=True,
        xaxis3_rangeslider_thickness=0.03,
        barmode="relative",
    )

    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


# ============================================================
# MAIN DASHBOARD RENDERER
# ============================================================
def render_dashboard(_df=None):
    """Main entry point for the Dashboard tab."""

    # ── Dashboard title ──
    st.markdown(
        """
        <div style="text-align:center; padding: 0.5rem 0 1rem 0;">
            <h1 style="
                background: linear-gradient(90deg, #6366f1, #00d4aa, #f59e0b);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-size: 2rem;
                font-weight: 800;
                margin-bottom: 0.2rem;
            ">CRYPTO FUTURES DASHBOARD</h1>
            <p style="color: #9ca3af; font-size: 0.9rem;">
                Phân tích ETH · SOL · DOGE — Hợp đồng Vĩnh Cửu — Q1/2024
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Global Filters ──
    st.markdown(
        """<div style="
            background: rgba(17, 24, 39, 0.6);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 12px;
            padding: 0.8rem 1.2rem;
            margin-bottom: 1rem;
        ">""",
        unsafe_allow_html=True,
    )

    filter_cols = st.columns([2, 3, 2, 1])

    with filter_cols[0]:
        selected_coins = st.multiselect(
            "🪙 Chọn Coin",
            options=COINS,
            default=COINS,
            key="dash_coins",
        )

    with filter_cols[1]:
        date_range = st.slider(
            "📅 Khoảng thời gian",
            min_value=pd.Timestamp("2024-01-01").to_pydatetime(),
            max_value=pd.Timestamp("2024-03-31").to_pydatetime(),
            value=(
                pd.Timestamp("2024-01-01").to_pydatetime(),
                pd.Timestamp("2024-03-31").to_pydatetime(),
            ),
            format="DD/MM/YYYY",
            key="dash_date_range",
        )

    with filter_cols[2]:
        timeframe = st.selectbox(
            "⏱ Khung thời gian",
            options=list(TIMEFRAME_MAP.keys()),
            index=2,  # default 4H — better performance
            key="dash_timeframe",
        )

    with filter_cols[3]:
        st.markdown("<br>", unsafe_allow_html=True)
        primary_coin = st.selectbox(
            "📌 Coin chính",
            options=selected_coins if selected_coins else COINS,
            index=0,
            key="dash_primary_coin",
        )

    st.markdown("</div>", unsafe_allow_html=True)

    if not selected_coins:
        st.warning("⚠️ Vui lòng chọn ít nhất một coin.")
        return

    # ── Load Data ──
    freq = TIMEFRAME_MAP[timeframe]
    start_date, end_date = date_range

    with st.spinner("Đang tải dữ liệu..."):
        # Load raw data
        all_candles = load_all_candles()
        all_liq = load_all_liquidations()
        all_metrics = load_all_metrics()

        # Filter by coins
        all_candles = filter_by_coins(all_candles, selected_coins)
        all_liq = filter_by_coins(all_liq, selected_coins)
        all_metrics = filter_by_coins(all_metrics, selected_coins)

        # Filter by date
        all_candles = filter_by_date(all_candles, start_date, end_date, "open_time")
        all_liq = filter_by_date(all_liq, start_date, end_date, "time")
        all_metrics = filter_by_date(all_metrics, start_date, end_date, "create_time")

        # Resample
        candles = resample_candles(all_candles, freq)
        metrics = resample_metrics(all_metrics, freq)
        liq_agg = aggregate_liquidations(all_liq, freq)

    # ── KPI Strip ──
    _render_kpi_strip(candles, metrics, all_liq, selected_coins)

    st.markdown("---")

    # ── PANEL 1: Candlestick + MA + Volume ──
    _render_candlestick_panel(candles, primary_coin)

    st.markdown("---")

    # ── PANEL 2-3: OI + Liquidation (side by side) ──
    col_oi, col_liq = st.columns(2)
    with col_oi:
        _render_oi_panel(metrics, selected_coins)
    with col_liq:
        _render_liquidation_panel(liq_agg, primary_coin)

    st.markdown("---")

    # ── PANEL 4-5: Volume Profile + Correlation (side by side) ──
    col_vp, col_corr = st.columns(2)
    with col_vp:
        _render_volume_profile(candles, primary_coin)
    with col_corr:
        _render_correlation_panel(candles)

    st.markdown("---")

    # ── PANEL 5b: Rolling Correlation ──
    corr_window = st.slider("🔄 Cửa sổ tương quan (ngày)", 3, 30, 7, key="corr_window")
    _render_rolling_correlation_panel(candles, window_days=corr_window)

    st.markdown("---")

    # ── PANEL 6-7: L/S Ratio + Taker (side by side) ──
    col_ls, col_taker = st.columns(2)
    with col_ls:
        _render_ls_ratio_panel(metrics, primary_coin)
    with col_taker:
        _render_taker_ratio_panel(candles, metrics, primary_coin)

    st.markdown("---")

    # ── PANEL 8: Synced multi-panel (Price + OI + Liquidation) ──
    _render_synced_panel(candles, metrics, liq_agg, primary_coin)

    st.markdown("---")

    # ── PANEL 9: Market State Signals ──
    _render_market_signals_panel(all_candles, all_metrics, aggregate_liquidations(all_liq, "1D"), primary_coin)

    # Footer
    st.markdown(
        """
        <div style="text-align:center; padding: 2rem 0 1rem 0; opacity: 0.4; font-size: 0.75rem;">
            Dữ liệu từ Binance · Coin-Margined Futures · Q1/2024
        </div>
        """,
        unsafe_allow_html=True,
    )
