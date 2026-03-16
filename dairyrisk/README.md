# 乳制品供应链风险研判智能体

**知识驱动 · 规则增强 · 双模式联动 · 可解释 · 可演示**

[![Version](https://img.shields.io/badge/version-1.2.0-blue.svg)](./docs/答辩材料_v1.2.md)
[![Python](https://img.shields.io/badge/python-3.12+-green.svg)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/node.js-22+-green.svg)](https://nodejs.org/)

> **当前版本**: v1.2.0 Mode A/B 联动版
>
> ⚠️ **系统定位**: 演示原型（PoC），非生产系统
>
> ⚠️ **不宣称**: 真实世界精准预测

## 📋 目录

- [快速开始](#快速开始)
- [安装部署](#安装部署)
- [系统架构](#系统架构)
- [核心功能](#核心功能)
- [项目依赖](#项目依赖)
- [数据说明](#数据说明)
- [开发团队](#开发团队)

## 🚀 快速开始

### 前置要求

- Python 3.12+
- Node.js 22+
- npm 或 pnpm
- MiniMax API Key (可选，用于LLM增强)

### 一键启动

```bash
# 1. 克隆项目
git clone https://github.com/yourusername/dairy-supply-chain-risk.git
cd dairy-supply-chain-risk

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的 MiniMax API Key

# 3. 启动后端
cd backend
pip install -r requirements.txt
python api.py

# 4. 启动前端 (新终端)
cd frontend
npm install
npm run dev

# 5. 访问系统
open http://localhost:3000
```

## 📦 安装部署

### 详细安装步骤

#### 1. 环境准备

```bash
# 检查 Python 版本
python --version  # 需要 3.12+

# 检查 Node.js 版本
node --version    # 需要 22+
npm --version
```

#### 2. 后端部署

```bash
# 进入后端目录
cd backend

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp ../.env.example ../.env
# 编辑 .env 文件，填入必要的 API Key
```

**依赖的知识库项目**:

此项目依赖 `standalone_food_risk_kb` 作为知识库。确保两个项目在同一父目录下：

```
parent/
├── dairy_supply_chain_risk/     # 本项目
└── standalone_food_risk_kb/     # 知识库依赖
```

如果 knowledge 目录已存在，系统会自动使用；否则会尝试从 standalone_food_risk_kb 加载。

#### 3. 前端部署

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install
# 或使用 pnpm: pnpm install

# 配置 API 地址 (如需要)
# 编辑 .env.local 文件:
# NEXT_PUBLIC_API_URL=http://localhost:8000

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
npm start
```

#### 4. 环境变量配置

复制 `.env.example` 为 `.env` 并配置以下变量：

```env
# MiniMax LLM API (可选，用于增强分析)
MINIMAX_API_KEY=your_api_key_here
MINIMAX_MODEL=MiniMax-M2.5
MINIMAX_TEMPERATURE=0.3

# 强制使用 Mock LLM (无API密钥时使用)
# USE_MOCK_LLM=true
```

**获取 API Key**:
- MiniMax: https://www.minimaxi.com/

### Docker 部署 (可选)

```bash
# 构建镜像
docker build -t dairy-risk-agent .

# 运行容器
docker run -p 8000:8000 -p 3000:3000 \
  -e MINIMAX_API_KEY=your_key \
  dairy-risk-agent
```

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent 工作流主链路                         │
│  识别对象 → 取数 → 规则匹配 → 风险计算 → 生成报告              │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   数据层       │    │   规则引擎     │    │   报告生成器   │
│  (6张核心表)   │    │  (GB标准驱动)  │    │  (完整版报告)  │
└───────────────┘    └───────────────┘    └───────────────┘
```

### 双模式工作流

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Mode A     │      │   Mode B     │      │  Mode A+B    │
│  供应链研判   │  +   │  症状驱动    │  =   │   联动研判    │
│  (企业/批次)  │      │  (症状输入)  │      │  (完整链路)   │
└──────────────┘      └──────────────┘      └──────────────┘
       │                     │                     │
       ▼                     ▼                     ▼
  企业风险评分          症状→风险因子         症状→企业→
  传播分析              环节→企业关联         深度核查报告
```

## ✨ 核心功能

### 1. Mode A - 供应链风险研判

输入企业ID或批次号，进行全链路风险评估。

**流程**: 识别对象 → 取数 → GB规则匹配 → 风险计算 → 传播分析 → LLM增强 → 生成报告

### 2. Mode B - 症状驱动研判

输入症状描述，自动推断风险因子和关联企业。

**流程**: 症状提取 → 风险因子推断 → 生产环节定位 → 企业关联 → 监管建议

### 3. Mode A+B - 联动研判

症状驱动 + 供应链核查的完整工作流。

**流程**: 症状分析 → 生成假设 → 定向核查 → 联合报告

## 📊 数据说明

### 数据来源

| 数据表 | 来源 | 说明 |
|--------|------|------|
| enterprise_master | 上海市监局SC证数据 | 20家企业主档 |
| batch_records | 抽检公告生成 | 15个批次记录 |
| inspection_records | 上海市抽检公告 | 15条检验记录 |
| regulatory_events | 公告处罚数据 | 5条监管事件 |
| supply_edges | 公开记录+规则推断 | 25条供应链边 |
| gb_rules | GB标准结构化 | 18条规则 |

### 数据类型占比

- 公开监管数据: ~10%
- 规则推断数据: ~30%
- 模拟补全数据: ~60%

## 📁 项目结构

```
dairy_supply_chain_risk/
├── backend/                 # FastAPI 后端
│   ├── api.py              # 主API入口
│   ├── requirements.txt    # Python依赖
│   └── ...
├── frontend/               # Next.js 前端
│   ├── app/               # 页面路由
│   ├── components/        # React组件
│   ├── package.json       # Node依赖
│   └── ...
├── agent/                  # Agent核心逻辑
│   ├── workflow.py        # Mode A工作流
│   ├── symptom_router.py  # Mode B路由器
│   └── ...
├── data/                   # 数据集
│   ├── merged/            # 主数据集
│   └── schema/            # 数据Schema
├── rules/                  # 规则库
│   └── gb_standards/      # GB标准规则
├── .env.example           # 环境变量模板
├── .gitignore            # Git忽略规则
└── README.md             # 本文件
```

## 🔧 项目依赖

### 后端依赖

```
fastapi>=0.104.0
uvicorn>=0.24.0
pandas>=2.0.0
numpy>=1.24.0
networkx>=3.0
requests>=2.31.0
pydantic>=2.5.0
pyyaml>=6.0
python-dotenv>=1.0.0
```

### 前端依赖

```
next: 14.x
react: 18.x
react-dom: 18.x
typescript: 5.x
tailwindcss: 3.x
```

### 外部知识库

- standalone_food_risk_kb: 风险知识库系统

## 🛡️ 安全说明

### API Key 管理

- **永远不要**将 `.env` 文件提交到 Git
- 项目已配置 `.gitignore` 排除敏感文件
- 生产环境使用环境变量或密钥管理服务

### 数据隐私

- 系统仅使用公开监管数据
- 不涉及个人隐私数据
- 企业数据来源于政府公开信息

## 📝 使用示例

### API 调用示例

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

## 🤝 开发团队

- 项目负责人: [Your Name]
- 技术团队: [Team Members]
- 联系邮箱: [Email]

## 📄 许可证

MIT License - 详见 [LICENSE](./LICENSE) 文件

## 🙏 致谢

- MiniMax 提供 LLM API 支持
- 上海市市场监督管理局公开数据
- GB 国家标准公开信息

---

**免责声明**: 本系统为学术研究原型，研判结果仅供参考，具体执法决策请以现场检查为准。
