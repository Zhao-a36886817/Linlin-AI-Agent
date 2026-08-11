#Requires -Version 5.1

<#
.SYNOPSIS
    使用固定的 Linlin_agent 環境啟動 Linlin Agent Tauri 桌面版。

.DESCRIPTION
    此腳本會載入指定的 Node、pnpm、Rust 與 Visual Studio C++ 工具，並依
    pnpm-lock.yaml 補齊桌面依賴。Cargo 快取放在 Conda 環境內，避開 F 槽
    exFAT 無法保存 crates 時間戳的限制；專案原始碼與編譯輸出仍留在 F 槽。
#>

[CmdletBinding()]
param(
    # 維護驗證模式只還原依賴並執行 cargo check，不開啟持續執行的桌面視窗。
    [switch]$CheckOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = "F:\Linlin-Agent"
$BackendRoot = Join-Path $ProjectRoot "backend"
$DesktopRoot = Join-Path $ProjectRoot "desktop"
$CondaRoot = "C:\Users\Zhao\Anaconda3\envs\Linlin_agent"
$PythonExe = Join-Path $CondaRoot "python.exe"
$PnpmCmd = Join-Path $CondaRoot "Library\bin\pnpm.bat"
$CargoExe = Join-Path $CondaRoot "Library\bin\cargo.exe"
$VsWhere = "C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
$RuntimeRoot = Join-Path $ProjectRoot "tools\launcher\runtime"
$DesktopLogRoot = Join-Path $RuntimeRoot "desktop-logs"
$ProjectDataRoot = Join-Path $RuntimeRoot "project-data"
$BackendHealthUrl = "http://127.0.0.1:8000/api/health"

foreach ($requiredFile in @($PythonExe, $PnpmCmd, $CargoExe, $VsWhere)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "桌面版缺少必要工具：$requiredFile"
    }
}

# 直接把指定環境放到 PATH 前端，不依賴目前視窗是否執行過 conda init。
$environmentPaths = @(
    $CondaRoot,
    (Join-Path $CondaRoot "Scripts"),
    (Join-Path $CondaRoot "Library\bin")
)
$env:PATH = (($environmentPaths + @($env:PATH)) -join [IO.Path]::PathSeparator)
$env:CONDA_PREFIX = $CondaRoot
$env:CONDA_DEFAULT_ENV = "Linlin_agent"

# 後端所有可變資料仍集中到 launcher runtime，不在正式原始碼目錄散落。
$env:WORKSPACE_ROOT = Join-Path $ProjectDataRoot "workspace"
$env:OUTPUT_ROOT = Join-Path $ProjectDataRoot "outputs"
$env:TRAINING_OUTPUT_ROOT = Join-Path $ProjectDataRoot "outputs\training"
$env:LOG_ROOT = Join-Path $ProjectDataRoot "logs"
$env:DATA_ROOT = Join-Path $ProjectDataRoot "data"
$env:TRAINING_MODEL_ROOT = Join-Path $ProjectRoot "models"

# crates 解壓需要 NTFS 時間戳能力；F: 是 exFAT，因此快取固定留在環境內。
$env:CARGO_HOME = Join-Path $CondaRoot ".cargo"

# 同時支援正式版與預覽版 Visual Studio，並要求完整的 x64 C++ 工具鏈。
$VsInstallPath = & $VsWhere -latest -prerelease -products "*" -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $VsInstallPath) {
    throw "找不到含 C++ Build Tools 的 Visual Studio，無法編譯 Tauri。"
}

$DevShellModule = Join-Path $VsInstallPath "Common7\Tools\Microsoft.VisualStudio.DevShell.dll"
Import-Module $DevShellModule
Enter-VsDevShell -VsInstallPath $VsInstallPath -SkipAutomaticLocation -DevCmdArguments "-arch=x64 -host_arch=x64" | Out-Null

Set-Location $DesktopRoot

# frozen-lockfile 可防止安裝時悄悄改寫版本；hoisted 佈局已由 workspace 設定處理。
& $PnpmCmd install --frozen-lockfile
if ($LASTEXITCODE -ne 0) {
    throw "桌面版 Node 套件還原失敗（結束代碼：$LASTEXITCODE）。"
}

if ($CheckOnly) {
    Write-Host "正在檢查 Tauri Rust 專案..." -ForegroundColor Cyan
    & $CargoExe check --manifest-path (Join-Path $DesktopRoot "src-tauri\Cargo.toml") --locked
    if ($LASTEXITCODE -ne 0) {
        throw "Tauri Cargo 檢查失敗（結束代碼：$LASTEXITCODE）。"
    }
    Write-Host "桌面版環境檢查通過。" -ForegroundColor Green
    return
}

function Test-BackendHealth {
    try {
        $response = Invoke-WebRequest -Uri $BackendHealthUrl -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

$OwnedBackend = $null
try {
    if (-not (Test-BackendHealth)) {
        New-Item -ItemType Directory -Path $DesktopLogRoot -Force | Out-Null
        New-Item -ItemType Directory -Path $env:WORKSPACE_ROOT, $env:OUTPUT_ROOT, $env:TRAINING_OUTPUT_ROOT, $env:LOG_ROOT, $env:DATA_ROOT -Force | Out-Null

        Write-Host "正在啟動桌面版專用後端..." -ForegroundColor Cyan
        $OwnedBackend = Start-Process -FilePath $PythonExe -ArgumentList @(
            "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1",
            "--port", "8000"
        ) -WorkingDirectory $BackendRoot -RedirectStandardOutput (Join-Path $DesktopLogRoot "backend.out.log") -RedirectStandardError (Join-Path $DesktopLogRoot "backend.err.log") -WindowStyle Hidden -PassThru

        $deadline = [DateTime]::UtcNow.AddSeconds(90)
        while (-not (Test-BackendHealth)) {
            if ($OwnedBackend.HasExited) {
                throw "桌面版後端在完成啟動前已結束（代碼：$($OwnedBackend.ExitCode)）。"
            }
            if ([DateTime]::UtcNow -ge $deadline) {
                throw "等待桌面版後端逾時：$BackendHealthUrl"
            }
            Start-Sleep -Milliseconds 500
        }
    }

    Write-Host "正在啟動 Linlin Agent 桌面版..." -ForegroundColor Cyan
    & $PnpmCmd tauri dev
    if ($LASTEXITCODE -ne 0) {
        throw "Tauri 桌面版結束代碼：$LASTEXITCODE"
    }
}
finally {
    # 只停止由本腳本建立的後端；若原本已有後端，完全不碰既有程序。
    if ($null -ne $OwnedBackend -and -not $OwnedBackend.HasExited) {
        Stop-Process -Id $OwnedBackend.Id -Force -ErrorAction SilentlyContinue
        Write-Host "已停止桌面版專用後端。" -ForegroundColor DarkGray
    }
}
