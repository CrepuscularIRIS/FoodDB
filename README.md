# FoodDB - 食品安全风险研判系统

[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/node.js-22+-green.svg)](https://nodejs.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)

> **FoodDB** 是一个综合性的食品安全风险研判平台，包含知识库系统和供应链风险研判系统。

## 📦 项目组成

本项目包含两个子系统：

| 子系统 | 目录 | 说明 |
|--------|------|------|
| **RiskKB** | [`riskkb/`](./riskkb) | 食品安全风险知识库 - 症状到风险因子的智能推理 |
| **DairyRisk** | [`dairyrisk/`](./dairyrisk) | 乳制品供应链风险研判 - 双模式联动研判系统 |

## 🚀 快速开始

### 前置要求

- Python 3.12+
- Node.js 22+
- npm 或 pnpm
- MiniMax API Key (可选)

### 一键安装

```bash
# 1. 克隆项目
git clone https://github.com/CrepuscularIRIS/FoodDB.git
cd FoodDB

# 2. 安装知识库 (RiskKB)
cd riskkb
cp .env.example .env
pip install pyyaml python-dotenv requests
cd ..

# 3. 安装后端 (DairyRisk)
cd dairyrisk/backend
pip install -r requirements.txt
cp ../.env.example ../.env
cd ../frontend
npm install
cd ../..

# 4. 启动系统
cd dairyrisk
./start_all.sh  # 或手动启动前后端
```

## 📂 目录结构

```
FoodDB/
├── README.md              # 本文件
├── LICENSE                # MIT许可证
├── .gitignore            # Git忽略规则
├── riskkb/               # 食品安全风险知识库
│   ├── README.md
│   ├── backend/          # Python核心库
│   ├── knowledge/        # 知识库数据
│   └── ...
└── dairyrisk/            # 乳制品供应链风险研判
    ├── README.md
    ├── backend/          # FastAPI后端
    ├── frontend/         # Next.js前端
    ├── agent/            # Agent工作流
    └── ...
```

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        FoodDB 平台                           │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐        ┌─────────────────────────────┐ │
│  │   RiskKB        │        │      DairyRisk              │ │
│  │   知识库系统     │◄──────►│   供应链风险研判系统         │ │
│  │                 │        │                             │ │
│  │ • 风险因子推理   │        │ • Mode A: 企业/批次研判      │ │
│  │ • GB标准检索    │        │ • Mode B: 症状驱动研判       │ │
│  │ • 症状-风险映射 │        │ • Mode A+B: 联动研判         │ │
│  └─────────────────┘        └─────────────────────────────┘ │
│           │                            │                    │
│           └────────────┬───────────────┘                    │
│                        ▼                                    │
│              ┌─────────────────┐                           │
│              │   统一数据层     │                           │
│              │  (30家企业数据)  │                           │
│              └─────────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

## 💡 核心功能

### RiskKB - 知识库系统

- **风险因子推理**: 症状 → 风险因子 Top-K
- **GB标准检索**: 4056条标准语料
- **生产环节推断**: 风险因子 → 生产环节
- **证据链构建**: 标准依据 + 检测方法

### DairyRisk - 研判系统

- **Mode A - 供应链研判**: 企业/批次级风险评估
- **Mode B - 症状驱动**: 症状描述 → 关联企业
- **Mode A+B - 联动研判**: 完整工作流整合
- **LLM增强**: Minimax M2.5 深度分析

## 📊 数据规模

| 数据类型 | 规模 | 说明 |
|---------|------|------|
| 企业数据 | 30家 | 上海乳制品企业 |
| 风险因子 | 39个 | 微生物/化学/物理 |
| 症状映射 | 170个 | 症状-风险关联 |
| GB语料 | 4056条 | 标准文本检索块 |
| 检测方法 | 959条 | 检测标准 |

## 🛠️ 详细安装指南

### 安装 RiskKB (知识库)

```bash
cd riskkb

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install pyyaml python-dotenv requests

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 MiniMax API Key (可选)

# 验证安装
python -c "from backend.router import LayeredFoodRiskKB; kb = LayeredFoodRiskKB(); print('✓ 知识库加载成功')"
```

### 安装 DairyRisk (研判系统)

```bash
cd dairyrisk

# 后端安装
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..

# 前端安装
cd frontend
npm install
cd ..

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 API Key
```

### 启动系统

```bash
# 方法1: 使用启动脚本
cd dairyrisk
./start_all.sh

# 方法2: 手动启动
cd dairyrisk/backend
python api.py &
cd ../frontend
npm run dev &

# 访问系统
open http://localhost:3000
```

## 🔧 环境变量配置

### RiskKB 配置 (`riskkb/.env`)

```env
# MiniMax API (可选)
MINIMAX_API_KEY=your_key_here
MINIMAX_MODEL=MiniMax-M2.5

# 其他数据源 (可选)
PubMed-API-KEY=your_key
openFDA-API-KEY=your_key
```

### DairyRisk 配置 (`dairyrisk/.env`)

```env
# MiniMax API (可选，用于LLM增强)
MINIMAX_API_KEY=your_key_here
MINIMAX_MODEL=MiniMax-M2.5

# 强制使用Mock模式 (无API密钥时)
# USE_MOCK_LLM=true
```

**获取 API Key**:
- MiniMax: https://www.minimaxi.com/

## 📝 使用示例

### 使用 RiskKB

```python
from riskkb.backend.router import LayeredFoodRiskKB

kb = LayeredFoodRiskKB()

# 症状分析
signals = kb.analyze_query("腹泻、发热")
print(signals['symptoms'])

# 风险因子推断
risks = kb.infer_risk_factors("腹泻、发热", signals)
for r in risks:
    print(f"{r['name']}: {r['score']}")
```

### 使用 DairyRisk API

```bash
# Mode A - 企业风险研判
curl -X POST http://localhost:8000/assess \
  -H "Content-Type: application/json" \
  -d '{"query": "ENT-0001"}'

# Mode B - 症状驱动
curl -X POST http://localhost:8000/symptom/assess \
  -H "Content-Type: application/json" \
  -d '{"query": "腹泻、发热"}'

# Mode A+B - 联动研判
curl -X POST http://localhost:8000/linked_workflow \
  -H "Content-Type: application/json" \
  -d '{"symptom_description": "儿童腹泻", "location_hint": "上海"}'
```

## 🛡️ 安全说明

### API Key 管理

- ✅ `.env` 文件已配置在 `.gitignore` 中
- ✅ 示例配置见 `.env.example`
- ✅ 生产环境使用环境变量
- ❌ 永远不要提交真实 API Key 到 Git

### 验证配置

```bash
# 检查是否有敏感文件将被提交
git status
git diff --cached --name-only

# 确保 .env 文件被正确忽略
git check-ignore -v riskkb/.env
git check-ignore -v dairyrisk/.env
```

## 📖 文档

- [RiskKB 详细文档](./riskkb/README.md)
- [DairyRisk 详细文档](./dairyrisk/README.md)
- [API 接口文档](./dairyrisk/API_CONTRACT.md)

## 🤝 项目依赖关系

```
DairyRisk
    │
    ├── RiskKB (知识库依赖)
    │
    └── 外部 API
        └── MiniMax LLM (可选)
```

## 📝 开发计划

- [x] 知识库系统 (RiskKB)
- [x] 供应链研判 (Mode A)
- [x] 症状驱动研判 (Mode B)
- [x] 联动研判 (Mode A+B)
- [ ] HGNN 图神经网络
- [ ] MAPPO 抽检优化
- [ ] 实时数据接入

## 📄 许可证

MIT License - 详见 [LICENSE](./LICENSE) 文件

## 🙏 致谢

- GB 国家标准公开信息
- MiniMax 提供 LLM 支持
- 上海市市场监督管理局公开数据

---

**免责声明**: 本系统为学术研究原型，研判结果仅供参考，具体执法决策请以现场检查为准。
