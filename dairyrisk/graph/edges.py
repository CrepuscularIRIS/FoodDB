"""
边类型定义模块

定义乳制品供应链异构图中的10种边类型：
1. enterprise --purchases--> raw_material
2. enterprise --owns--> production_line
3. production_line --produces--> batch
4. raw_material --used_in--> batch
5. enterprise --manufactures--> batch
6. batch --transported_by--> logistics
7. logistics --delivers_to--> retail
8. batch --sold_at--> retail
9. enterprise --supplies--> enterprise
10. batch --temporal_next--> batch
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum
import torch
from torch import Tensor


class EdgeType(Enum):
    """边类型枚举 - 定义供应链中的关系"""
    
    # 企业间关系
    SUPPLIES = ("enterprise", "supplies", "enterprise")           # 供应关系
    COMPETES = ("enterprise", "competes", "enterprise")           # 竞争关系
    COOPERATES = ("enterprise", "cooperates", "enterprise")       # 合作关系
    
    # 企业与原料关系
    PURCHASES = ("enterprise", "purchases", "raw_material")       # 采购原料
    
    # 企业与生产线关系
    OWNS = ("enterprise", "owns", "production_line")              # 拥有生产线
    
    # 生产线与批次关系
    PRODUCES = ("production_line", "produces", "batch")           # 生产批次
    
    # 原料与批次关系
    USED_IN = ("raw_material", "used_in", "batch")                # 原料用于批次
    
    # 企业与批次关系
    MANUFACTURES = ("enterprise", "manufactures", "batch")        # 制造批次
    
    # 批次与物流关系
    TRANSPORTED_BY = ("batch", "transported_by", "logistics")     # 批次由物流运输
    
    # 物流与零售关系
    DELIVERS_TO = ("logistics", "delivers_to", "retail")          # 物流配送至零售
    
    # 批次与零售关系
    SOLD_AT = ("batch", "sold_at", "retail")                      # 批次销售于零售点
    
    # 时序关系（同一节点不同时间）
    TEMPORAL_NEXT = ("batch", "temporal_next", "batch")           # 时间上的下一个批次
    
    def __init__(self, src: str, rel: str, dst: str):
        self.src = src
        self.rel = rel
        self.dst = dst
    
    @property
    def canonical_name(self) -> str:
        """获取规范名称 (用于PyG HeteroData)"""
        return f"{self.src}__{self.rel}__{self.dst}"
    
    @property
    def tuple_name(self) -> tuple:
        """获取元组名称 (用于PyG)"""
        return (self.src, self.rel, self.dst)


@dataclass
class Edge:
    """边数据类"""
    src_id: str                         # 源节点ID
    dst_id: str                         # 目标节点ID
    edge_type: EdgeType                 # 边类型
    
    # 边特征
    features: Optional[Dict[str, Any]] = None
    
    # 边权重（用于风险传导）
    weight: float = 1.0
    
    # 时间戳
    timestamp: Optional[str] = None
    
    # 风险传导系数（用于风险传播建模）
    risk_transmission_coeff: Optional[float] = None
    
    def get_feature_vector(self) -> Tensor:
        """获取边特征向量"""
        if self.features is None:
            return torch.tensor([self.weight], dtype=torch.float32)
        
        feat_list = []
        for key in sorted(self.features.keys()):
            val = self.features[key]
            if val is not None:
                feat_list.append(float(val))
            else:
                feat_list.append(0.0)
        
        # 添加权重
        feat_list.append(self.weight)
        
        return torch.tensor(feat_list, dtype=torch.float32)


# 边类型到特征维度的映射
EDGE_FEATURE_DIMS = {
    EdgeType.SUPPLIES: 4,         # 供应量、供应频率、合作时长、信任度
    EdgeType.PURCHASES: 4,        # 采购量、采购频率、价格、质量评分
    EdgeType.OWNS: 1,             # 所有权比例
    EdgeType.PRODUCES: 2,         # 产量、生产效率
    EdgeType.USED_IN: 2,          # 使用量、配比
    EdgeType.MANUFACTURES: 1,     # 制造日期编码
    EdgeType.TRANSPORTED_BY: 4,   # 运输量、运输时长、距离、温度控制
    EdgeType.DELIVERS_TO: 2,      # 配送量、配送频率
    EdgeType.SOLD_AT: 3,          # 销售量、销售速度、库存周转
    EdgeType.TEMPORAL_NEXT: 1,    # 时间间隔
    EdgeType.COMPETES: 1,         # 竞争强度
    EdgeType.COOPERATES: 2,       # 合作深度、合作时长
}


# 风险传导系数配置（用于边级风险预测）
RISK_TRANSMISSION_CONFIG = {
    # 供应关系风险传导
    EdgeType.SUPPLIES: {
        "base_coeff": 0.7,        # 基础传导系数
        "factors": ["supply_volume", "supply_frequency", "cooperation_duration"]
    },
    # 原料到批次的风险传导
    EdgeType.USED_IN: {
        "base_coeff": 0.8,
        "factors": ["usage_ratio", "raw_quality"]
    },
    # 生产线到批次的风险传导
    EdgeType.PRODUCES: {
        "base_coeff": 0.75,
        "factors": ["production_volume", "efficiency"]
    },
    # 物流风险传导
    EdgeType.TRANSPORTED_BY: {
        "base_coeff": 0.6,
        "factors": ["transport_duration", "temp_control", "distance"]
    },
    # 企业间采购风险传导
    EdgeType.PURCHASES: {
        "base_coeff": 0.65,
        "factors": ["purchase_volume", "quality_score"]
    },
    # 时序风险传导（历史批次影响）
    EdgeType.TEMPORAL_NEXT: {
        "base_coeff": 0.5,
        "factors": ["time_interval"]
    },
}


def calculate_risk_transmission_coeff(edge_type: EdgeType, edge_features: Dict[str, Any]) -> float:
    """
    计算风险传导系数
    
    Args:
        edge_type: 边类型
        edge_features: 边特征
        
    Returns:
        风险传导系数 0-1
    """
    config = RISK_TRANSMISSION_CONFIG.get(edge_type)
    if config is None:
        return 0.5  # 默认传导系数
    
    base_coeff = config["base_coeff"]
    factors = config["factors"]
    
    # 根据特征调整传导系数
    adjustment = 0.0
    for factor in factors:
        if factor in edge_features and edge_features[factor] is not None:
            val = float(edge_features[factor])
            # 归一化到-0.1到0.1的调整范围
            adjustment += (val - 0.5) * 0.2 / len(factors)
    
    # 确保在合理范围内
    return max(0.1, min(1.0, base_coeff + adjustment))


# 任务所需10种边的规范名称
REQUIRED_EDGES = [
    ("enterprise", "purchases", "raw_material"),
    ("enterprise", "owns", "production_line"),
    ("production_line", "produces", "batch"),
    ("raw_material", "used_in", "batch"),
    ("enterprise", "manufactures", "batch"),
    ("batch", "transported_by", "logistics"),
    ("logistics", "delivers_to", "retail"),
    ("batch", "sold_at", "retail"),
    ("enterprise", "supplies", "enterprise"),
    ("batch", "temporal_next", "batch"),
]


# 导出所有边类型
__all__ = [
    'EdgeType',
    'Edge',
    'EDGE_FEATURE_DIMS',
    'RISK_TRANSMISSION_CONFIG',
    'calculate_risk_transmission_coeff',
    'REQUIRED_EDGES'
]
