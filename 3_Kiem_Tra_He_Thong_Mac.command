#!/bin/bash
# ==============================================================================
# FB AUTO VIDEO STUDIO PRO V3 — CHẨN ĐOÁN HỆ THỐNG TRÊN MACOS (MACBOOK)
# ==============================================================================
cd "$(dirname "$0")"

export NO_PROXY="localhost,127.0.0.1"

if [ -d ".venv" ]; then
    source .venv/bin/activate
    PYTHON_CMD="python"
elif command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

echo "===================================================================="
echo "   ĐANG KIỂM TRA CHẨN ĐOÁN TOÀN BỘ TÀI NGUYÊN VÀ THƯ VIỆN MACOS..."
echo "===================================================================="
echo ""
$PYTHON_CMD configure.py --doctor
echo ""
echo "--------------------------------------------------------------------"
echo "Chạy kiểm thử tự động 27 bài test hệ thống:"
$PYTHON_CMD -m pytest
echo "--------------------------------------------------------------------"
echo ""
read -p "Nhấn Enter để đóng..."
