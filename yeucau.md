Dưới đây là danh sách các **field được trích xuất từ JSON sản phẩm** và mô tả ý nghĩa của chúng.

---

# 1. Thông tin định danh sản phẩm

| Field | Kiểu dữ liệu | Mô tả |
|---|---|---|
| `id` | integer | ID duy nhất của sản phẩm trong hệ thống |
| `sku` | string | SKU của sản phẩm (Stock Keeping Unit) |
| `name` | string | Tên sản phẩm |
| `url_key` | string | Slug URL của sản phẩm |
| `url_path` | string | Đường dẫn URL đầy đủ tới trang sản phẩm |
| `productset_id` | integer | ID của bộ sản phẩm (product set) |
| `master_product_sku` | string | SKU chính của sản phẩm trong hệ thống |
| `seller_product_id` | integer | ID sản phẩm tương ứng với seller |
| `seller_product_sku` | string | SKU sản phẩm do seller quản lý |

---

# 2. Thông tin người bán

| Field | Kiểu dữ liệu | Mô tả |
|---|---|---|
| `seller_id` | integer | ID của người bán |
| `seller_name` | string | Tên cửa hàng bán sản phẩm |
| `is_from_official_store` | boolean | Sản phẩm có thuộc official store hay không |
| `tiki_verified` | integer | Seller đã được Tiki xác minh |
| `is_authentic` | integer | Sản phẩm được xác nhận chính hãng |
| `tiki_hero` | integer | Flag cho các sản phẩm nổi bật của Tiki |

---

# 3. Thông tin giá

| Field | Kiểu dữ liệu | Mô tả |
|---|---|---|
| `price` | integer | Giá bán hiện tại |
| `original_price` | integer | Giá gốc trước khi giảm |
| `discount` | integer | Số tiền giảm giá |
| `discount_rate` | integer | Tỷ lệ giảm giá (%) |
| `is_high_price_penalty` | boolean | Flag nếu giá bị đánh giá là cao |

---

# 4. Thông tin đánh giá

| Field | Kiểu dữ liệu | Mô tả |
|---|---|---|
| `rating_average` | float | Điểm rating trung bình |
| `review_count` | integer | Số lượng đánh giá |
| `quantity_sold.text` | string | Chuỗi hiển thị số lượng đã bán |
| `quantity_sold.value` | integer | Số lượng đã bán |

---

# 5. Thông tin phân loại

| Field | Kiểu dữ liệu | Mô tả |
|---|---|---|
| `category_ids` | array\<int\> | Danh sách ID các category của sản phẩm |
| `primary_category_path` | string | Đường dẫn category chính |
| `primary_category_name` | string | Tên category chính |

---

# 6. Thông tin hình ảnh

| Field | Kiểu dữ liệu | Mô tả |
|---|---|---|
| `thumbnail_url` | string | URL ảnh thumbnail của sản phẩm |
| `thumbnail_width` | integer | Chiều rộng ảnh thumbnail |
| `thumbnail_height` | integer | Chiều cao ảnh thumbnail |

---

# 7. Thông tin giao hàng

| Field | Kiểu dữ liệu | Mô tả |
|---|---|---|
| `shippable` | boolean | Có thể vận chuyển hay không |
| `fastest_delivery_time` | datetime | Thời gian giao hàng sớm nhất |
| `order_route` | string | Tuyến giao hàng (ví dụ: hn_hcm) |
| `is_tikinow_delivery` | boolean | Có giao TikiNOW |
| `is_nextday_delivery` | boolean | Có giao ngày hôm sau |
| `freeship_campaign` | string | Chương trình freeship áp dụng |

---

# 8. Badges (nhãn hiển thị trên sản phẩm)

## `badges_new`

| Field | Mô tả |
|---|---|
| `placement` | Vị trí hiển thị badge |
| `type` | Loại badge |
| `code` | Mã badge |
| `icon` | URL icon |
| `icon_width` | Chiều rộng icon |
| `icon_height` | Chiều cao icon |
| `text` | Nội dung badge |
| `text_color` | Màu chữ badge |

---

## `badges_v3`

| Field | Mô tả |
|---|---|
| `placement` | Vị trí hiển thị |
| `type` | Loại badge |
| `code` | Mã badge |
| `image` | URL hình badge |

---

# 9. Metadata về impression (tracking search)

## `impression_info`

| Field | Mô tả |
|---|---|
| `impression_id` | ID của lần hiển thị sản phẩm |
| `metadata.request_id` | ID request tìm kiếm |
| `metadata.params` | Tham số query tìm kiếm |
| `metadata.delivery_zone` | Mã khu vực giao hàng |
| `metadata.query` | Từ khóa tìm kiếm |
| `metadata.category` | Category được tìm |
| `metadata.position` | Vị trí sản phẩm trong danh sách |
| `metadata.is_ad` | Có phải quảng cáo |
| `metadata.price` | Giá tại thời điểm hiển thị |
| `metadata.rating` | Rating tại thời điểm hiển thị |

---

# 10. Visible Impression Info (analytics)

## `visible_impression_info.amplitude`

| Field | Mô tả |
|---|---|
| `seller_type` | Loại seller |
| `category_l1_name` | Category cấp 1 |
| `category_l2_name` | Category cấp 2 |
| `category_l3_name` | Category cấp 3 |
| `price` | Giá sản phẩm |
| `product_rating` | Rating sản phẩm |
| `search_rank` | Thứ hạng tìm kiếm |
| `number_of_reviews` | Số review |
| `layout` | Kiểu layout hiển thị |
| `variant` | Có variant sản phẩm |
| `is_best_offer_available` | Có deal tốt nhất |
| `is_flash_deal` | Có flash sale |
| `is_freeship_xtra` | Có freeship xtra |

---

# 11. Các flag hiển thị UI

| Field | Mô tả |
|---|---|
| `layout_type` | Kiểu layout (grid/list) |
| `is_top_brand` | Có phải thương hiệu top |
| `isGiftAvailable` | Có hỗ trợ gift |

---