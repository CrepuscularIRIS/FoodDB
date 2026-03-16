# HANDOFF

本目录当前采用“分层外挂知识库”思路，不再把所有语料混成一个统一 RAG 桶处理。

核心原则：

- GB 标准为主，外部材料为辅
- 规则层和证据层分开
- 辅助推断不能覆盖 GB 规则
- 方法层不再优先用 Python 关键词筛选做主判断
- 方法层主判断交给模型逐条阅读和改写

## 当前目录角色

- `knowledge/configs/`
  - 结构化规则层
- `knowledge/corpora/rag_corpus_standard_txt.jsonl`
  - GB 正文检索层
- `knowledge/corpora/rag_corpus_management_v2.jsonl`
  - 生产问题 / 管控措施层
- `knowledge/corpora/rag_corpus_methods_standards.jsonl`
  - 方法标准原始层，当前质量不均，需要继续清洗
- `knowledge/standard_txt/`
  - 原始 GB txt

## 方法层处理策略

`rag_corpus_methods_standards.jsonl` 的清洗任务，后续按“纯 LLM 逐批手动改写”执行。

不推荐：

- 用 Python 脚本做主判断
- 用关键词一刀切地 keep / drop
- 一次性改完整个文件

推荐：

- 模型逐条读取原始记录
- 按知识角色做语义判断
- 每轮只处理很小一批
- 每轮只改一个目标文件

## 方法层知识角色

允许的 `kb_role`：

- `dairy_specific_standard`
- `general_method_applicable_to_dairy`
- `mixed_scope_method_with_dairy`
- `non_dairy`
- `uncertain`

允许的 `decision`：

- `keep`
- `drop`
- `uncertain`

判断原则：

- 乳制品专用标准：`keep`
- 通用但在乳制品场景明确可调用的方法标准：`keep`
- 混合适用范围但明确包含牛奶/乳制品：`keep`
- 明显非乳制品：`drop`
- 无法判断：`uncertain`

注意：

- 不能因为是通用标准，就直接视为非乳制品
- 不能伪造 `source_url` / `source_domain`
- 如果原始来源字段可疑，只能保留原值并注明可疑，不能美化

## 方法层目标文件

输入：

- `knowledge/corpora/rag_corpus_methods_standards.jsonl`

输出：

- `knowledge/corpora/rag_corpus_methods_standards_dairy_cleaned.jsonl`
- `knowledge/corpora/rag_corpus_methods_standards_dairy_uncertain.jsonl`

保留或 uncertain 记录必须尽量补齐这些字段：

- `source_url`
- `source_domain`
- `authority`
- `source_type`
- `product_scope`
- `method_scope`
- `dairy_relevance`
- `kb_role`
- `decision`
- `decision_reason`

规则：

- 能从原文提取就提取
- 提取不到就留空
- 不得编造

## RalphLoop 使用方式

如果使用 RalphLoop，当前推荐采用“小步慢改”模式：

- 每轮只处理 3 到 5 条原始记录
- 每轮只改一个目标文件
- 不要一轮处理整库
- 不要依赖 Python 批处理脚本

推荐命令：

```text
/ralph-loop:ralph-loop "
你现在只做 standalone_food_risk_kb 方法层的人工式语义清洗，不使用 Python 脚本做主判断，不使用关键词批处理逻辑，不做整库一次性改写。

工作目录：
/home/yarizakurahime/Food/standalone_food_risk_kb

输入文件：
knowledge/corpora/rag_corpus_methods_standards.jsonl

目标：
用“模型逐条阅读、判断、手动改写文件”的方式，逐步构建乳制品可调用的方法标准层。

强规则：
1. 不能使用 Python、批处理脚本、自动分类脚本来完成主任务。
2. 每一轮只允许处理一个小批次，不能一次性处理整库。
3. 每一轮最多只改一个目标文件。
4. 每一轮处理完成后必须停下来汇报。
5. 必须允许 uncertain。
6. 不得伪造来源字段。

允许的 kb_role：
- dairy_specific_standard
- general_method_applicable_to_dairy
- mixed_scope_method_with_dairy
- non_dairy
- uncertain

decision：
- keep
- drop
- uncertain

本轮执行方式：
1. 只读取一小段记录。
2. 只处理当前这一小段。
3. 只改一个输出文件。
4. 本轮结束时说明处理了哪些记录、为什么这样判断、下一轮继续哪些记录。

完成条件：
只有全部原始记录都被逐批处理过后，才允许输出：
<promise>METHODS_LAYER_MANUAL_DONE</promise>
" --max-iterations 80 --completion-promise "METHODS_LAYER_MANUAL_DONE"
```

## 当前建议

如果模型在 RalphLoop 中继续出现：

- 为了尽快结束而过度 keep
- 为了规避误删而把大量记录都放进 `general_method_applicable_to_dairy`
- 没有真正逐条阅读记录

则不要继续扩大 prompt，而是进一步缩小每轮批次，例如：

- 每轮只处理 2 条记录
- 每轮只允许追加 1 个文件

目标是提高判断质量，而不是提高清洗速度。
