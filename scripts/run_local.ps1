$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ProjectPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $ProjectPython)) {
    throw "No existe .venv. Ejecuta primero scripts/setup_and_train.ps1"
}

Set-Location $ProjectRoot
& $ProjectPython app.py

