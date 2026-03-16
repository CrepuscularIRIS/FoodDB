# 乳制品供应链风险研判系统 - 稳定性修复总结

## 问题概述
用户报告点击演示案例时频繁报错 "研判请求失败 - 无法识别目标"，原因是案例库的查询文本（如"雀巢能恩 ARA原料污染"）无法匹配到模拟数据中的批次/企业ID。

## 修复内容

### 1. 案例库数据修复 (`data/mock/case_library.json`)
- **问题**：`demo_batch_id` 指向不存在的批次（如 BATCH-NESTLE-2026-001）
- **修复**：添加 `target_hint` 字段，映射到实际存在的批次ID
  ```json
  "target_hint": {
    "type": "batch",
    "batch_id": "BATCH-000015",
    "enterprise_id": "ENT-0009",
    "product_name": "莫斯利安"
  }
  ```
- **结果**：所有10个案例现在都映射到有效的模拟数据

### 2. 增强识别逻辑 (`agent/workflow.py`)
- **问题**：`_identify_target()` 仅支持精确ID匹配，无法处理多关键词查询
- **修复**：实现4级回退策略
  1. 精确ID匹配（BATCH-xxx, ENT-xxx）
  2. 名称精确匹配
  3. 分词关键词搜索（企业优先）
  4. 无法识别时提供候选建议
- **结果**："光明乳业 莫斯利安" 等复合查询可正确匹配到 BATCH-000015

### 3. 添加关键词搜索 (`agent/retriever.py`)
- **新增方法**：
  - `search_enterprise_candidates(query, top_k)` - 企业关键词搜索
  - `search_batch_candidates(query, top_k)` - 批次关键词搜索
- **算法**：提取2字以上关键词，计算匹配分数（完全匹配10分，部分匹配5分）
- **结果**：支持模糊匹配，查询更灵活

### 4. CORS配置修复 (`backend/api.py`)
- **问题**：前端在端口3009运行，但CORS仅允许3000-3002
- **修复**：扩展允许的源端口 3000-3009
- **结果**：前端可正常访问后端API

### 5. 前端增强 (`frontend/`)

#### API层 (`lib/api.ts`)
- 添加 `DemoCase` 和 `TargetHint` 类型定义
- `/demo_cases` 端点返回 `target_hint` 字段

#### 演示案例组件 (`components/DemoCases.tsx`)
- 更新 `onSelect` 回调签名，支持传递 `target_hint`
- 使用 `target_hint.batch_id` 进行精确查询

#### 主页面 (`app/page.tsx`)
- `handleDemoSelect` 优先使用 `target_hint` 中的ID
- 增强错误显示：多行错误信息分行展示
- 添加候选建议显示

## 测试验证

### API测试
```bash
# 测试关键词搜索
curl -X POST http://localhost:8000/assess -d '{"query": "莫斯利安"}'
# 结果：成功匹配到 BATCH-000015

# 测试精确ID
curl -X POST http://localhost:8000/assess -d '{"query": "BATCH-000015"}'
# 结果：成功，风险等级 medium (45.0)
```

### 端到端测试
- 搜索 "莫斯利安" -> 识别为 "上海晨冠乳业有限公司-莫斯利安"
- 完整 workflow 执行成功（8个步骤）
- 生成完整风险研判报告

## 系统鲁棒性提升

| 场景 | 修复前 | 修复后 |
|------|--------|--------|
| 演示案例点击 | 报错 "无法识别目标" | 使用 target_hint 精确查询，成功 |
| 产品名称搜索 | 失败（如"莫斯利安"） | 关键词匹配成功 |
| 复合查询 | 失败（如"光明乳业 莫斯利安"） | 分词匹配成功 |
| 错误提示 | 简单 "无法识别目标" | 带候选建议的详细提示 |
| 跨域请求 | 浏览器拦截 | CORS 配置正确，请求成功 |

## 6. 传播分析增强 (`agent/workflow.py`)

### 问题
原有的 `_analyze_propagation` 只返回基础信息，缺少：
- 传播概率计算
- 风险耦合分析
- 关键传播节点识别
- 管控建议

### 修复
新增增强版传播分析：

1. **传播概率计算**
   ```python
   base_prob = current_risk * edge_weight
   hop_decay = 0.7 ** current_hop  # 跳数衰减
   edge_type_factor = factor(edge_type)
   risk_influence = base_prob * hop_decay * edge_type_factor
   ```

2. **边类型因子**
   - production: 0.9 (生产关系风险高)
   - transport: 0.8 (运输/冷链传播)
   - raw_material: 0.85 (原料关联)
   - supply: 0.7 (供应关系)

3. **关键节点识别**
   - 基于子节点数（出度）识别传播枢纽
   - 计算betweenness中心性分数

4. **管控建议生成**
   - immediate: 控制关键传播节点
   - high: 隔离直接关联节点
   - medium: 溯源上游原料

5. **风险趋势分析**
   - rapid_expansion: 快速扩散 (>50%增长)
   - gradual_expansion: 缓慢扩散
   - contained: 基本受控
   - declining: 逐渐消退

## 7. LLM调用优化 (`agent/workflow.py`, `hooks/useStreamingAgent.ts`)

### 问题
- LLM调用使用mock模式，速度过快不真实
- 没有重试机制
- 步骤延迟固定，不够真实

### 修复

1. **配置检测**
   ```python
   has_minimax_config = bool(
       os.environ.get("MINIMAX_API_KEY") and
       os.environ.get("MINIMAX_GROUP_ID")
   )
   llm_client = get_llm_client(use_mock=not has_minimax_config)
   ```

2. **重试机制**
   - 最多2次重试
   - 失败后3秒延迟再试
   - 详细的错误记录

3. **前端步骤延迟优化**
   ```typescript
   const stepDelays = {
     'identify': 800,      // 对象识别
     'retrieve': 1500,     // 数据检索
     'gb_match': 1200,     // 规则匹配
     'score': 1000,        // 风险计算
     'graph_analysis': 1500, // 图分析
     'case_match': 1000,   // 案例匹配
     'llm_analysis': 3000, // LLM分析最慢
     'propagation': 2000,  // 传播分析
   };
   ```

4. **延迟显示**
   - 显示LLM API调用延迟(ms)
   - 显示Token使用量

## 测试验证

### 传播分析测试
```bash
curl -X POST http://localhost:8000/assess \
  -d '{"query": "BATCH-000015", "with_propagation": true}'
```

结果：
- Affected nodes: 22
- Diffusion coefficient: 0.16
- Risk trend: rapid_expansion
- Key nodes: 1
- Containment suggestions: 2

### LLM配置
复制 `.env.example` 为 `.env` 并填入Minimax API密钥：
```bash
cp .env.example .env
# 编辑 .env 填入 MINIMAX_API_KEY 和 MINIMAX_GROUP_ID
```

## 建议的后续优化

1. **缓存机制**：为关键词搜索结果添加缓存
2. **异步LLM调用**：真正的流式SSE响应
3. **传播可视化**：前端展示传播路径图
4. **实时监控**：WebSocket推送研判进度
