#Requires -Version 5.1

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet(
        "",
        "menu",
        "backend",
        "desktop",
        "test",
        "review",
        "doctor",
        "format",
        "clean",
        "status"
    )]
    [string]$Command = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$DevRoot = Join-Path $ProjectRoot "scripts\dev"

function Invoke-ToolkitScript {
    param(
        [Parameter(Mandatory)]
        [string]$Name
    )

    $ScriptPath = Join-Path $DevRoot $Name

    if (-not (Test-Path $ScriptPath)) {
        throw "Toolkit script not found: $ScriptPath"
    }

    & $ScriptPath
}

function Start-Backend {
    $ScriptPath = Join-Path $ProjectRoot "scripts\start-backend.ps1"

    if (Test-Path $ScriptPath) {
        & $ScriptPath
        return
    }

    Set-Location (Join-Path $ProjectRoot "backend")
    $env:PYTHONPATH = Join-Path $ProjectRoot "backend"

    python -m uvicorn app.main:app `
        --host 127.0.0.1 `
        --port 8000 `
        --reload
}

function Start-Desktop {
    $ScriptPath = Join-Path $ProjectRoot "scripts\start-desktop.ps1"

    if (Test-Path $ScriptPath) {
        & $ScriptPath
        return
    }

    Set-Location (Join-Path $ProjectRoot "desktop")
    pnpm tauri dev
}

function Show-ProjectStatus {
    Write-Host ""
    Write-Host "Linlin Agent Project Status" -ForegroundColor Cyan
    Write-Host "----------------------------------------------"

    $Checks = @(
        @{
            Name = "FastAPI Backend"
            Path = "$ProjectRoot\backend\app\main.py"
        },
        @{
            Name = "Desktop Application"
            Path = "$ProjectRoot\desktop\package.json"
        },
        @{
            Name = "Provider Manager"
            Path = "$ProjectRoot\backend\app\providers\manager.py"
        },
        @{
            Name = "Provider Factory"
            Path = "$ProjectRoot\backend\app\providers\factory.py"
        },
        @{
            Name = "Provider Cache"
            Path = "$ProjectRoot\backend\app\providers\cache.py"
        },
        @{
            Name = "Ollama Adapter"
            Path = "$ProjectRoot\backend\app\providers\adapters\ollama.py"
        },
        @{
            Name = "Models API"
            Path = "$ProjectRoot\backend\app\api\routes\models.py"
        },
        @{
            Name = "Chat API"
            Path = "$ProjectRoot\backend\app\api\routes\chat.py"
        },
        @{
            Name = "Credential Store"
            Path = "$ProjectRoot\backend\app\security\credential_store.py"
        }
    )

    foreach ($Check in $Checks) {
        if (Test-Path $Check.Path) {
            Write-Host ("[OK]   {0}" -f $Check.Name) -ForegroundColor Green
        }
        else {
            Write-Host ("[TODO] {0}" -f $Check.Name) -ForegroundColor Yellow
        }
    }

    Write-Host ""
    git -C $ProjectRoot status --short
}

function Show-Menu {
    while ($true) {
        Clear-Host

        Write-Host "====================================================" -ForegroundColor Cyan
        Write-Host "             Linlin Dev Toolkit v1.0" -ForegroundColor Cyan
        Write-Host "====================================================" -ForegroundColor Cyan
        Write-Host ""
        Write-Host " 1. Run Backend"
        Write-Host " 2. Run Desktop"
        Write-Host " 3. Run Tests"
        Write-Host " 4. Review Project"
        Write-Host " 5. Environment Doctor"
        Write-Host " 6. Format and Ruff Fix"
        Write-Host " 7. Clean Cache"
        Write-Host " 8. Project Status"
        Write-Host " 0. Exit"
        Write-Host ""

        $Choice = Read-Host "Select"

        switch ($Choice) {
            "1" {
                Start-Backend
            }

            "2" {
                Start-Desktop
            }

            "3" {
                Invoke-ToolkitScript "Test.ps1"
                Read-Host "Press Enter to continue"
            }

            "4" {
                Invoke-ToolkitScript "Review.ps1"
                Read-Host "Press Enter to continue"
            }

            "5" {
                Invoke-ToolkitScript "Doctor.ps1"
                Read-Host "Press Enter to continue"
            }

            "6" {
                Invoke-ToolkitScript "Format.ps1"
                Read-Host "Press Enter to continue"
            }

            "7" {
                Invoke-ToolkitScript "Clean.ps1"
                Read-Host "Press Enter to continue"
            }

            "8" {
                Show-ProjectStatus
                Read-Host "Press Enter to continue"
            }

            "0" {
                return
            }

            default {
                Write-Host "Invalid selection." -ForegroundColor Red
                Start-Sleep -Seconds 1
            }
        }
    }
}

switch ($Command) {
    "" {
        Show-Menu
    }

    "menu" {
        Show-Menu
    }

    "backend" {
        Start-Backend
    }

    "desktop" {
        Start-Desktop
    }

    "test" {
        Invoke-ToolkitScript "Test.ps1"
    }

    "review" {
        Invoke-ToolkitScript "Review.ps1"
    }

    "doctor" {
        Invoke-ToolkitScript "Doctor.ps1"
    }

    "format" {
        Invoke-ToolkitScript "Format.ps1"
    }

    "clean" {
        Invoke-ToolkitScript "Clean.ps1"
    }

    "status" {
        Show-ProjectStatus
    }
}
