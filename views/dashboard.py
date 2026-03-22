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
from pyecharts.commons.utils import JsCode

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
    BULL_COLOR, BEAR_COLOR, ACCENT_COLOR, WARNING_COLOR, VOL_COLOR,
    BG_COLOR, CARD_BG, TEXT_PRIMARY, TEXT_SECONDARY,
    COIN_COLORS, DEFAULT_START, DEFAULT_END,
)

# ── Shared ECharts DARK theme helpers ──
_GRID = {"left": "6%", "right": "6%", "top": "14%", "bottom": "15%", "containLabel": True}
_TOOLTIP = {
    "trigger": "axis",
    "axisPointer": {
        "type": "cross",
        "show": True,
        "crossStyle": {"color": "rgba(255,255,255,0.2)"},
        "link": [{"xAxisIndex": "all"}],   # sync crosshair across all charts
    },
    "backgroundColor": "rgba(15, 23, 42, 0.95)",
    "borderColor": "rgba(124, 92, 252, 0.3)",
    "borderWidth": 1,
    "textStyle": {"color": "#e2e8f0", "fontSize": 15},
}
_TOOLTIP_NONE = {"show": False}
_AXIS_LINE = {"lineStyle": {"color": "rgba(255,255,255,0.1)"}}
_AXIS_LABEL = {"color": "#fafafa", "fontSize": 15}
_SPLIT_LINE = {"lineStyle": {"color": "rgba(255,255,255,0.05)"}}
_DATAZOOM = [
    {"type": "slider", "show": True, "start": 0, "end": 100, "height": 20,
     "bottom": 5, "fillerColor": "rgba(124,92,252,0.15)",
     "borderColor": "rgba(124,92,252,0.2)",
     "handleStyle": {"color": "#7c5cfc"}, "textStyle": {"color": "#fafafa"},
     "dataBackground": {"lineStyle": {"color": "#7c5cfc"}, "areaStyle": {"color": "rgba(124,92,252,0.2)"}},
     "selectedDataBackground": {"lineStyle": {"color": "#00e5cc"}, "areaStyle": {"color": "rgba(0,229,204,0.2)"}}},
    {"type": "inside", "start": 0, "end": 100},
]
_LEGEND = {"top": 8, "textStyle": {"color": "#fafafa"}, "itemGap": 20, "itemIcon": "circle"}
_BG = "#0f172a"  # Dark slate background


def _coin_selector(label, key, default=None):
    return st.multiselect(label, options=COINS, default=default or COINS, key=key)


def _fmt_val(val, unit="$"):
    if val >= 1e9: return f"{unit}{val/1e9:.2f}B"
    if val >= 1e6: return f"{unit}{val/1e6:.2f}M"
    if val >= 1e3: return f"{unit}{val/1e3:.2f}K"
    return f"{unit}{val:.2f}"


def _fmt_price(val):
    """Format price label adaptively by magnitude — handles DOGE $0.08 up to ETH $3000."""
    if val >= 1e3:  return f"${val:,.0f}"
    if val >= 1:    return f"${val:.2f}"
    return f"${val:.4f}"


def _fmt_vol(val):
    """Format volume to K/M/B suffix."""
    if val >= 1e9: return f"{val/1e9:.1f}B"
    if val >= 1e6: return f"{val/1e6:.1f}M"
    if val >= 1e3: return f"{val/1e3:.0f}K"
    return str(int(val))


def _ts_labels(series, fmt="%d/%m %H:%M"):
    return [t.strftime(fmt) for t in series]


# ──────────────────────────────────────────────────────────────
# PANEL 0 – KPI STRIP (no chart changes needed)
# ──────────────────────────────────────────────────────────────
def _render_kpi_strip(all_candles, all_metrics, all_liq):
    st.markdown("### 📈 Tổng quan thị trường")
    
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
    st.markdown("### 🕯️ Biểu đồ nến & khối lượng")
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        cs_dates = st.date_input(
            "Khoảng thời gian",
            value=(pd.Timestamp(DEFAULT_START).date(), pd.Timestamp(DEFAULT_END).date()),
            min_value=pd.Timestamp("2024-01-01").date(),
            max_value=pd.Timestamp("2024-03-31").date(), format="DD/MM/YYYY", key="cs_dates")
    with c2:
        coin = st.selectbox("Coin", COINS, key="cs_coin")
    with c3:
        tf_label = st.selectbox("Khung thời gian", ["1 giờ", "4 giờ", "1 ngày"], key="cs_tf", index=2)
    with c4:
        chart_mode = st.radio("Chế độ", ["Thường", "% Thay đổi"], horizontal=True, key="cs_mode")

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

    # Calculate % change mode
    is_percent_mode = (chart_mode == "% Thay đổi")

    if is_percent_mode:
        # For % mode: calculate from first candle in the selected range
        base_price = r["close"].iloc[0]

        r["pct_change"] = ((r["close"] - base_price) / base_price * 100).round(2)
        r["pct_open"] = ((r["open"] - base_price) / base_price * 100).round(2)
        r["pct_high"] = ((r["high"] - base_price) / base_price * 100).round(2)
        r["pct_low"] = ((r["low"] - base_price) / base_price * 100).round(2)
        # MA always calculated on close price first, then converted
        r["close_ma7"] = compute_ma(r, 7)
        r["close_ma25"] = compute_ma(r, 25)
        r["ma7"] = ((r["close_ma7"] - base_price) / base_price * 100).round(2)
        r["ma25"] = ((r["close_ma25"] - base_price) / base_price * 100).round(2)
        # For candlestick: [open, close, low, high] in % relative to base
        ohlc = r[["pct_open", "pct_change", "pct_low", "pct_high"]].values.tolist()
        y_axis_name = f"% từ {r['open_time'].iloc[0].strftime('%d/%m')}"
    else:
        ohlc = r[["open", "close", "low", "high"]].values.tolist()
        r["ma7"] = compute_ma(r, 7)
        r["ma25"] = compute_ma(r, 25)
        y_axis_name = "Giá (USD)"

    x = _ts_labels(r["open_time"])
    vol = r["volume"].tolist()
    vol_colors = [BULL_COLOR if c >= o else BEAR_COLOR for o, c in zip(r["open"], r["close"])]

    # Scale volume for readable axis labels (e.g. 1.5M instead of 1500000)
    vol_max = max(vol) if vol else 1
    if vol_max >= 1e9:
        vol_scaled = [round(v / 1e9, 2) for v in vol]
        vol_name = "Khối lượng (B)"   # Billions
    elif vol_max >= 1e6:
        vol_scaled = [round(v / 1e6, 2) for v in vol]
        vol_name = "Khối lượng (M)"   # Millions
    else:
        vol_scaled = [round(v / 1e3, 1) for v in vol]
        vol_name = "Khối lượng (K)"   # Thousands

    # Build y-axis label with formatter
    if is_percent_mode:
        y_axis_formatter = "{value}%"
    else:
        y_axis_formatter = None

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
            {"type": "value", "name": y_axis_name, "nameTextStyle": {"color": "#fafafa"},
             "gridIndex": 0, "axisLabel": {**_AXIS_LABEL, "formatter": y_axis_formatter},
             "splitLine": _SPLIT_LINE, "axisLine": {"show": False}, "scale": True},
            {"type": "value", "name": vol_name, "nameTextStyle": {"color": "#fafafa"},
             "gridIndex": 1, "splitLine": _SPLIT_LINE,
             "axisLine": {"show": False}, "scale": True,
             "max": round(vol_max / (1e9 if vol_max >= 1e9 else 1e6 if vol_max >= 1e6 else 1e3), 2),
             "min": 0},

        ],
        "dataZoom": [
            {"type": "slider", "xAxisIndex": [0, 1], "start": 0, "end": 100,
             "bottom": 5, "height": 18, "fillerColor": "rgba(124,92,252,0.12)",
             "borderColor": "rgba(255,255,255,0.08)",
             "handleStyle": {"color": "#7c5cfc"}, "textStyle": {"color": "#fafafa"}},
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
             "data": [{"value": v, "itemStyle": {"color": c}} for v, c in zip(vol_scaled, vol_colors)],
             "barMaxWidth": 8},
        ],
    }
    st_echarts(options=option, height="650px", key=f"candle_ec_v3_{chart_mode}")


# ──────────────────────────────────────────────────────────────
# PANEL 2 – OPEN INTEREST (ECharts)
# ──────────────────────────────────────────────────────────────
def _render_oi_panel(all_metrics):
    st.markdown("### 📊 Open interest")
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    with c1:
        oi_dates = st.date_input(
            "Khoảng thời gian",
            value=(pd.Timestamp(DEFAULT_START).date(), pd.Timestamp(DEFAULT_END).date()),
            min_value=pd.Timestamp("2024-01-01").date(),
            max_value=pd.Timestamp("2024-03-31").date(), format="DD/MM/YYYY", key="oi_dates")
    with c2:
        coins = _coin_selector("Coins", "oi_coins")
    with c3:
        oi_tf = st.selectbox("Khung giờ", ["5p", "4h", "12h", "1 ngày"], index=0, key="oi_tf")

    if len(oi_dates) != 2:
        st.warning("Chọn đầy đủ ngày bắt đầu và kết thúc."); return
    start_date, end_date = pd.Timestamp(oi_dates[0]), pd.Timestamp(oi_dates[1])

    oi_tf_map = {"5p": "1h", "4h": "4h", "12h": "12h", "1 ngày": "1D"}
    freq = oi_tf_map[oi_tf]

    metrics_f = filter_by_date(filter_by_coins(all_metrics, coins), start_date, end_date, "create_time")
    resampled = resample_metrics(metrics_f, freq)

    all_times = sorted(resampled["create_time"].unique())
    x = [t.strftime("%d/%m %H:%M") if isinstance(t, pd.Timestamp) else str(t) for t in all_times]

    # ── Step 1: collect all OI values as % change from first point ──
    coin_data = {}
    for coin in coins:
        df = resampled[resampled["coin"] == coin].sort_values("create_time")
        if df.empty: continue
        t_map = {t: v for t, v in zip(df["create_time"], df["sum_open_interest_value"])}
        base_oi = df["sum_open_interest_value"].dropna().iloc[0] if not df["sum_open_interest_value"].dropna().empty else 1
        if base_oi == 0: base_oi = 1
        vals = []
        for t in all_times:
            v = t_map.get(t)
            if v is None:
                vals.append(None)
            else:
                vals.append(round((v - base_oi) / base_oi * 100, 2))
        coin_data[coin] = vals

    # ── Step 2: build series ──
    series = []
    for coin, raw_vals in coin_data.items():
        scaled_vals = raw_vals[:]
        first_idx = next((i for i, v in enumerate(scaled_vals) if v is not None), None)
        if first_idx is not None:
            scaled_vals[first_idx] = 0.0
        color = COIN_COLORS.get(coin, ACCENT_COLOR)
        series.append({
            "name": coin, "type": "line", "data": scaled_vals, "smooth": True, "symbol": "none",
            "lineStyle": {"color": color, "width": 2},
            "itemStyle": {"color": color},
            "areaStyle": {"color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                "colorStops": [
                    {"offset": 0, "color": f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.18)"},
                    # {"offset": 1, "color": "rgba(0,0,0,0)"},
                ]}},
        })

    option = {
        "backgroundColor": _BG, "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "cross", "show": True, "crossStyle": {"color": "rgba(255,255,255,0.2)"}, "link": [{"xAxisIndex": "all"}]},
            "backgroundColor": "rgba(15, 23, 42, 0.95)",
            "borderColor": "rgba(124, 92, 252, 0.3)",
            "borderWidth": 1,
            "textStyle": {"color": "#e2e8f0", "fontSize": 15},
            "formatter": JsCode(
                "function(params){"
                "  if(!params||!params.length)return '';"
                "  return '<div style=\"font-size:13px;color:#94a3b8;margin-bottom:4px\">'+params[0].axisValue+'</div>'+"
                "    params.map(function(p){return '<div style=\"color:'+p.color+';font-weight:bold\">'+p.seriesName+': '+p.value+'%</div>';}).join('');"
                "}"
            ).js_code,
        }, "legend": _LEGEND,
        "grid": _GRID,
        "xAxis": {"type": "category", "data": x, "axisLine": _AXIS_LINE,
                  "axisLabel": {**_AXIS_LABEL, "interval": max(0, len(x)//12-1)}, "splitLine": {"show": False}},
        "yAxis": {"type": "value", "name": "% thay đổi", "nameTextStyle": {"color": "#fafafa"},
                  "axisLabel": {**_AXIS_LABEL, "formatter": "{value}%"},
                  "splitLine": _SPLIT_LINE, "axisLine": {"show": False}},
        "series": series,
        "dataZoom": _DATAZOOM,
    }
    st_echarts(options=option, height="500px", key=f"oi_ec_{freq}")


# ──────────────────────────────────────────────────────────────
# PANEL 3 – LIQUIDATION (ECharts – Coinglass style)
# ──────────────────────────────────────────────────────────────
def _render_liquidation_echarts(all_liq, all_candles):
    st.markdown("### Biểu đồ thanh lý")
    lc1, lc2, lc3 = st.columns([1, 2, 1])
    with lc1:
        liq_coin = st.selectbox("Coin", COINS, key="liq_coin")
    with lc2:
        liq_dates = st.date_input(
            "Khoảng thời gian",
            value=(pd.Timestamp(DEFAULT_START).date(), pd.Timestamp(DEFAULT_END).date()),
            min_value=pd.Timestamp("2024-01-01").date(),
            max_value=pd.Timestamp("2024-03-31").date(), format="DD/MM/YYYY", key="liq_dates")
    with lc3:
        liq_tf = st.selectbox("Khung giờ", ["All", "1h", "4h", "12h", "1 ngày"], index=3, key="liq_tf")

    if len(liq_dates) != 2:
        st.info("Chọn đầy đủ ngày bắt đầu và kết thúc."); return

    liq_start, liq_end = pd.Timestamp(liq_dates[0]), pd.Timestamp(liq_dates[1])
    date_range_days = (liq_end - liq_start).days

    # Use selected timeframe
    liq_tf_map = {"All": "all", "1h": "1h", "4h": "4h", "12h": "12h", "1 ngày": "1D"}
    bucket_freq = liq_tf_map[liq_tf]

    # Mode "All": Show all individual liquidations (cascade effect)
    if bucket_freq == "all":
        liq_raw = filter_by_date(filter_by_coins(all_liq, [liq_coin]), liq_start, liq_end, "time")
        if liq_raw.empty:
            st.warning("Không có dữ liệu thanh lý trong khoảng này."); return

        # Aggregate by 10-minute windows for cascade view
        liq_sorted = liq_raw.sort_values("time").copy()
        liq_sorted["time_bucket"] = liq_sorted["time"].dt.floor("10min")

        # Calculate value for each liquidation
        liq_sorted["liq_value_calc"] = liq_sorted["original_quantity"] * liq_sorted["average_price"]

        # Aggregate by time bucket and side
        agg = liq_sorted.groupby(["time_bucket", "liq_side"]).agg(
            total_value=("liq_value_calc", "sum"),
            count=("time", "count")
        ).reset_index()

        if agg.empty:
            st.warning("Không có dữ liệu thanh lý hợp lệ."); return

        # Prepare data for chart
        all_buckets = sorted(agg["time_bucket"].unique())
        x_labels = [t.strftime("%d/%m %H:%M") for t in all_buckets]

        long_map, short_map = {}, {}
        for _, row in agg.iterrows():
            t, v = row["time_bucket"], row["total_value"] if pd.notna(row["total_value"]) else 0
            if row["liq_side"] == "Long Liq":
                long_map[t] = long_map.get(t, 0) + v
            else:
                short_map[t] = short_map.get(t, 0) + v

        long_vals = [long_map.get(t, 0) / 1e6 for t in all_buckets]
        short_vals = [short_map.get(t, 0) / 1e6 for t in all_buckets]

        # Show as line chart with markers to visualize cascade
        stacked_vals = [l + s for l, s in zip(long_vals, short_vals)]
        max_liq = max(stacked_vals) if stacked_vals else 0.1

        option = {
            "backgroundColor": _BG,
            "grid": {"left": "6%", "right": "6%", "top": "14%", "bottom": "18%"},
            "tooltip": _TOOLTIP,
            "legend": {**_LEGEND, "data": ["Long Liq", "Short Liq", "Tổng"]},
            "xAxis": {
                "type": "category",
                "data": x_labels,
                "axisLine": _AXIS_LINE,
                "axisLabel": {
                    **_AXIS_LABEL,
                    "rotate": 45,
                    "interval": max(0, len(x_labels)//20 - 1)
                },
                "splitLine": {"show": False}
            },
            "yAxis": {
                "type": "value",
                "name": "Giá trị (M USD)",
                "nameTextStyle": {"color": "#fafafa", "fontSize": 15},
                "axisLabel": {**_AXIS_LABEL, "formatter": "${value}M"},
                "axisLine": {"show": False},
                "splitLine": _SPLIT_LINE,
                "max": round(max_liq * 1.15, 2)
            },
            "series": [
                {
                    "name": "Long Liq",
                    "type": "line",
                    "stack": "total",
                    "symbol": "circle",
                    "symbolSize": 6,
                    "data": long_vals,
                    "itemStyle": {"color": "#00e5cc"},
                    "areaStyle": {"opacity": 0.4},
                    "smooth": True
                },
                {
                    "name": "Short Liq",
                    "type": "line",
                    "stack": "total",
                    "symbol": "circle",
                    "symbolSize": 6,
                    "data": short_vals,
                    "itemStyle": {"color": "#ff3d71"},
                    "areaStyle": {"opacity": 0.4},
                    "smooth": True
                }
            ],
            "dataZoom": [
                {"type": "inside", "start": 0, "end": 100},
                {"type": "slider", "start": 0, "end": 100}
            ],
        }
        st_echarts(options=option, height="650px", key="liq_echarts_all")

        # Show total count from aggregated data
        total_long_count = agg[agg["liq_side"] == "Long Liq"]["count"].sum()
        total_short_count = agg[agg["liq_side"] == "Short Liq"]["count"].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("🟢 Long Liq Count", f"{total_long_count}")
        c2.metric("🔴 Short Liq Count", f"{total_short_count}")
        c3.metric("📊 Tổng sự kiện", f"{total_long_count + total_short_count}")
        return

    # Set format based on timeframe
    if bucket_freq == "1D":
        x_fmt = "%d/%m"
    elif bucket_freq == "12h":
        x_fmt = "%d/%m %Hh"
    elif bucket_freq == "4h":
        x_fmt = "%d/%m %Hh"
    else:
        x_fmt = "%d/%m %Hh" if date_range_days > 7 else "%H:%M"

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

    # Calculate liquidation imbalance: (Long - Short) / (Long + Short) * 100
    # Positive = Long dominance, Negative = Short dominance
    imbalance_vals = []
    for l, s in zip(long_vals, short_vals):
        total = l + s
        if total > 0:
            imbalance_vals.append(round((l - s) / total * 100, 1))
        else:
            imbalance_vals.append(0)

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
        "tooltip": {
            **_TOOLTIP,
            "axisPointer": {
                "type": "cross",
                "show": True,                         # always show crosshair line
                "crossStyle": {"color": "rgba(255,255,255,0.2)"},
                "link": [{"xAxisIndex": "all"}],       # sync across both rows
            },
        },
        "legend": {
            **_LEGEND,
            "data": [
                {"name": "Short", "icon": "roundRect", "itemStyle": {"color": "#ff3d71"}},
                {"name": "Long", "icon": "roundRect", "itemStyle": {"color": "#00e5cc"}},
                {"name": "Mất cân bằng %", "icon": "circle", "itemStyle": {"color": "#a855f7"}},
                {"name": f"Giá {price_coin}", "icon": "circle", "itemStyle": {"color": WARNING_COLOR}},
            ]
        },
        # Two-row grid: row 0 = Imbalance %, row 1 = Liquidation + Price (no overlap)
        "grid": [
            {"left": "6%", "right": "6%", "top": "8%", "height": "28%"},
            {"left": "6%", "right": "6%", "top": "46%", "height": "42%"},
        ],
        "xAxis": [
            {"type": "category", "data": x_labels, "gridIndex": 0,
             "axisLine": _AXIS_LINE, "axisLabel": {"show": False},
             "splitLine": {"show": False}},
            {"type": "category", "data": x_labels, "gridIndex": 1,
             "axisLine": _AXIS_LINE,
             "axisLabel": {**_AXIS_LABEL, "interval": max(0, len(x_labels)//12-1)},
             "splitLine": {"show": False}},
        ],
        "yAxis": [
            # Row 0 — Imbalance %
            {"type": "value", "name": "Mất cân bằng %", "gridIndex": 0,
             "nameTextStyle": {"color": "#a855f7", "fontSize": 15},
             "axisLabel": {**_AXIS_LABEL, "formatter": "{value}%"},
             "axisLine": {"show": False}, "splitLine": {"show": False},
             "min": -100, "max": 100},
            # Row 1 — Thanh lý (left)
            {"type": "value", "name": "Thanh lý (M USD)", "gridIndex": 1,
             "nameTextStyle": {"color": "#fafafa", "fontSize": 15},
             "axisLabel": {**_AXIS_LABEL, "formatter": "{value}M"},
             "axisLine": {"show": False}, "splitLine": _SPLIT_LINE,
             "max": round(max_liq * 1.15, 4)},
            # Row 1 — Price (right)
            {"type": "value", "name": f"Giá {price_coin}", "gridIndex": 1,
             "nameTextStyle": {"color": "#fafafa", "fontSize": 15},
             "position": "right",
             "axisLabel": {**_AXIS_LABEL, "formatter": "${value}"},
             "axisLine": {"show": False}, "splitLine": {"show": False},
             "min": round(price_min - price_pad, 0), "max": round(price_max + price_pad, 0)},
        ],
        "series": [
            # Imbalance in top row
            {"name": "Mất cân bằng (L-S)", "type": "line",
             "xAxisIndex": 0, "yAxisIndex": 0,
             "data": imbalance_vals,
             "smooth": True, "symbol": "circle", "symbolSize": 6,
             "lineStyle": {"color": "#a855f7", "width": 2, "type": "dashed"},
             "itemStyle": {"color": "#a855f7"}, "z": 5, "connectNulls": True},
            # Short / Long in bottom row
            {"name": "Short", "type": "line", "stack": "liq",
             "xAxisIndex": 1, "yAxisIndex": 1,
             "data": short_vals,
             "itemStyle": {"color": "#ff3d71", "opacity": 0.88},
             "areaStyle": {"opacity": 0.5}, "smooth": True, "symbol": "none"},
            {"name": "Long", "type": "line", "stack": "liq",
             "xAxisIndex": 1, "yAxisIndex": 1,
             "data": long_vals,
             "itemStyle": {"color": "#00e5cc", "opacity": 0.88},
             "areaStyle": {"opacity": 0.5}, "smooth": True, "symbol": "none"},
            # Price in bottom row
            {"name": f"{price_coin} Price", "type": "line",
             "xAxisIndex": 1, "yAxisIndex": 2,
             "data": price_vals_clean,
             "smooth": True, "symbol": "none",
             "lineStyle": {"color": "#f59e0b", "width": 2}, "connectNulls": True, "z": 10},
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
# PANEL 3b – LIQUIDATION IMBALANCE (Price + Imbalance %)
# ──────────────────────────────────────────────────────────────
def _render_liq_imbalance_panel(all_liq, all_candles):
    # st.markdown("### ⚖️ Chỉ Số Lệch Thanh Lý (Liquidation Imbalance)")
    lc1, lc2 = st.columns([1, 2])
    with lc1:
        liq_coin = st.selectbox("Coin", COINS, key="imb_coin")
    with lc2:
        liq_dates = st.date_input(
            "Khoảng thời gian",
            value=(pd.Timestamp(DEFAULT_START).date(), pd.Timestamp(DEFAULT_END).date()),
            min_value=pd.Timestamp("2024-01-01").date(),
            max_value=pd.Timestamp("2024-03-31").date(), format="DD/MM/YYYY", key="imb_dates")

    if len(liq_dates) != 2:
        st.info("Chọn đầy đủ ngày bắt đầu và kết thúc."); return

    liq_start, liq_end = pd.Timestamp(liq_dates[0]), pd.Timestamp(liq_dates[1])
    bucket_freq = "1h" 
    x_fmt = "%d/%m %Hh"

    liq_raw = filter_by_date(filter_by_coins(all_liq, [liq_coin]), liq_start, liq_end, "time")
    if liq_raw.empty:
        st.warning("Không có dữ liệu thanh lý."); return

    agg = aggregate_liquidations(liq_raw, bucket_freq)
    all_buckets = sorted(agg["time_bucket"].unique())
    x_labels = [t.strftime(x_fmt) for t in all_buckets]

    long_map, short_map = {}, {}
    for _, row in agg.iterrows():
        t, v = row["time_bucket"], row["total_value"] or 0
        if row["liq_side"] == "Long Liq": long_map[t] = long_map.get(t, 0) + v
        else: short_map[t] = short_map.get(t, 0) + v

    long_vals = [long_map.get(t, 0) / 1e6 for t in all_buckets]
    short_vals = [short_map.get(t, 0) / 1e6 for t in all_buckets]

    imbalance_vals = []
    for l, s in zip(long_vals, short_vals):
        total = l + s
        val = round((l - s) / total * 100, 1) if total > 0 else 0
        color = BULL_COLOR if val > 0 else (BEAR_COLOR if val < 0 else "#94a3b8")
        imbalance_vals.append({
            "value": val,
            "itemStyle": {"color": color}
        })

    candles_f = filter_by_date(filter_by_coins(all_candles, [liq_coin]), liq_start, liq_end, "open_time").sort_values("open_time")
    price_resampled = resample_candles(candles_f, bucket_freq) if not candles_f.empty else pd.DataFrame()

    price_vals = [None] * len(all_buckets)
    if not price_resampled.empty:
        pt_map = {t.floor(bucket_freq): c for t, c in zip(price_resampled["open_time"], price_resampled["close"])}
        price_vals = [pt_map.get(t, None) for t in all_buckets]

    p_valid = [v for v in price_vals if v is not None]
    price_min, price_max = min(p_valid) if p_valid else 0, max(p_valid) if p_valid else 0
    price_pad = (price_max - price_min) * 0.1

    option = {
        "backgroundColor": _BG, "tooltip": _TOOLTIP, "legend": {**_LEGEND, "data": ["Imbalance %", f"{liq_coin} Price"]},
        "grid": {"left": "6%", "right": "6%", "top": "14%", "bottom": "12%"},
        "xAxis": {"type": "category", "data": x_labels, "axisLine": _AXIS_LINE, "axisLabel": _AXIS_LABEL},
        "yAxis": [
            {"type": "value", "name": "Imbalance %", "min": -100, "max": 100, "axisLabel": {**_AXIS_LABEL, "formatter": "{value}%"}, "splitLine": _SPLIT_LINE},
            {"type": "value", "name": "Price", "position": "right", "min": round(price_min - price_pad, 0), "max": round(price_max + price_pad, 0), "axisLabel": _AXIS_LABEL, "splitLine": {"show": False}},
        ],
        "series": [
            {
                "name": "Imbalance %", "type": "bar", "data": imbalance_vals, "barMaxWidth": 20,
                "markLine": {
                    "silent": True, "symbol": "none",
                    "data": [{"yAxis": 0, "lineStyle": {"color": "#fafafa", "type": "dashed", "width": 1}}]
                }, "z": 5
            },
            {"name": f"{liq_coin} Price", "type": "line", "yAxisIndex": 1, "data": price_vals, "smooth": True, "lineStyle": {"color": WARNING_COLOR, "width": 2}, "symbol": "none", "z": 10, "connectNulls": True},
        ],
        "dataZoom": _DATAZOOM,
    }
    st_echarts(options=option, height="500px", key="liq_imb_ec")


# ──────────────────────────────────────────────────────────────
# PANEL 4 – VOLUME PROFILE (ECharts)
# ──────────────────────────────────────────────────────────────
def _render_volume_profile(all_candles, num_bins=50):
    st.markdown("### 📐 Hồ sơ khối lượng")
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

    # Keep original row index so we can find POC position reliably
    vol_profile = vol_profile.reset_index(drop=True)
    poc_row_idx = int(vol_profile["volume"].idxmax())
    poc_price = float(vol_profile.loc[poc_row_idx, "price_level"])

    total_vol = float(vol_profile["volume"].sum())
    if total_vol == 0:
        st.warning("Không có dữ liệu khối lượng."); return

    # ── Standard Volume Profile VA algorithm (starts from POC, expands outward) ──
    # 1. POC: bin with highest volume (already found above as poc_row_idx)
    # 2. Sort by price and expand outward from POC toward higher-volume adjacent bins
    levels = vol_profile.sort_values("price_level").reset_index(drop=True)
    n = len(levels)
    poc_pos = int(levels[levels["price_level"] == poc_price].index[0])

    va_start, va_end = poc_pos, poc_pos
    va_sum = float(levels.loc[poc_pos, "volume"])
    target = total_vol * 0.7

    while va_sum < target and (va_start > 0 or va_end < n - 1):
        vol_left  = float(levels.loc[va_start, "volume"]) if va_start > 0 else -1
        vol_right = float(levels.loc[va_end,   "volume"]) if va_end   < n-1 else -1
        if vol_left >= vol_right and va_start > 0:
            va_start -= 1
            va_sum += vol_left
        elif va_end < n - 1:
            va_end += 1
            va_sum += vol_right
        else:
            break

    va_low  = float(levels.loc[va_start, "price_level"])
    va_high = float(levels.loc[va_end,   "price_level"])

    y_labels = [_fmt_price(pl) for pl in vol_profile["price_level"]]

    # Scale volume to readable K/M for x-axis
    raw_vols = vol_profile["volume"].tolist()
    vol_max = max(raw_vols) if raw_vols else 1
    if vol_max >= 1e9:
        vol_scaled = [round(v / 1e9, 2) for v in raw_vols]
        vol_suffix = "B"
    elif vol_max >= 1e6:
        vol_scaled = [round(v / 1e6, 2) for v in raw_vols]
        vol_suffix = "M"
    else:
        vol_scaled = [round(v / 1e3, 1) for v in raw_vols]
        vol_suffix = "K"

    bar_data = []
    for i, (_, row) in enumerate(vol_profile.iterrows()):
        pl = float(row["price_level"])
        coin_color = COIN_COLORS.get(coin, ACCENT_COLOR)
        if va_low <= pl <= va_high:
            color = coin_color
        else:
            color = f"rgba({int(coin_color[1:3],16)},{int(coin_color[3:5],16)},{int(coin_color[5:7],16)},0.12)"
        bar_data.append({
            "value": [vol_scaled[i], _fmt_price(pl)],
            "itemStyle": {"color": color}
        })

    # poc_row_idx is the exact category index — no string lookup needed
    poc_idx = poc_row_idx

    option = {
        "backgroundColor": _BG, "tooltip": {**_TOOLTIP, "trigger": "axis"},
        "grid": {"left": "12%", "right": "6%", "top": "10%", "bottom": "10%"},
        "xAxis": {"type": "value", "name": f"Khối lượng ({vol_suffix} USD)", "nameTextStyle": {"color": "#fafafa"},
                  "axisLabel": {**_AXIS_LABEL, "formatter": f"{{value}}{vol_suffix}"}, "splitLine": _SPLIT_LINE},
        "yAxis": {"type": "category", "data": y_labels, "axisLine": _AXIS_LINE, "axisLabel": _AXIS_LABEL},
        "series": [
            {"type": "bar", "data": bar_data, "barMaxWidth": 12},
            {
                "type": "line",
                "markLine": {
                    "silent": True,
                    "symbol": "none",
                    "data": [{"yAxis": poc_idx}],
                    "label": {
                        "formatter": f"POC {_fmt_price(poc_price)}",
                        "color": WARNING_COLOR,
                        "fontWeight": "bold",
                        "backgroundColor": "rgba(245,158,11,0.15)",
                        "padding": [3, 6],
                        "borderRadius": 4,
                        "position": "insideEndTop",
                    },
                    "lineStyle": {"color": WARNING_COLOR, "type": "dashed", "width": 2},
                },
                "data": [],
                "z": 10,
                "symbol": "none",
            },
        ],
    }
    st_echarts(options=option, height="550px", key="vp_ec")


# ──────────────────────────────────────────────────────────────
# PANEL 5 – CORRELATION HEATMAP (ECharts)
# ──────────────────────────────────────────────────────────────
def _render_correlation_panel(all_candles):
    st.markdown("### 🔗 Ma trận tương quan giá")
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
        "visualMap": {"min": 0.2, "max": 0.8, "calculable": True, "orient": "horizontal",
                      "left": "center", "bottom": 0,
                      "inRange": {"color": [BEAR_COLOR, "#0b1120", BULL_COLOR]},
                      "textStyle": {"color": "#fafafa"}},
        "series": [{"type": "heatmap", "data": hm_data,
                    "label": {"show": True, "formatter": "{@[2]}", "color": "#e2e8f0", "fontSize": 14},
                    "itemStyle": {"borderColor": "#080c14", "borderWidth": 2}}],
    }
    st_echarts(options=option, height="420px", key="corr_ec")


# ──────────────────────────────────────────────────────────────
# PANEL 5b – ROLLING CORRELATION (ECharts)
# ──────────────────────────────────────────────────────────────
def _render_rolling_correlation_panel(all_candles):
    st.markdown("### 📉 Tương quan động")
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
    n = len(x)
    # Auto-scroll slider: show exactly `window_days` days at the start
    _start = max(0.0, min(100.0, (window_days / n * 100) if n > 0 else 0))
    _DATAZOOM_AUTO = [
        {"type": "slider", "show": True, "start": round(_start, 2), "end": 100,
         "height": 20, "bottom": 5,
         "fillerColor": "rgba(124,92,252,0.15)",
         "borderColor": "rgba(124,92,252,0.2)",
         "handleStyle": {"color": "#7c5cfc"}, "textStyle": {"color": "#fafafa"},
         "dataBackground": {"lineStyle": {"color": "#7c5cfc"}, "areaStyle": {"color": "rgba(124,92,252,0.2)"}},
         "selectedDataBackground": {"lineStyle": {"color": "#00e5cc"}, "areaStyle": {"color": "rgba(0,229,204,0.2)"}}},
        {"type": "inside", "start": 0, "end": 100},
    ]

    series = []
    coins_list = returns.columns.tolist()

    # Distinct color palette for known coin pairs
    pair_colors = {
        "ETH-SOL":   "#f59e0b",   # amber
        "DOGE-ETH":  "#00e5cc",   # teal
        "DOGE-SOL":  "#a855f7",   # purple
    }
    # Fallback cycle for unknown pairs
    _color_cycle = ["#f59e0b", "#00e5cc", "#a855f7", "#7c5cfc", "#ff3d71", "#10b981"]
    pair_idx = 0
    for i, c1 in enumerate(coins_list):
        for j, c2 in enumerate(coins_list):
            if i < j:
                rc = returns[c1].rolling(window=window, min_periods=24).corr(returns[c2])
                vals = [round(v, 4) if pd.notna(v) else None for v in rc]
                pair_key = f"{c1}-{c2}"
                pair_color = pair_colors.get(pair_key, _color_cycle[pair_idx % len(_color_cycle)])
                pair_idx += 1
                series.append({
                    "name": f"{c1}–{c2}", "type": "line", "data": vals,
                    "smooth": True, "symbol": "none",
                    "lineStyle": {"color": pair_color, "width": 2},
                    "itemStyle": {"color": pair_color},
                })

    # Tooltip — color matches each series line
    _ROLLING_TOOLTIP = {
        "trigger": "axis",
        "axisPointer": {
            "type": "cross",
            "show": True,
            "crossStyle": {"color": "rgba(255,255,255,0.2)"},
            "link": [{"xAxisIndex": "all"}],
        },
        "backgroundColor": "rgba(15, 23, 42, 0.95)",
        "borderColor": "rgba(124, 92, 252, 0.3)",
        "borderWidth": 1,
        "textStyle": {"color": "#e2e8f0", "fontSize": 15},
        "formatter": JsCode(
            "function(params) {"
            "  if (!params || !params.length) return '';"
            "  return '<div style=\"font-size:13px;color:#94a3b8;margin-bottom:4px\">' + params[0].axisValue + '</div>' +"
            "    params.map(function(p){ return '<div style=\"color:'+p.color+';font-weight:bold\">'+p.seriesName+': '+p.value+'</div>'; }).join('');"
            "}"
        ).js_code,
    }

    option = {
        "backgroundColor": _BG, "tooltip": _ROLLING_TOOLTIP, "legend": _LEGEND,
        "grid": _GRID,
        "xAxis": {"type": "category", "data": x, "axisLine": _AXIS_LINE,
                  "axisLabel": {**_AXIS_LABEL, "interval": max(0, len(x)//12-1)}, "splitLine": {"show": False}},
        "yAxis": {"type": "value", "name": "Hệ số tương quan", "nameTextStyle": {"color": "#fafafa"},
                  "axisLabel": _AXIS_LABEL, "splitLine": _SPLIT_LINE, "min": 0, "max": 1},
        "series": series + [{"type": "line", "markLine": {"data": [{"yAxis": 0}],
                  "lineStyle": {"color": "rgba(255,255,255,0.2)", "type": "dotted"}, "symbol": "none", "label": {"show": False}}}],
        "dataZoom": _DATAZOOM_AUTO,
    }
    st_echarts(options=option, height="420px", key=f"rc_ec_{window_days}")


# ──────────────────────────────────────────────────────────────
# PANEL 6 – LONG/SHORT RATIO (ECharts)
# ──────────────────────────────────────────────────────────────
def _render_ls_ratio_panel(all_metrics):
    st.markdown("### ⚖️ Tỷ lệ long/short — cá voi vs tổng thể")
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
        "backgroundColor": _BG, "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "cross", "show": True, "crossStyle": {"color": "rgba(255,255,255,0.2)"}, "link": [{"xAxisIndex": "all"}]},
            "backgroundColor": "rgba(15, 23, 42, 0.95)",
            "borderColor": "rgba(124, 92, 252, 0.3)",
            "borderWidth": 1,
            "textStyle": {"color": "#e2e8f0", "fontSize": 15},
            "formatter": JsCode(
                "function(params){"
                "  if(!params||!params.length)return '';"
                "  return '<div style=\"font-size:13px;color:#94a3b8;margin-bottom:4px\">'+params[0].axisValue+'</div>'+"
                "    params.map(function(p){return '<div style=\"color:'+p.color+';font-weight:bold\">'+p.seriesName+': '+p.value+'%</div>';}).join('');"
                "}"
            ).js_code,
        }, "legend": _LEGEND,
        "grid": _GRID,
        "xAxis": {"type": "category", "data": x, "axisLine": _AXIS_LINE,
                  "axisLabel": {**_AXIS_LABEL, "interval": max(0, len(x)//12-1)}, "splitLine": {"show": False}},
        "yAxis": [
            {"type": "value", "name": "Tỷ lệ L/S", "nameTextStyle": {"color": "#fafafa"},
             "axisLabel": _AXIS_LABEL, "splitLine": _SPLIT_LINE, "axisLine": {"show": False}},
            {"type": "value", "name": "Phân kỳ", "nameTextStyle": {"color": "#fafafa"},
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
    st.markdown("### 💹 Tỷ lệ taker mua/bán & giá")
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

    coin_color = COIN_COLORS.get(coin, ACCENT_COLOR)
    series = [
        {"name": "Giá", "type": "line", "yAxisIndex": 0, "data": price_data,
         "smooth": True, "symbol": "none",
         "lineStyle": {"color": coin_color, "width": 2},
         "itemStyle": {"color": coin_color}},
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
            {"type": "value", "name": "Giá (USD)", "nameTextStyle": {"color": "#fafafa"},
             "axisLabel": _AXIS_LABEL, "splitLine": _SPLIT_LINE, "axisLine": {"show": False}, "scale": True},
            {"type": "value", "name": "Tỷ lệ Taker", "nameTextStyle": {"color": "#fafafa"},
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
    st.markdown("### 📊 Giá — open interest")
    c1, ps2, pi3 = st.columns([2, 1, 1])
    with c1:
        sync_dates = st.date_input(
            "Khoảng thời gian",
            value=(pd.Timestamp(DEFAULT_START).date(), pd.Timestamp(DEFAULT_END).date()),
            min_value=pd.Timestamp("2024-01-01").date(),
            max_value=pd.Timestamp("2024-03-31").date(), format="DD/MM/YYYY", key="sync_dates")
    with ps2:
        coin = st.selectbox("Coin", COINS, key="sync_coin")
    with pi3:
        interval_label = st.selectbox("Khung thời gian", ["1h", "4h", "12h", "1 ngày"], index=0, key="sync_interval")
        freq = "1h" if interval_label == "1h" else "4h" if interval_label == "4h" else "12h" if interval_label == "12h" else "1D"

    if len(sync_dates) != 2:
        st.warning("Chọn đầy đủ ngày bắt đầu và kết thúc."); return
    start_date, end_date = pd.Timestamp(sync_dates[0]), pd.Timestamp(sync_dates[1])

    # Filter and Resample
    raw_candles = filter_by_date(filter_by_coins(all_candles, [coin]), start_date, end_date, "open_time")
    coin_candles = resample_candles(raw_candles, freq).sort_values("open_time")
    
    raw_metrics = filter_by_date(filter_by_coins(all_metrics, [coin]), start_date, end_date, "create_time")
    coin_metrics = resample_metrics(raw_metrics, freq).sort_values("create_time")

    if coin_candles.empty:
        st.warning("Không có dữ liệu."); return

    # Merge price and OI on time for perfect alignment using asof for robustness
    merged = pd.merge_asof(
        coin_candles[['open_time', 'close']].sort_values('open_time'),
        coin_metrics[['create_time', 'sum_open_interest_value']].sort_values('create_time'),
        left_on='open_time', right_on='create_time', direction='backward'
    )
    merged['sum_open_interest_value'] = merged['sum_open_interest_value'].ffill().bfill()
    
    x = _ts_labels(merged['open_time'])
    price_vals = merged['close'].tolist()
    oi_vals = merged['sum_open_interest_value'].tolist()
    
    # Dynamic OI series type: bar if points < 60 (increased for better usability)
    oi_series_type = "bar" if len(x) < 60 else "line"

    # Calculate scaling for vertical separation
    p_min, p_max = min(price_vals), max(price_vals)
    p_range = p_max - p_min if p_max > p_min else p_max or 1
    
    oi_clean = [v for v in oi_vals if v is not None]
    if oi_clean:
        o_min, o_max = min(oi_clean), max(oi_clean)
        o_range = o_max - o_min if o_max > o_min else o_max or 1
    else:
        o_min, o_max, o_range = 0, 1, 1

    coin_color = COIN_COLORS.get(coin, ACCENT_COLOR)
    option = {
        "backgroundColor": _BG, "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "cross", "show": True, "crossStyle": {"color": "rgba(255,255,255,0.2)"}, "link": [{"xAxisIndex": "all"}]},
            "backgroundColor": "rgba(15, 23, 42, 0.95)",
            "borderColor": "rgba(124, 92, 252, 0.3)",
            "borderWidth": 1,
            "textStyle": {"color": "#e2e8f0", "fontSize": 15},
            "formatter": JsCode(
                "function(params){"
                "  if(!params||!params.length)return '';"
                "  return '<div style=\"font-size:13px;color:#94a3b8;margin-bottom:4px\">'+params[0].axisValue+'</div>'+"
                "    params.map(function(p){return '<div style=\"color:'+p.color+';font-weight:bold\">'+p.seriesName+': '+p.value+'</div>';}).join('');"
                "}"
            ).js_code,
        }, "legend": _LEGEND,
        "grid": {"left": "6%", "right": "6%", "top": "12%", "bottom": "12%"},
        "xAxis": {"type": "category", "data": x, "axisLine": _AXIS_LINE,
                  "axisLabel": {**_AXIS_LABEL, "interval": max(0, len(x)//12-1)}},
        "yAxis": [
            {"type": "value", "name": "Giá (USD)", "nameTextStyle": {"color": WARNING_COLOR},
             "axisLabel": _AXIS_LABEL, "splitLine": _SPLIT_LINE, "scale": True,
             "min": round(p_min - p_range * 0.05, 2), "max": round(p_max + p_range * 0.05, 2)},
            {"type": "value", "name": "OI (USD)", "nameTextStyle": {"color": coin_color},
             "position": "right", "axisLabel": _AXIS_LABEL, "splitLine": {"show": False},
             "min": round(o_min - o_range * 0.05, 2), "max": round(o_max + o_range * 0.05, 2)},
        ],
        "dataZoom": _DATAZOOM,
        "series": [
            {"name": "Giá", "type": "line", "yAxisIndex": 0, "data": [round(v, 2) for v in price_vals],
             "smooth": True, "symbol": "none",
             "lineStyle": {"color": WARNING_COLOR, "width": 2},
             "itemStyle": {"color": WARNING_COLOR},
             "z": 10},
            {"name": "OI", "type": "line", "yAxisIndex": 1,
             "data": [round(v, 2) if v is not None and not np.isnan(v) else None for v in oi_vals],
             "smooth": True, "symbol": "none",
             "lineStyle": {"color": coin_color, "width": 2},
             "itemStyle": {"color": coin_color},
             "areaStyle": {
                 "color": {
                     "type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                     "colorStops": [
                         {"offset": 0, "color": f"rgba({int(coin_color[1:3],16)},{int(coin_color[3:5],16)},{int(coin_color[5:7],16)},0.15)"},
                        #  {"offset": 1, "color": "rgba(0,0,0,0)"},
                     ],
                 }
             },
             "z": 5},
        ],
    }
    # Unique key ensures full re-render on any parameter change
    chart_key = f"price_oi_sync_{coin}_{freq}_{sync_dates}_{oi_series_type}_{len(x)}"
    st_echarts(options=option, height="600px", key=chart_key)



# ──────────────────────────────────────────────────────────────
# PANEL 9 – MARKET STATE SIGNALS (ECharts heatmap + bar)
# ──────────────────────────────────────────────────────────────
def _render_market_signals_panel(all_candles, all_metrics, all_liq):
    st.markdown("### 🧠 Tín hiệu trạng thái thị trường")
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
                      "text": ["Bullish", "Bearish"], "textStyle": {"color": "#fafafa"}},
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
# PANEL 10 – CANDLE STATISTICS (Length Hist + Mean Volume)
# ──────────────────────────────────────────────────────────────
def _render_candle_stats_panel(all_candles):
    st.markdown("### 📊 Thống kê độ dài nến (mở, đóng) & khối lượng trung bình")
    c1, ps2 = st.columns([3, 1])
    with c1:
        st_dates = st.date_input(
            "Khoảng thời gian",
            value=(pd.Timestamp(DEFAULT_START).date(), pd.Timestamp(DEFAULT_END).date()),
            min_value=pd.Timestamp("2024-01-01").date(),
            max_value=pd.Timestamp("2024-03-31").date(), format="DD/MM/YYYY", key="st_dates")
    with ps2:
        coin = st.selectbox("Coin", COINS, key="st_coin")

    if len(st_dates) != 2:
        st.warning("Chọn đầy đủ ngày bắt đầu và kết thúc."); return
    start_date, end_date = pd.Timestamp(st_dates[0]), pd.Timestamp(st_dates[1])

    df = filter_by_date(filter_by_coins(all_candles, [coin]), start_date, end_date, "open_time")
    if df.empty:
        st.warning("Không có dữ liệu."); return

    # Calculate candle body percentage (Open vs Close)
    df = df.copy()
    df["range_pct"] = abs(df["open"] - df["close"]) / df["open"] * 100
    
    # Binning
    num_bins = 14
    bins = np.linspace(df["range_pct"].min(), df["range_pct"].max(), num_bins + 1)
    df["bin"] = pd.cut(df["range_pct"], bins=bins, include_lowest=True)
    
    # Aggregation
    stats = df.groupby("bin", observed=True).agg({
        "range_pct": "count",
        "volume": "mean"
    }).rename(columns={"range_pct": "frequency", "volume": "avg_volume"}).reset_index()
    
    x_labels = [f"{b.left:.2f}%-{b.right:.2f}%" for b in stats["bin"]]
    freq_data = stats["frequency"].tolist()
    # Actual numeric data for the line
    vol_data = [float(round(v, 2)) if pd.notna(v) else 0 for v in stats["avg_volume"]]

    # Calculate overall mean volume for reference line
    mean_vol = df["volume"].mean()

    coin_color = COIN_COLORS.get(coin, ACCENT_COLOR)
    option = {
        "backgroundColor": _BG, "tooltip": _TOOLTIP, "legend": _LEGEND,
        "grid": _GRID,
        "xAxis": {"type": "category", "data": x_labels, "axisLine": _AXIS_LINE,
                  "axisLabel": {**_AXIS_LABEL, "rotate": 35}},
        "yAxis": [
            {"type": "value", "name": "Tần suất (Số nến)", "nameTextStyle": {"color": TEXT_SECONDARY},
             "axisLabel": _AXIS_LABEL, "splitLine": _SPLIT_LINE},
            {"type": "value", "name": "K/L TB (USD)", "nameTextStyle": {"color": coin_color},
             "position": "right", "axisLabel": _AXIS_LABEL, "splitLine": {"show": False}},
        ],
        "series": [
            {"name": "Số lượng nến", "type": "bar", "data": freq_data,
             "itemStyle": {"color": f"rgba({int(coin_color[1:3],16)},{int(coin_color[3:5],16)},{int(coin_color[5:7],16)},0.25)"}, "barMaxWidth": 30, "z": 2,
             "label": {"show": True, "position": "top", "color": coin_color, "fontSize": 10}},
            {"name": "K/L trung bình", "type": "line", "yAxisIndex": 1, "data": vol_data,
             "smooth": True, "connectNulls": True,
             "lineStyle": {"color": coin_color, "width": 4},
             "symbol": "circle", "symbolSize": 8, "itemStyle": {"color": coin_color}, "zlevel": 1},
        ],
    }
    st_echarts(options=option, height="500px", key=f"st_ec_{coin}_{start_date}_{end_date}")


# ──────────────────────────────────────────────────────────────
# PANEL 11 – TAIL STATISTICS (Wick Hist + OI Change)
# ──────────────────────────────────────────────────────────────
def _render_tail_stats_panel(all_candles, all_metrics):
    st.markdown("### 📊 Thống kê đuôi nến & khối lượng")
    c1, ps2 = st.columns([3, 1])
    with c1:
        tail_dates = st.date_input(
            "Khoảng thời gian",
            value=(pd.Timestamp(DEFAULT_START).date(), pd.Timestamp(DEFAULT_END).date()),
            min_value=pd.Timestamp("2024-01-01").date(),
            max_value=pd.Timestamp("2024-03-31").date(), format="DD/MM/YYYY", key="tail_dates")
    with ps2:
        coin = st.selectbox("Coin", COINS, key="tail_coin")

    if len(tail_dates) != 2:
        st.warning("Chọn đầy đủ ngày bắt đầu và kết thúc."); return
    start_date, end_date = pd.Timestamp(tail_dates[0]), pd.Timestamp(tail_dates[1])

    c_df = filter_by_date(filter_by_coins(all_candles, [coin]), start_date, end_date, "open_time")
    if c_df.empty:
        st.warning("Không có dữ liệu."); return

    # Calculate tail length
    c_df = c_df.copy()
    c_df["tail_len"] = (c_df["high"] - c_df["low"]) - abs(c_df["open"] - c_df["close"])
    c_df["tail_pct"] = c_df["tail_len"] / c_df["low"] * 100
    
    # Binning by tail_pct
    num_bins = 15
    merged = c_df[c_df["tail_pct"] > 0]
    if merged.empty: st.warning("Không có dữ liệu đuôi."); return
    
    bins = np.linspace(merged["tail_pct"].min(), merged["tail_pct"].max(), num_bins + 1)
    merged = merged.copy()
    merged["bin"] = pd.cut(merged["tail_pct"], bins=bins, include_lowest=True)
    
    stats = merged.groupby("bin", observed=True).agg({
        "tail_pct": "count",
        "volume": "mean"
    }).rename(columns={"tail_pct": "freq", "volume": "avg_vol"}).reset_index()
    
    x_labels = [f"{b.left:.2f}%-{b.right:.2f}%" for b in stats["bin"]]
    freq_data = stats["freq"].tolist()
    vol_data = [round(v, 2) if pd.notna(v) else 0 for v in stats["avg_vol"]]

    coin_color = COIN_COLORS.get(coin, ACCENT_COLOR)
    option = {
        "backgroundColor": _BG, "tooltip": _TOOLTIP, "legend": _LEGEND,
        "grid": _GRID,
        "xAxis": {"type": "category", "data": x_labels, "axisLine": _AXIS_LINE,
                  "axisLabel": {**_AXIS_LABEL, "rotate": 35}},
        "yAxis": [
            {"type": "value", "name": "Số nến", "nameTextStyle": {"color": TEXT_SECONDARY},
             "axisLabel": _AXIS_LABEL, "splitLine": _SPLIT_LINE},
            {"type": "value", "name": "K/L trung bình", "nameTextStyle": {"color": coin_color},
             "position": "right", "axisLabel": _AXIS_LABEL, "splitLine": {"show": False}},
        ],
        "series": [
            {"name": "Số lượng nến", "type": "bar", "data": freq_data,
             "itemStyle": {"color": f"rgba({int(coin_color[1:3],16)},{int(coin_color[3:5],16)},{int(coin_color[5:7],16)},0.2)"}, "barMaxWidth": 40, "z": 2},
            {"name": "K/L trung bình", "type": "line", "yAxisIndex": 1, "data": vol_data,
             "smooth": True, "connectNulls": True,
             "lineStyle": {"color": coin_color, "width": 4},
             "symbol": "circle", "symbolSize": 8, "itemStyle": {"color": coin_color}, "zlevel": 1},
        ],
    }
    st_echarts(options=option, height="500px", key=f"tail_ec_{coin}_{start_date}")

# ──────────────────────────────────────────────────────────────
# INLINE – OI + Volume correlation chart (used inside OI panel)
# ──────────────────────────────────────────────────────────────
# PANEL – OI vs VOLUME CORRELATION
# ──────────────────────────────────────────────────────────────
def _render_oi_volume_panel(all_candles, all_metrics):
    st.markdown("### 📊 Tương quan OI & khối lượng")
    c1, c2 = st.columns([2, 1])
    with c1:
        corr_dates = st.date_input(
            "Khoảng thời gian",
            value=(pd.Timestamp(DEFAULT_START).date(), pd.Timestamp(DEFAULT_END).date()),
            min_value=pd.Timestamp("2024-01-01").date(),
            max_value=pd.Timestamp("2024-03-31").date(), format="DD/MM/YYYY", key="oi_vol_corr_dates")
    with c2:
        corr_coin = st.selectbox("Coin", COINS, key="corr_coin")

    if len(corr_dates) != 2:
        st.warning("Chọn đầy đủ ngày."); return
    start_date, end_date = pd.Timestamp(corr_dates[0]), pd.Timestamp(corr_dates[1])

    c_df = filter_by_date(
        filter_by_coins(all_candles, [corr_coin]), start_date, end_date, "open_time"
    ).sort_values("open_time")
    m_df = filter_by_date(
        filter_by_coins(all_metrics, [corr_coin]), start_date, end_date, "create_time"
    ).sort_values("create_time")

    if c_df.empty or m_df.empty:
        st.warning("Không có dữ liệu."); return

    # Daily volume from candles
    c_df = c_df.copy()
    c_df["date"] = c_df["open_time"].dt.normalize()

    # Aggregate daily: volume sum + first open + last close (same logic as candlestick panel)
    daily_agg = c_df.groupby("date").agg(
        volume=("volume", "sum"),
        daily_open=("open", "first"),
        daily_close=("close", "last"),
    ).reset_index()

    # Daily avg OI from metrics
    m_df = m_df.copy()
    m_df["date"] = m_df["create_time"].dt.normalize()
    daily_oi = m_df.groupby("date")["sum_open_interest"].mean().reset_index()
    daily_oi.columns = ["date", "oi"]

    merged = pd.merge(daily_agg, daily_oi, on="date").sort_values("date").reset_index(drop=True)
    merged["week"] = merged["date"].dt.isocalendar().week.astype(int)
    merged["week_start"] = merged["date"] - pd.to_timedelta(merged["date"].dt.dayofweek, unit="D")

    # ── Week-over-week % changes ──
    weekly = merged.groupby("week").agg(
        vol_start=("volume", "sum"), vol_end=("volume", "sum"),
        oi_start=("oi", "first"), oi_end=("oi", "last"),
        week_start=("week_start", "first"), n_days=("date", "count")
    ).reset_index()
    weekly = weekly[weekly["n_days"] >= 4].copy()
    weekly["vol_sum"] = weekly["vol_end"]  # weekly total volume (sum of all days in week)
    weekly["vol_chg"] = weekly["vol_sum"].pct_change().mul(100).round(1)  # current week vs previous week
    weekly["oi_chg"] = ((weekly["oi_end"] - weekly["oi_start"]) / weekly["oi_start"] * 100).round(1)
    weekly["corr"] = [
        round(merged[merged["week"] == w]["volume"].corr(merged[merged["week"] == w]["oi"]), 3)
        if len(merged[merged["week"] == w]) >= 3 else None
        for w in weekly["week"]
    ]
    weekly["dates"] = (
        weekly["week_start"].dt.strftime("%d/%m") + " – " +
        (weekly["week_start"] + pd.Timedelta(days=6)).dt.strftime("%d/%m")
    )

    x_labels = [d.strftime("%d/%m") for d in merged["date"]]
    coin_color = COIN_COLORS.get(corr_coin, ACCENT_COLOR)

    # ── Dual-axis: Volume (VOL_COLOR) + OI (coin_color) ──
    vol_data = [
        {"value": round(v / 1e6, 2), "itemStyle": {"color": VOL_COLOR}}
        for v in merged["volume"]
    ]

    oi_prev = merged["oi"].shift(1).fillna(merged["oi"])
    oi_data = [
        {"value": round(o / 1e6, 2), "itemStyle": {"color": coin_color}}
        for o in merged["oi"]
    ]

    option = {
        "backgroundColor": _BG,
        "tooltip": {"trigger": "axis", "backgroundColor": "#0d1420", "textStyle": {"color": "#e2e8f0"},
                    "axisPointer": {"type": "shadow", "lineStyle": {"color": VOL_COLOR, "width": 1.5}}},
        "legend": {"top": 8, "textStyle": {"color": "#fafafa"}, "itemGap": 20,
                   "inactiveColor": "#4a5568",
                   "data": [{"name": "Volume (M)", "icon": "roundRect", "itemStyle": {"color": VOL_COLOR}},
                            {"name": "OI", "icon": "circle", "itemStyle": {"color": coin_color}}]},
        "grid": {"left": "6%", "right": "6%", "top": "18%", "bottom": "18%", "containLabel": True},
        "xAxis": {
            "type": "category", "data": x_labels,
            "axisLine": _AXIS_LINE,
            "axisLabel": {**_AXIS_LABEL, "interval": max(0, len(x_labels) // 10 - 1)},
            "splitLine": {"show": False},
        },
        "yAxis": [
            {"type": "value", "name": "Khối lượng giao dịch (USD)", "nameTextStyle": {"color": "#fafafa"},
             "axisLabel": {**_AXIS_LABEL, "formatter": "{value}M"},
             "splitLine": _SPLIT_LINE, "axisLine": {"show": False}},
            {"type": "value", "name": "OI (USD)", "nameTextStyle": {"color": coin_color},
             "position": "right",
             "axisLabel": {**_AXIS_LABEL, "formatter": "{value}M", "color": coin_color},
             "splitLine": {"show": False}, "axisLine": {"show": False}},
        ],
        "series": [
            {
                "name": "Volume (M)", "type": "bar", "data": vol_data,
                "itemStyle": {"color": VOL_COLOR},
                "barMaxWidth": 20, "z": 1,
            },
            {
                "name": "OI", "type": "line", "yAxisIndex": 1,
                "data": oi_data, "smooth": True, "symbol": "none",
                "lineStyle": {"color": coin_color, "width": 2.5},
                "areaStyle": {
                    "color": {
                        "type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                        "colorStops": [
                            {"offset": 0, "color": f"rgba({int(coin_color[1:3],16)},{int(coin_color[3:5],16)},{int(coin_color[5:7],16)},0.15)"},
                            # {"offset": 1, "color": "rgba(0,0,0,0)"},
                        ],
                    }
                },
            },
        ],
        "dataZoom": _DATAZOOM,
    }
    st_echarts(options=option, height="380px", key=f"corr_dual_{corr_coin}")

    # ── Weekly summary table ──
    st.markdown("**📅 Thay đổi theo tuần**")

    def vol_color(v):
        if v > 5:   return "🟢"
        elif v < -5: return "🔴"
        else:        return "⚪"
    def oi_color(v):
        if v > 5:   return "🟢"
        elif v < -5: return "🔴"
        else:        return "⚪"

    table_md = "| Tuần | Ngày | Vol % | OI % | Corr | Nhận xét |\n" + \
               "|:---:|:---:|:---:|:---:|:---:|:---|\n"
    for _, row in weekly.dropna(subset=["vol_chg"]).iterrows():
        vol_sgn = vol_color(row["vol_chg"])
        oi_sgn  = oi_color(row["oi_chg"])
        corr_v  = row["corr"] if row["corr"] is not None else "–"
        v, o = row["vol_chg"], row["oi_chg"]
        if abs(v) < 5 and abs(o) < 5:
            note = "⚖️ Ổn định"
        elif abs(v) < 5 and o > 5:
            note = "📊 Vol ổn, OI tăng ↑"
        elif abs(v) < 5 and o < -5:
            note = "📊 Vol ổn, OI giảm ↓"
        elif v > 5 and abs(o) < 5:
            note = "🔥 Vol tăng, OI ổn"
        elif v < -5 and abs(o) < 5:
            note = "❄️ Vol giảm, OI ổn"
        elif v > 5 and o > 5:
            note = "✅ Cùng chiều (tăng)"
        elif v < -5 and o < -5:
            note = "📉 Cùng chiều (giảm)"
        elif v > 5 and o < -5:
            note = "⚠️ Phân kỳ! Vol↑ OI↓"
        else:
            note = "⚠️ Phân kỳ! Vol↓ OI↑"

        table_md += f"| {row['week']} | {row['dates']} | {vol_sgn} {row['vol_chg']:+.1f}% | {oi_sgn} {row['oi_chg']:+.1f}% | {corr_v} | {note} |\n"

    st.markdown(table_md)

    full_corr = merged["volume"].corr(merged["oi"])
    st.success(f"**Pearson Correlation (toàn kỳ) `{corr_coin}`:** r = **{full_corr:.4f}**  — {'🔗 Tương quan thuận — OI phản ánh khối lượng' if full_corr > 0.3 else '🔗 Tương quan nghịch / yếu — OI KHÔNG phản ánh đúng khối lượng' if full_corr < -0.1 else '⚖️ Tương quan trung bình — OI phản ánh khối lượng ở mức hạn chế'}")


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

    # _render_kpi_strip(all_candles, all_metrics, all_liq)
    st.markdown("---")
    _render_candlestick_panel(all_candles, all_liq)
    st.markdown("---")
    _render_oi_panel(all_metrics)
    st.markdown("---")
    _render_oi_volume_panel(all_candles, all_metrics)
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

    # col_ls, col_taker = st.columns(2)
    # with col_ls:
    #     _render_ls_ratio_panel(all_metrics)
    # with col_taker:
    #     _render_taker_ratio_panel(all_candles, all_metrics)
    # st.markdown("---")

    _render_synced_panel(all_candles, all_metrics, all_liq)
    st.markdown("---")

    # _render_liq_imbalance_panel(all_liq, all_candles)
    st.markdown("---")

    # _render_market_signals_panel(all_candles, all_metrics, all_liq)
    st.markdown("---")

    # _render_candle_stats_panel(all_candles)
    # st.markdown("---")

    # _render_tail_stats_panel(all_candles, all_metrics)

    st.markdown(
        """<div style="text-align:center; padding:2rem 0 1rem 0; opacity:0.35; font-size:0.7rem;">
        Dữ liệu từ Binance · Coin-Margined Futures · Q1/2024
        </div>""", unsafe_allow_html=True)
