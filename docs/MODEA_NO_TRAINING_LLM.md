# ModeA 无训练版（异构图 + LLM）快速配置

目标：不训练模型，先把数据组织成统一异构图，然后做子图抽取与 LLM 风险研判，达到可用级别。

## 1. 必要数据处理（必须做）

将原始 `dataset_3_18.zip` 转为统一图结构并生成节点风险先验：

```bash
cd /home/yarizakurahime/data/dairy_supply_chain_risk
python scripts/prepare_llm_hetero_graph.py \
  --input /home/yarizakurahime/data/graph/dataset_3_18.zip \
  --output-dir data/llm_graph
```

输出文件：

- `data/llm_graph/graph_llm_ready.json`
- `data/llm_graph/node_risk_summary.csv`
- `data/llm_graph/edge_risk_summary.csv`

## 2. 子图抽取 + LLM 研判

### 2.1 先用 mock LLM 验证链路

```bash
python scripts/run_llm_subgraph_assessment.py \
  --graph data/llm_graph/graph_llm_ready.json \
  --region 上海 \
  --start-time '2025-01-01 00:00:00' \
  --end-time '2025-03-31 23:59:59' \
  --k-hop 2 \
  --use-mock-llm \
  --output data/llm_graph/sample_assessment.json
```

### 2.2 切真实 Minimax LLM

在 `.env` 中配置（已有模板 `.env.example`）：

- `MINIMAX_API_KEY`
- `MINIMAX_MODEL`（可选）
- `MINIMAX_TEMPERATURE`（可选）

然后去掉 `--use-mock-llm` 即可。

## 3. 当前版本可用边界

已支持：

- 全图统一异构结构（节点+边+时间+风险标签）
- `region/time_window/k-hop/seed_node` 子图提取
- 节点低中高风险先验（规则统计）
- LLM 生成结构化监管建议（JSON）

未完成（后续增强）：

- 精细产品品类（如 `flavored_fermented_milk`）自动标注
- 区县级地域标签（目前默认 `region=上海`）
- 训练式图模型（目前不依赖训练）

## 4. 结论

不训练可以先上线“可用版”。

但需要做一层最小数据处理（第1步），否则 LLM 只有原始表，很难稳定做子图和风险归纳。
