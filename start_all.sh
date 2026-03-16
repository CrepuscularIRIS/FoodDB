#!/bin/bash
#
# 一键启动脚本 - 同时启动后端和前端
# 用于答辩演示
#

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}  乳制品供应链风险研判系统 v1.1${NC}"
echo -e "${BLUE}      一键启动脚本${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# 获取项目根目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# 检查依赖
echo -e "${YELLOW}[1/4] 检查依赖...${NC}"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 python3${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Python3: $(python3 --version)"

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}错误: 未找到 Node.js${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Node.js: $(node --version)"

# 检查 pip 依赖
echo -e "  ${YELLOW}检查 Python 依赖...${NC}"
pip3 install -q pandas pyyaml fastapi uvicorn 2>/dev/null || pip install -q pandas pyyaml fastapi uvicorn 2>/dev/null
echo -e "  ${GREEN}✓${NC} Python 依赖已就绪"

# 检查前端依赖
echo -e "  ${YELLOW}检查前端依赖...${NC}"
if [ ! -d "$PROJECT_DIR/frontend/node_modules" ]; then
    echo -e "  ${YELLOW}  安装前端依赖...${NC}"
    cd "$PROJECT_DIR/frontend"
    npm install
fi
echo -e "  ${GREEN}✓${NC} 前端依赖已就绪"

echo ""

# 启动后端
echo -e "${YELLOW}[2/4] 启动后端服务...${NC}"
cd "$PROJECT_DIR"
python3 backend/api.py > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo -e "  ${GREEN}✓${NC} 后端 PID: $BACKEND_PID"

# 等待后端启动
echo -e "  ${YELLOW}  等待后端启动...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} 后端服务已就绪 (http://localhost:8000)"
        break
    fi
    sleep 1
    if [ $i -eq 30 ]; then
        echo -e "${RED}错误: 后端启动超时${NC}"
        exit 1
    fi
done

echo ""

# 启动前端
echo -e "${YELLOW}[3/4] 启动前端服务...${NC}"
cd "$PROJECT_DIR/frontend"
npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo -e "  ${GREEN}✓${NC} 前端 PID: $FRONTEND_PID"

# 等待前端启动
echo -e "  ${YELLOW}  等待前端启动...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} 前端服务已就绪 (http://localhost:3000)"
        break
    fi
    sleep 1
    if [ $i -eq 30 ]; then
        echo -e "${RED}错误: 前端启动超时${NC}"
        exit 1
    fi
done

echo ""

# 保存 PID
echo "$BACKEND_PID" > "$PROJECT_DIR/logs/backend.pid"
echo "$FRONTEND_PID" > "$PROJECT_DIR/logs/frontend.pid"

# 完成
echo -e "${GREEN}[4/4] 所有服务已启动！${NC}"
echo ""
echo -e "${BLUE}================================${NC}"
echo -e "  前端地址: ${GREEN}http://localhost:3000${NC}"
echo -e "  后端地址: ${GREEN}http://localhost:8000${NC}"
echo -e "  API文档:  ${GREEN}http://localhost:8000/docs${NC}"
echo -e "${BLUE}================================${NC}"
echo ""
echo -e "  ${YELLOW}日志文件:${NC}"
echo -e "    - 后端日志: logs/backend.log"
echo -e "    - 前端日志: logs/frontend.log"
echo ""
echo -e "  ${YELLOW}停止服务:${NC}"
echo -e "    ./stop_all.sh"
echo ""
echo -e "${GREEN}祝答辩顺利！${NC}"
