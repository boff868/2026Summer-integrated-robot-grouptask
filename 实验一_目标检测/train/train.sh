#!/bin/bash
# 一键训练脚本（Linux 环境）
# 用法:
#   ./train.sh                            # 用默认参数
#   ./train.sh --epochs 200 --imgsz 640   # 自定义参数（会透传给 train.py）
set -e
cd "$(dirname "$0")"

# 检查 Python / pip
if ! command -v python3 >/dev/null; then
    echo "未找到 python3，请先安装 Python 3"
    exit 1
fi

# 首次运行安装依赖（已安装会自动跳过）
python3 -c "import ultralytics" 2>/dev/null || {
    echo "==> 安装 ultralytics ..."
    pip install -q ultralytics
}

echo "==> 开始训练 ..."
python3 train.py "$@"
