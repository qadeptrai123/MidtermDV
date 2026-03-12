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
# CHART CACHING & DOWNSAMPLING
# ============================================================
def _downsample_df(df: pd.DataFrame, max_points: int = 2000) -> pd.DataFrame:
    """Downsample DataFrame if it exceeds max_points to improve Plotly rendering."""
    if len(df) <= max_points:
        return df
    # Simple nth-row sampling for speed
    step = len(df) // max_points
    return df.iloc[::step].copy()


# ============================================================
# KPI METRIC STRIP
# ============================================================
def _render_kpi_strip(candles_df: pd.DataFrame, metrics_df: pd.DataFrame, liq_df: pd.DataFrame, selected_coins: list):
    """Render a row of KPI metric cards."""
    st.markdown("### 📈 Tổng Quan Thị Trường")
    # ... (rest of function remains same, but let's keep it concise)

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
@st.cache_resource
def _create_candlestick_figure(cache_key: str, coin_df: pd.DataFrame, selected_coin: str):
    """Factory for the main candlestick chart."""
    # Compute MAs locally for caching
    df = coin_df.copy()
    df["ma7"] = compute_ma(df, 7)
    df["ma14"] = compute_ma(df, 14)
    
    # Downsample for browser performance
    display_df = _downsample_df(df, 1500)

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
    )

    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=display_df["open_time"],
            open=display_df["open"], high=display_df["high"],
            low=display_df["low"], close=display_df["close"],
            increasing_line_color=BULL_COLOR, decreasing_line_color=BEAR_COLOR,
            name="Giá", showlegend=False,
        ),
        row=1, col=1,
    )

    # MAs
    fig.add_trace(go.Scatter(x=display_df["open_time"], y=display_df["ma7"], line=dict(color="#f59e0b", width=1.5), name="MA(7)"), row=1, col=1)
    fig.add_trace(go.Scatter(x=display_df["open_time"], y=display_df["ma14"], line=dict(color="#8b5cf6", width=1.5), name="MA(14)"), row=1, col=1)

    # Volume
    fig.add_trace(go.Bar(
        x=display_df["open_time"], y=display_df["volume"], 
        marker_color=[BULL_COLOR if c >= o else BEAR_COLOR for o, c in zip(display_df["open"], display_df["close"])],
        marker_line_width=0, # Fix visibility on zoom out
        name="Khối lượng", showlegend=False
    ), row=2, col=1)

    fig.update_layout(**CHART_LAYOUT, title=f"{selected_coin}/USD — Biểu đồ Nến", height=600, xaxis_rangeslider_visible=False, xaxis2_rangeslider_visible=True, yaxis2_rangemode="tozero")
    return fig

def _render_candlestick_panel(candles_df: pd.DataFrame, selected_coin: str):
    """Interactive candlestick chart with MA(7), MA(25), and volume bars."""
    st.markdown("### 🕯️ Biểu Đồ Nến & Khối Lượng")
    coin_df = candles_df[candles_df["coin"] == selected_coin].copy().sort_values("open_time")
    if coin_df.empty:
        st.warning("Không có dữ liệu.")
        return
    # Use unique key to avoid DataFrame hashing in cache_resource
    ckey = f"{selected_coin}_{coin_df.index.min()}_{coin_df.index.max()}_{len(coin_df)}"
    fig = _create_candlestick_figure(ckey, coin_df, selected_coin)
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


# ============================================================
# PANEL 2: OPEN INTEREST TIMELINE
# ============================================================
@st.cache_resource
def _create_oi_figure(cache_key: str, metrics_df: pd.DataFrame, selected_coins: list, price_df: pd.DataFrame = None, primary_coin: str = None):
    """Factory for OI area chart with optional price overlay."""
    fig = go.Figure()
    colors = {"ETH": ACCENT_COLOR, "SOL": WARNING_COLOR, "DOGE": "#06b6d4"}
    
    # 1. Add OI Area traces
    for coin in selected_coins:
        coin_df = metrics_df[metrics_df["coin"] == coin].sort_values("create_time")
        if coin_df.empty: continue
        fig.add_trace(go.Scatter(
            x=coin_df["create_time"], 
            y=coin_df["sum_open_interest_value"], 
            mode="lines", 
            name=f"{coin} OI", 
            fill="tozeroy",
            opacity=0.2, # Slightly lower opacity for better visibility
            line=dict(color=colors.get(coin, ACCENT_COLOR), width=1)
        ))
    
    # 2. Optional Price Overlay (Added LAST to be on top)
    if price_df is not None and not price_df.empty and primary_coin:
        fig.add_trace(go.Scatter(
            x=price_df["open_time"],
            y=price_df["close"],
            mode="lines",
            name=f"Giá {primary_coin}",
            line=dict(color="white", width=2),
            yaxis="y2"
        ))
        fig.update_layout(
            yaxis2=dict(
                title="Giá ($)",
                overlaying="y",
                side="right",
                showgrid=False,
                zeroline=False
            )
        )

    _apply_layout(fig, title="Open Interest Over Time", height=400)
    fig.update_yaxes(title_text="OI Value (USD)")
    fig.update_layout(xaxis_rangeslider_visible=True)
    return fig

def _render_oi_panel(metrics_df: pd.DataFrame, selected_coins: list, candles_df: pd.DataFrame = None, primary_coin: str = None):
    """OI panel with area chart and optional price overlay."""
    st.markdown("### 📊 Open Interest")
    
    show_price = st.checkbox("Hiển thị giá", key="oi_show_price")
    p_df = None
    if show_price and candles_df is not None:
        p_df = candles_df[candles_df["coin"] == primary_coin]
        
    ckey = f"{selected_coins}_{primary_coin}_{show_price}_{len(metrics_df)}"
    fig = _create_oi_figure(ckey, metrics_df, selected_coins, p_df, primary_coin)
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


# ============================================================
# PANEL 3: LIQUIDATION CHART (Mirrored bars like Coinglass)
# ============================================================
@st.cache_resource
def _create_liquidation_figure(cache_key: str, liq_agg: pd.DataFrame, selected_coin: str):
    """Factory for liquidation chart."""
    coin_df = liq_agg[liq_agg["coin"] == selected_coin].copy()
    if coin_df.empty: return None
    fig = go.Figure()
    for side, color, sign in [("Long Liq", BEAR_COLOR, 1), ("Short Liq", BULL_COLOR, -1)]:
        df = coin_df[coin_df["liq_side"] == side]
        fig.add_trace(go.Bar(x=df["time_bucket"], y=df["total_value"] * sign, name=side, marker_color=color))
    _apply_layout(fig, title=f"{selected_coin} — Liquidation", height=400)
    fig.update_layout(barmode="relative", xaxis_rangeslider_visible=True)
    return fig

def _render_liquidation_panel(liq_agg: pd.DataFrame, selected_coin: str):
    """Standard Liq panel."""
    st.markdown("### 🔥 Biểu Đồ Thanh Lý")
    ckey = f"{selected_coin}_{len(liq_agg)}"
    fig = _create_liquidation_figure(ckey, liq_agg, selected_coin)
    if fig: st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
    else: st.warning("No data.")


# ============================================================
# PANEL 4: VOLUME PROFILE (Horizontal histogram)
# ============================================================
@st.cache_resource
def _create_volume_profile_figure(cache_key: str, coin_df: pd.DataFrame, selected_coin: str, num_bins: int):
    """Factory for volume profile chart."""
    if coin_df.empty: return None
    price_min, price_max = coin_df["low"].min(), coin_df["high"].max()
    bins = np.linspace(price_min, price_max, num_bins + 1)
    coin_df["price_bin"] = pd.cut(coin_df["close"], bins=bins, labels=False)
    vp = coin_df.groupby("price_bin")["volume"].sum().reset_index()
    vp["price_level"] = [(bins[int(i)] + bins[int(i) + 1]) / 2 for i in vp["price_bin"]]
    poc_idx = vp["volume"].idxmax()
    poc_price = vp.loc[poc_idx, "price_level"]

    fig = go.Figure()
    fig.add_trace(go.Bar(y=vp["price_level"], x=vp["volume"], orientation="h", marker_color=ACCENT_COLOR, name="KL"))
    fig.add_hline(y=poc_price, line_dash="dash", line_color=WARNING_COLOR, annotation_text=f"POC: ${poc_price:,.2f}")
    _apply_layout(fig, title=f"{selected_coin} — Volume Profile", height=500)
    return fig

def _render_volume_profile(candles_df: pd.DataFrame, selected_coin: str, num_bins: int = 50):
    """Standard Volume Profile panel."""
    st.markdown("### 📐 Hồ Sơ Khối Lượng (Volume Profile)")
    coin_df = candles_df[candles_df["coin"] == selected_coin].copy()
    ckey = f"{selected_coin}_{num_bins}_{len(coin_df)}"
    fig = _create_volume_profile_figure(ckey, coin_df, selected_coin, num_bins)
    if fig: st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
    else: st.warning("No data.")


# ============================================================
# PANEL 5: PRICE CORRELATION HEATMAP
# ============================================================
@st.cache_resource
def _create_correlation_figure(cache_key: str, candles_df: pd.DataFrame):
    """Factory for correlation heatmap."""
    pivot = candles_df.pivot_table(index="open_time", columns="coin", values="close")
    returns = pivot.pct_change().dropna()
    if returns.empty or returns.shape[1] < 2: return None
    corr_matrix = returns.corr()
    fig = px.imshow(corr_matrix, text_auto=".3f", 
                    color_continuous_scale=[[0, BEAR_COLOR], [0.5, "#1a1a2e"], [1, BULL_COLOR]],
                    zmin=-1, zmax=1, aspect="auto")
    _apply_layout(fig, title="Tương quan lợi suất giữa các Coin", height=400)
    fig.update_layout(coloraxis_colorbar=dict(title="Corr"))
    return fig

def _render_correlation_panel(candles_df: pd.DataFrame):
    """Correlation heatmap panel."""
    st.markdown("### 🔗 Ma Trận Tương Quan Giá")
    ckey = f"corr_{len(candles_df)}"
    fig = _create_correlation_figure(ckey, candles_df)
    if fig: st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
    else: st.info("Cần ít nhất 2 coin.")


# ============================================================
# PANEL 5b: ROLLING CORRELATION TIME SERIES
# ============================================================
@st.cache_resource
def _create_rolling_corr_figure(cache_key: str, candles_df: pd.DataFrame, window_hours: int):
    """Factory for rolling correlation chart."""
    pivot = candles_df.pivot_table(index="open_time", columns="coin", values="close")
    returns = pivot.pct_change().dropna()
    if returns.shape[1] < 2: return None
    
    # Estimate window
    avg_int = (candles_df["open_time"].max() - candles_df["open_time"].min()) / len(candles_df)
    cph = pd.Timedelta(hours=1) / avg_int if avg_int > pd.Timedelta(0) else 12
    window = max(int(window_hours * cph), 2)
    fig = go.Figure()
    coins = returns.columns.tolist()
    colors = [ACCENT_COLOR, WARNING_COLOR, "#06b6d4", BULL_COLOR, BEAR_COLOR]
    
    idx = 0
    for i, c1 in enumerate(coins):
        for j, c2 in enumerate(coins):
            if i < j:
                rc = returns[c1].rolling(window=window, min_periods=min(window, 20)).corr(returns[c2])
                fig.add_trace(go.Scatter(x=returns.index, y=rc, mode="lines", name=f"{c1}-{c2}", line=dict(color=colors[idx % len(colors)], width=1.5)))
                idx += 1
    _apply_layout(fig, title=f"Rolling Correlation ({window_hours}h)", height=350)
    fig.update_layout(xaxis_rangeslider_visible=True)
    return fig

def _render_rolling_correlation_panel(candles_df: pd.DataFrame, window_hours: int = 24):
    """Standard Rolling Correlation panel."""
    st.markdown("### 📉 Tương Quan Động (Rolling Correlation)")
    ckey = f"rolling_{window_hours}_{len(candles_df)}"
    fig = _create_rolling_corr_figure(ckey, candles_df, window_hours)
    if fig: st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
    else: st.info("Need at least 2 coins.")


# ============================================================
# PANEL 6: LONG/SHORT RATIO (Whale vs Overall)
# ============================================================
@st.cache_resource
def _create_ls_ratio_figure(cache_key: str, coin_df: pd.DataFrame, selected_coin: str):
    """Factory for L/S ratio chart."""
    if coin_df.empty: return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=coin_df["create_time"], y=coin_df["count_toptrader_long_short_ratio"], name="Top Trader L/S", line=dict(color=WARNING_COLOR)))
    fig.add_trace(go.Scatter(x=coin_df["create_time"], y=coin_df["count_long_short_ratio"], name="Overall L/S", line=dict(color=ACCENT_COLOR)))
    fig.add_hline(y=1.0, line_dash="dot", line_color="rgba(255,255,255,0.3)")
    _apply_layout(fig, title=f"{selected_coin} — L/S Ratio", height=400)
    fig.update_layout(xaxis_rangeslider_visible=True)
    return fig

def _render_ls_ratio_panel(metrics_df: pd.DataFrame, selected_coin: str):
    """Standard L/S panel."""
    st.markdown("### ⚖️ Tỷ Lệ Long/Short — Cá Voi vs Tổng Thể")
    coin_df = metrics_df[metrics_df["coin"] == selected_coin].sort_values("create_time")
    ckey = f"{selected_coin}_{len(coin_df)}"
    fig = _create_ls_ratio_figure(ckey, coin_df, selected_coin)
    if fig: st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
    else: st.warning("No data.")


# ============================================================
# PANEL 7: TAKER BUY/SELL RATIO + PRICE
# ============================================================
@st.cache_resource
def _create_taker_ratio_figure(cache_key: str, coin_candles: pd.DataFrame, coin_metrics: pd.DataFrame, selected_coin: str):
    """Factory for Taker ratio chart."""
    if coin_candles.empty: return None
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=coin_candles["open_time"], y=coin_candles["close"], name="Giá", line=dict(color=TEXT_PRIMARY, width=1.5)), secondary_y=False)
    fig.add_trace(go.Scatter(x=coin_candles["open_time"], y=coin_candles["taker_buy_volume"]/coin_candles["volume"], name="Taker Buy Ratio", line=dict(color=BULL_COLOR, width=1), opacity=0.7), secondary_y=True)
    if not coin_metrics.empty:
        fig.add_trace(go.Scatter(x=coin_metrics["create_time"], y=coin_metrics["sum_taker_long_short_vol_ratio"], name="Taker L/S Vol Ratio", line=dict(color=WARNING_COLOR, width=1), opacity=0.7), secondary_y=True)
    _apply_layout(fig, title=f"{selected_coin} — Taker Pressure", height=400)
    fig.update_layout(xaxis_rangeslider_visible=True)
    return fig

def _render_taker_ratio_panel(candles_df: pd.DataFrame, metrics_df: pd.DataFrame, selected_coin: str):
    """Standard Taker panel."""
    st.markdown("### 💹 Tỷ Lệ Taker Mua/Bán & Giá")
    coin_candles = candles_df[candles_df["coin"] == selected_coin].copy().sort_values("open_time")
    coin_metrics = metrics_df[metrics_df["coin"] == selected_coin].copy().sort_values("create_time")
    ckey = f"{selected_coin}_{len(coin_candles)}_{len(coin_metrics)}"
    fig = _create_taker_ratio_figure(ckey, coin_candles, coin_metrics, selected_coin)
    if fig: st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
    else: st.warning("No data.")


# ============================================================
# PANEL 8: MARKET STATE SIGNAL HEATMAP
# ============================================================
@st.cache_data(ttl=3600)
def _prepare_market_signals_data(candles_df: pd.DataFrame, metrics_df: pd.DataFrame, liq_agg_1d: pd.DataFrame, selected_coin: str):
    """Heavy calculation for market signals, cached to avoid re-running on UI changes."""
    coin_candles = candles_df[candles_df["coin"] == selected_coin].copy().sort_values("open_time")
    coin_metrics = metrics_df[metrics_df["coin"] == selected_coin].copy().sort_values("create_time")

    if coin_candles.empty or coin_metrics.empty:
        return None

    # Resample to 1D
    daily_candles = coin_candles.set_index("open_time").resample("1D").agg({
        "open": "first", "high": "max", "low": "min", "close": "last",
        "volume": "sum", "taker_buy_volume": "sum",
    }).dropna(subset=["close"]).reset_index()

    daily_metrics = coin_metrics.set_index("create_time").resample("1D").agg({
        "sum_open_interest_value": "last",
        "sum_taker_long_short_vol_ratio": "mean",
    }).dropna(subset=["sum_open_interest_value"]).reset_index()

    # Signals
    daily_candles["price_change_pct"] = daily_candles["close"].pct_change() * 100
    daily_candles["taker_buy_ratio"] = daily_candles["taker_buy_volume"] / daily_candles["volume"].replace(0, np.nan)
    daily_metrics["oi_change_pct"] = daily_metrics["sum_open_interest_value"].pct_change() * 100

    # Merge
    daily_candles["date"] = daily_candles["open_time"].dt.date
    daily_metrics["date"] = daily_metrics["create_time"].dt.date
    merged = pd.merge(daily_candles, daily_metrics, on="date", how="inner")

    # Liq imbal
    liq_1d = liq_agg_1d[liq_agg_1d["coin"] == selected_coin].copy()
    if not liq_1d.empty:
        liq_1d["date"] = liq_1d["time_bucket"].dt.date
        liq_pivot = liq_1d.pivot_table(index="date", columns="liq_side", values="total_value", aggfunc="sum", fill_value=0).reset_index()
        liq_total = liq_pivot.get("Long Liq", 0) + liq_pivot.get("Short Liq", 0)
        liq_pivot["liq_imbalance"] = (liq_pivot.get("Long Liq", 0) - liq_pivot.get("Short Liq", 0)) / liq_total.replace(0, np.nan)
        merged = pd.merge(merged, liq_pivot[["date", "liq_imbalance"]], on="date", how="left")
    else:
        merged["liq_imbalance"] = 0
    
    return merged.fillna(0)

@st.cache_resource
def _create_market_signals_heatmap(merged_df: pd.DataFrame, selected_coin: str):
    """Factory for market signals heatmap figure."""
    if merged_df.empty: return None
    
    # Normalize 
    cols = ["price_change_pct", "oi_change_pct", "liq_imbalance", "taker_buy_ratio"]
    labels = ["Biến động giá %", "Biến động OI %", "Mất cân bằng thanh lý", "Tỷ lệ Taker Mua"]
    
    sig_mat = pd.DataFrame()
    for col in cols:
        s = merged_df[col]
        s_min, s_max = s.min(), s.max()
        sig_mat[col] = 2 * (s - s_min) / (s_max - s_min + 1e-9) - 1

    fig = px.imshow(sig_mat.T, x=[str(d) for d in merged_df["date"]], y=labels, 
                    color_continuous_scale=[[0, BEAR_COLOR], [0.5, "#1a1a2e"], [1, BULL_COLOR]],
                    zmin=-1, zmax=1, aspect="auto")
    _apply_layout(fig, title=f"{selected_coin} — Tín hiệu thị trường", height=300)
    fig.update_layout(coloraxis_colorbar=dict(title="Tín hiệu", tickvals=[-1, 0, 1], ticktext=["Bearish", "Neutral", "Bullish"]), xaxis=dict(tickangle=-45, dtick=7))
    return fig

def _render_market_signals_panel(candles_df: pd.DataFrame, metrics_df: pd.DataFrame, liq_agg: pd.DataFrame, selected_coin: str):
    """Render market signals using cached prep and render functions."""
    st.markdown("### 🧠 Tín Hiệu Trạng Thái Thị Trường")
    merged = _prepare_market_signals_data(candles_df, metrics_df, liq_agg, selected_coin)
    if merged is None or merged.empty:
        st.warning("Không đủ dữ liệu.")
        return
    fig = _create_market_signals_heatmap(merged, selected_coin)
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


# ============================================================
# PANEL 8.5: LIQUIDATION HEATMAP (Binance Style)
# ============================================================
@st.cache_resource
def _create_liquidation_heatmap(cache_key: str, liq_df: pd.DataFrame, candle_df: pd.DataFrame, threshold: float = 0.0):
    """Factory for liquidation heatmap overlay."""
    if liq_df.empty or candle_df.empty: return None
    
    # 1. Prepare Heatmap Matrix
    df = liq_df.copy()
    c_df = candle_df.copy()
    
    # Define price bins (e.g. 100 bins over range)
    p_min, p_max = c_df["low"].min(), c_df["high"].max()
    p_range = p_max - p_min
    if p_range == 0: p_range = 1
    
    # Bins for Y-axis (Price)
    price_bins = np.linspace(p_min * 0.999, p_max * 1.001, 150)
    df["price_bin"] = pd.cut(df["average_price"], bins=price_bins, labels=price_bins[:-1])
    
    # Pivot for Heatmap: Time (X) vs Price Bin (Y)
    # Resample liq to match candle frequency or fixed interval
    df = df.set_index("time")
    agg = df.groupby([pd.Grouper(freq="30min"), "price_bin"])["liq_value"].sum().reset_index()
    
    # Apply Threshold (normalized 0 to 1)
    max_liq = agg["liq_value"].max()
    if max_liq > 0:
        agg["liq_norm"] = agg["liq_value"] / max_liq
    else:
        agg["liq_norm"] = 0.0
        
    agg = agg[agg["liq_norm"] >= threshold]
    
    # Generate Heatmap
    fig = go.Figure()
    
    # Background Heatmap
    fig.add_trace(go.Heatmap(
        x=agg["time"],
        y=agg["price_bin"],
        z=agg["liq_value"],
        colorscale="Viridis",
        showscale=True,
        colorbar=dict(title="Thanh lý ($)", thickness=15, len=0.5),
        hovertemplate="Thời gian: %{x}<br>Giá: %{y}<br>Thanh lý: $%{z:,.0f}<extra></extra>",
        zsmooth=False
    ))
    
    # Price Line Overlay
    fig.add_trace(go.Scatter(
        x=c_df["open_time"],
        y=c_df["close"],
        mode="lines",
        line=dict(color="white", width=1.5, shape="hv"),
        name="Giá",
        hoverinfo="skip"
    ))
    
    _apply_layout(fig, title="Bản đồ nhiệt thanh lý (Heatmap)", height=500)
    fig.update_layout(
        yaxis=dict(side="right", title="Giá ($)"),
        xaxis=dict(title="Thời gian"),
        plot_bgcolor="#0a0e17",
        paper_bgcolor="#0a0e17"
    )
    return fig

@st.fragment
def _render_liquidation_heatmap_panel(all_liq: pd.DataFrame, all_candles: pd.DataFrame, primary_coin: str):
    """Heatmap panel with local threshold control (Fragmented)."""
    st.markdown("### 🔥 Bản Đồ Nhiệt Thanh Lý")
    
    # Filter data for primary coin only
    coin_liq = all_liq[all_liq["coin"] == primary_coin]
    coin_candles = all_candles[all_candles["coin"] == primary_coin]
    
    col_ctrl, _ = st.columns([1, 2])
    with col_ctrl:
        threshold = st.slider(
            "💎 Ngưỡng thanh lý (Threshold)",
            min_value=0.0,
            max_value=1.0,
            value=0.1,
            step=0.01,
            key="liq_heatmap_thresh"
        )
    
    if not coin_liq.empty:
        # Avoid hashing large DFs
        ckey = f"{primary_coin}_{threshold}_{len(coin_liq)}"
        fig = _create_liquidation_heatmap(ckey, coin_liq, coin_candles, threshold)
        if fig:
            st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
        else:
            st.warning("Không có dữ liệu vượt ngưỡng hiển thị.")
    else:
        st.warning(f"Không có dữ liệu thanh lý cho {primary_coin}.")


# ============================================================
# PANEL 9: PRICE + OI + LIQUIDATION SYNCED (Multi-panel)
# ============================================================
@st.cache_resource
def _create_synced_figure(cache_key: str, coin_candles: pd.DataFrame, coin_metrics: pd.DataFrame, coin_liq: pd.DataFrame, selected_coin: str):
    """Factory for the 3-row synced figure."""
    # Downsample
    d_candles = _downsample_df(coin_candles, 1200)
    d_metrics = _downsample_df(coin_metrics, 1200)
    d_liq = _downsample_df(coin_liq, 1200)

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.45, 0.25, 0.30],
        subplot_titles=["Giá", "Open Interest", "Khối lượng Thanh lý"],
    )

    # Row 1: Candlestick
    fig.add_trace(go.Candlestick(x=d_candles["open_time"], open=d_candles["open"], high=d_candles["high"], low=d_candles["low"], close=d_candles["close"], increasing_line_color=BULL_COLOR, decreasing_line_color=BEAR_COLOR, name="Giá", showlegend=False), row=1, col=1)

    # Row 2: OI
    if not d_metrics.empty:
        fig.add_trace(go.Scatter(x=d_metrics["create_time"], y=d_metrics["sum_open_interest_value"], mode="lines", name="OI", line=dict(color=ACCENT_COLOR, width=1.5), fill="tozeroy"), row=2, col=1)

    # Row 3: Liquidation
    if not d_liq.empty:
        for side, color, sign in [("Long Liq", BEAR_COLOR, 1), ("Short Liq", BULL_COLOR, -1)]:
            side_df = d_liq[d_liq["liq_side"] == side]
            fig.add_trace(go.Bar(
                x=side_df["time_bucket"], y=side_df["total_value"] * sign, 
                name=side, marker_color=color, marker_line_width=0
            ), row=3, col=1)

    fig.update_layout(**CHART_LAYOUT, height=800, title=f"{selected_coin} — Phân tích đồng bộ Pricing/OI/Liq", barmode="relative", xaxis_rangeslider_visible=False, xaxis3_rangeslider_visible=True)
    return fig

def _render_synced_panel(candles_df: pd.DataFrame, metrics_df: pd.DataFrame, liq_agg: pd.DataFrame, selected_coin: str):
    """3-row synced chart: Price, OI, and Liquidation."""
    st.markdown("### 📊 Giá — Open Interest — Thanh Lý (Đồng Bộ)")
    coin_candles = candles_df[candles_df["coin"] == selected_coin].copy().sort_values("open_time")
    coin_metrics = metrics_df[metrics_df["coin"] == selected_coin].copy().sort_values("create_time")
    coin_liq = liq_agg[liq_agg["coin"] == selected_coin].copy()

    if coin_candles.empty:
        st.warning("Không có dữ liệu.")
        return

    ckey = f"{selected_coin}_{len(coin_candles)}_{len(coin_metrics)}_{len(coin_liq)}"
    fig = _create_synced_figure(ckey, coin_candles, coin_metrics, coin_liq, selected_coin)
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
            max_value=pd.Timestamp("2024-03-03").to_pydatetime(),
            value=(
                pd.Timestamp("2024-01-01").to_pydatetime(),
                pd.Timestamp("2024-03-03").to_pydatetime(),
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
        from data_loader import get_dashboard_data
        (
            candles, metrics, liq_agg, 
            all_candles, all_metrics, all_liq
        ) = get_dashboard_data(tuple(selected_coins), start_date, end_date, freq)

    # ── KPI Strip ──
    _render_kpi_strip(candles, metrics, all_liq, selected_coins)

    st.markdown("---")

    # ── PANEL 1.5: Liquidation Heatmap ──
    _render_liquidation_heatmap_panel(all_liq, all_candles, primary_coin)

    st.markdown("---")

    # ── PANEL 1: Candlestick + MA + Volume ──
    _render_candlestick_panel(candles, primary_coin)

    st.markdown("---")

    # ── PANEL 2-3: OI + Liquidation (side by side) ──
    col_oi, col_liq = st.columns(2)
    with col_oi:
        _render_oi_panel(metrics, selected_coins, candles, primary_coin)
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
    corr_window = st.slider("🔄 Cửa sổ tương quan (giờ)", 1, 168, 24, key="corr_window")
    _render_rolling_correlation_panel(candles, window_hours=corr_window)
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

    # Hide Market Signals as requested
    # _render_market_signals_panel(all_candles, all_metrics, aggregate_liquidations(all_liq, "1D"), primary_coin)

    # Footer
    st.markdown(
        """
        <div style="text-align:center; padding: 2rem 0 1rem 0; opacity: 0.4; font-size: 0.75rem;">
            Dữ liệu từ Binance · Coin-Margined Futures · Q1/2024
        </div>
        """,
        unsafe_allow_html=True,
    )
