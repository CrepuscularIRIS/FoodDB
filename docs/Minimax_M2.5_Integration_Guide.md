# Minimax M2.5 LLM Integration Guide

**版本**: v1.2.0
**更新日期**: 2026-03-13
**状态**: ✅ 已完成

---

## 一、功能概述

本系统已实现 Minimax M2.5 LLM API 集成，用于生成智能风险研判报告。结合异构图建模和真实案例库，提供更专业、更可解释的风险分析。

### 核心能力

| 能力 | 说明 | 状态 |
|------|------|------|
| LLM智能报告 | Minimax M2.5生成专业风险分析报告 | ✅ |
| 异构图建模 | 5类节点（牧场/乳企/物流/仓储/零售） | ✅ |
| 真实案例库 | 6个完整案例，覆盖5种风险类型 | ✅ |
| 混合架构 | 规则评分+LLM增强 | ✅ |
| 模拟模式 | 无需API密钥即可测试 | ✅ |

---

## 二、架构设计

### 2.1 混合架构流程

```
用户查询
    ↓
数据检索 (Retriever)
    ↓
规则评分引擎 (Engine)
    ↓
风险分数 + 触发规则
    ↓
┌─────────────────────────────────────────────────────────────┐
│                      LLM增强层                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 异构图上下文 │  │ 相似案例检索 │  │ Prompt构建   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                           ↓                                  │
│                    Minimax M2.5 API                          │
│                           ↓                                  │
│                    AI深度分析报告                            │
└─────────────────────────────────────────────────────────────┘
    ↓
综合报告输出
```

### 2.2 模块结构

```
agent/
├── llm_client.py          # Minimax M2.5 API客户端
├── heterogeneous_graph.py # 异构图建模
├── case_mapper.py         # 真实案例库
├── enhanced_reporter.py   # 增强报告生成器
└── reporter.py           # 基础报告生成器
```

---

## 三、Minimax M2.5 API 配置

### 3.1 获取API密钥

1. 访问 [Minimax开放平台](https://www.minimaxi.com/)
2. 注册账号并创建应用
3. 获取 `API Key` 和 `Group ID`

### 3.2 环境变量配置

```bash
export MINIMAX_API_KEY="your-api-key-here"
export MINIMAX_GROUP_ID="your-group-id-here"
export MINIMAX_MODEL="abab6.5s-chat"  # 可选，默认abab6.5s-chat
export MINIMAX_TEMPERATURE="0.3"       # 可选，默认0.3
export MINIMAX_MAX_TOKENS="4096"       # 可选，默认4096
```

### 3.3 配置文件方式（可选）

创建 `.env` 文件：

```
MINIMAX_API_KEY=your-api-key-here
MINIMAX_GROUP_ID=your-group-id-here
```

### 3.4 模型配置说明

**重要**: Minimax M2.5 是模型系列名称，实际API调用使用以下模型ID：

| 模型名称 | API Model ID | 说明 |
|----------|-------------|------|
| Minimax M2.5 (标准版) | `abab6.5-chat` | 通用对话，4000 tokens |
| Minimax M2.5 (精简版) | `abab6.5s-chat` | 更快更便宜，默认使用 |

推荐配置：
- Model ID: `abab6.5s-chat`（默认）
- Temperature: 0.3 (低风险研判需要一致性)
- Max tokens: 4096

---

## 四、使用指南

### 4.1 快速测试（无需API密钥）

系统内置 Mock LLM，无需配置即可测试：

```bash
python run_enhanced_demo.py --demo all
```

### 4.2 生成特定案例报告

```bash
# 使用Mock LLM
python run_enhanced_demo.py --demo report --case-id CASE-001

# 使用真实Minimax LLM
export MINIMAX_API_KEY="your-key"
python run_enhanced_demo.py --demo report --case-id CASE-001 --use-llm
```

### 4.3 代码集成示例

```python
from agent.enhanced_reporter import EnhancedReportGenerator

# 初始化生成器（使用Mock模式）
generator = EnhancedReportGenerator(
    use_llm=True,
    use_mock_llm=True  # 设为False使用真实API
)

# 生成基于案例的报告
report = generator.generate_report_with_demo_case("CASE-002")

# 转换为Markdown
markdown = generator.format_enhanced_report_to_markdown(report)
print(markdown)
```

### 4.4 完整工作流示例

```python
from agent.llm_client import get_llm_client
from agent.heterogeneous_graph import create_sample_heterogeneous_graph
from agent.case_mapper import get_repository
from agent.enhanced_reporter import EnhancedReportGenerator

# 1. 初始化组件
llm_client = get_llm_client(use_mock=True)
graph = create_sample_heterogeneous_graph()
case_repo = get_repository()

# 2. 创建增强报告生成器
generator = EnhancedReportGenerator(
    use_llm=True,
    use_mock_llm=True,
    graph=graph
)

# 3. 获取相似案例
similar_cases = case_repo.get_similar_cases("microbial", "high", limit=2)

# 4. 生成LLM增强内容
response = llm_client.generate_risk_report(
    target_name="测试批次",
    target_type="batch",
    risk_level="high",
    risk_score=75,
    triggered_rules=[...],
    evidence={...},
    similar_cases=[c.to_dict() for c in similar_cases]
)

if response.success:
    print(response.content)
```

---

## 五、真实案例库

### 5.1 案例列表

| 案例ID | 案例名称 | 风险类型 | 年份 | 企业 |
|--------|---------|---------|------|------|
| CASE-001 | 雀巢ARA原料蜡样芽孢杆菌毒素召回 | microbial | 2026 | 雀巢集团 |
| CASE-002 | 光明莫斯利安冷链受热包装膨胀 | cold_chain | 2022 | 光明乳业 |
| CASE-003 | 雅培喜康优香兰素违规添加 | additive | 2021 | 雅培贸易 |
| CASE-004 | 麦趣尔丙二醇非法添加 | cross_contamination | 2022 | 麦趣尔集团 |
| CASE-005 | 明治醇壹兽药磺胺残留 | veterinary_drug | 2023 | 明治乳业 |
| CASE-006 | 卡士餐后一小时酵母超标 | microbial | 2022 | 卡士酸奶 |

### 5.2 案例数据结构

每个案例包含以下信息：
- 基本信息：时间、地点、企业、产品、批次
- 风险分类：风险类型、风险等级
- 详细分析：直接原因、根因、调查路径
- 监管建议：抽检重点、检测项目、整治措施
- 影响评估：波及范围、人群影响、经济损失

### 5.3 获取案例信息

```python
from agent.case_mapper import get_repository

repo = get_repository()

# 获取单个案例
case = repo.get_case("CASE-001")
print(case.case_name)
print(case.root_cause)

# 按风险类型获取
cases = repo.get_cases_by_risk_type("microbial")

# 获取相似案例
similar = repo.get_similar_cases("cold_chain", "medium", limit=3)

# 获取LLM上下文
context = repo.get_llm_context_for_case("CASE-001")
```

---

## 六、异构图建模

### 6.1 节点类型

| 类型 | 英文 | 说明 |
|------|------|------|
| 牧场 | FARM | 原奶供应商 |
| 乳企 | PROCESSOR | 乳制品加工厂 |
| 物流 | LOGISTICS | 冷链物流服务商 |
| 仓储 | WAREHOUSE | 冷链仓储中心 |
| 零售 | RETAIL | 终端零售点 |

### 6.2 边类型

| 类型 | 说明 | 示例 |
|------|------|------|
| SUPPLY | 原料供应 | 牧场→乳企 |
| TRANSPORT | 产品运输 | 乳企→物流→仓储 |
| SALE | 销售关系 | 仓储→零售 |
| CONTRACT | 长期合同 | 乳企↔牧场 |

### 6.3 使用示例

```python
from agent.heterogeneous_graph import (
    HeterogeneousSupplyChainGraph,
    NodeType,
    EdgeType
)

# 创建图
graph = HeterogeneousSupplyChainGraph()

# 添加节点
graph.add_node(
    node_id="FARM-001",
    node_type=NodeType.FARM,
    name="光明牧业金山种奶牛场",
    attributes={"scale": "large"}
)

# 添加边
graph.add_edge(
    edge_id="EDGE-001",
    source_id="FARM-001",
    target_id="PROC-001",
    edge_type=EdgeType.SUPPLY,
    weight=1.0
)

# 获取上游供应商
upstream = graph.get_upstream_network("PROC-001", depth=2)

# 获取下游客户
downstream = graph.get_downstream_network("PROC-001", depth=2)

# 计算网络指标
metrics = graph.calculate_network_metrics()
```

### 6.4 从真实数据构建

```python
from agent.heterogeneous_graph import RealDataGraphBuilder

builder = RealDataGraphBuilder()
graph = builder.build_graph_from_real_data(
    processing_plants_file="path/to/乳制品加工厂.xlsx",
    supply_chain_nodes_file="path/to/供应链节点.csv"
)
```

---

## 七、Prompt设计

### 7.1 System Prompt

```
你是一位资深的乳制品供应链风险评估专家，拥有丰富的食品安全监管经验。

你的任务是基于结构化数据生成专业的风险研判报告。报告需要：
1. 使用正式的监管语言和专业术语
2. 引用相关的GB国家标准条款
3. 提供具体的、可操作的监管建议
4. 结合历史案例进行类比分析
5. 识别潜在的风险传导路径

请确保报告内容准确、客观、有洞察力，能够为监管决策提供有价值的参考。
```

### 7.2 User Prompt结构

Prompt包含以下结构化数据：
- 评估对象信息（名称、类型、风险等级、评分）
- 触发的风险规则
- 相关检验记录
- 相关监管事件
- 供应链网络信息
- 相似历史案例

### 7.3 输出格式

LLM生成的报告包含以下章节：
1. **执行摘要** - 风险等级判定及核心原因
2. **深度风险分析** - 基于规则的详细分析
3. **根因分析** - 问题的根本原因推断
4. **法规依据** - 引用的GB标准条款
5. **监管建议** - 立即/短期/长期行动项

---

## 八、测试与验证

### 8.1 运行测试

```bash
# 测试LLM客户端
python run_enhanced_demo.py --demo llm

# 测试异构图
python run_enhanced_demo.py --demo graph

# 测试案例库
python run_enhanced_demo.py --demo cases

# 生成所有案例报告
python run_enhanced_demo.py --demo all-reports
```

### 8.2 验证清单

- [ ] LLM客户端配置正确
- [ ] Mock模式可以生成报告
- [ ] 异构图正确加载真实数据
- [ ] 6个案例都可以生成报告
- [ ] 报告包含历史案例类比
- [ ] 报告包含供应链网络分析
- [ ] （可选）真实LLM API调用成功

---

## 九、故障排除

### 9.1 API调用失败

**现象**: `API request failed` 或 `timeout`

**解决**:
1. 检查 `MINIMAX_API_KEY` 和 `MINIMAX_GROUP_ID` 是否正确设置
2. 检查网络连接
3. 增加超时时间：`export MINIMAX_TIMEOUT=120`
4. 使用Mock模式测试：`use_mock_llm=True`

### 9.2 真实数据加载失败

**现象**: `Failed to build graph from real data`

**解决**:
1. 检查文件路径是否正确
2. 确保已安装依赖：`pip install pandas openpyxl`
3. 系统会自动回退到样本图

### 9.3 报告生成缓慢

**现象**: LLM报告生成时间超过30秒

**解决**:
1. 这是正常现象，LLM调用需要10-30秒
2. 可以通过缓存相似案例结果来优化
3. 使用更快的模型：`abab6.5s-chat` 比 `abab6.5-chat` 更快

---

## 十、后续优化建议

### 10.1 v2.0路线图

| 阶段 | 功能 | 优先级 |
|------|------|--------|
| 短期 | 集成更多案例（10+） | P1 |
| 短期 | 异构图HGNN替换规则引擎 | P1 |
| 中期 | MAPPO优化抽检决策 | P2 |
| 中期 | ST-GNN时空风险预测 | P2 |
| 长期 | 真实数据比例提升至50% | P3 |

### 10.2 性能优化

- 实现LLM响应缓存
- 异步API调用
- 图数据预计算
- 案例向量索引

---

## 附录：API参考

### MinimaxLLMClient

```python
class MinimaxLLMClient:
    def __init__(self, config: Optional[LLMConfig] = None)
    def is_configured(self) -> bool
    def generate_risk_report(...) -> LLMResponse
```

### EnhancedReportGenerator

```python
class EnhancedReportGenerator:
    def __init__(self, use_llm=True, use_mock_llm=False, graph=None)
    def generate_enhanced_report(...) -> RiskAssessmentReport
    def generate_report_with_demo_case(case_id) -> RiskAssessmentReport
    def format_enhanced_report_to_markdown(report) -> str
```

### CaseRepository

```python
class CaseRepository:
    def get_case(case_id: str) -> Optional[RiskCase]
    def get_cases_by_risk_type(risk_type: str) -> List[RiskCase]
    def get_similar_cases(risk_type, risk_level, limit=3) -> List[RiskCase]
    def get_llm_context_for_case(case_id: str) -> str
```

---

**文档结束**
