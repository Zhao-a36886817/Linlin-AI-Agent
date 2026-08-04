#Requires -Version 5.1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$BackendRoot = Join-Path $ProjectRoot "backend"

if ($env:CONDA_DEFAULT_ENV -ne "Linlin_agent") {
    throw "Activate the Linlin_agent Conda environment first."
}

Set-Location $BackendRoot

Write-Host ""
Write-Host "Running Ruff automatic fixes..." -ForegroundColor Cyan
python -m ruff check . --fix

if ($LASTEXITCODE -ne 0) {
    throw "Ruff check failed."
}

Write-Host ""
Write-Host "Formatting Python files..." -ForegroundColor Cyan
python -m ruff format .

if ($LASTEXITCODE -ne 0) {
    throw "Ruff format failed."
}

Write-Host ""
Write-Host "Running final Ruff check..." -ForegroundColor Cyan
python -m ruff check .

if ($LASTEXITCODE -ne 0) {
    throw "Final Ruff check failed."
}

Write-Host ""
Write-Host "Formatting completed." -ForegroundColor Green
