@echo off
chcp 65001 >nul
title Chẩn Đoán Hệ Thống - FB Auto Video Studio v3
cd /d "%~dp0"
set NO_PROXY=localhost,127.0.0.1
echo Đang kiểm tra toàn bộ cấu hình và tài nguyên hệ thống...
echo.
python configure.py --doctor
echo.
pause
