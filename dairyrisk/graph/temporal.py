"""
时序图构建器 (TemporalGraphBuilder)

管理时序异构图的构建、时间窗口管理和快照创建。
支持滑动窗口（默认7天）、时序快照（按小时/天/周）和增量更新。
"""

import json
import sqlite3
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading
import logging

from dairyrisk.graph.nodes import (
    NodeType, EnterpriseNode, RawMaterialNode, ProductionLineNode,
    BatchNode, LogisticsNode, RetailNode
)
from dairyrisk.graph.edges import EdgeType, Edge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TimeGranularity(Enum):
    """时间粒度枚举"""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"


@dataclass
class TemporalNode:
    """时序节点包装器"""
    node: Any  # 原始节点对象
    node_type: NodeType
    node_id: str
    timestamps: List[datetime] = field(default_factory=list)  # 节点出现的时间点
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    features_history: List[Dict[str, Any]] = field(default_factory=list)  # 特征历史
    
    def __post_init__(self):
        if self.first_seen is None and self.timestamps:
            self.first_seen = min(self.timestamps)
            self.last_seen = max(self.timestamps)
    
    def add_timestamp(self, timestamp: datetime, features: Optional[Dict] = None):
        """添加新的时间点"""
        self.timestamps.append(timestamp)
        self.timestamps.sort()
        self.first_seen = self.timestamps[0]
        self.last_seen = self.timestamps[-1]
        if features:
            self.features_history.append({
                "timestamp": timestamp.isoformat(),
                "features": features
            })
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "timestamp_count": len(self.timestamps),
            "features_history_count": len(self.features_history)
        }


@dataclass
class TemporalEdge:
    """时序边包装器"""
    edge: Edge
    edge_type: EdgeType
    timestamps: List[datetime] = field(default_factory=list)
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    weight_history: List[Dict] = field(default_factory=list)
    
    def __post_init__(self):
        if self.first_seen is None and self.timestamps:
            self.first_seen = min(self.timestamps)
            self.last_seen = max(self.timestamps)
    
    def add_timestamp(self, timestamp: datetime, weight: float = 1.0):
        """添加新的时间点"""
        self.timestamps.append(timestamp)
        self.timestamps.sort()
        self.first_seen = self.timestamps[0]
        self.last_seen = self.timestamps[-1]
        self.weight_history.append({
            "timestamp": timestamp.isoformat(),
            "weight": weight
        })


@dataclass
class TimeWindow:
    """时间窗口定义"""
    start: datetime
    end: datetime
    
    def contains(self, timestamp: datetime) -> bool:
        """检查时间点是否在窗口内"""
        return self.start <= timestamp <= self.end
    
    def duration_days(self) -> int:
        """获取窗口天数"""
        return (self.end - self.start).days
    
    def to_dict(self) -> Dict:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "duration_days": self.duration_days()
        }


class TemporalGraphBuilder:
    """
    时序图构建器
    
    核心功能：
    - 时间窗口管理（滑动窗口，默认7天）
    - 时序快照创建（按小时/天/周）
    - 增量更新机制（新数据接入）
    - 过期数据清理（自动淘汰旧数据）
    """
    
    def __init__(
        self,
        data_dir: Optional[str] = None,
        window_days: int = 7,
        enable_auto_cleanup: bool = True,
        db_path: Optional[str] = None
    ):
        """
        初始化时序图构建器
        
        Args:
            data_dir: 数据存储目录
            window_days: 滑动窗口天数（默认7天）
            enable_auto_cleanup: 是否启用自动清理
            db_path: SQLite数据库路径（可选）
        """
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent.parent / "data" / "temporal"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.window_days = window_days
        self.enable_auto_cleanup = enable_auto_cleanup
        self.db_path = db_path or str(self.data_dir / "temporal_graph.db")
        
        # 内存中的时序图数据
        self._temporal_nodes: Dict[str, TemporalNode] = {}
        self._temporal_edges: Dict[str, TemporalEdge] = {}
        self._current_window: Optional[TimeWindow] = None
        
        # 节点索引（按类型）
        self._node_index_by_type: Dict[NodeType, Set[str]] = {
            node_type: set() for node_type in NodeType
        }
        
        # 边索引（按类型）
        self._edge_index_by_type: Dict[EdgeType, Set[str]] = {
            edge_type: set() for edge_type in EdgeType
        }
        
        # 邻居索引（用于快速遍历）
        self._out_neighbors: Dict[str, Set[str]] = {}  # node_id -> set of dst_node_ids
        self._in_neighbors: Dict[str, Set[str]] = {}   # node_id -> set of src_node_ids
        
        # 线程锁
        self._lock = threading.RLock()
        
        # 初始化数据库
        self._init_db()
        
        # 初始化时间窗口
        self._update_window()
        
        logger.info(f"TemporalGraphBuilder 初始化完成: window={window_days}天, db={self.db_path}")
    
    def _init_db(self):
        """初始化SQLite数据库"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 节点表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS temporal_nodes (
                    node_id TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    node_data TEXT NOT NULL,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    features_history TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 边表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS temporal_edges (
                    edge_id TEXT PRIMARY KEY,
                    src_id TEXT NOT NULL,
                    dst_id TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    edge_data TEXT NOT NULL,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    weight_history TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 快照表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS graph_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    granularity TEXT NOT NULL,
                    node_count INTEGER,
                    edge_count INTEGER,
                    snapshot_data BLOB,
                    compression_type TEXT DEFAULT 'gzip',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 时序事件表（用于回溯）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS temporal_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    node_id TEXT,
                    edge_id TEXT,
                    timestamp TIMESTAMP NOT NULL,
                    event_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_type ON temporal_nodes(node_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_time ON temporal_nodes(first_seen, last_seen)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_type ON temporal_edges(edge_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_src ON temporal_edges(src_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_dst ON temporal_edges(dst_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_time ON graph_snapshots(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_time ON temporal_events(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_node ON temporal_events(node_id)")
            
            conn.commit()
        
        logger.info("数据库初始化完成")
    
    def _update_window(self):
        """更新时间窗口"""
        now = datetime.now()
        self._current_window = TimeWindow(
            start=now - timedelta(days=self.window_days),
            end=now
        )
        logger.debug(f"时间窗口更新: {self._current_window.to_dict()}")
    
    def _get_edge_id(self, src_id: str, dst_id: str, edge_type: EdgeType) -> str:
        """生成边的唯一ID"""
        key = f"{src_id}__{edge_type.name}__{dst_id}"
        return hashlib.md5(key.encode()).hexdigest()
    
    # ==================== 节点操作 ====================
    
    def add_node(
        self,
        node: Any,
        node_type: NodeType,
        timestamp: Optional[datetime] = None,
        features: Optional[Dict] = None
    ) -> str:
        """
        添加时序节点
        
        Args:
            node: 节点对象
            node_type: 节点类型
            timestamp: 时间点（默认为当前时间）
            features: 节点特征（可选）
            
        Returns:
            node_id: 节点ID
        """
        with self._lock:
            node_id = getattr(node, 'node_id', str(id(node)))
            timestamp = timestamp or datetime.now()
            
            if node_id in self._temporal_nodes:
                # 更新现有节点
                temporal_node = self._temporal_nodes[node_id]
                temporal_node.add_timestamp(timestamp, features)
                logger.debug(f"更新节点: {node_id}")
            else:
                # 创建新节点
                temporal_node = TemporalNode(
                    node=node,
                    node_type=node_type,
                    node_id=node_id,
                    timestamps=[timestamp],
                    first_seen=timestamp,
                    last_seen=timestamp
                )
                if features:
                    temporal_node.features_history.append({
                        "timestamp": timestamp.isoformat(),
                        "features": features
                    })
                self._temporal_nodes[node_id] = temporal_node
                self._node_index_by_type[node_type].add(node_id)
                logger.debug(f"添加新节点: {node_id}")
            
            # 保存到数据库
            self._save_node_to_db(temporal_node)
            
            return node_id
    
    def _save_node_to_db(self, temporal_node: TemporalNode):
        """保存节点到数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO temporal_nodes 
                    (node_id, node_type, node_data, first_seen, last_seen, features_history)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    temporal_node.node_id,
                    temporal_node.node_type.value,
                    json.dumps(asdict(temporal_node.node) if hasattr(temporal_node.node, '__dataclass_fields__') else {"id": temporal_node.node_id}),
                    temporal_node.first_seen.isoformat() if temporal_node.first_seen else None,
                    temporal_node.last_seen.isoformat() if temporal_node.last_seen else None,
                    json.dumps(temporal_node.features_history)
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"保存节点到数据库失败: {e}")
    
    def get_node(self, node_id: str) -> Optional[TemporalNode]:
        """获取时序节点"""
        with self._lock:
            return self._temporal_nodes.get(node_id)
    
    def remove_node(self, node_id: str) -> bool:
        """
        移除节点及其关联的边
        
        Args:
            node_id: 节点ID
            
        Returns:
            是否成功移除
        """
        with self._lock:
            if node_id not in self._temporal_nodes:
                return False
            
            temporal_node = self._temporal_nodes[node_id]
            node_type = temporal_node.node_type
            
            # 移除关联的边
            edges_to_remove = []
            for edge_id, temporal_edge in self._temporal_edges.items():
                if temporal_edge.edge.src_id == node_id or temporal_edge.edge.dst_id == node_id:
                    edges_to_remove.append(edge_id)
            
            for edge_id in edges_to_remove:
                self.remove_edge_by_id(edge_id)
            
            # 移除节点
            del self._temporal_nodes[node_id]
            self._node_index_by_type[node_type].discard(node_id)
            
            # 从数据库删除
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM temporal_nodes WHERE node_id = ?", (node_id,))
                    conn.commit()
            except Exception as e:
                logger.error(f"从数据库删除节点失败: {e}")
            
            logger.info(f"移除节点: {node_id}, 关联边: {len(edges_to_remove)}")
            return True
    
    # ==================== 边操作 ====================
    
    def add_edge(
        self,
        edge: Edge,
        timestamp: Optional[datetime] = None,
        weight: float = 1.0
    ) -> str:
        """
        添加时序边
        
        Args:
            edge: 边对象
            timestamp: 时间点（默认为当前时间）
            weight: 边权重
            
        Returns:
            edge_id: 边ID
        """
        with self._lock:
            edge_id = self._get_edge_id(edge.src_id, edge.dst_id, edge.edge_type)
            timestamp = timestamp or datetime.now()
            
            if edge_id in self._temporal_edges:
                # 更新现有边
                temporal_edge = self._temporal_edges[edge_id]
                temporal_edge.add_timestamp(timestamp, weight)
                logger.debug(f"更新边: {edge_id}")
            else:
                # 创建新边
                temporal_edge = TemporalEdge(
                    edge=edge,
                    edge_type=edge.edge_type,
                    timestamps=[timestamp],
                    first_seen=timestamp,
                    last_seen=timestamp
                )
                temporal_edge.weight_history.append({
                    "timestamp": timestamp.isoformat(),
                    "weight": weight
                })
                self._temporal_edges[edge_id] = temporal_edge
                self._edge_index_by_type[edge.edge_type].add(edge_id)
                
                # 更新邻居索引
                if edge.src_id not in self._out_neighbors:
                    self._out_neighbors[edge.src_id] = set()
                self._out_neighbors[edge.src_id].add(edge.dst_id)
                
                if edge.dst_id not in self._in_neighbors:
                    self._in_neighbors[edge.dst_id] = set()
                self._in_neighbors[edge.dst_id].add(edge.src_id)
                
                logger.debug(f"添加新边: {edge_id}")
            
            # 保存到数据库
            self._save_edge_to_db(edge_id, temporal_edge)
            
            return edge_id
    
    def _save_edge_to_db(self, edge_id: str, temporal_edge: TemporalEdge):
        """保存边到数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO temporal_edges 
                    (edge_id, src_id, dst_id, edge_type, edge_data, first_seen, last_seen, weight_history)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    edge_id,
                    temporal_edge.edge.src_id,
                    temporal_edge.edge.dst_id,
                    temporal_edge.edge_type.name,
                    json.dumps({
                        "src_id": temporal_edge.edge.src_id,
                        "dst_id": temporal_edge.edge.dst_id,
                        "weight": temporal_edge.edge.weight
                    }),
                    temporal_edge.first_seen.isoformat() if temporal_edge.first_seen else None,
                    temporal_edge.last_seen.isoformat() if temporal_edge.last_seen else None,
                    json.dumps(temporal_edge.weight_history)
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"保存边到数据库失败: {e}")
    
    def remove_edge_by_id(self, edge_id: str) -> bool:
        """通过ID移除边"""
        with self._lock:
            if edge_id not in self._temporal_edges:
                return False
            
            temporal_edge = self._temporal_edges[edge_id]
            src_id = temporal_edge.edge.src_id
            dst_id = temporal_edge.edge.dst_id
            
            # 从索引中移除
            self._edge_index_by_type[temporal_edge.edge_type].discard(edge_id)
            
            if src_id in self._out_neighbors:
                self._out_neighbors[src_id].discard(dst_id)
            if dst_id in self._in_neighbors:
                self._in_neighbors[dst_id].discard(src_id)
            
            # 从内存中移除
            del self._temporal_edges[edge_id]
            
            # 从数据库删除
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM temporal_edges WHERE edge_id = ?", (edge_id,))
                    conn.commit()
            except Exception as e:
                logger.error(f"从数据库删除边失败: {e}")
            
            return True
    
    # ==================== 查询操作 ====================
    
    def get_nodes_by_type(self, node_type: NodeType) -> List[TemporalNode]:
        """获取指定类型的所有节点"""
        with self._lock:
            node_ids = self._node_index_by_type.get(node_type, set())
            return [self._temporal_nodes[nid] for nid in node_ids if nid in self._temporal_nodes]
    
    def get_edges_by_type(self, edge_type: EdgeType) -> List[TemporalEdge]:
        """获取指定类型的所有边"""
        with self._lock:
            edge_ids = self._edge_index_by_type.get(edge_type, set())
            return [self._temporal_edges[eid] for eid in edge_ids if eid in self._temporal_edges]
    
    def get_neighbors(
        self,
        node_id: str,
        direction: str = "out"
    ) -> List[str]:
        """
        获取邻居节点
        
        Args:
            node_id: 节点ID
            direction: "out"（出邻居）/"in"（入邻居）/"all"（所有邻居）
            
        Returns:
            邻居节点ID列表
        """
        with self._lock:
            neighbors = set()
            if direction in ("out", "all"):
                neighbors.update(self._out_neighbors.get(node_id, set()))
            if direction in ("in", "all"):
                neighbors.update(self._in_neighbors.get(node_id, set()))
            return list(neighbors)
    
    def get_temporal_changes(
        self,
        node_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict]:
        """
        获取节点的时序变化
        
        Args:
            node_id: 节点ID
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            时序变化列表
        """
        with self._lock:
            temporal_node = self._temporal_nodes.get(node_id)
            if not temporal_node:
                return []
            
            changes = []
            for history in temporal_node.features_history:
                ts = datetime.fromisoformat(history["timestamp"])
                if start_time and ts < start_time:
                    continue
                if end_time and ts > end_time:
                    continue
                changes.append(history)
            
            return changes
    
    # ==================== 窗口和清理 ====================
    
    def get_current_window(self) -> TimeWindow:
        """获取当前时间窗口"""
        self._update_window()
        return self._current_window
    
    def cleanup_expired_data(self) -> Dict[str, int]:
        """
        清理过期数据
        
        Returns:
            清理统计信息
        """
        with self._lock:
            self._update_window()
            window_start = self._current_window.start
            
            removed_nodes = 0
            removed_edges = 0
            
            # 清理过期节点
            nodes_to_remove = []
            for node_id, temporal_node in self._temporal_nodes.items():
                if temporal_node.last_seen < window_start:
                    nodes_to_remove.append(node_id)
            
            for node_id in nodes_to_remove:
                if self.remove_node(node_id):
                    removed_nodes += 1
            
            # 清理过期边
            edges_to_remove = []
            for edge_id, temporal_edge in self._temporal_edges.items():
                if temporal_edge.last_seen < window_start:
                    edges_to_remove.append(edge_id)
            
            for edge_id in edges_to_remove:
                if self.remove_edge_by_id(edge_id):
                    removed_edges += 1
            
            stats = {
                "removed_nodes": removed_nodes,
                "removed_edges": removed_edges,
                "window_start": window_start.isoformat(),
                "remaining_nodes": len(self._temporal_nodes),
                "remaining_edges": len(self._temporal_edges)
            }
            
            logger.info(f"清理完成: 移除节点={removed_nodes}, 移除边={removed_edges}")
            return stats
    
    # ==================== 统计信息 ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """获取时序图统计信息"""
        with self._lock:
            self._update_window()
            
            node_stats = {node_type.value: len(node_ids) 
                         for node_type, node_ids in self._node_index_by_type.items()}
            edge_stats = {edge_type.value: len(edge_ids) 
                         for edge_type, edge_ids in self._edge_index_by_type.items()}
            
            return {
                "total_nodes": len(self._temporal_nodes),
                "total_edges": len(self._temporal_edges),
                "node_stats": node_stats,
                "edge_stats": edge_stats,
                "current_window": self._current_window.to_dict(),
                "window_days": self.window_days,
                "db_path": self.db_path
            }
    
    def get_node_temporal_summary(self, node_id: str) -> Optional[Dict]:
        """获取节点时序摘要"""
        with self._lock:
            temporal_node = self._temporal_nodes.get(node_id)
            if not temporal_node:
                return None
            
            # 获取关联边数
            out_degree = len(self._out_neighbors.get(node_id, set()))
            in_degree = len(self._in_neighbors.get(node_id, set()))
            
            return {
                "node_id": node_id,
                "node_type": temporal_node.node_type.value,
                "first_seen": temporal_node.first_seen.isoformat() if temporal_node.first_seen else None,
                "last_seen": temporal_node.last_seen.isoformat() if temporal_node.last_seen else None,
                "timespan_days": (temporal_node.last_seen - temporal_node.first_seen).days 
                    if temporal_node.first_seen and temporal_node.last_seen else 0,
                "timestamp_count": len(temporal_node.timestamps),
                "features_history_count": len(temporal_node.features_history),
                "out_degree": out_degree,
                "in_degree": in_degree
            }


# ==================== 便捷函数 ====================

def create_temporal_builder(
    data_dir: Optional[str] = None,
    window_days: int = 7
) -> TemporalGraphBuilder:
    """创建时序图构建器实例"""
    return TemporalGraphBuilder(
        data_dir=data_dir,
        window_days=window_days,
        enable_auto_cleanup=True
    )
