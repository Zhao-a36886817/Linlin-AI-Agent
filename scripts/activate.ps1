#Requires -Version 5.1

$ErrorActionPreference = "Stop"

$EnvironmentName = "LinlinAgent"
$ProjectRoot = "C:\Linlin-Agent"

if (-not (Get-Command conda -ErrorAction SilentlyContinue)) {
    throw "Conda is not available. Open Anaconda PowerShell Prompt."
}

conda activate $EnvironmentName

Set-Location $ProjectRoot

$env:LINLIN_PROJECT_ROOT = $ProjectRoot
$env:PYTHONPATH = "$ProjectRoot\backend"

Write-Host ""
Write-Host "Linlin Agent environment activated" -ForegroundColor Green
Write-Host "Conda environment : $env:CONDA_DEFAULT_ENV"
Write-Host "Project location  : $ProjectRoot"
Write-Host "Python            : $(python --version)"
Write-Host "Node.js           : $(node --version)"
Write-Host "pnpm              : $(pnpm --version)"
Write-Host ""
