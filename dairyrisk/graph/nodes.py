"""
节点类型定义模块

定义乳制品供应链异构图中的6种节点类型：
- EnterpriseNode (企业): 大/中/小三种规模，不同数据完整性
- RawMaterialNode (原料): 菌落数、体细胞数、抗生素残留等
- ProductionLineNode (生产线): 洁净度等级、杀菌温度等
- BatchNode (批次): 核心节点，包含质检结果作为标签
- LogisticsNode (物流): 运输温度、冷链监控等
- RetailNode (零售): 货架温度、库存天数、投诉数等
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import torch
from torch import Tensor


class NodeType(Enum):
    """节点类型枚举"""
    ENTERPRISE = "enterprise"           # 企业节点
    RAW_MATERIAL = "raw_material"       # 原料节点
    PRODUCTION_LINE = "production_line" # 生产线节点
    BATCH = "batch"                     # 批次节点
    LOGISTICS = "logistics"             # 物流节点
    RETAIL = "retail"                   # 零售节点


class EnterpriseScale(Enum):
    """企业规模枚举"""
    LARGE = "large"      # 大型企业
    MEDIUM = "medium"    # 中型企业
    SMALL = "small"      # 小微企业


@dataclass
class EnterpriseNode:
    """
    企业节点
    
    数据完整性策略:
    - 大企业: 95%完整度
    - 中企业: 80%完整度
    - 小企业: 50%完整度 (重点监管对象)
    """
    node_id: str                        # 节点唯一ID
    name: str                           # 企业名称
    scale: EnterpriseScale              # 企业规模
    enterprise_type: str                # 企业类型 (producer/processor/distributor/retailer)
    location: str                       # 地理位置（上海市XX区）
    registration_date: str              # 注册日期
    license_number: Optional[str] = None  # 许可证号
    
    # 数据完整性评分 (0-1)
    data_completeness: Dict[str, float] = field(default_factory=dict)
    
    # 节点特征（根据规模动态生成）
    features: Dict[str, Any] = field(default_factory=dict)
    
    # 时间戳
    timestamp: Optional[str] = None
    
    def get_feature_vector(self, feature_schema: Optional[List[str]] = None) -> Tensor:
        """
        获取特征向量（处理缺失值）
        
        Args:
            feature_schema: 特征schema列表，如果为None则使用默认schema
            
        Returns:
            特征向量Tensor
        """
        if feature_schema is None:
            # 默认特征schema
            feature_schema = [
                "employee_count", "annual_output",
                "raw_storage_temp", "raw_storage_duration",
                "cleanliness_level_encoded", "pasteurization_temp",
                "pasteurization_duration", "pasteurization_temp_std",
                "env_temp", "env_humidity", "air_quality_index",
                "equipment_clean_freq", "transport_temp",
                "transport_duration", "vehicle_type_encoded",
                "inventory_days", "consumer_complaints",
                "return_count", "turnover_rate", "scale_encoded"
            ]
        
        feature_vector = []
        for feat_name in feature_schema:
            if feat_name in self.features and self.features[feat_name] is not None:
                feature_vector.append(float(self.features[feat_name]))
            else:
                # 根据企业规模使用不同的填充策略
                feature_vector.append(self._get_default_value(feat_name))
        
        return torch.tensor(feature_vector, dtype=torch.float32)
    
    def _get_default_value(self, feat_name: str) -> float:
        """根据特征名称获取默认值"""
        # 温度类特征：使用行业平均值
        if "temp" in feat_name:
            return 4.0  # 冷藏温度平均值
        # 时长类特征：使用行业中位数
        elif "duration" in feat_name or "days" in feat_name:
            return 24.0
        # 计数类特征：使用0
        elif "count" in feat_name or "complaints" in feat_name:
            return 0.0
        # 比例类特征：使用0.5
        elif "rate" in feat_name or "index" in feat_name:
            return 0.5
        # 等级编码：使用中等值
        elif "level" in feat_name:
            return 0.5
        # 企业规模：根据规模编码
        elif "scale" in feat_name:
            scale_map = {EnterpriseScale.LARGE: 1.0, EnterpriseScale.MEDIUM: 0.6, EnterpriseScale.SMALL: 0.3}
            return scale_map.get(self.scale, 0.5)
        # 其他：使用0
        else:
            return 0.0


@dataclass
class RawMaterialNode:
    """
    原料节点
    
    特征字段:
    - colony_count: 菌落总数 (CFU/mL)
    - somatic_cell_count: 体细胞数 (个/mL)
    - antibiotic_residue: 抗生素残留 (μg/kg)
    - protein_content: 蛋白质含量 (%)
    - fat_content: 脂肪含量 (%)
    - storage_temp: 储存温度 (°C)
    - storage_duration: 储存时长 (小时)
    """
    node_id: str
    batch_id: str                       # 原料批次号
    supplier_id: str                    # 供应商ID
    supplier_name: Optional[str] = None
    
    # 原料特征
    colony_count: Optional[float] = None        # 菌落总数
    somatic_cell_count: Optional[float] = None  # 体细胞数
    antibiotic_residue: Optional[float] = None  # 抗生素残留
    protein_content: Optional[float] = None     # 蛋白质含量
    fat_content: Optional[float] = None         # 脂肪含量
    
    # 储存信息
    storage_temp: Optional[float] = None
    storage_duration: Optional[float] = None
    
    # 采集时间
    collection_date: Optional[str] = None
    
    def get_feature_vector(self) -> Tensor:
        """获取原料特征向量"""
        features = [
            self.colony_count if self.colony_count is not None else 50000.0,
            self.somatic_cell_count if self.somatic_cell_count is not None else 200000.0,
            self.antibiotic_residue if self.antibiotic_residue is not None else 0.0,
            self.protein_content if self.protein_content is not None else 3.0,
            self.fat_content if self.fat_content is not None else 3.5,
            self.storage_temp if self.storage_temp is not None else 4.0,
            self.storage_duration if self.storage_duration is not None else 12.0,
        ]
        return torch.tensor(features, dtype=torch.float32)


@dataclass
class ProductionLineNode:
    """
    生产线节点
    
    特征字段:
    - cleanliness_level: 洁净度等级 (A/B/C/D)
    - pasteurization_temp: 杀菌温度 (°C)
    - pasteurization_duration: 杀菌时长 (秒)
    - pasteurization_temp_std: 温度波动标准差
    - env_temp: 环境温度 (°C)
    - env_humidity: 环境湿度 (%)
    - air_quality_index: 空气质量指数
    - equipment_clean_freq: 设备清洗频率 (次/天)
    """
    node_id: str
    enterprise_id: str                  # 所属企业ID
    line_name: str                      # 生产线名称
    
    # 生产环境特征
    cleanliness_level: Optional[str] = None     # 洁净度等级
    pasteurization_temp: Optional[float] = None # 杀菌温度
    pasteurization_duration: Optional[float] = None  # 杀菌时长
    pasteurization_temp_std: Optional[float] = None  # 温度波动
    
    # 环境监控
    env_temp: Optional[float] = None
    env_humidity: Optional[float] = None
    air_quality_index: Optional[float] = None
    
    # 设备管理
    equipment_clean_freq: Optional[int] = None
    last_maintenance_date: Optional[str] = None
    
    def get_feature_vector(self) -> Tensor:
        """获取生产线特征向量"""
        # 洁净度等级编码
        cleanliness_map = {"A": 1.0, "B": 0.75, "C": 0.5, "D": 0.25, None: 0.5}
        cleanliness_encoded = cleanliness_map.get(self.cleanliness_level, 0.5)
        
        features = [
            cleanliness_encoded,
            self.pasteurization_temp if self.pasteurization_temp is not None else 72.0,
            self.pasteurization_duration if self.pasteurization_duration is not None else 15.0,
            self.pasteurization_temp_std if self.pasteurization_temp_std is not None else 1.0,
            self.env_temp if self.env_temp is not None else 20.0,
            self.env_humidity if self.env_humidity is not None else 60.0,
            self.air_quality_index if self.air_quality_index is not None else 50.0,
            self.equipment_clean_freq if self.equipment_clean_freq is not None else 2.0,
        ]
        return torch.tensor(features, dtype=torch.float32)


@dataclass
class BatchNode:
    """
    产品批次节点（供应链中的核心流转单元）
    
    包含质检结果作为风险预测标签:
    - qc_colony_count: 质检菌落数
    - qc_result: 质检结果 (pass/fail/pending)
    """
    node_id: str
    batch_id: str                       # 批次号
    product_name: str                   # 产品名称
    product_type: str                   # 产品类型 (milk/yogurt/cheese/etc.)
    
    # 关联节点
    enterprise_id: str                  # 生产企业ID
    raw_material_ids: List[str] = field(default_factory=list)  # 使用的原料批次
    production_line_id: Optional[str] = None  # 生产线ID
    
    # 生产信息
    production_date: Optional[str] = None
    expiration_date: Optional[str] = None
    shelf_life_days: Optional[int] = None
    
    # 质量检测
    qc_colony_count: Optional[float] = None     # 质检菌落数
    qc_result: Optional[str] = None             # 质检结果 (pass/fail/pending)
    
    def get_feature_vector(self) -> Tensor:
        """获取批次特征向量"""
        # 产品类型编码
        product_type_map = {
            "milk": 1.0, "yogurt": 2.0, "cheese": 3.0,
            "butter": 4.0, "powder": 5.0, None: 0.0
        }
        product_type_encoded = product_type_map.get(self.product_type, 0.0)
        
        # 质检结果编码
        qc_map = {"pass": 1.0, "pending": 0.5, "fail": 0.0, None: 0.5}
        qc_encoded = qc_map.get(self.qc_result, 0.5)
        
        features = [
            product_type_encoded,
            self.shelf_life_days if self.shelf_life_days is not None else 7.0,
            self.qc_colony_count if self.qc_colony_count is not None else 10000.0,
            qc_encoded,
            len(self.raw_material_ids),  # 原料种类数
        ]
        return torch.tensor(features, dtype=torch.float32)
    
    def get_risk_label(self) -> float:
        """
        获取风险标签（基于qc_colony_count）
        
        Returns:
            风险分数 0-1, 越高表示风险越大
        """
        if self.qc_colony_count is not None:
            # 菌落数越高，风险越大（国家标准100000 CFU/mL为限值）
            risk = min(1.0, self.qc_colony_count / 100000.0)
            return risk
        return 0.5  # 未知风险
    
    def get_binary_label(self) -> int:
        """
        获取二分类标签
        
        Returns:
            0: 合格 (pass)
            1: 不合格 (fail/pending)
        """
        if self.qc_result == "fail":
            return 1
        elif self.qc_result == "pending":
            return 1  # pending视为有风险
        else:
            return 0


@dataclass
class LogisticsNode:
    """
    物流节点
    
    特征字段:
    - transport_temp: 运输温度 (°C)
    - transport_temp_max: 运输最高温度 (°C)
    - transport_duration: 运输时长 (小时)
    - transport_distance: 运输距离 (km)
    - vehicle_type: 车辆类型 (refrigerated/normal)
    - cold_chain_break: 是否断链
    - break_duration: 断链时长 (小时)
    """
    node_id: str
    shipment_id: str                    # 运单号
    logistics_provider: Optional[str] = None  # 物流供应商
    
    # 运输信息
    transport_temp: Optional[float] = None
    transport_temp_max: Optional[float] = None
    transport_duration: Optional[float] = None
    transport_distance: Optional[float] = None
    vehicle_type: Optional[str] = None  # 冷藏车/常温车
    
    # 冷链监控
    cold_chain_break: Optional[bool] = None
    break_duration: Optional[float] = None  # 断链时长
    
    # 起止点
    origin_location: Optional[str] = None
    destination_location: Optional[str] = None
    
    # 时间
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    
    def get_feature_vector(self) -> Tensor:
        """获取物流特征向量"""
        # 车辆类型编码
        vehicle_map = {"refrigerated": 1.0, "normal": 0.0, None: 0.5}
        vehicle_encoded = vehicle_map.get(self.vehicle_type, 0.5)
        
        features = [
            self.transport_temp if self.transport_temp is not None else 4.0,
            self.transport_temp_max if self.transport_temp_max is not None else 8.0,
            self.transport_duration if self.transport_duration is not None else 4.0,
            self.transport_distance if self.transport_distance is not None else 50.0,
            vehicle_encoded,
            1.0 if self.cold_chain_break else 0.0,
            self.break_duration if self.break_duration is not None else 0.0,
        ]
        return torch.tensor(features, dtype=torch.float32)


@dataclass
class RetailNode:
    """
    零售节点
    
    特征字段:
    - retail_type: 零售终端类型 (supermarket/convenience/ecommerce/wholesale)
    - shelf_temp: 货架温度 (°C)
    - inventory_days: 库存天数
    - turnover_rate: 周转率
    - consumer_complaints: 消费者投诉数
    - return_count: 退货数量
    """
    node_id: str
    retail_name: str                    # 零售点名称
    retail_type: Optional[str] = None   # 超市/便利店/电商/批发市场
    retail_channel: Optional[str] = None
    
    # 位置
    location: Optional[str] = None
    district: Optional[str] = None      # 上海市区
    
    # 销售信息
    shelf_temp: Optional[float] = None
    inventory_days: Optional[int] = None
    turnover_rate: Optional[float] = None
    
    # 售后
    consumer_complaints: Optional[int] = None
    return_count: Optional[int] = None
    
    def get_feature_vector(self) -> Tensor:
        """获取零售特征向量"""
        # 零售类型编码
        type_map = {
            "supermarket": 1.0, "convenience": 2.0,
            "ecommerce": 3.0, "wholesale": 4.0, None: 0.0
        }
        type_encoded = type_map.get(self.retail_type, 0.0)
        
        features = [
            type_encoded,
            self.shelf_temp if self.shelf_temp is not None else 6.0,
            self.inventory_days if self.inventory_days is not None else 3.0,
            self.turnover_rate if self.turnover_rate is not None else 0.5,
            self.consumer_complaints if self.consumer_complaints is not None else 0.0,
            self.return_count if self.return_count is not None else 0.0,
        ]
        return torch.tensor(features, dtype=torch.float32)


# 节点类型到特征维度的映射
NODE_FEATURE_DIMS = {
    NodeType.ENTERPRISE: 20,      # 企业特征维度
    NodeType.RAW_MATERIAL: 7,     # 原料特征维度
    NodeType.PRODUCTION_LINE: 8,  # 生产线特征维度
    NodeType.BATCH: 5,            # 批次特征维度
    NodeType.LOGISTICS: 7,        # 物流特征维度
    NodeType.RETAIL: 6,           # 零售特征维度
}


# 导出所有节点类型
__all__ = [
    'NodeType',
    'EnterpriseScale', 
    'EnterpriseNode',
    'RawMaterialNode',
    'ProductionLineNode',
    'BatchNode',
    'LogisticsNode',
    'RetailNode',
    'NODE_FEATURE_DIMS'
]
