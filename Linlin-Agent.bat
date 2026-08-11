@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
title Linlin Agent - 一鍵啟動

REM 這是正式專案的一鍵入口；詳細環境與套件檢查集中放在 tools\launcher。
set "LAUNCHER_PS1=F:\Linlin-Agent\tools\launcher\Linlin-Agent-Host.ps1"
set "COMMAND_LAUNCHER_PS1=F:\Linlin-Agent\scripts\windows_launcher.ps1"

echo ============================================================
echo                 Linlin Agent 一鍵啟動
echo ============================================================
echo 專案：F:\Linlin-Agent
echo 環境：%USERPROFILE%\Anaconda3\envs\Linlin_agent
echo.
echo 將自動檢查環境與必要套件，完成後直接開啟操作畫面。
echo.

REM 有命令參數時保留既有 install、verify、smoke 等維護介面；無參數時才是
REM 使用者指定的一鍵 Run。PowerShell 端有 ValidateSet，未知命令會安全拒絕。
if not "%~1"=="" (
    if not exist "%COMMAND_LAUNCHER_PS1%" (
        echo [錯誤] 找不到命令啟動器：%COMMAND_LAUNCHER_PS1%
        pause
        exit /b 1
    )
    powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%COMMAND_LAUNCHER_PS1%" -Command "%~1"
    exit /b !ERRORLEVEL!
)

if not exist "%LAUNCHER_PS1%" (
    echo [錯誤] 找不到啟動器：%LAUNCHER_PS1%
    echo 請確認 F:\Linlin-Agent\tools\launcher 資料夾仍然存在。
    pause
    exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER_PS1%" -Mode Run
set "RESULT=%ERRORLEVEL%"

if not "%RESULT%"=="0" (
    echo.
    echo [失敗] Linlin Agent 未能正常啟動，請保留此畫面以便檢查。
    pause
)

exit /b %RESULT%
