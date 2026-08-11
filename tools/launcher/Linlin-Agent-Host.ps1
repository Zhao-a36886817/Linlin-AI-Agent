<#
.SYNOPSIS
    Linlin Agent 的 Windows 主機啟動器。

.DESCRIPTION
    這支腳本刻意放在正式專案資料夾之外，避免為了方便啟動而改動
    F:\Linlin-Agent 內的核心功能程式碼。整理後啟動工具集中放在
    F:\Linlin-Agent\tools\launcher，並固定使用使用者指定的 Conda 環境：
    C:\Users\Zhao\Anaconda3\envs\Linlin_agent。

    支援模式：
      Run      建置前端、啟動後端與前端，並開啟獨立的瀏覽器視窗。
      Terminal 開啟已設定好環境的 PowerShell，提示字元固定從 F:\ 開始。
      Stop     安全停止由本啟動器記錄的後端與前端程序。
      Smoke    自動啟動、檢查兩個服務後立即停止，供維護驗證使用。

    執行時產生的記錄、程序狀態與使用者資料都集中在：
    F:\Linlin-Agent\tools\launcher\runtime
#>

[CmdletBinding()]
param(
    [ValidateSet("Run", "Terminal", "Stop", "Smoke")]
    [string]$Mode = "Run"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# -----------------------------------------------------------------------------
# 固定路徑：環境路徑依使用者本次更正，專案與執行資料一律留在 F 槽。
# -----------------------------------------------------------------------------
$ProjectRoot = "F:\Linlin-Agent"
$BackendRoot = Join-Path $ProjectRoot "backend"
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$CondaRoot = "C:\Users\Zhao\Anaconda3\envs\Linlin_agent"
$CondaExe = "C:\Users\Zhao\Anaconda3\Scripts\conda.exe"
$EnvironmentFile = Join-Path $ProjectRoot "environment.yml"
$PythonExe = Join-Path $CondaRoot "python.exe"
$NodeExe = Join-Path $CondaRoot "node.exe"
$NpmCmd = Join-Path $CondaRoot "npm.cmd"
# conda-forge 的 Windows pnpm 入口位於 Library\bin，而不是環境根目錄。
$PnpmCmd = Join-Path $CondaRoot "Library\bin\pnpm.bat"

$LauncherRoot = "F:\Linlin-Agent\tools\launcher"
$RuntimeRoot = Join-Path $LauncherRoot "runtime"
$LogRoot = Join-Path $RuntimeRoot "logs"
$StatePath = Join-Path $RuntimeRoot "session.json"
$ProjectDataRoot = Join-Path $RuntimeRoot "project-data"
$FrontendDist = Join-Path $RuntimeRoot "frontend-dist"

$BackendUrl = "http://127.0.0.1:8000"
$FrontendUrl = "http://127.0.0.1:5173"

function Write-Heading {
    param([Parameter(Mandatory)][string]$Text)

    Write-Host ""
    Write-Host $Text -ForegroundColor Cyan
}

function Assert-File {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Description
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "找不到$Description：$Path"
    }
}

function Initialize-Directories {
    # 所有可變資料都放在外部 runtime，正式專案原始碼不會被啟動器改寫。
    $directories = @(
        $RuntimeRoot,
        $LogRoot,
        (Join-Path $ProjectDataRoot "workspace"),
        (Join-Path $ProjectDataRoot "outputs"),
        (Join-Path $ProjectDataRoot "outputs\training"),
        (Join-Path $ProjectDataRoot "logs"),
        (Join-Path $ProjectDataRoot "data"),
        $FrontendDist,
        (Join-Path $RuntimeRoot "browser-profile")
    )

    foreach ($directory in $directories) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }
}

function Enable-LinlinEnvironment {
    # 不依賴目前 PowerShell 是否已執行 conda init；直接把指定環境放到 PATH
    # 最前面，因此 python、node 與 npm 都會確定來自 Linlin_agent。
    $environmentPaths = @(
        $CondaRoot,
        (Join-Path $CondaRoot "Scripts"),
        (Join-Path $CondaRoot "Library\bin"),
        (Join-Path $CondaRoot "Library\usr\bin"),
        (Join-Path $CondaRoot "Library\mingw-w64\bin")
    )

    $env:PATH = (($environmentPaths + @($env:PATH)) -join [IO.Path]::PathSeparator)
    $env:CONDA_PREFIX = $CondaRoot
    $env:CONDA_DEFAULT_ENV = "Linlin_agent"
    $env:CONDA_PROMPT_MODIFIER = "(Linlin-Agent) "
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
}

function Assert-ProjectFiles {
    Assert-File -Path (Join-Path $BackendRoot "app\main.py") -Description "後端入口"
    Assert-File -Path (Join-Path $FrontendRoot "package.json") -Description "前端設定"
    Assert-File -Path $EnvironmentFile -Description "Conda 環境設定"
}

function Ensure-LinlinEnvironment {
    # 對照 environment.yml 檢查主要工具。全部存在時只需數個本機檔案檢查；
    # 任一工具遺失才呼叫 Conda 補齊，避免每次啟動都重新解析所有套件。
    $environmentTools = @(
        $PythonExe,
        $NodeExe,
        $NpmCmd,
        # 桌面版依 pnpm-lock.yaml 還原套件，因此 pnpm 也是正式環境工具。
        $PnpmCmd,
        (Join-Path $CondaRoot "Library\bin\ffmpeg.exe"),
        (Join-Path $CondaRoot "Library\bin\openssl.exe"),
        (Join-Path $CondaRoot "Library\bin\pkg-config.exe"),
        (Join-Path $CondaRoot "Library\bin\rustc.exe"),
        (Join-Path $CondaRoot "Library\bin\cargo.exe"),
        (Join-Path $CondaRoot "Library\bin\cmake.exe"),
        (Join-Path $CondaRoot "Library\bin\ninja.exe"),
        (Join-Path $CondaRoot "Library\bin\git.exe"),
        (Join-Path $CondaRoot "Library\bin\sqlite3.exe")
    )
    $missingTools = @($environmentTools | Where-Object {
        -not (Test-Path -LiteralPath $_ -PathType Leaf)
    })

    if ($missingTools.Count -eq 0) {
        Write-Host "指定環境：已就緒（Linlin_agent）" -ForegroundColor Green
        return
    }

    Assert-File -Path $CondaExe -Description "Anaconda 的 conda.exe"
    Assert-File -Path $EnvironmentFile -Description "專案 environment.yml"
    Write-Heading "環境元件不完整，正在自動建立或補齊 Linlin_agent..."

    if (Test-Path -LiteralPath $CondaRoot -PathType Container) {
        & $CondaExe env update --prefix $CondaRoot --file $EnvironmentFile
    }
    else {
        & $CondaExe env create --prefix $CondaRoot --file $EnvironmentFile
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Conda 環境建立或更新失敗（結束代碼：$LASTEXITCODE）。"
    }

    $stillMissing = @($environmentTools | Where-Object {
        -not (Test-Path -LiteralPath $_ -PathType Leaf)
    })
    if ($stillMissing.Count -gt 0) {
        throw "環境更新後仍缺少工具：$($stillMissing -join ', ')"
    }
}

function Ensure-AppDependencies {
    # 後端先以匯入測試判斷必要套件是否齊全；只有失敗時才執行 pip。
    Write-Heading "正在檢查專案套件..."
    & $PythonExe -c "import fastapi, uvicorn, orjson, pydantic, pydantic_settings, httpx, cryptography, psutil, sse_starlette" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "後端套件不完整，正在自動安裝..." -ForegroundColor Yellow
        & $PythonExe -m pip install -e $BackendRoot
        if ($LASTEXITCODE -ne 0) {
            throw "後端套件安裝失敗（結束代碼：$LASTEXITCODE）。"
        }
    }
    else {
        Write-Host "後端套件：已就緒" -ForegroundColor Green
    }

    # 使用者已確認會使用主機測試與本機 LoRA；只做模組存在性檢查，避免每次
    # 啟動都載入大型 Torch。任一模組缺少時，依 pyproject.toml 的固定版本補齊。
    & $PythonExe -c "import importlib.util; names=('yaml','pytest','pytest_asyncio','pytest_cov','ruff','accelerate','numpy','peft','sentencepiece','torch','transformers'); raise SystemExit(any(importlib.util.find_spec(name) is None for name in names))" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "測試或本機 LoRA 套件不完整，正在依固定版本補齊..." -ForegroundColor Yellow
        $backendExtras = "${BackendRoot}[dev,training]"
        & $PythonExe -m pip install -e $backendExtras
        if ($LASTEXITCODE -ne 0) {
            throw "測試或本機 LoRA 套件安裝失敗（結束代碼：$LASTEXITCODE）。"
        }
    }
    else {
        Write-Host "測試與本機 LoRA 套件：已就緒" -ForegroundColor Green
    }

    # package-lock.json 是專案鎖定的版本來源；缺少 Vite 或 TypeScript 時使用
    # npm ci 完整還原，避免安裝到任意的最新版。
    $vite = Join-Path $FrontendRoot "node_modules\vite\bin\vite.js"
    $typescript = Join-Path $FrontendRoot "node_modules\typescript\bin\tsc"
    if (-not (Test-Path -LiteralPath $vite -PathType Leaf) -or
        -not (Test-Path -LiteralPath $typescript -PathType Leaf)) {
        Write-Host "前端套件不完整，正在依 package-lock.json 自動安裝..." -ForegroundColor Yellow
        Push-Location $FrontendRoot
        try {
            & $NpmCmd ci
            if ($LASTEXITCODE -ne 0) {
                throw "前端套件安裝失敗（結束代碼：$LASTEXITCODE）。"
            }
        }
        finally {
            Pop-Location
        }
    }
    else {
        Write-Host "前端套件：已就緒" -ForegroundColor Green
    }

    Assert-File -Path $vite -Description "前端 Vite 執行檔"
}

function Test-LocalUrl {
    param([Parameter(Mandatory)][string]$Url)

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    }
    catch {
        return $false
    }
}

function Wait-LocalUrl {
    param(
        [Parameter(Mandatory)][string]$Url,
        [Parameter(Mandatory)][System.Diagnostics.Process]$Process,
        [int]$TimeoutSeconds = 60
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($Process.HasExited) {
            throw "服務在完成啟動前已結束（結束代碼：$($Process.ExitCode)）。"
        }
        if (Test-LocalUrl -Url $Url) {
            return
        }
        Start-Sleep -Milliseconds 500
    }

    throw "等待服務逾時：$Url"
}

function Get-ProcessRecord {
    param([Parameter(Mandatory)][System.Diagnostics.Process]$Process)

    # 同時記錄 PID 與開始時間，可避免 Windows 日後重複使用 PID 時誤停別的程式。
    return [ordered]@{
        pid = $Process.Id
        start_time_utc = $Process.StartTime.ToUniversalTime().ToString("o")
    }
}

function Stop-RecordedProcess {
    param(
        [Parameter(Mandatory)]$Record,
        [Parameter(Mandatory)][string]$Name
    )

    if ($null -eq $Record -or $null -eq $Record.pid -or $null -eq $Record.start_time_utc) {
        return
    }

    $process = Get-Process -Id ([int]$Record.pid) -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        return
    }

    $actualStart = $process.StartTime.ToUniversalTime()
    $recordedStart = [DateTime]::Parse([string]$Record.start_time_utc).ToUniversalTime()
    if ([Math]::Abs(($actualStart - $recordedStart).TotalSeconds) -gt 1) {
        Write-Warning "$Name 的 PID 已被其他程式使用，因此未停止該程序。"
        return
    }

    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    Write-Host "已停止：$Name" -ForegroundColor DarkGray
}

function Stop-RecordedSession {
    if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
        Write-Host "目前沒有由啟動器記錄的執行中服務。" -ForegroundColor Yellow
        return
    }

    try {
        $state = Get-Content -LiteralPath $StatePath -Raw -Encoding UTF8 | ConvertFrom-Json
        # 先停前端再停後端，讓畫面不會繼續送出新的 API 要求。
        Stop-RecordedProcess -Record $state.frontend -Name "Linlin Agent 前端"
        Stop-RecordedProcess -Record $state.backend -Name "Linlin Agent 後端"
    }
    finally {
        Remove-Item -LiteralPath $StatePath -Force -ErrorAction SilentlyContinue
    }
}

function Assert-PortsAvailable {
    $occupied = @()
    foreach ($url in @($BackendUrl, $FrontendUrl)) {
        if (Test-LocalUrl -Url $url) {
            $occupied += $url
        }
    }

    if ($occupied.Count -gt 0) {
        throw "啟動所需網址已被其他程式使用：$($occupied -join ', ')。請先點兩下 F:\Linlin-Agent\tools\launcher\Linlin-Agent-Stop.bat，再重新啟動。"
    }
}

function Build-Frontend {
    Write-Heading "正在準備 Linlin Agent 畫面..."

    # 前端在建置時把 API 位址固定為本機後端；這樣使用 preview 模式時不需要
    # 額外代理設定，瀏覽器會直接連到 127.0.0.1:8000。
    $previousApiUrl = $env:VITE_API_BASE_URL
    $viteScript = Join-Path $FrontendRoot "node_modules\vite\bin\vite.js"
    $env:VITE_API_BASE_URL = "$BackendUrl/api"
    try {
        Push-Location $FrontendRoot
        try {
            # 只呼叫 Vite 建置畫面，產物明確寫到外部 runtime；正式專案內不會
            # 新增 dist。完整型別與 lint 檢查已由 Docker 測試流程負責。
            & $NodeExe $viteScript build --outDir $FrontendDist --emptyOutDir
            if ($LASTEXITCODE -ne 0) {
                throw "前端建置失敗（結束代碼：$LASTEXITCODE）。"
            }
        }
        finally {
            Pop-Location
        }
    }
    finally {
        $env:VITE_API_BASE_URL = $previousApiUrl
    }
}

function Start-LinlinServices {
    Initialize-Directories
    Assert-ProjectFiles
    Ensure-LinlinEnvironment
    Enable-LinlinEnvironment
    Ensure-AppDependencies
    Stop-RecordedSession
    Assert-PortsAvailable
    Build-Frontend

    # 後端的可變資料導向外部 runtime；模型仍讀取正式專案 models 資料夾。
    $env:WORKSPACE_ROOT = Join-Path $ProjectDataRoot "workspace"
    $env:OUTPUT_ROOT = Join-Path $ProjectDataRoot "outputs"
    $env:TRAINING_OUTPUT_ROOT = Join-Path $ProjectDataRoot "outputs\training"
    $env:LOG_ROOT = Join-Path $ProjectDataRoot "logs"
    $env:DATA_ROOT = Join-Path $ProjectDataRoot "data"
    $env:TRAINING_MODEL_ROOT = Join-Path $ProjectRoot "models"

    $backendOut = Join-Path $LogRoot "backend.out.log"
    $backendErr = Join-Path $LogRoot "backend.err.log"
    $frontendOut = Join-Path $LogRoot "frontend.out.log"
    $frontendErr = Join-Path $LogRoot "frontend.err.log"

    Write-Heading "正在啟動後端..."
    $backend = Start-Process -FilePath $PythonExe `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $BackendRoot `
        -RedirectStandardOutput $backendOut `
        -RedirectStandardError $backendErr `
        -PassThru `
        -WindowStyle Hidden

    try {
        Wait-LocalUrl -Url "$BackendUrl/api/health" -Process $backend -TimeoutSeconds 90

        Write-Heading "正在啟動操作畫面..."
        $viteScript = Join-Path $FrontendRoot "node_modules\vite\bin\vite.js"
        $frontend = $null
        $frontend = Start-Process -FilePath $NodeExe `
            -ArgumentList @($viteScript, "preview", "--outDir", $FrontendDist, "--host", "127.0.0.1", "--port", "5173", "--strictPort") `
            -WorkingDirectory $FrontendRoot `
            -RedirectStandardOutput $frontendOut `
            -RedirectStandardError $frontendErr `
            -PassThru `
            -WindowStyle Hidden

        try {
            Wait-LocalUrl -Url $FrontendUrl -Process $frontend -TimeoutSeconds 60

            $state = [ordered]@{
                created_at_utc = [DateTime]::UtcNow.ToString("o")
                environment = $CondaRoot
                project = $ProjectRoot
                backend = Get-ProcessRecord -Process $backend
                frontend = Get-ProcessRecord -Process $frontend
            }
            $state | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $StatePath -Encoding UTF8

            return [pscustomobject]@{
                Backend = $backend
                Frontend = $frontend
            }
        }
        catch {
            if ($null -ne $frontend -and -not $frontend.HasExited) {
                Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue
            }
            throw
        }
    }
    catch {
        if (-not $backend.HasExited) {
            Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
        }
        throw
    }
}

function Open-LinlinBrowser {
    # 優先用 Edge/Chrome 的應用程式視窗；若找不到則交給 Windows 預設瀏覽器。
    $browserCandidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe"),
        (Join-Path $env:ProgramFiles "Microsoft\Edge\Application\msedge.exe"),
        (Join-Path $env:LOCALAPPDATA "Microsoft\Edge\Application\msedge.exe"),
        (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe")
    )

    $browser = $browserCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    if ($null -ne $browser) {
        $profile = Join-Path $RuntimeRoot "browser-profile"
        Start-Process -FilePath $browser -ArgumentList @("--app=$FrontendUrl", "--user-data-dir=$profile") | Out-Null
    }
    else {
        Start-Process $FrontendUrl | Out-Null
    }
}

function Enter-LinlinTerminal {
    Initialize-Directories
    Assert-ProjectFiles
    Ensure-LinlinEnvironment
    Enable-LinlinEnvironment
    Set-Location "F:\"
    $host.UI.RawUI.WindowTitle = "Linlin Agent - Linlin_agent environment"

    # 此提示字元是使用者指定的固定顯示；實際使用的環境仍是 Linlin_agent。
    function global:prompt {
        return "(Linlin_agent) PS $((Get-Location).Path)> "
    }

    Write-Host "Linlin Agent 專案終端機已就緒。" -ForegroundColor Green
    Write-Host "環境：$CondaRoot"
    Write-Host "專案：$ProjectRoot"
    Write-Host "要啟動專案時，直接點兩下 F:\Linlin-Agent\Linlin-Agent.bat 即可。"
    Write-Host ""
}

try {
    switch ($Mode) {
        "Terminal" {
            Enter-LinlinTerminal
        }
        "Stop" {
            Write-Heading "正在停止 Linlin Agent..."
            Stop-RecordedSession
        }
        "Smoke" {
            Write-Heading "Linlin Agent 啟動驗證"
            $services = Start-LinlinServices
            Write-Host "後端健康檢查：通過" -ForegroundColor Green
            Write-Host "前端頁面檢查：通過" -ForegroundColor Green
            Stop-RecordedSession
        }
        default {
            Write-Heading "Linlin Agent 一鍵啟動"
            $services = Start-LinlinServices
            Open-LinlinBrowser

            Write-Host ""
            Write-Host "Linlin Agent 已成功啟動。" -ForegroundColor Green
            Write-Host "操作畫面：$FrontendUrl"
            Write-Host ""
            Write-Host "使用完畢後，回到這個黑色視窗按 Enter，即可安全停止專案。" -ForegroundColor Yellow
            [void](Read-Host)
            Stop-RecordedSession
        }
    }
}
catch {
    Write-Host ""
    Write-Host "啟動失敗：$($_.Exception.Message)" -ForegroundColor Red
    Write-Host "記錄位置：$LogRoot" -ForegroundColor Yellow
    Stop-RecordedSession
    exit 1
}
