#Requires -Version 5.1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\Linlin-Agent"
$BackendRoot = "$ProjectRoot\backend"

Set-Location $BackendRoot
$env:PYTHONPATH = $BackendRoot

python -m pytest -v
