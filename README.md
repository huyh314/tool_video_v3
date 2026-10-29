# FB Auto Video Studio Pro v3 🎬🚀

> **Hệ thống tự động hóa sản xuất video ngắn 9:16 (Facebook Reels, TikTok, YouTube Shorts) từ nội dung Facebook có sẵn, tích hợp trí tuệ nhân tạo Google Gemini AI và công nghệ render đồ họa video tự động.**
> **Tương thích 100% đa nền tảng: Windows 10/11 & Apple MacBook (macOS Intel, M1, M2, M3, M4).**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![OS](https://img.shields.io/badge/OS-Windows%20%7C%20macOS-success.svg)
![GUI](https://img.shields.io/badge/GUI-CustomTkinter-emerald.svg)
![AI](https://img.shields.io/badge/AI-Google%20Gemini-orange.svg)
![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)

---

## ✨ Tính Năng Nổi Bật

1. 🎯 **Bố Cục Quang Học Thích Ứng (Adaptive Dynamic Layout):**
   - Tự động đo đạc và căn giữa quang học (`offset_y = (available_h - total_h) // 2`).
   - Tùy biến cỡ chữ thông minh (`auto`, `large`, `medium`, `small`) theo số lượng ý (3 ý, 5 ý, hay 8 ý luôn cân đối tuyệt đối).
   - Tự do đổi màu chữ, màu thẻ viền và áp dụng 5 Theme màu dựng sẵn (*Gold, Emerald, Cyan, Ruby, White*).

2. 🎵 **Kho Nhạc Nền 10 Bản CC0 Không Bản Quyền:**
   - 10 bản nhạc nền tuyển chọn: *Thiền Định Chuông Gió, Piano Cảm Hứng, Lo-fi Học Bài, Guitar Mộc Mạc, Sáo Trúc Dưỡng Sinh...*
   - Hỗ trợ xoay vòng nhạc tự động theo kịch bản hoặc ghim bản nhạc yêu thích cho từng video.

3. 🌄 **Kho Video Nền Chuyển Động 9:16 Tuyển Chọn:**
   - 12 video nền Full HD dọc: *Rừng tre, Thác nước, Sóng biển, Hoàng hôn, Đồi thông, Tầng mây...*

4. 🤖 **AI Quét & Viết Kịch Bản Tự Động:**
   - Kết hợp Chrome Extension quét Reels từ Facebook Fanpage.
   - Google Gemini AI trích xuất nội dung cốt lõi và biên soạn kịch bản 9:16 viral.

5. 🖥️ **Đa Nền Tảng — Chạy Mượt Mà Trên Windows & MacBook:**
   - Hỗ trợ 1-click launcher cho cả Windows (`.bat`) và macOS (`.command`).
   - Tích hợp font Unicode tiếng Việt nội bộ, không phụ thuộc font hệ thống.
   - Xây dựng bằng Modern GUI (CustomTkinter), hỗ trợ Dark Theme chuẩn Studio.

---

## 🚀 Hướng Dẫn Cài Đặt & Sử Dụng (Clone & Run)

### 1. Tải Mã Nguồn Về Máy (Git Clone)

Mở **Terminal** (trên Mac) hoặc **PowerShell** (trên Windows) và chạy lệnh:

```bash
git clone https://github.com/huyh314/tool_video_v3.git
cd FB_Auto_Video_Studio_v3
```

*(Hoặc dùng link SSH nếu đã thêm key: `git clone git@github.com:huyh314/tool_video_v3.git`)*

---

### 2. Cài Đặt Môi Trường (Chỉ Chạy 1 Lần Đầu)

> **Yêu cầu chung:** Máy tính đã cài đặt **Python 3.10 trở lên** (tải tại: https://www.python.org/downloads/).

#### 🪟 Đối Với Máy Tính Windows:
- Khi cài Python, nhớ tích chọn ô **"Add Python.exe to PATH"**.
- Nhấp đúp chuột vào tệp: 👉 **`1_Cai_Dat_Moi_Truong.bat`**
- Chương trình sẽ tự động cài đặt toàn bộ thư viện cần thiết.

#### 🍎 Đối Với Máy MacBook (macOS Intel & Apple Silicon M1/M2/M3/M4):
- Nhấp đúp chuột vào tệp: 👉 **`1_Cai_Dat_Moi_Truong_Mac.command`**  
  *(Hoặc mở Terminal và gõ: `bash 1_Cai_Dat_Moi_Truong_Mac.command`)*
- Chương trình sẽ tự động khởi tạo môi trường ảo `.venv` và cài đặt trọn gói thư viện.

---

### 3. Cài Đặt Chrome Extension (Quét Bài Tự Động)

1. Mở Google Chrome, truy cập: `chrome://extensions/`
2. Bật công tắc **Chế độ dành cho nhà phát triển (Developer mode)** ở góc trên bên phải.
3. Bấm nút **Tải tiện ích đã giải nén (Load unpacked)**.
4. Trỏ đến thư mục **`extension`** trong thư mục mã nguồn vừa clone về và bấm **Select Folder**.

---

### 4. Khởi Động & Sử Dụng Studio

#### 🪟 Trên Windows:
- Nhấp đúp chuột vào: 👉 **`2_Chay_Ung_Dung.bat`**

#### 🍎 Trên MacBook (macOS):
- Nhấp đúp chuột vào: 👉 **`2_Chay_Ung_Dung_Mac.command`**

---

### 5. Thiết Lập & Bắt Đầu Sản Xuất Video

1. Tại tab **⚙ Cài Đặt**:
   - Sao chép **Mã Token kết nối** và dán vào Extension Chrome để liên kết.
   - Nhập **Gemini API Key** (lấy miễn phí tại: [Google AI Studio](https://aistudio.google.com/)).
   - Nhập **Google Sheet ID** quản lý bài viết.
2. Bấm **Lưu Cấu Hình** và bắt đầu sản xuất video tự động!

---

## 🛠️ Cấu Trúc Mã Nguồn

```text
FB_Auto_Video_Studio_v3/
├── 1_Cai_Dat_Moi_Truong.bat          # [Windows] Script 1-click cài đặt thư viện
├── 2_Chay_Ung_Dung.bat               # [Windows] Script 1-click mở Studio
├── 3_Kiem_Tra_He_Thong.bat           # [Windows] Script 1-click chẩn đoán lỗi
├── 4_Day_Len_Github.bat              # [Windows] Script 1-click đẩy lên GitHub
├── 1_Cai_Dat_Moi_Truong_Mac.command  # [macOS] Script 1-click cài đặt trên MacBook
├── 2_Chay_Ung_Dung_Mac.command       # [macOS] Script 1-click mở Studio trên MacBook
├── 3_Kiem_Tra_He_Thong_Mac.command   # [macOS] Script 1-click chẩn đoán trên MacBook
├── HUONG_DAN_SU_DUNG_FB_AUTO_VIDEO_STUDIO_V3.pdf # Sổ tay hướng dẫn PDF chuẩn A4 (10 trang)
├── README.md                         # Tài liệu hướng dẫn GitHub
├── README_HUONG_DAN_CHUYEN_GIAO.md   # Hướng dẫn chi tiết bàn giao
├── requirements.txt                  # Danh sách thư viện Python
├── configure.py                      # Công cụ cấu hình & chẩn đoán hệ thống
├── app.py                            # Ứng dụng Desktop Studio (CustomTkinter GUI)
├── tool1.py                          # Tiến trình AI quét & trích xuất kịch bản
├── tool2.py                          # Tiến trình Render video tự động
├── collector/                        # Bộ thu thập dữ liệu & kết nối Chrome/Gemini
├── renderer/                         # Bộ render đồ họa, layout quang học & âm thanh
├── shared/                           # Cấu hình dùng chung, model & database SQLite
├── assets/
│   ├── backgrounds/                  # 12 Video nền 9:16 Full HD
│   ├── music/                        # 10 Bản nhạc nền CC0 mở quyền
│   └── fonts/                        # Font Unicode tiếng Việt (arialbd.ttf)
├── extension/                        # Mã nguồn Chrome Extension quét Reels
└── tests/                            # Bộ Unit Test tự động (27/27 passed)
```

---

## 🧪 Chạy Kiểm Thử Tự Động (Unit Tests)

Dự án đi kèm bộ test toàn diện bao phủ Collector, Bridge, Engine Render, Recovery và Models:

```bash
# Trên Windows hoặc macOS:
python -m pytest
```

---

## 🔒 Bản Quyền & Giấy Phép

* Toàn bộ video nền (`assets/backgrounds/`) và nhạc nền (`assets/music/`) đều thuộc bản quyền miễn phí (CC0 / Royalty-Free), an toàn tuyệt đối khi đăng lên Facebook Reels, TikTok, YouTube Shorts.
* Hệ thống hoạt động theo kiến trúc **Local-First** trên máy tính cá nhân, bảo mật dữ liệu tuyệt đối.
