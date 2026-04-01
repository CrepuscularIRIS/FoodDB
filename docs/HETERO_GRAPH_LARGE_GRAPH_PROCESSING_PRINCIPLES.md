# 大图异构图处理原理说明（dataset_3_18.zip -> graph_llm_ready.json）

## 1. 目标与结论
本流程的目标是：

1. 将 `dataset_3_18.zip` 中的多文件原始数据，统一为一个可直接被 LLM 子图评估使用的异构图 JSON。
2. 在不训练图模型的前提下，为每个节点计算可解释的风险先验（`risk_score/risk_level/risk_vector`）。
3. 处理规模达到当前数据量：`4276` 节点、`209982` 边。

当前产物：

- `data/llm_graph/graph_llm_ready.json`（约 148MB）
- `data/llm_graph/node_risk_summary.csv`
- `data/llm_graph/edge_risk_summary.csv`

对应脚本：

- `scripts/prepare_llm_hetero_graph.py`

## 2. 输入与输出结构

### 2.1 输入（zip 内）
核心输入文件：

- `enterprise_node.csv`：节点基础属性（名称、经纬度、节点类型、企业规模）
- `graph_edges_sorted_with_logistics_scale.csv`：时序边（src/dst、时间、停留、在途、物流企业规模等）
- `edge_labels_sorted.npy`：每条边 7 维风险标签
- `node_labels_sorted.npy`：每条边两端节点的 7 维风险标签

### 2.2 输出（统一异构图）
输出 JSON 顶层：

- `meta`
- `nodes`
- `edges`

其中：

- `nodes` 除基础属性外，增加了 `product_tag`、`risk_score`、`risk_level`、`risk_vector`
- `edges` 统一到 `source/target/timestamp/risk_labels/...` 的消费友好结构

## 3. 处理流程（按执行顺序）

### Step A. 解压与路径解析
- 若输入是 zip，先解压到临时目录（`/tmp/llm_hetero_graph_*`）。
- 自动识别包含 `graph_edges_sorted_with_logistics_scale.csv` 的目录作为 `data_dir`。

效率要点：

- 一次解压，后续全部本地顺序读，避免反复随机 I/O。

### Step B. 批量加载关键表
- `pandas.read_csv` 读取节点/边 CSV。
- `numpy.load` 读取 `.npy` 风险标签矩阵。
- 先校验长度一致性（边数必须与标签矩阵首维一致）。

效率要点：

- 边标签和节点标签使用 NumPy 连续内存数组，单条边取标签为 O(1)。
- 提前做长度校验，避免后续半程失败重算。

### Step C. 生成 `product_tag`（批次 -> 节点）
- 先找每个 `batch_id` 对应的加工厂（`dst_type == 乳制品加工厂`）。
- 基于加工厂名称关键词映射（如“光明/蒙牛/菲仕兰辉山”）得到批次 `product_tag`。
- 再把每个节点跨批次出现的 `product_tag` 做众数聚合，得到节点 `product_tag`。

效率要点：

- 聚合逻辑是线性扫描，避免高代价图遍历。

### Step D. 节点注册与补全
- 先用 `enterprise_node.csv` 建节点主表。
- 再扫描边表，将“只在边里出现”的节点补进来（缺失属性填默认值）。
- 对节点名排序后一次性生成稳定 ID：`N-00001` ...

效率要点：

- 使用哈希表（Python dict）做节点去重与存在性判断，平均 O(1)。

### Step E. 单次扫描构建边 + 累计节点统计
对边表做一次主循环，同时完成三件事：

1. 生成边对象（包括时间、物流、停留、风险标签等）
2. 更新两端节点 `edge_count`
3. 累加两端节点 `risk_sum`（来自 `node_labels_sorted.npy`）

效率要点：

- 单 pass 同步完成“建边 + 统计”，避免多轮重复遍历 20 万边。
- `risk_sum` 是固定 7 维向量累加，常数开销小。

### Step F. 节点风险先验计算
对每个节点：

- `risk_vec = risk_sum / max(edge_count, 1)`
- 通过加权平均得到 `risk_score`（微生物/重金属权重更高）
- 用分位点 `q1=60%`, `q2=85%` 划分 `low/medium/high`

效率要点：

- 全部为向量/标量数值计算，时间复杂度与节点数线性相关。

### Step G. 落盘
- 写出完整 JSON（`graph_llm_ready.json`）。
- 写出两个摘要 CSV，便于前端和快速检索。

效率要点：

- 摘要文件将常见查询从“读 148MB 大 JSON”降到“读 280KB/18MB CSV”。

## 4. 为什么这套流程能“高效处理”大图
当前规模下（约 21 万边）效率来自 5 个关键设计：

1. **数据结构选择正确**：标签矩阵走 NumPy，索引和聚合走 dict。
2. **线性扫描优先**：核心处理均为 O(E) 或 O(V)；无高阶图算法。
3. **一次遍历做多事**：建边和统计合并，避免重复 I/O 与重复 CPU。
4. **预聚合再查询**：把风险先验预计算到节点上，在线子图评估无需重算全图。
5. **输出分层**：完整图 + 摘要表并存，兼顾准确性和后续访问速度。

## 5. 复杂度与资源画像
设：

- `V` 节点数（4276）
- `E` 边数（209982）
- `K` 风险维度（7，常数）

时间复杂度（主项）：

- 构建与统计：`O(E)`
- 节点风险计算：`O(V * K)`，约等于 `O(V)`
- 总体：`O(E + V)`（线性）

空间复杂度（主项）：

- 边列表 + 节点字典 + 标签矩阵：`O(E + V)`

## 6. 与 zip 原始规范的关系

一致部分：

- 节点/边主数据、时间序、7 维风险标签均来自 zip。
- 节点数和边数与原始数据对齐。

转换部分：

- 增加 LLM 友好字段：`risk_score/risk_level/risk_vector/product_tag/region`。
- 边字段标准化为统一键名（`source/target/...`）。
- 部分原始列不进入最终 JSON（例如 `edge_text_feature`）。

因此它是“规范化增强版”，不是原始表的 1:1 直接镜像。

## 7. 当前瓶颈（客观）
当前实现可用，但存在可优化点：

1. 使用 `iterrows()` 的 Python 层循环较多，CPU 不是最优。
2. 全量 JSON 一次性序列化，内存峰值和写入时间偏高。
3. zip 先全量解压，再读表；对更大数据集会增加磁盘压力。

## 8. 可落地优化路线（从易到难）

### 8.1 低风险优化（建议先做）
1. `iterrows()` 改为 `itertuples()` 或向量化处理。
2. `read_csv` 显式指定 `dtype` 与 `usecols`，减少内存和解析开销。
3. JSON 输出改为 `orjson`（若可引入依赖），提升序列化速度。

### 8.2 中等优化
1. 边处理改为分块（`chunksize`）流式构图。
2. 结果先写 Parquet，再按需导出 JSON（兼顾分析与接口）。
3. 利用 `np.add.at` 或 groupby 聚合替代部分 Python 循环。

### 8.3 高阶优化
1. 对超大图采用二进制图存储（Arrow/Parquet + 索引）。
2. 子图查询层改为“按条件增量加载”，避免启动时全量载入。
3. 将风险先验计算做增量更新（新增边只更新受影响节点）。

## 9. 一句话总结
这套大图处理之所以快，核心不是复杂模型，而是：

- 先把多源原始数据做成单一异构图结构，
- 用线性扫描和预聚合把在线计算搬到离线，
- 用统一字段让后续子图抽取和 LLM 研判直接消费。

在当前 20 万边规模上，这个设计是工程上稳定且可扩展的。

## 10. 子图提取流程（Subgraph Extraction）
本项目有两条子图提取链路：

1. 离线脚本链路：`scripts/run_llm_subgraph_assessment.py::extract_subgraph`
2. 在线 API 链路：`backend/api.py::_extract_subgraph_local`（逻辑一致，增加返回上限控制）

### 10.1 输入参数
常见输入维度：

- `region`：区域过滤（默认 `上海`）
- `start_time / end_time`：时间窗过滤（作用于边）
- `seed_node`：种子节点（名字或 `node_id`）
- `k_hop`：以种子为中心的扩展深度
- `product_tag`：仅离线脚本支持的产品类别过滤

API 额外支持：

- `max_nodes`：返回节点上限（默认 300）
- `max_edges`：返回边上限（默认 600）

### 10.2 核心步骤

#### Step 1. 边级时间过滤
对全图边做时间窗筛选，只保留命中时间范围的边。

目的：

- 先在边层面收缩搜索空间，降低后续邻接构建和 BFS 成本。

#### Step 2. 节点级属性过滤
先形成基础节点集合 `base_node_ids`：

- 按 `region`（以及脚本版可选 `product_tag`）过滤节点。
- 若未给属性过滤条件，则退化为“时间过滤后边所触达的所有节点”。

目的：

- 将“业务条件”转换为统一的节点候选集。

#### Step 3. 邻接构建 + k-hop 扩展
基于“已通过时间过滤”的边构建无向邻接表，然后：

- 若给了 `seed_node`，从 seed 做 BFS，扩展到 `k_hop`。
- 扩展结果与 `base_node_ids` 取交集，得到 `selected_nodes`。
- 若未给 seed，`selected_nodes = base_node_ids`。

目的：

- 在满足业务过滤的同时，提取与目标节点局部连通的上下游网络。

#### Step 4. 边裁剪
保留两端都在 `selected_nodes` 内的边，得到 `sub_edges`。

脚本版：

- 直接返回全部满足条件的 `sub_edges`。

API 版：

- 先按 `risk_positive_count` 降序，再截断到 `max_edges`，优先保留高风险边。

#### Step 5. 节点裁剪与补全
脚本版：

- 若 `sub_edges` 非空，只保留出现在 `sub_edges` 中的连通节点；
- 若 `sub_edges` 为空，保留 `selected_nodes`。

API 版：

- 先保留边内节点；
- 再按 `risk_score` 从高到低补充候选节点，直到 `max_nodes`；
- 这样即使部分高风险节点暂时孤立，也可出现在返回结果中。

#### Step 6. 生成元信息
返回：

- `node_count / edge_count`
- 过滤条件回显（`region/time_window/seed/k_hop` 等）

便于前端展示和 LLM 提示词拼装。

### 10.3 算法复杂度
设原图为 `V` 节点、`E` 边，提取后子图为 `V'`、`E'`：

- 时间过滤：`O(E)`
- 邻接构建：`O(E_filtered)`
- BFS 扩展：`O(V_filtered + E_filtered)`（局部图）
- 边裁剪：`O(E_filtered)`
- API 额外排序截断：`O(E' log E')`（按风险排序）

总体仍以线性项为主，满足在线场景。

### 10.4 为什么子图提取是高效的
关键在于“先过滤、后扩展、再截断”的顺序：

1. 时间过滤先砍掉大量无关边。
2. 属性过滤把节点候选集限制在业务范围。
3. BFS 只在过滤后的局部图上运行。
4. API 层用 `max_edges/max_nodes` 做硬上限，稳定响应时间和传输体积。

### 10.5 与大图预处理的协同关系
子图提取之所以能快，是因为大图阶段已做了两件事：

1. 统一字段命名（`source/target/timestamp/risk_*`），提取逻辑无需多源适配。
2. 预计算节点风险先验（`risk_score/risk_level`），API 可直接按风险排序截断。

这使得“全图一次预处理 + 多次快速子图查询”成为可扩展的工程模式。

## 11. 项目效果快速评测（2026-03-24）
本节基于当前项目代码与数据做了小样本实测，目标是给出“可落地、可复现”的基线指标。

评测结果文件：

- `reports/quick_project_eval_results_v2.json`

### 11.1 评测维度与口径
本次选取 4 类与项目契合度高的指标：

1. Agent 调用成功率（流程可用性）
2. 常识问答准确率（LLM 基础正确性）
3. 查询召回率@3（企业检索能力）
4. 风险预测准确性（规则引擎与检验标签一致性）

说明：

- 常识问答使用 `.env` 中配置的真实模型（实测读取为 `MiniMax-M2.7`）。
- Agent 调用成功率为了聚焦流程本身，采用非 LLM 口径（屏蔽外部网络不稳定因素）。

### 11.2 指标结果

#### A) Agent 调用成功率（非 LLM 口径）
- 样本：6（3 个企业 + 3 个批次）
- 成功：6/6
- 成功率：`100%`

#### B) 常识问答准确率（真实模型）
- 模型：`MiniMax-M2.7`
- 样本：5
- API 成功率：`100%`
- 严格准确率（只认“是/否”字面）：`80%`（4/5）
- 放宽准确率（“否/不”都计为否）：`100%`（5/5）
- 平均延迟：`2753.97 ms`

#### C) 查询召回率@3（企业检索）
- 样本：12（企业名部分片段查询）
- 命中：12/12
- Recall@3：`100%`

注：

- 初版统计曾为 0，是因为读取了错误字段。
- 修正后候选 ID 从 `candidate.enterprise.enterprise_id` 提取，得到上述结果。

#### D) 风险预测准确率（批次级）
- 样本：100（按检验记录聚合后的批次）
- 3 分类准确率（high/medium/low）：`4%`
- high 类 Precision/Recall/F1：`0 / 0 / 0`

原因分析：

- 当前评分阈值 `high >= 70`，但实测最高分仅 `61.5`，模型不会输出 `high`，导致 high 召回为 0。

补充一个更实用的运维口径（正类=非低风险，即 high 或 medium）：

- Accuracy：`79%`
- Precision：`1.0`
- Recall：`0.78125`
- F1：`0.8772`
- Confusion：`TP=75, FP=0, TN=4, FN=21`

### 11.3 样例（批次）
- `BATCH-000001`：真实 `high`，预测 `medium`，得分 `42.0`
- `BATCH-000003`：真实 `high`，预测 `medium`，得分 `52.0`

### 11.4 当前结论
从工程可用性看：

1. Agent 主流程可稳定跑通；
2. LLM 常识能力在小样本下表现稳定；
3. 检索层召回能力可用；
4. 风险分级与现有标签分布存在明显错位（阈值/权重需校准），是当前最主要精度短板。
