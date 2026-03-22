# Liquidation (Force Liquidation) Data — Field Definitions

> **Source:** Binance USDⓈ-Margined Futures API — `GET /fapi/v1/allForceOrders`
> **Data Type:** Individual force liquidation events (snapshots)
> **Symbols:** `ETHUSD_PERP`, `SOLUSD_PERP`, `DOGEUSD_PERP`
> **Format:** CSV (converted from daily snapshot zips)
> **Note:** This data comes from Binance's **liquidation snapshot** files (`liquidationSnapshot/`), which aggregate force liquidation events per time bucket. Each row represents one individual liquidation order.

---

## Field Definitions

| CSV Column | Field Name | Type | Unit | Description |
|:---|:---|:---|:---|:---|
| `time` | Event time | `datetime` | UTC | **Timestamp** when the force liquidation event occurred |
| `side` | Order side | `string` | — | Direction of the liquidated position: `BUY` (long position liquidated) or `SELL` (short position liquidated) |
| `order_type` | Order type | `string` | — | Order type used in the liquidation: `LIMIT`, `MARKET`, `STOP`, etc. Here always `LIMIT` |
| `time_in_force` | Time in force | `string` | — | Order execution condition: `IOC` (Immediate-Or-Cancel), `GTC` (Good-Till-Cancel), etc. Here always `IOC` |
| `original_quantity` | Original quantity | `float` | **Base asset** (e.g. ETH, SOL, DOGE) | **Total quantity** of the liquidated position (before fills) |
| `price` | Order price | `float` | Quote asset (USDT) | The **limit price** specified in the liquidation order |
| `average_price` | Average fill price | `float` | Quote asset (USDT) | The **weighted average execution price** at which the position was fully filled |
| `order_status` | Order status | `string` | — | Status of the liquidation order: `FILLED` (fully liquidated), `PARTIALLY_FILLED`, `CANCELED`, etc. Here always `FILLED` |
| `last_fill_quantity` | Last fill quantity | `float` | **Base asset** (e.g. ETH, SOL, DOGE) | Quantity filled in the **last individual trade** of the liquidation sequence |
| `accumulated_fill_quantity` | Accumulated fill quantity | `float` | **Base asset** (e.g. ETH, SOL, DOGE) | **Total quantity** that has been filled so far (sum of all partial fills) |

---

## Key Concepts

### What is a Force Liquidation?
When a trader's position margin falls below the **maintenance margin threshold**, Binance automatically liquidates (closes) their position at the **bankruptcy price**. The liquidated position is then taken over by the **auto-deleveraging (ADL) queue** or **insurance fund**.

### Side Meaning
| `side` Value | Meaning | Dashboard Label |
|---|---|---|
| `BUY` | A **long** position was liquidated | `Long Liq` (🔴 Short traders profit) |
| `SELL` | A **short** position was liquidated | `Short Liq` (🟢 Long traders profit) |

### Quantity Fields Explained

| Field | What It Represents | In Your Data |
|---|---|---|
| `original_quantity` | Total size of the liquidated position | Matches `accumulated_fill_quantity` (fully filled) |
| `accumulated_fill_quantity` | Total filled so far | Equals `original_quantity` (status = `FILLED`) |
| `last_fill_quantity` | Size of the last individual fill | ≤ `original_quantity` |

### Value Calculation
The **USD value** of a liquidation event is computed as:

```
liq_value = accumulated_fill_quantity × average_price
```

This formula is used in `data_loader.py` to compute `liq_value` for aggregation.

---

## Unit Clarification

| Asset Type | Examples in your data | Meaning |
|---|---|---|
| **Base asset** | ETH, SOL, DOGE | The perpetual futures contract's underlying coin |
| **Quote asset** | USDT | The currency used to quote prices |

**Example for `ETHUSD_PERP_liquidation.csv`:**

| Field | Example Value | Unit |
|---|---|---|
| `original_quantity` | `3` | ETH |
| `price` | `2302.09` | USDT |
| `average_price` | `2291.22` | USDT |
| `accumulated_fill_quantity` | `3` | ETH |
| `liq_value` (computed) | `3 × 2291.22 = 6873.66` | USDT |

---

## Usage in Dashboard

| Field | Used in Dashboard? | How It's Used |
|---|---|---|
| `time` | ✅ | X-axis time bucket aggregation for all liquidation charts |
| `side` | ✅ | Split into `Long Liq` vs `Short Liq` series in charts |
| `order_type` | ❌ Unused | Not referenced anywhere |
| `time_in_force` | ❌ Unused | Not referenced anywhere |
| `original_quantity` | ✅ | Used to compute `liq_value = original_quantity × average_price` |
| `price` | ❌ Unused | Not referenced anywhere |
| `average_price` | ✅ | Used as the fill price in `liq_value` computation |
| `order_status` | ❌ Unused | Not referenced — data is already filtered to `FILLED` events |
| `last_fill_quantity` | ❌ Unused | Not referenced anywhere |
| `accumulated_fill_quantity` | ✅ | Used as the primary quantity field in `liq_value = accumulated_fill_quantity × average_price` |

---

## API Reference

- **Official REST API:** `GET /fapi/v1/allForceOrders` — [Binance API Docs](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md)
- **Data Source:** [data.binance.vision](https://data.binance.vision/?prefix=data/futures/cm/daily/liquidationSnapshot/)
- **Note:** Your data comes from **liquidation snapshots** (`liquidationSnapshot/`), not the raw `allForceOrders` stream. The snapshot aggregates events over time buckets, while the API returns individual liquidation orders.
