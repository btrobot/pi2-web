#!/usr/bin/env bash
# scripts/setup_env.sh
# Pi5 离线翻译系统环境安装脚本
# 适用平台: Raspberry Pi 5 (Debian Bookworm ARM64)
# 幂等设计: 重复运行安全

set -e

# 脚本所在目录，用于定位项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

echo "=== Pi5 离线翻译系统环境安装脚本 ==="
echo "项目根目录: ${PROJECT_ROOT}"

# ─────────────────────────────────────────
# 1. 安装系统依赖
# ─────────────────────────────────────────
echo ""
echo "[1/4] 安装系统依赖..."

sudo apt-get update -qq

# 逐个检查并安装，确保幂等
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
        echo "  已安装: ${pkg}"
    else
        echo "  安装中: ${pkg}"
        sudo apt-get install -y -qq "${pkg}"
    fi
done

echo "  系统依赖安装完成。"

# ─────────────────────────────────────────
# 2. 创建 Python 虚拟环境
# ─────────────────────────────────────────
echo ""
echo "[2/4] 配置 Python 虚拟环境..."

if [ -d "${VENV_DIR}" ]; then
    echo "  虚拟环境已存在: ${VENV_DIR}"
else
    echo "  创建虚拟环境: ${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
fi

# 激活虚拟环境
# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

echo "  升级 pip..."
pip install --upgrade pip -q

# ─────────────────────────────────────────
# 3. 安装 Python 依赖
# ─────────────────────────────────────────
echo ""
echo "[3/4] 安装 Python 依赖 (requirements.txt)..."

REQUIREMENTS="${PROJECT_ROOT}/requirements.txt"

if [ ! -f "${REQUIREMENTS}" ]; then
    echo "  错误: 未找到 ${REQUIREMENTS}"
    exit 1
fi

pip install -r "${REQUIREMENTS}" -q
echo "  Python 依赖安装完成。"

# ─────────────────────────────────────────
# 4. 配置 ALSA 默认声卡为 USB 麦克风
# ─────────────────────────────────────────
echo ""
echo "[4/4] 配置 ALSA USB 麦克风..."

ASOUNDRC="${HOME}/.asoundrc"

# 仅在文件不存在时写入，避免覆盖用户自定义配置
if [ -f "${ASOUNDRC}" ]; then
    echo "  ~/.asoundrc 已存在，跳过写入（如需重置请手动删除后重新运行）。"
else
    cat > "${ASOUNDRC}" << 'EOF'
# ~/.asoundrc — ALSA 默认声卡配置
# 将 USB 麦克风设为默认录音设备
# card 1 对应第一块 USB 音频设备（可通过 arecord -l 确认编号）

pcm.!default {
    type asym
    playback.pcm {
        type plug
        slave.pcm "hw:0,0"
    }
    capture.pcm {
        type plug
        slave.pcm "hw:1,0"
    }
}

ctl.!default {
    type hw
    card 0
}
EOF
    echo "  已写入 ${ASOUNDRC}"
    echo "  提示: 如 USB 麦克风卡号不是 1，请编辑 ~/.asoundrc 中的 hw:1,0。"
    echo "        运行 'arecord -l' 查看实际卡号。"
fi

# ─────────────────────────────────────────
# 完成
# ─────────────────────────────────────────
echo ""
echo "=== 安装完成 ==="
echo "激活虚拟环境: source ${VENV_DIR}/bin/activate"
echo "启动应用:     python main.py"
