#Requires -Version 5.1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$BackendRoot = Join-Path $ProjectRoot "backend"
$ExpectedEnvironment = "Linlin_agent"

function Write-Check {
    param(
        [Parameter(Mandatory)]
        [string]$Name,

        [Parameter(Mandatory)]
        [bool]$Passed,

        [string]$Detail = ""
    )

    if ($Passed) {
        Write-Host "[OK]   $Name" -ForegroundColor Green -NoNewline
    }
    else {
        Write-Host "[FAIL] $Name" -ForegroundColor Red -NoNewline
    }

    if ($Detail) {
        Write-Host " - $Detail"
    }
    else {
        Write-Host ""
    }
}

function Test-CommandAvailable {
    param(
        [Parameter(Mandatory)]
        [string]$Name
    )

    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

Write-Host ""
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host " Linlin Agent Environment Doctor" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host ""

Write-Check `
    -Name "Conda environment" `
    -Passed ($env:CONDA_DEFAULT_ENV -eq $ExpectedEnvironment) `
    -Detail "Current: $env:CONDA_DEFAULT_ENV"

foreach ($Command in @(
    "python",
    "git",
    "node",
    "npm",
    "pnpm",
    "rustc",
    "cargo",
    "ollama"
)) {
    $Exists = Test-CommandAvailable $Command
    $Detail = ""

    if ($Exists) {
        try {
            switch ($Command) {
                "python" {
                    $Detail = python --version
                }

                "git" {
                    $Detail = git --version
                }

                "node" {
                    $Detail = node --version
                }

                "npm" {
                    $Detail = npm --version
                }

                "pnpm" {
                    $Detail = pnpm --version
                }

                "rustc" {
                    $Detail = rustc --version
                }

                "cargo" {
                    $Detail = cargo --version
                }

                "ollama" {
                    $Detail = ollama --version
                }
            }
        }
        catch {
            $Detail = "Version check failed"
        }
    }

    Write-Check `
        -Name $Command `
        -Passed $Exists `
        -Detail $Detail
}

Write-Host ""
Write-Host "Python modules" -ForegroundColor Cyan

foreach ($Module in @(
    "fastapi",
    "uvicorn",
    "httpx",
    "pydantic",
    "structlog",
    "psutil"
)) {
    python -c "import $Module" 2>$null
    Write-Check `
        -Name $Module `
        -Passed ($LASTEXITCODE -eq 0)
}

Write-Host ""
Write-Host "Project files" -ForegroundColor Cyan

foreach ($Path in @(
    "$BackendRoot\app\main.py",
    "$BackendRoot\app\providers\manager.py",
    "$BackendRoot\app\providers\factory.py",
    "$BackendRoot\app\providers\cache.py",
    "$BackendRoot\app\providers\adapters\ollama.py",
    "$BackendRoot\app\api\routes\models.py"
)) {
    Write-Check `
        -Name $Path.Replace("$ProjectRoot\", "") `
        -Passed (Test-Path $Path)
}

Write-Host ""
Write-Host "Services" -ForegroundColor Cyan

try {
    $OllamaResponse = Invoke-RestMethod `
        -Uri "http://127.0.0.1:11434/api/tags" `
        -TimeoutSec 3

    $ModelCount = @($OllamaResponse.models).Count

    Write-Check `
        -Name "Ollama API" `
        -Passed $true `
        -Detail "$ModelCount local models"
}
catch {
    Write-Check `
        -Name "Ollama API" `
        -Passed $false `
        -Detail "http://127.0.0.1:11434"
}

try {
    $BackendResponse = Invoke-RestMethod `
        -Uri "http://127.0.0.1:8000/api/health" `
        -TimeoutSec 3

    Write-Check `
        -Name "FastAPI Backend" `
        -Passed ($BackendResponse.status -eq "healthy") `
        -Detail "http://127.0.0.1:8000"
}
catch {
    Write-Check `
        -Name "FastAPI Backend" `
        -Passed $false `
        -Detail "Not running"
}

Write-Host ""
