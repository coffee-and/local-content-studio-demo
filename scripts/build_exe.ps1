$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    Write-Host "[1/4] Creating virtual environment..."
    py -3.12 -m venv .venv
}

Write-Host "[2/4] Activating environment and installing dependencies..."
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

Write-Host "[3/4] Running tests..."
python -m pytest -q

Write-Host "[4/4] Building Windows EXE..."
python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name LocalContentStudio `
    --add-data "sample_data;sample_data" `
    --collect-data cv2 `
    --collect-submodules openai `
    run.py

Write-Host "Build complete: dist\LocalContentStudio\LocalContentStudio.exe"
