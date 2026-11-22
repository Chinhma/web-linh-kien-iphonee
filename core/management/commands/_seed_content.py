"""Nội dung mẫu tiếng Việt cho seed_data (trang chính sách, FAQ, đánh giá). Đây là nội dung mẫu cho đồ án."""

NOTE = '\n\n_Đây là nội dung mẫu phục vụ đồ án tốt nghiệp._'

PAGES = {
    'gioi-thieu': ('Giới thiệu iParts Store',
                   'iParts Store là cửa hàng trực tuyến chuyên cung cấp **linh kiện thay thế iPhone**: màn hình, pin, camera, '
                   'chân sạc, loa, micro, vỏ và khung máy...\n\n## Điểm khác biệt\n'
                   '- Tra cứu linh kiện tương thích theo từng dòng iPhone dựa trên dữ liệu đã xác nhận.\n'
                   '- Trợ lý **iParts AI Assistant** tư vấn 24/7, dữ liệu giá và tồn kho lấy trực tiếp từ hệ thống.\n'
                   '- Bảo hành rõ ràng, đổi trả nhanh chóng.' + NOTE),
    'chinh-sach-bao-hanh': ('Chính sách bảo hành',
                            '## Thời gian bảo hành\n- Bảo hành **3, 6 hoặc 12 tháng** tùy sản phẩm (ghi rõ trên trang sản phẩm).\n'
                            '- Linh kiện chính hãng tháo máy được bảo hành tối đa 12 tháng.\n\n## Điều kiện bảo hành\n'
                            '- Lỗi kỹ thuật do nhà sản xuất (điểm chết, sọc màn, pin phồng, mất cảm ứng...).\n'
                            '- Sản phẩm còn nguyên tem bảo hành của iParts Store.\n\n## Không bảo hành\n'
                            '- Lắp đặt sai kỹ thuật, rơi vỡ, cấn móp, vào nước, cháy nổ do nguồn điện.\n'
                            '- Tem bảo hành bị rách hoặc có dấu hiệu tác động.' + NOTE),
    'chinh-sach-doi-tra': ('Chính sách đổi trả',
                           '- Đổi mới trong **7 ngày** nếu sản phẩm lỗi do nhà sản xuất và còn nguyên tem, chưa qua sửa chữa.\n'
                           '- Sản phẩm đổi trả cần còn đầy đủ phụ kiện, bao bì.\n'
                           '- Không áp dụng đổi trả với linh kiện đã lắp sai hoặc hư hỏng do tác động bên ngoài.\n'
                           '- Hoàn tiền trong 3–5 ngày làm việc với đơn đã thanh toán online.' + NOTE),
    'chinh-sach-van-chuyen': ('Chính sách vận chuyển',
                              '- Giao **tiêu chuẩn** 3–5 ngày: 30.000₫, **miễn phí** cho đơn từ 2.000.000₫.\n'
                              '- Giao **nhanh** 1–2 ngày: 50.000₫.\n- Giao hàng toàn quốc, được kiểm tra hàng trước khi nhận.\n'
                              '- Phí vận chuyển có thể thay đổi theo cài đặt cửa hàng.' + NOTE),
    'huong-dan-mua-hang': ('Hướng dẫn mua hàng',
                           '## Các bước đặt hàng\n- Bước 1: Tra cứu linh kiện tương thích với dòng iPhone của bạn.\n'
                           '- Bước 2: Thêm sản phẩm vào giỏ hàng (cần đăng nhập).\n'
                           '- Bước 3: Áp mã giảm giá (nếu có) và tiến hành thanh toán.\n'
                           '- Bước 4: Chọn phương thức vận chuyển và thanh toán: COD, VNPay hoặc MoMo.\n'
                           '- Bước 5: Theo dõi đơn hàng trong mục Tài khoản > Đơn hàng của tôi.\n\n## Thanh toán\n'
                           '- **COD**: thanh toán tiền mặt khi nhận hàng.\n'
                           '- **VNPay / MoMo**: thanh toán online, đơn giữ hàng trong 15 phút.' + NOTE),
    'dieu-khoan': ('Điều khoản sử dụng',
                   '- Khi sử dụng website iParts Store, bạn đồng ý cung cấp thông tin chính xác khi đặt hàng.\n'
                   '- Giá và tồn kho có thể thay đổi; giá cuối cùng được hệ thống tính lại tại thời điểm đặt hàng.\n'
                   '- Thông tin tương thích mang tính tham khảo theo dữ liệu đã xác nhận của cửa hàng.\n'
                   '- iParts Store có quyền hủy đơn khi phát hiện gian lận hoặc thông tin không hợp lệ.' + NOTE),
    'chinh-sach-bao-mat': ('Chính sách bảo mật',
                           '- iParts Store chỉ thu thập thông tin cần thiết để xử lý đơn hàng: họ tên, email, số điện thoại, địa chỉ.\n'
                           '- Mật khẩu được mã hóa một chiều, nhân viên không xem được.\n'
                           '- Không lưu thông tin thẻ thanh toán; giao dịch online được xử lý bởi cổng VNPay/MoMo.\n'
                           '- Nội dung trò chuyện với iParts AI Assistant chỉ dùng để cải thiện chất lượng tư vấn.' + NOTE),
}

FAQS = [
    ('Làm sao biết linh kiện có tương thích với máy của tôi?',
     'Bạn vào trang Tra cứu tương thích, chọn dòng iPhone và loại linh kiện. Hệ thống chỉ hiển thị linh kiện đã được xác nhận tương thích. Bạn cũng có thể hỏi iParts AI Assistant.'),
    ('Linh kiện "Chính hãng tháo máy" khác gì OEM?',
     'Chính hãng tháo máy là linh kiện zin tháo từ máy Apple; OEM là linh kiện sản xuất theo tiêu chuẩn tương đương với giá tốt hơn; Linh kiện thay thế là phân khúc phổ thông.'),
    ('Thời gian bảo hành bao lâu?', 'Từ 3 đến 12 tháng tùy sản phẩm, được ghi rõ trên trang chi tiết sản phẩm.'),
    ('Tôi có được kiểm tra hàng trước khi nhận không?', 'Có, bạn được kiểm tra ngoại quan sản phẩm trước khi thanh toán cho đơn COD.'),
    ('Phí vận chuyển tính như thế nào?', 'Giao tiêu chuẩn 30.000₫ (miễn phí cho đơn từ 2.000.000₫), giao nhanh 50.000₫.'),
    ('Tôi có thể hủy đơn hàng không?', 'Bạn có thể tự hủy đơn khi đơn đang chờ xác nhận (hoặc đã xác nhận với đơn COD) trong mục Đơn hàng của tôi.'),
    ('Thanh toán online có an toàn không?', 'Giao dịch được xử lý qua cổng VNPay/MoMo và được xác minh chữ ký điện tử; iParts Store không lưu thông tin thẻ.'),
    ('Thay màn hình có mất True Tone không?', 'Với iPhone 8 trở lên, cần chuyển dữ liệu True Tone từ màn cũ sang màn mới bằng máy chuyên dụng để giữ tính năng này.'),
]

REVIEW_TEXTS = {
    5: ['Linh kiện đúng mô tả, lắp vào máy hoạt động ngon lành. Shop tư vấn nhiệt tình!',
        'Hàng đóng gói cẩn thận, giao nhanh. Màn hiển thị đẹp, cảm ứng mượt.',
        'Pin dùng cả ngày không lo hết, rất hài lòng với chất lượng.',
        'Tra cứu tương thích rất tiện, mua đúng linh kiện cho máy ngay lần đầu.',
        'Giá tốt, chất lượng ổn định, sẽ ủng hộ shop lâu dài.',
        'Thợ bên mình lắp thử rất vừa, không phải chỉnh sửa gì. Tuyệt vời.'],
    4: ['Sản phẩm tốt, giao hàng hơi chậm một chút nhưng vẫn ổn.',
        'Chất lượng tương xứng với giá, đóng gói kỹ.',
        'Lắp vừa khít, chỉ tiếc là hộp hơi móp do vận chuyển.',
        'Dùng được một tuần thấy ổn định, sẽ quay lại mua tiếp.'],
    3: ['Sản phẩm dùng tạm ổn, màu màn hơi khác bản gốc một chút.',
        'Hàng đúng mô tả nhưng giao lâu hơn dự kiến.'],
    2: ['Pin xuống hơi nhanh so với mong đợi, đang liên hệ bảo hành.',
        'Cảm ứng thỉnh thoảng hơi trễ, shop hỗ trợ đổi khá nhanh.'],
}
