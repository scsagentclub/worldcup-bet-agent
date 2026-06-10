#!/bin/bash
# 世界杯竞猜 Agent — 自更新守护脚本
#
# 用法:
#   chmod +x run_agent.sh
#   ./run_agent.sh
#
# 功能:
# - 每次启动前自动 git pull 更新最新 skill/agent 代码
# - Agent 出错崩溃后自动重新拉取更新并重启
# - 适合部署在远端服务器长期运行

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENT_SCRIPT="$REPO_DIR/agent.py"
INTERVAL="${AGENT_INTERVAL:-1800}"

echo "========================================"
echo "🦞 世界杯竞猜 Agent 自更新守护启动"
echo "仓库目录: $REPO_DIR"
echo "检查间隔: ${INTERVAL}秒"
echo "========================================"

while true; do
    echo ""
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 检查更新..."

    # 进入仓库目录，拉取最新代码
    cd "$REPO_DIR"
    if git pull origin master 2>/dev/null; then
        echo "✅ 代码已是最新或已更新"
    else
        echo "⚠️ git pull 失败，使用本地代码继续"
    fi

    # 确保依赖已安装
    if ! python3 -c "import requests" 2>/dev/null; then
        echo "📦 安装依赖 requests..."
        pip3 install requests -q || pip install requests -q
    fi

    # 运行 Agent
    echo "🚀 启动 Agent..."
    if python3 "$AGENT_SCRIPT" --strategy hot; then
        echo "✅ 本次执行成功"
    else
        echo "❌ Agent 出错，5分钟后重新拉取更新并重试..."
        sleep 300
        continue
    fi

    echo "😴 休眠 ${INTERVAL} 秒后下次检查..."
    sleep "$INTERVAL"
done
