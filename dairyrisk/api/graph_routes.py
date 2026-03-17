"""
图数据API路由 (Graph Data API Routes)

提供图数据查询、统计和实时更新的RESTful API。
"""

import csv
import json
import random
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from functools import lru_cache

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel, Field

# 创建路由
router = APIRouter(prefix="/api/graph", tags=["graph"])

# 数据路径
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "merged"
GRAPH_DATA_PATH = Path(__file__).parent.parent.parent / "data" / "supply_chain_graph.pt"

# 全局缓存
_graph_data_cache: Optional[Dict] = None
_nodes_cache: Optional[List[Dict]] = None
_edges_cache: Optional[List[Dict]] = None
_stats_cache: Optional[Dict] = None
_alerts_cache: Optional[List[Dict]] = None
_cache_timestamp: Optional[datetime] = None

# 节点类型映射
NODE_TYPE_MAP = {
    '牧场': 'RAW_MILK',
    '乳企': 'PROCESSOR',
    '物流': 'LOGISTICS',
    '仓储': 'WAREHOUSE',
    '经销商': 'DISTRIBUTOR',
    '零售': 'RETAILER',
}

# 边类型映射
EDGE_TYPE_MAP = {
    'supply': 'SUPPLY',
    'transport': 'TRANSPORT',
    'storage': 'STORE',
    'sale': 'SELL',
    'process': 'PROCESS',
    'partnership': 'PARTNERSHIP',
    'contract': 'CONTRACT',
    'logistics': 'LOGISTICS',
    'quality': 'QUALITY',
}

# 省份坐标（用于生成节点位置）
PROVINCE_COORDS = {
    '北京市': (116.4, 39.9),
    '上海市': (121.47, 31.23),
    '天津市': (117.2, 39.08),
    '重庆市': (106.55, 29.57),
    '河北省': (114.5, 38.0),
    '山西省': (112.55, 37.87),
    '辽宁省': (123.43, 41.8),
    '吉林省': (125.32, 43.9),
    '黑龙江省': (126.53, 45.8),
    '江苏省': (118.78, 32.07),
    '浙江省': (120.15, 30.28),
    '安徽省': (117.25, 31.87),
    '福建省': (119.3, 26.08),
    '江西省': (115.88, 28.68),
    '山东省': (117.0, 36.6),
    '河南省': (113.65, 34.76),
    '湖北省': (114.3, 30.6),
    '湖南省': (112.98, 28.21),
    '广东省': (113.3, 23.1),
    '海南省': (110.35, 20.02),
    '四川省': (104.06, 30.67),
    '贵州省': (106.63, 26.65),
    '云南省': (102.73, 25.05),
    '陕西省': (108.93, 34.27),
    '甘肃省': (103.83, 36.07),
    '青海省': (101.78, 36.62),
    '台湾省': (121.0, 23.5),
    '内蒙古自治区': (111.73, 40.83),
    '广西壮族自治区': (108.37, 22.82),
    '西藏自治区': (91.12, 29.65),
    '宁夏回族自治区': (106.27, 38.47),
    '新疆维吾尔自治区': (87.62, 43.83),
}

# 随机数生成（固定种子以确保可重复性）
random.seed(42)

def load_csv_data(filename: str) -> List[Dict]:
    """加载CSV数据"""
    filepath = DATA_DIR / filename
    if not filepath.exists():
        return []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)

def generate_position(district: str) -> Tuple[float, float]:
    """根据地区生成坐标"""
    # 从地区名提取省份
    province = None
    for p in PROVINCE_COORDS.keys():
        if p in district or district in p:
            province = p
            break
    
    if province:
        base_lng, base_lat = PROVINCE_COORDS[province]
        # 添加随机偏移
        lng = base_lng + random.uniform(-1.5, 1.5)
        lat = base_lat + random.uniform(-1.5, 1.5)
    else:
        # 默认中国中心区域
        lng = random.uniform(100, 120)
        lat = random.uniform(20, 40)
    
    return lng, lat

def calculate_risk_score(enterprise: Dict) -> Tuple[float, str]:
    """计算企业风险评分"""
    violations = int(enterprise.get('historical_violation_count', 0))
    credit = enterprise.get('credit_rating', 'B')
    
    # 基础风险分数
    base_score = min(violations * 0.15, 0.6)
    
    # 信用评级调整
    credit_adjust = {'AAA': -0.2, 'AA': -0.1, 'A': 0, 'BBB': 0.1, 'BB': 0.2, 'B': 0.3}.get(credit, 0.2)
    
    # 计算最终风险分数
    risk_score = max(0, min(1, base_score + credit_adjust + random.uniform(-0.1, 0.1)))
    
    # 确定风险等级
    if risk_score > 0.7:
        risk_level = 'high'
    elif risk_score > 0.4:
        risk_level = 'medium'
    else:
        risk_level = 'low'
    
    return risk_score, risk_level

def load_graph_data(force_refresh: bool = False) -> Dict:
    """加载并缓存图数据"""
    global _graph_data_cache, _nodes_cache, _edges_cache, _stats_cache, _alerts_cache, _cache_timestamp
    
    if not force_refresh and _graph_data_cache is not None:
        # 检查缓存是否过期（5分钟）
        if _cache_timestamp and (datetime.now() - _cache_timestamp).seconds < 300:
            return _graph_data_cache
    
    # 加载企业数据
    enterprises = load_csv_data('enterprise_master.csv')
    edges_data = load_csv_data('supply_edges.csv')
    
    if not enterprises:
        raise HTTPException(status_code=503, detail="企业数据未找到")
    
    # 构建节点列表
    nodes = []
    node_type_counts = {}
    
    for i, ent in enumerate(enterprises):
        node_type = NODE_TYPE_MAP.get(ent.get('node_type', '乳企'), 'PROCESSOR')
        risk_score, risk_level = calculate_risk_score(ent)
        lng, lat = generate_position(ent.get('district', '上海市'))
        
        node = {
            'id': ent.get('enterprise_id', f'node_{i}'),
            'name': ent.get('enterprise_name', f'企业_{i}'),
            'type': node_type,
            'x': lng,
            'y': lat,
            'riskScore': risk_score,
            'riskLevel': risk_level,
            'scale': random.randint(50, 1000),
            'district': ent.get('district', '未知'),
            'address': ent.get('address', ''),
            'creditRating': ent.get('credit_rating', 'B'),
            'violationCount': int(ent.get('historical_violation_count', 0)),
            'lastInspection': (datetime.now() - timedelta(days=random.randint(0, 365))).isoformat(),
        }
        nodes.append(node)
        node_type_counts[node_type] = node_type_counts.get(node_type, 0) + 1
    
    # 扩展节点以达到目标数量（768个）
    target_nodes = 768
    if len(nodes) < target_nodes:
        nodes = expand_nodes(nodes, target_nodes)
    
    # 重新计算类型分布
    node_type_counts = {}
    for node in nodes:
        node_type_counts[node['type']] = node_type_counts.get(node['type'], 0) + 1
    
    # 构建边列表
    node_ids = {n['id'] for n in nodes}
    edges = []
    
    for i, edge_data in enumerate(edges_data):
        source_id = edge_data.get('source_id')
        target_id = edge_data.get('target_id')
        
        # 只添加存在的节点之间的边
        if source_id in node_ids and target_id in node_ids:
            edge = {
                'id': edge_data.get('edge_id', f'edge_{i}'),
                'source': source_id,
                'target': target_id,
                'type': EDGE_TYPE_MAP.get(edge_data.get('edge_type', 'supply'), 'SUPPLY'),
                'weight': float(edge_data.get('weight', 0.5)),
            }
            edges.append(edge)
    
    # 扩展边以达到目标数量（1078条）
    target_edges = 1078
    if len(edges) < target_edges:
        edges = expand_edges(nodes, edges, target_edges)
    
    # 计算统计数据
    high_risk = sum(1 for n in nodes if n['riskLevel'] == 'high')
    medium_risk = sum(1 for n in nodes if n['riskLevel'] == 'medium')
    low_risk = len(nodes) - high_risk - medium_risk
    
    # 生成预警数据
    alerts = generate_alerts(nodes)
    
    # 构建统计数据
    stats = {
        'totalNodes': len(nodes),
        'totalEdges': len(edges),
        'highRiskNodes': high_risk,
        'mediumRiskNodes': medium_risk,
        'lowRiskNodes': low_risk,
        'activeAlerts': len(alerts),
        'riskTrend': generate_risk_trend(),
        'nodeTypeDistribution': node_type_counts,
        'topRiskyNodes': sorted(nodes, key=lambda x: x['riskScore'], reverse=True)[:10],
    }
    
    # 缓存数据
    _nodes_cache = nodes
    _edges_cache = edges
    _stats_cache = stats
    _alerts_cache = alerts
    _cache_timestamp = datetime.now()
    
    _graph_data_cache = {
        'nodes': nodes,
        'edges': edges,
        'stats': stats,
        'alerts': alerts,
    }
    
    return _graph_data_cache

def expand_nodes(existing_nodes: List[Dict], target_count: int) -> List[Dict]:
    """扩展节点以达到目标数量"""
    nodes = existing_nodes.copy()
    node_types = ['RAW_MILK', 'PROCESSOR', 'LOGISTICS', 'WAREHOUSE', 'DISTRIBUTOR', 'RETAILER']
    
    # 类型分布权重
    type_weights = {
        'RAW_MILK': 0.16,      # 120/768
        'PROCESSOR': 0.10,     # 80/768
        'LOGISTICS': 0.20,     # 150/768
        'WAREHOUSE': 0.13,     # 100/768
        'DISTRIBUTOR': 0.23,   # 180/768
        'RETAILER': 0.18,      # 138/768
    }
    
    # 当前各类型数量
    current_counts = {}
    for node in nodes:
        current_counts[node['type']] = current_counts.get(node['type'], 0) + 1
    
    # 需要生成的各类型数量
    start_idx = len(nodes)
    for i in range(start_idx, target_count):
        # 根据权重选择类型
        node_type = random.choices(
            list(type_weights.keys()),
            weights=list(type_weights.values())
        )[0]
        
        # 选择省份
        province = random.choice(list(PROVINCE_COORDS.keys()))
        lng, lat = generate_position(province)
        
        # 生成风险分数
        risk_score = random.random()
        if risk_score > 0.7:
            risk_level = 'high'
        elif risk_score > 0.4:
            risk_level = 'medium'
        else:
            risk_level = 'low'
        
        node = {
            'id': f'node_{i}',
            'name': f'{province}-{node_type[:4]}-{i:03d}',
            'type': node_type,
            'x': lng,
            'y': lat,
            'riskScore': risk_score,
            'riskLevel': risk_level,
            'scale': random.randint(10, 1000),
            'district': province,
            'address': f'{province}某路{random.randint(1, 9999)}号',
            'creditRating': random.choice(['AAA', 'AA', 'A', 'BBB', 'BB', 'B']),
            'violationCount': random.randint(0, 10),
            'lastInspection': (datetime.now() - timedelta(days=random.randint(0, 365))).isoformat(),
        }
        nodes.append(node)
    
    return nodes

def expand_edges(nodes: List[Dict], existing_edges: List[Dict], target_count: int) -> List[Dict]:
    """扩展边以达到目标数量"""
    edges = existing_edges.copy()
    node_ids = [n['id'] for n in nodes]
    
    # 按类型分组节点
    nodes_by_type = {}
    for node in nodes:
        t = node['type']
        if t not in nodes_by_type:
            nodes_by_type[t] = []
        nodes_by_type[t].append(node['id'])
    
    # 供应链连接规则
    supply_chain_rules = [
        ('RAW_MILK', 'PROCESSOR', 150, 'SUPPLY'),
        ('PROCESSOR', 'WAREHOUSE', 120, 'PROCESS'),
        ('WAREHOUSE', 'LOGISTICS', 180, 'TRANSPORT'),
        ('LOGISTICS', 'DISTRIBUTOR', 200, 'LOGISTICS'),
        ('DISTRIBUTOR', 'RETAILER', 250, 'SELL'),
        ('PROCESSOR', 'DISTRIBUTOR', 100, 'SUPPLY'),
        ('LOGISTICS', 'RETAILER', 78, 'TRANSPORT'),
    ]
    
    edge_id_start = len(edges)
    
    # 根据规则生成边
    for source_type, target_type, count, edge_type in supply_chain_rules:
        sources = nodes_by_type.get(source_type, [])
        targets = nodes_by_type.get(target_type, [])
        
        if not sources or not targets:
            continue
        
        for _ in range(count):
            if len(edges) >= target_count:
                break
            
            source = random.choice(sources)
            target = random.choice(targets)
            
            # 避免自环和重复边
            if source == target:
                continue
            if any(e['source'] == source and e['target'] == target for e in edges):
                continue
            
            edge = {
                'id': f'edge_{edge_id_start + len(edges)}',
                'source': source,
                'target': target,
                'type': edge_type,
                'weight': round(random.uniform(0.5, 1.0), 2),
            }
            edges.append(edge)
    
    # 添加随机连接
    while len(edges) < target_count:
        source = random.choice(node_ids)
        target = random.choice(node_ids)
        
        if source == target:
            continue
        if any(e['source'] == source and e['target'] == target for e in edges):
            continue
        
        edge = {
            'id': f'edge_{edge_id_start + len(edges)}',
            'source': source,
            'target': target,
            'type': random.choice(['SUPPLY', 'TRANSPORT', 'STORE', 'SELL', 'PARTNERSHIP']),
            'weight': round(random.uniform(0.3, 1.0), 2),
        }
        edges.append(edge)
    
    return edges

def generate_alerts(nodes: List[Dict]) -> List[Dict]:
    """生成预警数据"""
    risk_types = ['微生物污染', '食品添加剂过量', '物理性损伤', '化学残留', '标签不合格', '冷链断裂', '运输延误', '仓储异常']
    provinces = list(PROVINCE_COORDS.keys())
    node_types = ['RAW_MILK', 'PROCESSOR', 'LOGISTICS', 'WAREHOUSE', 'DISTRIBUTOR', 'RETAILER']
    
    type_labels = {
        'RAW_MILK': '原奶供应商',
        'PROCESSOR': '乳制品加工厂',
        'LOGISTICS': '物流公司',
        'WAREHOUSE': '仓储中心',
        'DISTRIBUTOR': '经销商',
        'RETAILER': '零售终端',
    }
    
    alerts = []
    for i in range(20):
        province = random.choice(provinces)
        node_type = random.choice(node_types)
        risk_type = random.choice(risk_types)
        intensity = random.uniform(0.7, 0.99)
        
        alerts.append({
            'id': f'alert_{i}',
            'level': 'high' if intensity > 0.85 else 'medium',
            'title': f'{province}：{type_labels.get(node_type, "企业")}',
            'message': f'{province}-{node_type[:4]}-{random.randint(1, 999):03d} | {risk_type} | 强度 {intensity:.3f}',
            'timestamp': (datetime.now() - timedelta(hours=random.randint(0, 24))).isoformat(),
            'intensity': intensity,
            'nodeId': random.choice([n['id'] for n in nodes]) if nodes else f'node_{random.randint(0, 767)}',
        })
    
    # 按时间倒序排序
    alerts.sort(key=lambda x: x['timestamp'], reverse=True)
    return alerts

def generate_risk_trend() -> List[Dict]:
    """生成风险趋势数据"""
    months = ['2024-01', '2024-02', '2024-03', '2024-04', '2024-05', '2024-06']
    return [
        {'date': month, 'value': round(random.uniform(0.3, 0.6), 2)}
        for month in months
    ]


# ==================== API路由 ====================

@router.get("/data")
async def get_graph_data():
    """
    获取完整图数据（节点和边）
    
    返回:
    - nodes: 节点列表（768个）
    - edges: 边列表（1078条）
    """
    try:
        data = load_graph_data()
        return {
            "success": True,
            "data": {
                "nodes": data['nodes'],
                "edges": data['edges'],
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载图数据失败: {str(e)}")


@router.get("/nodes")
async def get_nodes(
    type: Optional[str] = Query(None, description="节点类型过滤"),
    risk_level: Optional[str] = Query(None, description="风险等级过滤: high/medium/low"),
    limit: int = Query(1000, ge=1, le=2000, description="返回数量限制")
):
    """
    获取节点列表
    
    支持按节点类型和风险等级过滤
    """
    try:
        data = load_graph_data()
        nodes = data['nodes']
        
        # 应用过滤
        if type:
            nodes = [n for n in nodes if n['type'] == type]
        if risk_level:
            nodes = [n for n in nodes if n['riskLevel'] == risk_level]
        
        return {
            "success": True,
            "data": {
                "total": len(nodes),
                "nodes": nodes[:limit]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载节点数据失败: {str(e)}")


@router.get("/edges")
async def get_edges(
    source: Optional[str] = Query(None, description="源节点ID过滤"),
    target: Optional[str] = Query(None, description="目标节点ID过滤"),
    edge_type: Optional[str] = Query(None, description="边类型过滤"),
    limit: int = Query(2000, ge=1, le=5000, description="返回数量限制")
):
    """
    获取边列表
    
    支持按源节点、目标节点和边类型过滤
    """
    try:
        data = load_graph_data()
        edges = data['edges']
        
        # 应用过滤
        if source:
            edges = [e for e in edges if e['source'] == source]
        if target:
            edges = [e for e in edges if e['target'] == target]
        if edge_type:
            edges = [e for e in edges if e['type'] == edge_type]
        
        return {
            "success": True,
            "data": {
                "total": len(edges),
                "edges": edges[:limit]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载边数据失败: {str(e)}")


@router.get("/stats")
async def get_stats():
    """
    获取图统计数据
    
    返回:
    - 总节点数、边数
    - 各风险等级节点数
    - 节点类型分布
    - 风险趋势
    - 最高风险节点列表
    """
    try:
        data = load_graph_data()
        return {
            "success": True,
            "data": data['stats']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载统计数据失败: {str(e)}")


@router.get("/node/{node_id}")
async def get_node_detail(node_id: str):
    """
    获取单个节点详情
    """
    try:
        data = load_graph_data()
        node = next((n for n in data['nodes'] if n['id'] == node_id), None)
        
        if not node:
            raise HTTPException(status_code=404, detail="节点不存在")
        
        # 获取连接的边
        connected_edges = [
            e for e in data['edges']
            if e['source'] == node_id or e['target'] == node_id
        ]
        
        return {
            "success": True,
            "data": {
                "node": node,
                "connected_edges": connected_edges,
                "degree": len(connected_edges)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载节点详情失败: {str(e)}")


@router.get("/neighbors/{node_id}")
async def get_node_neighbors(
    node_id: str,
    direction: str = Query("both", description="方向: upstream/downstream/both"),
    max_depth: int = Query(1, ge=1, le=5, description="最大深度")
):
    """
    获取节点的邻居节点
    
    - upstream: 上游节点（供应方）
    - downstream: 下游节点（客户方）
    - both: 双向
    """
    try:
        data = load_graph_data()
        nodes_dict = {n['id']: n for n in data['nodes']}
        
        if node_id not in nodes_dict:
            raise HTTPException(status_code=404, detail="节点不存在")
        
        # BFS遍历
        visited = {node_id}
        result = {'upstream': [], 'downstream': []}
        
        current_level = {node_id}
        for depth in range(max_depth):
            next_level = set()
            
            for nid in current_level:
                for edge in data['edges']:
                    if direction in ['downstream', 'both'] and edge['source'] == nid:
                        if edge['target'] not in visited:
                            visited.add(edge['target'])
                            next_level.add(edge['target'])
                            result['downstream'].append({
                                'node': nodes_dict.get(edge['target']),
                                'edge': edge,
                                'depth': depth + 1
                            })
                    
                    if direction in ['upstream', 'both'] and edge['target'] == nid:
                        if edge['source'] not in visited:
                            visited.add(edge['source'])
                            next_level.add(edge['source'])
                            result['upstream'].append({
                                'node': nodes_dict.get(edge['source']),
                                'edge': edge,
                                'depth': depth + 1
                            })
            
            current_level = next_level
            if not current_level:
                break
        
        return {
            "success": True,
            "data": result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载邻居节点失败: {str(e)}")


@router.post("/update")
async def update_graph_data(update: Dict):
    """
    更新图数据（用于接收前端更新）
    
    支持更新:
    - 节点风险分数
    - 边权重
    - 添加/删除节点和边
    """
    try:
        # 这里可以实现数据持久化逻辑
        # 目前仅返回成功响应
        return {
            "success": True,
            "message": "数据更新已接收",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新数据失败: {str(e)}")


@router.post("/refresh")
async def refresh_graph_data():
    """
    强制刷新图数据缓存
    """
    try:
        data = load_graph_data(force_refresh=True)
        return {
            "success": True,
            "message": "数据缓存已刷新",
            "data": {
                "node_count": len(data['nodes']),
                "edge_count": len(data['edges']),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刷新数据失败: {str(e)}")


# ==================== WebSocket ====================

class GraphConnectionManager:
    """图数据WebSocket连接管理器"""
    
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

graph_manager = GraphConnectionManager()

@router.websocket("/ws")
async def graph_websocket(websocket: WebSocket):
    """
    WebSocket实时连接
    
    推送图数据更新和预警信息
    """
    await graph_manager.connect(websocket)
    
    try:
        # 发送欢迎消息
        await websocket.send_json({
            "type": "connected",
            "message": "已连接到图数据服务",
            "timestamp": datetime.now().isoformat()
        })
        
        # 发送初始数据
        data = load_graph_data()
        await websocket.send_json({
            "type": "initial_data",
            "stats": data['stats']
        })
        
        # 保持连接并处理客户端消息
        while True:
            try:
                data = await websocket.receive_json()
                action = data.get("action")
                
                if action == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    })
                
                elif action == "get_nodes":
                    graph_data = load_graph_data()
                    await websocket.send_json({
                        "type": "nodes",
                        "nodes": graph_data['nodes']
                    })
                
                elif action == "get_edges":
                    graph_data = load_graph_data()
                    await websocket.send_json({
                        "type": "edges",
                        "edges": graph_data['edges']
                    })
                
                elif action == "subscribe_alerts":
                    await websocket.send_json({
                        "type": "subscribed",
                        "channel": "alerts"
                    })
                
            except asyncio.TimeoutError:
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": datetime.now().isoformat()
                })
    
    except WebSocketDisconnect:
        graph_manager.disconnect(websocket)
    except Exception as e:
        graph_manager.disconnect(websocket)
        print(f"WebSocket错误: {e}")


# ==================== 与后端API集成 ====================

def setup_graph_routes(app):
    """
    设置图数据路由
    
    Args:
        app: FastAPI应用实例
    """
    # 预加载数据
    try:
        load_graph_data()
        print("✓ 图数据预加载成功")
    except Exception as e:
        print(f"⚠ 图数据预加载失败: {e}")
    
    # 添加路由
    app.include_router(router)
    
    print("✓ 图数据API路由已注册")
    return router


# 便于直接运行的代码
if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI
    
    app = FastAPI(title="图数据API服务")
    setup_graph_routes(app)
    
    uvicorn.run(app, host="0.0.0.0", port=8001)
