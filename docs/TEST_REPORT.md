# Báo cáo kiểm thử – iParts Store

Ngày: 19/11/2026 · Môi trường: Windows 11, Python 3.13.8, Django 6.0.4, SQLite

## 1. Test tự động (`python manage.py test`)
Kết quả: **50 test – tất cả đạt (OK)**.

| Nhóm | Ca kiểm thử | Kết quả |
|---|---|---|
| Phân quyền | Guest gọi `/api/cart/add/` → 401; Guest vào `/thanh-toan/` → chuyển đăng nhập kèm `next`; Customer vào `/quan-tri/` → 403; Guest vào `/quan-tri/` → trang đăng nhập Admin; Customer xem đơn người khác → 404; sửa hồ sơ kèm `is_staff=on` không đổi quyền; user Google không phải staff; `next` ra domain ngoài bị bỏ qua; Admin không mua hàng được | Đạt |
| Xác thực | Đăng ký trùng email (khác hoa thường) bị chặn; đăng ký tự đăng nhập; đăng nhập bằng email và username; khóa tạm sau 5 lần sai; đăng xuất bằng GET không có tác dụng | Đạt |
| Giá & giỏ | `effective_price` trong/ngoài thời gian KM; thêm vượt tồn kho bị giới hạn; sản phẩm ngừng bán không thêm được | Đạt |
| Coupon | Đủ điều kiện ở 9.4 (không tồn tại, tắt, chưa bắt đầu, hết hạn, hết lượt, đã dùng, đơn tối thiểu); giảm % có trần; không giảm quá tạm tính | Đạt |
| Đặt hàng | Trừ kho + ghi InventoryTransaction; giá client bị bỏ qua; thiếu kho rollback toàn bộ; cùng idempotency_key không tạo đơn thứ hai; 2 đơn tranh sản phẩm cuối chỉ 1 thành công | Đạt |
| Trạng thái đơn | Luồng hợp lệ; chuyển không hợp lệ bị từ chối; hủy hoàn kho + hoàn coupon; giao COD tự `paid`; Customer không hủy được đơn đang giao; Admin hủy đơn đang giao phải có lý do | Đạt |
| Doanh thu | Đơn hủy, COD chưa giao, COD đã giao, online paid chưa giao; đơn qua nửa đêm (múi giờ VN) | Đạt |
| Tương thích | Chỉ trả `verified`; sản phẩm không active bị loại; `resolve_iphone_model` với nhiều cách viết; tên mơ hồ; model không tồn tại | Đạt |
| Chatbot | Tools trả dữ liệu DB, không chứa `cost_price`; chế độ dự phòng khi không có key; Gemini lỗi → dự phòng (mock, không gọi mạng); rate limit 429; history không trả hội thoại người khác; tin nhắn rỗng/quá dài → 400 | Đạt |
| Thanh toán | Ký/xác minh VNPay, MoMo; callback sai chữ ký bị từ chối (97); callback trùng không xử lý 2 lần (02); sai số tiền bị từ chối (04) | Đạt |
| Đánh giá | Chưa giao không đánh giá được; mỗi OrderItem một đánh giá; duyệt cập nhật điểm TB | Đạt |

## 2. Kiểm thử luồng bằng Django test client (đã chạy)
| Vai trò | Kịch bản | Kết quả | Ghi chú |
|---|---|---|---|
| Guest | 23 trang công khai/API (trang chủ, danh sách có tham số sai `price_min=abc`, chi tiết, tra cứu, chính sách, FAQ, liên hệ, đăng nhập/đăng ký…) | Đạt | Trang mua hàng chuyển đăng nhập kèm `next` |
| Customer | Đăng nhập → thêm giỏ → áp `WELCOME10` → checkout COD → xem đơn → hủy đơn | Đạt | Kho 37→33→37 khớp |
| Customer | Gửi lại form đặt hàng cùng idempotency_key | Đạt | Không tạo đơn thứ hai |
| Chatbot | 9 kịch bản mục 12.8 ở chế độ dự phòng | Đạt | Trả Product Card từ DB; từ chối prompt injection |
| Admin | 52 trang/API `/quan-tri/` | Đạt | Tất cả HTTP 200 |
| Admin | Xử lý đơn COD pending → delivered; chuyển ngược bị chặn | Đạt | Tự `paid` khi giao |
| Admin | Tạo sản phẩm (tồn đầu 20, thông số, tương thích) → nhập kho 10 → kiểm kê 28 → xóa | Đạt | Lịch sử kho đúng |
| Hệ thống | `DEBUG=False`: trang 404 / 403 tùy biến | Đạt | |

## 3. Kiểm thử thủ công trên trình duyệt (cần thực hiện)
| Hạng mục | Kết quả | Ghi chú |
|---|---|---|
| Responsive 375 / 768 / 1280 / 1440 px | Chưa kiểm | |
| Console JS không lỗi trên các trang chính | Chưa kiểm | |
| Google Login (sau khi khai báo redirect URI) | Chưa kiểm | |
| Gemini thật (sau khi có API key) – 9 kịch bản | Chưa kiểm | |
| VNPay / MoMo sandbox | Chưa kiểm | Chờ credentials |
