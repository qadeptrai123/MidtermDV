# Data Dictionary — Crypto Futures Dashboard

> **Coins:** ETH, SOL, DOGE (USD Perpetual Futures)
> **Period:** Q1/2024 (2024-01-01 → 2024-03-03)
> **Base Interval:** 1 hour (1h)
> **Type:** Binance Coin-Margined Perpetual Futures (`*USD_PERP`)

---

## Data Sources

| Dataset | Folder | API Endpoint | Data Type |
|---|---|---|---|
| **Candlesticks (OHLCV)** | `candles/` | `GET /fapi/v1/klines` | OHLCV price & volume bars |
| **Liquidations** | `liquid/` | `GET /fapi/v1/allForceOrders` (snapshots) | Individual force liquidation events |
| **Metrics** | `detail/` | Multiple `/fapi/v1/*` endpoints | Open interest + sentiment ratios |

**Download source:** [data.binance.vision](https://data.binance.vision/?prefix=data/futures/cm/daily/)

---

## Quick Reference

### candles/*.csv — 12 fields
| # | Field | Unit | Description |
|---|---|---|---|
| 1 | `open_time` | datetime | Candle start time |
| 2 | `open` | USDT | Opening price |
| 3 | `high` | USDT | Highest price in interval |
| 4 | `low` | USDT | Lowest price in interval |
| 5 | `close` | USDT | Closing price |
| 6 | `volume` | **Base coin** | Total volume (in coin units) |
| 7 | `close_time` | datetime | Candle end time |
| 8 | `quote_volume` | USDT | Total volume (in USDT) |
| 9 | `count` | int | Number of trades |
| 10 | `taker_buy_volume` | **Base coin** | Taker buy volume (coin units) |
| 11 | `taker_buy_quote_volume` | USDT | Taker buy volume (USDT) |
| 12 | `ignore` | — | Always 0 — unused |

### liquid/*.csv — 10 fields
| # | Field | Unit | Description |
|---|---|---|---|
| 1 | `time` | datetime | Liquidation event time |
| 2 | `side` | — | `BUY` = long liq, `SELL` = short liq |
| 3 | `order_type` | — | Order type (always `LIMIT`) |
| 4 | `time_in_force` | — | Execution condition (always `IOC`) |
| 5 | `original_quantity` | **Base coin** | Total liquidated quantity |
| 6 | `price` | USDT | Limit price of liquidation order |
| 7 | `average_price` | USDT | Average fill price |
| 8 | `order_status` | — | Status (always `FILLED`) |
| 9 | `last_fill_quantity` | **Base coin** | Size of last partial fill |
| 10 | `accumulated_fill_quantity` | **Base coin** | Total filled quantity |

### detail/*.csv — 8 fields
| # | Field | Unit | Description |
|---|---|---|---|
| 1 | `create_time` | datetime | Metric snapshot time |
| 2 | `symbol` | — | Trading pair |
| 3 | `sum_open_interest` | **Base coin** | Open interest (coin units) |
| 4 | `sum_open_interest_value` | USDT | Open interest (USDT value) |
| 5 | `count_toptrader_long_short_ratio` | ratio | Top traders L/S (count-based) |
| 6 | `sum_toptrader_long_short_ratio` | ratio | Top traders L/S (notional-weighted) |
| 7 | `count_long_short_ratio` | ratio | All traders L/S (count-based) |
| 8 | `sum_taker_long_short_vol_ratio` | ratio | Taker volume L/S ratio |

---

## Long/Short Ratio Interpretation

```
ratio > 1.0  →  More longs than shorts  (bullish)
ratio < 1.0  →  More shorts than longs  (bearish)
ratio = 1.0  →  Balanced
```

---

## Liquidation Side Interpretation

| `side` | Labeled As | Who Profits |
|---|---|---|
| `BUY` (order to BUY the base coin) | `Long Liq` 🔴 | Short traders |
| `SELL` (order to SELL the base coin) | `Short Liq` 🟢 | Long traders |

---

## Long/Short Ratio Sources

| Field | Population | Weighting |
|---|---|---|
| `count_toptrader_long_short_ratio` | Top 20% traders by volume | Count of positions |
| `sum_toptrader_long_short_ratio` | Top 20% traders by volume | Notional (USD) size |
| `count_long_short_ratio` | All traders | Count of positions |
| `sum_taker_long_short_vol_ratio` | All takers (fills) | Taker volume |

---

## Detailed Field Documentation

See the per-dataset field documentation files:

| File | Dataset |
|---|---|
| `candles/candles_fields.md` | Candlestick (OHLCV) data — full field definitions, units, API source |
| `liquid/liquid_fields.md` | Liquidation data — full field definitions, liquidation concepts, API source |
| `detail/detail_fields.md` | Metrics data — full field definitions, ratio interpretations, API source |

---

## Data Download Notes

- **Perpetual futures** (`_PERP`): contracts that never expire
- **Coin-margined**: PnL and margins settled in the base coin (ETH, SOL, DOGE), not USDT
- Each daily file is named by date (e.g. `ETHUSD_PERP-1h-2024-01-01.csv`)
- Scripts: `download_data.py` (download), `convert_to_parquet.py` (convert to Parquet)
