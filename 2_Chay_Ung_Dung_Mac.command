#!/bin/bash
# ==============================================================================
# FB AUTO VIDEO STUDIO PRO V3 — KHỞI ĐỘNG STUDIO TRÊN MACOS (MACBOOK)
# ==============================================================================
cd "$(dirname "$0")"

export NO_PROXY="localhost,127.0.0.1"

if [ -d ".venv" ]; then
    source .venv/bin/activate
    PYTHON_CMD="python"
elif command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "[LỖI] Không tìm thấy Python! Vui lòng chạy 1_Cai_Dat_Moi_Truong_Mac.command trước."
    read -p "Nhấn Enter để đóng..."
    exit 1
fi

echo "===================================================================="
echo "       ĐANG KHỞI ĐỘNG FB AUTO VIDEO STUDIO PRO V3 TRÊN MACOS..."
echo "===================================================================="
$PYTHON_CMD app.py
