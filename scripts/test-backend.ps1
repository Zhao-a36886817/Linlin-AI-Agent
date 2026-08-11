#Requires -Version 5.1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = "F:\Linlin-Agent"
$BackendRoot = "$ProjectRoot\backend"
$PythonExe = "C:\Users\Zhao\Anaconda3\envs\Linlin_agent\python.exe"

# 測試必須由指定的 Linlin_agent 環境執行，不能誤用系統 Python。
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "找不到 Linlin_agent 的 Python：$PythonExe"
}

Set-Location $BackendRoot
$env:PYTHONPATH = $BackendRoot

& $PythonExe -m pytest -v
