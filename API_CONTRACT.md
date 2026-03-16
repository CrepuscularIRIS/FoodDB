# API 契约文档

## 概述

本文档定义了乳制品供应链风险研判智能体的前后端 API 接口规范。

## 通信方式

- **Node 前端** -> **Python 后端**
- **协议**: HTTP/REST
- **数据格式**: JSON
- **字符编码**: UTF-8

## 基础信息

```yaml
base_url: http://localhost:8000
version: v1
timeout: 60s
```

## 接口列表

### 1. 风险研判

#### POST /assess

执行风险研判。

**请求参数**:
```json
{
  "query": "string",           // 查询字符串（企业ID/名称 或 批次ID/号）
  "with_propagation": false    // 是否启用风险传播分析（可选，默认false）
}
```

**响应**:
```json
{
  "success": true,
  "data": {
    "report_id": "RPT-20260313-143211-BATCH-000001",
    "generated_at": "2026-03-13 14:32:11",
    "target_type": "batch",
    "target_id": "BATCH-000001",
    "target_name": "上海纽贝滋营养乳品-原料乳",
    "risk_level": "medium",
    "risk_score": 51.0,
    "conclusion": "经综合研判，批次...",
    "evidence_summary": "检验记录1条...",
    "related_inspections": [
      {
        "inspection_id": "INS-000001",
        "inspection_date": "2024-10-10",
        "test_result": "unqualified",
        "unqualified_items": "大肠菌群"
      }
    ],
    "related_events": [],
    "supply_chain_path": [
      {
        "direction": "upstream",
        "node_type": "牧场",
        "name": "光明牧业金山牧场",
        "relation": "raw_material_supplier"
      }
    ],
    "gb_references": [
      {
        "gb_no": "GB 19645-2010",
        "clause": "冷链储运要求",
        "requirement": "巴氏杀菌乳应在2-6°C条件下储存和运输"
      }
    ],
    "triggered_rules": [
      {
        "factor": "product_type",
        "score": 70,
        "reason": "产品类型风险: raw_milk"
      }
    ],
    "sampling_suggestions": [
      {
        "priority": "high",
        "action": "立即抽检",
        "target": "BATCH-000001",
        "reason": "风险评分51.0分",
        "sampling_items": ["菌落总数", "大肠菌群", "蛋白质"],
        "deadline": "24小时内"
      }
    ],
    "traceability_suggestions": [
      {
        "direction": "upstream",
        "target": "光明牧业金山牧场",
        "action": "核查原料批次和供应商资质",
        "evidence_needed": ["原料检验报告", "供应商许可证"]
      }
    ],
    "risk_mitigation_suggestions": [
      {
        "category": "储运管理",
        "action": "整改冷链设施",
        "details": "检查冷藏设备和温控系统"
      }
    ],
    "propagation_analysis": {
      "source_node": "BATCH-000001",
      "max_hops": 3,
      "affected_nodes": 5,
      "propagation_radius": 2,
      "affected_list": [
        {"node_id": "ENT-0001", "hop": 1}
      ]
    }
  }
}
```

**错误响应**:
```json
{
  "success": false,
  "error": "未找到目标: BATCH-000001"
}
```

---

### 2. 批量研判

#### POST /batch_assess

批量执行风险研判。

**请求参数**:
```json
{
  "queries": ["BATCH-000001", "ENT-0005"]
}
```

**响应**:
```json
{
  "success": true,
  "data": [
    {
      "report_id": "RPT-xxx",
      "risk_level": "medium",
      "risk_score": 51.0,
      // ... 完整报告
    }
  ]
}
```

---

### 3. 获取演示案例

#### GET /demo_cases

获取预定义的演示案例列表。

**响应**:
```json
{
  "success": true,
  "data": [
    {
      "id": "case1",
      "name": "低温奶冷链异常",
      "description": "巴氏杀菌乳冷链温度异常...",
      "query": "BATCH-000001"
    }
  ]
}
```

---

### 4. 数据查询

#### GET /enterprises

获取企业列表。

**响应**:
```json
{
  "success": true,
  "data": [
    {
      "enterprise_id": "ENT-0001",
      "enterprise_name": "光明乳业股份有限公司",
      "enterprise_type": "large",
      "node_type": "乳企",
      "credit_rating": "A",
      "historical_violation_count": 0
    }
  ]
}
```

#### GET /enterprises/{id}

获取企业详情。

**响应**: 企业完整信息

#### GET /batches

获取批次列表。

**响应**:
```json
{
  "success": true,
  "data": [
    {
      "batch_id": "BATCH-000001",
      "enterprise_id": "ENT-0001",
      "product_name": "鲜牛奶",
      "product_type": "pasteurized",
      "batch_no": "20240320-9883",
      "production_date": "2024-03-20"
    }
  ]
}
```

#### GET /batches/{id}

获取批次详情。

**响应**: 批次完整信息

---

### 5. 抽检优化

#### POST /sampling/suggestions

获取抽检建议。

**请求参数**:
```json
{
  "enterprise_id": "ENT-0001"  // 可选，不提供则返回全局建议
}
```

**响应**:
```json
{
  "success": true,
  "data": {
    "suggestions": [
      {
        "priority": "high",
        "action": "优先抽检",
        "target": "ENT-0001",
        "reason": "风险评分较高",
        "sampling_items": ["菌落总数", "大肠菌群"],
        "deadline": "3日内"
      }
    ]
  }
}
```

#### GET /sampling/top_n

获取Top-N抽检清单。

**查询参数**:
- `n`: 数量（默认10）

**响应**:
```json
{
  "success": true,
  "data": {
    "total": 10,
    "items": [
      {
        "rank": 1,
        "target_id": "BATCH-000001",
        "target_name": "光明鲜牛奶",
        "risk_score": 85.0,
        "risk_level": "high",
        "priority": "immediate",
        "sampling_items": ["菌落总数", "大肠菌群", "蛋白质"]
      }
    ]
  }
}
```

---

### 6. 传播分析

#### POST /propagation/analyze

执行风险传播分析。

**请求参数**:
```json
{
  "node_id": "BATCH-000001",
  "max_hops": 3
}
```

**响应**:
```json
{
  "success": true,
  "data": {
    "source_node": "BATCH-000001",
    "max_hops": 3,
    "affected_nodes": 5,
    "propagation_radius": 2,
    "affected_list": [
      {"node_id": "ENT-0001", "hop": 1},
      {"node_id": "ENT-0002", "hop": 2}
    ],
    "propagation_tree": {
      "node_id": "BATCH-000001",
      "children": [
        {
          "node_id": "ENT-0001",
          "hop": 1,
          "children": []
        }
      ]
    }
  }
}
```

---

## 数据模型

### RiskLevel 枚举
```typescript
type RiskLevel = 'high' | 'medium' | 'low';
```

### TargetType 枚举
```typescript
type TargetType = 'batch' | 'enterprise';
```

### Enterprise 模型
```typescript
interface Enterprise {
  enterprise_id: string;
  enterprise_name: string;
  enterprise_type: 'large' | 'medium' | 'small' | 'micro';
  node_type: '牧场' | '乳企' | '物流' | '仓储' | '零售';
  address: string;
  latitude?: number;
  longitude?: number;
  license_no: string;
  credit_rating: 'A' | 'B' | 'C' | 'D';
  historical_violation_count: number;
  supervision_freq: number;
  haccp_certified: boolean;
  iso22000_certified: boolean;
}
```

### Batch 模型
```typescript
interface Batch {
  batch_id: string;
  enterprise_id: string;
  product_name: string;
  product_type: 'pasteurized' | 'UHT' | 'yogurt' | 'powder' | 'raw_milk';
  batch_no: string;
  production_date: string;
  shelf_life: number;
  storage_temp_avg?: number;
  transport_temp_avg?: number;
  transport_duration_hours?: number;
}
```

---

## 错误码

| 错误码 | 描述 |
|--------|------|
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## 前后端集成说明

### Node 前端调用 Python 后端

#### 方式1: 直接调用 Python CLI

```javascript
const { exec } = require('child_process');

// 调用 run_demo.py
exec(`python run_demo.py --query "${query}" --json`, (error, stdout, stderr) => {
  if (error) {
    console.error(`执行错误: ${error}`);
    return;
  }
  const result = JSON.parse(stdout);
  // 处理结果
});
```

#### 方式2: FastAPI 服务（推荐）

后端需要提供 FastAPI 服务封装现有功能：

```python
# backend/api.py
from fastapi import FastAPI
from agent.workflow import RiskAssessmentAgent

app = FastAPI()
agent = RiskAssessmentAgent()

@app.post("/assess")
async def assess(request: AssessRequest):
    report = agent.assess(request.query, request.with_propagation)
    return {"success": True, "data": report}
```

启动服务:
```bash
uvicorn backend.api:app --host 0.0.0.0 --port 8000
```

前端调用:
```javascript
const response = await axios.post('http://localhost:8000/assess', {
  query: 'BATCH-000001',
  with_propagation: true
});
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-13 | 初始版本 |
| v1.1 | 2026-03-13 | 添加前端对接接口 |
