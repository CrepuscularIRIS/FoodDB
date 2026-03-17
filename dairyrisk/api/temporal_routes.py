"""
时序API路由 (Temporal Routes)

提供时序图动态更新的RESTful API和WebSocket实时推送功能。
"""

import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# 导入时序图模块
try:
    from dairyrisk.graph.temporal import (
        TemporalGraphBuilder, TimeWindow, TimeGranularity,
        create_temporal_builder
    )
    from dairyrisk.graph.incremental import (
        IncrementalUpdateEngine, UpdateEvent, UpdateEventType,
        IncrementalUpdateResult
    )
    from dairyrisk.data.snapshot_manager import (
        SnapshotManager, GraphSnapshot
    )
    from dairyrisk.graph.nodes import NodeType
    from dairyrisk.graph.edges import EdgeType
    TEMPORAL_AVAILABLE = True
except ImportError as e:
    TEMPORAL_AVAILABLE = False
    print(f"时序模块导入失败: {e}")

# 全局实例
temporal_builder: Optional[TemporalGraphBuilder] = None
incremental_engine: Optional[IncrementalUpdateEngine] = None
snapshot_manager: Optional[SnapshotManager] = None

# WebSocket连接管理器
class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: Dict[str, Any]):
        """广播消息给所有连接"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)
        
        # 清理断开的连接
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)
    
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """发送个人消息"""
        try:
            await websocket.send_json(message)
        except:
            pass

manager = ConnectionManager()


# ==================== 数据模型 ====================

class NodeCreateRequest(BaseModel):
    """节点创建请求"""
    node_id: str
    node_type: str = Field(..., description="节点类型: enterprise, batch, raw_material, logistics, retail, production_line")
    data: Dict[str, Any] = Field(default_factory=dict, description="节点数据")
    features: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None


class NodeUpdateRequest(BaseModel):
    """节点更新请求"""
    data: Dict[str, Any]
    features: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None


class EdgeCreateRequest(BaseModel):
    """边创建请求"""
    src_id: str
    dst_id: str
    edge_type: str = Field(..., description="边类型: supplies, produces, used_in, transported_by, etc.")
    weight: float = 1.0
    features: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None


class BatchImportRequest(BaseModel):
    """批量导入请求"""
    nodes: List[NodeCreateRequest] = Field(default_factory=list)
    edges: List[EdgeCreateRequest] = Field(default_factory=list)
    timestamp: Optional[str] = None


class SnapshotCreateRequest(BaseModel):
    """快照创建请求"""
    granularity: str = Field(default="day", description="时间粒度: hour, day, week")
    metadata: Optional[Dict[str, Any]] = None


class GraphUpdateResponse(BaseModel):
    """图更新响应"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


# ==================== 路由 ====================

router = APIRouter(prefix="/api/graph", tags=["temporal-graph"])


def init_temporal_components(data_dir: Optional[str] = None):
    """初始化时序组件"""
    global temporal_builder, incremental_engine, snapshot_manager
    
    if not TEMPORAL_AVAILABLE:
        raise RuntimeError("时序模块不可用")
    
    if temporal_builder is None:
        temporal_builder = create_temporal_builder(data_dir=data_dir, window_days=7)
    
    if incremental_engine is None:
        incremental_engine = IncrementalUpdateEngine(
            temporal_builder=temporal_builder,
            enable_async_processing=True
        )
        
        # 订阅事件以进行WebSocket推送
        def on_update_event(event: UpdateEvent):
            asyncio.create_task(broadcast_update(event))
        
        for event_type in UpdateEventType:
            incremental_engine.subscribe(event_type, on_update_event)
    
    if snapshot_manager is None:
        snapshot_manager = SnapshotManager(
            temporal_builder=temporal_builder,
            data_dir=data_dir
        )
    
    return temporal_builder, incremental_engine, snapshot_manager


async def broadcast_update(event: UpdateEvent):
    """广播更新事件"""
    await manager.broadcast({
        "type": "graph_update",
        "event_type": event.event_type.value,
        "timestamp": event.timestamp.isoformat(),
        "node_id": event.node_id,
        "edge_id": event.edge_id,
        "data": event.data
    })


# ==================== 增量更新API ====================

@router.post("/update", response_model=GraphUpdateResponse)
async def update_graph(request: BatchImportRequest):
    """
    批量更新图数据
    
    接收新节点和边数据，进行增量更新
    """
    if not TEMPORAL_AVAILABLE or incremental_engine is None:
        raise HTTPException(status_code=503, detail="时序模块未初始化")
    
    try:
        # 转换请求数据
        batch_data = {
            "enterprises": [],
            "raw_materials": [],
            "production_lines": [],
            "batches": [],
            "logistics": [],
            "retail": [],
            "edges": []
        }
        
        node_type_map = {
            "enterprise": "enterprises",
            "batch": "batches",
            "raw_material": "raw_materials",
            "logistics": "logistics",
            "retail": "retail",
            "production_line": "production_lines"
        }
        
        for node in request.nodes:
            data_dict = node.data.copy()
            data_dict["node_id"] = node.node_id
            if node.features:
                data_dict["features"] = node.features
            
            key = node_type_map.get(node.node_type)
            if key:
                batch_data[key].append(data_dict)
        
        for edge in request.edges:
            batch_data["edges"].append({
                "src_id": edge.src_id,
                "dst_id": edge.dst_id,
                "edge_type": edge.edge_type,
                "weight": edge.weight,
                "features": edge.features
            })
        
        # 解析时间戳
        timestamp = None
        if request.timestamp:
            timestamp = datetime.fromisoformat(request.timestamp)
        
        # 执行增量更新
        result = incremental_engine.import_batch_data(batch_data, timestamp)
        
        return GraphUpdateResponse(
            success=result.success,
            message=f"更新完成: 添加{len(result.added_nodes)}节点, {len(result.added_edges)}边",
            data=result.to_dict()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/nodes", response_model=GraphUpdateResponse)
async def add_node(request: NodeCreateRequest):
    """添加单个节点"""
    if not TEMPORAL_AVAILABLE or incremental_engine is None:
        raise HTTPException(status_code=503, detail="时序模块未初始化")
    
    try:
        node_type_enum = NodeType(request.node_type)
        timestamp = datetime.fromisoformat(request.timestamp) if request.timestamp else None
        
        success, message, node_id = incremental_engine.add_or_update_node(
            node_data={**request.data, "node_id": request.node_id},
            node_type=node_type_enum,
            timestamp=timestamp,
            features=request.features
        )
        
        return GraphUpdateResponse(
            success=success,
            message=message,
            data={"node_id": node_id}
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"无效的节点类型: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/nodes/{node_id}", response_model=GraphUpdateResponse)
async def update_node(node_id: str, request: NodeUpdateRequest):
    """更新节点"""
    if not TEMPORAL_AVAILABLE or temporal_builder is None:
        raise HTTPException(status_code=503, detail="时序模块未初始化")
    
    try:
        temporal_node = temporal_builder.get_node(node_id)
        if not temporal_node:
            raise HTTPException(status_code=404, detail="节点不存在")
        
        timestamp = datetime.fromisoformat(request.timestamp) if request.timestamp else datetime.now()
        
        # 更新节点
        temporal_node.add_timestamp(timestamp, request.features)
        
        return GraphUpdateResponse(
            success=True,
            message="节点更新成功",
            data={"node_id": node_id, "timestamp": timestamp.isoformat()}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/nodes/{node_id}", response_model=GraphUpdateResponse)
async def delete_node(node_id: str):
    """删除节点"""
    if not TEMPORAL_AVAILABLE or temporal_builder is None:
        raise HTTPException(status_code=503, detail="时序模块未初始化")
    
    try:
        success = temporal_builder.remove_node(node_id)
        if not success:
            raise HTTPException(status_code=404, detail="节点不存在")
        
        return GraphUpdateResponse(
            success=True,
            message="节点删除成功",
            data={"node_id": node_id}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/edges", response_model=GraphUpdateResponse)
async def add_edge(request: EdgeCreateRequest):
    """添加边"""
    if not TEMPORAL_AVAILABLE or incremental_engine is None:
        raise HTTPException(status_code=503, detail="时序模块未初始化")
    
    try:
        edge_type_enum = EdgeType[request.edge_type.upper()]
        timestamp = datetime.fromisoformat(request.timestamp) if request.timestamp else None
        
        success, message, edge_id = incremental_engine.add_or_update_edge(
            src_id=request.src_id,
            dst_id=request.dst_id,
            edge_type=edge_type_enum,
            edge_data={"features": request.features} if request.features else None,
            timestamp=timestamp,
            weight=request.weight
        )
        
        return GraphUpdateResponse(
            success=success,
            message=message,
            data={"edge_id": edge_id}
        )
        
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"无效的边类型: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 快照API ====================

@router.post("/snapshot", response_model=GraphUpdateResponse)
async def create_snapshot(request: SnapshotCreateRequest):
    """创建快照"""
    if not TEMPORAL_AVAILABLE or snapshot_manager is None:
        raise HTTPException(status_code=503, detail="时序模块未初始化")
    
    try:
        snapshot = snapshot_manager.create_snapshot(
            granularity=request.granularity,
            metadata=request.metadata
        )
        
        return GraphUpdateResponse(
            success=True,
            message="快照创建成功",
            data=snapshot.to_dict()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshot/{date}")
async def get_snapshot(date: str, granularity: str = "day"):
    """
    获取指定日期的快照
    
    - date: 日期格式 YYYY-MM-DD 或 YYYY-MM-DD-HH (小时粒度)
    - granularity: day/hour/week
    """
    if not TEMPORAL_AVAILABLE or snapshot_manager is None:
        raise HTTPException(status_code=503, detail="时序模块未初始化")
    
    try:
        snapshot = snapshot_manager.get_snapshot_by_date(date, granularity)
        if not snapshot:
            raise HTTPException(status_code=404, detail="快照不存在")
        
        return {
            "success": True,
            "data": {
                "snapshot_id": snapshot.snapshot_id,
                "timestamp": snapshot.timestamp.isoformat(),
                "granularity": snapshot.granularity,
                "node_count": snapshot.node_count,
                "edge_count": snapshot.edge_count,
                "nodes": list(snapshot.nodes.keys()),
                "edges": list(snapshot.edges.keys()),
                "metadata": snapshot.metadata
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshots")
async def list_snapshots(
    granularity: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100
):
    """列出快照"""
    if not TEMPORAL_AVAILABLE or snapshot_manager is None:
        raise HTTPException(status_code=503, detail="时序模块未初始化")
    
    try:
        start_time = datetime.fromisoformat(start_date) if start_date else None
        end_time = datetime.fromisoformat(end_date) if end_date else None
        
        snapshots = snapshot_manager.list_snapshots(
            granularity=granularity,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
        
        return {
            "success": True,
            "data": snapshots
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshot/{snapshot_id_1}/compare/{snapshot_id_2}")
async def compare_snapshots(snapshot_id_1: str, snapshot_id_2: str):
    """对比两个快照"""
    if not TEMPORAL_AVAILABLE or snapshot_manager is None:
        raise HTTPException(status_code=503, detail="时序模块未初始化")
    
    try:
        diff = snapshot_manager.compare_snapshots(snapshot_id_1, snapshot_id_2)
        return {
            "success": True,
            "data": diff
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 时序变化API ====================

@router.get("/temporal/{node_id}")
async def get_temporal_changes(
    node_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    获取节点的时序变化
    
    - node_id: 节点ID
    - start_date: 开始日期 (ISO格式)
    - end_date: 结束日期 (ISO格式)
    """
    if not TEMPORAL_AVAILABLE or temporal_builder is None:
        raise HTTPException(status_code=503, detail="时序模块未初始化")
    
    try:
        start_time = datetime.fromisoformat(start_date) if start_date else None
        end_time = datetime.fromisoformat(end_date) if end_date else None
        
        changes = temporal_builder.get_temporal_changes(node_id, start_time, end_time)
        summary = temporal_builder.get_node_temporal_summary(node_id)
        
        return {
            "success": True,
            "data": {
                "summary": summary,
                "changes": changes
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/temporal/changes")
async def get_global_changes(
    start_date: str,
    end_date: str,
    granularity: str = "day"
):
    """获取全局时序变化"""
    if not TEMPORAL_AVAILABLE or snapshot_manager is None:
        raise HTTPException(status_code=503, detail="时序模块未初始化")
    
    try:
        start_time = datetime.fromisoformat(start_date)
        end_time = datetime.fromisoformat(end_date)
        
        changes = snapshot_manager.get_temporal_changes(start_time, end_time)
        
        return {
            "success": True,
            "data": changes
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== WebSocket ====================

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket实时连接
    
    推送图更新事件:
    - node_added: 节点添加
    - node_updated: 节点更新
    - node_removed: 节点删除
    - edge_added: 边添加
    - edge_updated: 边更新
    - edge_removed: 边删除
    - risk_recalculated: 风险重计算
    """
    await manager.connect(websocket)
    
    try:
        # 发送欢迎消息
        await manager.send_personal_message({
            "type": "connected",
            "message": "已连接到图更新服务",
            "timestamp": datetime.now().isoformat()
        }, websocket)
        
        # 保持连接并处理客户端消息
        while True:
            try:
                data = await websocket.receive_json()
                
                # 处理客户端请求
                action = data.get("action")
                
                if action == "ping":
                    await manager.send_personal_message({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                
                elif action == "get_stats":
                    if temporal_builder:
                        stats = temporal_builder.get_stats()
                        await manager.send_personal_message({
                            "type": "stats",
                            "data": stats
                        }, websocket)
                
                elif action == "subscribe":
                    event_type = data.get("event_type")
                    await manager.send_personal_message({
                        "type": "subscribed",
                        "event_type": event_type,
                        "message": f"已订阅 {event_type} 事件"
                    }, websocket)
                
            except asyncio.TimeoutError:
                # 发送心跳
                await manager.send_personal_message({
                    "type": "heartbeat",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket连接断开")
    except Exception as e:
        manager.disconnect(websocket)
        logger.error(f"WebSocket错误: {e}")


# ==================== 统计和状态API ====================

@router.get("/stats")
async def get_graph_stats():
    """获取图统计信息"""
    if not TEMPORAL_AVAILABLE or temporal_builder is None:
        raise HTTPException(status_code=503, detail="时序模块未初始化")
    
    try:
        stats = temporal_builder.get_stats()
        
        # 添加增量引擎统计
        if incremental_engine:
            engine_stats = incremental_engine.get_stats()
            stats["incremental_engine"] = engine_stats
        
        # 添加快照管理器统计
        if snapshot_manager:
            snapshot_stats = snapshot_manager.get_stats()
            stats["snapshot_manager"] = snapshot_stats
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def cleanup_expired_data():
    """清理过期数据"""
    if not TEMPORAL_AVAILABLE or temporal_builder is None:
        raise HTTPException(status_code=503, detail="时序模块未初始化")
    
    try:
        stats = temporal_builder.cleanup_expired_data()
        
        # 也清理旧快照
        if snapshot_manager:
            deleted_snapshots = snapshot_manager.cleanup_old_snapshots()
            stats["deleted_snapshots"] = deleted_snapshots
        
        return {
            "success": True,
            "message": "清理完成",
            "data": stats
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 初始化函数 ====================

def setup_temporal_routes(app: FastAPI, data_dir: Optional[str] = None):
    """
    设置时序路由
    
    Args:
        app: FastAPI应用实例
        data_dir: 数据目录
    """
    # 初始化组件
    init_temporal_components(data_dir)
    
    # 添加路由
    app.include_router(router)
    
    print("✓ 时序图API路由已注册")
    return router


# 便于直接运行的代码
if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI
    
    app = FastAPI(title="时序图API服务")
    setup_temporal_routes(app)
    
    uvicorn.run(app, host="0.0.0.0", port=8001)
