# Tải

Nến (5 phút = 5m, 1 phút = 1m, ...): https://data.binance.vision/?prefix=data/futures/cm/daily/klines/ETHUSD_PERP/5m/

Thanh lý: https://data.binance.vision/?prefix=data/futures/cm/daily/liquidationSnapshot/ETHUSD_PERP/

Các chỉ số khác: https://data.binance.vision/?prefix=data/futures/cm/daily/metrics/ETHUSD_PERP/

còn cái coin khác như DOGE thì thêm hậu tố USD_PERP (như trên)

ae down đúng tất cả trong khoảng thời gian như trong proposal, viết script để down (claude/gemini)

Mỗi file là theo ngày (như ngày 2024-01-31), tên có format, vd như kline (nến) 5 phút: "<coin>USD_PERP-5m-<date>.zip", trong đó <coin> = ETH, <date> = 2024-01-31. Có thể lên web xem các loại khác.

# Tiền xử lý
Định dạng là csv, có thể tiền xử lý để phù hợp cho plot, dùng: pandas, numpy,...

# Hiểu data
Các coin dự kiến dùng: BTC, ETH, SOL, DOGE 

Data là coin margined futures (KO phải USD-S), lấy asset coin (BTC, ETH,...) để trade và tính PnL (lãi/lỗ).

Hậu tố _PERP là hợp đồng vĩnh cửu, contract k bao h hết hạn
