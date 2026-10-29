#!/bin/bash
# ==============================================================================
# FB AUTO VIDEO STUDIO PRO V3 — CÀI ĐẶT MÔI TRƯỜNG TRÊN MACOS (MACBOOK)
# ==============================================================================
cd "$(dirname "$0")"

echo "===================================================================="
echo "    FB AUTO VIDEO STUDIO PRO V3 — CÀI ĐẶT MÔI TRƯỜNG TRÊN MACOS"
echo "===================================================================="
echo ""

# 1. Tìm kiếm Python 3
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "[LỖI] Không tìm thấy Python 3 trên máy Mac của bạn!"
    echo "----------------------------------------------------"
    echo "Vui lòng cài đặt Python 3 theo một trong hai cách:"
    echo "  Cách 1 (Khuyên dùng): Tải từ trang chủ https://www.python.org/downloads/macos/"
    echo "  Cách 2: Cài qua Homebrew bằng lệnh: brew install python python-tk"
    echo "----------------------------------------------------"
    read -p "Nhấn Enter để đóng..."
    exit 1
fi

PY_VER=$($PYTHON_CMD --version)
echo "[THÔNG TIN] Đang sử dụng: $PY_VER"
echo ""

# 2. Tạo / Cập nhật môi trường ảo (khuyên dùng trên macOS)
echo "[BƯỚC 1/3] Đang chuẩn bị môi trường ảo Python (.venv)..."
if [ ! -d ".venv" ]; then
    $PYTHON_CMD -m venv .venv
    echo "[OK] Đã tạo môi trường ảo .venv thành công."
else
    echo "[OK] Môi trường ảo .venv đã tồn tại."
fi

# Kích hoạt venv
source .venv/bin/activate
VENV_PY="python"

echo ""
echo "[BƯỚC 2/3] Đang nâng cấp pip..."
$VENV_PY -m pip install --upgrade pip

echo ""
echo "[BƯỚC 3/3] Đang tải và cài đặt các thư viện cần thiết..."
$VENV_PY -m pip install -r requirements.txt

echo ""
echo "===================================================================="
echo "      CÀI ĐẶT THÀNH CÔNG CHO MACBOOK! SẴN SÀNG HOẠT ĐỘNG!"
echo "===================================================================="
echo "Bạn có thể khởi động ứng dụng bằng cách:"
echo "  👉 Nhấp đúp chuột vào tệp: 2_Chay_Ung_Dung_Mac.command"
echo "===================================================================="
echo ""
read -p "Nhấn Enter để hoàn tất..."
