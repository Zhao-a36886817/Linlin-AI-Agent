#Requires -Version 5.1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$EnvironmentName = "Linlin_agent"
$ProjectRoot = "F:\Linlin-Agent"
$BackendRoot = "$ProjectRoot\backend"
$PythonExe = "C:\Users\Zhao\Anaconda3\envs\Linlin_agent\python.exe"

if ($env:CONDA_DEFAULT_ENV -ne $EnvironmentName) {
    throw "目前不是 Linlin_agent 環境；請先執行 conda activate Linlin_agent。"
}

if (-not (Test-Path -LiteralPath "$BackendRoot\app\main.py" -PathType Leaf)) {
    throw "找不到後端入口：$BackendRoot\app\main.py"
}

# 使用絕對路徑鎖定 Python，避免 PATH 中其他環境搶先被執行。
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "找不到 Linlin_agent 的 Python：$PythonExe"
}

Set-Location $BackendRoot
$env:PYTHONPATH = $BackendRoot

Write-Host ""
Write-Host "Linlin Agent Backend" -ForegroundColor Cyan
Write-Host "API  : http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Docs : http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host ""

& $PythonExe -m uvicorn app.main:app `
    --host 127.0.0.1 `
    --port 8000 `
    --reload
