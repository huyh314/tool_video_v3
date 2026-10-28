# Cài Google Apps Script v3

Không cần file OAuth JSON. Apps Script chạy dưới quyền tài khoản triển khai; hai tool gửi yêu cầu POST có mã kết nối riêng.

1. Mở đúng Google Sheet → **Tiện ích mở rộng → Apps Script**.
2. Sao lưu mã Apps Script hiện tại của bảng nếu có. Thay mã trong trình soạn thảo bằng nội dung `GoogleAppsScript_Code.gs` ở thư mục này. Không giữ đồng thời các hàm `doGet`, `doPost`, `onOpen` phiên bản cũ.
3. Lưu rồi chạy hàm `setupV3` từ trình soạn thảo. Đăng nhập/cấp quyền theo màn hình Google. Bốn bảng v3 và một bảng công việc ẩn được tạo; bảng dữ liệu cũ được giữ nguyên.
4. Quay lại Sheet, tải lại trang. Chọn menu **🎬 Video Studio v3 → 2. Đặt mã kết nối API** và nhập `sheet_token` lấy từ cấu hình cục bộ của hai tool. Mã được lưu vào Script Properties, không đặt trong ô bảng.
5. **Triển khai → Lần triển khai mới → Ứng dụng web**. Thực thi dưới dạng tài khoản của anh. Cho phép ứng dụng truy cập URL theo cấu hình phù hợp tài khoản; với client Python không đăng nhập trình duyệt, bản này yêu cầu quyền truy cập Web App **Anyone / Bất kỳ ai**, còn API xác thực mọi yêu cầu bằng `sheet_token`. Nếu chính sách Workspace không cho tùy chọn này, cần cấu hình phương thức xác thực khác trước khi dùng.
6. Sao chép URL kết thúc bằng `/exec` vào cấu hình `webhook_url` trên máy. Khi cập nhật mã sau này, **quản lý lần triển khai → sửa → phiên bản mới** để URL cũ dùng mã mới.
7. Chạy kiểm tra kết nối từ chương trình trên máy. GET trực tiếp vào URL trả `POST_REQUIRED` là bình thường; kiểm tra chuẩn là POST action `ping` có token, nhận `status: success`, `protocol: 3`.

Nếu đã có bảng **📋 Danh Sách Kênh** của bản cũ, chọn menu **Nhập danh sách kênh từ bảng cũ**. Lệnh sao chép kênh chưa có sang v3, giữ phạm vi và trạng thái tạm dừng, không chỉnh sửa bảng cũ. Kiểm tra lại cột thương hiệu đầu ra sau nhập. Không tự chạy chuyển dữ liệu khi mở Sheet.

## Dùng bốn bảng

- **V3 · Kênh theo dõi:** nhập tên và link fanpage HTTPS, bật TRUE, chu kỳ phút, phạm vi ngày, số bài tối đa/lượt, thương hiệu đầu ra. Mã kênh để trống lần đầu, hệ thống tự tạo. Muốn quét ngay: chọn dòng và dùng menu “Quét các kênh đang chọn”. Mặc định chu kỳ 60 phút, phạm vi 7 ngày, tối đa 10 video/lượt.
- **V3 · Bài và video gốc:** hiển thị bài, file và phần trích xuất. `PENDING` → `RUNNING` → `DONE` hoặc `FAILED`. Muốn thử lại: chọn dòng và dùng menu “Thử lại”. Chọn `SKIP` ở Lệnh để bỏ qua bài chưa xử lý.
- **V3 · Kịch bản:** sửa HOOK, các ý (mỗi dòng một ý), caption, thương hiệu, mẫu `auto`/`list`/`pages`, thời lượng (0 là tự động). Chọn dòng → menu “Duyệt các kịch bản đang chọn”. Chỉ gõ chữ APPROVED vào ô không thay thế việc duyệt bằng menu. Tool 2 chỉ nhận đúng mã nội dung đã duyệt.
- **V3 · Video thành phẩm:** một dòng theo mã thành phẩm, có phiên bản và file MP4/preview trên máy. Đường dẫn local không phải link xem từ điện thoại.

Sửa nội dung sau khi duyệt sẽ chuyển sang `NEEDS_REAPPROVAL`. Video đang dựng vẫn thuộc phiên bản cũ; kết quả được lưu nhưng dòng kịch bản báo `OUTDATED` để anh duyệt và dựng lại bản mới.

Không đổi tên bảng/cột hoặc sửa mã định danh và mã nội dung; dùng filter view để xem/sắp xếp. Nếu cần sửa cấu trúc, phải cập nhật schema ứng dụng tương ứng. Script kiểm tra tiêu đề và báo lỗi thay vì ghi nhầm cột. Các cột trạng thái kỹ thuật dùng mã tiếng Anh để hai tool đối chiếu nhất quán.

## Ý nghĩa trạng thái quét

- `DONE`: lượt quét hoàn thành có video nhận diện được.
- `PARTIAL`: chạm giới hạn lượt quét, chưa đến cuối trang hoặc thiếu ngày đăng; không bảo đảm đã lấy toàn bộ bài trong khoảng thời gian.
- `EMPTY`: không tìm được video đủ định danh; có thể kênh chưa có bài phù hợp hoặc giao diện Facebook thay đổi.
- `FAILED`: lỗi truy cập hoặc quá thời gian; hệ thống chờ 5 phút trước khi thử lịch lại, hoặc anh chọn quét ngay.

Mỗi lượt phân tích/render chỉ tự nhận lại khi tác vụ đang chạy bị hết lease. Lỗi đã xác nhận được giữ để anh xem và thử lại rõ ràng, tránh vòng lặp tốn API.
