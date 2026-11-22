# Tiến độ dự án iParts Store

Cập nhật: 19/11/2026

## Hiện trạng ban đầu (khảo sát Giai đoạn 1)
- Django 6.0.4, allauth 65.16, Python 3.13; đã có custom user `accounts.User`.
- 5 app (`accounts`, `catalog`, `commerce`, `chatbot`, `dashboard`) ở dạng khung: phần lớn template 1 dòng, chưa có tầng service, máy trạng thái đơn, function calling, Admin Panel.
- DB chỉ có dữ liệu demo (34 sản phẩm, 2 user, 0 đơn). `python manage.py check` không lỗi.
- Đã sao lưu DB cũ (`db.backup-20261119.sqlite3`), code cũ chuyển vào `_archive/`.

## Đã hoàn thành
| Giai đoạn | Nội dung | Ngày |
|---|---|---|
| 1 | Khảo sát, SPEC, kế hoạch | 19/11/2026 |
| 2 | Settings đọc `.env`, Tailwind build, design system, logo SVG, base/header/footer, trang lỗi, toàn bộ model + migration, ERD | 19/11/2026 |
| 3 | Đăng ký/đăng nhập (email hoặc username, ghi nhớ, khóa 5 lần sai), đăng xuất POST, quên/đổi/đặt mật khẩu, Google OAuth (adapter không cấp quyền Admin), module phân quyền, Login Required Modal | 19/11/2026 |
| 4 | `seed_data` (46 sản phẩm, 27 dòng iPhone, 120 đơn, 85 đánh giá, 20 hội thoại), `create_demo_accounts` | 19/11/2026 |
| 5 | Trang chủ 13 khối, danh sách/lọc/sắp xếp, danh mục, chi tiết + kiểm tra máy, tra cứu tương thích 5 trạng thái, trang nội dung, FAQ, liên hệ | 19/11/2026 |
| 6 | Giỏ AJAX, coupon, wishlist, checkout, tạo đơn trong transaction, kết quả, khu vực tài khoản, hủy đơn, mua lại, đánh giá | 19/11/2026 |
| 7 | Admin Panel `/quan-tri/`: dashboard 5 biểu đồ, sản phẩm, danh mục, thương hiệu, dòng iPhone, tương thích (danh sách + ma trận), kho, đơn hàng, thanh toán, khách hàng, đánh giá, khuyến mãi, chatbot, báo cáo + CSV, nội dung, tài khoản Admin, cài đặt | 19/11/2026 |
| 8 | iParts AI Assistant: function calling Gemini, 9 tools, chế độ dự phòng, rate limit, lịch sử | 19/11/2026 |
| 9 | Gateway COD/VNPay/MoMo, xác minh chữ ký, idempotent, kiểm tra số tiền | 19/11/2026 |
| 10 | 50 test tự động – tất cả đạt | 19/11/2026 |
| 11 | Địa chỉ 2 cấp (34 tỉnh/thành, 3.321 phường/xã) – `static/data/vn-address-2025.json` + `address-picker.js` | 19/11/2026 |
| 12 | **SPEC_ADMIN_PANEL** bước 1–11: phân quyền Admin trên web khách (thanh công cụ Admin, ẩn giỏ/wishlist, công cụ quản trị ở trang sản phẩm); khung sidebar accordion + topbar (breadcrumb, tìm nhanh `/`, chuông, avatar); C1 dashboard; C2–C4 sản phẩm (SKU tự sinh, nhân bản sang dòng máy khác, thông số theo danh mục), cây danh mục, dòng iPhone; C5 tương thích (thêm, ma trận, độ phủ); C6 kho (nhập nhiều dòng, kiểm kê, lịch sử); C7 đơn (chọn nhiều, xác nhận hàng loạt, CSV, thanh tiến trình, ghi chú nội bộ); C8 thanh toán (thẻ tổng, chờ hoàn tiền); C9 khách hàng (thẻ số liệu, tab chi tiết); C10 đánh giá dạng thẻ + duyệt hàng loạt; C11 mã giảm giá (thanh tiến trình lượt dùng, công tắc, mã ngẫu nhiên, xem trước số tiền giảm), giảm giá hàng loạt; C12 cấu hình chatbot (sửa câu gợi ý kéo thả), thống kê, câu hỏi chưa trả lời, chi tiết kỹ thuật; C13 báo cáo (so sánh kỳ trước, In, CSV); C14 banner dạng thẻ kéo thả, FAQ kéo thả, soạn trang có thanh công cụ + xem trước, liên hệ Mới/Đã xử lý; C15 cài đặt chia tab + bật/tắt từng phương thức thanh toán; C16 tài khoản Admin (mật khẩu tạm ngẫu nhiên hiển thị 1 lần, không tự khóa/thu hồi); C17 hồ sơ | 19/11/2026 |
| 13 | 73 test tự động – tất cả đạt | 19/11/2026 |

## Đang chờ cấu hình (đã code xong)
- **Gemini API**: điền `GEMINI_API_KEY` – hiện chatbot chạy chế độ cơ bản.
- **Google OAuth**: `.env` đã có Client ID/Secret; cần khai báo redirect URI `http://127.0.0.1:8000/accounts/google/login/callback/` trong Google Cloud Console (URL mới khác URL cũ).
- **VNPay / MoMo Sandbox**: chưa có credentials → phương thức hiển thị "Đang bảo trì".
- **SMTP Gmail**: chưa cấu hình → email in ra console.

## Việc còn lại / lỗi đã biết
- Kiểm thử thủ công trên trình duyệt (responsive 375/768/1280/1440, Console JS) cần thực hiện và ghi vào `TEST_REPORT.md`.
- Nhật ký thao tác Admin (`AdminActivityLog`) – mục [NÊN CÓ], chưa làm.
