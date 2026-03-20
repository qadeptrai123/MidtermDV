"""
Download Binance Futures (coin-margined) daily data:
  - Klines (candles)
  - Liquidation snapshots
  - Metrics (detail)

Extract from ZIP, merge into one CSV per symbol, and skip
symbols whose merged CSV already exists.

Usage:
    python download_data.py
"""

import os
import io
import zipfile
from datetime import date, timedelta

import requests
import pandas as pd

# ============================================================
# CONFIGURATION
# ============================================================
BASE_URL = "https://data.binance.vision/data/futures/cm/daily"
SYMBOLS = ["ETHUSD_PERP", "DOGEUSD_PERP", "SOLUSD_PERP"]
INTERVAL = "1h"
START_DATE = date(2024, 1, 1)
END_DATE = date(2024, 3, 6)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CANDLES_DIR = os.path.join(SCRIPT_DIR, "candles")
LIQUID_DIR = os.path.join(SCRIPT_DIR, "liquid")
DETAIL_DIR = os.path.join(SCRIPT_DIR, "detail")


# ============================================================
# HELPERS
# ============================================================
def _date_range(start: date, end: date):
    """Yield each date from *start* to *end* inclusive."""
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _download_and_merge(
    symbols: list[str],
    start_date: date,
    end_date: date,
    output_dir: str,
    url_builder,
    filename_builder,
    post_process=None,
    label: str = "data",
) -> dict[str, str]:
    """
    Generic download-merge pipeline.

    Parameters
    ----------
    symbols : list[str]
        Trading pair symbols.
    start_date, end_date : date
        Date range (inclusive).
    output_dir : str
        Directory for merged CSVs.
    url_builder : callable(symbol, date) -> str
        Returns the download URL for one day.
    filename_builder : callable(symbol) -> str
        Returns the output CSV filename for a symbol.
    post_process : callable(DataFrame) -> DataFrame, optional
        Extra transformations after merge (e.g. datetime conversion).
    label : str
        Human-readable label for console output.

    Returns
    -------
    dict[str, str]
        Mapping of symbol -> absolute path to merged CSV.
    """
    os.makedirs(output_dir, exist_ok=True)
    result_paths: dict[str, str] = {}

    for symbol in symbols:
        out_path = os.path.join(output_dir, filename_builder(symbol))

        # --- Skip if already downloaded ---
        if os.path.exists(out_path):
            print(f"\n[SKIP] {out_path} already exists. "
                  f"Delete it to re-download.")
            result_paths[symbol] = out_path
            continue

        print(f"\n{'='*60}")
        print(f"  Downloading {symbol} {label} "
              f"from {start_date} to {end_date}")
        print(f"{'='*60}")

        daily_frames: list[pd.DataFrame] = []
        total_days = (end_date - start_date).days + 1
        success_count = 0
        fail_count = 0

        for i, d in enumerate(_date_range(start_date, end_date), start=1):
            url = url_builder(symbol, d)
            progress = f"[{i}/{total_days}]"

            try:
                resp = requests.get(url, timeout=30)
                if resp.status_code == 200:
                    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                        csv_name = zf.namelist()[0]
                        with zf.open(csv_name) as csv_file:
                            df = pd.read_csv(csv_file)
                            daily_frames.append(df)
                    success_count += 1
                    print(f"  {progress} [OK] {d}")
                else:
                    fail_count += 1
                    print(f"  {progress} [FAIL] {d}  "
                          f"(HTTP {resp.status_code})")
            except Exception as exc:
                fail_count += 1
                print(f"  {progress} [FAIL] {d}  ({exc})")

        # Merge all daily DataFrames
        if daily_frames:
            merged = pd.concat(daily_frames, ignore_index=True)

            # Apply optional post-processing
            if post_process is not None:
                merged = post_process(merged)

            merged.to_csv(out_path, index=False)
            result_paths[symbol] = out_path

            print(f"\n  [DONE] Saved {len(merged):,} rows -> {out_path}")
        else:
            print(f"\n  [WARN] No data downloaded for {symbol}.")

        print(f"  Summary: {success_count} succeeded, {fail_count} failed "
              f"out of {total_days} days")

    return result_paths


# ============================================================
# POST-PROCESSING FUNCTIONS
# ============================================================
def _postprocess_candles(df: pd.DataFrame) -> pd.DataFrame:
    """Convert epoch-ms timestamps to readable datetimes."""
    df["open_time"] = pd.to_datetime(
        pd.to_numeric(df["open_time"]), unit="ms"
    )
    df["close_time"] = pd.to_datetime(
        pd.to_numeric(df["close_time"]), unit="ms"
    )
    df.sort_values("open_time", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def _postprocess_liquidation(df: pd.DataFrame) -> pd.DataFrame:
    """Convert epoch-ms timestamp to readable datetime."""
    df["time"] = pd.to_datetime(pd.to_numeric(df["time"]), unit="ms")
    df.sort_values("time", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def _postprocess_detail(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure create_time is datetime and sort."""
    df["create_time"] = pd.to_datetime(df["create_time"])
    df.sort_values("create_time", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


# ============================================================
# PUBLIC API
# ============================================================
def download_candles(
    symbols: list[str] = SYMBOLS,
    interval: str = INTERVAL,
    start_date: date = START_DATE,
    end_date: date = END_DATE,
    output_dir: str = CANDLES_DIR,
) -> dict[str, str]:
    """Download and merge daily kline (candle) data."""
    return _download_and_merge(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        output_dir=output_dir,
        url_builder=lambda sym, d: (
            f"{BASE_URL}/klines/{sym}/{interval}/"
            f"{sym}-{interval}-{d.isoformat()}.zip"
        ),
        filename_builder=lambda sym: f"{sym}_{interval}.csv",
        post_process=_postprocess_candles,
        label=f"klines ({interval})",
    )


def download_liquidation(
    symbols: list[str] = SYMBOLS,
    start_date: date = START_DATE,
    end_date: date = END_DATE,
    output_dir: str = LIQUID_DIR,
) -> dict[str, str]:
    """Download and merge daily liquidation snapshot data."""
    return _download_and_merge(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        output_dir=output_dir,
        url_builder=lambda sym, d: (
            f"{BASE_URL}/liquidationSnapshot/{sym}/"
            f"{sym}-liquidationSnapshot-{d.isoformat()}.zip"
        ),
        filename_builder=lambda sym: f"{sym}_liquidation.csv",
        post_process=_postprocess_liquidation,
        label="liquidation",
    )


def download_detail(
    symbols: list[str] = SYMBOLS,
    start_date: date = START_DATE,
    end_date: date = END_DATE,
    output_dir: str = DETAIL_DIR,
) -> dict[str, str]:
    """Download and merge daily metrics (detail) data."""
    return _download_and_merge(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        output_dir=output_dir,
        url_builder=lambda sym, d: (
            f"{BASE_URL}/metrics/{sym}/"
            f"{sym}-metrics-{d.isoformat()}.zip"
        ),
        filename_builder=lambda sym: f"{sym}_metrics.csv",
        post_process=_postprocess_detail,
        label="metrics",
    )


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  [1/3] Downloading CANDLES")
    print("=" * 60)
    candle_paths = download_candles()

    # print("\n" + "=" * 60)
    # print("  [2/3] Downloading LIQUIDATION SNAPSHOTS")
    # print("=" * 60)
    # liquid_paths = download_liquidation()

    # print("\n" + "=" * 60)
    # print("  [3/3] Downloading METRICS (DETAIL)")
    # print("=" * 60)
    # detail_paths = download_detail()

    print("\n" + "=" * 60)
    print("  All downloads complete!")
    print("=" * 60)
    for label, paths in [("Candles", candle_paths),
    ]:
                        #  ("Liquidation", liquid_paths),
                        #  ("Metrics", detail_paths)]:
        print(f"\n  {label}:")
        for sym, p in paths.items():
            print(f"    {sym} -> {p}")