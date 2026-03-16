#!/bin/bash
#
# 一键验证脚本 - 验证系统可正常运行
# 用于答辩前检查
#

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}  系统验证脚本${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

PASS=0
FAIL=0

# 检查函数
check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASS++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAIL++))
}

check_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

# 1. 检查文件结构
echo -e "${YELLOW}[1/6] 检查文件结构...${NC}"
[ -f "backend/api.py" ] && check_pass "后端API文件存在" || check_fail "后端API文件缺失"
[ -f "run_demo.py" ] && check_pass "演示脚本存在" || check_fail "演示脚本缺失"
[ -f "start_all.sh" ] && check_pass "启动脚本存在" || check_fail "启动脚本缺失"
[ -d "frontend" ] && check_pass "前端目录存在" || check_fail "前端目录缺失"
[ -d "data/release_v1_1" ] && check_pass "答辩数据已冻结" || check_fail "答辩数据未冻结"
echo ""

# 2. 检查数据文件
echo -e "${YELLOW}[2/6] 检查数据文件...${NC}"
for file in enterprise_master.csv batch_records.csv inspection_records.csv regulatory_events.csv supply_edges.csv gb_rules.csv; do
    if [ -f "data/release_v1_1/$file" ]; then
        check_pass "数据文件: $file"
    else
        check_fail "数据文件缺失: $file"
    fi
done
echo ""

# 3. 检查依赖
echo -e "${YELLOW}[3/6] 检查依赖...${NC}"
python3 -c "import pandas" 2>/dev/null && check_pass "pandas 已安装" || check_fail "pandas 未安装"
python3 -c "import yaml" 2>/dev/null && check_pass "pyyaml 已安装" || check_fail "pyyaml 未安装"
python3 -c "import fastapi" 2>/dev/null && check_pass "fastapi 已安装" || check_fail "fastapi 未安装"
python3 -c "import uvicorn" 2>/dev/null && check_pass "uvicorn 已安装" || check_fail "uvicorn 未安装"
command -v node >/dev/null 2>& && check_pass "Node.js 已安装 ($(node --version))" || check_fail "Node.js 未安装"
echo ""

# 4. 运行后端测试
echo -e "${YELLOW}[4/6] 运行后端测试...${NC}"
python3 run_demo.py --case case1 > /tmp/case1_test.log 2>&1
if [ $? -eq 0 ]; then
    check_pass "案例1 (低温奶冷链异常) 通过"
else
    check_fail "案例1 失败"
fi

python3 run_demo.py --case case2 > /tmp/case2_test.log 2>&1
if [ $? -eq 0 ]; then
    check_pass "案例2 (常温奶批次检验) 通过"
else
    check_fail "案例2 失败"
fi

python3 run_demo.py --case case3 > /tmp/case3_test.log 2>&1
if [ $? -eq 0 ]; then
    check_pass "案例3 (供应商联动风险) 通过"
else
    check_fail "案例3 失败"
fi
echo ""

# 5. 检查报告生成
echo -e "${YELLOW}[5/6] 检查报告文件...${NC}"
if [ -d "reports" ]; then
    REPORT_COUNT=$(ls -1 reports/*.md 2>/dev/null | wc -l)
    if [ $REPORT_COUNT -ge 3 ]; then
        check_pass "报告文件已生成 ($REPORT_COUNT 份)"
    else
        check_fail "报告文件不足 (仅 $REPORT_COUNT 份)"
    fi
else
    check_fail "reports 目录不存在"
fi
echo ""

# 6. 检查API健康
echo -e "${YELLOW}[6/6] 检查API服务...${NC}"
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    check_pass "后端API服务运行中"
    HEALTH=$(curl -s http://localhost:8000/health)
    check_info "健康状态: $HEALTH"
else
    check_info "后端API服务未运行 (运行 ./start_all.sh 启动)"
fi
echo ""

# 汇总
echo -e "${BLUE}================================${NC}"
echo -e "  验证完成"
echo -e "${BLUE}================================${NC}"
echo -e "  ${GREEN}通过: $PASS${NC}"
echo -e "  ${RED}失败: $FAIL${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✓ 所有检查通过，系统可正常运行！${NC}"
    echo ""
    echo -e "  快速启动: ${YELLOW}./start_all.sh${NC}"
    echo -e "  查看演示: ${YELLOW}http://localhost:3000${NC}"
    exit 0
else
    echo -e "${RED}✗ 存在 $FAIL 个问题，请修复后再试${NC}"
    exit 1
fi
