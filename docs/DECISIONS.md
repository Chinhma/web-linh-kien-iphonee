# Nhật ký quyết định kỹ thuật

| # | Vấn đề | Lựa chọn | Lý do |
|---|---|---|---|
| 1 | Schema cũ khác hoàn toàn đặc tả | Reset DB (đã sao lưu `db.backup-20261119.sqlite3`), code cũ chuyển vào `_archive/` | Đã được chủ dự án đồng ý; DB cũ chỉ có dữ liệu demo |
| 2 | Cấu trúc app | Các app đặt ngang hàng ở gốc (`core`, `accounts`, `products`, `cart`, `orders`, `payments`, `inventory`, `reviews`, `promotions`, `chatbot`, `dashboard`) | Giữ cách bố trí sẵn có của dự án (không có thư mục `apps/`) |
| 3 | App `compatibility` | Model `Compatibility` đặt trong `products` | Đặc tả cho phép; giảm phụ thuộc vòng |
| 4 | Wishlist | Đặt trong app `cart` | Cùng nghiệp vụ mua sắm, ít code |
| 5 | Kiểu dữ liệu tiền | `PositiveIntegerField` (VND) | Không dùng float; VND không có phần lẻ |
| 6 | Badge giỏ hàng | Đếm **số dòng sản phẩm** | Ổn định khi đổi số lượng, giống đa số sàn TMĐT |
| 7 | Chính sách tồn kho | Trừ kho ngay khi tạo đơn, hoàn kho khi hủy/quá hạn thanh toán | Giữ hàng cho khách, chống bán vượt tồn |
| 8 | Chống bán vượt tồn kho | `UPDATE ... WHERE stock_quantity >= n` + `select_for_update` | SQLite không khóa dòng; cập nhật có điều kiện đảm bảo đúng |
| 9 | Doanh thu danh mục/sản phẩm | Tính theo `OrderItem.line_total` = **doanh thu trước giảm giá coupon** | Đơn giản, minh bạch; ghi rõ trong README và giao diện |
| 10 | Đơn online quá hạn | Hàm `expire_unpaid_orders()` gọi khi mở trang đơn (khách/Admin) + management command | Demo không cần cron |
| 11 | localhost không nhận được IPN | Return URL (đã xác minh chữ ký) cập nhật qua cùng hàm idempotent `apply_gateway_result` | Theo 14.3 của đặc tả |
| 12 | Gemini model mặc định | `gemini-2.5-flash` (đổi qua `GEMINI_MODEL`) | Model flash phổ biến trong thư viện `google-genai` 3.6 |
| 13 | Gọi Gemini | Function calling thủ công (tắt automatic function calling), tối đa 4 vòng | Kiểm soát tham số tool, ghi log tool_calls cho Admin |
| 14 | Tên máy mơ hồ ("iPhone 13") | `resolve_iphone_model` trả `ambiguous=True` + danh sách phiên bản; chế độ dự phòng trả kết quả bản tiêu chuẩn kèm câu hỏi lại | Vừa hỏi lại phiên bản (kịch bản 3) vừa trả lời được "ip 11 thay pin" (kịch bản 2) |
| 15 | Logo website | Theo yêu cầu của chủ dự án (19/11/2026): dùng hình quả táo xanh do chủ dự án cung cấp làm biểu tượng (`static/images/brand/logo-mark.png`, nhúng vào các file SVG). Bộ logo iParts tự thiết kế trước đó lưu ở `_archive/static/brand-iparts-cu/` | Lựa chọn của chủ dự án. Lưu ý: khác với mục 5.1 của SPEC (cấm logo Apple) – có thể bị hỏi khi bảo vệ; khôi phục bằng cách chép lại thư mục trong `_archive` |
| 16 | Chart.js, Lucide | File local ở `static/vendor/` (cài qua npm) | Không phụ thuộc CDN, không cần SRI |
| 17 | Rate limit | Django cache (LocMem) | Đủ cho localhost; production nên dùng Redis |
| 18 | Ảnh seed | Sinh bằng Pillow (gradient + hình khối + chữ), lưu `media/products/YYYY/MM/` | Không dùng ảnh có bản quyền |
| 19 | Đơn mẫu đã thanh toán online | Payment mẫu có `raw_response = {"sample_data": true}` | Đặc tả yêu cầu đủ phương thức; đánh dấu rõ không phải giao dịch thật |
| 20 | Admin dùng để chuyển trạng thái đơn mẫu | Tài khoản `seed_admin` ở trạng thái khóa, mật khẩu không dùng được | Lịch sử trạng thái có người thực hiện hợp lệ, không đăng nhập được |
| 21 | Console Windows lỗi tiếng Việt | `manage.py` cấu hình stdout UTF-8 | Tránh `UnicodeEncodeError` khi chạy lệnh |
| 22 | Cảnh báo `check --deploy` (HSTS, SSL redirect, cookie secure) | Chấp nhận trên localhost, có thể bật qua `.env` | Các thiết lập này chỉ đúng khi chạy HTTPS |
| 23 | Thư viện thêm | Không thêm thư viện ngoài danh sách cho phép | — |
| 24 | Địa chỉ hành chính | 2 cấp Tỉnh/Thành phố → Phường/Xã (sau sáp nhập, hiệu lực 01/07/2025, QĐ 19/2025/QĐ-TTg); bỏ Quận/Huyện. Dữ liệu: `static/data/vn-address-2025.json` (34 tỉnh, 3.321 phường/xã – đã kiểm tra đủ số lượng và không trùng mã) | **Nguồn:** API công khai provinces.open-api.vn, phiên bản v2 (`/api/v2/?depth=2`, danh mục sau sáp nhập, mã theo danh mục hành chính), tải một lần ngày 19/11/2026 rồi lưu file tĩnh; website không gọi API khi chạy. Cập nhật lại bằng cách tải lại và chạy test `core.tests.test_address` |
| 25 | Địa chỉ cũ trong DB (có Quận/Huyện) | Migration gộp Quận/Huyện vào `street_address`, tên tỉnh/xã cũ giữ trong `*_name`, mã để trống | Không mất dữ liệu; đơn cũ là snapshot nên giữ nguyên chữ |
| 26 | Session khách vãng lai cho chatbot | Đánh dấu `session.modified` khi tạo session | Đảm bảo trình duyệt nhận cookie: giữ lịch sử chat và giới hạn tần suất đúng |



## Admin Panel theo SPEC_ADMIN_PANEL (19/11/2026)
- Trang quản trị chính: `/quan-tri/`. Django admin chuyển sang `/django-admin/` và **chỉ Superuser** vào được; `/admin/` và `/dashboard/` chuyển hướng về `/quan-tri/`.
- Menu sidebar khai báo một nơi duy nhất: `dashboard/menu.py` (nhóm, mục con, badge, mục chỉ Superuser, alias cho trang chi tiết).
- `templates/base_admin.html` giữ ở thư mục gốc `templates/` (không chuyển vào `dashboard/`) để không phải sửa mọi template kế thừa.
- Ghi chú nội bộ của đơn lưu trong `Order.admin_notes` (JSON list `{text, by, at}`) thay vì bảng riêng – đơn giản, chỉ Admin thấy.
- Bật/tắt phương thức thanh toán: `StoreSetting.enable_cod/enable_vnpay/enable_momo`; phương thức chỉ dùng được khi **đã cấu hình `.env` VÀ đang bật**; phải còn ít nhất 1 phương thức.
- Sắp xếp kéo thả banner/FAQ: API `POST /quan-tri/api/sap-xep/<banner|faq>/` ghi `display_order`.
- Mật khẩu tạm của tài khoản Admin mới: để trống → sinh ngẫu nhiên, lưu tạm trong session và xóa ngay khi hiển thị (chỉ thấy 1 lần).
- `pyflakes` được dùng làm công cụ kiểm tra tĩnh khi phát triển (không phải dependency chạy web).
