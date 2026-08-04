#Requires -Version 5.1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Write-Host ""
Write-Host "Cleaning Linlin Agent caches..." -ForegroundColor Cyan

$Directories = Get-ChildItem `
    -Path $ProjectRoot `
    -Directory `
    -Recurse `
    -Force `
    -ErrorAction SilentlyContinue |
Where-Object {
    $_.Name -in @(
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache"
    )
}

foreach ($Directory in $Directories) {
    Write-Host "Removing $($Directory.FullName)"
    Remove-Item `
        -Path $Directory.FullName `
        -Recurse `
        -Force `
        -ErrorAction SilentlyContinue
}

$PyCacheFiles = Get-ChildItem `
    -Path $ProjectRoot `
    -File `
    -Recurse `
    -Include "*.pyc", "*.pyo" `
    -ErrorAction SilentlyContinue

foreach ($File in $PyCacheFiles) {
    Remove-Item `
        -Path $File.FullName `
        -Force `
        -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Cache cleanup completed." -ForegroundColor Green
