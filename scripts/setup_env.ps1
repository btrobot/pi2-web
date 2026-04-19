param(
    [string]$VenvDir = ".venv"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$FullVenvPath = Join-Path $ProjectRoot $VenvDir
$PythonExe = Join-Path $FullVenvPath "Scripts\python.exe"
$Requirements = Join-Path $ProjectRoot "requirements-dev.txt"

Write-Host "=== Windows dev/test environment setup ==="
Write-Host "Project root: $ProjectRoot"

if (-not (Test-Path $FullVenvPath)) {
    Write-Host "[1/4] Creating virtual environment..."
    python -m venv $FullVenvPath
} else {
    Write-Host "[1/4] Virtual environment already exists: $FullVenvPath"
}

Write-Host "[2/4] Upgrading pip..."
& $PythonExe -m pip install --upgrade pip

Write-Host "[3/4] Installing requirements-dev.txt..."
& $PythonExe -m pip install -r $Requirements

Write-Host "[4/4] Done"
Write-Host "Activate: $FullVenvPath\Scripts\Activate.ps1"
Write-Host "Run tests: pytest -q"
Write-Host "Start app: python main.py"
Write-Host "Note: Windows dev profile excludes pyalsaaudio, so real ALSA record/playback must run on Linux / Raspberry Pi."
