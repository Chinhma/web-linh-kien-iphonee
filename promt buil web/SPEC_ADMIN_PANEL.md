# PROMPT — PHÂN QUYỀN ADMIN VÀ XÂY DỰNG ADMIN PANEL iParts Store

> Đọc kèm `docs/SPEC.md` (Phần 6 và Phần 13), `docs/SPEC_BO_SUNG_DANH_MUC.md` (nếu có) và `docs/PROGRESS.md`.
> Khi mâu thuẫn, tài liệu này được ưu tiên cho phần phân quyền Admin và Admin Panel.
> Kiểm tra code hiện có trước. Phần nào đã làm đúng thì giữ, chỉ sửa hoặc bổ sung. Không xóa dữ liệu khi chưa báo tôi.

---

## PHẦN A. PHÂN QUYỀN ADMIN TRÊN WEBSITE KHÁCH HÀNG

### A1. Nguyên tắc

Admin (tài khoản `is_staff = True`) khi vào website khách hàng được **xem mọi thứ như Customer**, nhưng **không mua hàng**.

| Chức năng trên website khách                                   | Customer |                 Admin                  |
| -------------------------------------------------------------- | :------: | :------------------------------------: |
| Xem trang chủ, danh mục, sản phẩm, chi tiết, đánh giá          |    ✔     |                   ✔                    |
| Tìm kiếm, lọc, sắp xếp, tra cứu tương thích, mua theo dòng máy |    ✔     |                   ✔                    |
| Chat với iParts AI Assistant                                   |    ✔     |                   ✔                    |
| Giỏ hàng, Thêm vào giỏ, Mua ngay                               |    ✔     |                   ✖                    |
| Checkout, Đặt hàng                                             |    ✔     |                   ✖                    |
| Yêu thích (Wishlist)                                           |    ✔     |                   ✖                    |
| Viết đánh giá                                                  |    ✔     |                   ✖                    |
| Khu vực "Tài khoản của tôi" của khách (đơn hàng, địa chỉ)      |    ✔     | ✖ (Admin dùng hồ sơ trong Admin Panel) |
| Vào Admin Panel                                                | ✖ (403)  |                   ✔                    |

### A2. Giao diện website khi Admin đăng nhập

- **Header**: ẩn icon Giỏ hàng và icon Yêu thích. Ở vị trí tài khoản hiển thị avatar (hoặc chữ cái đầu) + tên + **badge nhỏ "Admin"**. Bấm vào sổ dropdown:
  - Dòng đầu: email admin (chữ nhỏ, màu muted).
  - **Vào trang quản trị** (icon `layout-dashboard`) → `/quan-tri/`.
  - **Hồ sơ quản trị** → trang hồ sơ trong Admin Panel.
  - **Đăng xuất** (form POST, màu đỏ).
- **Thanh công cụ Admin** (mỏng, cao 36px, nền `#0F172A`, chữ trắng, nằm trên cùng, trên announcement bar): "Bạn đang xem cửa hàng với quyền Quản trị viên — các chức năng mua hàng đã bị tắt" + link "Vào trang quản trị". Có nút thu gọn (nhớ trong `localStorage`).
- **Product Card**: ẩn nút Thêm vào giỏ và nút trái tim.
- **Trang chi tiết sản phẩm**: thay khối Thêm vào giỏ / Mua ngay / Yêu thích bằng **khối "Công cụ quản trị"**, gồm: tồn kho hiện tại (số chính xác), giá nhập, trạng thái sản phẩm, nút **Sửa sản phẩm** (mở trang sửa trong Admin Panel), nút **Nhập kho**, nút **Quản lý tương thích**. Sản phẩm ở trạng thái Nháp/Ngừng kinh doanh Admin vẫn xem được, có thanh cảnh báo màu vàng.
- **Trang tra cứu tương thích, Mua theo dòng máy**: ẩn nút Thêm vào giỏ, thay bằng link "Sửa".
- **Chatbot**: Admin chat bình thường; phản hồi **không** trả action `add_to_cart` (Product Card trong chat chỉ có nút "Xem" và "Sửa").
- Admin bấm vào link `/gio-hang/`, `/thanh-toan/`, `/yeu-thich/`, `/tai-khoan/...` (gõ tay) → chuyển về trang chủ kèm toast "Tài khoản quản trị không sử dụng chức năng này".

### A3. Chặn ở backend — [BẮT BUỘC]

- Mọi view và API mua hàng (`/api/cart/*`, `/api/wishlist/*`, checkout, tạo đơn, đánh giá, khu vực tài khoản khách) dùng decorator/mixin `customer_required`: Admin gọi tới thì trang thường chuyển hướng như trên, AJAX trả `403 {"ok": false, "code": "ADMIN_CANNOT_PURCHASE", "message": "Tài khoản quản trị không dùng để mua hàng"}`.
- Ẩn nút trên giao diện chỉ là phụ. Gọi thẳng URL/API vẫn phải bị chặn.
- Template dùng biến dùng chung từ context processor: `is_admin_user`, `is_customer_user` (không viết `user.is_staff` rải rác khắp template).

### A4. Vai trò và quyền

| Vai trò     | Cách xác định                 | Quyền                                            |
| ----------- | ----------------------------- | ------------------------------------------------ |
| Guest       | Chưa đăng nhập                | Xem                                              |
| Customer    | Đăng nhập, `is_staff = False` | Xem + mua hàng                                   |
| Admin       | `is_staff = True`             | Toàn bộ Admin Panel, trừ quản lý tài khoản Admin |
| Super Admin | `is_superuser = True`         | Toàn bộ, kể cả tạo/cấp/thu hồi quyền Admin       |

- Không có form nào cho người dùng tự đăng ký thành Admin. Đăng ký thường và đăng nhập Google luôn tạo Customer (`is_staff = False`, `is_superuser = False`, đặt cứng trong adapter allauth).
- Form sửa hồ sơ của Customer chỉ liệt kê rõ các trường được sửa (`fields = [...]`), không bao giờ chứa `is_staff`, `is_superuser`, `groups`, `user_permissions`.
- Tài khoản Admin chỉ được tạo bằng: lệnh `createsuperuser` / `create_demo_accounts`, hoặc Super Admin tạo trong Admin Panel.
- [NÊN CÓ] Django Groups cho nhân viên: **Quản lý** (toàn bộ trừ tài khoản Admin), **Nhân viên bán hàng** (Đơn hàng, Thanh toán xem, Khách hàng xem, Đánh giá), **Nhân viên kho** (Sản phẩm xem, Tồn kho). Sidebar chỉ hiện mục người đó có quyền; vào URL không có quyền → trang 403 trong Admin Panel. Nếu chưa làm Groups thì mọi `is_staff` có toàn quyền trừ mục Tài khoản Admin.

### A5. Test phân quyền — [BẮT BUỘC]

- Admin gọi `/api/cart/add/` → 403 `ADMIN_CANNOT_PURCHASE`; mở `/thanh-toan/` → chuyển về trang chủ; mở `/yeu-thich/` → chuyển về trang chủ.
- Admin xem được trang chi tiết sản phẩm Nháp; Customer xem sản phẩm Nháp → 404.
- Customer mở `/quan-tri/` → 403; Guest mở `/quan-tri/` → trang đăng nhập Admin.
- Customer gửi form hồ sơ kèm `is_staff=on` → quyền không đổi.
- User mới tạo qua Google → `is_staff = False`.
- Admin thường (không phải superuser) mở trang Tài khoản Admin → 403.

---

## PHẦN B. ADMIN PANEL — BỐ CỤC VÀ GIAO DIỆN

### B1. Thông tin chung

- URL gốc: `/quan-tri/`. Tên hiển thị: **iParts Store Admin**. Template riêng `templates/dashboard/base_admin.html`, **không** kế thừa giao diện khách hàng, **không** có widget chatbot.
- Phong cách Modern SaaS Dashboard: nền nội dung `#F8FAFC`, card trắng bo góc 16px, đổ bóng nhẹ, font Be Vietnam Pro, icon Lucide, màu theo Design System của SPEC.
- Django admin mặc định đổi sang `/django-admin/` và chỉ dành cho Superuser (dự phòng kỹ thuật). Giao diện quản lý chính là `/quan-tri/`.

### B2. Bố cục 3 vùng

```
┌──────────────┬────────────────────────────────────────────────────┐
│              │  TOPBAR: ☰ | Breadcrumb  | 🔍 Tìm nhanh | 🔔 | 🏪 | 👤 │
│   SIDEBAR    ├────────────────────────────────────────────────────┤
│  (bên trái,  │                                                    │
│  cố định,    │   NỘI DUNG                                         │
│  rộng 260px) │   Tiêu đề trang + nút hành động chính (bên phải)    │
│              │   Card thống kê / bộ lọc / bảng / form              │
│              │                                                    │
└──────────────┴────────────────────────────────────────────────────┘
```

### B3. Sidebar trái — [BẮT BUỘC]

- Nền `#0F172A`, chữ `#CBD5E1`, mục đang chọn: nền `#1E293B`, chữ trắng, vạch dọc màu primary `#2563EB` bên trái.
- Trên cùng: logo **iParts Store Admin**. Dưới cùng: avatar + tên admin + vai trò.
- Các mục **nhóm theo khối**, mỗi khối có tiêu đề nhỏ in hoa. Mục có mục con hiển thị mũi tên ▸; **bấm vào thì sổ xuống (accordion)** danh sách chức năng con, bấm lần nữa thì thu lại. Mũi tên xoay 90° khi mở, animation 200ms.
- Mục cha của trang đang mở **tự động mở sẵn** khi tải trang. Trạng thái mở/đóng nhớ trong `localStorage`.
- Badge số đỏ/vàng cạnh mục cần chú ý (lấy từ DB, cập nhật khi tải trang).
- Nút thu gọn sidebar thành thanh icon 72px (hover hiện tooltip/menu con nổi). Trạng thái nhớ trong `localStorage`.
- Mobile/tablet (< 1024px): sidebar ẩn, nút ☰ ở topbar mở dạng drawer có lớp phủ.

**Cấu trúc menu:**

```
TỔNG QUAN
  ▣ Dashboard

SẢN PHẨM
  ▸ Sản phẩm
      • Danh sách sản phẩm
      • Thêm sản phẩm mới
      • Sản phẩm sắp hết hàng
  ▸ Danh mục
      • Cây danh mục
      • Thêm danh mục
  ▸ Dòng iPhone
      • Danh sách dòng máy
      • Thêm dòng máy
  ▸ Linh kiện tương thích
      • Danh sách tương thích
      • Thêm tương thích
      • Ma trận tương thích
      • Độ phủ linh kiện
  ▸ Thương hiệu

KHO HÀNG
  ▸ Tồn kho
      • Tổng quan tồn kho
      • Nhập kho
      • Điều chỉnh kiểm kê
      • Lịch sử nhập xuất

BÁN HÀNG
  ▸ Đơn hàng                    [badge: số đơn chờ xác nhận]
      • Tất cả đơn hàng
      • Chờ xác nhận
      • Đang xử lý & đang giao
      • Đã giao
      • Đã hủy
  ▸ Thanh toán
      • Danh sách giao dịch
      • Chờ hoàn tiền           [badge]
  ▸ Khách hàng
      • Danh sách khách hàng
      • Khách hàng bị khóa
  ▸ Đánh giá                    [badge: số chờ duyệt]
      • Chờ duyệt
      • Đã duyệt
      • Đã ẩn
  ▸ Khuyến mãi
      • Mã giảm giá
      • Thêm mã giảm giá
      • Giảm giá sản phẩm hàng loạt

AI SYSTEM
  ▸ iParts AI Assistant
      • Cấu hình chatbot
      • Lịch sử hội thoại
      • Thống kê chatbot
      • Câu hỏi chưa có câu trả lời

BÁO CÁO & THỐNG KÊ
  ▸ Báo cáo
      • Doanh thu
      • Sản phẩm
      • Danh mục
      • Đơn hàng
      • Kho hàng
      • Khách hàng

NỘI DUNG WEBSITE
  ▸ Nội dung
      • Banner trang chủ
      • Trang chính sách
      • Câu hỏi thường gặp
      • Người đăng ký nhận tin
      • Tin nhắn liên hệ

HỆ THỐNG
  ▸ Cài đặt
      • Thông tin cửa hàng
      • Vận chuyển & thanh toán
      • Liên hệ & mạng xã hội
      • Trạng thái tích hợp
  ▸ Tài khoản quản trị          (chỉ Super Admin thấy)
  ▣ Hồ sơ của tôi
```

### B4. Topbar

- Nút ☰ thu/mở sidebar.
- Breadcrumb (ví dụ `Sản phẩm › Danh sách sản phẩm`).
- Ô **tìm nhanh** (phím tắt `/` hoặc `Ctrl+K`): gõ là gợi ý ngay theo nhóm: Đơn hàng (theo mã), Sản phẩm (tên/SKU), Khách hàng (tên/email/SĐT). Enter mở kết quả đầu.
- Chuông 🔔 có số đếm: đơn mới chờ xác nhận, sản phẩm sắp hết/hết hàng, đánh giá chờ duyệt, đơn chờ hoàn tiền. Bấm sổ danh sách, mỗi dòng dẫn tới trang tương ứng.
- Nút 🏪 **Xem cửa hàng** (mở website khách ở tab mới).
- Avatar + dropdown: Hồ sơ của tôi, Đổi mật khẩu, Xem cửa hàng, Đăng xuất (POST).

### B5. Mẫu trang dùng chung — [BẮT BUỘC] áp dụng cho mọi module

**Trang danh sách:**

1. Tiêu đề + mô tả ngắn + nút chính bên phải (ví dụ **+ Thêm sản phẩm**), nút phụ (Xuất CSV).
2. Hàng thẻ số liệu nhỏ (3–4 thẻ) liên quan module.
3. Thanh công cụ: ô tìm kiếm (debounce 400ms), các dropdown lọc, nút "Xóa bộ lọc"; tab trạng thái nếu có. Mọi tham số nằm trên URL.
4. Bảng: header dính, sắp xếp theo cột (bấm tiêu đề), hàng hover, checkbox chọn nhiều + thanh thao tác hàng loạt hiện ra khi có hàng được chọn, cột Hành động cuối dòng (icon Xem / Sửa / Xóa có tooltip, hoặc menu `⋯`).
5. Phân trang: "Hiển thị 1–20 trong 135", chọn 20/50/100 dòng/trang.
6. Empty state (icon + "Chưa có dữ liệu" + nút thêm), skeleton khi đang tải.
7. Mobile: bảng chuyển thành dạng thẻ.

**Trang form (thêm/sửa):**

- Bố cục 2 cột: cột trái (2/3) các khối nội dung chính, cột phải (1/3) các khối phụ (trạng thái, ảnh, tổ chức) dính khi cuộn.
- Mỗi khối là một card có tiêu đề. Ô bắt buộc có dấu `*` đỏ. Lỗi hiện dưới từng ô và một hộp tổng hợp lỗi trên đầu (tiếng Việt).
- Thanh nút cố định cuối trang: **Lưu**, **Lưu & thêm mới**, **Hủy**. Cảnh báo khi rời trang mà chưa lưu thay đổi.
- Sửa xong → toast "Đã lưu thành công" và ở lại trang sửa.

**Trang chi tiết:** header (tên + badge trạng thái + nút hành động), các card thông tin, timeline lịch sử ở cột phải.

**Thao tác xóa/hủy:** luôn mở confirm modal ghi rõ hậu quả (ví dụ "Xóa danh mục 'Pin'? Danh mục còn 12 sản phẩm nên không thể xóa"). Không dùng `alert`/`confirm` của trình duyệt.

**Thông báo:** toast góc trên phải cho mọi kết quả thao tác.

---

## PHẦN C. ĐẶC TẢ TỪNG MODULE

### C1. Dashboard `/quan-tri/` — [BẮT BUỘC]

**Bộ lọc thời gian** góc phải: 7 ngày gần nhất (mặc định), Hôm nay, 30 ngày, Tháng này, Tháng trước, Tùy chọn khoảng ngày.

**Hàng 1 — 4 thẻ KPI** (mỗi thẻ: icon tròn màu, tên, giá trị lớn, % so với kỳ trước có mũi tên xanh/đỏ):

1. Doanh thu (kỳ đã chọn)
2. Số đơn hàng (kỳ đã chọn)
3. Khách hàng mới (kỳ đã chọn)
4. Giá trị đơn trung bình

**Hàng 2 — 4 thẻ cảnh báo nhỏ** (bấm vào sang trang đã lọc sẵn): Đơn chờ xác nhận · Sản phẩm sắp hết hàng · Sản phẩm hết hàng · Đánh giá chờ duyệt.

**Hàng 3 — Biểu đồ (Chart.js):**

| Vị trí     | Biểu đồ                                            | Chi tiết                                                                                                                                                                                        |
| ---------- | -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Trái (2/3) | **Doanh thu 7 ngày** — Line có vùng tô màu primary | Trục X: đủ 7 ngày (`T2 13/11`...), ngày không có doanh thu = 0; trục Y định dạng `1,2tr`; tooltip: `1.250.000₫ · 5 đơn`. Có nút chuyển nhanh 7 ngày / 30 ngày / 12 tháng                        |
| Phải (1/3) | **Sản phẩm theo danh mục** — Doughnut              | Số sản phẩm đang có trong DB theo 10 nhóm danh mục; giữa vòng hiển thị tổng số sản phẩm; chú thích bên dưới có số lượng và %; bấm vào một phần thì sang danh sách sản phẩm lọc theo danh mục đó |

**Hàng 4 — Biểu đồ:**

| Vị trí     | Biểu đồ                                                                       |
| ---------- | ----------------------------------------------------------------------------- |
| Trái (1/2) | **Doanh thu theo danh mục** — Doughnut (kỳ đã chọn), danh mục < 3% gộp "Khác" |
| Phải (1/2) | **Top 5 sản phẩm bán chạy** — Bar ngang, tooltip có số lượng và doanh thu     |

**Hàng 5 — Biểu đồ:** **Đơn hàng theo trạng thái** — Bar dọc 6 trạng thái, màu theo badge.

**Hàng 6 — 2 bảng:** 8 đơn hàng mới nhất (mã, khách, tổng tiền, trạng thái, thời gian, nút Xem) · Sản phẩm sắp hết hàng (ảnh, tên, SKU, tồn/ngưỡng, nút **Nhập kho** mở modal nhập nhanh).

Quy tắc doanh thu dùng đúng SPEC 13.5: chỉ tính đơn `delivered` + `paid`, theo ngày `delivered_at`, giờ Việt Nam. Dữ liệu biểu đồ lấy qua API JSON (`/quan-tri/api/stats/...`, chỉ staff), dùng `aggregate`/`annotate`/`TruncDate`, có skeleton khi tải và empty state khi không có dữ liệu. Không dùng dữ liệu giả cố định.

### C2. Quản lý sản phẩm

**Danh sách** — thẻ: Tổng sản phẩm · Đang bán · Sắp hết · Hết hàng.
Cột: ☐ · Ảnh · Tên + SKU · Danh mục · Chất lượng · Giá bán (giá KM gạch) · Tồn kho (màu theo mức) · Đã bán · Trạng thái · Nổi bật (toggle bật/tắt ngay) · Hành động.
Lọc: danh mục (cây), dòng iPhone, chất lượng, trạng thái, tình trạng kho, đang giảm giá. Tìm: tên, SKU, mã linh kiện.
Thao tác hàng loạt: Đổi trạng thái · Bật/tắt nổi bật · Xuất CSV.
Hành động từng dòng: Xem trên website · Sửa · **Nhân bản sang dòng máy khác** · Nhập kho · Ngừng kinh doanh/Xóa.

**Thêm/Sửa** — cột trái:

1. _Thông tin cơ bản_: Tên `*`, Slug (tự sinh), SKU (để trống tự sinh), Mã linh kiện, Danh mục `*` (dropdown nhóm theo cấp 1, chỉ chọn cấp 2), Thương hiệu, Chất lượng `*`.
2. _Giá_: Giá nhập, Giá bán `*`, Giá khuyến mãi, Thời gian khuyến mãi (từ–đến). Hiển thị ngay "% giảm" và "Lợi nhuận dự kiến".
3. _Mô tả_: Mô tả ngắn, Mô tả chi tiết, Điểm nổi bật (thêm/xóa từng dòng), Hướng dẫn lắp đặt.
4. _Thông số kỹ thuật_: bảng động (Tên – Giá trị), nút "Dùng mẫu thông số theo loại".
5. _Tương thích_: chọn nhiều dòng iPhone (ô tìm + checkbox nhóm theo thế hệ), trạng thái mặc định Đã xác nhận, ghi chú tương thích.

Cột phải:

- _Trạng thái_: Nháp / Đang bán / Ngừng kinh doanh; Nổi bật; Yêu cầu kỹ thuật viên; Độ khó lắp đặt.
- _Hình ảnh_: kéo thả nhiều ảnh, xem trước, chọn ảnh chính (ngôi sao), kéo để sắp xếp, xóa; chỉ JPG/PNG/WEBP ≤ 5 MB; tên file tự đổi thành UUID.
- _Kho_: khi thêm mới nhập tồn đầu kỳ; khi sửa chỉ hiển thị tồn hiện tại + nút Nhập kho / Điều chỉnh (không sửa trực tiếp), ngưỡng cảnh báo, bảo hành (tháng).

**Xóa**: sản phẩm đã có trong đơn hàng → không cho xóa, gợi ý "Ngừng kinh doanh".

**Sản phẩm sắp hết hàng**: danh sách lọc sẵn, có nút nhập kho nhanh từng dòng.

### C3. Quản lý danh mục

- **Cây danh mục**: hiển thị dạng cây 2 cấp (cấp 1 có icon, in đậm, mở/thu được; cấp 2 thụt vào), mỗi dòng: tên, mã, số sản phẩm, thứ tự, trạng thái (toggle), hành động. [NÊN CÓ] Kéo thả để đổi thứ tự.
- **Thêm/Sửa**: Tên `*`, Slug (tự sinh), Mã `*` (cho cấp 1, 3 chữ in hoa), Danh mục cha, Icon (ô chọn có xem trước icon Lucide), Ảnh, Mô tả, Thứ tự, Hoạt động. Có giải thích ngắn dưới mỗi ô (ví dụ "Thứ tự: số nhỏ hiển thị trước").
- Không xóa được danh mục còn sản phẩm hoặc còn danh mục con (thông báo rõ số lượng).

### C4. Quản lý dòng iPhone

- Danh sách dạng thẻ hoặc bảng nhóm theo thế hệ: ảnh, tên, năm ra mắt, số linh kiện tương thích đã xác nhận, trạng thái.
- Thêm/Sửa: Tên `*`, Slug, Thế hệ (số), Năm ra mắt, Mã model (A-number, tùy chọn), Ảnh, Mô tả, Thứ tự, Hoạt động.
- Trang chi tiết dòng máy: danh sách linh kiện tương thích nhóm theo 10 nhóm + nút "Thêm linh kiện tương thích cho máy này".
- Không xóa được dòng máy đang có dữ liệu tương thích (chỉ cho tắt).

### C5. Quản lý linh kiện tương thích — [NGHIỆP VỤ CỐT LÕI]

- **Danh sách**: Sản phẩm (ảnh, tên, SKU) · Danh mục · Dòng iPhone · Trạng thái (Đã xác nhận / Chưa xác nhận / Không tương thích) · Ghi chú · Dữ liệu mẫu · Người xác nhận · Ngày. Lọc theo dòng máy, danh mục, trạng thái. Thao tác hàng loạt: Xác nhận · Chuyển "Chưa xác nhận" · Xóa.
- **Thêm**: chọn 1 sản phẩm (ô tìm có gợi ý ảnh + SKU) + chọn **nhiều** dòng iPhone + trạng thái + ghi chú + nguồn. Cặp đã tồn tại thì bỏ qua và báo.
- **Ma trận tương thích**: chọn một danh mục → bảng hàng = sản phẩm, cột = dòng iPhone, mỗi ô là biểu tượng trạng thái (✔ xanh / ? vàng / ✖ đỏ / trống); bấm ô để đổi trạng thái tuần tự, lưu bằng AJAX ngay.
- **Độ phủ linh kiện**: bảng hàng = dòng iPhone, cột = 10 nhóm, ô = số sản phẩm đã xác nhận; ô 0 tô vàng, bấm vào ô sang trang thêm sản phẩm/tương thích tương ứng.

### C6. Quản lý tồn kho

- **Tổng quan**: thẻ Tổng giá trị tồn kho (tồn × giá nhập) · Tổng số lượng · Sắp hết · Hết hàng. Bảng: ảnh, tên, SKU, tồn, ngưỡng, trạng thái, giá trị tồn, nút Nhập / Điều chỉnh.
- **Nhập kho**: chọn sản phẩm (hoặc nhiều dòng một lúc), số lượng > 0, giá nhập, nhà cung cấp/ghi chú → ghi phiếu nhập; có thể in phiếu nhập [NÊN CÓ].
- **Điều chỉnh kiểm kê**: chọn sản phẩm, nhập số tồn thực tế, lý do `*` → hệ thống tự tính chênh lệch.
- **Lịch sử nhập xuất**: thời gian · sản phẩm · loại (Nhập kho / Xuất theo đơn / Hoàn kho do hủy / Điều chỉnh / Tồn đầu kỳ) · thay đổi (+xanh / −đỏ) · tồn trước → sau · đơn hàng liên quan · người thực hiện · ghi chú. Lọc theo sản phẩm, loại, khoảng ngày; xuất CSV.
- Mọi thay đổi tồn kho đi qua service `adjust_stock` (SPEC 9.8).

### C7. Quản lý đơn hàng

- **Danh sách**: tab trạng thái có số đếm (Tất cả · Chờ xác nhận · Đã xác nhận · Đang chuẩn bị · Đang giao · Đã giao · Đã hủy). Cột: mã đơn · khách hàng · SĐT · ngày đặt · số SP · tổng tiền · phương thức thanh toán · trạng thái thanh toán · trạng thái đơn · hành động. Lọc khoảng ngày, phương thức, trạng thái thanh toán; tìm theo mã, tên, SĐT, email. Thao tác hàng loạt: Xác nhận các đơn đã chọn (chỉ áp dụng cho đơn hợp lệ), Xuất CSV.
- **Chi tiết đơn**:
  - Header: mã đơn, ngày đặt, 2 badge trạng thái, **các nút hành động chỉ gồm những bước hợp lệ tiếp theo** theo bảng SPEC 9.6 (ví dụ đơn chờ xác nhận: "Xác nhận đơn", "Hủy đơn"; đang chuẩn bị: "Bắt đầu giao hàng"; đang giao: "Đã giao thành công", "Giao thất bại / Hủy"). Mỗi nút mở modal ghi chú (hủy thì bắt buộc lý do).
  - **Thanh tiến trình** ngang các bước đơn hàng.
  - Card: thông tin khách hàng (link sang trang khách) · người nhận & địa chỉ · ghi chú · danh sách sản phẩm (ảnh, tên, SKU, đơn giá, SL, thành tiền) · tổng tiền chi tiết (tạm tính, giảm giá + mã, phí ship, tổng) · thanh toán và danh sách giao dịch.
  - Cột phải: **timeline lịch sử trạng thái** (ai, lúc nào, ghi chú) + ghi chú nội bộ của Admin (thêm được).
  - Nút **In hóa đơn / phiếu giao hàng** (trang in A4 có logo).
- Không có ô sửa tay trạng thái hoặc tổng tiền.

### C8. Quản lý thanh toán

- Thẻ: Tổng tiền thành công theo từng phương thức (COD / VNPay / MoMo) · Số giao dịch thất bại · Chờ hoàn tiền.
- Bảng: mã giao dịch · mã giao dịch cổng · mã đơn (link) · khách hàng · phương thức · số tiền · trạng thái · thời gian. Lọc phương thức, trạng thái, khoảng ngày.
- Chi tiết: thông tin giao dịch + dữ liệu phản hồi của cổng (JSON định dạng đẹp, không có dữ liệu nhạy cảm).
- Mục **Chờ hoàn tiền**: nút "Đánh dấu đã hoàn tiền" (nhập mã giao dịch hoàn + ghi chú). Ngoài thao tác này, trang thanh toán chỉ để xem.

### C9. Quản lý khách hàng

- Thẻ: Tổng khách hàng · Khách mới 30 ngày · Khách đã mua hàng · Tài khoản bị khóa.
- Bảng: avatar · họ tên · email · SĐT · đăng ký bằng (Email/Google) · ngày đăng ký · số đơn · tổng chi tiêu · trạng thái. Lọc trạng thái, cách đăng ký, khoảng ngày; sắp xếp theo tổng chi tiêu.
- **Chi tiết khách hàng**: thẻ hồ sơ; 4 số liệu (tổng đơn, tổng chi tiêu, đơn gần nhất, số đánh giá); tab: Đơn hàng · Địa chỉ · Đánh giá · Hội thoại chatbot; ghi chú nội bộ.
- Hành động: **Khóa / Mở khóa** tài khoản (confirm modal), Gửi email đặt lại mật khẩu.
- [CẤM] hiển thị mật khẩu/hash/token; Admin không sửa email của khách; trang này không cấp quyền Admin.

### C10. Quản lý đánh giá

- Tab: Chờ duyệt (badge) · Đã duyệt · Đã ẩn.
- Mỗi đánh giá dạng thẻ: sao, nội dung, sản phẩm (ảnh + tên), khách hàng, mã đơn, ngày. Nút: Duyệt · Ẩn · Xóa · Trả lời.
- Chọn nhiều → "Duyệt tất cả đã chọn". Lọc theo số sao, sản phẩm.
- Sau thao tác tự cập nhật điểm trung bình sản phẩm.

### C11. Quản lý khuyến mãi

- **Mã giảm giá**: bảng: mã · mô tả · loại (% / số tiền) · giá trị · đơn tối thiểu · đã dùng/giới hạn (thanh tiến trình) · thời gian · trạng thái tự tính (Đang chạy / Sắp diễn ra / Hết hạn / Đã tắt) · toggle bật/tắt.
- **Thêm/Sửa mã**: Mã `*` (nút tạo mã ngẫu nhiên), Mô tả, Loại giảm `*`, Giá trị `*`, Giảm tối đa (cho loại %), Đơn tối thiểu, Tổng lượt dùng, Lượt/khách, Bắt đầu – Kết thúc `*`, Kích hoạt. Ô xem trước: "Đơn 1.000.000₫ sẽ được giảm X₫".
- **Chi tiết mã**: lịch sử sử dụng (khách, đơn, số tiền giảm, thời gian).
- **Giảm giá sản phẩm hàng loạt**: chọn danh mục hoặc nhiều sản phẩm → nhập % giảm + thời gian → xem trước danh sách giá mới → Áp dụng. Có nút "Gỡ giảm giá".

### C12. Quản lý chatbot (iParts AI Assistant)

- **Cấu hình**: bật/tắt chatbot · lời chào · danh sách câu hỏi gợi ý (thêm/xóa/kéo sắp xếp) · thông tin cửa hàng bổ sung cho AI · giới hạn tin nhắn/giờ cho Khách vãng lai và Khách hàng · trạng thái kết nối Gemini (Đã cấu hình / Chưa cấu hình, không hiển thị key) + nút **Kiểm tra kết nối** (gửi câu thử, báo thời gian phản hồi).
- **Lịch sử hội thoại**: bảng: người dùng (hoặc "Khách vãng lai") · câu hỏi đầu · số tin nhắn · thời gian · có lỗi. Lọc ngày, loại người dùng, có lỗi; tìm theo nội dung/email. Chi tiết hiển thị **dạng khung chat** giống widget, mỗi câu trả lời có nút "Xem chi tiết kỹ thuật" (ý định, công cụ đã gọi, thời gian phản hồi).
- **Thống kê**: thẻ (tổng hội thoại, tin nhắn hôm nay, thời gian phản hồi TB, tỉ lệ lỗi); biểu đồ line số tin nhắn theo ngày; bar Top dòng iPhone được hỏi; bar Top loại linh kiện được hỏi.
- **Câu hỏi chưa có câu trả lời**: danh sách câu hỏi mà chatbot không tìm thấy sản phẩm/tương thích, kèm nút "Thêm sản phẩm" / "Thêm tương thích" để Admin bổ sung dữ liệu.

### C13. Báo cáo & thống kê

Mỗi báo cáo có: bộ lọc thời gian (ngày/tuần/tháng/khoảng tùy chọn), thẻ tổng, biểu đồ, bảng chi tiết, nút **Xuất CSV** (UTF-8 có BOM để Excel đọc đúng tiếng Việt) và **In**.

| Báo cáo    | Nội dung                                                                                                           |
| ---------- | ------------------------------------------------------------------------------------------------------------------ |
| Doanh thu  | Doanh thu, số đơn, giảm giá, phí ship, AOV theo kỳ; line chart; so sánh kỳ trước                                   |
| Sản phẩm   | SL bán, doanh thu, lợi nhuận gộp ước tính, điểm đánh giá theo sản phẩm; danh sách sản phẩm không bán được trong kỳ |
| Danh mục   | Doanh thu và SL bán theo 10 nhóm; doughnut + bảng                                                                  |
| Đơn hàng   | Số đơn theo trạng thái, theo phương thức thanh toán, tỉ lệ hủy, lý do hủy phổ biến                                 |
| Kho hàng   | Tồn hiện tại, giá trị tồn, nhập/xuất trong kỳ, sắp hết, hết hàng                                                   |
| Khách hàng | Khách mới theo thời gian, top khách chi tiêu nhiều, tỉ lệ khách mua lại                                            |

### C14. Nội dung website

- **Banner trang chủ**: danh sách thẻ có ảnh xem trước, kéo thả sắp xếp, bật/tắt; form: tiêu đề, mô tả, ảnh (khuyến nghị 1600×600), chữ nút, link nút.
- **Trang chính sách**: danh sách các trang (giới thiệu, bảo hành, đổi trả, vận chuyển, hướng dẫn mua hàng, điều khoản, bảo mật); form sửa có trình soạn thảo đơn giản (in đậm, tiêu đề, danh sách, link), nút xem trước.
- **Câu hỏi thường gặp**: CRUD + kéo thả thứ tự.
- **Người đăng ký nhận tin**: danh sách, tìm, xuất CSV, xóa.
- **Tin nhắn liên hệ**: danh sách tin khách gửi từ trang Liên hệ, trạng thái Mới / Đã xử lý.

### C15. Cài đặt hệ thống

Chia tab:

- **Thông tin cửa hàng**: logo, tên, giới thiệu ngắn, địa chỉ, giờ làm việc, thanh thông báo đầu trang.
- **Vận chuyển & thanh toán**: phí giao tiêu chuẩn, phí giao nhanh, ngưỡng miễn phí vận chuyển, bật/tắt từng phương thức thanh toán (chỉ bật được khi đã cấu hình `.env`).
- **Liên hệ & mạng xã hội**: hotline, email, link Zalo, Messenger, Telegram, Facebook (trống thì ẩn trên web).
- **Trạng thái tích hợp** (chỉ xem): Google OAuth, Gemini, VNPay, MoMo, SMTP: hiển thị Đã cấu hình ✔ / Chưa cấu hình ✖ kèm hướng dẫn ngắn; phiên bản Python/Django; chế độ DEBUG. Không bao giờ hiển thị giá trị key.

Lưu xong có hiệu lực ngay trên website (xóa cache StoreSetting).

### C16. Tài khoản quản trị (chỉ Super Admin)

- Danh sách: avatar, tên, email, vai trò (Super Admin / Admin / nhóm), lần đăng nhập cuối, trạng thái.
- Tạo tài khoản Admin: họ tên, email, mật khẩu tạm (nút tạo ngẫu nhiên, hiển thị một lần), vai trò/nhóm.
- Hành động: đổi vai trò, khóa/mở khóa, thu hồi quyền Admin (chuyển thành Customer). Không cho tự thu hồi quyền của chính mình; không cho khóa Super Admin cuối cùng.
- [NÊN CÓ] Nhật ký hoạt động quản trị: ai làm gì, đối tượng nào, lúc nào.

### C17. Hồ sơ của tôi

Sửa họ tên, avatar, SĐT; đổi mật khẩu; xem lịch sử đăng nhập gần đây [NÊN CÓ].

### C18. Đăng nhập Admin `/quan-tri/dang-nhap/`

Trang riêng nền tối có logo iParts Store Admin; email/username, mật khẩu (hiện/ẩn), ghi nhớ; giới hạn đăng nhập sai như SPEC 7.3. Tài khoản không phải staff → "Tài khoản không có quyền quản trị". Admin đăng nhập ở trang khách vẫn được, ở lại website khách (không tự chuyển trang).

---

## PHẦN D. KỸ THUẬT

- Tổ chức code trong app `dashboard`: `views/` tách theo module (`products.py`, `orders.py`...), `forms/`, `services/` (thống kê, doanh thu), `urls.py` có `app_name = "dashboard"`. Template ở `templates/dashboard/<module>/`.
- Component dùng chung trong `templates/dashboard/components/`: `page_header.html`, `stat_card.html`, `filter_bar.html`, `data_table.html`, `pagination.html`, `empty_state.html`, `confirm_modal.html`, `status_badge.html`.
- Cấu hình menu sidebar viết **một nơi duy nhất** (ví dụ `dashboard/menu.py`: danh sách mục, icon, url name, quyền cần có, hàm đếm badge) để render tự động, đánh dấu mục đang chọn theo `request.resolver_match`.
- JS: `static/js/dashboard/` tách `sidebar.js`, `charts.js`, `tables.js`, `quick-search.js`, `product-form.js`, `compat-matrix.js`. Chart.js lưu local trong `static/vendor/`.
- Mọi view dùng `StaffRequiredMixin`; mục Tài khoản quản trị dùng `SuperuserRequiredMixin`. Mọi thao tác ghi là POST + CSRF.
- Truy vấn tối ưu (`select_related`, `prefetch_related`, `annotate`), không N+1. Trang danh sách tải dưới 1 giây với dữ liệu seed.
- Toàn bộ chữ tiếng Việt có dấu. Định dạng tiền `1.250.000₫`, ngày `19/11/2026 14:30`.

---

## PHẦN E. THỨ TỰ THỰC HIỆN VÀ TIÊU CHÍ HOÀN THÀNH

Làm theo thứ tự. Xong mỗi bước: chạy `python manage.py check`, test, runserver kiểm tra trang, cập nhật `docs/PROGRESS.md`, báo tôi ngắn gọn bằng tiếng Việt rồi mới sang bước sau.

1. **Phân quyền Admin trên website khách** (Phần A) + test A5.
2. **Khung Admin Panel**: base layout, sidebar accordion, topbar, component dùng chung, đăng nhập admin, trang 403.
3. **Dashboard** (C1) với dữ liệu thật.
4. **Sản phẩm, Danh mục, Dòng iPhone, Thương hiệu** (C2–C4).
5. **Linh kiện tương thích** (C5) gồm ma trận và độ phủ.
6. **Tồn kho** (C6).
7. **Đơn hàng, Thanh toán** (C7–C8).
8. **Khách hàng, Đánh giá, Khuyến mãi** (C9–C11).
9. **Chatbot** (C12).
10. **Báo cáo** (C13).
11. **Nội dung, Cài đặt, Tài khoản quản trị, Hồ sơ** (C14–C17).

**Hoàn thành khi:**

- [ ] Admin xem toàn bộ website như khách, chat được với AI, không thấy và không gọi được giỏ hàng/yêu thích/đặt hàng (kể cả gọi thẳng URL/API).
- [ ] Dropdown tài khoản Admin có "Vào trang quản trị" dẫn tới `/quan-tri/`.
- [ ] Customer và Guest không vào được `/quan-tri/`.
- [ ] Sidebar bên trái đủ các mục ở B3, bấm mục cha sổ ra mục con, mục đang mở được tô sáng, thu gọn được, chạy tốt trên mobile.
- [ ] Dashboard có biểu đồ doanh thu 7 ngày và biểu đồ tròn sản phẩm theo danh mục từ dữ liệu thật, cùng các biểu đồ và bảng ở C1.
- [ ] Mỗi module C2–C17 thao tác được đầy đủ thêm/sửa/xóa/xem theo đặc tả, có tìm kiếm, lọc, phân trang, thông báo kết quả.
- [ ] Không có nút "chết", không lỗi 500, không lỗi Console.
- [ ] `python manage.py test` chạy xanh.
