# ARCHITECT

## 1. 项目定位

本项目定位为“可审计的异构图监管排序引擎”，用于乳制品供应链风险研判（Mode A）。
它不是机理精确预测系统，而是把定性监管知识转换为可执行的定量排序与资源分配策略。

核心交付目标：

1. 初始筛选：避免随机抽检，先查最值得查的节点/边。
2. 不确定性量化：区分“高风险且证据足”与“高不确定需探索”。
3. 预算分配：在成本约束下提升单位抽检收益。

## 2. 总体架构

系统为 6 层架构：

1. 数据层
2. 异构图层
3. 公式引擎层（定性 -> 定量）
4. 决策层（排序/预算）
5. LLM 解释层
6. 前端可视化层

数据流主链路：

`原始节点/边 + 补充特征` -> `异构图` -> `risk/credibility/uncertainty` -> `priority` -> `预算策略` -> `LLM解释` -> `前端图谱与报告`

## 3. 数据层设计

### 3.1 已接入原始数据

来自 `dataset_3_24` 的核心输入：

1. `enterprise_node.csv`（节点主档）
2. `graph_edges_reformatted_with_product.csv`（供应链边，含品类）

### 3.2 生成补充数据（为“可评分”服务）

仅靠图结构无法完成风险排序，因此在 `scripts/modela_v2_pipeline.py` 中补充生成：

1. 节点画像特征（抽检、冷链、证照、舆情、历史事件等代理特征）
2. 节点 7 维风险概率向量（七大风险类）
3. 边 7 维风险概率向量
4. Top5 标签与规则命中信号
5. 预算相关特征（抽检成本、覆盖收益基线）

输出目录：`data/modela_v2/`

### 3.3 可用性策略

针对“小企业数据少、大企业数据多”的场景：

1. 缺失字段不直接判高风险，只进入不确定性分支。
2. 采用 peer-group 相对比较（`node_type x scale`，样本足够时加 `region`）。
3. 用稳健归一化（winsorize + robust scale）抑制极端值。

## 4. 异构图层设计

### 4.1 图模式

节点类型：

1. 原奶供应商
2. 乳制品加工厂
3. 冷链仓储
4. 物流/配送
5. 零售终端
6. 其他供应链实体

边类型：

1. 上下游供给关系
2. 物流流转关系
3. 时序关联关系（用于暴露传播近似）

属性体系：

1. 节点属性：身份、类型、规模、区域、画像特征、7 维风险概率
2. 边属性：产品、时长、停留、7 维风险概率、规则命中

### 4.2 图视图能力

1. 全图视图：`view_mode=full`
2. 品类子图：`view_mode=product`
3. Seed + K-hop 子图提取
4. Top5 热点叠加

## 5. GPT 5.4 Pro 建模思想（定性转定量）

本项目按 GPT 5.4 Pro 提供的思路落地为“分层公式引擎”，目标是可解释排序而非黑盒概率。

### 5.1 建模原则

1. 排序优先：目标是 Top-K 准确，而非每个企业的绝对风险精确概率。
2. 风险与不确定性分离：缺失主要影响 `uncertainty_proxy`，不直接抬高 `risk_proxy`。
3. 强规则兜底：监管硬信号使用分段抬升，避免被均值稀释。
4. LLM 只解释不打分：分数主干必须可回放和可审计。

### 5.2 三层公式结构（已实现）

实现文件：`scripts/modea_formula_engine.py`

第一层 Base scorecard：

1. `risk_proxy`
2. `credibility_proxy`
3. `uncertainty_proxy`
4. `exploit/explore`
5. `priority_base_score`

第二层 Piecewise override：

1. 对强监管证据（Top5/历史失败等）做“只抬升不打压”
2. 输出 `priority_piecewise_score`

第三层 Static KQV overlay：

1. Query `Q`（品类、环节、节点类型、风险维度）驱动静态调权
2. Key 固定小集合：`rule/exposure/history/coldchain/profile/dataquality`
3. 输出 `kqv_overlay` 与最终 `priority_score`

### 5.3 定性到定量映射路径

1. 定性规则拆解：
   规则命中、链路暴露、冷链脆弱、历史事件、数据质量。
2. 指标化：
   每个定性信号映射到 `[0,1]` 代理变量。
3. 代理融合：
   形成 `risk/credibility/uncertainty` 三代理。
4. 决策函数：
   `priority = lambda * exploit + (1-lambda) * explore + bonus`。
5. 场景调权：
   KQV 根据监管查询上下文对证据贡献做轻量重排。

### 5.4 可解释性链路

每个节点返回完整链路字段：

1. `risk_proxy`
2. `credibility_proxy`
3. `uncertainty_proxy`
4. `priority_base_score`
5. `priority_piecewise_score`
6. `kqv_overlay`（weights/values/delta/mu/tau）
7. `priority_score`（最终）

这套字段可直接用于“为什么判高风险”的审计说明。

## 6. 异构图任务分解与解决方案

### 任务 1：图数据统一建模

问题：节点与边来源异构、字段不一致。
方案：统一编码为图 JSON，维护 node/edge schema 与类型映射。
结果：支持同一接口加载全图与子图。

### 任务 2：节点特征构建

问题：仅有结构数据，无法排序。
方案：生成企业画像代理特征并归一化。
结果：节点可计算 `risk/credibility/uncertainty`。

### 任务 3：边特征构建

问题：供应链传播脆弱性缺少量化。
方案：构建 `time_fragility` + 边风险代理。
结果：边可参与暴露传播与边优先级排序。

### 任务 4：7 大风险维度输出

问题：业务要每个节点/边给 7 维概率。
方案：节点、边都输出 7 维风险向量与对应 Top5。
结果：前端可按风险维切换可视化。

### 任务 5：子图提取

问题：全图过大，不利于研判。
方案：按品类/seed/k-hop 构建子图接口。
结果：支持监管按场景局部研判。

### 任务 6：筛选排序（目标 1）

问题：如何避免随机抽检。
方案：按 `priority_score` 排序返回 Top-K。
结果：形成可解释“初筛名单”。

### 任务 7：不确定性量化（目标 2）

问题：如何识别“应优先核查”的不确定对象。
方案：输出 `uncertainty_proxy` 与探索分支贡献。
结果：支持“高风险优先 + 高不确定补充”的双轨策略。

### 任务 8：预算优化（目标 3）

问题：有限成本下如何选样本。
方案：`resource_plan` 贪心选择，综合优先级、覆盖收益、不确定性、成本。
结果：输出 `budget_utility` 与推荐抽检清单。

### 任务 9：报告闭环

问题：分数很难给监管人员解释。
方案：LLM 消费结构化评分链路，生成报告与行动建议。
结果：可解释、可追溯、可用于汇报。

## 7. API 与前端落地

后端接口（`backend/api.py`）：

1. `/api/modela/v2/view`：全图/子图与风险字段
2. `/api/modela/v2/screening`：Top-K 与链路分解
3. `/api/modela/v2/ranking_eval`：排序评估
4. `/api/modela/v2/resource_plan`：预算分配建议
5. `/api/modela/v2/modea_report`：LLM 报告

前端（`frontend/app/modela-v2/page.tsx`）：

1. 图谱可视化（全图/子图/品类）
2. 7 维风险展示（节点与边）
3. 评分链路展示（Base -> Piecewise -> KQV -> Final）
4. 目标 1-3 面板（筛选、排序、预算）
5. 报告与解释视图

类型定义：`frontend/types/index.ts`

## 8. 可审计与工程化保障

1. 元信息透出：
   `formula_version`、`params`、`piecewise_enabled`、`kqv_enabled`。
2. 参数可配置：
   支持后续阈值与权重微调。
3. 版本化输出：
   报告可绑定数据版本与公式版本。
4. 回放能力：
   同输入可重现同输出（便于答辩与审计）。

## 9. 当前边界与下一步

当前边界：

1. 这是排序型决策引擎，不是机理因果仿真。
2. KQV 是静态可解释调权，不是深度训练注意力网络。
3. 对连续机理参数缺失场景，无法输出实验室级绝对风险概率。

建议下一步：

1. 先上线品类子图 + Top-K 研判主流程。
2. 增加专家反馈闭环，做参数回标与阈值学习。
3. 将预算策略与真实抽检结果联动，迭代 `coverage_gain` 估计。
