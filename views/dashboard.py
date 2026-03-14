"""
views/dashboard.py — Crypto Futures Dashboard (All ECharts, Coinglass style).

All charts use Apache ECharts via streamlit-echarts.
Data interval: 1 hour base.
"""

import streamlit as st
from streamlit_echarts import st_echarts
import pandas as pd
import numpy as np
import sys, os

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

# ── Shared ECharts dark theme helpers ──
_GRID = {"left": "6%", "right": "6%", "top": "14%", "bottom": "15%", "containLabel": True}
_TOOLTIP = {
    "trigger": "axis",
    "axisPointer": {"type": "cross", "crossStyle": {"color": "rgba(255,255,255,0.2)"}},
    "backgroundColor": "#0d1420",
    "borderColor": "rgba(255,255,255,0.1)",
    "borderWidth": 1,
    "textStyle": {"color": "#e2e8f0", "fontSize": 12},
}
_AXIS_LINE = {"lineStyle": {"color": "rgba(255,255,255,0.1)"}}
_AXIS_LABEL = {"color": "#94a3b8", "fontSize": 11}
_SPLIT_LINE = {"lineStyle": {"color": "rgba(255,255,255,0.05)"}}
_DATAZOOM = [
    {"type": "slider", "show": True, "start": 0, "end": 100, "height": 20,
     "bottom": 5, "fillerColor": "rgba(124,92,252,0.12)",
     "borderColor": "rgba(255,255,255,0.08)",
     "handleStyle": {"color": "#7c5cfc"}, "textStyle": {"color": "#94a3b8"}},
    {"type": "inside", "start": 0, "end": 100},
]
_LEGEND = {"top": 8, "textStyle": {"color": "#94a3b8"}, "itemGap": 20}
_BG = "#080c14"


def _coin_selector(label, key, default=None):
    return st.multiselect(label, options=COINS, default=default or COINS, key=key)


def _fmt_val(val, unit="$"):
    if val >= 1e9: return f"{unit}{val/1e9:.2f}B"
    if val >= 1e6: return f"{unit}{val/1e6:.2f}M"
    if val >= 1e3: return f"{unit}{val/1e3:.2f}K"
    return f"{unit}{val:.2f}"


def _ts_labels(series, fmt="%d/%m %H:%M"):
    return [t.strftime(fmt) for t in series]


# ──────────────────────────────────────────────────────────────
# PANEL 0 – KPI STRIP (no chart changes needed)
# ──────────────────────────────────────────────────────────────
def _render_kpi_strip(all_candles, all_metrics, all_liq):
    st.markdown("### 📈 Tổng Quan Thị Trường")
    
    start_date, end_date = pd.Timestamp(DEFAULT_START), pd.Timestamp(DEFAULT_END)
    selected_coins = COINS

    candles_f = filter_by_date(filter_by_coins(all_candles, selected_coins), start_date, end_date, "open_time")
    metrics_f = filter_by_date(filter_by_coins(all_metrics, selected_coins), start_date, end_date, "create_time")
    liq_f = filter_by_date(filter_by_coins(all_liq, selected_coins), start_date, end_date, "time")
    cols = st.columns(len(selected_coins) * 2 or 1)
    for i, coin in enumerate(selected_coins):
        cc = candles_f[candles_f["coin"] == coin]
        if cc.empty: continue
        last_price = cc.sort_values("open_time").iloc[-1]["close"]
        first_price = cc.sort_values("open_time").iloc[0]["open"]
        pct_change = ((last_price - first_price) / first_price) * 100
        cm = metrics_f[metrics_f["coin"] == coin]
        cl = liq_f[liq_f["coin"] == coin]
        total_liq = cl["liq_value"].sum() if not cl.empty else 0
        with cols[i * 2]:
            st.metric(label=f"💰 {coin}", value=f"${last_price:,.2f}",
                      delta=f"{pct_change:+.2f}%",
                      delta_color="normal" if pct_change >= 0 else "inverse")
        with cols[i * 2 + 1]:
            st.metric(label=f"📊 {coin} Tổng thanh lý", value=_fmt_val(total_liq))


# ──────────────────────────────────────────────────────────────
# PANEL 1 – CANDLESTICK + MA + VOLUME + LIQ HEATMAP (ECharts)
# ──────────────────────────────────────────────────────────────
def _render_candlestick_panel(all_candles, all_liq):
    st.markdown("### 🕯️ Biểu Đồ Nến & Khối Lượng")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        cs_dates = st.date_input(
            "Khoảng thời gian",
            value=(pd.Timestamp(DEFAULT_START).date(), pd.Timestamp(DEFAULT_END).date()),
            min_value=pd.Timestamp("2024-01-01").date(),
            max_value=pd.Timestamp("2024-03-31").date(), format="DD/MM/YYYY", key="cs_dates")
    with c2:
        coin = st.selectbox("Coin", COINS, key="cs_coin")
    with c3:
        tf_label = st.selectbox("Khung thời gian", ["1 giờ", "4 giờ", "1 ngày"], key="cs_tf")

    if len(cs_dates) != 2:
        st.warning("Chọn đầy đủ ngày bắt đầu và kết thúc."); return
    start_date, end_date = pd.Timestamp(cs_dates[0]), pd.Timestamp(cs_dates[1])
    
    freq_map = {"1 giờ": "1h", "4 giờ": "4h", "1 ngày": "1D"}
    freq = freq_map[tf_label]

    coin_df = filter_by_date(
        filter_by_coins(all_candles, [coin]), start_date, end_date, "open_time"
    ).sort_values("open_time")
    if coin_df.empty:
        st.warning("Không có dữ liệu."); return

    r = resample_candles(coin_df, freq).sort_values("open_time")
    r["ma7"] = compute_ma(r, 7)
    r["ma25"] = compute_ma(r, 25)

    x = _ts_labels(r["open_time"])
    ohlc = r[["open", "close", "low", "high"]].values.tolist()
    vol = r["volume"].tolist()
    vol_colors = [BULL_COLOR if c >= o else BEAR_COLOR for o, c in zip(r["open"], r["close"])]

    # Generate Heatmap Data
    min_p = r["low"].min() * 0.99
    max_p = r["high"].max() * 1.01
    option = {
        "backgroundColor": _BG,
        "animation": True,
        "legend": {**_LEGEND, "data": ["MA(7)", "MA(25)"]},
        "tooltip": _TOOLTIP,
        "axisPointer": {"link": [{"xAxisIndex": "all"}]},
        "grid": [
            {"left": "6%", "right": "6%", "top": "10%", "height": "55%"},
            {"left": "6%", "right": "6%", "top": "72%", "height": "18%"},
        ],
        "xAxis": [
            {"type": "category", "data": x, "gridIndex": 0,
             "axisLine": _AXIS_LINE, "axisLabel": {"show": False},
             "splitLine": {"show": False}, "boundaryGap": True},
            {"type": "category", "data": x, "gridIndex": 1,
             "axisLine": _AXIS_LINE, "axisLabel": _AXIS_LABEL,
             "splitLine": {"show": False}, "boundaryGap": True},
        ],
        "yAxis": [
            {"type": "value", "name": "Giá (USD)", "nameTextStyle": {"color": "#94a3b8"},
             "gridIndex": 0, "axisLabel": _AXIS_LABEL, "splitLine": _SPLIT_LINE,
             "axisLine": {"show": False}, "scale": True},
            {"type": "value", "name": "KL", "nameTextStyle": {"color": "#94a3b8"},
             "gridIndex": 1, "axisLabel": _AXIS_LABEL, "splitLine": _SPLIT_LINE,
             "axisLine": {"show": False}},
        ],
        "dataZoom": [
            {"type": "slider", "xAxisIndex": [0, 1], "start": 0, "end": 100,
             "bottom": 5, "height": 18, "fillerColor": "rgba(124,92,252,0.12)",
             "borderColor": "rgba(255,255,255,0.08)",
             "handleStyle": {"color": "#7c5cfc"}, "textStyle": {"color": "#94a3b8"}},
            {"type": "inside", "xAxisIndex": [0, 1]},
        ],
        "series": [
            {"name": "Candle", "type": "candlestick", "xAxisIndex": 0, "yAxisIndex": 0,
             "data": ohlc,
             "itemStyle": {"color": BULL_COLOR, "color0": BEAR_COLOR,
                           "borderColor": BULL_COLOR, "borderColor0": BEAR_COLOR}},
            {"name": "MA(7)", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0,
             "data": [round(v, 2) if pd.notna(v) else None for v in r["ma7"]],
             "smooth": True, "symbol": "none",
             "lineStyle": {"color": WARNING_COLOR, "width": 1.5}},
            {"name": "MA(25)", "type": "line", "xAxisIndex": 0, "yAxisIndex": 0,
             "data": [round(v, 2) if pd.notna(v) else None for v in r["ma25"]],
             "smooth": True, "symbol": "none",
             "lineStyle": {"color": ACCENT_COLOR, "width": 1.5}},
            {"name": "Volume", "type": "bar", "xAxisIndex": 1, "yAxisIndex": 1,
             "data": [{"value": v, "itemStyle": {"color": c}} for v, c in zip(vol, vol_colors)],
             "barMaxWidth": 8},
        ],
    }
    st_echarts(options=option, height="650px", key="candle_ec_v3")


# ──────────────────────────────────────────────────────────────
# PANEL 2 – OPEN INTEREST (ECharts)
# ──────────────────────────────────────────────────────────────
def _render_oi_panel(all_metrics):
    st.markdown("### 📊 Open Interest")
    c1, c2 = st.columns([3, 1])
    with c1:
        oi_dates = st.date_input(
            "Khoảng thời gian",
            value=(pd.Timestamp(DEFAULT_START).date(), pd.Timestamp(DEFAULT_END).date()),
            min_value=pd.Timestamp("2024-01-01").date(),
            max_value=pd.Timestamp("2024-03-31").date(), format="DD/MM/YYYY", key="oi_dates")
    with c2:
        coins = _coin_selector("Coins", "oi_coins")

    if len(oi_dates) != 2:
        st.warning("Chọn đầy đủ ngày bắt đầu và kết thúc."); return
    start_date, end_date = pd.Timestamp(oi_dates[0]), pd.Timestamp(oi_dates[1])
    freq = "1h"

    metrics_f = filter_by_date(filter_by_coins(all_metrics, coins), start_date, end_date, "create_time")
    resampled = resample_metrics(metrics_f, freq)

    # build common x from first coin that has data
    all_times = sorted(resampled["create_time"].unique())
    x = [t.strftime("%d/%m %H:%M") if isinstance(t, pd.Timestamp) else str(t) for t in all_times]

    series = []
    for coin in coins:
        df = resampled[resampled["coin"] == coin].sort_values("create_time")
        if df.empty: continue
        t_map = {t: v for t, v in zip(df["create_time"], df["sum_open_interest_value"])}
        vals = [round(t_map.get(t, None) or 0, 2) for t in all_times]
        color = COIN_COLORS.get(coin, ACCENT_COLOR)
        s = {"name": coin, "type": "line", "data": vals, "smooth": True, "symbol": "none",
             "lineStyle": {"color": color, "width": 2}}
        if len(coins) == 1:
            s["areaStyle"] = {"color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                "colorStops": [{"offset": 0, "color": color.replace(")", ",0.18)").replace("#", "rgba(") if color.startswith("rgba") else f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.18)"},
                               {"offset": 1, "color": "rgba(0,0,0,0)"}]}}
        series.append(s)

    option = {
        "backgroundColor": _BG, "tooltip": _TOOLTIP, "legend": _LEGEND,
        "grid": _GRID,
        "xAxis": {"type": "category", "data": x, "axisLine": _AXIS_LINE, "axisLabel": {**_AXIS_LABEL, "interval": max(0, len(x)//12-1)}, "splitLine": {"show": False}},
        "yAxis": {"type": "value", "name": "OI Value (USD)", "nameTextStyle": {"color": "#94a3b8"},
                  "axisLabel": _AXIS_LABEL, "splitLine": _SPLIT_LINE, "axisLine": {"show": False}},
        "series": series,
        "dataZoom": _DATAZOOM,
    }
    st_echarts(options=option, height="500px", key="oi_ec")


# ──────────────────────────────────────────────────────────────
# PANEL 3 – LIQUIDATION (ECharts – Coinglass style)
# ──────────────────────────────────────────────────────────────
def _render_liquidation_echarts(all_liq, all_candles):
    st.markdown("### Biểu Đồ Thanh Lý")
    lc1, lc2 = st.columns([1, 2])
    with lc1:
        liq_coin = st.selectbox("Coin", COINS, key="liq_coin")
    with lc2:
        liq_dates = st.date_input(
            "Khoảng thời gian",
            value=(pd.Timestamp(DEFAULT_START).date(), pd.Timestamp(DEFAULT_END).date()),
            min_value=pd.Timestamp("2024-01-01").date(),
            max_value=pd.Timestamp("2024-03-31").date(), format="DD/MM/YYYY", key="liq_dates")

    if len(liq_dates) != 2:
        st.info("Chọn đầy đủ ngày bắt đầu và kết thúc."); return

    liq_start, liq_end = pd.Timestamp(liq_dates[0]), pd.Timestamp(liq_dates[1])
    date_range_days = (liq_end - liq_start).days
    
    # Dynamic frequency based on selected date range: >1 day = 1D, <=1 day = 1h
    bucket_freq = "1D" if date_range_days > 1 else "1h"
    x_fmt = "%d/%m" if date_range_days > 7 else ("%d/%m %Hh" if date_range_days > 1 else "%H:%M")

    liq_raw = filter_by_date(filter_by_coins(all_liq, [liq_coin]), liq_start, liq_end, "time")
    if liq_raw.empty:
        st.warning("Không có dữ liệu thanh lý trong khoảng này."); return

    agg = aggregate_liquidations(liq_raw, bucket_freq)
    all_buckets = sorted(agg["time_bucket"].unique())
    x_labels = [t.strftime(x_fmt) for t in all_buckets]

    long_map, short_map = {}, {}
    for _, row in agg.iterrows():
        t, v = row["time_bucket"], row["total_value"] if pd.notna(row["total_value"]) else 0
        if row["liq_side"] == "Long Liq": long_map[t] = long_map.get(t, 0) + v
        else: short_map[t] = short_map.get(t, 0) + v

    long_vals = [long_map.get(t, 0) / 1e6 for t in all_buckets]
    short_vals = [short_map.get(t, 0) / 1e6 for t in all_buckets]

    price_coin = liq_coin
    candles_f = filter_by_date(
        filter_by_coins(all_candles, [price_coin]), liq_start, liq_end, "open_time"
    ).sort_values("open_time")
    price_resampled = resample_candles(candles_f, bucket_freq) if not candles_f.empty else pd.DataFrame()

    price_vals = [None] * len(all_buckets)
    if not price_resampled.empty:
        pt_map = {}
        for t, c in zip(price_resampled["open_time"], price_resampled["close"]):
            floored = t.floor(bucket_freq) if bucket_freq != "1D" else t.normalize()
            pt_map[floored] = c
        price_vals = [pt_map.get(t, None) for t in all_buckets]

    price_vals_clean = [round(v, 2) if v is not None else "-" for v in price_vals]
    stacked_vals = [l + s for l, s in zip(long_vals, short_vals)]
    max_liq = max(stacked_vals) if stacked_vals else 0
    if max_liq <= 0:
        max_liq = 0.1
    p_valid = [v for v in price_vals if v is not None]
    price_min = min(p_valid) if p_valid else 0
    price_max = max(p_valid) if p_valid else 0
    price_pad = (price_max - price_min) * 0.05 if price_max > price_min else price_max * 0.05

    option = {
        "backgroundColor": _BG,
        "grid": {"left": "6%", "right": "7%", "top": "14%", "bottom": "12%"},
        "tooltip": _TOOLTIP,
        "legend": {**_LEGEND, "data": ["Short", "Long", f"{price_coin} Price"]},
        "xAxis": {"type": "category", "data": x_labels, "axisLine": _AXIS_LINE,
                  "axisLabel": {**_AXIS_LABEL, "interval": max(0, len(x_labels)//12-1)},
                  "splitLine": {"show": False}},
        "yAxis": [
            {"type": "value", "name": "Thanh lý (M USD)", "nameTextStyle": {"color": "#94a3b8", "fontSize": 11},
             "axisLabel": {**_AXIS_LABEL, "formatter": "{value}M"}, "axisLine": {"show": False},
             "splitLine": _SPLIT_LINE, "max": round(max_liq * 1.15, 4)},
            {"type": "value", "name": f"{price_coin} (USD)", "nameTextStyle": {"color": "#94a3b8", "fontSize": 11},
             "position": "right", "axisLabel": {**_AXIS_LABEL, "formatter": "${value}"},
             "axisLine": {"show": False}, "splitLine": {"show": False},
             "min": round(price_min - price_pad, 0), "max": round(price_max + price_pad, 0)},
        ],
        "series": [
            {"name": "Short", "type": "line", "stack": "liq", "yAxisIndex": 0, "data": short_vals,
             "itemStyle": {"color": "#ff3d71", "opacity": 0.88}, "areaStyle": {"opacity": 0.5}, "smooth": True, "symbol": "none"},
            {"name": "Long", "type": "line", "stack": "liq", "yAxisIndex": 0, "data": long_vals,
             "itemStyle": {"color": "#00e5cc", "opacity": 0.88}, "areaStyle": {"opacity": 0.5}, "smooth": True, "symbol": "none"},
            {"name": f"{price_coin} Price", "type": "line", "yAxisIndex": 1, "data": price_vals_clean,
             "smooth": True, "symbol": "none", "lineStyle": {"color": "#f59e0b", "width": 2}, "connectNulls": True,
             "areaStyle": {"color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                 "colorStops": [{"offset": 0, "color": "rgba(245,158,11,0.18)"},
                                {"offset": 1, "color": "rgba(245,158,11,0.0)"}]}}, "z": 10},
        ],
        "dataZoom": _DATAZOOM,
    }
    st_echarts(options=option, height="650px", key="liq_echarts")

    # total_long, total_short = sum(long_vals), sum(short_vals)
    # total_all = total_long + total_short
    # s1, s2, s3 = st.columns(3)
    # s1.metric("🟢 Long Liq", f"${total_long:.1f}M")
    # s2.metric("🔴 Short Liq", f"${total_short:.1f}M")
    # s3.metric("⚖️ Long %", f"{total_long/total_all*100:.1f}%" if total_all > 0 else "—")


# ──────────────────────────────────────────────────────────────
# PANEL 4 – VOLUME PROFILE (ECharts)
# ──────────────────────────────────────────────────────────────
def _render_volume_profile(all_candles, num_bins=50):
    st.markdown("### 📐 Hồ Sơ Khối Lượng (Volume Profile)")
    c1, p4c2 = st.columns([3, 1])
    with c1:
        vp_dates = st.date_input(
            "Khoảng thời gian",
            value=(pd.Timestamp(DEFAULT_START).date(), pd.Timestamp(DEFAULT_END).date()),
            min_value=pd.Timestamp("2024-01-01").date(),
            max_value=pd.Timestamp("2024-03-31").date(), format="DD/MM/YYYY", key="vp_dates")
    with p4c2:
        coin = st.selectbox("Coin", COINS, key="vp_coin")

    if len(vp_dates) != 2:
        st.warning("Chọn đầy đủ ngày bắt đầu và kết thúc."); return
    start_date, end_date = pd.Timestamp(vp_dates[0]), pd.Timestamp(vp_dates[1])

    coin_df = filter_by_date(filter_by_coins(all_candles, [coin]), start_date, end_date, "open_time")
    if coin_df.empty:
        st.warning("Không có dữ liệu."); return

    price_min, price_max = coin_df["low"].min(), coin_df["high"].max()
    bins = np.linspace(price_min, price_max, num_bins + 1)
    cdf = coin_df.copy()
    cdf["price_bin"] = pd.cut(cdf["close"], bins=bins, labels=False)
    vol_profile = cdf.groupby("price_bin")["volume"].sum().reset_index()
    vol_profile["price_level"] = [(bins[int(i)] + bins[int(i)+1]) / 2 for i in vol_profile["price_bin"]]

    poc_idx = vol_profile["volume"].idxmax()
    poc_price = vol_profile.loc[poc_idx, "price_level"]
    total_vol = vol_profile["volume"].sum()
    sorted_vp = vol_profile.sort_values("volume", ascending=False)
    cumsum = sorted_vp["volume"].cumsum()
    va_mask = cumsum <= total_vol * 0.7
    va_prices = sorted_vp[va_mask]["price_level"] if va_mask.any() else pd.Series([poc_price])
    va_high, va_low = va_prices.max(), va_prices.min()

    y_labels = [f"${pl:,.0f}" for pl in vol_profile["price_level"]]
    bar_data = []
    for _, row in vol_profile.iterrows():
        pl = row["price_level"]
        if abs(pl - poc_price) < (price_max - price_min) / num_bins:
            color = WARNING_COLOR
        elif va_low <= pl <= va_high:
            color = ACCENT_COLOR
        else:
            color = "rgba(124,92,252,0.28)"
        bar_data.append({"value": round(row["volume"], 2), "itemStyle": {"color": color}})

    option = {
        "backgroundColor": _BG, "tooltip": {**_TOOLTIP, "trigger": "axis"},
        "grid": {"left": "12%", "right": "6%", "top": "10%", "bottom": "10%"},
        "xAxis": {"type": "value", "name": "Khối lượng tích lũy", "nameTextStyle": {"color": "#94a3b8"},
                  "axisLabel": _AXIS_LABEL, "splitLine": _SPLIT_LINE},
        "yAxis": {"type": "category", "data": y_labels, "axisLine": _AXIS_LINE, "axisLabel": _AXIS_LABEL},
        "series": [{"type": "bar", "data": bar_data, "barMaxWidth": 12,
                    "markLine": {"data": [{"yAxis": f"${poc_price:,.0f}", "label": {"formatter": f"POC: ${poc_price:,.2f}", "color": WARNING_COLOR},
                                           "lineStyle": {"color": WARNING_COLOR, "type": "dashed"}}],
                                 "symbol": "none"}}],
    }
    st_echarts(options=option, height="550px", key="vp_ec")


# ──────────────────────────────────────────────────────────────
# PANEL 5 – CORRELATION HEATMAP (ECharts)
# ──────────────────────────────────────────────────────────────
def _render_correlation_panel(all_candles):
    st.markdown("### 🔗 Ma Trận Tương Quan Giá")
    c1, p5c2 = st.columns([3, 1])
    with c1:
        corr_dates = st.date_input(
            "Khoảng thời gian",
            value=(pd.Timestamp(DEFAULT_START).date(), pd.Timestamp(DEFAULT_END).date()),
            min_value=pd.Timestamp("2024-01-01").date(),
            max_value=pd.Timestamp("2024-03-31").date(), format="DD/MM/YYYY", key="corr_dates")
    with p5c2:
        coins = _coin_selector("Coins", "corr_coins")

    if len(corr_dates) != 2:
        st.warning("Chọn đầy đủ ngày bắt đầu và kết thúc."); return
    start_date, end_date = pd.Timestamp(corr_dates[0]), pd.Timestamp(corr_dates[1])

    candles_f = filter_by_date(filter_by_coins(all_candles, coins), start_date, end_date, "open_time")
    pivot = candles_f.pivot_table(index="open_time", columns="coin", values="close")
    returns = pivot.pct_change().dropna()
    if returns.empty or returns.shape[1] < 2:
        st.info("Cần ít nhất 2 coin."); return

    corr_matrix = returns.corr()
    coin_list = corr_matrix.columns.tolist()
    hm_data = []
    for i, c1 in enumerate(coin_list):
        for j, c2 in enumerate(coin_list):
            hm_data.append([i, j, round(corr_matrix.loc[c1, c2], 3)])

    option = {
        "backgroundColor": _BG, "tooltip": {"position": "top",
            "formatter": "{c}", "backgroundColor": "#0d1420", "textStyle": {"color": "#e2e8f0"}},
        "grid": {"left": "15%", "right": "15%", "top": "10%", "bottom": "15%"},
        "xAxis": {"type": "category", "data": coin_list, "axisLabel": _AXIS_LABEL, "splitLine": {"show": False}},
        "yAxis": {"type": "category", "data": coin_list, "axisLabel": _AXIS_LABEL, "splitLine": {"show": False}},
        "visualMap": {"min": -1, "max": 1, "calculable": True, "orient": "horizontal",
                      "left": "center", "bottom": 0,
                      "inRange": {"color": [BEAR_COLOR, "#0b1120", BULL_COLOR]},
                      "textStyle": {"color": "#94a3b8"}},
        "series": [{"type": "heatmap", "data": hm_data,
                    "label": {"show": True, "formatter": "{@[2]}", "color": "#e2e8f0", "fontSize": 14},
                    "itemStyle": {"borderColor": "#080c14", "borderWidth": 2}}],
    }
    st_echarts(options=option, height="420px", key="corr_ec")


# ──────────────────────────────────────────────────────────────
# PANEL 5b – ROLLING CORRELATION (ECharts)
# ──────────────────────────────────────────────────────────────
def _render_rolling_correlation_panel(all_candles):
    st.markdown("### 📉 Tương Quan Động (Rolling Correlation)")
    c1, p6c2, p6c3 = st.columns([1.5, 2, 1])
    with c1:
        rc_dates = st.date_input(
            "Khoảng thời gian",
            value=(pd.Timestamp(DEFAULT_START).date(), pd.Timestamp(DEFAULT_END).date()),
            min_value=pd.Timestamp("2024-01-01").date(),
            max_value=pd.Timestamp("2024-03-31").date(), format="DD/MM/YYYY", key="rc_dates")
    with p6c2:
        coins = _coin_selector("Coins", "rc_coins")
    with p6c3:
        window_days = st.slider("Cửa sổ (ngày)", 3, 30, 7, key="rc_window")

    if len(rc_dates) != 2:
        st.warning("Chọn đầy đủ ngày bắt đầu và kết thúc."); return
    start_date, end_date = pd.Timestamp(rc_dates[0]), pd.Timestamp(rc_dates[1])

    candles_f = filter_by_date(filter_by_coins(all_candles, coins), start_date, end_date, "open_time")
    pivot = candles_f.pivot_table(index="open_time", columns="coin", values="close")
    returns = pivot.pct_change().dropna()
    if returns.shape[1] < 2:
        st.info("Cần ít nhất 2 coin."); return

    avg_interval = (candles_f["open_time"].max() - candles_f["open_time"].min()) / max(len(candles_f), 1)
    candles_per_day = int(pd.Timedelta(days=1) / avg_interval) if avg_interval > pd.Timedelta(0) else 24
    window = max(int(window_days * candles_per_day), 24)

    x = _ts_labels(returns.index)
    pair_colors = [ACCENT_COLOR, WARNING_COLOR, "#06b6d4", BULL_COLOR, BEAR_COLOR]
    series = []
    ci = 0
    coins_list = returns.columns.tolist()
    for i, c1 in enumerate(coins_list):
        for j, c2 in enumerate(coins_list):
            if i < j:
                rc = returns[c1].rolling(window=window, min_periods=24).corr(returns[c2])
                vals = [round(v, 4) if pd.notna(v) else None for v in rc]
                series.append({
                    "name": f"{c1}–{c2}", "type": "line", "data": vals,
                    "smooth": True, "symbol": "none",
                    "lineStyle": {"color": pair_colors[ci % len(pair_colors)], "width": 1.8},
                })
                ci += 1

    option = {
        "backgroundColor": _BG, "tooltip": _TOOLTIP, "legend": _LEGEND,
        "grid": _GRID,
        "xAxis": {"type": "category", "data": x, "axisLine": _AXIS_LINE,
                  "axisLabel": {**_AXIS_LABEL, "interval": max(0, len(x)//12-1)}, "splitLine": {"show": False}},
        "yAxis": {"type": "value", "name": "Hệ số tương quan", "nameTextStyle": {"color": "#94a3b8"},
                  "axisLabel": _AXIS_LABEL, "splitLine": _SPLIT_LINE, "min": -1.1, "max": 1.1},
        "series": series + [{"type": "line", "markLine": {"data": [{"yAxis": 0}],
                  "lineStyle": {"color": "rgba(255,255,255,0.2)", "type": "dotted"}, "symbol": "none", "label": {"show": False}}}],
        "dataZoom": _DATAZOOM,
    }
    st_echarts(options=option, height="420px", key="rc_ec")


# ──────────────────────────────────────────────────────────────
# PANEL 6 – LONG/SHORT RATIO (ECharts)
# ──────────────────────────────────────────────────────────────
def _render_ls_ratio_panel(all_metrics):
    st.markdown("### ⚖️ Tỷ Lệ Long/Short — Cá Voi vs Tổng Thể")
    c1, p7c2 = st.columns([3, 1])
    with c1:
        ls_dates = st.date_input(
            "Khoảng thời gian",
            value=(pd.Timestamp(DEFAULT_START).date(), pd.Timestamp(DEFAULT_END).date()),
            min_value=pd.Timestamp("2024-01-01").date(),
            max_value=pd.Timestamp("2024-03-31").date(), format="DD/MM/YYYY", key="ls_dates")
    with p7c2:
        coin = st.selectbox("Coin", COINS, key="ls_coin")

    if len(ls_dates) != 2:
        st.warning("Chọn đầy đủ ngày bắt đầu và kết thúc."); return
    start_date, end_date = pd.Timestamp(ls_dates[0]), pd.Timestamp(ls_dates[1])

    coin_df = filter_by_date(
        filter_by_coins(all_metrics, [coin]), start_date, end_date, "create_time"
    ).sort_values("create_time")
    if coin_df.empty:
        st.warning("Không có dữ liệu."); return

    x = _ts_labels(coin_df["create_time"])
    top_ls = [round(v, 4) if pd.notna(v) else None for v in coin_df["count_toptrader_long_short_ratio"]]
    total_ls = [round(v, 4) if pd.notna(v) else None for v in coin_df["count_long_short_ratio"]]
    div = [(t - g if t is not None and g is not None else None) for t, g in zip(top_ls, total_ls)]

    option = {
        "backgroundColor": _BG, "tooltip": _TOOLTIP, "legend": _LEGEND,
        "grid": _GRID,
        "xAxis": {"type": "category", "data": x, "axisLine": _AXIS_LINE,
                  "axisLabel": {**_AXIS_LABEL, "interval": max(0, len(x)//12-1)}, "splitLine": {"show": False}},
        "yAxis": [
            {"type": "value", "name": "Tỷ lệ L/S", "nameTextStyle": {"color": "#94a3b8"},
             "axisLabel": _AXIS_LABEL, "splitLine": _SPLIT_LINE, "axisLine": {"show": False}},
            {"type": "value", "name": "Phân kỳ", "nameTextStyle": {"color": "#94a3b8"},
             "position": "right", "axisLabel": _AXIS_LABEL, "splitLine": {"show": False}, "axisLine": {"show": False}},
        ],
        "series": [
            {"name": "Top Trader L/S", "type": "line", "yAxisIndex": 0, "data": top_ls,
             "smooth": True, "symbol": "none", "lineStyle": {"color": WARNING_COLOR, "width": 2}},
            {"name": "Tổng thể L/S", "type": "line", "yAxisIndex": 0, "data": total_ls,
             "smooth": True, "symbol": "none", "lineStyle": {"color": ACCENT_COLOR, "width": 2}},
            {"name": "Phân kỳ", "type": "line", "yAxisIndex": 1, "data": div,
             "smooth": True, "symbol": "none",
             "lineStyle": {"color": "rgba(124,92,252,0.3)", "width": 0},
             "areaStyle": {"color": "rgba(124,92,252,0.12)"}},
        ],
        "dataZoom": _DATAZOOM,
    }
    st_echarts(options=option, height="500px", key="ls_ec")


# ──────────────────────────────────────────────────────────────
# PANEL 7 – TAKER BUY RATIO + PRICE (ECharts)
# ──────────────────────────────────────────────────────────────
def _render_taker_ratio_panel(all_candles, all_metrics):
    st.markdown("### 💹 Tỷ Lệ Taker Mua/Bán & Giá")
    c1, p8c2 = st.columns([3, 1])
    with c1:
        taker_dates = st.date_input(
            "Khoảng thời gian",
            value=(pd.Timestamp(DEFAULT_START).date(), pd.Timestamp(DEFAULT_END).date()),
            min_value=pd.Timestamp("2024-01-01").date(),
            max_value=pd.Timestamp("2024-03-31").date(), format="DD/MM/YYYY", key="taker_dates")
    with p8c2:
        coin = st.selectbox("Coin", COINS, key="taker_coin")

    if len(taker_dates) != 2:
        st.warning("Chọn đầy đủ ngày bắt đầu và kết thúc."); return
    start_date, end_date = pd.Timestamp(taker_dates[0]), pd.Timestamp(taker_dates[1])
    freq = "1h"

    coin_candles = filter_by_date(
        filter_by_coins(all_candles, [coin]), start_date, end_date, "open_time"
    ).sort_values("open_time")
    coin_metrics = filter_by_date(
        filter_by_coins(all_metrics, [coin]), start_date, end_date, "create_time"
    ).sort_values("create_time")
    if coin_candles.empty:
        st.warning("Không có dữ liệu."); return

    resampled = resample_candles(coin_candles, freq)
    resampled["taker_buy_ratio"] = compute_taker_buy_ratio(resampled)

    x = _ts_labels(resampled["open_time"])
    price_data = [round(v, 2) for v in resampled["close"]]
    tbr_data = [round(v, 4) if pd.notna(v) else None for v in resampled["taker_buy_ratio"]]

    series = [
        {"name": "Giá", "type": "line", "yAxisIndex": 0, "data": price_data,
         "smooth": True, "symbol": "none", "lineStyle": {"color": TEXT_PRIMARY, "width": 1.5}},
        {"name": "Taker Buy Ratio", "type": "line", "yAxisIndex": 1, "data": tbr_data,
         "smooth": True, "symbol": "none", "lineStyle": {"color": BULL_COLOR, "width": 1}},
    ]
    if not coin_metrics.empty:
        tls = [round(v, 4) if pd.notna(v) else None for v in coin_metrics["sum_taker_long_short_vol_ratio"]]
        x_m = _ts_labels(coin_metrics["create_time"])
        # use metrics x-axis if different length — simplify by using candle x
        series.append({"name": "Taker L/S Vol", "type": "line", "yAxisIndex": 1,
                       "data": tls[:len(x)], "smooth": True, "symbol": "none",
                       "lineStyle": {"color": WARNING_COLOR, "width": 1}})

    option = {
        "backgroundColor": _BG, "tooltip": _TOOLTIP, "legend": _LEGEND, "grid": _GRID,
        "xAxis": {"type": "category", "data": x, "axisLine": _AXIS_LINE,
                  "axisLabel": {**_AXIS_LABEL, "interval": max(0, len(x)//12-1)}, "splitLine": {"show": False}},
        "yAxis": [
            {"type": "value", "name": "Giá (USD)", "nameTextStyle": {"color": "#94a3b8"},
             "axisLabel": _AXIS_LABEL, "splitLine": _SPLIT_LINE, "axisLine": {"show": False}, "scale": True},
            {"type": "value", "name": "Tỷ lệ Taker", "nameTextStyle": {"color": "#94a3b8"},
             "position": "right", "axisLabel": _AXIS_LABEL, "splitLine": {"show": False}, "axisLine": {"show": False}},
        ],
        "series": series,
        "dataZoom": _DATAZOOM,
    }
    st_echarts(options=option, height="500px", key="taker_ec")


# ──────────────────────────────────────────────────────────────
# PANEL 8 – SYNCED PRICE + OI + LIQUIDATION (ECharts 3-grid)
# ──────────────────────────────────────────────────────────────
def _render_synced_panel(all_candles, all_metrics, all_liq):
    st.markdown("### 📊 Giá — Open Interest — Thanh Lý (Đồng Bộ)")
    c1, ps2 = st.columns([3, 1])
    with c1:
        sync_dates = st.date_input(
            "Khoảng thời gian",
            value=(pd.Timestamp(DEFAULT_START).date(), pd.Timestamp(DEFAULT_END).date()),
            min_value=pd.Timestamp("2024-01-01").date(),
            max_value=pd.Timestamp("2024-03-31").date(), format="DD/MM/YYYY", key="sync_dates")
    with ps2:
        coin = st.selectbox("Coin", COINS, key="sync_coin")

    if len(sync_dates) != 2:
        st.warning("Chọn đầy đủ ngày bắt đầu và kết thúc."); return
    start_date, end_date = pd.Timestamp(sync_dates[0]), pd.Timestamp(sync_dates[1])
    freq = "1h"

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
        st.warning("Không có dữ liệu."); return

    x = _ts_labels(coin_candles["open_time"])
    ohlc = coin_candles[["open", "close", "low", "high"]].values.tolist()

    # OI data mapped to same x
    oi_vals = [None] * len(x)
    if not coin_metrics.empty:
        oi_map = {t.strftime("%d/%m %H:%M"): v for t, v in
                  zip(coin_metrics["create_time"], coin_metrics["sum_open_interest_value"])}
        oi_vals = [oi_map.get(label, None) for label in x]

    # Liq data
    long_liq_vals = [0] * len(x)
    short_liq_vals = [0] * len(x)
    if not liq_agg.empty:
        coin_liq = liq_agg[liq_agg["coin"] == coin]
        for _, row in coin_liq.iterrows():
            label = row["time_bucket"].strftime("%d/%m %H:%M")
            idx = None
            for k, xl in enumerate(x):
                if xl == label:
                    idx = k; break
            if idx is not None:
                if row["liq_side"] == "Long Liq":
                    long_liq_vals[idx] = round(row["total_value"], 2)
                else:
                    short_liq_vals[idx] = round(-row["total_value"], 2)

    option = {
        "backgroundColor": _BG, "tooltip": _TOOLTIP, "legend": _LEGEND,
        "axisPointer": {"link": [{"xAxisIndex": "all"}]},
        "grid": [
            {"left": "6%", "right": "6%", "top": "8%", "height": "35%"},
            {"left": "6%", "right": "6%", "top": "48%", "height": "18%"},
            {"left": "6%", "right": "6%", "top": "70%", "height": "18%"},
        ],
        "xAxis": [
            {"type": "category", "data": x, "gridIndex": 0, "axisLabel": {"show": False},
             "axisLine": _AXIS_LINE, "splitLine": {"show": False}, "boundaryGap": True},
            {"type": "category", "data": x, "gridIndex": 1, "axisLabel": {"show": False},
             "axisLine": _AXIS_LINE, "splitLine": {"show": False}},
            {"type": "category", "data": x, "gridIndex": 2, "axisLabel": _AXIS_LABEL,
             "axisLine": _AXIS_LINE, "splitLine": {"show": False}},
        ],
        "yAxis": [
            {"type": "value", "gridIndex": 0, "name": "Giá", "nameTextStyle": {"color": "#94a3b8"},
             "axisLabel": _AXIS_LABEL, "splitLine": _SPLIT_LINE, "scale": True},
            {"type": "value", "gridIndex": 1, "name": "OI", "nameTextStyle": {"color": "#94a3b8"},
             "axisLabel": _AXIS_LABEL, "splitLine": _SPLIT_LINE},
            {"type": "value", "gridIndex": 2, "name": "Thanh lý", "nameTextStyle": {"color": "#94a3b8"},
             "axisLabel": _AXIS_LABEL, "splitLine": _SPLIT_LINE},
        ],
        "dataZoom": [
            {"type": "slider", "xAxisIndex": [0, 1, 2], "start": 0, "end": 100,
             "bottom": 5, "height": 18, "fillerColor": "rgba(124,92,252,0.12)",
             "borderColor": "rgba(255,255,255,0.08)",
             "handleStyle": {"color": "#7c5cfc"}, "textStyle": {"color": "#94a3b8"}},
            {"type": "inside", "xAxisIndex": [0, 1, 2]},
        ],
        "series": [
            {"name": "Candle", "type": "candlestick", "xAxisIndex": 0, "yAxisIndex": 0,
             "data": ohlc,
             "itemStyle": {"color": BULL_COLOR, "color0": BEAR_COLOR,
                           "borderColor": BULL_COLOR, "borderColor0": BEAR_COLOR}},
            {"name": "OI", "type": "line", "xAxisIndex": 1, "yAxisIndex": 1,
             "data": oi_vals, "smooth": True, "symbol": "none",
             "lineStyle": {"color": ACCENT_COLOR, "width": 1.5},
             "areaStyle": {"color": "rgba(124,92,252,0.08)"}},
            {"name": "Long Liq", "type": "bar", "xAxisIndex": 2, "yAxisIndex": 2,
             "data": long_liq_vals, "stack": "liq",
             "itemStyle": {"color": BEAR_COLOR}, "barMaxWidth": 8},
            {"name": "Short Liq", "type": "bar", "xAxisIndex": 2, "yAxisIndex": 2,
             "data": short_liq_vals, "stack": "liq",
             "itemStyle": {"color": BULL_COLOR}, "barMaxWidth": 8},
        ],
    }
    st_echarts(options=option, height="900px", key="sync_ec")


# ──────────────────────────────────────────────────────────────
# PANEL 9 – MARKET STATE SIGNALS (ECharts heatmap + bar)
# ──────────────────────────────────────────────────────────────
def _render_market_signals_panel(all_candles, all_metrics, all_liq):
    st.markdown("### 🧠 Tín Hiệu Trạng Thái Thị Trường")
    c1, pm2 = st.columns([3, 1])
    with c1:
        ms_dates = st.date_input(
            "Khoảng thời gian",
            value=(pd.Timestamp(DEFAULT_START).date(), pd.Timestamp(DEFAULT_END).date()),
            min_value=pd.Timestamp("2024-01-01").date(),
            max_value=pd.Timestamp("2024-03-31").date(), format="DD/MM/YYYY", key="ms_dates")
    with pm2:
        coin = st.selectbox("Coin", COINS, key="ms_coin")

    if len(ms_dates) != 2:
        st.warning("Chọn đầy đủ ngày bắt đầu và kết thúc."); return
    start_date, end_date = pd.Timestamp(ms_dates[0]), pd.Timestamp(ms_dates[1])

    coin_candles = filter_by_date(filter_by_coins(all_candles, [coin]), start_date, end_date, "open_time").sort_values("open_time")
    coin_metrics = filter_by_date(filter_by_coins(all_metrics, [coin]), start_date, end_date, "create_time").sort_values("create_time")
    if coin_candles.empty or coin_metrics.empty:
        st.warning("Không đủ dữ liệu."); return

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
    daily_candles["taker_buy_ratio"] = daily_candles["taker_buy_volume"] / daily_candles["volume"].replace(0, np.nan)
    daily_metrics["oi_change_pct"] = daily_metrics["sum_open_interest_value"].pct_change() * 100

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
            if side not in liq_pivot.columns: liq_pivot[side] = 0
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
        st.info("Không đủ dữ liệu sau khi tính toán."); return

    def normalize(s):
        s_min, s_max = s.min(), s.max()
        return 2 * (s - s_min) / (s_max - s_min) - 1 if s_max != s_min else s * 0

    signal_cols = ["price_change_pct", "oi_change_pct", "liq_imbalance", "taker_buy_ratio"]
    signal_labels = ["Biến động giá %", "Biến động OI %", "Mất cân bằng TL", "Tỷ lệ Taker Mua"]
    signal_matrix = pd.DataFrame({col: normalize(merged[col].fillna(0)) for col in signal_cols})

    dates = [str(d) for d in merged["date"]]
    hm_data = []
    for j, col in enumerate(signal_cols):
        for i, val in enumerate(signal_matrix[col]):
            hm_data.append([i, j, round(val, 3)])

    option_hm = {
        "backgroundColor": _BG,
        "tooltip": {"position": "top", "backgroundColor": "#0d1420", "textStyle": {"color": "#e2e8f0"}},
        "grid": {"left": "15%", "right": "5%", "top": "10%", "bottom": "15%"},
        "xAxis": {"type": "category", "data": dates, "axisLabel": {**_AXIS_LABEL, "rotate": 45, "interval": 4}, "splitLine": {"show": False}},
        "yAxis": {"type": "category", "data": signal_labels, "axisLabel": _AXIS_LABEL, "splitLine": {"show": False}},
        "visualMap": {"min": -1, "max": 1, "calculable": True, "orient": "horizontal",
                      "left": "center", "bottom": 0,
                      "inRange": {"color": [BEAR_COLOR, "#0b1120", BULL_COLOR]},
                      "text": ["Bullish", "Bearish"], "textStyle": {"color": "#94a3b8"}},
        "series": [{"type": "heatmap", "data": hm_data,
                    "label": {"show": False},
                    "itemStyle": {"borderColor": "#080c14", "borderWidth": 1}}],
    }
    st_echarts(options=option_hm, height="320px", key="ms_hm_ec")

    # Market state timeline bar
    def classify_state(row):
        score = row["price_change_pct"] + row["oi_change_pct"] * 0.5
        if score > 0.8: return "🟢 Hưng phấn"
        elif score < -0.8: return "🔴 Hoảng loạn"
        else: return "🟡 Bình thường"

    merged["market_state"] = signal_matrix.apply(classify_state, axis=1)
    state_colors_map = {"🟢 Hưng phấn": BULL_COLOR, "🔴 Hoảng loạn": BEAR_COLOR, "🟡 Bình thường": WARNING_COLOR}

    bar_data = [{"value": 1, "itemStyle": {"color": state_colors_map.get(s, WARNING_COLOR)}}
                for s in merged["market_state"]]

    option_bar = {
        "backgroundColor": _BG,
        "tooltip": {"trigger": "axis", "backgroundColor": "#0d1420", "textStyle": {"color": "#e2e8f0"}},
        "grid": {"left": "5%", "right": "5%", "top": "15%", "bottom": "10%"},
        "xAxis": {"type": "category", "data": dates, "axisLabel": {**_AXIS_LABEL, "rotate": 45, "interval": 4}, "splitLine": {"show": False}},
        "yAxis": {"type": "value", "show": False},
        "series": [{"type": "bar", "data": bar_data, "barMaxWidth": 20}],
    }
    st_echarts(options=option_bar, height="150px", key="ms_bar_ec")


# ──────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ──────────────────────────────────────────────────────────────
def render_dashboard(_df=None):
    st.markdown(
        """
        <div style="text-align:center; padding: 0.5rem 0 0.8rem 0;">
            <h1 style="
                background: linear-gradient(90deg, #7c5cfc, #00e5cc, #f59e0b);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-size: 2rem; font-weight: 800;
                margin-bottom: 0.15rem; letter-spacing: -0.5px;
            ">CRYPTO FUTURES DASHBOARD</h1>
            <p style="color: #94a3b8; font-size: 0.85rem; margin:0; padding-bottom: 1rem;">
                ETH · SOL · DOGE &nbsp;|&nbsp; Hợp đồng Vĩnh Cửu &nbsp;|&nbsp; Q1/2024 &nbsp;|&nbsp; Dữ liệu 1H
            </p>
        </div>
        """, unsafe_allow_html=True)

    with st.spinner("Đang tải dữ liệu…"):
        all_candles = load_all_candles()
        all_liq = load_all_liquidations()
        all_metrics = load_all_metrics()

    _render_kpi_strip(all_candles, all_metrics, all_liq)
    st.markdown("---")
    _render_candlestick_panel(all_candles, all_liq)
    st.markdown("---")
    _render_oi_panel(all_metrics)
    st.markdown("---")
    _render_liquidation_echarts(all_liq, all_candles)
    st.markdown("---")

    col_vp, col_corr = st.columns(2)
    with col_vp:
        _render_volume_profile(all_candles)
    with col_corr:
        _render_correlation_panel(all_candles)
    st.markdown("---")

    _render_rolling_correlation_panel(all_candles)
    st.markdown("---")

    col_ls, col_taker = st.columns(2)
    with col_ls:
        _render_ls_ratio_panel(all_metrics)
    with col_taker:
        _render_taker_ratio_panel(all_candles, all_metrics)
    st.markdown("---")

    _render_synced_panel(all_candles, all_metrics, all_liq)
    st.markdown("---")

    _render_market_signals_panel(all_candles, all_metrics, all_liq)

    st.markdown(
        """<div style="text-align:center; padding:2rem 0 1rem 0; opacity:0.35; font-size:0.7rem;">
        Dữ liệu từ Binance · Coin-Margined Futures · Q1/2024
        </div>""", unsafe_allow_html=True)
