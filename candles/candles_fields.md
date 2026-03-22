# Candlestick (Klines) Data — Field Definitions

> **Source:** Binance USDⓈ-Margined Futures API — `GET /fapi/v1/klines`
> **Interval:** 1 hour (`1h`)
> **Symbols:** `ETHUSD_PERP`, `SOLUSD_PERP`, `DOGEUSD_PERP`
> **Format:** CSV (converted from Parquet)

---

## Field Definitions

| CSV Column | API Array Index | Field Name | Type | Unit | Description |
|:---|:---:|---|---|---|---|
| `open_time` | `[0]` | Open time | `long` | Unix timestamp (ms) → parsed to `datetime` | **Start time** of the candlestick interval |
| `open` | `[1]` | Open | `string/number` | Quote asset (USDT) | Opening price at `open_time` |
| `high` | `[2]` | High | `string/number` | Quote asset (USDT) | Highest price **during** the interval |
| `low` | `[3]` | Low | `string/number` | Quote asset (USDT) | Lowest price **during** the interval |
| `close` | `[4]` | Close | `string/number` | Quote asset (USDT) | Closing price at `close_time` |
| `volume` | `[5]` | Taker buy **base** asset volume | `string/number` | **Base asset** (e.g. ETH, SOL, DOGE) | Volume of taker **buy** orders in the base asset |
| `close_time` | `[6]` | Close time | `long` | Unix timestamp (ms) → parsed to `datetime` | **End time** of the candlestick interval |
| `quote_volume` | `[7]` | Quote asset volume | `string/number` | **Quote asset** (USDT) | Total traded volume in the quote asset (USDT) |
| `count` | `[8]` | Number of trades | `int` | Integer | Total number of trades executed in the interval |
| `taker_buy_volume` | `[9]` | Taker buy base asset volume | `string/number` | **Base asset** (e.g. ETH, SOL, DOGE) | Volume of taker **buy** orders in the base asset |
| `taker_buy_quote_volume` | `[10]` | Taker buy quote asset volume | `string/number` | **Quote asset** (USDT) | Volume of taker **buy** orders in the quote asset |
| `ignore` | `[11]` | Ignore | `string` | — | **Unused** — reserved field, always `0` |

---

## Unit Clarification

| Asset Type | Examples in your data | Meaning |
|---|---|---|
| **Base asset** | ETH, SOL, DOGE | The perpetual futures contract's underlying coin |
| **Quote asset** | USDT | The currency used to quote prices |

**Example for `ETHUSD_PERP_1h.csv`:**

| Field | Example Value | Unit |
|---|---|---|
| `open` / `high` / `low` / `close` | `2283.22` | USDT |
| `volume` | `2053984` | ETH |
| `quote_volume` | `8956.99` | USDT |
| `taker_buy_volume` | `1136982` | ETH |
| `taker_buy_quote_volume` | `4958.98` | USDT |

> **Note:** `volume` and `taker_buy_volume` are in **base asset units** (coin amount), while `quote_volume` and `taker_buy_quote_volume` are in **quote asset units** (USDT value). The two are related by price: `quote_volume ≈ volume × average_price`.

---

## Usage in Dashboard

| Field | Used in Dashboard? | How It's Used |
|---|---|---|
| `open_time` | ✅ | X-axis timestamp for all chart panels |
| `open` | ✅ | Candlestick body left edge; bull/bear color logic |
| `high` | ✅ | Candlestick wick high; Volume Profile `price_max` |
| `low` | ✅ | Candlestick wick low; Volume Profile `price_min` |
| `close` | ✅ | Candlestick body right edge; MA lines; correlation charts |
| `volume` | ✅ | Volume bar chart (Panel 1); Volume Profile; market signals |
| `close_time` | ⚠️ Parsed only | Loaded but never referenced — `open_time` is used instead |
| `quote_volume` | ⚠️ Resampled only | Aggregated (`sum`) in `resample_candles()` — not rendered |
| `count` | ⚠️ Resampled only | Aggregated (`sum`) in `resample_candles()` — not rendered |
| `taker_buy_volume` | ✅ | Taker buy ratio (`taker_buy_volume / volume`); market signals |
| `taker_buy_quote_volume` | ⚠️ Resampled only | Aggregated (`sum`) in `resample_candles()` — not rendered |
| `ignore` | ❌ Unused | Always `0` — never referenced anywhere |

---

## API Reference

- **Official Docs:** [Binance REST API — klines](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md)
- **Developer Docs:** [Binance Developers — Klines](https://developers.binance.com/docs/derivatives/usds-market-data/klines)
- **Data Source:** [data.binance.vision](https://data.binance.vision/?prefix=data/futures/cm/daily/klines/)
