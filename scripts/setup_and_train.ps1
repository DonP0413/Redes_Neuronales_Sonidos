param(
    [string]$Esc50Source = "C:\tmp\ESC-50"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ProjectPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
Set-Location $ProjectRoot

Write-Host "[1/5] Creando entorno Python 3.11..."
uv venv --python 3.11 .venv

Write-Host "[2/5] Instalando dependencias..."
uv pip install --python $ProjectPython -r requirements-train.txt

$PreparedCount = (Get-ChildItem -Path dataset\esc50 -Recurse -File -Filter *.wav -ErrorAction SilentlyContinue).Count
if ($PreparedCount -ne 240) {
    if (-not (Test-Path (Join-Path $Esc50Source "meta\esc50.csv"))) {
        throw "No se encontró ESC-50 en $Esc50Source. Clónalo o pasa -Esc50Source con la ruta correcta."
    }
    Write-Host "[3/5] Preparando seis clases reales de ESC-50..."
    & $ProjectPython -m src.prepare_esc50 --source-dir $Esc50Source
} else {
    Write-Host "[3/5] Dataset ESC-50 preparado (240 audios)."
}

Write-Host "[4/5] Entrenando y comparando Adam vs. SGD..."
& $ProjectPython -m src.train --dataset-dir dataset\esc50 --epochs 70 --batch-size 16 --patience 12 --seed 2026

Write-Host "[5/5] Ejecutando pruebas..."
& $ProjectPython -m pytest -q

Write-Host "Listo. Inicia la web con: .venv\Scripts\python.exe app.py"
