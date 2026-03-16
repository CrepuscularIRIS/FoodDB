# 食品安全风险知识库 (Food Risk Knowledge Base)

**分层知识架构 · GB标准驱动 · 风险因子推理 · 证据检索**

[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)

> 独立的食品安全风险知识库系统，支持症状到风险因子的智能推理。
>
> **核心原则**: "先把候选风险因子找对，再去做后面的法规、方法、环节和生成。"

## 📋 目录

- [快速开始](#快速开始)
- [安装部署](#安装部署)
- [知识架构](#知识架构)
- [使用方法](#使用方法)
- [数据资产](#数据资产)
- [API参考](#api参考)

## 🚀 快速开始

### 前置要求

- Python 3.10+
- PyYAML
- (可选) MiniMax API Key - 用于LLM增强

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/yourusername/standalone-food-risk-kb.git
cd standalone-food-risk-kb

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的 API Key (可选)

# 3. 安装依赖
pip install pyyaml python-dotenv requests

# 4. 验证安装
python -c "from backend.router import LayeredFoodRiskKB; kb = LayeredFoodRiskKB(); print('✓ 知识库加载成功')"
```

## 📦 安装部署

### 详细安装步骤

#### 1. 环境准备

```bash
# 检查 Python 版本
python --version  # 需要 3.10+

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows
```

#### 2. 安装依赖

```bash
pip install pyyaml python-dotenv requests

# 如果需要使用 MiniMax LLM 增强
# 确保在 .env 中配置 MINIMAX_API_KEY
```

#### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置以下变量：

```env
# MiniMax LLM API (可选)
MINIMAX_API_KEY=your_api_key_here
MINIMAX_MODEL=MiniMax-M2.5
MINIMAX_TEMPERATURE=0.3
MINIMAX_MAX_TOKENS=4096

# 其他数据源 (可选)
PubMed-API-KEY=your_pubmed_key
openFDA-API-KEY=your_openfda_key
```

**获取 API Key**:
- MiniMax: https://www.minimaxi.com/
- PubMed: https://www.ncbi.nlm.nih.gov/home/develop/api/
- OpenFDA: https://open.fda.gov/apis/

#### 4. 验证安装

```bash
# 测试知识库加载
python backend/cli.py "婴幼儿奶粉发热症状"

# 或运行测试脚本
python test_minimax.py
```

## 🏗️ 知识架构

系统采用**分层知识架构**（非统一RAG桶）：

```
知识层架构（自上而下）:
┌─────────────────────────────────────────┐
│  Rule Layer (knowledge/configs/)        │
│  - GB标准规则 (gb_dairy_rules.yaml)      │
│  - 污染物限制 (gb2762_contaminant_limits.yaml)│
│  - 风险分类 (risk_taxonomy.yaml)         │
│  - 环节规则 (stage_rules.yaml)          │
├─────────────────────────────────────────┤
│  Evidence Layer (knowledge/corpora/)    │
│  - 标准文本语料 (4056条)                 │
│  - 管理措施语料 (110条)                  │
│  - 检测方法语料 (959条)                  │
├─────────────────────────────────────────┤
│  Structured Assets (knowledge/derived/) │
│  - GB标准元数据                         │
│  - 检索块                              │
│  - 提取规则                            │
├─────────────────────────────────────────┤
│  Raw Sources (knowledge/standard_txt/)  │
│  - 69个GB标准文本文件                    │
└─────────────────────────────────────────┘
```

### 数据流

```
standard_txt/*.txt → gb_agent.py → derived/gb_agent_minimax/*.jsonl
                                    ↓
                              methods_layer_rebuilder.py
                                    ↓
                         corpora/rag_corpus_methods_standards_v2.jsonl
```

## 💡 使用方法

### 1. 命令行接口 (CLI)

```bash
# 查询并输出 JSON
python backend/cli.py "婴幼儿奶粉发热症状"

# 格式化输出
python backend/cli.py "婴幼儿奶粉发热症状" --pretty
```

### 2. Python API

```python
from backend.router import LayeredFoodRiskKB

# 初始化知识库
kb = LayeredFoodRiskKB()

# 分析查询
query = "腹泻、发热、腹痛"
signals = kb.analyze_query(query)
print(f"检测到的症状: {signals['symptoms']}")

# 推断风险因子
risk_factors = kb.infer_risk_factors(query, signals, top_k=5)
for risk in risk_factors:
    print(f"- {risk['name']}: {risk['score']}")

# 推断生产环节
stage_candidates = kb.infer_stages(risk_factors, top_k=3)
for stage in stage_candidates:
    print(f"- {stage['stage']}: {stage['score']}")

# 检索证据
evidence = kb.retrieve_evidence(query, signals, risk_factors, stage_candidates)
```

### 3. 作为依赖库使用

在你的项目中：

```python
import sys
sys.path.insert(0, '/path/to/standalone_food_risk_kb')

from backend.router import LayeredFoodRiskKB

# 使用知识库
kb = LayeredFoodRiskKB()
```

## 📊 数据资产

### 风险因子库

- **数量**: 39个风险因子
- **分类**: 微生物、化学污染物、物理危害、过敏原
- **症状映射**: 170个症状关联

### GB标准语料

- **标准文本**: 4056条检索块
- **管理措施**: 110条
- **检测方法**: 959条
- **原始标准**: 69个GB文本文件

### 数据文件

| 文件 | 记录数 | 说明 |
|------|--------|------|
| rag_corpus_standard_txt.jsonl | 4056 | GB标准文本语料 |
| rag_corpus_methods_standards_v2.jsonl | 959 | 检测方法语料 |
| rag_corpus_management_v2.jsonl | 110 | 管理措施语料 |
| risk_taxonomy.yaml | - | 风险分类定义 |
| gb_dairy_rules.yaml | - | GB 2760-2024规则 |

## 🔧 重建知识库

### 重新处理GB标准

```bash
# 完整运行（需要MiniMax API Key）
python backend/gb_agent.py

# 无LLM模式（仅规则提取，更快）
python backend/gb_agent.py --disable-llm

# 仅处理前3个文件（测试）
python backend/gb_agent.py --max-files 3 --disable-llm
```

输出: `knowledge/derived/gb_agent_minimax/`

### 重建方法语料

```bash
python backend/methods_layer_rebuilder.py
```

输出: `knowledge/corpora/rag_corpus_methods_standards_v2.jsonl`

## 📁 项目结构

```
standalone_food_risk_kb/
├── backend/                     # 后端代码
│   ├── router.py               # 主路由器 LayeredFoodRiskKB
│   ├── gb_agent.py             # GB标准处理Agent
│   ├── methods_layer_rebuilder.py
│   ├── cli.py                  # 命令行接口
│   └── ...
├── knowledge/                   # 知识库数据
│   ├── configs/                # 规则层配置
│   │   ├── risk_taxonomy.yaml
│   │   ├── gb_dairy_rules.yaml
│   │   └── stage_rules.yaml
│   ├── corpora/                # 证据层语料
│   │   ├── rag_corpus_standard_txt.jsonl
│   │   ├── rag_corpus_methods_standards_v2.jsonl
│   │   └── rag_corpus_management_v2.jsonl
│   ├── derived/                # 结构化资产
│   │   └── gb_agent_minimax/
│   └── standard_txt/           # 原始标准文本
│       └── *.txt               # 69个GB文件
├── .env.example                # 环境变量模板
├── .gitignore                 # Git忽略规则
└── README.md                  # 本文件
```

## 🔌 API参考

### LayeredFoodRiskKB 类

#### 方法

```python
# 分析查询
analyze_query(query: str, use_llm: bool = False) -> dict

# 推断风险因子
infer_risk_factors(query: str, query_signals: dict, top_k: int = 5) -> list

# 推断生产环节
infer_stages(risk_candidates: list, top_k: int = 5) -> list

# 检索证据
retrieve_evidence(query: str, query_signals: dict,
                  risk_candidates: list, stage_candidates: list) -> dict
```

#### 返回格式

```python
# analyze_query 返回
{
    "symptoms": [{"term": "腹泻", "source": "keyword"}],
    "test_items": [],
    "products": [],
    "processing_steps": []
}

# infer_risk_factors 返回
[
    {
        "risk_factor_id": "microbial_salmonella",
        "name": "沙门氏菌",
        "category": "microbial",
        "score": 2.5,
        "typical_symptoms": ["腹泻", "发热"],
        ...
    }
]
```

## 🛡️ 安全说明

### API Key 管理

- `.env` 文件已配置在 `.gitignore` 中，不会被提交
- 生产环境使用环境变量或密钥管理服务
- 示例配置见 `.env.example`

### 数据安全

- 所有数据来源于公开GB标准
- 不涉及个人隐私信息

## 🤝 集成到主项目

本知识库被以下项目依赖：

- [dairy-supply-chain-risk](https://github.com/yourusername/dairy-supply-chain-risk) - 乳制品供应链风险研判系统

确保两个项目在同一目录下：

```
parent/
├── standalone_food_risk_kb/     # 本知识库
└── dairy_supply_chain_risk/     # 主项目
```

## 📝 许可证

MIT License - 详见 [LICENSE](./LICENSE) 文件

## 🙏 致谢

- GB 国家标准公开信息
- MiniMax 提供 LLM 支持

---

**注意**: 本知识库用于学术研究，风险因子推理结果仅供参考。
