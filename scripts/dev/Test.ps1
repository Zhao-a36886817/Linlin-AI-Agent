#Requires -Version 5.1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$BackendRoot = Join-Path $ProjectRoot "backend"

if ($env:CONDA_DEFAULT_ENV -ne "Linlin_agent") {
    throw "Activate the Linlin_agent Conda environment first."
}

Set-Location $BackendRoot
$env:PYTHONPATH = $BackendRoot

Write-Host ""
Write-Host "Running backend tests..." -ForegroundColor Cyan
Write-Host ""

python -m pytest -v

if ($LASTEXITCODE -ne 0) {
    throw "Pytest failed."
}

Write-Host ""
Write-Host "Tests passed." -ForegroundColor Green
