#!/bin/bash
set -e

echo "=== UptimeGuard 启动 ==="

if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

source venv/bin/activate
echo "安装依赖..."
pip install -r requirements.txt -q

echo ""
echo "启动服务..."
echo "访问地址: http://localhost:8000"
echo "按 Ctrl+C 停止"
echo ""

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
