# FB AUTO VIDEO STUDIO PRO V3 — TÀI LIỆU BÀN GIAO & HƯỚNG DẪN VẬN HÀNH

Hệ thống tự động hóa sản xuất video ngắn 9:16 (Facebook Reels, TikTok, Shorts) từ nội dung Facebook có sẵn, sử dụng trí tuệ nhân tạo Gemini AI và công nghệ render đồ họa video tự động.
Hỗ trợ cả máy tính **Windows (10/11)** và **Apple MacBook (macOS Intel & Apple Silicon M1/M2/M3/M4)**.

---

## 📁 1. CẤU TRÚC THƯ MỤC BÀN GIAO

* **Bộ Khởi Động Cho Windows:**
  * `1_Cai_Dat_Moi_Truong.bat`: Chạy lần đầu tiên để cài đặt toàn bộ thư viện Python cần thiết.
  * `2_Chay_Ung_Dung.bat`: Nhấp đúp để mở giao diện trung tâm điều khiển Studio.
  * `3_Kiem_Tra_He_Thong.bat`: Kiểm tra chẩn đoán kết nối, thư viện và tài nguyên hệ thống.
  * `4_Day_Len_Github.bat`: Script hỗ trợ đẩy nhanh mã nguồn lên GitHub.

* **Bộ Khởi Động Cho MacBook (macOS):**
  * `1_Cai_Dat_Moi_Truong_Mac.command`: Nhấp đúp để tự động khởi tạo môi trường ảo `.venv` và cài thư viện.
  * `2_Chay_Ung_Dung_Mac.command`: Nhấp đúp để mở Studio trên MacBook.
  * `3_Kiem_Tra_He_Thong_Mac.command`: Nhấp đúp để chạy kiểm tra chẩn đoán trên MacBook.

* **Tài Liệu Hướng Dẫn:**
  * `HUONG_DAN_SU_DUNG_FB_AUTO_VIDEO_STUDIO_V3.pdf`: Sổ tay hướng dẫn chi tiết chuẩn in ấn A4 (10 trang).
  * `README.md`: Hướng dẫn tổng quan trên GitHub.

* **Tài Nguyên & Mã Nguồn:**
  * `assets/backgrounds/`: **12 video nền 9:16 chất lượng cao** (Rừng tre, Thác nước, Nắng mai, Sóng biển, Hoàng hôn, Đồi thông...).
  * `assets/music/`: **10 bản nhạc nền bản quyền mở CC0** (Thiền định, Piano cảm hứng, Guitar mộc, Sáo trúc dưỡng sinh...).
  * `assets/fonts/`: Font Unicode Arial Bold hỗ trợ tiếng Việt đầy đủ.
  * `extension/`: Mã nguồn tiện ích mở rộng Chrome Extension `FB Video Studio v3` (quét bài tự động).
  * `app.py`: Ứng dụng Desktop điều khiển trung tâm (CustomTkinter GUI).
  * `tool1.py`: Tiến trình AI quét bài, trích xuất âm thanh/văn bản và viết kịch bản 9:16.
  * `tool2.py`: Tiến trình dựng video 9:16 từ kịch bản đã duyệt.
  * `google_apps_script/`: Mã Apps Script nạp vào Google Sheet quản lý kênh và duyệt bài.

---

## 🚀 2. HƯỚNG DẪN CÀI ĐẶT & SỬ DỤNG LẦN ĐẦU

### BƯỚC 1: Cài Đặt Môi Trường
* **Trên Windows:** Nhấp đúp vào **`1_Cai_Dat_Moi_Truong.bat`**.
* **Trên MacBook:** Nhấp đúp vào **`1_Cai_Dat_Moi_Truong_Mac.command`**.  
  *(Yêu cầu: Máy đã có Python 3.10 trở lên tải từ https://www.python.org/downloads/)*

### BƯỚC 2: Cài Đặt Extension Vào Trình Duyệt Chrome
1. Mở Chrome, vào: `chrome://extensions/`
2. Bật **Developer mode** ở góc trên bên phải.
3. Bấm **Load unpacked** và chọn thư mục **`extension`** trong gói này.

### BƯỚC 3: Điền Cấu Hình & Khởi Động Studio
1. Nhấp đúp vào **`2_Chay_Ung_Dung.bat`** (Windows) hoặc **`2_Chay_Ung_Dung_Mac.command`** (MacBook).
2. Tại tab **⚙ Cài Đặt**:
   * Sao chép **Mã Token kết nối** và dán vào Extension Chrome.
   * Điền **Gemini API Key** (lấy miễn phí tại: https://aistudio.google.com/) và **Google Sheet ID**.
3. Bấm **Lưu Cấu Hình** và bắt đầu sản xuất video!

---

## 🎬 3. QUY TRÌNH VẬN HÀNH SẢN XUẤT 3 BƯỚC

1. **Bước 1 — Quét & Trích xuất AI:** 
   * Tích chọn kênh cần quét trên App ➔ Bấm "Kích hoạt quét".
   * Extension quét Reels ➔ Gemini AI trích xuất nội dung và viết kịch bản chuẩn 9:16.
2. **Bước 2 — Duyệt & Tùy biến kịch bản:**
   * Tùy chọn 1 trong 12 Video nền và 1 trong 10 Bản nhạc nền CC0 (hoặc để tự động đổi).
   * Bố cục quang học tự động căn giữa (3 ý, 5 ý hay 8 ý luôn cân đối tuyệt đối).
   * Áp dụng 5 Theme màu: Gold, Emerald, Cyan, Ruby, White.
3. **Bước 3 — Kho Video Thành Phẩm:**
   * Nhận video 9:16 hoàn chỉnh với âm thanh đã lồng ghép chuẩn xác.
   * Xem video trực tiếp trên App, bấm "Sao Chép Caption" để đăng bài ngay lên Facebook/TikTok/Shorts!

---

## 🔒 4. BẢO MẬT & BẢN QUYỀN
* Toàn bộ 12 video nền và 10 bản nhạc nền trong thư viện đều thuộc quyền sử dụng miễn phí (Royalty-Free / CC0), hoàn toàn không dính bản quyền âm thanh khi đăng tải lên mạng xã hội.
* Hệ thống hoạt động hoàn toàn cục bộ (Local First) trên máy tính của bạn, không gửi dữ liệu ra bên ngoài.
