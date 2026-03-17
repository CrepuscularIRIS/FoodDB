"""
风险预警API路由 (Risk Alert API Routes)

提供风险传播模拟、传播路径查询、影响评估和预警管理的RESTful API。
支持WebSocket实时推送高风险预警。
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# 导入风险模块
try:
    from dairyrisk.risk.transmission import (
        RiskTransmissionModel,
        RiskTransmissionResult
    )
    from dairyrisk.risk.simulation import (
        RiskPropagationSimulator,
        SimulationConfig,
        SimulationMode,
        MonteCarloResult
    )
    from dairyrisk.risk.edge_predictor import (
        EdgeRiskPredictor,
        EdgePredictionResult
    )
    from dairyrisk.risk.alerts import (
        AlertGenerator,
        AlertSeverity,
        AlertCategory,
        AlertStatus,
        RiskAlert
    )
    from dairyrisk.graph.edges import EdgeType, Edge
    from dairyrisk.graph.nodes import NodeType
    RISK_AVAILABLE = True
except ImportError as e:
    RISK_AVAILABLE = False
    print(f"风险模块导入失败: {e}")

# 全局实例
transmission_model: Optional[RiskTransmissionModel] = None
simulator: Optional[RiskPropagationSimulator] = None
edge_predictor: Optional[EdgeRiskPredictor] = None
alert_generator: Optional[AlertGenerator] = None

# 图数据缓存（在实际应用中应从数据库或图引擎获取）
_graph_edges: Dict[str, List[Dict]] = {}
_node_risks: Dict[str, float] = {}


# ==================== WebSocket连接管理器 ====================

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

class SimulateRequest(BaseModel):
    """风险模拟请求"""
    source_node_id: str = Field(..., description="源节点ID")
    initial_risk: float = Field(default=0.8, ge=0.0, le=1.0, description="初始风险值")
    mode: str = Field(default="monte_carlo", description="模拟模式: monte_carlo, single, cascade")
    num_rounds: int = Field(default=100, ge=1, le=1000, description="蒙特卡洛轮次")
    max_steps: int = Field(default=10, ge=1, le=50, description="最大传播步数")
    risk_threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="风险阈值")
    time_step_hours: int = Field(default=1, description="时间步长（小时）")


class WhatIfScenario(BaseModel):
    """What-if场景"""
    name: str
    initial_risk: float = 0.8
    blocked_edges: List[List[str]] = Field(default_factory=list, description="阻断的边 [[src, dst], ...]")
    boosted_nodes: List[List] = Field(default_factory=list, description="增强的节点 [[node_id, factor], ...]")


class WhatIfRequest(BaseModel):
    """What-if分析请求"""
    source_node_id: str
    scenarios: List[WhatIfScenario]


class EdgePredictRequest(BaseModel):
    """边预测请求"""
    edge_type: str = Field(..., description="边类型")
    source_node_id: str
    target_node_id: str
    source_risk: float = Field(default=0.5, ge=0.0, le=1.0)
    edge_features: Optional[Dict[str, Any]] = None
    weight: float = 1.0


class AlertAcknowledgeRequest(BaseModel):
    """确认预警请求"""
    alert_id: str
    notes: Optional[str] = None


class RiskHeatmapRequest(BaseModel):
    """风险热力图请求"""
    node_ids: Optional[List[str]] = None
    time_window_hours: int = Field(default=24, ge=1, le=168)


# ==================== 路由 ====================

router = APIRouter(prefix="/api/risk", tags=["risk"])


def init_risk_components():
    """初始化风险组件"""
    global transmission_model, simulator, edge_predictor, alert_generator
    
    if not RISK_AVAILABLE:
        raise RuntimeError("风险模块不可用")
    
    if transmission_model is None:
        transmission_model = RiskTransmissionModel()
    
    if simulator is None:
        config = SimulationConfig(num_rounds=100, max_steps=10)
        simulator = RiskPropagationSimulator(transmission_model, config)
    
    if edge_predictor is None:
        edge_predictor = EdgeRiskPredictor(model_type="logistic_regression")
    
    if alert_generator is None:
        alert_generator = AlertGenerator()
    
    return transmission_model, simulator, edge_predictor, alert_generator


# ==================== 风险模拟API ====================

@router.post("/simulate")
async def simulate_risk_propagation(request: SimulateRequest):
    """
    模拟风险传播
    
    支持多种模拟模式：
    - monte_carlo: 蒙特卡洛模拟（多轮次）
    - single: 单次模拟
    - cascade: 级联失效模拟
    """
    if not RISK_AVAILABLE or simulator is None:
        raise HTTPException(status_code=503, detail="风险模块未初始化")
    
    try:
        # 更新配置
        simulator.config.num_rounds = request.num_rounds
        simulator.config.max_steps = request.max_steps
        simulator.config.risk_threshold = request.risk_threshold
        simulator.config.time_step_hours = request.time_step_hours
        
        if request.mode == "monte_carlo":
            result = simulator.run_monte_carlo(
                request.source_node_id,
                request.initial_risk,
                request.num_rounds
            )
            return {
                "success": True,
                "mode": "monte_carlo",
                "data": result.to_dict()
            }
        
        elif request.mode == "single":
            result = simulator.run_single_simulation(
                request.source_node_id,
                request.initial_risk
            )
            return {
                "success": True,
                "mode": "single",
                "data": result.to_dict()
            }
        
        elif request.mode == "cascade":
            result = simulator.run_cascade_failure(
                [request.source_node_id],
                request.initial_risk
            )
            return {
                "success": True,
                "mode": "cascade",
                "data": result.to_dict()
            }
        
        else:
            raise HTTPException(status_code=400, detail=f"不支持的模拟模式: {request.mode}")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/what-if")
async def what_if_analysis(request: WhatIfRequest):
    """
    What-if假设分析
    
    支持多种场景对比：
    - 阻断特定边
    - 增强特定节点
    - 不同初始风险
    """
    if not RISK_AVAILABLE or simulator is None:
        raise HTTPException(status_code=503, detail="风险模块未初始化")
    
    try:
        # 转换场景格式
        scenarios = []
        for s in request.scenarios:
            scenarios.append({
                "name": s.name,
                "initial_risk": s.initial_risk,
                "blocked_edges": [(e[0], e[1]) for e in s.blocked_edges],
                "boosted_nodes": [(n[0], n[1]) for n in s.boosted_nodes]
            })
        
        result = simulator.run_what_if_analysis(
            request.source_node_id,
            scenarios
        )
        
        return {
            "success": True,
            "data": result
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 传播路径API ====================

@router.get("/propagation/{node_id}")
async def get_propagation_paths(
    node_id: str,
    direction: str = Query("downstream", description="方向: upstream/downstream/both"),
    max_depth: int = Query(5, ge=1, le=10),
    min_coeff: float = Query(0.1, ge=0.0, le=1.0)
):
    """
    获取传播路径
    
    - upstream: 向上游追溯风险来源
    - downstream: 向下游追踪风险影响
    - both: 双向查询
    """
    if not RISK_AVAILABLE or transmission_model is None:
        raise HTTPException(status_code=503, detail="风险模块未初始化")
    
    try:
        result = {"node_id": node_id, "paths": {}}
        
        if direction in ["upstream", "both"]:
            upstream_paths = transmission_model.trace_upstream(
                node_id, simulator._graph_edges if simulator else {},
                max_depth=max_depth, min_coeff=min_coeff
            )
            result["paths"]["upstream"] = [
                {
                    "path": [node_id] + [p[0] for p in path],
                    "coefficients": [p[2] for p in path],
                    "total_coeff": round(
                        __import__('functools').reduce(lambda x, y: x * y, [p[2] for p in path], 1.0), 4
                    ) if path else 0
                }
                for path in upstream_paths[:20]  # 限制返回数量
            ]
        
        if direction in ["downstream", "both"]:
            downstream_paths = transmission_model.trace_downstream(
                node_id, simulator._graph_edges if simulator else {},
                max_depth=max_depth, min_coeff=min_coeff
            )
            result["paths"]["downstream"] = [
                {
                    "path": [node_id] + [p[0] for p in path],
                    "coefficients": [p[2] for p in path],
                    "total_coeff": round(
                        __import__('functools').reduce(lambda x, y: x * y, [p[2] for p in path], 1.0), 4
                    ) if path else 0
                }
                for path in downstream_paths[:20]
            ]
        
        return {"success": True, "data": result}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 影响评估API ====================

@router.get("/impact/{node_id}")
async def get_impact_assessment(
    node_id: str,
    node_risk: float = Query(0.8, ge=0.0, le=1.0, description="节点风险值"),
    max_depth: int = Query(3, ge=1, le=5)
):
    """
    获取节点风险影响评估
    
    评估指定节点的风险对供应链的影响范围和程度。
    """
    if not RISK_AVAILABLE or transmission_model is None:
        raise HTTPException(status_code=503, detail="风险模块未初始化")
    
    try:
        impact = transmission_model.calculate_risk_impact_score(
            node_id, node_risk,
            simulator._graph_edges if simulator else {},
            max_depth=max_depth
        )
        
        # 生成预警（如果影响严重）
        if impact["total_impact_score"] > 0.5 and alert_generator:
            alert = alert_generator.create_cascade_alert(
                node_id,
                impact["affected_node_count"],
                impact.get("critical_node_count", 0),
                impact
            )
            if alert:
                # 通过WebSocket推送
                asyncio.create_task(manager.broadcast({
                    "type": "high_risk_alert",
                    "alert": alert.to_dict()
                }))
        
        return {"success": True, "data": impact}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 边级风险预测API ====================

@router.post("/edge/predict")
async def predict_edge_risk(request: EdgePredictRequest):
    """
    预测边的风险传导
    
    输入边特征和源节点风险，输出传导概率。
    """
    if not RISK_AVAILABLE or edge_predictor is None:
        raise HTTPException(status_code=503, detail="风险模块未初始化")
    
    try:
        # 创建边对象
        edge_type = EdgeType[request.edge_type.upper()]
        edge = Edge(
            src_id=request.source_node_id,
            dst_id=request.target_node_id,
            edge_type=edge_type,
            weight=request.weight,
            features=request.edge_features
        )
        
        # 预测
        result = edge_predictor.predict(edge, request.source_risk)
        
        # 如果风险高，生成预警
        if result.transmission_probability > 0.7 and alert_generator:
            alert = alert_generator.create_prediction_alert(result)
            if alert:
                asyncio.create_task(manager.broadcast({
                    "type": "edge_risk_alert",
                    "alert": alert.to_dict()
                }))
        
        return {"success": True, "data": result.to_dict()}
    
    except KeyError:
        raise HTTPException(status_code=400, detail=f"无效的边类型: {request.edge_type}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/edge/predict-batch")
async def predict_edge_risk_batch(requests: List[EdgePredictRequest]):
    """批量预测边风险"""
    if not RISK_AVAILABLE or edge_predictor is None:
        raise HTTPException(status_code=503, detail="风险模块未初始化")
    
    try:
        edges = []
        source_risks = {}
        
        for req in requests:
            edge_type = EdgeType[req.edge_type.upper()]
            edge = Edge(
                src_id=req.source_node_id,
                dst_id=req.target_node_id,
                edge_type=edge_type,
                weight=req.weight,
                features=req.edge_features
            )
            edges.append(edge)
            source_risks[req.source_node_id] = req.source_risk
        
        results = edge_predictor.predict_batch(edges, source_risks)
        
        return {
            "success": True,
            "data": [r.to_dict() for r in results]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 预警管理API ====================

@router.get("/alert")
async def get_alerts(
    status: Optional[str] = Query(None, description="状态过滤: active/acknowledged/resolved/expired"),
    severity: Optional[str] = Query(None, description="严重级别过滤: info/low/medium/high/critical"),
    category: Optional[str] = Query(None, description="类别过滤"),
    limit: int = Query(50, ge=1, le=200)
):
    """
    获取预警列表
    
    支持按状态、严重级别和类别过滤。
    """
    if not RISK_AVAILABLE or alert_generator is None:
        raise HTTPException(status_code=503, detail="风险模块未初始化")
    
    try:
        # 过滤条件
        severity_filter = None
        if severity:
            severity_filter = [AlertSeverity(s) for s in severity.split(",")]
        
        category_filter = None
        if category:
            category_filter = [AlertCategory(c) for c in category.split(",")]
        
        # 获取预警
        if status == "active":
            alerts = alert_generator.get_active_alerts(severity_filter, category_filter)
        else:
            alerts = alert_generator.get_alert_history(limit=limit)
            if severity_filter:
                alerts = [a for a in alerts if a.severity in severity_filter]
            if category_filter:
                alerts = [a for a in alerts if a.category in category_filter]
        
        return {
            "success": True,
            "data": {
                "total": len(alerts),
                "alerts": [alert.to_dict() for alert in alerts[:limit]]
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alert/summary")
async def get_alert_summary():
    """获取预警摘要统计"""
    if not RISK_AVAILABLE or alert_generator is None:
        raise HTTPException(status_code=503, detail="风险模块未初始化")
    
    try:
        summary = alert_generator.get_summary()
        return {"success": True, "data": summary.to_dict()}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alert/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, request: Optional[AlertAcknowledgeRequest] = None):
    """确认预警"""
    if not RISK_AVAILABLE or alert_generator is None:
        raise HTTPException(status_code=503, detail="风险模块未初始化")
    
    try:
        success = alert_generator.acknowledge_alert(alert_id)
        if success:
            return {"success": True, "message": "预警已确认"}
        else:
            raise HTTPException(status_code=404, detail="预警不存在或已处理")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alert/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    """解决预警"""
    if not RISK_AVAILABLE or alert_generator is None:
        raise HTTPException(status_code=503, detail="风险模块未初始化")
    
    try:
        success = alert_generator.resolve_alert(alert_id)
        if success:
            return {"success": True, "message": "预警已解决"}
        else:
            raise HTTPException(status_code=404, detail="预警不存在")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alert/{alert_id}")
async def get_alert_detail(alert_id: str):
    """获取预警详情"""
    if not RISK_AVAILABLE or alert_generator is None:
        raise HTTPException(status_code=503, detail="风险模块未初始化")
    
    try:
        alert = alert_generator.get_alert(alert_id)
        if alert:
            return {"success": True, "data": alert.to_dict()}
        else:
            raise HTTPException(status_code=404, detail="预警不存在")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 风险热力图API ====================

@router.post("/heatmap")
async def get_risk_heatmap(request: RiskHeatmapRequest):
    """
    获取风险热力图数据
    
    用于前端可视化风险分布和传播路径。
    """
    if not RISK_AVAILABLE:
        raise HTTPException(status_code=503, detail="风险模块未初始化")
    
    try:
        # 构建热力图数据
        heatmap_data = {
            "nodes": [],
            "edges": [],
            "risk_levels": {}
        }
        
        # 这里应该从实际图数据中获取
        # 简化实现：使用缓存的节点风险
        for node_id, risk in _node_risks.items():
            if request.node_ids and node_id not in request.node_ids:
                continue
            
            heatmap_data["nodes"].append({
                "id": node_id,
                "risk": risk,
                "risk_level": "high" if risk > 0.7 else "medium" if risk > 0.4 else "low"
            })
            heatmap_data["risk_levels"][node_id] = risk
        
        # 获取边（简化实现）
        if simulator:
            for src_id, targets in simulator._graph_edges.items():
                for dst_id, edge_type, coeff in targets:
                    heatmap_data["edges"].append({
                        "source": src_id,
                        "target": dst_id,
                        "type": edge_type.name if hasattr(edge_type, 'name') else str(edge_type),
                        "coefficient": coeff
                    })
        
        return {"success": True, "data": heatmap_data}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== WebSocket ====================

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket实时连接
    
    推送高风险预警和模拟进度：
    - high_risk_alert: 高风险预警
    - edge_risk_alert: 边风险预警
    - simulation_progress: 模拟进度
    - heartbeat: 心跳
    """
    await manager.connect(websocket)
    
    try:
        # 发送欢迎消息
        await manager.send_personal_message({
            "type": "connected",
            "message": "已连接到风险预警服务",
            "timestamp": datetime.now().isoformat()
        }, websocket)
        
        # 保持连接并处理客户端消息
        while True:
            try:
                data = await websocket.receive_json()
                action = data.get("action")
                
                if action == "ping":
                    await manager.send_personal_message({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                
                elif action == "subscribe_alerts":
                    severity = data.get("severity", ["high", "critical"])
                    await manager.send_personal_message({
                        "type": "subscribed",
                        "channel": "alerts",
                        "severity_filter": severity
                    }, websocket)
                
                elif action == "get_active_alerts":
                    if alert_generator:
                        alerts = alert_generator.get_active_alerts()
                        await manager.send_personal_message({
                            "type": "active_alerts",
                            "alerts": [a.to_dict() for a in alerts[:20]]
                        }, websocket)
                
            except asyncio.TimeoutError:
                await manager.send_personal_message({
                    "type": "heartbeat",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)
        print(f"WebSocket错误: {e}")


# ==================== 配置和工具API ====================

@router.get("/config/transmission-coeffs")
async def get_transmission_coefficients():
    """获取风险传导系数配置"""
    from dairyrisk.risk.transmission import RISK_TRANSMISSION_COEFFICIENTS
    
    coeffs = {
        edge_type.name if hasattr(edge_type, 'name') else str(edge_type): coeff
        for edge_type, coeff in RISK_TRANSMISSION_COEFFICIENTS.items()
    }
    
    return {"success": True, "data": coeffs}


@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "success": True,
        "status": "healthy" if RISK_AVAILABLE else "degraded",
        "modules": {
            "transmission": transmission_model is not None,
            "simulation": simulator is not None,
            "edge_predictor": edge_predictor is not None,
            "alert_generator": alert_generator is not None
        },
        "timestamp": datetime.now().isoformat()
    }


# ==================== 初始化函数 ====================

def setup_risk_routes(app: FastAPI):
    """
    设置风险路由
    
    Args:
        app: FastAPI应用实例
    """
    # 初始化组件
    try:
        init_risk_components()
        print("✓ 风险模块初始化成功")
    except Exception as e:
        print(f"⚠ 风险模块初始化失败: {e}")
    
    # 添加路由
    app.include_router(router)
    
    print("✓ 风险预警API路由已注册")
    return router


# 便于直接运行的代码
if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI
    
    app = FastAPI(title="风险预警API服务")
    setup_risk_routes(app)
    
    uvicorn.run(app, host="0.0.0.0", port=8002)
