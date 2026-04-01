# ModeA 公式化定量引擎（定性->定量）落地实现与测试说明

更新时间：2026-03-29

## 1. 本次目标

将你在 `/home/yarizakurahime/data/5.4Pro` 中给出的公式重构方案接入到既有 ModeA（保留 LLM 驱动结论），实现：

1. 节点优先级排序（初筛）
2. 不确定性量化（explore/exploit）
3. 预算约束下资源分配
4. 前端图可视化展示公式结果

## 2. 已实现内容

### 2.1 新增公式引擎

新增文件：

- `scripts/modea_formula_engine.py`

核心输出（节点）：

- `risk_proxy`
- `credibility_proxy`
- `uncertainty_proxy`
- `priority_score`
- `exploit_score`
- `explore_score`
- `budget_cost`
- `source_mix`
- `formula_contrib`

核心输出（边）：

- `time_fragility`
- `edge_risk_proxy`
- `edge_uncertainty`
- `edge_priority`

元信息：

- `meta.formula.formula_version = modea_formula_v1`
- `parameter_set_id = default_v1`
- `query_context`
- `params`

补充（本轮已补齐）：

- `piecewise override` 已接入（`priority_base_score -> priority_piecewise_score`）
- `KQV overlay` 已接入（`priority_piecewise_score -> priority_score`）
- 节点新增 `kqv_overlay`（含 `weights/values/mu/tau/delta`）
- `meta.formula` 新增 `piecewise_enabled`、`kqv_enabled`

### 2.2 后端接入（ModeA v2）

修改文件：

- `backend/api.py`

已接入公式引擎的接口：

- `GET /api/modela/v2/view`
- `GET /api/modela/v2/subgraph`
- `GET /api/modela/v2/screening`
- `GET /api/modela/v2/ranking_eval`
- `POST /api/modela/v2/resource_plan`
- `POST /api/modela/v2/modea_report`

其中 `modea_report` 规则摘要已改为使用公式字段（`avg_priority`、`avg_credibility` 等），LLM 继续负责结论文本。

### 2.3 前端适配（ModeA v2 页面）

修改文件：

- `frontend/app/modela-v2/page.tsx`
- `frontend/types/index.ts`

前端已改为优先展示公式字段：

- 节点主分：`priority_score`（回退 `risk_proxy`）
- 边主分：`edge_priority`（回退 `edge_risk_proxy`）
- tooltip/详情面板新增：风险代理、可信度、不确定性
- 节点详情新增 `formula_contrib` 贡献拆解
- 图谱信息区新增 `formula_version`
- Top榜单标题改为按公式优先级

## 3. 编译与联调结果

### 3.1 编译检查

执行：

```bash
python -m py_compile backend/api.py scripts/modea_formula_engine.py scripts/modela_v2_pipeline.py
npm -C frontend run build
```

结果：通过。

### 3.2 接口联调（实测）

测试场景：`product_type=全脂乳粉`

实测结果摘要：

- `GET /api/modela/v2/view`：`200`
  - `meta.formula.formula_version = modea_formula_v1`
  - `meta.formula.piecewise_enabled = true`
  - `meta.formula.kqv_enabled = true`
  - 节点样例：`priority_score=0.632525, risk_proxy=0.733602, credibility_proxy=0.775577, uncertainty_proxy=0.462494`
  - 边样例：`edge_priority=0.515453, edge_risk_proxy=0.475351`
- `GET /api/modela/v2/subgraph`：`200`（返回公式字段）
- `GET /api/modela/v2/screening`：`200`
  - `total_candidates=275`
- `GET /api/modela/v2/ranking_eval`：`200`
- `POST /api/modela/v2/resource_plan`：`200`
  - `selected_count=10`, `budget_used=13.95`
  - 返回 `budget_utility/coverage_gain`
- `POST /api/modela/v2/modea_report`：`200`
  - `avg_priority/avg_credibility` 已返回
  - `llm.mock=true, llm.success=true`

## 4. 你本地复测步骤（前后端）

在项目根目录执行：

```bash
cd /home/yarizakurahime/data/dairy_supply_chain_risk
```

### 4.1 启动后端

```bash
python backend/api.py
```

启动后检查：

```bash
curl http://127.0.0.1:8000/health
```

### 4.2 启动前端

另开终端：

```bash
cd /home/yarizakurahime/data/dairy_supply_chain_risk/frontend
npm run dev -- -p 3001
```

访问：

- `http://127.0.0.1:3001/modela-v2`

### 4.3 页面测试点

1. 选择任一品类（默认 product 模式）
2. 点击“刷新图谱”
3. 点击节点/边，确认展示：
   - 节点：优先级、风险代理、可信度、不确定性、贡献拆解
   - 边：边优先级、边风险代理、边不确定性
4. 运行“1+2 初筛与排序”，确认列表返回
5. 运行“3 预算分配”，确认返回 `budget_utility`
6. 运行“生成Mode A报告”，确认 `avg_priority/avg_credibility` 与 LLM 摘要输出

## 5. 当前边界与注意事项

1. 当前主交付定位为“排序型决策引擎”，不是绝对污染概率预测。
2. 公式引擎是可审计的线性/规则结构，LLM 不参与核心打分，只负责解释。
3. `view_mode=full` 且节点/边上限较大时，CPU 计算会显著变慢；建议日常在品类子图和受限规模下运行。
