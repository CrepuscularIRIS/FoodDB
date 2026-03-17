#!/bin/bash
# start_all_services.sh - 启动前后端服务

echo "=========================================="
echo "启动乳制品供应链风险研判系统"
echo "=========================================="

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到python3${NC}"
    exit 1
fi

# 检查Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}错误: 未找到node${NC}"
    exit 1
fi

# 启动后端服务
echo ""
echo -e "${YELLOW}[1/2] 正在启动后端服务...${NC}"
echo "后端地址: http://localhost:8000"
echo "API文档: http://localhost:8000/docs"

# 在新终端窗口启动后端（如果可用）
if command -v gnome-terminal &> /dev/null; then
    gnome-terminal -- bash -c "cd '$SCRIPT_DIR' && python3 start_backend.py; exec bash" 2>/dev/null || \
    xterm -e "cd '$SCRIPT_DIR' && python3 start_backend.py" 2>/dev/null || \
    python3 start_backend.py &
elif command -v xterm &> /dev/null; then
    xterm -e "cd '$SCRIPT_DIR' && python3 start_backend.py" 2>/dev/null || \
    python3 start_backend.py &
else
    python3 start_backend.py &
fi

BACKEND_PID=$!
echo -e "${GREEN}✓ 后端服务已启动 (PID: $BACKEND_PID)${NC}"

# 等待后端启动
sleep 3

# 启动前端服务
echo ""
echo -e "${YELLOW}[2/2] 正在启动前端服务...${NC}"
echo "前端地址: http://localhost:3000"

cd "$SCRIPT_DIR/frontend"

# 检查node_modules
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}正在安装前端依赖...${NC}"
    npm install
fi

# 启动前端
npm run dev &
FRONTEND_PID=$!
echo -e "${GREEN}✓ 前端服务已启动 (PID: $FRONTEND_PID)${NC}"

echo ""
echo "=========================================="
echo -e "${GREEN}所有服务已启动！${NC}"
echo "=========================================="
echo ""
echo "访问地址:"
echo "  - 前端界面: http://localhost:3000/dashboard/simple"
echo "  - 后端API:  http://localhost:8000"
echo "  - API文档:  http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo ""

# 等待信号
trap "echo ''; echo '正在停止服务...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT
wait
