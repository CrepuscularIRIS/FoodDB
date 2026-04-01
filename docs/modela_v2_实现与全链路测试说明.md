# ModelA v2 实现与全链路测试说明

## 1. 任务目标

根据用户需求，重做 `ModelA`，实现以下能力：

1. 基于 `dataset_3_24` 的初始异构图数据构建风险预测体系。  
2. 不仅使用图结构，还要生成可用于节点特征构建的新增数据。  
3. 对**节点和边**都输出 7 大类风险概率值（范围 `[0,1]`）。  
4. 支持按乳制品品类提取子图并进行风险可视化。  
5. 提供可运行的后端接口与前端页面，形成完整链路。

---

## 2. 数据输入与产物

### 2.1 输入数据

来自：

- `/home/yarizakurahime/data/HandOff/乳制品供应链异构图数据和国标语料.zip`

核心输入文件（压缩包内 `dataset_3_24`）：

- `enterprise_node.csv`
- `graph_edges_reformatted_with_product.csv`

### 2.2 输出数据

输出目录：

- `/home/yarizakurahime/data/dairy_supply_chain_risk/data/modela_v2`

生成文件：

1. `enterprise_node_features_generated.csv`  
   - 新增企业画像特征（历史抽检次数、不合格次数、冷链断链次数、舆情指数、设备老化、合规度等）  
   - 格式与 `enterprise_node` 兼容扩展，便于自动读入构建节点特征。

2. `node_risk_probabilities.csv`  
   - 节点级 7 类风险概率输出。

3. `edge_risk_probabilities.csv`  
   - 边级 7 类风险概率输出。

4. `modela_v2_graph.json`  
   - 前后端统一消费的图谱数据（节点、边、品类、风险向量、画像特征）。

---

## 3. 代码实现内容

## 3.1 新增脚本与核心模块

1. `scripts/modela_v2_pipeline.py`  
   负责：
   - 读取 `dataset_3_24`；
   - 生成企业画像节点特征；
   - 生成边级 7 维风险概率；
   - 聚合得到节点总体/品类 7 维风险概率；
   - 产出 `modela_v2_graph.json` 与 csv 文件；
   - 支持按品类提取子图（含 k-hop 和 seed node）。

2. `scripts/build_modela_v2_dataset.py`  
   一键构建入口脚本。

## 3.2 后端 API 增加

文件：`backend/api.py`

新增接口：

1. `GET /api/modela/v2/meta`  
   - 返回 ModelA v2 元信息（节点数、边数、7类风险维度、品类列表）。

2. `GET /api/modela/v2/categories`  
   - 返回乳制品品类列表（13类）。

3. `GET /api/modela/v2/subgraph`  
   参数：
   - `product_type`（必填）
   - `seed_node`（可选）
   - `k_hop`、`max_nodes`、`max_edges`
   返回：
   - 品类子图节点/边；
   - 节点和边的 7 类风险概率。

4. `POST /api/modela/v2/rebuild`  
   - 强制重建数据产物。

## 3.3 前端页面与 API 封装

1. 新增页面：`frontend/app/modela-v2/page.tsx`
   - 支持品类选择、seed node、k-hop；
   - 可视化品类子图；
   - 点击节点/边显示 7 维风险向量。

2. 新增前端 API：`frontend/lib/api.ts`
   - `modelAV2Api.getMeta/getCategories/getSubgraph/rebuild`。

3. 新增类型定义：`frontend/types/index.ts`
   - `ModelAV2Node/ModelAV2Edge/ModelAV2Subgraph/ModelAV2Meta`。

4. 导航入口：`frontend/app/layout.tsx`
   - 增加 `ModelA v2` 页面入口。

---

## 4. 全链路测试过程与结果

测试日期：`2026-03-29`  
测试环境：本地开发机（同仓库）

## 4.1 数据构建测试

执行：

```bash
cd /home/yarizakurahime/data/dairy_supply_chain_risk
python -u scripts/build_modela_v2_dataset.py \
  --input '/home/yarizakurahime/data/HandOff/乳制品供应链异构图数据和国标语料.zip' \
  --output-dir data/modela_v2
```

结果：

- 成功生成；
- `node_count=4276`；
- `edge_count=209982`；
- `categories=13`。

## 4.2 后端接口测试

启动：

```bash
cd /home/yarizakurahime/data/dairy_supply_chain_risk
python backend/api.py
```

验证接口（均返回 `200`）：

- `/health`
- `/api/modela/v2/meta`
- `/api/modela/v2/categories`
- `/api/modela/v2/subgraph?product_type=巴氏杀菌乳&k_hop=0&max_nodes=220&max_edges=320`

关键断言结果：

1. 子图节点存在 `category_risk_probabilities` 且长度为 7。  
2. 子图边存在 `risk_probabilities` 且长度为 7。  
3. 节点包含 `profile_features`（企业画像特征）。  

## 4.3 前端构建与页面可达测试

构建：

```bash
cd /home/yarizakurahime/data/dairy_supply_chain_risk/frontend
npm run build
```

结果：构建成功，包含路由：

- `/modela-v2`

启动：

```bash
npm run start -- -p 13000
```

页面可达：

- `http://127.0.0.1:13000/modela-v2` 返回 `HTTP 200`

页面关键元素可见：

- `乳制品品类`
- `刷新子图`
- `风险向量详情`

---

## 5. 与需求逐条对应结论

1. 使用指定初始数据（`enterprise_node` + `graph_edges_reformatted_with_product`）：**已完成**。  
2. 额外生成节点特征数据（企业画像，不仅图结构）：**已完成**。  
3. 节点与边都输出 7 类风险概率：**已完成**。  
4. 按不同乳制品品类提取并展示异构子图：**已完成**。  
5. 前端与后端代码均已提供并联通：**已完成**。  
6. 全链路可运行（构建→后端→前端→接口/页面）：**已验证通过**。

---

## 6. 本次新增/修改的关键文件

新增：

- `scripts/modela_v2_pipeline.py`
- `scripts/build_modela_v2_dataset.py`
- `frontend/app/modela-v2/page.tsx`
- `docs/modela_v2_实现与全链路测试说明.md`（本文件）

修改：

- `backend/api.py`
- `frontend/lib/api.ts`
- `frontend/types/index.ts`
- `frontend/app/layout.tsx`

---

## 7. 2026-03-29 二次增强（可视化强化 + ModeA 报告）

### 7.1 数据层增强

- 输入已验证支持本轮文件：
  - `/home/yarizakurahime/data/项目文件和要求.zip`（内含 `dataset_3_24` CSV）
- `scripts/modela_v2_pipeline.py` 增加了 `Top5%` 风险标签产出：
  - 节点与边均新增 `top5_flags/top5_count/is_top5_any`
  - `node_risk_probabilities.csv` 与 `edge_risk_probabilities.csv` 增加 7 类 `_top5` 标签列
  - `modela_v2_graph.json` 的 `meta` 增加 `top5_thresholds`

### 7.2 后端接口增强

新增接口：

1. `GET /api/modela/v2/view`  
   - 统一支持 `view_mode=full|product`  
   - 支持 `seed_node + k_hop`  
   - 返回节点和边的 `view_risk_*` 与 `Top5%` 标签  
   - 支持 `max_nodes/max_edges/top_ratio` 限制与阈值控制

2. `POST /api/modela/v2/modea_report`  
   - 基于当前图视图（全图或品类图）生成 Mode A 规则汇总  
   - 调用 LLM 产出结论与策略（无密钥时可 mock）  
   - 返回 `rule_summary + llm + view_meta`

### 7.3 前端可视化增强

- `frontend/app/modela-v2/page.tsx` 已重构为高密度图谱页：
  - 全图/品类子图切换
  - Top5% 热点过滤
  - 高风险节点/边强化着色和关系线加权
  - 右侧节点/边 7 类风险向量详情
  - Top 节点榜单
  - Mode A 报告按钮与回显区
  - 目标1-3（初筛/排序/预算）继续保留

### 7.4 本轮测试结果

测试日期：`2026-03-29`

- 数据重建成功（`node_count=4276`, `edge_count=209982`, `categories=13`）
- Python 语法检查通过：`backend/api.py`、`scripts/modela_v2_pipeline.py`
- 接口测试通过（均 `200`）：
  - `/api/modela/v2/view?view_mode=product&product_type=巴氏杀菌乳`
  - `/api/modela/v2/view?view_mode=full`
  - `/api/modela/v2/modea_report`（`use_mock_llm=true`）
  - `/api/modela/v2/screening`
  - `/api/modela/v2/ranking_eval`
  - `/api/modela/v2/resource_plan`
- 前端 `npm run build` 通过，路由 `/modela-v2` 正常产出

---

## 8. 本轮补充（首页ModeA统一链路 + 建模交付包）

1. 首页 `Mode A` 已默认切换为统一链路入口（嵌入 `ModelA v2` 全链路页面）。  
   - 目标：避免旧 `Mode A` 与 `ModeA v2` 两套逻辑并行导致口径不一致。  

2. `ModelA v2` 可视化增强：  
   - 新增“边风险阈值”过滤；  
   - 新增“标签模式（智能/全部/隐藏）”；  
   - 新增图导出工具（saveAsImage / restore）；  
   - 节点边框增加类型色编码，提升可读性。  

3. 新增建模交付包（Zip）：  
   - `/home/yarizakurahime/data/dairy_supply_chain_risk/reports/modeling_handoff_package_20260329.zip`  
   - 包内包含：数据属性说明、Mock输入、指标与公式任务书、以及 Gemini/GPT 两阶段到三阶段 Prompt。  
