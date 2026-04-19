#!/usr/bin/env bash
# scripts/setup_env.sh
# Raspberry Pi / Linux setup helper for real-device runtime.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
REQUIREMENTS="${PROJECT_ROOT}/requirements-pi.txt"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This script is for Linux / Raspberry Pi only."
  echo "On Windows use: powershell -ExecutionPolicy Bypass -File scripts/setup_env.ps1"
  exit 1
fi

echo "=== Pi runtime environment setup ==="
echo "Project root: ${PROJECT_ROOT}"

echo ""
echo "[1/4] Installing system packages..."
sudo apt-get update -qq
SYSTEM_PACKAGES=(
  espeak-ng
  libasound2-dev
  python3-dev
  python3-pip
  python3-venv
  ffmpeg
)
for pkg in "${SYSTEM_PACKAGES[@]}"; do
  if dpkg -s "${pkg}" &>/dev/null; then
    echo "  already installed: ${pkg}"
  else
    echo "  installing: ${pkg}"
    sudo apt-get install -y -qq "${pkg}"
  fi
done

echo ""
echo "[2/4] Creating virtual environment..."
if [[ -d "${VENV_DIR}" ]]; then
  echo "  virtualenv exists: ${VENV_DIR}"
else
  python3 -m venv "${VENV_DIR}"
  echo "  created: ${VENV_DIR}"
fi

# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"
python -m pip install --upgrade pip

echo ""
echo "[3/4] Installing Python dependencies from requirements-pi.txt..."
python -m pip install -r "${REQUIREMENTS}"

echo ""
echo "[4/4] Notes"
echo "  If USB audio card indexes differ, adjust config/default.yaml or ~/.asoundrc manually."

echo ""
echo "=== Done ==="
echo "Activate: source ${VENV_DIR}/bin/activate"
echo "Run tests: pytest -q"
echo "Start app: python main.py"
