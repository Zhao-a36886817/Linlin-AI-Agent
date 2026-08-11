@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Linlin Agent - 桌面版

REM 一鍵桌面入口：腳本會自行補齊鎖定依賴、啟動後端，關閉桌面視窗後再停止後端。
set "DESKTOP_PS1=F:\Linlin-Agent\scripts\start-desktop.ps1"

if not exist "%DESKTOP_PS1%" (
    echo [錯誤] 找不到桌面啟動器：%DESKTOP_PS1%
    pause
    exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%DESKTOP_PS1%"
set "RESULT=%ERRORLEVEL%"

if not "%RESULT%"=="0" (
    echo.
    echo [失敗] 桌面版未能正常啟動，請保留此畫面以便檢查。
    pause
)

exit /b %RESULT%
