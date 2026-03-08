"""
data_loader.py — Central data loading & preprocessing for Crypto Futures Dashboard.

Loads candles, liquidation, and metrics data for ETH, SOL, DOGE.
Provides resampling, indicator computation, and derived metrics.
"""

import streamlit as st
import pandas as pd
import numpy as np
import os

# ============================================================
# CONSTANTS
# ============================================================
COINS = ["ETH", "SOL", "DOGE"]
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
CANDLES_DIR = os.path.join(DATA_DIR, "candles")
LIQUID_DIR = os.path.join(DATA_DIR, "liquid")
METRICS_DIR = os.path.join(DATA_DIR, "detail")

BULL_COLOR = "#00d4aa"
BEAR_COLOR = "#ff4976"
ACCENT_COLOR = "#6366f1"
WARNING_COLOR = "#f59e0b"
BG_COLOR = "#0a0e17"
CARD_BG = "#111827"
TEXT_PRIMARY = "#e5e7eb"
TEXT_SECONDARY = "#9ca3af"


# ============================================================
# RAW DATA LOADERS
# ============================================================
@st.cache_data(ttl=3600)
def load_candles(coin: str) -> pd.DataFrame:
    """Load 5-minute candle data for a coin."""
    path = os.path.join(CANDLES_DIR, f"{coin}USD_PERP_5m.csv")
    df = pd.read_csv(path)
    df["open_time"] = pd.to_datetime(df["open_time"])
    df["close_time"] = pd.to_datetime(df["close_time"])
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    df["quote_volume"] = pd.to_numeric(df["quote_volume"], errors="coerce")
    df["taker_buy_volume"] = pd.to_numeric(df["taker_buy_volume"], errors="coerce")
    df["taker_buy_quote_volume"] = pd.to_numeric(df["taker_buy_quote_volume"], errors="coerce")
    df["count"] = pd.to_numeric(df["count"], errors="coerce")
    df["coin"] = coin
    return df


@st.cache_data(ttl=3600)
def load_liquidations(coin: str) -> pd.DataFrame:
    """Load liquidation snapshot data for a coin."""
    path = os.path.join(LIQUID_DIR, f"{coin}USD_PERP_liquidation.csv")
    df = pd.read_csv(path)
    df["time"] = pd.to_datetime(df["time"])
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["average_price"] = pd.to_numeric(df["average_price"], errors="coerce")
    df["original_quantity"] = pd.to_numeric(df["original_quantity"], errors="coerce")
    df["last_fill_quantity"] = pd.to_numeric(df["last_fill_quantity"], errors="coerce")
    df["accumulated_fill_quantity"] = pd.to_numeric(df["accumulated_fill_quantity"], errors="coerce")
    # BUY side = Long liquidation (forced buy = short was liquidated? No.)
    # In futures liquidation: side=BUY means the liquidation order is a BUY,
    # which means a SHORT position was liquidated.
    # side=SELL means a LONG position was liquidated.
    df["liq_side"] = df["side"].map({"BUY": "Short Liq", "SELL": "Long Liq"})
    df["liq_value"] = df["accumulated_fill_quantity"] * df["average_price"]
    df["coin"] = coin
    return df


@st.cache_data(ttl=3600)
def load_metrics(coin: str) -> pd.DataFrame:
    """Load metrics data (OI, long/short ratios) for a coin."""
    path = os.path.join(METRICS_DIR, f"{coin}USD_PERP_metrics.csv")
    df = pd.read_csv(path)
    df["create_time"] = pd.to_datetime(df["create_time"])
    for col in [
        "sum_open_interest",
        "sum_open_interest_value",
        "count_toptrader_long_short_ratio",
        "sum_toptrader_long_short_ratio",
        "count_long_short_ratio",
        "sum_taker_long_short_vol_ratio",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["coin"] = coin
    return df


# ============================================================
# MULTI-COIN LOADERS
# ============================================================
@st.cache_data(ttl=3600)
def load_all_candles() -> pd.DataFrame:
    """Load and concatenate candle data for all coins."""
    frames = [load_candles(c) for c in COINS]
    return pd.concat(frames, ignore_index=True)


@st.cache_data(ttl=3600)
def load_all_liquidations() -> pd.DataFrame:
    """Load and concatenate liquidation data for all coins."""
    frames = [load_liquidations(c) for c in COINS]
    return pd.concat(frames, ignore_index=True)


@st.cache_data(ttl=3600)
def load_all_metrics() -> pd.DataFrame:
    """Load and concatenate metrics data for all coins."""
    frames = [load_metrics(c) for c in COINS]
    return pd.concat(frames, ignore_index=True)


# ============================================================
# RESAMPLING
# ============================================================
def resample_candles(df: pd.DataFrame, freq: str = "1h") -> pd.DataFrame:
    """
    Resample OHLCV candle data to a coarser frequency.
    freq: '5min', '1h', '4h', '1D'
    """
    if freq == "5min":
        return df.copy()

    resampled_frames = []
    for coin in df["coin"].unique():
        coin_df = df[df["coin"] == coin].copy()
        coin_df = coin_df.set_index("open_time").sort_index()
        agg = coin_df.resample(freq).agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
                "quote_volume": "sum",
                "taker_buy_volume": "sum",
                "taker_buy_quote_volume": "sum",
                "count": "sum",
            }
        )
        agg = agg.dropna(subset=["open"])
        agg["coin"] = coin
        agg = agg.reset_index()
        resampled_frames.append(agg)

    return pd.concat(resampled_frames, ignore_index=True)


def resample_metrics(df: pd.DataFrame, freq: str = "1h") -> pd.DataFrame:
    """Resample metrics data to a coarser frequency."""
    if freq == "5min":
        return df.copy()

    resampled_frames = []
    for coin in df["coin"].unique():
        coin_df = df[df["coin"] == coin].copy()
        coin_df = coin_df.set_index("create_time").sort_index()
        agg = coin_df.resample(freq).agg(
            {
                "sum_open_interest": "last",
                "sum_open_interest_value": "last",
                "count_toptrader_long_short_ratio": "mean",
                "sum_toptrader_long_short_ratio": "mean",
                "count_long_short_ratio": "mean",
                "sum_taker_long_short_vol_ratio": "mean",
            }
        )
        agg = agg.dropna(subset=["sum_open_interest"])
        agg["coin"] = coin
        agg = agg.reset_index()
        resampled_frames.append(agg)

    return pd.concat(resampled_frames, ignore_index=True)


def aggregate_liquidations(df: pd.DataFrame, freq: str = "1h") -> pd.DataFrame:
    """
    Aggregate liquidation data by time bucket and side.
    Returns columns: time_bucket, liq_side, total_quantity, total_value, count, coin
    """
    result_frames = []
    for coin in df["coin"].unique():
        coin_df = df[df["coin"] == coin].copy()
        coin_df["time_bucket"] = coin_df["time"].dt.floor(freq)
        agg = (
            coin_df.groupby(["time_bucket", "liq_side"])
            .agg(
                total_quantity=("accumulated_fill_quantity", "sum"),
                total_value=("liq_value", "sum"),
                liq_count=("time", "count"),
            )
            .reset_index()
        )
        agg["coin"] = coin
        result_frames.append(agg)

    return pd.concat(result_frames, ignore_index=True)


# ============================================================
# INDICATORS & DERIVED METRICS
# ============================================================
def compute_ma(df: pd.DataFrame, window: int, col: str = "close") -> pd.Series:
    """Compute simple moving average."""
    return df[col].rolling(window=window, min_periods=1).mean()


def compute_bollinger_bands(df: pd.DataFrame, window: int = 20, num_std: int = 2):
    """Compute Bollinger Bands."""
    ma = df["close"].rolling(window=window, min_periods=1).mean()
    std = df["close"].rolling(window=window, min_periods=1).std()
    return ma, ma + num_std * std, ma - num_std * std


def compute_price_change_pct(df: pd.DataFrame) -> pd.Series:
    """Compute percentage change of close price."""
    return df["close"].pct_change() * 100


def compute_candle_body_pct(df: pd.DataFrame) -> pd.Series:
    """Compute candle body as percentage of open price: (close - open) / open * 100."""
    return (df["close"] - df["open"]) / df["open"] * 100


def detect_large_red_candles(df: pd.DataFrame, threshold_pct: float = -1.0) -> pd.Series:
    """Flag candles with body < threshold_pct (large drops)."""
    body_pct = compute_candle_body_pct(df)
    return body_pct < threshold_pct


def compute_taker_buy_ratio(df: pd.DataFrame) -> pd.Series:
    """Compute taker buy volume / total volume ratio."""
    return df["taker_buy_volume"] / df["volume"].replace(0, np.nan)


def compute_oi_change_pct(df: pd.DataFrame) -> pd.Series:
    """Compute OI percentage change."""
    return df["sum_open_interest_value"].pct_change() * 100


def compute_liquidation_imbalance(liq_agg: pd.DataFrame) -> pd.DataFrame:
    """
    Compute liquidation imbalance: (Long Liq - Short Liq) / Total.
    Positive = more long liquidations, Negative = more short liquidations.
    """
    pivot = liq_agg.pivot_table(
        index=["time_bucket", "coin"],
        columns="liq_side",
        values="total_value",
        fill_value=0,
    ).reset_index()

    if "Long Liq" not in pivot.columns:
        pivot["Long Liq"] = 0
    if "Short Liq" not in pivot.columns:
        pivot["Short Liq"] = 0

    total = pivot["Long Liq"] + pivot["Short Liq"]
    pivot["liq_imbalance"] = (pivot["Long Liq"] - pivot["Short Liq"]) / total.replace(0, np.nan)
    return pivot


def compute_rolling_correlation(candles_df: pd.DataFrame, window: int = 7 * 288) -> pd.DataFrame:
    """
    Compute rolling correlation of returns between coins.
    window: number of candles (7 days * 288 candles/day for 5min data).
    Returns a long-format DataFrame with pairs and rolling correlation values.
    """
    # Pivot to get returns for each coin
    returns = candles_df.pivot_table(
        index="open_time", columns="coin", values="close"
    ).pct_change()

    correlations = []
    coins = returns.columns.tolist()
    for i, c1 in enumerate(coins):
        for j, c2 in enumerate(coins):
            if i <= j:
                rolling_corr = returns[c1].rolling(window=window, min_periods=50).corr(returns[c2])
                corr_df = pd.DataFrame(
                    {
                        "time": returns.index,
                        "coin_1": c1,
                        "coin_2": c2,
                        "correlation": rolling_corr.values,
                    }
                )
                correlations.append(corr_df)

    return pd.concat(correlations, ignore_index=True).dropna(subset=["correlation"])


# ============================================================
# FILTERING HELPERS
# ============================================================
def filter_by_date(df: pd.DataFrame, start_date, end_date, time_col: str = "open_time") -> pd.DataFrame:
    """Filter DataFrame by date range."""
    mask = (df[time_col] >= pd.Timestamp(start_date)) & (df[time_col] <= pd.Timestamp(end_date) + pd.Timedelta(days=1))
    return df[mask].copy()


def filter_by_coins(df: pd.DataFrame, coins: list) -> pd.DataFrame:
    """Filter DataFrame by selected coins."""
    return df[df["coin"].isin(coins)].copy()


# ============================================================
# TIMEFRAME MAPPING
# ============================================================
TIMEFRAME_MAP = {
    "5 phút": "5min",
    "1 giờ": "1h",
    "4 giờ": "4h",
    "1 ngày": "1D",
}

FREQ_MAP = {
    "5 phút": "5min",
    "1 giờ": "1h",
    "4 giờ": "4h",
    "1 ngày": "1D",
}
