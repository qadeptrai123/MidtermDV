# Futures Metrics (Open Interest & Sentiment) Data — Field Definitions

> **Source:** Binance USDⓈ-Margined Futures API — Multiple endpoints
> - `GET /fapi/v1/openInterestHist` — Open Interest History
> - `GET /fapi/v1/topLongShortPositionRatio` — Top Trader Long/Short Ratio
> - `GET /fapi/v1/longShortRatio` — Long/Short Ratio
> - `GET /fapi/v1/takerLongShortVolRatio` — Taker Long/Short Volume Ratio
> **Interval:** 5 minutes (`5m`), aggregated to `1h`
> **Symbols:** `ETHUSD_PERP`, `SOLUSD_PERP`, `DOGEUSD_PERP`
> **Format:** CSV (converted from daily metrics files)
> **Note:** This data comes from Binance's **metrics** files (`metrics/`), which bundle multiple indicators into one time-series.

---

## Field Definitions

| CSV Column | Field Name | Type | Unit | Description |
|:---|:---|:---|:---|:---|
| `create_time` | Creation time | `datetime` | UTC | **Timestamp** when this metric snapshot was recorded |
| `symbol` | Symbol | `string` | — | Trading pair identifier, e.g. `ETHUSD_PERP` |
| `sum_open_interest` | Open interest (base) | `float` | **Base asset** (e.g. ETH) | Total open interest in **base asset units** — sum of all open positions in the contract |
| `sum_open_interest_value` | Open interest (quote) | `float` | Quote asset (USDT) | Total open interest in **USDT value** — `sum_open_interest × index_price` |
| `count_toptrader_long_short_ratio` | Top trader L/S ratio (count) | `float` | Ratio | **Count-based** long/short ratio among **top 20% traders** by volume — ratio = `long_count / short_count` |
| `sum_toptrader_long_short_ratio` | Top trader L/S ratio (sum) | `float` | Ratio | **Position-size-weighted** long/short ratio among top traders — ratio = `long_notional / short_notional` |
| `count_long_short_ratio` | Long/short ratio (count) | `float` | Ratio | **Count-based** long/short ratio among **all traders** — ratio = `long_count / short_count` |
| `sum_taker_long_short_vol_ratio` | Taker L/S volume ratio | `float` | Ratio | **Taker volume** based long/short ratio — ratio = `long_taker_volume / short_taker_volume` |

---

## Key Concepts

### Open Interest (OI)
**Open Interest** is the total value/volume of all open (unclosed) positions in a futures contract at a given time.

| Field | What It Measures | Unit |
|---|---|---|
| `sum_open_interest` | Total positions in **coin amount** | Base asset (e.g. ETH) |
| `sum_open_interest_value` | Total positions in **USD value** | USDT |

> **Why two OI fields?** `sum_open_interest` can be converted to USDT by multiplying with the index price. `sum_open_interest_value` is the pre-computed USD equivalent.

### Long/Short Ratios Explained

All L/S ratios follow this formula:

```
ratio > 1.0  →  More longs than shorts  (🟢 bullish sentiment)
ratio < 1.0  →  More shorts than longs  (🔴 bearish sentiment)
ratio = 1.0  →  Balanced
```

| Field | Population | Weighting | Use Case |
|---|---|---|---|
| `count_toptrader_long_short_ratio` | Top 20% traders by volume | Count of positions | Institutional positioning signal |
| `sum_toptrader_long_short_ratio` | Top 20% traders by volume | Notional (USD) size | Size-weighted institutional signal |
| `count_long_short_ratio` | **All** traders | Count of positions | Broad retail + institutional sentiment |
| `sum_taker_long_short_vol_ratio` | **All** taker orders | Taker volume | Aggressive trader direction (fills, not positions) |

> **Why both `*_count_*` and `*_sum_*`?** The `count_*` versions count how many traders are long vs short. The `sum_*` versions weight by position size — a large long holder and a small long holder count equally in `count_*`, but the large holder dominates in `sum_*`.

### Taker Long/Short Volume Ratio
Takers are traders who **immediately match** against existing orders (as opposed to makers who place limit orders). This ratio shows the **directional aggression** of active traders:

```
sum_taker_long_short_vol_ratio > 1  →  Takers are buying more than selling  (aggressive long)
sum_taker_long_short_vol_ratio < 1  →  Takers are selling more than buying  (aggressive short)
```

---

## Ratio Interpretation Guide

| Ratio Value | `count_toptrader_long_short_ratio` / `sum_toptrader_long_short_ratio` | `count_long_short_ratio` | `sum_taker_long_short_vol_ratio` |
|---|---|---|---|
| `> 1.5` | Strong 🟢 long bias among top traders | Strong 🟢 long bias overall | Aggressive 🟢 buying pressure |
| `1.0 – 1.5` | Mild 🟢 long bias | Mild 🟢 long bias | Mild 🟢 buying pressure |
| `= 1.0` | Balanced | Balanced | Neutral |
| `0.5 – 1.0` | Mild 🔴 short bias | Mild 🔴 short bias | Mild 🔴 selling pressure |
| `< 0.5` | Strong 🔴 short bias among top traders | Strong 🔴 short bias overall | Aggressive 🔴 selling pressure |

---

## Unit Clarification

| Asset Type | Examples in your data | Meaning |
|---|---|---|
| **Base asset** | ETH, SOL, DOGE | The perpetual futures contract's underlying coin |
| **Quote asset** | USDT | The currency used to quote prices |

**Example for `ETHUSD_PERP_metrics.csv`:**

| Field | Example Value | Unit |
|---|---|---|
| `sum_open_interest` | `35933019.0` | ETH |
| `sum_open_interest_value` | `157378.69` | USDT |
| `count_toptrader_long_short_ratio` | `—` (empty) | Ratio |
| `sum_toptrader_long_short_ratio` | `—` (empty) | Ratio |
| `count_long_short_ratio` | `—` (empty) | Ratio |
| `sum_taker_long_short_vol_ratio` | `0.6615` | Ratio |

> **Note:** Some fields may be empty (`NaN`) in early records — this is normal as Binance backfills data gradually.

---

## Usage in Dashboard

| Field | Used in Dashboard? | How It's Used |
|---|---|---|
| `create_time` | ✅ | X-axis timestamp for all metrics panels |
| `symbol` | ❌ Unused | Loaded but never referenced — coin is tracked via `coin` column added at load time |
| `sum_open_interest` | ✅ | OI Volume Correlation panel — daily average OI per coin |
| `sum_open_interest_value` | ✅ | OI line chart; OI + Price synced chart; market signals |
| `count_toptrader_long_short_ratio` | ✅ (commented) | Long/Short Ratio panel (Panel 6) — not rendered in current active panels |
| `sum_toptrader_long_short_ratio` | ❌ Unused | Not referenced anywhere |
| `count_long_short_ratio` | ✅ (commented) | Long/Short Ratio panel (Panel 6) — not rendered in current active panels |
| `sum_taker_long_short_vol_ratio` | ✅ | Taker Ratio chart (Panel 7, commented out) — not rendered in current active panels |

---

## API Reference

| Endpoint | Field(s) | Official Docs |
|---|---|---|
| `GET /fapi/v1/openInterestHist` | `sum_open_interest`, `sum_open_interest_value` | [Binance Developers](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/Get-Open-Interest-Statistics) |
| `GET /fapi/v1/topLongShortPositionRatio` | `count_toptrader_long_short_ratio`, `sum_toptrader_long_short_ratio` | [Binance Developers](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/Top-Long-Short-Position-Ratio) |
| `GET /fapi/v1/longShortRatio` | `count_long_short_ratio` | [Binance Developers](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/Long-Short-Ratio) |
| `GET /fapi/v1/takerLongShortVolRatio` | `sum_taker_long_short_vol_ratio` | [Binance Developers](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/Taker-Long-Short-Volume-Ratio) |
| **Combined** | All fields | [Combined Metrics Stream](https://developers.binance.com/docs/derivatives/coin-margined-futures/market-data/Get-Collective-Open-Interest) |
| **Data Source** | — | [data.binance.vision](https://data.binance.vision/?prefix=data/futures/cm/daily/metrics/) |
