#!/usr/bin/env python3
"""
时序图更新模块 - 使用示例

演示如何使用时序图构建器、增量更新引擎和快照管理器。
"""

# 示例1: 基础时序图操作
"""
from dairyrisk.graph.temporal import create_temporal_builder
from dairyrisk.graph.nodes import NodeType, EnterpriseNode, BatchNode, EnterpriseScale

# 创建时序图构建器
builder = create_temporal_builder(data_dir="./temporal_data", window_days=7)

# 添加企业节点
enterprise = EnterpriseNode(
    node_id="ENT_001",
    name="光明乳业",
    scale=EnterpriseScale.LARGE,
    enterprise_type="producer",
    location="上海市浦东新区"
)
builder.add_node(enterprise, NodeType.ENTERPRISE)

# 添加批次节点
batch = BatchNode(
    node_id="BATCH_001",
    batch_id="B202503001",
    product_name="鲜牛奶",
    product_type="milk",
    enterprise_id="ENT_001"
)
builder.add_node(batch, NodeType.BATCH)

# 获取统计信息
stats = builder.get_stats()
print(f"总节点数: {stats['total_nodes']}")
print(f"总边数: {stats['total_edges']}")
print(f"时间窗口: {stats['current_window']['duration_days']}天")
"""

# 示例2: 增量数据导入
"""
from dairyrisk.graph.incremental import IncrementalUpdateEngine
from dairyrisk.graph.nodes import NodeType

# 创建增量引擎
engine = IncrementalUpdateEngine(temporal_builder=builder)

# 准备批量数据
batch_data = {
    "enterprises": [
        {"node_id": "ENT_002", "name": "蒙牛乳业", "location": "上海"}
    ],
    "batches": [
        {
            "batch_id": "B202503002",
            "product_name": "酸奶",
            "product_type": "yogurt",
            "enterprise_id": "ENT_002"
        }
    ],
    "edges": [
        {
            "src_id": "ENT_002",
            "dst_id": "B202503002",
            "edge_type": "MANUFACTURES"
        }
    ]
}

# 执行批量导入
result = engine.import_batch_data(batch_data)
print(f"成功: {result.success}")
print(f"新增节点: {len(result.added_nodes)}")
print(f"新增边: {len(result.added_edges)}")
"""

# 示例3: 快照管理
"""
from dairyrisk.data.snapshot_manager import SnapshotManager

# 创建快照管理器
manager = SnapshotManager(temporal_builder=builder)

# 创建每日快照
snapshot = manager.create_snapshot(
    granularity="day",
    metadata={"description": "每日自动快照"}
)
print(f"快照ID: {snapshot.snapshot_id}")
print(f"节点数: {snapshot.node_count}")
print(f"边数: {snapshot.edge_count}")

# 列出所有快照
snapshots = manager.list_snapshots(limit=10)
for s in snapshots:
    print(f"  - {s['timestamp']} ({s['granularity']}): {s['node_count']}节点")

# 获取指定日期快照
snapshot = manager.get_snapshot_by_date("2025-03-17", "day")

# 对比两个快照
diff = manager.compare_snapshots(snapshot_id_1, snapshot_id_2)
print(f"新增节点: {len(diff['added_nodes'])}")
print(f"移除节点: {len(diff['removed_nodes'])}")
"""

# 示例4: API集成
"""
from fastapi import FastAPI
from dairyrisk.api.temporal_routes import setup_temporal_routes

app = FastAPI(title="乳制品供应链风险研判系统")

# 注册时序图路由
setup_temporal_routes(app, data_dir="./data")

# 启动服务
# uvicorn main:app --host 0.0.0.0 --port 8000
"""

# 示例5: WebSocket客户端
"""
import asyncio
import websockets
import json

async def connect_websocket():
    uri = "ws://localhost:8000/api/graph/ws"
    async with websockets.connect(uri) as websocket:
        # 接收欢迎消息
        response = await websocket.recv()
        print(f"连接成功: {response}")
        
        # 监听实时更新
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            
            if data["type"] == "graph_update":
                print(f"图更新: {data['event_type']} - {data.get('node_id', '')}")
            elif data["type"] == "heartbeat":
                print("心跳...")

# asyncio.run(connect_websocket())
"""

# 示例6: 风险重计算回调
"""
def calculate_risk_score(node_id: str) -> float:
    # 自定义风险计算逻辑
    return 0.5

# 设置风险计算器
engine.set_risk_calculator(calculate_risk_score)

# 触发风险重计算
affected_nodes = engine.trigger_risk_recalculation(
    node_ids=["BATCH_001", "BATCH_002"],
    propagate=True  # 传播到邻居节点
)
print(f"重计算节点数: {len(affected_nodes)}")
"""

# 示例7: 事件订阅
"""
from dairyrisk.graph.incremental import UpdateEventType

def on_node_added(event):
    print(f"节点添加: {event.node_id}")

def on_risk_recalculated(event):
    print(f"风险重计算: {event.node_id}")

# 订阅事件
engine.subscribe(UpdateEventType.NODE_ADDED, on_node_added)
engine.subscribe(UpdateEventType.RISK_RECALCULATED, on_risk_recalculated)
"""

# 示例8: 清理过期数据
"""
# 清理过期节点和边（基于时间窗口）
cleanup_stats = builder.cleanup_expired_data()
print(f"移除节点: {cleanup_stats['removed_nodes']}")
print(f"移除边: {cleanup_stats['removed_edges']}")

# 清理旧快照
deleted_count = manager.cleanup_old_snapshots(days=30)
print(f"删除旧快照: {deleted_count}")
"""

if __name__ == "__main__":
    print("时序图更新模块 - 使用示例")
    print("="*60)
    print("请查看源代码中的示例代码，取消注释后运行")
    print()
    print("模块列表:")
    print("  - dairyrisk.graph.temporal: 时序图构建器")
    print("  - dairyrisk.graph.incremental: 增量更新引擎")
    print("  - dairyrisk.data.snapshot_manager: 快照管理器")
    print("  - dairyrisk.api.temporal_routes: 时序API路由")
    print()
    print("详细文档: dairyrisk/docs/TEMPORAL_GRAPH_GUIDE.md")
