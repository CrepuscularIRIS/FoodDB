"""
增量更新引擎 (IncrementalUpdateEngine)

处理新批次数据的接入、节点边的增量添加、特征更新和风险重计算。
支持批量数据导入、数据验证和更新事件触发。
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading
from queue import Queue
import asyncio

from dairyrisk.graph.nodes import (
    NodeType, EnterpriseNode, RawMaterialNode, ProductionLineNode,
    BatchNode, LogisticsNode, RetailNode
)
from dairyrisk.graph.edges import EdgeType, Edge, calculate_risk_transmission_coeff
from dairyrisk.graph.temporal import TemporalGraphBuilder, TemporalNode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UpdateEventType(Enum):
    """更新事件类型"""
    NODE_ADDED = "node_added"
    NODE_UPDATED = "node_updated"
    NODE_REMOVED = "node_removed"
    EDGE_ADDED = "edge_added"
    EDGE_UPDATED = "edge_updated"
    EDGE_REMOVED = "edge_removed"
    BATCH_IMPORTED = "batch_imported"
    RISK_RECALCULATED = "risk_recalculated"


@dataclass
class UpdateEvent:
    """更新事件"""
    event_type: UpdateEventType
    timestamp: datetime
    node_id: Optional[str] = None
    edge_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "node_id": self.node_id,
            "edge_id": self.edge_id,
            "data": self.data
        }


@dataclass
class DataValidationResult:
    """数据验证结果"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    validated_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "validated_count": len(self.validated_data)
        }


@dataclass
class IncrementalUpdateResult:
    """增量更新结果"""
    success: bool
    added_nodes: List[str] = field(default_factory=list)
    updated_nodes: List[str] = field(default_factory=list)
    added_edges: List[str] = field(default_factory=list)
    updated_edges: List[str] = field(default_factory=list)
    risk_recalculated_nodes: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "added_nodes": self.added_nodes,
            "updated_nodes": self.updated_nodes,
            "added_edges": self.added_edges,
            "updated_edges": self.updated_edges,
            "risk_recalculated_nodes": self.risk_recalculated_nodes,
            "errors": self.errors,
            "timestamp": self.timestamp.isoformat(),
            "total_changes": len(self.added_nodes) + len(self.updated_nodes) + 
                           len(self.added_edges) + len(self.updated_edges)
        }


class IncrementalUpdateEngine:
    """
    增量更新引擎
    
    核心功能：
    - 新批次数据接入和验证
    - 增量添加节点和边
    - 更新现有节点特征
    - 触发风险重计算
    - 事件订阅和通知机制
    """
    
    def __init__(
        self,
        temporal_builder: Optional[TemporalGraphBuilder] = None,
        data_dir: Optional[str] = None,
        enable_async_processing: bool = True,
        max_queue_size: int = 1000
    ):
        """
        初始化增量更新引擎
        
        Args:
            temporal_builder: 时序图构建器实例
            data_dir: 数据目录（如果temporal_builder为None）
            enable_async_processing: 是否启用异步处理
            max_queue_size: 更新队列最大大小
        """
        if temporal_builder:
            self.temporal_builder = temporal_builder
        elif data_dir:
            self.temporal_builder = TemporalGraphBuilder(data_dir=data_dir)
        else:
            self.temporal_builder = TemporalGraphBuilder()
        
        self.enable_async_processing = enable_async_processing
        self.max_queue_size = max_queue_size
        
        # 事件订阅者
        self._event_subscribers: Dict[UpdateEventType, List[Callable]] = {
            event_type: [] for event_type in UpdateEventType
        }
        
        # 更新队列
        self._update_queue: Queue = Queue(maxsize=max_queue_size)
        
        # 处理锁
        self._lock = threading.RLock()
        
        # 风险计算回调
        self._risk_calculator: Optional[Callable] = None
        
        # 启动异步处理线程
        if self.enable_async_processing:
            self._processing_thread = threading.Thread(
                target=self._process_queue,
                daemon=True
            )
            self._processing_thread.start()
            logger.info("异步处理线程已启动")
        
        logger.info("IncrementalUpdateEngine 初始化完成")
    
    def set_risk_calculator(self, calculator: Callable):
        """
        设置风险计算器
        
        Args:
            calculator: 风险计算函数，接收node_id返回risk_score
        """
        self._risk_calculator = calculator
        logger.info("风险计算器已设置")
    
    # ==================== 事件订阅机制 ====================
    
    def subscribe(
        self,
        event_type: UpdateEventType,
        callback: Callable[[UpdateEvent], None]
    ):
        """
        订阅更新事件
        
        Args:
            event_type: 事件类型
            callback: 回调函数
        """
        with self._lock:
            if callback not in self._event_subscribers[event_type]:
                self._event_subscribers[event_type].append(callback)
                logger.debug(f"订阅事件: {event_type.value}")
    
    def unsubscribe(
        self,
        event_type: UpdateEventType,
        callback: Callable[[UpdateEvent], None]
    ):
        """取消订阅"""
        with self._lock:
            if callback in self._event_subscribers[event_type]:
                self._event_subscribers[event_type].remove(callback)
                logger.debug(f"取消订阅: {event_type.value}")
    
    def _emit_event(self, event: UpdateEvent):
        """触发事件"""
        callbacks = self._event_subscribers.get(event.event_type, [])
        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"事件回调执行失败: {e}")
        
        # 也触发通配符订阅（所有事件）
        for callback in self._event_subscribers.get(None, []):
            try:
                callback(event)
            except Exception as e:
                logger.error(f"通配符回调执行失败: {e}")
    
    # ==================== 数据验证 ====================
    
    def validate_node_data(
        self,
        node_data: Dict[str, Any],
        node_type: NodeType
    ) -> DataValidationResult:
        """
        验证节点数据
        
        Args:
            node_data: 节点数据
            node_type: 节点类型
            
        Returns:
            验证结果
        """
        errors = []
        warnings = []
        
        # 基本字段验证
        if "node_id" not in node_data:
            errors.append("缺少必需字段: node_id")
        
        # 根据节点类型验证特定字段
        if node_type == NodeType.ENTERPRISE:
            if "name" not in node_data:
                warnings.append("企业节点缺少name字段")
        
        elif node_type == NodeType.BATCH:
            if "batch_id" not in node_data:
                errors.append("批次节点缺少batch_id字段")
            if "enterprise_id" not in node_data:
                warnings.append("批次节点缺少enterprise_id字段")
        
        elif node_type == NodeType.RAW_MATERIAL:
            if "batch_id" not in node_data:
                warnings.append("原料节点缺少batch_id字段")
        
        # 时间戳验证
        if "timestamp" in node_data:
            try:
                datetime.fromisoformat(node_data["timestamp"])
            except ValueError:
                warnings.append("timestamp格式无效，将使用当前时间")
        
        is_valid = len(errors) == 0
        
        return DataValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            validated_data=node_data if is_valid else {}
        )
    
    def validate_edge_data(
        self,
        edge_data: Dict[str, Any],
        edge_type: EdgeType
    ) -> DataValidationResult:
        """
        验证边数据
        
        Args:
            edge_data: 边数据
            edge_type: 边类型
            
        Returns:
            验证结果
        """
        errors = []
        warnings = []
        
        # 必需字段
        if "src_id" not in edge_data:
            errors.append("缺少必需字段: src_id")
        if "dst_id" not in edge_data:
            errors.append("缺少必需字段: dst_id")
        
        # 检查节点是否存在
        if "src_id" in edge_data:
            src_node = self.temporal_builder.get_node(edge_data["src_id"])
            if src_node is None:
                warnings.append(f"源节点不存在: {edge_data['src_id']}")
        
        if "dst_id" in edge_data:
            dst_node = self.temporal_builder.get_node(edge_data["dst_id"])
            if dst_node is None:
                warnings.append(f"目标节点不存在: {edge_data['dst_id']}")
        
        is_valid = len(errors) == 0
        
        return DataValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            validated_data=edge_data if is_valid else {}
        )
    
    # ==================== 节点操作 ====================
    
    def add_or_update_node(
        self,
        node_data: Dict[str, Any],
        node_type: NodeType,
        timestamp: Optional[datetime] = None,
        skip_validation: bool = False
    ) -> Tuple[bool, str, Optional[str]]:
        """
        添加或更新节点
        
        Args:
            node_data: 节点数据
            node_type: 节点类型
            timestamp: 时间戳
            skip_validation: 是否跳过验证
            
        Returns:
            (成功标志, 消息, 节点ID)
        """
        timestamp = timestamp or datetime.now()
        
        # 数据验证
        if not skip_validation:
            validation = self.validate_node_data(node_data, node_type)
            if not validation.is_valid:
                logger.warning(f"节点数据验证失败: {validation.errors}")
                return False, f"验证失败: {validation.errors}", None
        
        node_id = node_data.get("node_id", node_data.get("batch_id", node_data.get("id")))
        if not node_id:
            return False, "无法获取节点ID", None
        
        try:
            # 创建节点对象
            node = self._create_node_object(node_data, node_type)
            
            # 检查节点是否已存在
            existing_node = self.temporal_builder.get_node(node_id)
            is_update = existing_node is not None
            
            # 添加到时序图
            self.temporal_builder.add_node(
                node=node,
                node_type=node_type,
                timestamp=timestamp,
                features=node_data.get("features")
            )
            
            # 触发事件
            event_type = UpdateEventType.NODE_UPDATED if is_update else UpdateEventType.NODE_ADDED
            self._emit_event(UpdateEvent(
                event_type=event_type,
                timestamp=timestamp,
                node_id=node_id,
                data={"node_type": node_type.value, "is_update": is_update}
            ))
            
            action = "更新" if is_update else "添加"
            logger.info(f"{action}节点: {node_id} ({node_type.value})")
            
            return True, f"{action}成功", node_id
            
        except Exception as e:
            logger.error(f"添加节点失败: {e}")
            return False, str(e), None
    
    def _create_node_object(self, node_data: Dict, node_type: NodeType) -> Any:
        """根据数据创建节点对象"""
        if node_type == NodeType.ENTERPRISE:
            from dairyrisk.graph.nodes import EnterpriseScale
            scale = EnterpriseScale(node_data.get("scale", "medium"))
            return EnterpriseNode(
                node_id=node_data.get("node_id", node_data.get("id")),
                name=node_data.get("name", ""),
                scale=scale,
                enterprise_type=node_data.get("enterprise_type", "producer"),
                location=node_data.get("location", ""),
                registration_date=node_data.get("registration_date", ""),
                features=node_data.get("features", {}),
                timestamp=node_data.get("timestamp")
            )
        
        elif node_type == NodeType.BATCH:
            return BatchNode(
                node_id=node_data.get("node_id", node_data.get("batch_id")),
                batch_id=node_data.get("batch_id", ""),
                product_name=node_data.get("product_name", ""),
                product_type=node_data.get("product_type", "milk"),
                enterprise_id=node_data.get("enterprise_id", ""),
                raw_material_ids=node_data.get("raw_material_ids", []),
                production_date=node_data.get("production_date"),
                qc_result=node_data.get("qc_result")
            )
        
        elif node_type == NodeType.RAW_MATERIAL:
            return RawMaterialNode(
                node_id=node_data.get("node_id", node_data.get("batch_id")),
                batch_id=node_data.get("batch_id", ""),
                supplier_id=node_data.get("supplier_id", ""),
                colony_count=node_data.get("colony_count"),
                protein_content=node_data.get("protein_content")
            )
        
        elif node_type == NodeType.LOGISTICS:
            return LogisticsNode(
                node_id=node_data.get("node_id", node_data.get("shipment_id")),
                shipment_id=node_data.get("shipment_id", ""),
                transport_temp=node_data.get("transport_temp"),
                vehicle_type=node_data.get("vehicle_type")
            )
        
        elif node_type == NodeType.RETAIL:
            return RetailNode(
                node_id=node_data.get("node_id", node_data.get("retail_name", "")),
                retail_name=node_data.get("retail_name", ""),
                retail_type=node_data.get("retail_type"),
                shelf_temp=node_data.get("shelf_temp")
            )
        
        elif node_type == NodeType.PRODUCTION_LINE:
            return ProductionLineNode(
                node_id=node_data.get("node_id", ""),
                enterprise_id=node_data.get("enterprise_id", ""),
                line_name=node_data.get("line_name", ""),
                cleanliness_level=node_data.get("cleanliness_level")
            )
        
        else:
            # 通用节点
            class GenericNode:
                def __init__(self, node_id):
                    self.node_id = node_id
            return GenericNode(node_data.get("node_id", ""))
    
    # ==================== 边操作 ====================
    
    def add_or_update_edge(
        self,
        src_id: str,
        dst_id: str,
        edge_type: EdgeType,
        edge_data: Optional[Dict] = None,
        timestamp: Optional[datetime] = None,
        weight: float = 1.0,
        skip_validation: bool = False
    ) -> Tuple[bool, str, Optional[str]]:
        """
        添加或更新边
        
        Args:
            src_id: 源节点ID
            dst_id: 目标节点ID
            edge_type: 边类型
            edge_data: 边数据
            timestamp: 时间戳
            weight: 边权重
            skip_validation: 是否跳过验证
            
        Returns:
            (成功标志, 消息, 边ID)
        """
        timestamp = timestamp or datetime.now()
        edge_data = edge_data or {}
        
        # 数据验证
        if not skip_validation:
            validation_data = {"src_id": src_id, "dst_id": dst_id, **edge_data}
            validation = self.validate_edge_data(validation_data, edge_type)
            if not validation.is_valid:
                logger.warning(f"边数据验证失败: {validation.errors}")
                return False, f"验证失败: {validation.errors}", None
        
        try:
            # 计算风险传导系数
            risk_coeff = calculate_risk_transmission_coeff(edge_type, edge_data)
            
            # 创建边对象
            edge = Edge(
                src_id=src_id,
                dst_id=dst_id,
                edge_type=edge_type,
                features=edge_data.get("features"),
                weight=weight,
                timestamp=timestamp.isoformat(),
                risk_transmission_coeff=risk_coeff
            )
            
            # 添加到时序图
            edge_id = self.temporal_builder.add_edge(
                edge=edge,
                timestamp=timestamp,
                weight=weight
            )
            
            # 触发事件
            self._emit_event(UpdateEvent(
                event_type=UpdateEventType.EDGE_ADDED,
                timestamp=timestamp,
                edge_id=edge_id,
                data={"src_id": src_id, "dst_id": dst_id, "edge_type": edge_type.value}
            ))
            
            logger.info(f"添加边: {src_id} -> {dst_id} ({edge_type.value})")
            
            return True, "添加成功", edge_id
            
        except Exception as e:
            logger.error(f"添加边失败: {e}")
            return False, str(e), None
    
    # ==================== 批量导入 ====================
    
    def import_batch_data(
        self,
        batch_data: Dict[str, List[Dict]],
        timestamp: Optional[datetime] = None
    ) -> IncrementalUpdateResult:
        """
        批量导入数据
        
        Args:
            batch_data: 批量数据，格式为 {node_type: [node_data_list], edges: [edge_data_list]}
            timestamp: 时间戳
            
        Returns:
            更新结果
        """
        timestamp = timestamp or datetime.now()
        result = IncrementalUpdateResult(success=True, timestamp=timestamp)
        
        logger.info(f"开始批量导入数据...")
        
        # 导入节点
        node_type_map = {
            "enterprises": NodeType.ENTERPRISE,
            "raw_materials": NodeType.RAW_MATERIAL,
            "production_lines": NodeType.PRODUCTION_LINE,
            "batches": NodeType.BATCH,
            "logistics": NodeType.LOGISTICS,
            "retail": NodeType.RETAIL
        }
        
        for data_key, node_type in node_type_map.items():
            if data_key in batch_data:
                for node_data in batch_data[data_key]:
                    success, msg, node_id = self.add_or_update_node(
                        node_data=node_data,
                        node_type=node_type,
                        timestamp=timestamp
                    )
                    if success:
                        if "更新" in msg:
                            result.updated_nodes.append(node_id)
                        else:
                            result.added_nodes.append(node_id)
                    else:
                        result.errors.append(f"节点 {node_id}: {msg}")
        
        # 导入边
        if "edges" in batch_data:
            for edge_data in batch_data["edges"]:
                src_id = edge_data.get("src_id")
                dst_id = edge_data.get("dst_id")
                edge_type_str = edge_data.get("edge_type", "SUPPLIES")
                
                try:
                    edge_type = EdgeType[edge_type_str.upper()]
                except KeyError:
                    result.errors.append(f"未知的边类型: {edge_type_str}")
                    continue
                
                success, msg, edge_id = self.add_or_update_edge(
                    src_id=src_id,
                    dst_id=dst_id,
                    edge_type=edge_type,
                    edge_data=edge_data,
                    timestamp=timestamp,
                    weight=edge_data.get("weight", 1.0)
                )
                
                if success:
                    result.added_edges.append(edge_id)
                else:
                    result.errors.append(f"边 {src_id}->{dst_id}: {msg}")
        
        # 触发批量导入事件
        self._emit_event(UpdateEvent(
            event_type=UpdateEventType.BATCH_IMPORTED,
            timestamp=timestamp,
            data=result.to_dict()
        ))
        
        # 触发风险重计算
        affected_nodes = result.added_nodes + result.updated_nodes
        if affected_nodes:
            self.trigger_risk_recalculation(affected_nodes)
        
        logger.info(f"批量导入完成: 节点+{len(result.added_nodes)}, 更新{len(result.updated_nodes)}, 边+{len(result.added_edges)}")
        
        return result
    
    # ==================== 风险重计算 ====================
    
    def trigger_risk_recalculation(
        self,
        node_ids: List[str],
        propagate: bool = True
    ) -> List[str]:
        """
        触发风险重计算
        
        Args:
            node_ids: 需要重计算的节点ID列表
            propagate: 是否传播到邻居节点
            
        Returns:
            实际重计算的节点列表
        """
        recalculated = []
        
        for node_id in node_ids:
            try:
                # 调用风险计算器
                if self._risk_calculator:
                    risk_score = self._risk_calculator(node_id)
                    logger.debug(f"节点 {node_id} 风险分数: {risk_score}")
                
                recalculated.append(node_id)
                
                # 触发事件
                self._emit_event(UpdateEvent(
                    event_type=UpdateEventType.RISK_RECALCULATED,
                    timestamp=datetime.now(),
                    node_id=node_id,
                    data={"propagate": propagate}
                ))
                
            except Exception as e:
                logger.error(f"风险重计算失败 {node_id}: {e}")
        
        # 传播到邻居
        if propagate:
            neighbor_ids = set()
            for node_id in node_ids:
                neighbors = self.temporal_builder.get_neighbors(node_id, "all")
                neighbor_ids.update(neighbors)
            
            # 排除已计算的节点
            neighbor_ids = neighbor_ids - set(node_ids)
            
            if neighbor_ids:
                logger.info(f"风险传播到 {len(neighbor_ids)} 个邻居节点")
                # 递归调用，但不继续传播
                recalculated.extend(
                    self.trigger_risk_recalculation(list(neighbor_ids), propagate=False)
                )
        
        logger.info(f"风险重计算完成: {len(recalculated)} 个节点")
        return recalculated
    
    # ==================== 异步处理 ====================
    
    def _process_queue(self):
        """处理更新队列（后台线程）"""
        while True:
            try:
                task = self._update_queue.get(timeout=1)
                if task is None:
                    break
                
                task_type = task.get("type")
                
                if task_type == "import_batch":
                    self.import_batch_data(
                        task.get("data"),
                        task.get("timestamp")
                    )
                elif task_type == "add_node":
                    self.add_or_update_node(
                        task.get("node_data"),
                        task.get("node_type"),
                        task.get("timestamp")
                    )
                elif task_type == "add_edge":
                    self.add_or_update_edge(
                        task.get("src_id"),
                        task.get("dst_id"),
                        task.get("edge_type"),
                        task.get("edge_data"),
                        task.get("timestamp"),
                        task.get("weight", 1.0)
                    )
                
            except Exception as e:
                if "timeout" not in str(e).lower():
                    logger.error(f"队列处理错误: {e}")
    
    def queue_batch_import(
        self,
        batch_data: Dict[str, List[Dict]],
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        将批量导入任务加入队列
        
        Args:
            batch_data: 批量数据
            timestamp: 时间戳
            
        Returns:
            是否成功加入队列
        """
        try:
            self._update_queue.put({
                "type": "import_batch",
                "data": batch_data,
                "timestamp": timestamp or datetime.now()
            }, block=False)
            return True
        except:
            return False
    
    # ==================== 统计信息 ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """获取引擎统计信息"""
        return {
            "temporal_builder_stats": self.temporal_builder.get_stats(),
            "queue_size": self._update_queue.qsize(),
            "async_enabled": self.enable_async_processing,
            "event_subscribers": {
                event_type.value: len(callbacks)
                for event_type, callbacks in self._event_subscribers.items()
            }
        }
