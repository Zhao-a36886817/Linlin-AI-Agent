param(
    [ValidateSet("menu", "install", "install-training", "run", "install-run", "stop", "verify", "smoke", "help")]
    [string]$Command = "menu"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$AppRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$SessionDir = Join-Path $env:TEMP "Linlin-Agent-launcher"
$StateFile = Join-Path $SessionDir "session.json"
$BackendPort = 8000
$FrontendPort = 5173

# Some desktop hosts inject both Path and PATH. Windows PowerShell's
# Start-Process treats them as duplicate case-insensitive dictionary keys.
$processPath = $env:Path
[Environment]::SetEnvironmentVariable("PATH", $null, "Process")
[Environment]::SetEnvironmentVariable("Path", $processPath, "Process")

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Resolve-Tool([string]$Name, [string[]]$Fallbacks) {
    $found = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { return $found.Source }
    foreach ($path in $Fallbacks) { if ($path -and (Test-Path -LiteralPath $path)) { return $path } }
    return $null
}

function Resolve-Conda {
    return Resolve-Tool "conda.exe" @(
        (Join-Path $env:USERPROFILE "anaconda3\Scripts\conda.exe"),
        (Join-Path $env:USERPROFILE "miniconda3\Scripts\conda.exe")
    )
}

function Resolve-Python([switch]$Create) {
    $candidates = @(
        (Join-Path $AppRoot ".venv\Scripts\python.exe"),
        (Join-Path $env:USERPROFILE "anaconda3\envs\Linlin_agent\python.exe"),
        (Join-Path $env:USERPROFILE "miniconda3\envs\Linlin_agent\python.exe")
    )
    foreach ($path in $candidates) { if (Test-Path -LiteralPath $path) { return $path } }
    $conda = Resolve-Conda
    if ($Create -and $conda) {
        Write-Step "Creating the Linlin_agent environment"
        & $conda env create -f (Join-Path $AppRoot "environment.yml")
        if ($LASTEXITCODE -ne 0) { throw "Conda environment creation failed." }
        foreach ($path in $candidates) { if (Test-Path -LiteralPath $path) { return $path } }
    }
    $python = Resolve-Tool "python.exe" @()
    if ($python) { return $python }
    throw "Python was not found. Run Install after installing Miniconda or Python."
}

function Resolve-Node {
    # 優先使用專案指定的 Linlin_agent Node，再回退到系統 Node.js。
    $fallbacks = @(
        (Join-Path $env:USERPROFILE "Anaconda3\envs\Linlin_agent\node.exe"),
        (Join-Path $env:USERPROFILE "Miniconda3\envs\Linlin_agent\node.exe"),
        (Join-Path $env:ProgramFiles "nodejs\node.exe")
    )
    $node = Resolve-Tool "node.exe" $fallbacks
    if (-not $node) { throw "Node.js was not found. Install Node.js LTS and try again." }
    return $node
}

function Resolve-Npm {
    # npm 必須和 Node 來自同一個固定環境，避免建置時版本混用。
    $fallbacks = @(
        (Join-Path $env:USERPROFILE "Anaconda3\envs\Linlin_agent\npm.cmd"),
        (Join-Path $env:USERPROFILE "Miniconda3\envs\Linlin_agent\npm.cmd"),
        (Join-Path $env:ProgramFiles "nodejs\npm.cmd")
    )
    $npm = Resolve-Tool "npm.cmd" $fallbacks
    if (-not $npm) { throw "npm was not found. Install Node.js LTS and try again." }
    # Conda 的 npm.cmd 會再呼叫 node；把同一目錄放到 PATH，確保子程序找得到。
    $npmRoot = Split-Path $npm -Parent
    if (($env:Path -split [IO.Path]::PathSeparator) -notcontains $npmRoot) {
        $env:Path = "$npmRoot$([IO.Path]::PathSeparator)$env:Path"
    }
    return $npm
}

function Assert-PortFree([int]$Port) {
    $used = netstat -ano | Select-String -Pattern ":$Port\s+.*LISTENING"
    if ($used) { throw "Port $Port is already in use. Choose Stop from the launcher, then try again." }
}

function Wait-Ready([string]$Url, [int]$Seconds = 60) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) { return }
        } catch { Start-Sleep -Milliseconds 500 }
    } while ((Get-Date) -lt $deadline)
    throw "Timed out waiting for $Url"
}

function Save-State($Backend, $Frontend) {
    New-Item -ItemType Directory -Path $SessionDir -Force | Out-Null
    @{
        backend = @{ pid = $Backend.Id; started = $Backend.StartTime.ToUniversalTime().ToString("O") }
        frontend = @{ pid = $Frontend.Id; started = $Frontend.StartTime.ToUniversalTime().ToString("O") }
    } | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $StateFile -Encoding UTF8
}

function Save-BrowserState($Browser, [string]$Profile) {
    if (-not (Test-Path -LiteralPath $StateFile)) { return }
    $state = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
    $state | Add-Member -NotePropertyName browser -NotePropertyValue @{
        pid = $Browser.Id
        started = $Browser.StartTime.ToUniversalTime().ToString("O")
    } -Force
    $state | Add-Member -NotePropertyName browser_profile -NotePropertyValue $Profile -Force
    $state | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $StateFile -Encoding UTF8
}

function Stop-ProfileBrowserProcesses([string]$Profile) {
    if (-not $Profile) { return }
    $profilePath = [IO.Path]::GetFullPath($Profile)
    $sessionPath = [IO.Path]::GetFullPath($SessionDir)
    $parent = Split-Path $profilePath -Parent
    if ($parent -ne $sessionPath -or (Split-Path $profilePath -Leaf) -notlike "browser-profile-*") {
        Write-Warning "Refusing to inspect an unexpected browser profile path."
        return
    }
    try {
        $owned = Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
            $_.Name -in @("msedge.exe", "chrome.exe") -and
            $_.CommandLine -and
            $_.CommandLine.IndexOf($profilePath, [StringComparison]::OrdinalIgnoreCase) -ge 0
        }
        foreach ($item in $owned) {
            Stop-Process -Id ([int]$item.ProcessId) -Force -ErrorAction SilentlyContinue
        }
    } catch {
        Write-Warning "Could not inspect dedicated browser child processes: $($_.Exception.Message)"
    }
}

function Remove-SessionDirectory {
    $target = [IO.Path]::GetFullPath($SessionDir)
    $temp = [IO.Path]::GetFullPath($env:TEMP)
    if ((Split-Path $target -Parent) -ne $temp -or (Split-Path $target -Leaf) -ne "Linlin-Agent-launcher") {
        throw "Refusing to clean an unexpected session path."
    }
    if (-not (Test-Path -LiteralPath $target)) { return }
    for ($attempt = 1; $attempt -le 8; $attempt++) {
        try {
            Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction Stop
            return
        } catch {
            if ($attempt -eq 8) {
                Write-Warning "Temporary launcher files remain locked and will be retried next time: $target"
                return
            }
            Start-Sleep -Milliseconds 250
        }
    }
}

function Stop-OwnedProcess($Entry) {
    if (-not $Entry -or -not $Entry.pid) { return }
    $process = Get-Process -Id ([int]$Entry.pid) -ErrorAction SilentlyContinue
    if (-not $process) { return }
    $actual = $process.StartTime.ToUniversalTime().ToString("O")
    if ($actual -ne [string]$Entry.started) {
        Write-Warning "PID $($Entry.pid) was reused; it will not be stopped."
        return
    }
    Stop-Process -Id $process.Id -Force
    $process.WaitForExit(5000) | Out-Null
}

function Stop-Linlin {
    if (Test-Path -LiteralPath $StateFile) {
        try {
            $state = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
            Stop-OwnedProcess $state.browser
            Stop-ProfileBrowserProcesses $state.browser_profile
            Stop-OwnedProcess $state.frontend
            Stop-OwnedProcess $state.backend
        } catch { Write-Warning "Could not read the previous launcher state: $($_.Exception.Message)" }
    }
    Remove-SessionDirectory
}

function Show-Logs {
    foreach ($name in @("backend.err.log", "frontend.err.log")) {
        $path = Join-Path $SessionDir $name
        if (Test-Path -LiteralPath $path) {
            Write-Host "`n--- $name ---" -ForegroundColor Yellow
            Get-Content -LiteralPath $path -Tail 30
        }
    }
}

function Ensure-FrontendDependencies {
    $vite = Join-Path $AppRoot "frontend\node_modules\vite\bin\vite.js"
    $tsc = Join-Path $AppRoot "frontend\node_modules\typescript\bin\tsc"
    if ((Test-Path -LiteralPath $vite) -and (Test-Path -LiteralPath $tsc)) { return }
    $npm = Resolve-Npm
    Write-Step "Frontend dependencies are incomplete; repairing from package-lock.json"
    Push-Location (Join-Path $AppRoot "frontend")
    try { & $npm ci; if ($LASTEXITCODE -ne 0) { throw "Frontend dependency repair failed." } }
    finally { Pop-Location }
}

function Build-Frontend {
    Ensure-FrontendDependencies
    $npm = Resolve-Npm
    Write-Step "Building the web interface"
    Push-Location (Join-Path $AppRoot "frontend")
    try { & $npm run build; if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." } }
    finally { Pop-Location }
}

function Install-Dependencies {
    $python = Resolve-Python -Create
    $npm = Resolve-Npm
    Write-Step "Installing the backend"
    & $python -m pip install -e (Join-Path $AppRoot "backend")
    if ($LASTEXITCODE -ne 0) { throw "Backend installation failed." }
    Write-Step "Installing locked frontend dependencies"
    Push-Location (Join-Path $AppRoot "frontend")
    try { & $npm ci; if ($LASTEXITCODE -ne 0) { throw "Frontend installation failed." } }
    finally { Pop-Location }
    Write-Host "`nInstallation completed." -ForegroundColor Green
}

function Install-TrainingDependencies {
    $python = Resolve-Python -Create
    Write-Step "Installing optional local LoRA training support"
    & $python -m pip install -e ((Join-Path $AppRoot "backend") + "[training]")
    if ($LASTEXITCODE -ne 0) { throw "Local training dependency installation failed." }
    Write-Host "`nLocal LoRA support installed. Put Hugging Face model directories under models\." -ForegroundColor Green
}

function Start-Services {
    Stop-Linlin
    Assert-PortFree $BackendPort
    Assert-PortFree $FrontendPort
    $python = Resolve-Python
    $node = Resolve-Node
    $vite = Join-Path $AppRoot "frontend\node_modules\vite\bin\vite.js"
    if (-not (Test-Path -LiteralPath $vite)) { throw "Frontend dependencies are missing. Choose Install first." }
    New-Item -ItemType Directory -Path $SessionDir -Force | Out-Null
    Write-Step "Starting backend"
    $backend = Start-Process -FilePath $python -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort") -WorkingDirectory (Join-Path $AppRoot "backend") -RedirectStandardOutput (Join-Path $SessionDir "backend.out.log") -RedirectStandardError (Join-Path $SessionDir "backend.err.log") -WindowStyle Hidden -PassThru
    Write-Step "Starting web interface"
    $frontend = Start-Process -FilePath $node -ArgumentList @($vite, "preview", "--host", "127.0.0.1", "--port", "$FrontendPort", "--strictPort") -WorkingDirectory (Join-Path $AppRoot "frontend") -RedirectStandardOutput (Join-Path $SessionDir "frontend.out.log") -RedirectStandardError (Join-Path $SessionDir "frontend.err.log") -WindowStyle Hidden -PassThru
    Save-State $backend $frontend
    Wait-Ready "http://127.0.0.1:$BackendPort/api/health"
    Wait-Ready "http://127.0.0.1:$FrontendPort"
}

function Resolve-Browser {
    $paths = @(
        (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe"),
        (Join-Path $env:ProgramFiles "Microsoft\Edge\Application\msedge.exe"),
        (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe")
    )
    foreach ($path in $paths) { if ($path -and (Test-Path -LiteralPath $path)) { return $path } }
    throw "Microsoft Edge or Google Chrome is required."
}

function Run-App([switch]$Smoke) {
    Build-Frontend
    try {
        Start-Services
        if ($Smoke) {
            Write-Host "`nHidden startup and shutdown smoke passed." -ForegroundColor Green
            return
        }
        $browser = Resolve-Browser
        $profile = Join-Path $SessionDir ("browser-profile-" + [guid]::NewGuid().ToString("N"))
        Write-Host "`nLinlin Agent is ready. Close the app window to stop everything." -ForegroundColor Green
        $window = Start-Process -FilePath $browser -ArgumentList @("--app=http://127.0.0.1:$FrontendPort", "--user-data-dir=$profile", "--no-first-run", "--disable-background-mode") -PassThru
        Save-BrowserState $window $profile
        $window.WaitForExit()
    } catch {
        Show-Logs
        throw
    } finally {
        Stop-Linlin
    }
}

function Verify-App {
    $python = Resolve-Python
    $npm = Resolve-Npm
    Write-Step "Running backend tests"
    Push-Location (Join-Path $AppRoot "backend")
    try { & $python -m pytest tests -q --basetemp tests/__pycache__/pytest-launcher -p no:cacheprovider; if ($LASTEXITCODE -ne 0) { throw "Backend tests failed." } }
    finally { Pop-Location }
    Build-Frontend
    Write-Step "Linting the web interface"
    Push-Location (Join-Path $AppRoot "frontend")
    try { & $npm run lint; if ($LASTEXITCODE -ne 0) { throw "Frontend lint failed." } }
    finally { Pop-Location }
    Run-App -Smoke
    Write-Host "`nVerification passed." -ForegroundColor Green
}

function Show-Help {
    Write-Host "Linlin-Agent.bat [install|install-training|run|install-run|stop|verify|smoke|help]"
    Write-Host "Run without an argument to open the menu."
}

function Show-Menu {
    while ($true) {
        Clear-Host
        Write-Host "==========================================" -ForegroundColor DarkCyan
        Write-Host "        Linlin Agent — One-click App" -ForegroundColor Cyan
        Write-Host "==========================================" -ForegroundColor DarkCyan
        Write-Host "  1  Run Linlin Agent"
        Write-Host "  2  Install / update dependencies"
        Write-Host "  3  Install local LoRA training support"
        Write-Host "  4  Install, then run"
        Write-Host "  5  Verify everything"
        Write-Host "  6  Stop background services"
        Write-Host "  7  Exit"
        switch (Read-Host "`nSelect [1-7]") {
            "1" { Run-App; return }
            "2" { Install-Dependencies; Read-Host "Press Enter" | Out-Null }
            "3" { Install-TrainingDependencies; Read-Host "Press Enter" | Out-Null }
            "4" { Install-Dependencies; Run-App; return }
            "5" { Verify-App; Read-Host "Press Enter" | Out-Null }
            "6" { Stop-Linlin; Write-Host "Stopped." -ForegroundColor Green; Start-Sleep 1 }
            "7" { return }
        }
    }
}

try {
    switch ($Command) {
        "menu" { Show-Menu }
        "install" { Install-Dependencies }
        "install-training" { Install-TrainingDependencies }
        "run" { Run-App }
        "install-run" { Install-Dependencies; Run-App }
        "stop" { Stop-Linlin; Write-Host "Linlin Agent stopped." -ForegroundColor Green }
        "verify" { Verify-App }
        "smoke" { Run-App -Smoke }
        "help" { Show-Help }
    }
    exit 0
} catch {
    Write-Host "`nERROR: $($_.Exception.Message)" -ForegroundColor Red
    Show-Logs
    try { Stop-Linlin } catch { Write-Warning $_.Exception.Message }
    exit 1
}
