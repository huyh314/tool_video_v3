@echo off
chcp 65001 >nul
title Đẩy Mã Nguồn Lên GitHub - FB Auto Video Studio v3
cd /d "%~dp0"
echo ========================================================
echo       ĐẨY MÃ NGUỒN LÊN GITHUB (FB AUTO VIDEO STUDIO V3)
echo ========================================================
echo.
echo Bước 1: Kiểm tra kết nối Git...
git status
echo.
set /p REPO_URL="Nhập đường dẫn GitHub Repository của bạn (VD: https://github.com/huyh314/tool_video_v3.git): "
if "%REPO_URL%"=="" (
    echo [LỖI] Bạn chưa nhập link GitHub!
    pause
    exit /b
)

git remote remove origin 2>nul
git remote add origin %REPO_URL%
git branch -M main

echo.
echo Bước 2: Đang đẩy code lên GitHub...
git push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo  THÀNH CÔNG! Dự án đã được đưa lên GitHub.
    echo  Người khác có thể clone về bằng lệnh:
    echo  git clone %REPO_URL%
    echo ========================================================
) else (
    echo.
    echo [CHÚ Ý] Nếu bị lỗi xác thực quyền, bạn hãy mở Terminal và gõ:
    echo         gh auth login
    echo Hoặc đăng nhập bằng Personal Access Token của GitHub.
)
echo.
pause
