@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Linlin Agent - 安全停止

REM 只停止由 Linlin Agent 啟動器記錄的前端與後端程序，不會掃描或關閉其他程式。
set "LAUNCHER_PS1=F:\Linlin-Agent\tools\launcher\Linlin-Agent-Host.ps1"

if not exist "%LAUNCHER_PS1%" (
    echo [錯誤] 找不到啟動器：%LAUNCHER_PS1%
    pause
    exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER_PS1%" -Mode Stop
pause

