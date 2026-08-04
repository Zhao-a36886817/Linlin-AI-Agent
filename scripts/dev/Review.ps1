#Requires -Version 5.1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$BackendRoot = Join-Path $ProjectRoot "backend"
$Failed = $false

if ($env:CONDA_DEFAULT_ENV -ne "Linlin_agent") {
    Write-Host "[FAIL] Wrong Conda environment." -ForegroundColor Red
    Write-Host "Current: $env:CONDA_DEFAULT_ENV"
    exit 1
}

Set-Location $BackendRoot
$env:PYTHONPATH = $BackendRoot

Write-Host ""
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host " Linlin Agent Project Review" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

Write-Host ""
Write-Host "[1/4] Ruff check" -ForegroundColor Cyan
python -m ruff check .

if ($LASTEXITCODE -ne 0) {
    $Failed = $true
}

Write-Host ""
Write-Host "[2/4] Python compile check" -ForegroundColor Cyan
python -m compileall app tests

if ($LASTEXITCODE -ne 0) {
    $Failed = $true
}

Write-Host ""
Write-Host "[3/4] Pytest" -ForegroundColor Cyan
python -m pytest -v

if ($LASTEXITCODE -ne 0) {
    $Failed = $true
}

Write-Host ""
Write-Host "[4/4] Git review" -ForegroundColor Cyan

git -C $ProjectRoot status --short

Write-Host ""
git -C $ProjectRoot diff --stat

Write-Host ""

if ($Failed) {
    Write-Host "REVIEW FAILED" -ForegroundColor Red
    Write-Host "Do not commit until the errors are fixed." -ForegroundColor Yellow
    exit 1
}

Write-Host "REVIEW PASSED" -ForegroundColor Green
Write-Host "The project is ready for manual code review." -ForegroundColor Green
Write-Host "No Git commit was created automatically." -ForegroundColor Yellow
