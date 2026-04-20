#!/usr/bin/env bash
# 在有网络的机器上运行，下载离线运行所需模型与依赖。
# 下载完成后，可将 models/data/ 拷贝到 Pi。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MODELS_DIR="${PROJECT_ROOT}/models/data"
PIPER_DIR="${MODELS_DIR}/piper"
ARGOS_DIR="${MODELS_DIR}/argos"

for cmd in wget unzip python3; do
    if ! command -v "${cmd}" >/dev/null 2>&1; then
        echo "[错误] 缺少依赖命令: ${cmd}"
        exit 1
    fi
done

mkdir -p "${MODELS_DIR}" "${PIPER_DIR}" "${ARGOS_DIR}"
export ARGOS_PACKAGES_DIR="${ARGOS_DIR}"
export PYTHONPATH="${PROJECT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

download_if_missing() {
    local url="$1"
    local output="$2"
    if [ -f "${output}" ]; then
        echo "[跳过] 已存在: ${output}"
        return
    fi
    wget -q --show-progress -O "${output}" "${url}"
}

VOSK_CN_NAME="vosk-model-small-cn-0.22"
VOSK_CN_DIR="${MODELS_DIR}/${VOSK_CN_NAME}"
VOSK_CN_URL="https://alphacephei.com/vosk/models/${VOSK_CN_NAME}.zip"

if [ -d "${VOSK_CN_DIR}" ]; then
    echo "[跳过] Vosk 中文模型已存在: ${VOSK_CN_DIR}"
else
    echo "[下载] Vosk 中文模型..."
    download_if_missing "${VOSK_CN_URL}" "${MODELS_DIR}/${VOSK_CN_NAME}.zip"
    unzip -q "${MODELS_DIR}/${VOSK_CN_NAME}.zip" -d "${MODELS_DIR}"
    rm -f "${MODELS_DIR}/${VOSK_CN_NAME}.zip"
fi

VOSK_EN_NAME="vosk-model-small-en-us-0.15"
VOSK_EN_DIR="${MODELS_DIR}/${VOSK_EN_NAME}"
VOSK_EN_URL="https://alphacephei.com/vosk/models/${VOSK_EN_NAME}.zip"

if [ -d "${VOSK_EN_DIR}" ]; then
    echo "[跳过] Vosk 英文模型已存在: ${VOSK_EN_DIR}"
else
    echo "[下载] Vosk 英文模型..."
    download_if_missing "${VOSK_EN_URL}" "${MODELS_DIR}/${VOSK_EN_NAME}.zip"
    unzip -q "${MODELS_DIR}/${VOSK_EN_NAME}.zip" -d "${MODELS_DIR}"
    rm -f "${MODELS_DIR}/${VOSK_EN_NAME}.zip"
fi

if ! python3 -c "import argostranslate" >/dev/null 2>&1; then
    echo "[安装] argostranslate..."
    python3 -m pip install --quiet argostranslate
fi

echo "[检查] Argos 翻译包..."
python3 - <<'PY'
import argostranslate.package as pkg

pkg.update_package_index()
available = pkg.get_available_packages()
required_pairs = [("en", "zh"), ("zh", "en")]
installed = {(p.from_code, p.to_code) for p in pkg.get_installed_packages()}

for source, target in required_pairs:
    if (source, target) in installed:
        print(f"[跳过] Argos {source}->{target} 已安装")
        continue

    package = next((p for p in available if p.from_code == source and p.to_code == target), None)
    if package is None:
        raise SystemExit(f"[错误] 未找到 Argos 语言包: {source}->{target}")

    print(f"[安装] Argos {source}->{target}...")
    pkg.install_from_path(package.download())
PY

echo "[检查] 预热 Argos 离线分句依赖..."
python3 - <<'PY'
import os

from models.mt import validate_mt_runtime

issues = validate_mt_runtime(
    package_dir=os.environ["ARGOS_PACKAGES_DIR"],
    allow_network=True,
)
if issues:
    raise SystemExit("[错误] Argos 离线依赖准备失败:\n- " + "\n- ".join(issues))
print("[完成] Argos 离线分句依赖已就绪")
PY

PIPER_ZH_ONNX="${PIPER_DIR}/zh_CN-huayan-medium.onnx"
PIPER_ZH_JSON="${PIPER_DIR}/zh_CN-huayan-medium.onnx.json"
PIPER_ZH_BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium"

if [ -f "${PIPER_ZH_ONNX}" ] && [ -f "${PIPER_ZH_JSON}" ]; then
    echo "[跳过] Piper 中文模型已存在"
else
    echo "[下载] Piper 中文语音模型..."
    download_if_missing "${PIPER_ZH_BASE_URL}/zh_CN-huayan-medium.onnx" "${PIPER_ZH_ONNX}"
    download_if_missing "${PIPER_ZH_BASE_URL}/zh_CN-huayan-medium.onnx.json" "${PIPER_ZH_JSON}"
fi

PIPER_EN_ONNX="${PIPER_DIR}/en_US-lessac-medium.onnx"
PIPER_EN_JSON="${PIPER_DIR}/en_US-lessac-medium.onnx.json"
PIPER_EN_BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"

if [ -f "${PIPER_EN_ONNX}" ] && [ -f "${PIPER_EN_JSON}" ]; then
    echo "[跳过] Piper 英文模型已存在"
else
    echo "[下载] Piper 英文语音模型..."
    download_if_missing "${PIPER_EN_BASE_URL}/en_US-lessac-medium.onnx" "${PIPER_EN_ONNX}"
    download_if_missing "${PIPER_EN_BASE_URL}/en_US-lessac-medium.onnx.json" "${PIPER_EN_JSON}"
fi

echo
echo "========================================"
echo "  模型文件大小统计"
echo "========================================"

print_size() {
    local label="$1"
    local path="$2"
    if [ -e "${path}" ]; then
        local size
        size=$(du -sh "${path}" 2>/dev/null | cut -f1)
        printf "  %-30s %s\n" "${label}" "${size}"
    else
        printf "  %-30s %s\n" "${label}" "(未找到)"
    fi
}

print_size "Vosk 中文 (${VOSK_CN_NAME})" "${VOSK_CN_DIR}"
print_size "Vosk 英文 (${VOSK_EN_NAME})" "${VOSK_EN_DIR}"
print_size "Piper 中文 (zh_CN-huayan)" "${PIPER_ZH_ONNX}"
print_size "Piper 英文 (en_US-lessac)" "${PIPER_EN_ONNX}"

ARGOS_SIZE=$(python3 - <<'PY'
import os
import argostranslate.package as pkg

total = 0
for package in pkg.get_installed_packages():
    package_path = getattr(package, "package_path", None)
    if not package_path:
        continue
    for root, _, files in os.walk(package_path):
        total += sum(os.path.getsize(os.path.join(root, name)) for name in files)
print(f"{total / 1024 / 1024:.1f}M")
PY
)
printf "  %-30s %s\n" "Argos 翻译包" "${ARGOS_SIZE}"

echo "----------------------------------------"
TOTAL_SIZE=$(du -sh "${MODELS_DIR}" 2>/dev/null | cut -f1)
printf "  %-30s %s\n" "models/data/ 总占用" "${TOTAL_SIZE}"
echo "========================================"
echo
echo "[完成] 离线模型与 Argos/Stanza 依赖已准备完毕，可将 models/data/ 拷贝到 Pi。"
