@echo off
chcp 65001 >nul
title 1. Cài Đặt Môi Trường - FB Auto Video Studio v3
cd /d "%~dp0"
echo ======================================================================
echo    FB AUTO VIDEO STUDIO PRO V3 - BƯỚC 1: CÀI ĐẶT MÔI TRƯỜNG
echo ======================================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [LỖI] Máy tính chưa cài đặt Python!
    echo Vui lòng cài đặt Python 3.10 trở lên từ https://www.python.org/
    echo Lưu ý: Hãy tích chọn ô "Add Python to PATH" khi cài đặt.
    echo.
    pause
    exit /b 1
)

echo [1/3] Đang nâng cấp pip...
python -m pip install --upgrade pip

echo [2/3] Đang cài đặt các thư viện cần thiết từ requirements.txt...
python -m pip install -r requirements.txt

echo.
echo [3/3] Đang chẩn đoán kiểm tra hệ thống...
python configure.py --doctor

echo.
echo ======================================================================
echo  ĐÃ HOÀN TẤT CÀI ĐẶT! BẠN CÓ THỂ MỞ '2_Chay_Ung_Dung.bat' ĐỂ SỬ DỤNG.
echo ======================================================================
echo.
pause
