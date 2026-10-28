@echo off
chcp 65001 >nul
title FB Auto Video Studio Pro v3
cd /d "%~dp0"
set NO_PROXY=localhost,127.0.0.1
start "" pythonw app.py
exit
