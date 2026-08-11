@echo off
setlocal EnableExtensions

REM Keep this launcher ASCII-only because cmd.exe may misread UTF-8 batch comments.
REM The PowerShell script is UTF-8 with BOM and displays the Traditional Chinese UI.
set "SCRIPT_DIR=%~dp0"
set "TEST_SCRIPT=%SCRIPT_DIR%Run-Linlin-Agent-Tests.ps1"

if not exist "%TEST_SCRIPT%" (
    echo ERROR: Test script was not found: %TEST_SCRIPT%
    pause
    exit /b 1
)

REM ExecutionPolicy Bypass applies only to this process and changes no permanent setting.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%TEST_SCRIPT%"
set "RESULT=%ERRORLEVEL%"

echo.
if "%RESULT%"=="0" (
    echo Linlin Agent Docker test menu closed.
) else (
    echo The last test did not pass. Exit code: %RESULT%
    echo The failure remains visible for review.
)

pause
exit /b %RESULT%
