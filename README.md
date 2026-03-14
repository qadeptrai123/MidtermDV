# Project Structure

## Data

- `candles/`: 1h candles of ETH, DOGE, SOL
- `liquidations/`: Liquidations of ETH, DOGE, SOL
- `metrics/`: Metrics of ETH, DOGE, SOL

_render_kpi_strip(): Thẻ tổng quan thị trường (giá, tổng thanh lý). Nằm từ dòng 71.
_render_candlestick_panel(): Biểu đồ Nến & Khối Lượng. Nằm từ dòng 96.
_render_oi_panel(): Biểu đồ Open Interest. Nằm từ dòng 173.
_render_liquidation_echarts(): Biểu đồ Thanh lý (Coinglass Style, dạng Area). Nằm từ dòng 213.
_render_volume_profile(): Hồ sơ khối lượng (Volume Profile). Nằm từ dòng 353.
_render_correlation_panel(): Ma trận tương quan giá (Heatmap). Nằm từ dòng 407.
_render_rolling_correlation_panel(): Tương quan biến động Rolling. Nằm từ dòng 445.
_render_ls_ratio_panel(): Tỷ lệ Long/Short. Nằm từ dòng 495.
_render_taker_ratio_panel(): Tỷ lệ Taker Mua/Bán & Giá. Nằm từ dòng 540.
_render_synced_panel(): Biểu đồ đồng bộ Giá - OI - Thanh lý (3 trục). Nằm từ dòng 594.
_render_market_signals_panel(): Tín hiệu trạng thái thị trường (Hưng phấn / Hoảng loạn). Nằm từ dòng 692.
render_dashboard(): Hàm lắp ghép tất cả các hàm trên vào 1 giao diện chung. Nằm từ dòng 888.