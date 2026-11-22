# Giải thích các phần quan trọng (dùng khi bảo vệ đồ án)

## 1. Phân quyền Guest / Customer / Admin
- Phân quyền **kiểm tra ở backend** bằng module `core/permissions.py`. Ẩn nút trên giao diện chỉ là lớp phụ.
  - `customer_required`: Guest → chuyển tới `/dang-nhap/?next=...` (trang thường) hoặc trả JSON `401 LOGIN_REQUIRED` (API). Admin → từ chối mua hàng.
  - `staff_required`: Guest → trang đăng nhập Admin; Customer → trang 403.
  - `superuser_required`: chỉ Superuser quản lý tài khoản Admin.
  - `get_object_owned_or_404`: dữ liệu không thuộc người dùng trả **404** (không lộ việc đối tượng tồn tại → chống IDOR).
- Tham số `next` chỉ được chấp nhận nếu cùng host (`url_has_allowed_host_and_scheme`) → chống open redirect.
- Đăng nhập Google **không bao giờ** cấp `is_staff`/`is_superuser` (đặt cứng trong `accounts/adapters.py`).

## 2. Tạo đơn hàng trong transaction (`orders/services.py::create_order`)
1. Cùng `idempotency_key` → trả lại đơn cũ (chống bấm "Đặt hàng" 2 lần).
2. Trong `transaction.atomic()`: khóa sản phẩm (`select_for_update`), kiểm tra còn bán và đủ tồn kho.
3. Tính lại **toàn bộ giá ở backend**: giá hiệu lực, coupon, phí ship. Giá gửi từ trình duyệt bị bỏ qua.
4. Trừ kho bằng `UPDATE ... SET stock = stock - n WHERE stock >= n`. Nếu 0 dòng được cập nhật → ném lỗi → **rollback toàn bộ**. Nhờ vậy hai khách tranh nhau sản phẩm cuối cùng thì chỉ một người thành công (có test `LastItemRaceTests`).
5. Ghi `InventoryTransaction`, tạo `OrderItem` (snapshot tên/giá/SKU), lịch sử trạng thái, `CouponUsage`, xóa dòng giỏ.

## 3. Máy trạng thái đơn hàng
- Một hàm duy nhất `change_order_status(order, new_status, actor, note)` kiểm tra bảng `TRANSITIONS` (ai được chuyển từ trạng thái nào sang trạng thái nào).
- Hủy đơn → hoàn kho, hoàn lượt coupon; nếu đã thanh toán → `refund_pending`.
- Giao thành công → COD tự chuyển `paid`, tăng `sold_count`.
- Giao diện Admin chỉ hiện những nút chuyển trạng thái hợp lệ (`available_transitions`).

## 4. Function calling của iParts AI Assistant
- Backend khai báo 9 công cụ (`chatbot/services/tools.py`) cho Gemini: `search_products`, `check_compatibility`, `get_promotions`...
- Quy trình: Gemini đọc câu hỏi → **yêu cầu gọi hàm** kèm tham số → backend **truy vấn DB thật** → trả kết quả cho Gemini → Gemini viết câu trả lời dựa trên kết quả.
- Thẻ sản phẩm trong chat được **backend dựng từ ID sản phẩm trong kết quả tool**, không lấy từ chữ AI viết → AI không thể bịa giá/tồn kho trên thẻ.
- Tool không bao giờ trả `cost_price`; `get_my_order_status` chỉ trả đơn của chính người đang chat.
- Không có API key hoặc Gemini lỗi → **chế độ dự phòng** (`fallback.py`): nhận diện từ khóa rồi gọi trực tiếp các tool trên.
- AI không tự đặt hàng: chỉ trả action "Thêm vào giỏ", khách tự bấm (Guest nhận nút "Đăng nhập").

## 5. Quy tắc tính doanh thu (`dashboard/services/revenue.py`)
> Doanh thu ghi nhận = tổng `Order.total` của các đơn `delivered` **và** `paid`, tính theo ngày `delivered_at` (giờ Việt Nam).
- Không tính đơn hủy, đơn đang xử lý; đơn online đã thanh toán nhưng chưa giao hiển thị riêng ở "Doanh thu chờ ghi nhận".
- Truy vấn bằng `aggregate`/`TruncDate` với múi giờ `Asia/Ho_Chi_Minh` (có test đơn qua nửa đêm).

## 6. Xác minh chữ ký thanh toán (`payments/`)
- VNPay: sắp xếp tham số, URL-encode, ký **HMAC-SHA512**; MoMo: chuỗi tham số theo thứ tự quy định, ký **HMAC-SHA256**.
- `apply_gateway_result` chỉ xử lý kết quả **đã xác minh chữ ký**, kiểm tra **số tiền khớp**, khóa `Payment` bằng `select_for_update` và **idempotent** (callback trùng trả "đã xác nhận" và không xử lý lại).
- Chỉ IPN được `csrf_exempt`, vì đã có chữ ký bảo vệ.

## 7. Tồn kho luôn nhất quán
- `inventory/services.py::adjust_stock` là cách **duy nhất** thay đổi `stock_quantity`. Mỗi lần thay đổi đều ghi `InventoryTransaction` (tồn trước, tồn sau).
- Form sửa sản phẩm không cho sửa tồn kho; Admin dùng "Nhập kho" hoặc "Điều chỉnh kiểm kê".
- Sau khi seed, tổng `quantity_change` của mỗi sản phẩm luôn bằng `stock_quantity`.
