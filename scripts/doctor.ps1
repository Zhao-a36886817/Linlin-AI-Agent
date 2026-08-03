#Requires -Version 5.1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

function Test-Tool {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][scriptblock]$VersionCommand
    )

    if (Get-Command $Name -ErrorAction SilentlyContinue) {
        try {
            $version = & $VersionCommand
            Write-Host "[OK] $Name - $version" -ForegroundColor Green
        }
        catch {
            Write-Host "[WARN] $Name exists but version check failed" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "[FAIL] $Name not found" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Linlin Agent Environment Doctor"
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Conda environment: $env:CONDA_DEFAULT_ENV"
Write-Host ""

Test-Tool "conda"  { conda --version }
Test-Tool "python" { python --version }
Test-Tool "pip"    { python -m pip --version }
Test-Tool "node"   { node --version }
Test-Tool "npm"    { npm --version }
Test-Tool "pnpm"   { pnpm --version }
Test-Tool "rustc"  { rustc --version }
Test-Tool "cargo"  { cargo --version }
Test-Tool "git"    { git --version }
Test-Tool "ffmpeg" { ffmpeg -version | Select-Object -First 1 }
Test-Tool "docker" { docker --version }

Write-Host ""

if ($env:CONDA_DEFAULT_ENV -eq "LinlinAgent") {
    Write-Host "[OK] Correct Conda environment activated" -ForegroundColor Green
}
else {
    Write-Host "[FAIL] Activate LinlinAgent environment first" -ForegroundColor Red
}

$requiredModules = @(
    "fastapi",
    "uvicorn",
    "pydantic",
    "httpx",
    "openai",
    "anthropic"
)

foreach ($module in $requiredModules) {
    python -c "import $module" 2>$null

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Python module: $module" -ForegroundColor Green
    }
    else {
        Write-Host "[FAIL] Python module: $module" -ForegroundColor Red
    }
}

$ports = @(8000, 1420)

foreach ($port in $ports) {
    $connection = Get-NetTCPConnection `
        -LocalPort $port `
        -ErrorAction SilentlyContinue

    if ($connection) {
        Write-Host "[WARN] Port $port is currently in use" -ForegroundColor Yellow
    }
    else {
        Write-Host "[OK] Port $port is available" -ForegroundColor Green
    }
}

Write-Host ""
