# Bảng Ánh Xạ: Panel Dashboard ↔ Câu Hỏi Phân Tích

> Mỗi panel trên dashboard không chỉ trả lời một câu hỏi — chúng **kết hợp với nhau** để cung cấp bức tranh toàn diện.

## Ánh xạ chính

| Panel trên Dashboard | Dữ liệu sử dụng | Câu hỏi được trả lời |
|---|---|---|
| **Biểu đồ Nến + MA(7/25) + Khối lượng** | `candles` | Q1: Xu hướng giá ETH vs MA(7) |
| **Ma trận Tương quan Giá** | `candles` (tất cả coins) | Q2: Tương quan giá giữa các coin khi euphoria/panic |
| **Biểu đồ Nến + OI + Thanh lý** (đồng bộ) | `candles` + `metrics` + `liquid` | Q3: Nến đỏ dài → OI + thanh lý |
| **Open Interest + Thanh lý Timeline** | `metrics` + `liquid` | Q4: Diễn biến OI + thanh lý trong ngày crash |
| **Tín hiệu Trạng thái Thị trường** (heatmap tổng hợp) | Tất cả | Q5: Dự đoán trạng thái hưng phấn/hoảng loạn |
| **Hồ sơ Khối lượng** (Volume Profile) | `candles` | Q6: Vùng thanh khoản & hỗ trợ/kháng cự |
| **Tỷ lệ Long/Short** (Whale vs Tổng thể) | `metrics` | Q7: Phân kỳ tâm lý cá voi vs nhỏ lẻ |
| **Tỷ lệ Taker Mua/Bán + Giá** | `candles` + `metrics` | Q8: Áp lực taker → hướng giá |

## Ánh xạ chi tiết: Câu hỏi → Các panel liên quan

| Câu hỏi | Panel chính | Panel hỗ trợ |
|---|---|---|
| **Q1** – Giá vs MA(7) | Biểu đồ Nến + MA | KPI Strip (giá, % thay đổi) |
| **Q2** – Tương quan giá | Ma trận Tương quan | Biểu đồ Nến (chuyển coin để so sánh) |
| **Q3** – Nến đỏ dài → OI + Liq | Biểu đồ Nến + OI + Thanh lý | Volume Profile (vùng giá có khối lượng lớn) |
| **Q4** – Crash day | OI Timeline + Thanh lý Timeline | Biểu đồ Nến (zoom vào ngày crash) |
| **Q5** – Dự đoán trạng thái | Tín hiệu Trạng thái | Tất cả panel khác (xác minh tín hiệu) |
| **Q6** – Volume Profile | Hồ sơ Khối lượng | Biểu đồ Nến (xác nhận S/R) |
| **Q7** – Whale vs Retail | Tỷ lệ Long/Short | OI Timeline, Thanh lý Timeline |
| **Q8** – Taker pressure | Tỷ lệ Taker Mua/Bán | Biểu đồ Nến (kiểm tra hướng giá) |
