# FB AUTO VIDEO STUDIO PRO V3 — TÀI LIỆU BÀN GIAO & HƯỚNG DẪN VẬN HÀNH

Hệ thống tự động hóa sản xuất video ngắn 9:16 (Facebook Reels, TikTok, Shorts) từ nội dung Facebook có sẵn, sử dụng trí tuệ nhân tạo Gemini AI và công nghệ render đồ họa video tự động.

---

## 📁 1. CẤU TRÚC THƯ MỤC BÀN GIAO

* `1_Cai_Dat_Moi_Truong.bat`: Chạy lần đầu tiên để cài đặt toàn bộ thư viện Python cần thiết.
* `2_Chay_Ung_Dung.bat`: Nhấp đúp để mở giao diện trung tâm điều khiển Studio.
* `3_Kiem_Tra_He_Thong.bat`: Kiểm tra chẩn đoán kết nối, thư viện và tài nguyên hệ thống.
* `assets/`:
  * `backgrounds/`: **12 video nền 9:16 chất lượng cao** (Rừng tre, Thác nước, Nắng mai, Sóng biển, Hoàng hôn, Đồi thông...).
  * `music/`: **10 bản nhạc nền bản quyền mở CC0** (Thiền định, Piano cảm hứng, Guitar mộc, Sáo trúc dưỡng sinh...).
* `extension/`: Mã nguồn tiện ích mở rộng Chrome Extension `FB Video Studio v3` (quét bài tự động).
* `app.py`: Ứng dụng Desktop điều khiển trung tâm (CustomTkinter GUI).
* `tool1.py`: Tiến trình AI quét bài, trích xuất âm thanh/văn bản và viết kịch bản 9:16.
* `tool2.py`: Tiến trình dựng video 9:16 từ kịch bản đã duyệt.
* `google_apps_script/`: Mã Apps Script nạp vào Google Sheet quản lý kênh và duyệt bài.

---

## 🚀 2. HƯỚNG DẪN CÀI ĐẶT & SỬ DỤNG LẦN ĐẦU (3 BƯỚC ĐƠN GIẢN)

### BƯỚC 1: Cài Đặt Môi Trường
1. Yêu cầu máy tính đã cài **Python 3.10 trở lên** (tải tại: https://www.python.org/ - nhớ tích chọn *Add Python to PATH*).
2. Nhấp đúp vào tệp **`1_Cai_Dat_Moi_Truong.bat`**. Chương trình sẽ tự động tải và cài đặt đầy đủ tất cả thư viện cần thiết.

### BƯỚC 2: Cài Đặt Extension Vào Trình Duyệt Chrome
1. Mở trình duyệt Google Chrome, truy cập vào đường dẫn: `chrome://extensions/`
2. Bật công tắc **Chế độ dành cho nhà phát triển (Developer mode)** ở góc trên bên phải.
3. Bấm nút **Tải tiện ích đã giải nén (Load unpacked)** ở góc trên bên trái.
4. Trỏ đến thư mục **`extension`** trong gói bàn giao này và bấm **Select Folder**.
5. Biểu tượng tiện ích `FB Video Studio v3` sẽ xuất hiện trên thanh công cụ của Chrome.

### BƯỚC 3: Điền Cấu Hình & Khởi Động Studio
1. Nhấp đúp vào **`2_Chay_Ung_Dung.bat`** để mở ứng dụng.
2. Tại tab **⚙ Cài Đặt**:
   * Sao chép **Mã Token kết nối** (Local API Token) và dán vào tiện ích Chrome Extension để kết nối.
   * Điền **Google Sheet ID** và **Gemini API Key** (lấy miễn phí tại: https://aistudio.google.com/).
3. Bắt đầu sản xuất theo Quy trình 3 bước cốt lõi!

---

## 🎬 3. QUY TRÌNH VẬN HÀNH SẢN XUẤT 3 BƯỚC

1. **Bước 1 — Quét & Trích xuất AI:** 
   * Tích chọn kênh cần quét trên App ➜ Bấm "Kích hoạt quét".
   * Extension tự động mở Facebook Reels, thu thập video gốc ➜ Gemini AI trích xuất nội dung và viết kịch bản chuẩn 9:16.
2. **Bước 2 — Duyệt & Tùy biến kịch bản:**
   * Vào tab "Duyệt & Sửa Kịch Bản", bấm "Sửa" kịch bản bất kỳ.
   * Tùy chọn 1 trong 12 Video nền chuyển động hoặc để tự động đổi.
   * Tùy chọn 1 trong 10 Bản nhạc nền CC0 hoặc để tự động đổi.
   * Bố cục quang học tự động căn giữa (dù có 3 ý, 5 ý hay 8 ý luôn cân đối tuyệt đối).
   * Bấm "Lưu Sửa Đổi & Tạo Video Mẫu Ngay".
3. **Bước 3 — Kho Video Thành Phẩm:**
   * Nhận video 9:16 hoàn chỉnh với âm thanh đã lồng ghép chuẩn xác.
   * Xem video trực tiếp trên App, bấm "Sao Chép Caption" để đăng bài ngay lên Facebook/TikTok/Shorts!

---

## 🔒 4. BẢO MẬT & BẢN QUYỀN
* Toàn bộ 12 video nền và 10 bản nhạc nền trong thư viện đều thuộc quyền sử dụng miễn phí (Royalty-Free / CC0), hoàn toàn không dính bản quyền âm thanh khi đăng tải lên mạng xã hội.
* Hệ thống hoạt động hoàn toàn cục bộ (Local First) trên máy tính của bạn, không gửi dữ liệu ra bên ngoài ngoại trừ các API chính thức của Google Gemini và Google Sheet.
