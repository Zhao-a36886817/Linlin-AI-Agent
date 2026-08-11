# Linlin Agent 的簡易 Docker 測試選單。
#
# 設計目標：
# 1. 使用者只需雙擊 Linlin-Agent-Test.bat，不必記住 Docker 指令。
# 2. 自動確認並啟動名稱為 Linlin-Agent 的容器。
# 3. 第一次執行前端或桌面測試時，自動暫時開放網路下載免費開源依賴。
# 4. 下載完成後立即移除外部網路，正式專案仍維持唯讀掛載。
# 5. 測試失敗必須如實顯示，不會刪除、停用或弱化測試。

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ContainerName = "Linlin-Agent"
$ComposeFile = Join-Path $PSScriptRoot "compose.yaml"
$script:LastExitCode = 0

function Write-Section {
    param([Parameter(Mandatory = $true)][string]$Title)

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor DarkCyan
    Write-Host " $Title" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor DarkCyan
}

function Test-DockerAvailable {
    # docker info 同時確認指令存在且 Docker Desktop 引擎已啟動。
    $null = Get-Command docker -ErrorAction Stop
    docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Desktop 尚未啟動。請先開啟 Docker Desktop，等左下角顯示正常後重試。"
    }
}

function Test-ContainerExists {
    docker inspect $ContainerName *> $null
    return ($LASTEXITCODE -eq 0)
}

function Test-ContainerRunning {
    if (-not (Test-ContainerExists)) {
        return $false
    }

    $state = docker inspect --format "{{.State.Running}}" $ContainerName
    return ($state.Trim().ToLowerInvariant() -eq "true")
}

function Start-LinlinSandbox {
    Test-DockerAvailable

    if (-not (Test-ContainerExists)) {
        Write-Host "第一次建立 Docker 沙盒，請稍候……" -ForegroundColor Yellow
        docker compose -f $ComposeFile up -d --build
        if ($LASTEXITCODE -ne 0) {
            throw "Docker 沙盒建立失敗。"
        }
    }
    elseif (-not (Test-ContainerRunning)) {
        Write-Host "正在啟動 Docker 沙盒……" -ForegroundColor Yellow
        docker compose -f $ComposeFile start
        if ($LASTEXITCODE -ne 0) {
            throw "Docker 沙盒啟動失敗。"
        }
    }

    # 每次測試前重新啟動，讓 /workspace 取得 F:\Linlin-Agent 的最新唯讀程式碼副本。
    Write-Host "正在載入最新專案內容……" -ForegroundColor Yellow
    docker restart $ContainerName *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker 沙盒重新載入失敗。"
    }

    # docker restart 只代表容器程序已開始，不代表啟動腳本已複製完所有原始碼。
    # 等待後端、前端與 Cargo 三個代表性檔案同時出現，避免後續測試搶先執行。
    $ready = $false
    $deadline = [DateTime]::UtcNow.AddSeconds(60)

    while ([DateTime]::UtcNow -lt $deadline) {
        docker exec $ContainerName bash -lc "test -f /workspace/.linlin-sandbox-ready && test -f /workspace/backend/pyproject.toml && test -f /workspace/frontend/package.json && test -f /workspace/desktop/src-tauri/Cargo.toml" *> $null
        if ($LASTEXITCODE -eq 0) {
            $ready = $true
            break
        }

        if (-not (Test-ContainerRunning)) {
            throw "Docker 沙盒在載入專案內容時意外停止。"
        }

        Start-Sleep -Seconds 1
    }

    if (-not $ready) {
        throw "Docker 沙盒等待專案內容超過 60 秒，請保留畫面供檢查。"
    }

    Write-Host "Docker 沙盒已就緒。" -ForegroundColor Green
}

function Test-FrontendDependenciesReady {
    docker exec $ContainerName bash -lc "test -x /workspace/frontend/node_modules/.bin/vite" *> $null
    return ($LASTEXITCODE -eq 0)
}

function Test-CargoDependenciesReady {
    # --offline 不會使用網路；成功表示 Cargo 快取已足以執行目前 lockfile。
    docker exec $ContainerName bash -lc "cd /workspace/desktop/src-tauri && cargo fetch --locked --offline" *> $null
    return ($LASTEXITCODE -eq 0)
}

function Install-MissingDependencies {
    param(
        [bool]$NeedFrontend,
        [bool]$NeedCargo
    )

    $installFrontend = $NeedFrontend -and -not (Test-FrontendDependenciesReady)
    $installCargo = $NeedCargo -and -not (Test-CargoDependenciesReady)

    if (-not $installFrontend -and -not $installCargo) {
        Write-Host "測試依賴已準備完成。" -ForegroundColor Green
        return
    }

    Write-Host "第一次測試需要下載免費開源依賴，完成後會自動關閉外部網路。" -ForegroundColor Yellow

    # 只有下載期間暫時連接 Docker 預設 bridge；finally 可確保成功或失敗都會移除連線。
    $networkJson = docker inspect --format "{{json .NetworkSettings.Networks}}" $ContainerName
    $bridgeWasAlreadyConnected = $networkJson -match '"bridge"'
    $bridgeAddedHere = $false

    try {
        if (-not $bridgeWasAlreadyConnected) {
            docker network connect bridge $ContainerName
            if ($LASTEXITCODE -ne 0) {
                throw "無法暫時開啟 Docker 依賴下載網路。"
            }
            $bridgeAddedHere = $true
        }

        if ($installFrontend) {
            Write-Host "正在準備前端依賴……" -ForegroundColor Yellow
            docker exec $ContainerName bash -lc "cd /workspace/frontend && npm ci"
            if ($LASTEXITCODE -ne 0) {
                throw "前端依賴下載失敗。"
            }
        }

        if ($installCargo) {
            Write-Host "正在準備 Rust/Cargo 依賴……" -ForegroundColor Yellow
            docker exec $ContainerName bash -lc "cd /workspace/desktop/src-tauri && cargo fetch --locked"
            if ($LASTEXITCODE -ne 0) {
                throw "Rust/Cargo 依賴下載失敗。"
            }
        }
    }
    finally {
        if ($bridgeAddedHere) {
            docker network disconnect bridge $ContainerName *> $null
        }
    }

    Write-Host "依賴準備完成，外部網路已關閉。" -ForegroundColor Green
}

function Invoke-LinlinTest {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Command
    )

    Write-Section $Name
    # Out-Host 讓完整測試輸出直接顯示在畫面，同時避免函式回傳值混入大量文字。
    docker exec $ContainerName bash -lc $Command | Out-Host
    $result = $LASTEXITCODE

    if ($result -eq 0) {
        Write-Host "$Name：通過" -ForegroundColor Green
    }
    else {
        Write-Host "$Name：未通過（錯誤碼 $result）" -ForegroundColor Red
        Write-Host "失敗會完整保留，請勿刪除或停用測試。" -ForegroundColor Yellow
    }

    $script:LastExitCode = $result
    return $result
}

function Invoke-BackendTests {
    return Invoke-LinlinTest `
        -Name "後端測試" `
        -Command "cd /workspace/backend && python -m compileall -q app tests && python -m ruff check app tests && python -m pytest tests -q -p no:cacheprovider"
}

function Invoke-FrontendTests {
    return Invoke-LinlinTest `
        -Name "前端建置與檢查" `
        -Command "cd /workspace/frontend && npm run build && npm run lint"
}

function Invoke-DesktopTests {
    return Invoke-LinlinTest `
        -Name "桌面版 Cargo 檢查" `
        -Command "cd /workspace/desktop/src-tauri && cargo check --locked"
}

function Show-EnvironmentStatus {
    Write-Section "Docker 沙盒狀態"
    docker ps --filter "name=^/$ContainerName$" --format "名稱={{.Names}}  狀態={{.Status}}  映像={{.Image}}"
    docker exec $ContainerName bash -lc "python --version && node --version && rustc --version && cargo --version"
    $script:LastExitCode = $LASTEXITCODE
}

function Wait-ForMenu {
    Write-Host ""
    $null = Read-Host "按 Enter 回到選單"
}

do {
    Clear-Host
    Write-Host "Linlin Agent — Docker 測試選單" -ForegroundColor Cyan
    Write-Host "正式專案：F:\Linlin-Agent（Docker 內唯讀）"
    Write-Host ""
    Write-Host "1. 完整測試（建議）"
    Write-Host "2. 只測後端"
    Write-Host "3. 只測前端"
    Write-Host "4. 只測桌面版"
    Write-Host "5. 查看 Docker 狀態"
    Write-Host "6. 停止 Docker 沙盒"
    Write-Host "0. 離開"
    Write-Host ""

    $choice = Read-Host "請輸入數字"

    try {
        switch ($choice) {
            "1" {
                Start-LinlinSandbox
                Install-MissingDependencies -NeedFrontend $true -NeedCargo $true

                $backendResult = Invoke-BackendTests
                $frontendResult = Invoke-FrontendTests
                $desktopResult = Invoke-DesktopTests

                if ($backendResult -eq 0 -and $frontendResult -eq 0 -and $desktopResult -eq 0) {
                    $script:LastExitCode = 0
                    Write-Host "" 
                    Write-Host "三組測試全部通過。" -ForegroundColor Green
                }
                else {
                    $script:LastExitCode = 1
                    Write-Host ""
                    Write-Host "至少一組測試未通過，請保留畫面結果供後續修正。" -ForegroundColor Red
                }
                Wait-ForMenu
            }
            "2" {
                Start-LinlinSandbox
                $null = Invoke-BackendTests
                Wait-ForMenu
            }
            "3" {
                Start-LinlinSandbox
                Install-MissingDependencies -NeedFrontend $true -NeedCargo $false
                $null = Invoke-FrontendTests
                Wait-ForMenu
            }
            "4" {
                Start-LinlinSandbox
                Install-MissingDependencies -NeedFrontend $false -NeedCargo $true
                $null = Invoke-DesktopTests
                Wait-ForMenu
            }
            "5" {
                Start-LinlinSandbox
                Show-EnvironmentStatus
                Wait-ForMenu
            }
            "6" {
                Test-DockerAvailable
                docker compose -f $ComposeFile stop
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "Docker 沙盒已停止。正式專案與測試快取都保留。" -ForegroundColor Green
                    $script:LastExitCode = 0
                }
                else {
                    Write-Host "Docker 沙盒停止失敗。" -ForegroundColor Red
                    $script:LastExitCode = $LASTEXITCODE
                }
                Wait-ForMenu
            }
            "0" {
                # 離開選單；Docker 容器是否維持執行取決於使用者是否選過「停止」。
            }
            default {
                Write-Host "請輸入 0 到 6 的數字。" -ForegroundColor Yellow
                Start-Sleep -Seconds 1
            }
        }
    }
    catch {
        $script:LastExitCode = 1
        Write-Host ""
        Write-Host "操作失敗：$($_.Exception.Message)" -ForegroundColor Red
        Write-Host "正式專案沒有因此被修改。" -ForegroundColor Yellow
        Wait-ForMenu
    }
} while ($choice -ne "0")

exit $script:LastExitCode
