# 时序图更新模块使用指南

## 模块概述

时序图更新模块实现了乳制品供应链风险研判系统的动态时序图功能，包括：

1. **时序图构建器** (`temporal.py`): 管理时间窗口、时序快照和过期数据清理
2. **增量更新引擎** (`incremental.py`): 处理新数据接入、节点边更新和风险重计算
3. **快照管理器** (`snapshot_manager.py`): 管理历史快照、回溯查询和版本控制
4. **时序API路由** (`temporal_routes.py`): 提供RESTful API和WebSocket实时推送

## 快速开始

### 1. 基础使用

```python
from dairyrisk.graph.temporal import create_temporal_builder
from dairyrisk.graph.nodes import NodeType, EnterpriseNode, EnterpriseScale

# 创建时序图构建器
builder = create_temporal_builder(
    data_dir="./temporal_data",
    window_days=7  # 7天滑动窗口
)

# 添加节点
enterprise = EnterpriseNode(
    node_id="ENT_001",
    name="光明乳业",
    scale=EnterpriseScale.LARGE,
    enterprise_type="producer",
    location="上海市"
)
builder.add_node(enterprise, NodeType.ENTERPRISE)

# 获取统计信息
stats = builder.get_stats()
print(f"总节点数: {stats['total_nodes']}")
```

### 2. 增量更新

```python
from dairyrisk.graph.incremental import IncrementalUpdateEngine
from dairyrisk.graph.nodes import NodeType

# 创建增量引擎
engine = IncrementalUpdateEngine(
    temporal_builder=builder,
    enable_async_processing=True
)

# 批量导入数据
batch_data = {
    "batches": [
        {
            "batch_id": "B202503001",
            "product_name": "鲜牛奶",
            "product_type": "milk",
            "enterprise_id": "ENT_001"
        }
    ],
    "edges": [
        {
            "src_id": "ENT_001",
            "dst_id": "B202503001",
            "edge_type": "MANUFACTURES"
        }
    ]
}

result = engine.import_batch_data(batch_data)
print(f"添加节点: {len(result.added_nodes)}")
print(f"添加边: {len(result.added_edges)}")
```

### 3. 快照管理

```python
from dairyrisk.data.snapshot_manager import SnapshotManager

# 创建快照管理器
manager = SnapshotManager(
    temporal_builder=builder,
    data_dir="./snapshot_data"
)

# 创建每日快照
snapshot = manager.create_snapshot(granularity="day")
print(f"快照ID: {snapshot.snapshot_id}")

# 查询历史快照
snapshots = manager.list_snapshots(granularity="day", limit=10)

# 获取指定日期快照
snapshot = manager.get_snapshot_by_date("2025-03-17", "day")

# 对比快照差异
diff = manager.compare_snapshots(snapshot_id_1, snapshot_id_2)
print(f"新增节点: {len(diff['added_nodes'])}")
```

### 4. API服务集成

```python
from fastapi import FastAPI
from dairyrisk.api.temporal_routes import setup_temporal_routes

app = FastAPI()

# 设置时序路由
setup_temporal_routes(app, data_dir="./data")

# 现在可以使用以下API:
# POST   /api/graph/update          - 批量更新图数据
# POST   /api/graph/nodes           - 添加节点
# DELETE /api/graph/nodes/{id}      - 删除节点
# POST   /api/graph/edges           - 添加边
# POST   /api/graph/snapshot        - 创建快照
# GET    /api/graph/snapshot/{date} - 获取历史快照
# GET    /api/graph/snapshots       - 列出快照
# GET    /api/graph/temporal/{id}   - 获取节点时序变化
# GET    /api/graph/stats           - 获取统计信息
# WS     /api/graph/ws              - WebSocket实时连接
```

## API 详细说明

### RESTful API

#### 批量更新图数据
```http
POST /api/graph/update
Content-Type: application/json

{
    "nodes": [
        {
            "node_id": "ENT_001",
            "node_type": "enterprise",
            "data": {"name": "光明乳业", "location": "上海"}
        }
    ],
    "edges": [
        {
            "src_id": "ENT_001",
            "dst_id": "BATCH_001",
            "edge_type": "MANUFACTURES",
            "weight": 1.0
        }
    ]
}
```

#### 获取历史快照
```http
GET /api/graph/snapshot/2025-03-17?granularity=day

Response:
{
    "success": true,
    "data": {
        "snapshot_id": "abc123...",
        "timestamp": "2025-03-17T00:00:00",
        "granularity": "day",
        "node_count": 150,
        "edge_count": 320,
        "nodes": ["ENT_001", "BATCH_001", ...],
        "edges": [...]
    }
}
```

#### 获取节点时序变化
```http
GET /api/graph/temporal/BATCH_001?start_date=2025-03-01&end_date=2025-03-17

Response:
{
    "success": true,
    "data": {
        "summary": {
            "node_id": "BATCH_001",
            "node_type": "batch",
            "first_seen": "2025-03-01T10:00:00",
            "last_seen": "2025-03-17T15:00:00",
            "timespan_days": 16
        },
        "changes": [
            {"timestamp": "2025-03-01T10:00:00", "features": {...}},
            {"timestamp": "2025-03-15T14:00:00", "features": {...}}
        ]
    }
}
```

### WebSocket 实时推送

连接 WebSocket:
```javascript
const ws = new WebSocket('ws://localhost:8000/api/graph/ws');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('收到更新:', data);
};

// 发送ping保持连接
ws.send(JSON.stringify({action: 'ping'}));

// 订阅特定事件
ws.send(JSON.stringify({action: 'subscribe', event_type: 'node_added'}));
```

推送事件类型:
- `node_added`: 节点添加
- `node_updated`: 节点更新
- `node_removed`: 节点删除
- `edge_added`: 边添加
- `edge_updated`: 边更新
- `edge_removed`: 边删除
- `risk_recalculated`: 风险重计算
- `batch_imported`: 批量导入完成

## 数据流

```
新数据输入 → 验证 → 增量更新 → 风险重算 → 快照保存 → WebSocket推送
                ↓
           过期清理 ← 时间窗口管理
```

## 配置选项

### TemporalGraphBuilder
- `window_days`: 滑动窗口天数（默认7天）
- `enable_auto_cleanup`: 启用自动清理
- `db_path`: SQLite数据库路径

### IncrementalUpdateEngine
- `enable_async_processing`: 启用异步处理
- `max_queue_size`: 更新队列大小

### SnapshotManager
- `default_compression`: 默认压缩类型 (gzip/none/lz4)
- `auto_cleanup_days`: 自动清理天数（默认90天）
- `max_snapshots_per_granularity`: 每种粒度最大快照数

## 存储结构

```
data/
├── temporal/
│   └── temporal_graph.db      # 时序图SQLite数据库
├── snapshots/
│   ├── snapshots.db            # 快照元数据
│   └── {snapshot_id}.bin       # 快照数据文件
└── __init__.py
```

## 验收标准检查

- [x] 能成功创建时序快照（支持日/小时粒度）
- [x] 增量更新API正常工作（添加/删除节点边）
- [x] 时间窗口滑动正常（自动清理过期数据）
- [x] WebSocket实时推送功能
- [x] 前端能显示时序演发动画（通过API支持）
- [x] 支持查询任意历史时刻的图状态
