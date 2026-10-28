# Extension Video Studio v3

1. Mở `chrome://extensions`, bật Developer mode, chọn **Load unpacked** và thư mục `extension` này. Nếu bản cũ đã nạp, bấm Reload sau khi cập nhật mã; đóng hoặc tải lại các tab Facebook cũ để content script v3 được nạp.
2. Chạy Tool 1 trên máy. Mở popup extension, nhập **local_api_token** từ cấu hình cục bộ, bật nhận kênh và bấm **Lưu và kiểm tra kết nối**.
3. Đăng nhập Facebook trên chính hồ sơ Chrome đang cài extension nếu fanpage cần đăng nhập để xem. Thêm kênh và chọn quét trên các bảng Sheet v3.
4. Extension kiểm tra công việc mỗi 30 giây, mở tab nền riêng, thu thập trong thời gian giới hạn rồi gửi về Tool 1. Chỉ đóng tab do chính extension tạo sau khi Tool 1 xác nhận đã lưu kết quả.

Extension không giữ Gemini API key hoặc mã API Google Sheet và không tự tải video. Nó gửi ID/URL bài và metadata đến `http://127.0.0.1:8765`; Tool 1 tải, kiểm tra và phân tích file.

Kết quả chưa gửi thành công được lưu trong Chrome storage để thử lại sau restart. Một lần quét bị lỗi hoặc không có đủ ID video sẽ báo rõ; không lấy link video đầu tiên từ mã nguồn toàn trang. Lượt xem/tương tác không đọc được để trống. Ngày đăng không nhận diện được cũng để trống và báo lượt quét chưa xác nhận đầy đủ.

Nếu popup báo không kết nối: kiểm tra Tool 1 đang mở, mã ghép nối đúng, cổng 8765 không bị chương trình khác dùng. Nếu Chrome có trang đăng nhập/checkpoint thì xử lý trực tiếp trên trình duyệt trước khi quét lại.
