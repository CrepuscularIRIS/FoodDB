# FoodDB（技术报告版）

> 食品安全风险研判平台（乳制品供应链方向）  
> 当前版本：v1.2（Mode A / Mode B / A+B 联动）  
> 代码仓库：`https://github.com/CrepuscularIRIS/FoodDB`

---

## 1. 项目定位

本项目不是单一“模型推理脚本”，而是一个面向监管与研判场景的工程系统：

- **Mode A（供应链研判）**：输入企业/批次，输出结构化风险报告。
- **Mode B（症状驱动）**：输入症状描述，反推风险因子/环节/关联企业。
- **Mode A+B（联动研判）**：把症状线索和供应链核查融合，形成联合结论。

系统设计强调三个特征：

1. 可解释：规则触发、路径传播、GB依据可追溯。  
2. 可演示：前端大屏、历史案例、流式步骤展示。  
3. 可迭代：规则引擎先落地，后续可逐步替换为GNN/更强模型。

---

## 2. 架构总览

```text
[前端层] Next.js + React + ECharts/D3
    |
    | REST / SSE / WebSocket
    v
[服务层] FastAPI (backend/api.py)
    |
    +-- Mode A: RiskAssessmentAgent (agent/workflow.py)
    +-- Mode B: SymptomRiskRouter (agent/symptom_router.py)
    +-- A+B联动: Orchestrator (agent/orchestrator.py)
    +-- 图数据路由: dairyrisk/api/graph_routes.py
    |
    v
[算法层]
    +-- 弱监督标签: dairyrisk/data/labels.py
    +-- 风险传导: dairyrisk/risk/transmission.py
    +-- 传播模拟: dairyrisk/risk/simulation.py
    +-- 边级风险预测: dairyrisk/risk/edge_predictor.py
    |
    v
[数据/知识层]
    +-- 结构化供应链数据（本地，不随仓库分发）
    +-- RiskKB 知识库语料与规则配置
```

---

## 3. 目录说明（当前主干）

```text
FoodDB/
├── agent/                # Agent工作流（Mode A/B/联动）
├── backend/              # FastAPI服务入口
├── frontend/             # Next.js 前端
├── dairyrisk/            # 风险算法与图分析核心模块
│   ├── api/
│   ├── evaluation/
│   ├── graph/
│   ├── risk/
│   ├── training/
│   └── utils/
├── riskkb/               # 食品安全知识库系统
├── rules/                # 规则引擎与GB规则
├── scripts/              # 训练/评估脚本（保留主链）
├── configs/              # 系统配置
└── README.md
```

说明：

- 历史交付产物、截图、临时报告、legacy 脚本已做过清理。
- 数据集目录默认不入库（见 `.gitignore`）。

---

## 4. 数据策略（重要）

本仓库默认**不上传本地业务数据集**。  
你需要在本地准备数据目录（`DATA_DIR`）或按项目既有目录结构挂载。

### 4.1 为什么不随仓库上传

- 业务敏感（地域/企业相关）
- 数据量大，频繁变化
- 不适合长期公开保留在 Git 历史中

### 4.2 读取优先级（运行时）

`agent/retriever.py` 中按以下顺序解析数据源：

1. `DATA_DIR` 环境变量
2. 项目默认数据目录优先级
3. mock兜底

---

## 5. 核心算法设计

## 5.1 风险传导模型（`dairyrisk/risk/transmission.py`）

### 核心思想

风险沿供应链边传播，不同边类型使用不同传导系数，并考虑距离衰减。

### 基本公式

```text
传导风险 = 源节点风险 × 传导系数 × 衰减因子^(路径长度-1)
```

### 典型功能

- 多跳上下游追溯（例如最多3跳）
- 累积风险计算
- 传播路径记录（用于解释）

---

## 5.2 弱监督标签生成（`dairyrisk/data/labels.py`）

### 核心思想

在真实强标签稀缺条件下，用微生物机理规则生成可训练标签：

- 高温繁殖风险（温度阈值）
- 时长风险（运输时长×温控）
- 洁净度风险（GMP等级）
- 杀菌波动风险（温度稳定性）
- 夏季风险（季节因子）
- 原料污染风险（菌落阈值）

### 融合公式（加权置信融合）

```text
最终风险 = Σ(各层风险 × 权重 × 置信度) / Σ(权重 × 置信度)
```

---

## 5.3 传播模拟引擎（`dairyrisk/risk/simulation.py`）

支持三类关键分析：

1. **蒙特卡洛模拟**：多轮统计分布（默认100轮）
2. **级联失效模拟**：模拟连锁反应
3. **What-if分析**：对比阻断边/增强节点等干预策略

主要用途：

- 评估扩散范围和概率分布
- 用于监管资源预案推演

---

## 5.4 边级风险预测（`dairyrisk/risk/edge_predictor.py`）

当前实现：

- 逻辑回归（可解释）
- 小型神经网络（精度增强）

输入：边类型、边权重、源节点风险、边特征。  
输出：传导概率、风险等级、置信度。

---

## 6. Mode A / Mode B / A+B 业务流程

## 6.1 Mode A（供应链）

流程：

1. 目标识别（企业/批次）
2. 数据检索（上下游、检验、事件）
3. GB规则匹配
4. 风险计算与图分析
5. 案例类比
6. LLM增强分析（可选）
7. 报告输出

## 6.2 Mode B（症状）

流程：

1. 症状解析（可走LLM抽取）
2. 同义词归一化
3. 风险因子映射
4. 环节候选推断
5. 企业候选关联
6. 建议输出

## 6.3 Mode A+B（联动）

流程：

```text
症状输入 -> 风险假设(RiskHypothesis) -> 定向核查 -> 联合报告
```

价值：把社会面症状线索转化为可执法的供应链核查路径。

---

## 7. 接口清单（后端）

主入口：`backend/api.py`

常用接口：

- 健康检查：`GET /health`
- 供应链研判：`POST /assess`
- 供应链流式：`POST /assess_stream`
- 症状研判：`POST /symptom/assess`
- 联动研判：`POST /linked_workflow`
- 图数据：`/api/graph/*`
- 演示案例：`GET /demo_cases`

---

## 8. 前端说明

前端位于 `frontend/`，核心能力：

- 三模式切换（A/B/联动）
- 流式步骤可视化
- 大屏地图网络图、热力图、筛选器
- 联动跳转（诊断完成后一键进大屏并应用筛选）

已做稳定性改造（近期）：

- 端口/CORS统一
- 大屏布局与筛选器交互优化
- 视角状态保留（筛选不重置地图缩放/平移）
- Mode切换状态保留

---

## 9. 本地运行

## 9.1 环境要求

- Python 3.10+
- Node.js 18+（建议 20/22）

## 9.2 安装依赖

```bash
# 后端依赖
pip install -r backend/requirements.txt

# 前端依赖
cd frontend && npm install
```

## 9.3 启动服务

```bash
# 终端1：后端（建议多worker）
python -m uvicorn backend.api:app --host 0.0.0.0 --port 18080 --workers 2

# 终端2：前端
cd frontend
PORT=3000 npm run dev
```

访问：`http://localhost:3000`

---

## 10. 当前边界与后续计划

## 10.1 已落地

- 规则引擎 + 风险传播 + 模拟 + 联动工作流闭环
- 前后端联调可运行
- 可解释报告链路

## 10.2 仍在规划

- 研究级 HeteroGNN 主模型完整落地
- 在线增量学习与持续校准
- 更严格的自动化回归测试体系

---

## 11. 合规与安全提示

- 本项目用于研究与研判支持，不替代法定检验结论。
- 业务敏感数据应通过本地或私有数据源加载，不应提交到公开仓库。
- 生产环境请加鉴权、审计日志、脱敏策略与限流。

---

## 12. 维护建议（仓库治理）

- 保持“代码仓库”和“数据仓库”分离。
- 交付报告/截图建议放 release 附件，不入主分支。
- 所有临时脚本优先放 `tools/` 并设置生命周期。

