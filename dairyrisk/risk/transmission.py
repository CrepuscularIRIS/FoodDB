"""
风险传导模型 (Risk Transmission Model)

实现边级风险传导系数计算和静态风险传播分析。
基于方案文档5.7章节和中期工作建议。
"""

from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import numpy as np
from collections import defaultdict

from dairyrisk.graph.edges import EdgeType, Edge, RISK_TRANSMISSION_CONFIG, calculate_risk_transmission_coeff
from dairyrisk.graph.nodes import NodeType, BatchNode


# 简化版风险传导配置（用于快速计算）
RISK_TRANSMISSION_COEFFICIENTS = {
    EdgeType.SUPPLIES: 0.7,           # 供应关系
    EdgeType.USED_IN: 0.8,             # 原料到批次
    EdgeType.PRODUCES: 0.75,           # 生产线到批次
    EdgeType.TRANSPORTED_BY: 0.6,      # 物流风险
    EdgeType.TEMPORAL_NEXT: 0.5,       # 时序传导
    EdgeType.PURCHASES: 0.65,          # 采购风险
    EdgeType.OWNS: 0.5,                # 所有权关系
    EdgeType.MANUFACTURES: 0.7,        # 制造关系
    EdgeType.DELIVERS_TO: 0.55,        # 配送关系
    EdgeType.SOLD_AT: 0.45,            # 销售关系
    EdgeType.COMPETES: 0.3,            # 竞争关系（间接传导）
    EdgeType.COOPERATES: 0.4,          # 合作关系
}


@dataclass
class RiskTransmissionResult:
    """风险传导结果"""
    source_node_id: str                    # 源节点ID
    source_risk_level: float               # 源节点风险等级 (0-1)
    target_node_id: str                    # 目标节点ID
    edge_type: EdgeType                    # 边类型
    transmission_coeff: float              # 传导系数
    propagated_risk: float                 # 传导后的风险值
    path_length: int = 1                   # 传播路径长度
    propagation_path: List[str] = None     # 传播路径
    
    def __post_init__(self):
        if self.propagation_path is None:
            self.propagation_path = [self.source_node_id, self.target_node_id]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_node_id": self.source_node_id,
            "source_risk_level": self.source_risk_level,
            "target_node_id": self.target_node_id,
            "edge_type": self.edge_type.name if isinstance(self.edge_type, EdgeType) else str(self.edge_type),
            "transmission_coeff": round(self.transmission_coeff, 4),
            "propagated_risk": round(self.propagated_risk, 4),
            "path_length": self.path_length,
            "propagation_path": self.propagation_path
        }


@dataclass
class NodeRiskState:
    """节点风险状态"""
    node_id: str
    node_type: NodeType
    initial_risk: float                    # 初始风险值
    accumulated_risk: float                # 累积风险值
    incoming_transmissions: List[RiskTransmissionResult] = None
    
    def __post_init__(self):
        if self.incoming_transmissions is None:
            self.incoming_transmissions = []
    
    @property
    def final_risk(self) -> float:
        """计算最终风险（初始 + 传导）"""
        return min(1.0, self.initial_risk + self.accumulated_risk)


class RiskTransmissionModel:
    """
    风险传导模型
    
    负责计算风险在供应链图中的传导过程。
    支持静态传导计算和动态传播模拟。
    """
    
    def __init__(
        self,
        transmission_config: Optional[Dict[EdgeType, float]] = None,
        risk_decay_factor: float = 0.9
    ):
        """
        初始化风险传导模型
        
        Args:
            transmission_config: 自定义传导系数配置
            risk_decay_factor: 风险随距离的衰减因子
        """
        self.transmission_coeffs = transmission_config or RISK_TRANSMISSION_COEFFICIENTS
        self.risk_decay_factor = risk_decay_factor
        
        # 传播图缓存
        self._transmission_graph: Dict[str, List[Tuple[str, EdgeType, float]]] = {}
    
    def get_transmission_coefficient(
        self,
        edge_type: EdgeType,
        edge_features: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        获取风险传导系数
        
        Args:
            edge_type: 边类型
            edge_features: 边特征（用于动态调整系数）
            
        Returns:
            传导系数 0-1
        """
        base_coeff = self.transmission_coeffs.get(edge_type, 0.5)
        
        if edge_features:
            # 使用详细计算函数
            detailed_coeff = calculate_risk_transmission_coeff(edge_type, edge_features)
            # 混合基础系数和详细系数
            return 0.6 * base_coeff + 0.4 * detailed_coeff
        
        return base_coeff
    
    def calculate_propagated_risk(
        self,
        source_risk: float,
        edge_type: EdgeType,
        edge_features: Optional[Dict[str, Any]] = None,
        distance: int = 1
    ) -> float:
        """
        计算传导后的风险值
        
        Args:
            source_risk: 源节点风险值
            edge_type: 边类型
            edge_features: 边特征
            distance: 传播距离（用于衰减计算）
            
        Returns:
            传导后的风险值
        """
        coeff = self.get_transmission_coefficient(edge_type, edge_features)
        decay = self.risk_decay_factor ** (distance - 1)
        propagated = source_risk * coeff * decay
        return min(1.0, propagated)
    
    def build_transmission_graph(
        self,
        edges: List[Edge],
        edge_features_map: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Dict[str, List[Tuple[str, EdgeType, float]]]:
        """
        构建风险传导图
        
        Args:
            edges: 边列表
            edge_features_map: 边特征映射 {edge_id: features}
            
        Returns:
            传导图 {source_id: [(target_id, edge_type, coeff), ...]}
        """
        graph = defaultdict(list)
        
        for edge in edges:
            features = None
            if edge_features_map and edge.src_id in edge_features_map:
                features = edge_features_map[edge.src_id].get(edge.dst_id)
            
            coeff = self.get_transmission_coefficient(edge.edge_type, features)
            graph[edge.src_id].append((edge.dst_id, edge.edge_type, coeff))
        
        self._transmission_graph = dict(graph)
        return self._transmission_graph
    
    def calculate_single_step_transmission(
        self,
        source_node_id: str,
        source_risk: float,
        outgoing_edges: List[Edge],
        edge_features_map: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> List[RiskTransmissionResult]:
        """
        计算单步风险传导
        
        Args:
            source_node_id: 源节点ID
            source_risk: 源节点风险值
            outgoing_edges: 出边列表
            edge_features_map: 边特征映射
            
        Returns:
            风险传导结果列表
        """
        results = []
        
        for edge in outgoing_edges:
            features = None
            if edge_features_map:
                features = edge_features_map.get(f"{edge.src_id}_{edge.dst_id}")
            
            coeff = self.get_transmission_coefficient(edge.edge_type, features)
            propagated_risk = self.calculate_propagated_risk(
                source_risk, edge.edge_type, features, distance=1
            )
            
            result = RiskTransmissionResult(
                source_node_id=source_node_id,
                source_risk_level=source_risk,
                target_node_id=edge.dst_id,
                edge_type=edge.edge_type,
                transmission_coeff=coeff,
                propagated_risk=propagated_risk,
                path_length=1
            )
            results.append(result)
        
        return results
    
    def trace_upstream(
        self,
        target_node_id: str,
        graph_edges: Dict[str, List[Tuple[str, EdgeType, float]]],
        max_depth: int = 5,
        min_coeff: float = 0.1
    ) -> List[List[Tuple[str, EdgeType, float]]]:
        """
        向上游追溯风险来源
        
        Args:
            target_node_id: 目标节点ID
            graph_edges: 图边结构 {dst_id: [(src_id, edge_type, coeff), ...]}
            max_depth: 最大追溯深度
            min_coeff: 最小传导系数阈值
            
        Returns:
            风险来源路径列表
        """
        # 构建反向图
        reverse_graph = defaultdict(list)
        for src, targets in graph_edges.items():
            for dst, edge_type, coeff in targets:
                if coeff >= min_coeff:
                    reverse_graph[dst].append((src, edge_type, coeff))
        
        paths = []
        visited = set()
        
        def dfs(current_id: str, current_path: List[Tuple[str, EdgeType, float]], depth: int):
            if depth > max_depth:
                return
            
            if current_id in visited:
                return
            visited.add(current_id)
            
            sources = reverse_graph.get(current_id, [])
            if not sources and len(current_path) > 0:
                # 到达源头
                paths.append(current_path.copy())
                return
            
            for src_id, edge_type, coeff in sources:
                current_path.append((src_id, edge_type, coeff))
                dfs(src_id, current_path, depth + 1)
                current_path.pop()
            
            visited.remove(current_id)
        
        dfs(target_node_id, [], 0)
        return paths
    
    def trace_downstream(
        self,
        source_node_id: str,
        graph_edges: Dict[str, List[Tuple[str, EdgeType, float]]],
        max_depth: int = 5,
        min_coeff: float = 0.1
    ) -> List[List[Tuple[str, EdgeType, float]]]:
        """
        向下游追踪风险影响
        
        Args:
            source_node_id: 源节点ID
            graph_edges: 图边结构
            max_depth: 最大追踪深度
            min_coeff: 最小传导系数阈值
            
        Returns:
            风险影响路径列表
        """
        paths = []
        visited = set()
        
        def dfs(current_id: str, current_path: List[Tuple[str, EdgeType, float]], depth: int):
            if depth > max_depth:
                return
            
            if current_id in visited:
                return
            visited.add(current_id)
            
            targets = graph_edges.get(current_id, [])
            if not targets and len(current_path) > 0:
                paths.append(current_path.copy())
                return
            
            for dst_id, edge_type, coeff in targets:
                if coeff >= min_coeff:
                    current_path.append((dst_id, edge_type, coeff))
                    dfs(dst_id, current_path, depth + 1)
                    current_path.pop()
            
            visited.remove(current_id)
        
        dfs(source_node_id, [], 0)
        return paths
    
    def calculate_risk_impact_score(
        self,
        node_id: str,
        node_risk: float,
        graph_edges: Dict[str, List[Tuple[str, EdgeType, float]]],
        max_depth: int = 3
    ) -> Dict[str, Any]:
        """
        计算节点的风险影响评分
        
        Args:
            node_id: 节点ID
            node_risk: 节点风险值
            graph_edges: 图边结构
            max_depth: 最大影响深度
            
        Returns:
            影响评估结果
        """
        downstream_paths = self.trace_downstream(node_id, graph_edges, max_depth)
        
        affected_nodes = set()
        total_impact = 0.0
        path_impacts = []
        
        for path in downstream_paths:
            if not path:
                continue
            
            path_coeff_product = 1.0
            path_nodes = [node_id]
            
            for dst_id, edge_type, coeff in path:
                path_nodes.append(dst_id)
                affected_nodes.add(dst_id)
                path_coeff_product *= coeff
            
            path_impact = node_risk * path_coeff_product
            total_impact += path_impact
            
            path_impacts.append({
                "path": path_nodes,
                "coefficient_product": round(path_coeff_product, 4),
                "impact_score": round(path_impact, 4)
            })
        
        return {
            "source_node_id": node_id,
            "source_risk": round(node_risk, 4),
            "affected_node_count": len(affected_nodes),
            "total_impact_score": round(total_impact, 4),
            "path_count": len(downstream_paths),
            "average_impact": round(total_impact / len(affected_nodes), 4) if affected_nodes else 0,
            "path_details": path_impacts[:10]  # 只返回前10条路径
        }


def create_transmission_model(
    custom_coeffs: Optional[Dict[EdgeType, float]] = None
) -> RiskTransmissionModel:
    """
    创建风险传导模型实例
    
    Args:
        custom_coeffs: 自定义传导系数
        
    Returns:
        RiskTransmissionModel实例
    """
    return RiskTransmissionModel(transmission_config=custom_coeffs)


# 导出
__all__ = [
    'RISK_TRANSMISSION_COEFFICIENTS',
    'RiskTransmissionResult',
    'NodeRiskState',
    'RiskTransmissionModel',
    'create_transmission_model'
]
