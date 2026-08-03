#Requires -Version 5.1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$EnvironmentName = "Linlin_agent"
$ProjectRoot = "C:\Linlin-Agent"
$BackendRoot = "$ProjectRoot\backend"

if ($env:CONDA_DEFAULT_ENV -ne $EnvironmentName) {
    throw "隢??瑁?嚗onda activate Linlin_agent"
}

if (-not (Test-Path "$BackendRoot\app\main.py")) {
    throw "?曆???backend\app\main.py"
}

Set-Location $BackendRoot
$env:PYTHONPATH = $BackendRoot

Write-Host ""
Write-Host "Linlin Agent Backend" -ForegroundColor Cyan
Write-Host "API  : http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Docs : http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host ""

python -m uvicorn app.main:app `
    --host 127.0.0.1 `
    --port 8000 `
    --reload
