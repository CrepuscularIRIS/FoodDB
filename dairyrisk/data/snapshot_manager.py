"""
快照管理器 (SnapshotManager)

管理时序图的历史快照：创建、存储、压缩、版本管理和回溯查询。
支持多种时间粒度（小时/天/周）的快照。
"""

import json
import gzip
import sqlite3
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Union, BinaryIO
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib
import logging
import threading

from dairyrisk.graph.temporal import TemporalGraphBuilder, TimeWindow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CompressionType(Enum):
    """压缩类型"""
    NONE = "none"
    GZIP = "gzip"
    LZ4 = "lz4"  # 需要额外安装


@dataclass
class GraphSnapshot:
    """图快照数据类"""
    snapshot_id: str
    timestamp: datetime
    granularity: str  # hour/day/week
    node_count: int
    edge_count: int
    nodes: Dict[str, Dict] = field(default_factory=dict)
    edges: Dict[str, Dict] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp.isoformat(),
            "granularity": self.granularity,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "metadata": self.metadata
        }


@dataclass
class SnapshotVersion:
    """快照版本信息"""
    version_id: str
    snapshot_id: str
    created_at: datetime
    parent_version: Optional[str] = None
    change_summary: Dict[str, int] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "version_id": self.version_id,
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at.isoformat(),
            "parent_version": self.parent_version,
            "change_summary": self.change_summary,
            "tags": self.tags
        }


class SnapshotManager:
    """
    快照管理器
    
    核心功能：
    - 创建每日/小时快照
    - 支持回溯查询
    - 快照压缩存储
    - 版本管理
    """
    
    def __init__(
        self,
        temporal_builder: Optional[TemporalGraphBuilder] = None,
        data_dir: Optional[str] = None,
        db_path: Optional[str] = None,
        default_compression: CompressionType = CompressionType.GZIP,
        auto_cleanup_days: int = 90,
        max_snapshots_per_granularity: int = 1000
    ):
        """
        初始化快照管理器
        
        Args:
            temporal_builder: 时序图构建器实例
            data_dir: 数据目录
            db_path: 数据库路径
            default_compression: 默认压缩类型
            auto_cleanup_days: 自动清理天数
            max_snapshots_per_granularity: 每种粒度最大快照数
        """
        if temporal_builder:
            self.temporal_builder = temporal_builder
        else:
            self.temporal_builder = None
        
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent.parent / "data" / "snapshots"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = db_path or str(self.data_dir / "snapshots.db")
        self.default_compression = default_compression
        self.auto_cleanup_days = auto_cleanup_days
        self.max_snapshots_per_granularity = max_snapshots_per_granularity
        
        # 缓存
        self._cache: Dict[str, GraphSnapshot] = {}
        self._cache_lock = threading.RLock()
        self._max_cache_size = 10
        
        # 初始化数据库
        self._init_db()
        
        logger.info(f"SnapshotManager 初始化完成: db={self.db_path}")
    
    def _init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 快照表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    granularity TEXT NOT NULL,
                    node_count INTEGER DEFAULT 0,
                    edge_count INTEGER DEFAULT 0,
                    snapshot_data BLOB,
                    compression_type TEXT DEFAULT 'gzip',
                    file_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)
            
            # 版本表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS versions (
                    version_id TEXT PRIMARY KEY,
                    snapshot_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    parent_version TEXT,
                    change_summary TEXT,
                    tags TEXT,
                    FOREIGN KEY (snapshot_id) REFERENCES snapshots(snapshot_id)
                )
            """)
            
            # 快照差异表（用于增量存储）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS snapshot_diffs (
                    diff_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    base_snapshot_id TEXT,
                    target_snapshot_id TEXT NOT NULL,
                    diff_data BLOB,
                    added_nodes INTEGER DEFAULT 0,
                    removed_nodes INTEGER DEFAULT 0,
                    added_edges INTEGER DEFAULT 0,
                    removed_edges INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (base_snapshot_id) REFERENCES snapshots(snapshot_id),
                    FOREIGN KEY (target_snapshot_id) REFERENCES snapshots(snapshot_id)
                )
            """)
            
            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_time ON snapshots(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_granularity ON snapshots(granularity)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_versions_snapshot ON versions(snapshot_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_diffs_base ON snapshot_diffs(base_snapshot_id)")
            
            conn.commit()
        
        logger.info("快照数据库初始化完成")
    
    def _generate_snapshot_id(self, timestamp: datetime, granularity: str) -> str:
        """生成快照ID"""
        key = f"{timestamp.isoformat()}_{granularity}"
        return hashlib.md5(key.encode()).hexdigest()[:16]
    
    def _compress_data(self, data: bytes, compression: CompressionType) -> Tuple[bytes, str]:
        """
        压缩数据
        
        Args:
            data: 原始数据
            compression: 压缩类型
            
        Returns:
            (压缩后数据, 压缩类型)
        """
        if compression == CompressionType.GZIP:
            return gzip.compress(data), "gzip"
        elif compression == CompressionType.LZ4:
            try:
                import lz4.frame
                return lz4.frame.compress(data), "lz4"
            except ImportError:
                logger.warning("LZ4不可用，使用GZIP")
                return gzip.compress(data), "gzip"
        else:
            return data, "none"
    
    def _decompress_data(self, data: bytes, compression_type: str) -> bytes:
        """
        解压数据
        
        Args:
            data: 压缩数据
            compression_type: 压缩类型
            
        Returns:
            解压后数据
        """
        if compression_type == "gzip":
            return gzip.decompress(data)
        elif compression_type == "lz4":
            try:
                import lz4.frame
                return lz4.frame.decompress(data)
            except ImportError:
                logger.error("LZ4不可用，无法解压数据")
                raise
        else:
            return data
    
    def _serialize_snapshot(self, snapshot: GraphSnapshot) -> bytes:
        """序列化快照"""
        data = {
            "snapshot_id": snapshot.snapshot_id,
            "timestamp": snapshot.timestamp.isoformat(),
            "granularity": snapshot.granularity,
            "node_count": snapshot.node_count,
            "edge_count": snapshot.edge_count,
            "nodes": snapshot.nodes,
            "edges": snapshot.edges,
            "metadata": snapshot.metadata
        }
        return pickle.dumps(data)
    
    def _deserialize_snapshot(self, data: bytes) -> GraphSnapshot:
        """反序列化快照"""
        dict_data = pickle.loads(data)
        return GraphSnapshot(
            snapshot_id=dict_data["snapshot_id"],
            timestamp=datetime.fromisoformat(dict_data["timestamp"]),
            granularity=dict_data["granularity"],
            node_count=dict_data["node_count"],
            edge_count=dict_data["edge_count"],
            nodes=dict_data.get("nodes", {}),
            edges=dict_data.get("edges", {}),
            metadata=dict_data.get("metadata", {})
        )
    
    # ==================== 快照创建 ====================
    
    def create_snapshot(
        self,
        granularity: str = "day",
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict] = None
    ) -> GraphSnapshot:
        """
        创建快照
        
        Args:
            granularity: 时间粒度 (hour/day/week)
            timestamp: 时间戳（默认为当前时间）
            metadata: 附加元数据
            
        Returns:
            快照对象
        """
        if not self.temporal_builder:
            raise ValueError("需要temporal_builder才能创建快照")
        
        timestamp = timestamp or datetime.now()
        snapshot_id = self._generate_snapshot_id(timestamp, granularity)
        
        # 获取当前图状态
        stats = self.temporal_builder.get_stats()
        
        # 收集节点数据
        nodes_data = {}
        from dairyrisk.graph.nodes import NodeType
        for node_type in NodeType:
            temporal_nodes = self.temporal_builder.get_nodes_by_type(node_type)
            for tn in temporal_nodes:
                nodes_data[tn.node_id] = {
                    "node_id": tn.node_id,
                    "node_type": tn.node_type.value,
                    "first_seen": tn.first_seen.isoformat() if tn.first_seen else None,
                    "last_seen": tn.last_seen.isoformat() if tn.last_seen else None,
                    "features_history_count": len(tn.features_history)
                }
        
        # 收集边数据
        edges_data = {}
        from dairyrisk.graph.edges import EdgeType
        for edge_type in EdgeType:
            temporal_edges = self.temporal_builder.get_edges_by_type(edge_type)
            for te in temporal_edges:
                edge_id = f"{te.edge.src_id}__{edge_type.name}__{te.edge.dst_id}"
                edges_data[edge_id] = {
                    "src_id": te.edge.src_id,
                    "dst_id": te.edge.dst_id,
                    "edge_type": edge_type.value,
                    "first_seen": te.first_seen.isoformat() if te.first_seen else None,
                    "last_seen": te.last_seen.isoformat() if te.last_seen else None,
                    "weight": te.edge.weight
                }
        
        # 创建快照对象
        snapshot = GraphSnapshot(
            snapshot_id=snapshot_id,
            timestamp=timestamp,
            granularity=granularity,
            node_count=stats["total_nodes"],
            edge_count=stats["total_edges"],
            nodes=nodes_data,
            edges=edges_data,
            metadata=metadata or {
                "window_days": stats.get("window_days", 7),
                "node_stats": stats.get("node_stats", {}),
                "edge_stats": stats.get("edge_stats", {})
            }
        )
        
        # 保存快照
        self._save_snapshot(snapshot)
        
        # 更新缓存
        self._add_to_cache(snapshot)
        
        logger.info(f"创建快照: {snapshot_id} ({granularity}, 节点={snapshot.node_count}, 边={snapshot.edge_count})")
        
        return snapshot
    
    def _save_snapshot(self, snapshot: GraphSnapshot):
        """保存快照到数据库"""
        # 序列化
        raw_data = self._serialize_snapshot(snapshot)
        
        # 压缩
        compressed_data, compression_type = self._compress_data(raw_data, self.default_compression)
        
        # 保存到文件（大数据）或数据库
        file_path = None
        if len(compressed_data) > 1_000_000:  # 大于1MB保存到文件
            file_path = str(self.data_dir / f"{snapshot.snapshot_id}.bin")
            with open(file_path, 'wb') as f:
                f.write(compressed_data)
            compressed_data = None  # 不存入数据库
        
        # 保存到数据库
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO snapshots 
                (snapshot_id, timestamp, granularity, node_count, edge_count, 
                 snapshot_data, compression_type, file_path, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot.snapshot_id,
                snapshot.timestamp.isoformat(),
                snapshot.granularity,
                snapshot.node_count,
                snapshot.edge_count,
                compressed_data,
                compression_type,
                file_path,
                json.dumps(snapshot.metadata)
            ))
            conn.commit()
    
    def _load_snapshot_data(self, snapshot_id: str) -> Optional[bytes]:
        """加载快照数据"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT snapshot_data, compression_type, file_path 
                FROM snapshots WHERE snapshot_id = ?
            """, (snapshot_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            data, compression_type, file_path = row
            
            if file_path and Path(file_path).exists():
                with open(file_path, 'rb') as f:
                    data = f.read()
            
            return self._decompress_data(data, compression_type) if data else None
    
    # ==================== 快照查询 ====================
    
    def get_snapshot(self, snapshot_id: str) -> Optional[GraphSnapshot]:
        """
        获取快照
        
        Args:
            snapshot_id: 快照ID
            
        Returns:
            快照对象
        """
        # 检查缓存
        with self._cache_lock:
            if snapshot_id in self._cache:
                return self._cache[snapshot_id]
        
        # 从数据库加载
        data = self._load_snapshot_data(snapshot_id)
        if data:
            snapshot = self._deserialize_snapshot(data)
            self._add_to_cache(snapshot)
            return snapshot
        
        return None
    
    def get_snapshot_at_time(
        self,
        target_time: datetime,
        granularity: str = "day"
    ) -> Optional[GraphSnapshot]:
        """
        获取指定时间点的快照
        
        Args:
            target_time: 目标时间
            granularity: 时间粒度
            
        Returns:
            最接近的快照
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 查找最接近的快照
            cursor.execute("""
                SELECT snapshot_id, timestamp, ABS(strftime('%s', timestamp) - strftime('%s', ?)) as diff
                FROM snapshots
                WHERE granularity = ?
                ORDER BY diff
                LIMIT 1
            """, (target_time.isoformat(), granularity))
            
            row = cursor.fetchone()
            if row:
                return self.get_snapshot(row[0])
        
        return None
    
    def get_snapshot_by_date(
        self,
        date_str: str,
        granularity: str = "day"
    ) -> Optional[GraphSnapshot]:
        """
        通过日期字符串获取快照
        
        Args:
            date_str: 日期字符串 (YYYY-MM-DD 或 YYYY-MM-DD-HH)
            granularity: 时间粒度
            
        Returns:
            快照对象
        """
        try:
            if granularity == "hour":
                target_time = datetime.strptime(date_str, "%Y-%m-%d-%H")
            else:
                target_time = datetime.strptime(date_str, "%Y-%m-%d")
            return self.get_snapshot_at_time(target_time, granularity)
        except ValueError:
            logger.error(f"无效的日期格式: {date_str}")
            return None
    
    def list_snapshots(
        self,
        granularity: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        列出快照
        
        Args:
            granularity: 时间粒度过滤
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制
            
        Returns:
            快照列表
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            query = "SELECT snapshot_id, timestamp, granularity, node_count, edge_count, metadata FROM snapshots WHERE 1=1"
            params = []
            
            if granularity:
                query += " AND granularity = ?"
                params.append(granularity)
            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time.isoformat())
            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time.isoformat())
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            
            snapshots = []
            for row in cursor.fetchall():
                snapshots.append({
                    "snapshot_id": row[0],
                    "timestamp": row[1],
                    "granularity": row[2],
                    "node_count": row[3],
                    "edge_count": row[4],
                    "metadata": json.loads(row[5]) if row[5] else {}
                })
            
            return snapshots
    
    # ==================== 快照对比 ====================
    
    def compare_snapshots(
        self,
        snapshot_id_1: str,
        snapshot_id_2: str
    ) -> Dict[str, Any]:
        """
        对比两个快照
        
        Args:
            snapshot_id_1: 第一个快照ID
            snapshot_id_2: 第二个快照ID
            
        Returns:
            对比结果
        """
        snapshot1 = self.get_snapshot(snapshot_id_1)
        snapshot2 = self.get_snapshot(snapshot_id_2)
        
        if not snapshot1 or not snapshot2:
            return {"error": "无法加载快照"}
        
        # 计算差异
        nodes_1 = set(snapshot1.nodes.keys())
        nodes_2 = set(snapshot2.nodes.keys())
        
        edges_1 = set(snapshot1.edges.keys())
        edges_2 = set(snapshot2.edges.keys())
        
        added_nodes = nodes_2 - nodes_1
        removed_nodes = nodes_1 - nodes_2
        common_nodes = nodes_1 & nodes_2
        
        added_edges = edges_2 - edges_1
        removed_edges = edges_1 - edges_2
        
        return {
            "snapshot_1": snapshot1.to_dict(),
            "snapshot_2": snapshot2.to_dict(),
            "added_nodes": list(added_nodes),
            "removed_nodes": list(removed_nodes),
            "common_nodes": len(common_nodes),
            "added_edges": list(added_edges),
            "removed_edges": list(removed_edges),
            "node_change": len(nodes_2) - len(nodes_1),
            "edge_change": len(edges_2) - len(edges_1)
        }
    
    def get_temporal_changes(
        self,
        start_time: datetime,
        end_time: datetime,
        node_id: Optional[str] = None
    ) -> List[Dict]:
        """
        获取时间段内的变化
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            node_id: 特定节点ID（可选）
            
        Returns:
            变化列表
        """
        # 获取时间范围内的快照
        snapshots = self.list_snapshots(
            start_time=start_time,
            end_time=end_time,
            limit=1000
        )
        
        if len(snapshots) < 2:
            return []
        
        # 按时间排序
        snapshots.sort(key=lambda x: x["timestamp"])
        
        changes = []
        for i in range(1, len(snapshots)):
            diff = self.compare_snapshots(
                snapshots[i-1]["snapshot_id"],
                snapshots[i]["snapshot_id"]
            )
            
            if node_id:
                # 过滤特定节点的变化
                if (node_id in diff.get("added_nodes", []) or
                    node_id in diff.get("removed_nodes", [])):
                    changes.append({
                        "from": snapshots[i-1]["timestamp"],
                        "to": snapshots[i]["timestamp"],
                        "change_type": "node_added" if node_id in diff["added_nodes"] else "node_removed",
                        "node_id": node_id
                    })
            else:
                changes.append({
                    "from": snapshots[i-1]["timestamp"],
                    "to": snapshots[i]["timestamp"],
                    "added_nodes_count": len(diff.get("added_nodes", [])),
                    "removed_nodes_count": len(diff.get("removed_nodes", [])),
                    "added_edges_count": len(diff.get("added_edges", [])),
                    "removed_edges_count": len(diff.get("removed_edges", []))
                })
        
        return changes
    
    # ==================== 缓存管理 ====================
    
    def _add_to_cache(self, snapshot: GraphSnapshot):
        """添加快照到缓存"""
        with self._cache_lock:
            # LRU淘汰
            while len(self._cache) >= self._max_cache_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
            
            self._cache[snapshot.snapshot_id] = snapshot
    
    def clear_cache(self):
        """清空缓存"""
        with self._cache_lock:
            self._cache.clear()
            logger.info("缓存已清空")
    
    # ==================== 清理和压缩 ====================
    
    def cleanup_old_snapshots(self, days: Optional[int] = None) -> int:
        """
        清理旧快照
        
        Args:
            days: 保留天数（默认为auto_cleanup_days）
            
        Returns:
            删除的快照数量
        """
        days = days or self.auto_cleanup_days
        cutoff_time = datetime.now() - timedelta(days=days)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 获取要删除的快照
            cursor.execute("""
                SELECT snapshot_id, file_path FROM snapshots
                WHERE timestamp < ?
            """, (cutoff_time.isoformat(),))
            
            to_delete = cursor.fetchall()
            
            # 删除文件
            for snapshot_id, file_path in to_delete:
                if file_path and Path(file_path).exists():
                    Path(file_path).unlink()
                if snapshot_id in self._cache:
                    del self._cache[snapshot_id]
            
            # 删除数据库记录
            cursor.execute("DELETE FROM snapshots WHERE timestamp < ?", (cutoff_time.isoformat(),))
            deleted_count = cursor.rowcount
            
            conn.commit()
        
        logger.info(f"清理旧快照: 删除{deleted_count}个，保留{days}天")
        return deleted_count
    
    def compress_snapshot(
        self,
        snapshot_id: str,
        target_compression: CompressionType = CompressionType.GZIP
    ) -> bool:
        """
        重新压缩快照
        
        Args:
            snapshot_id: 快照ID
            target_compression: 目标压缩类型
            
        Returns:
            是否成功
        """
        snapshot = self.get_snapshot(snapshot_id)
        if not snapshot:
            return False
        
        self._save_snapshot(snapshot)
        logger.info(f"快照重新压缩: {snapshot_id}")
        return True
    
    # ==================== 统计信息 ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 总快照数
            cursor.execute("SELECT COUNT(*) FROM snapshots")
            total_count = cursor.fetchone()[0]
            
            # 按粒度统计
            cursor.execute("SELECT granularity, COUNT(*) FROM snapshots GROUP BY granularity")
            by_granularity = {row[0]: row[1] for row in cursor.fetchall()}
            
            # 总存储大小
            cursor.execute("SELECT SUM(LENGTH(snapshot_data)) FROM snapshots")
            total_size = cursor.fetchone()[0] or 0
            
            # 文件存储大小
            total_file_size = 0
            cursor.execute("SELECT file_path FROM snapshots WHERE file_path IS NOT NULL")
            for row in cursor.fetchall():
                file_path = row[0]
                if file_path and Path(file_path).exists():
                    total_file_size += Path(file_path).stat().st_size
        
        return {
            "total_snapshots": total_count,
            "by_granularity": by_granularity,
            "db_storage_bytes": total_size,
            "file_storage_bytes": total_file_size,
            "total_storage_bytes": total_size + total_file_size,
            "cache_size": len(self._cache),
            "db_path": self.db_path
        }
    
    def export_snapshot(
        self,
        snapshot_id: str,
        export_path: str,
        format: str = "json"
    ) -> bool:
        """
        导出快照
        
        Args:
            snapshot_id: 快照ID
            export_path: 导出路径
            format: 导出格式 (json/pickle)
            
        Returns:
            是否成功
        """
        snapshot = self.get_snapshot(snapshot_id)
        if not snapshot:
            return False
        
        export_file = Path(export_path)
        export_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            if format == "json":
                with open(export_file, 'w', encoding='utf-8') as f:
                    json.dump(snapshot.to_dict(), f, ensure_ascii=False, indent=2)
            elif format == "pickle":
                with open(export_file, 'wb') as f:
                    pickle.dump(snapshot, f)
            else:
                return False
            
            logger.info(f"导出快照: {snapshot_id} -> {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出快照失败: {e}")
            return False
