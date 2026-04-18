#!/usr/bin/env bash
# 模型下载脚本 — 在有网络的机器上运行，下载后拷贝到 Pi5
# 幂等：已存在的文件/目录自动跳过
set -e

# ── 路径配置 ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MODELS_DIR="${PROJECT_ROOT}/models/data"
PIPER_DIR="${MODELS_DIR}/piper"

# ── 工具检查 ──────────────────────────────────────────────────────────────────
for cmd in wget unzip python3; do
    if ! command -v "${cmd}" &>/dev/null; then
        echo "[错误] 缺少依赖命令: ${cmd}"
        exit 1
    fi
done

mkdir -p "${MODELS_DIR}" "${PIPER_DIR}"

# ── 1. Vosk 中文模型 ──────────────────────────────────────────────────────────
VOSK_CN_NAME="vosk-model-small-cn-0.22"
VOSK_CN_DIR="${MODELS_DIR}/${VOSK_CN_NAME}"
VOSK_CN_URL="https://alphacephei.com/vosk/models/${VOSK_CN_NAME}.zip"

if [ -d "${VOSK_CN_DIR}" ]; then
    echo "[跳过] Vosk 中文模型已存在: ${VOSK_CN_DIR}"
else
    echo "[下载] Vosk 中文模型..."
    wget -q --show-progress -O "${MODELS_DIR}/${VOSK_CN_NAME}.zip" "${VOSK_CN_URL}"
    echo "[解压] Vosk 中文模型..."
    unzip -q "${MODELS_DIR}/${VOSK_CN_NAME}.zip" -d "${MODELS_DIR}"
    rm "${MODELS_DIR}/${VOSK_CN_NAME}.zip"
    echo "[完成] Vosk 中文模型"
fi

# ── 2. Vosk 英文模型 ──────────────────────────────────────────────────────────
VOSK_EN_NAME="vosk-model-small-en-us-0.15"
VOSK_EN_DIR="${MODELS_DIR}/${VOSK_EN_NAME}"
VOSK_EN_URL="https://alphacephei.com/vosk/models/${VOSK_EN_NAME}.zip"

if [ -d "${VOSK_EN_DIR}" ]; then
    echo "[跳过] Vosk 英文模型已存在: ${VOSK_EN_DIR}"
else
    echo "[下载] Vosk 英文模型..."
    wget -q --show-progress -O "${MODELS_DIR}/${VOSK_EN_NAME}.zip" "${VOSK_EN_URL}"
    echo "[解压] Vosk 英文模型..."
    unzip -q "${MODELS_DIR}/${VOSK_EN_NAME}.zip" -d "${MODELS_DIR}"
    rm "${MODELS_DIR}/${VOSK_EN_NAME}.zip"
    echo "[完成] Vosk 英文模型"
fi

# ── 3. Argos Translate 语言包 (en→zh, zh→en) ─────────────────────────────────
# argospm 由 argostranslate 包提供，需提前 pip install argostranslate
if ! python3 -c "import argostranslate" &>/dev/null; then
    echo "[安装] argostranslate..."
    pip3 install --quiet argostranslate
fi

# 检查已安装语言包的辅助函数
argos_pkg_installed() {
    local from_code="$1"
    local to_code="$2"
    python3 - <<EOF
import argostranslate.package as pkg
pkg.update_package_index()
installed = pkg.get_installed_packages()
found = any(p.from_code == "${from_code}" and p.to_code == "${to_code}" for p in installed)
exit(0 if found else 1)
EOF
}

echo "[检查] Argos Translate 语言包..."

# en → zh
if argos_pkg_installed "en" "zh"; then
    echo "[跳过] Argos en→zh 语言包已安装"
else
    echo "[安装] Argos en→zh 语言包..."
    python3 - <<'EOF'
import argostranslate.package as pkg
pkg.update_package_index()
available = pkg.get_available_packages()
en_zh = next((p for p in available if p.from_code == "en" and p.to_code == "zh"), None)
if en_zh is None:
    raise RuntimeError("未找到 en→zh 语言包")
pkg.install_from_path(en_zh.download())
print("[完成] Argos en→zh 语言包")
EOF
fi

# zh → en
if argos_pkg_installed "zh" "en"; then
    echo "[跳过] Argos zh→en 语言包已安装"
else
    echo "[安装] Argos zh→en 语言包..."
    python3 - <<'EOF'
import argostranslate.package as pkg
pkg.update_package_index()
available = pkg.get_available_packages()
zh_en = next((p for p in available if p.from_code == "zh" and p.to_code == "en"), None)
if zh_en is None:
    raise RuntimeError("未找到 zh→en 语言包")
pkg.install_from_path(zh_en.download())
print("[完成] Argos zh→en 语言包")
EOF
fi

# ── 4. Piper TTS 语音模型 ─────────────────────────────────────────────────────
# 中文模型: zh_CN-huayan-medium
PIPER_ZH_ONNX="${PIPER_DIR}/zh_CN-huayan-medium.onnx"
PIPER_ZH_JSON="${PIPER_DIR}/zh_CN-huayan-medium.onnx.json"
PIPER_ZH_BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium"

if [ -f "${PIPER_ZH_ONNX}" ] && [ -f "${PIPER_ZH_JSON}" ]; then
    echo "[跳过] Piper 中文模型已存在"
else
    echo "[下载] Piper 中文语音模型..."
    wget -q --show-progress -O "${PIPER_ZH_ONNX}" "${PIPER_ZH_BASE_URL}/zh_CN-huayan-medium.onnx"
    wget -q --show-progress -O "${PIPER_ZH_JSON}" "${PIPER_ZH_BASE_URL}/zh_CN-huayan-medium.onnx.json"
    echo "[完成] Piper 中文语音模型"
fi

# 英文模型: en_US-lessac-medium
PIPER_EN_ONNX="${PIPER_DIR}/en_US-lessac-medium.onnx"
PIPER_EN_JSON="${PIPER_DIR}/en_US-lessac-medium.onnx.json"
PIPER_EN_BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"

if [ -f "${PIPER_EN_ONNX}" ] && [ -f "${PIPER_EN_JSON}" ]; then
    echo "[跳过] Piper 英文模型已存在"
else
    echo "[下载] Piper 英文语音模型..."
    wget -q --show-progress -O "${PIPER_EN_ONNX}" "${PIPER_EN_BASE_URL}/en_US-lessac-medium.onnx"
    wget -q --show-progress -O "${PIPER_EN_JSON}" "${PIPER_EN_BASE_URL}/en_US-lessac-medium.onnx.json"
    echo "[完成] Piper 英文语音模型"
fi

# ── 5. 输出各模型大小和总占用 ─────────────────────────────────────────────────
echo ""
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

# Argos 语言包路径由 argostranslate 管理，单独查询
ARGOS_SIZE=$(python3 -c "
import argostranslate.package as pkg, os
pkgs = pkg.get_installed_packages()
total = 0
for p in pkgs:
    if hasattr(p, 'package_path') and p.package_path:
        for root, dirs, files in os.walk(p.package_path):
            total += sum(os.path.getsize(os.path.join(root, f)) for f in files)
print(f'{total / 1024 / 1024:.1f}M')
" 2>/dev/null || echo "N/A")
printf "  %-30s %s\n" "Argos Translate 语言包" "${ARGOS_SIZE}"

echo "----------------------------------------"
TOTAL_SIZE=$(du -sh "${MODELS_DIR}" 2>/dev/null | cut -f1)
printf "  %-30s %s\n" "models/data/ 总占用" "${TOTAL_SIZE}"
echo "========================================"
echo ""
echo "[完成] 所有模型下载完毕，可拷贝 models/data/ 到 Pi5。"
