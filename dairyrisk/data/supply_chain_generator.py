"""
供应链异构图数据生成器

根据方案文档5.1-5.5章节实现，生成包含6种节点类型和10种边类型的异构图数据。
支持数据完整性差异（大/中/小企业），输出PyTorch Geometric HeteroData格式。

主要功能：
- 生成500-1000节点的异构图
- 模拟大/中/小企业的数据完整性差异
- 批次节点包含合理的风险标签
- 支持保存为PyTorch .pt文件
"""

import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import asdict
import numpy as np
import torch

try:
    from torch_geometric.data import HeteroData
    HAS_PYG = True
except ImportError:
    HAS_PYG = False
    print("Warning: PyTorch Geometric not available. Using fallback implementation.")

from dairyrisk.graph.nodes import (
    EnterpriseNode, RawMaterialNode, ProductionLineNode,
    BatchNode, LogisticsNode, RetailNode,
    NodeType, EnterpriseScale
)
from dairyrisk.graph.edges import Edge, EdgeType, calculate_risk_transmission_coeff, REQUIRED_EDGES


class SimpleHeteroData:
    """简化的HeteroData类，用于替代PyTorch Geometric的HeteroData"""
    
    def __init__(self):
        self._node_types = {}
        self._edge_types = {}
    
    def __getitem__(self, key):
        if isinstance(key, tuple):
            # 边类型 (src, rel, dst)
            edge_key = tuple(key)
            if edge_key not in self._edge_types:
                self._edge_types[edge_key] = {}
            return self._edge_types[edge_key]
        else:
            # 节点类型
            if key not in self._node_types:
                self._node_types[key] = {}
            return self._node_types[key]
    
    def __setitem__(self, key, value):
        if isinstance(key, tuple):
            self._edge_types[tuple(key)] = value
        else:
            self._node_types[key] = value
    
    def __contains__(self, key):
        if isinstance(key, tuple):
            return tuple(key) in self._edge_types
        return key in self._node_types
    
    @property
    def node_types(self):
        return list(self._node_types.keys())
    
    @property
    def edge_types(self):
        return list(self._edge_types.keys())
    
    def __repr__(self):
        return f"SimpleHeteroData(node_types={self.node_types}, edge_types={self.edge_types})"


# 使用PyG的HeteroData或简化版本
HeteroData = HeteroData if HAS_PYG else SimpleHeteroData


class SupplyChainDataGenerator:
    """
    上海市乳制品供应链数据生成器
    
    生成包含四个环节的完整供应链数据：
    - 原料环节 (Raw Material)
    - 生产环境 (Production)
    - 运输与储存 (Transport & Storage)
    - 销售环节 (Retail)
    """
    
    # 上海市各区列表
    SHANGHAI_DISTRICTS = [
        "浦东新区", "黄浦区", "静安区", "徐汇区", "长宁区",
        "普陀区", "虹口区", "杨浦区", "闵行区", "宝山区",
        "嘉定区", "金山区", "松江区", "青浦区", "奉贤区", "崇明区"
    ]
    
    # 企业类型
    ENTERPRISE_TYPES = ["producer", "processor", "distributor", "retailer"]
    
    # 产品类型
    PRODUCT_TYPES = ["milk", "yogurt", "cheese", "butter", "powder"]
    
    # 零售类型
    RETAIL_TYPES = ["supermarket", "convenience", "ecommerce", "wholesale"]
    
    # 数据完整性配置
    COMPLETENESS_CONFIG = {
        EnterpriseScale.LARGE: 0.95,   # 大企业: 95%完整度
        EnterpriseScale.MEDIUM: 0.80,  # 中企业: 80%完整度
        EnterpriseScale.SMALL: 0.50,   # 小企业: 50%完整度
    }
    
    def __init__(self, random_seed: int = 42):
        """初始化生成器"""
        self.rng = np.random.RandomState(random_seed)
        random.seed(random_seed)
        
        # 存储生成的节点
        self.enterprises: Dict[str, EnterpriseNode] = {}
        self.raw_materials: Dict[str, RawMaterialNode] = {}
        self.production_lines: Dict[str, ProductionLineNode] = {}
        self.batches: Dict[str, BatchNode] = {}
        self.logistics: Dict[str, LogisticsNode] = {}
        self.retails: Dict[str, RetailNode] = {}
        
        # 存储生成的边
        self.edges: List[Edge] = []
        
        # 节点ID计数器
        self._enterprise_id_counter = 0
        self._raw_id_counter = 0
        self._line_id_counter = 0
        self._batch_id_counter = 0
        self._logistics_id_counter = 0
        self._retail_id_counter = 0
    
    def generate_supply_chain(
        self,
        num_enterprises: Optional[Dict[str, int]] = None,
        num_batches_per_enterprise: int = 10,
        time_span_days: int = 30
    ) -> HeteroData:
        """
        生成完整供应链数据
        
        Args:
            num_enterprises: 各规模企业数量 {"large": 10, "medium": 50, "small": 200}
            num_batches_per_enterprise: 每个企业生成的批次数量
            time_span_days: 时间跨度（天）
            
        Returns:
            HeteroData对象
        """
        if num_enterprises is None:
            # 默认配置，总计约260家企业，可生成500-1000节点
            num_enterprises = {"large": 10, "medium": 50, "small": 100}
        
        print("=" * 60)
        print("开始生成上海市乳制品供应链数据")
        print("=" * 60)
        
        # 1. 生成企业节点
        print("\n[1/7] 生成企业节点...")
        self._generate_enterprises(num_enterprises)
        
        # 2. 生成原料节点
        print("\n[2/7] 生成原料节点...")
        self._generate_raw_materials()
        
        # 3. 生成生产线节点
        print("\n[3/7] 生成生产线节点...")
        self._generate_production_lines()
        
        # 4. 生成批次节点（核心流转单元）
        print("\n[4/7] 生成产品批次节点...")
        self._generate_batches(num_batches_per_enterprise, time_span_days)
        
        # 5. 生成物流节点
        print("\n[5/7] 生成物流节点...")
        self._generate_logistics()
        
        # 6. 生成零售节点
        print("\n[6/7] 生成零售节点...")
        self._generate_retails()
        
        # 7. 构建边关系
        print("\n[7/7] 构建供应链关系边...")
        self._build_supply_chain_edges()
        
        # 8. 构建异构图
        print("\n构建PyTorch Geometric异构图...")
        hetero_data = self._build_hetero_graph()
        
        # 打印统计信息
        self._print_statistics()
        
        return hetero_data
    
    def _generate_enterprises(self, num_enterprises: Dict[str, int]):
        """生成企业节点，根据规模设置不同的数据完整性"""
        
        for scale_name, count in num_enterprises.items():
            scale = EnterpriseScale(scale_name)
            completeness = self.COMPLETENESS_CONFIG[scale]
            
            for i in range(count):
                node_id = f"ENT_{scale_name.upper()}_{self._enterprise_id_counter:05d}"
                
                # 根据规模确定企业类型分布
                if scale == EnterpriseScale.LARGE:
                    # 大型企业多为生产商和加工商
                    ent_type = self.rng.choice(
                        ["producer", "processor"], 
                        p=[0.6, 0.4]
                    )
                elif scale == EnterpriseScale.MEDIUM:
                    ent_type = self.rng.choice(
                        ["processor", "distributor"],
                        p=[0.5, 0.5]
                    )
                else:  # SMALL
                    ent_type = self.rng.choice(
                        ["distributor", "retailer"],
                        p=[0.4, 0.6]
                    )
                
                # 数据完整性配置
                data_completeness = {
                    "raw_material": completeness,
                    "production": completeness * 0.9,
                    "transport": completeness * 0.95,
                    "retail": completeness * 0.85
                }
                
                enterprise = EnterpriseNode(
                    node_id=node_id,
                    name=f"企业_{scale_name}_{self._enterprise_id_counter}",
                    scale=scale,
                    enterprise_type=ent_type,
                    location=self.rng.choice(self.SHANGHAI_DISTRICTS),
                    registration_date=(datetime.now() - timedelta(days=self.rng.randint(365, 3650))).strftime("%Y-%m-%d"),
                    license_number=f"SC{self.rng.randint(10000000, 99999999)}",
                    data_completeness=data_completeness,
                    features=self._generate_enterprise_features(scale, ent_type, completeness)
                )
                
                self.enterprises[node_id] = enterprise
                self._enterprise_id_counter += 1
        
        print(f"  生成企业节点: {len(self.enterprises)} 个")
        for scale in EnterpriseScale:
            count = sum(1 for e in self.enterprises.values() if e.scale == scale)
            print(f"    - {scale.value}: {count} 个")
    
    def _generate_enterprise_features(
        self, 
        scale: EnterpriseScale, 
        ent_type: str,
        completeness: float
    ) -> Dict[str, Any]:
        """根据企业规模和数据完整性生成特征"""
        features = {}
        
        # 基础特征（所有企业都有）
        features["employee_count"] = {
            EnterpriseScale.LARGE: self.rng.randint(500, 5000),
            EnterpriseScale.MEDIUM: self.rng.randint(100, 500),
            EnterpriseScale.SMALL: self.rng.randint(10, 100)
        }[scale]
        
        features["annual_output"] = {
            EnterpriseScale.LARGE: self.rng.uniform(10000, 100000),
            EnterpriseScale.MEDIUM: self.rng.uniform(1000, 10000),
            EnterpriseScale.SMALL: self.rng.uniform(100, 1000)
        }[scale]
        
        # 企业规模编码
        scale_map = {EnterpriseScale.LARGE: 1.0, EnterpriseScale.MEDIUM: 0.6, EnterpriseScale.SMALL: 0.3}
        features["scale_encoded"] = scale_map[scale]
        
        # 原料环节特征（根据完整性决定是否生成）
        if self.rng.random() < completeness:
            features["raw_storage_temp"] = self.rng.normal(4, 1)
        if self.rng.random() < completeness:
            features["raw_storage_duration"] = self.rng.uniform(6, 24)
        
        # 生产环节特征
        if ent_type in ["producer", "processor"]:
            if self.rng.random() < completeness:
                cleanliness = self.rng.choice(["A", "B", "C", "D"])
                features["cleanliness_level"] = cleanliness
                cleanliness_map = {"A": 1.0, "B": 0.75, "C": 0.5, "D": 0.25}
                features["cleanliness_level_encoded"] = cleanliness_map[cleanliness]
            if self.rng.random() < completeness:
                features["pasteurization_temp"] = self.rng.normal(72, 2)
            if self.rng.random() < completeness:
                features["pasteurization_duration"] = self.rng.uniform(10, 20)
            if self.rng.random() < completeness:
                features["env_temp"] = self.rng.normal(20, 3)
            if self.rng.random() < completeness * 0.8:
                features["env_humidity"] = self.rng.normal(60, 10)
            if self.rng.random() < completeness:
                features["equipment_clean_freq"] = self.rng.randint(1, 4)
            
            # 大型企业特有特征
            if scale == EnterpriseScale.LARGE:
                features["pasteurization_temp_std"] = self.rng.uniform(0.5, 2.0)
                features["air_quality_index"] = self.rng.uniform(30, 80)
        
        # 运输环节特征
        if self.rng.random() < completeness:
            features["transport_temp"] = self.rng.normal(4, 1.5)
        if self.rng.random() < completeness:
            features["transport_duration"] = self.rng.uniform(2, 8)
        if self.rng.random() < completeness:
            vehicle_type = self.rng.choice(["refrigerated", "normal"])
            features["vehicle_type"] = vehicle_type
            features["vehicle_type_encoded"] = 1.0 if vehicle_type == "refrigerated" else 0.0
        
        # 销售环节特征
        if ent_type == "retailer" or self.rng.random() < completeness * 0.8:
            features["retail_type"] = self.rng.choice(self.RETAIL_TYPES)
        if self.rng.random() < completeness:
            features["inventory_days"] = self.rng.randint(1, 7)
        if self.rng.random() < completeness:
            features["consumer_complaints"] = self.rng.poisson(2)
        if self.rng.random() < completeness * 0.8:
            features["return_count"] = self.rng.poisson(0.5)
        if self.rng.random() < completeness * 0.7:
            features["turnover_rate"] = self.rng.uniform(0.3, 0.8)
        
        return features
    
    def _generate_raw_materials(self):
        """生成原料节点，根据企业规模设置数据完整性差异"""
        # 为每个生产企业生成原料
        producer_enterprises = [
            e for e in self.enterprises.values()
            if e.enterprise_type in ["producer", "processor"]
        ]
        
        for enterprise in producer_enterprises:
            # 根据规模确定原料供应商数量
            num_suppliers = {
                EnterpriseScale.LARGE: self.rng.randint(5, 10),
                EnterpriseScale.MEDIUM: self.rng.randint(2, 5),
                EnterpriseScale.SMALL: self.rng.randint(1, 3)
            }[enterprise.scale]
            
            # 每个供应商多批次
            num_raws = num_suppliers * self.rng.randint(2, 5)
            
            for _ in range(num_raws):
                node_id = f"RAW_{self._raw_id_counter:06d}"
                
                # 根据企业规模确定原料数据完整性
                completeness = self.COMPLETENESS_CONFIG[enterprise.scale]
                
                if enterprise.scale == EnterpriseScale.LARGE:
                    # 大企业：完整数据
                    colony_count = self.rng.lognormal(10, 0.5)  # 约22000
                    somatic_cell_count = self.rng.lognormal(12, 0.3)  # 约160000
                    antibiotic_residue = max(0, self.rng.normal(0.05, 0.02))
                elif enterprise.scale == EnterpriseScale.MEDIUM:
                    # 中企业：部分数据
                    colony_count = self.rng.lognormal(10.5, 0.6) if self.rng.random() < 0.8 else None
                    somatic_cell_count = None  # 中型企业不检测
                    antibiotic_residue = None
                else:
                    # 小企业：极少数据
                    colony_count = None
                    somatic_cell_count = None
                    antibiotic_residue = None
                
                raw_material = RawMaterialNode(
                    node_id=node_id,
                    batch_id=f"RB{datetime.now().strftime('%Y%m%d')}_{self._raw_id_counter:04d}",
                    supplier_id=f"SUP_{self.rng.randint(1, 1000):04d}",
                    supplier_name=f"原料供应商_{self._raw_id_counter}",
                    colony_count=colony_count,
                    somatic_cell_count=somatic_cell_count,
                    antibiotic_residue=antibiotic_residue,
                    protein_content=self.rng.normal(3.2, 0.2) if self.rng.random() < completeness else None,
                    fat_content=self.rng.normal(3.5, 0.3) if self.rng.random() < completeness else None,
                    storage_temp=self.rng.normal(4, 1) if self.rng.random() < completeness else None,
                    storage_duration=self.rng.uniform(6, 24) if self.rng.random() < completeness else None,
                    collection_date=(datetime.now() - timedelta(days=self.rng.randint(1, 7))).strftime("%Y-%m-%d")
                )
                
                self.raw_materials[node_id] = raw_material
                self._raw_id_counter += 1
        
        print(f"  生成原料节点: {len(self.raw_materials)} 个")
    
    def _generate_production_lines(self):
        """生成生产线节点"""
        producer_enterprises = [
            e for e in self.enterprises.values()
            if e.enterprise_type in ["producer", "processor"]
        ]
        
        for enterprise in producer_enterprises:
            # 根据规模确定生产线数量
            num_lines = {
                EnterpriseScale.LARGE: self.rng.randint(5, 15),
                EnterpriseScale.MEDIUM: self.rng.randint(2, 5),
                EnterpriseScale.SMALL: self.rng.randint(1, 2)
            }[enterprise.scale]
            
            completeness = self.COMPLETENESS_CONFIG[enterprise.scale]
            
            for i in range(num_lines):
                node_id = f"LINE_{self._line_id_counter:05d}"
                
                production_line = ProductionLineNode(
                    node_id=node_id,
                    enterprise_id=enterprise.node_id,
                    line_name=f"生产线_{i+1}",
                    cleanliness_level=self.rng.choice(["A", "B", "C", "D"]) if self.rng.random() < completeness else None,
                    pasteurization_temp=self.rng.normal(72, 2) if self.rng.random() < completeness else None,
                    pasteurization_duration=self.rng.uniform(10, 20) if self.rng.random() < completeness else None,
                    pasteurization_temp_std=self.rng.uniform(0.5, 2.0) if enterprise.scale == EnterpriseScale.LARGE else None,
                    env_temp=self.rng.normal(20, 3) if self.rng.random() < completeness else None,
                    env_humidity=self.rng.normal(60, 10) if self.rng.random() < completeness * 0.8 else None,
                    air_quality_index=self.rng.uniform(30, 80) if enterprise.scale == EnterpriseScale.LARGE else None,
                    equipment_clean_freq=self.rng.randint(1, 4) if self.rng.random() < completeness else None
                )
                
                self.production_lines[node_id] = production_line
                self._line_id_counter += 1
        
        print(f"  生成生产线节点: {len(self.production_lines)} 个")
    
    def _generate_batches(self, num_per_enterprise: int, time_span_days: int):
        """生成产品批次节点，包含质检结果作为风险标签"""
        producer_enterprises = [
            e for e in self.enterprises.values()
            if e.enterprise_type in ["producer", "processor"]
        ]
        
        for enterprise in producer_enterprises:
            # 获取该企业的生产线
            enterprise_lines = [
                l for l in self.production_lines.values()
                if l.enterprise_id == enterprise.node_id
            ]
            
            # 获取该企业的原料
            enterprise_raws = list(self.raw_materials.values())
            
            for _ in range(num_per_enterprise):
                node_id = f"BATCH_{self._batch_id_counter:07d}"
                
                # 随机选择生产线
                production_line = self.rng.choice(enterprise_lines) if enterprise_lines else None
                
                # 随机选择原料（1-3种）
                num_raws = self.rng.randint(1, min(4, len(enterprise_raws) + 1))
                selected_raws = self.rng.choice(enterprise_raws, size=num_raws, replace=False)
                raw_material_ids = [r.node_id for r in selected_raws]
                
                # 生产日期
                production_date = datetime.now() - timedelta(
                    days=self.rng.randint(0, time_span_days),
                    hours=self.rng.randint(0, 24)
                )
                shelf_life = self.rng.randint(7, 21)
                
                # 质检结果（根据原料质量推断）
                raw_colony_counts = [
                    r.colony_count for r in selected_raws 
                    if r.colony_count is not None
                ]
                
                if raw_colony_counts:
                    avg_colony = np.mean(raw_colony_counts)
                else:
                    # 没有原料数据时，根据企业规模使用默认值
                    avg_colony = {
                        EnterpriseScale.LARGE: 50000,
                        EnterpriseScale.MEDIUM: 80000,
                        EnterpriseScale.SMALL: 120000
                    }[enterprise.scale]
                
                # 质检菌落数 = 原料菌落 + 生产过程影响 + 随机噪声
                production_factor = self.rng.uniform(0.5, 2.0)
                # 小企业生产过程控制较差
                if enterprise.scale == EnterpriseScale.SMALL:
                    production_factor *= self.rng.uniform(1.0, 1.5)
                
                qc_colony = avg_colony * production_factor
                
                # 质检结果（国家标准：菌落总数 ≤ 100000 CFU/mL为合格）
                if qc_colony < 50000:
                    qc_result = "pass"
                elif qc_colony < 100000:
                    qc_result = "pending"
                else:
                    qc_result = "fail"
                
                batch = BatchNode(
                    node_id=node_id,
                    batch_id=f"PB{production_date.strftime('%Y%m%d')}_{self._batch_id_counter:05d}",
                    product_name=f"乳制品_{self._batch_id_counter}",
                    product_type=self.rng.choice(self.PRODUCT_TYPES),
                    enterprise_id=enterprise.node_id,
                    raw_material_ids=raw_material_ids,
                    production_line_id=production_line.node_id if production_line else None,
                    production_date=production_date.strftime("%Y-%m-%d"),
                    expiration_date=(production_date + timedelta(days=shelf_life)).strftime("%Y-%m-%d"),
                    shelf_life_days=shelf_life,
                    qc_colony_count=qc_colony,
                    qc_result=qc_result
                )
                
                self.batches[node_id] = batch
                self._batch_id_counter += 1
        
        print(f"  生成批次节点: {len(self.batches)} 个")
    
    def _generate_logistics(self):
        """生成物流节点"""
        # 为每个批次生成物流记录
        for batch in self.batches.values():
            # 获取生产企业
            enterprise = self.enterprises.get(batch.enterprise_id)
            if not enterprise:
                continue
            
            node_id = f"LOG_{self._logistics_id_counter:06d}"
            
            # 根据企业规模确定物流数据完整性
            completeness = self.COMPLETENESS_CONFIG.get(enterprise.scale, 0.5)
            
            # 运输温度（可能断链）
            cold_chain_break = self.rng.random() < 0.1  # 10%概率断链
            transport_temp = self.rng.normal(6 if cold_chain_break else 4, 2)
            transport_temp_max = None
            if self.rng.random() < completeness:
                transport_temp_max = transport_temp + self.rng.uniform(0, 5)
            
            logistics = LogisticsNode(
                node_id=node_id,
                shipment_id=f"SH{self._logistics_id_counter:06d}",
                logistics_provider=f"物流商_{self.rng.randint(1, 50)}",
                transport_temp=transport_temp if self.rng.random() < completeness else None,
                transport_temp_max=transport_temp_max,
                transport_duration=self.rng.uniform(2, 12),
                transport_distance=self.rng.uniform(10, 200),
                vehicle_type=self.rng.choice(["refrigerated", "normal"]),
                cold_chain_break=cold_chain_break,
                break_duration=self.rng.uniform(0.5, 3) if cold_chain_break else None,
                origin_location=enterprise.location,
                destination_location=self.rng.choice(self.SHANGHAI_DISTRICTS),
                departure_time=(datetime.now() - timedelta(days=self.rng.randint(1, 30))).strftime("%Y-%m-%d %H:%M:%S"),
                arrival_time=(datetime.now() - timedelta(days=self.rng.randint(0, 29))).strftime("%Y-%m-%d %H:%M:%S")
            )
            
            self.logistics[node_id] = logistics
            self._logistics_id_counter += 1
        
        print(f"  生成物流节点: {len(self.logistics)} 个")
    
    def _generate_retails(self):
        """生成零售节点"""
        # 生成零售点 - 动态调整数量以控制总节点数
        num_retails = {
            "supermarket": 30,
            "convenience": 50,
            "ecommerce": 10,
            "wholesale": 10
        }
        
        for retail_type, count in num_retails.items():
            for i in range(count):
                node_id = f"RET_{self._retail_id_counter:05d}"
                
                retail = RetailNode(
                    node_id=node_id,
                    retail_name=f"{retail_type}_{self._retail_id_counter}",
                    retail_type=retail_type,
                    retail_channel=retail_type,
                    location=self.rng.choice(self.SHANGHAI_DISTRICTS),
                    district=self.rng.choice(self.SHANGHAI_DISTRICTS),
                    shelf_temp=self.rng.normal(6, 2) if retail_type in ["supermarket", "convenience"] else None,
                    inventory_days=self.rng.randint(1, 7),
                    turnover_rate=self.rng.uniform(0.3, 0.8),
                    consumer_complaints=self.rng.poisson(1),
                    return_count=self.rng.poisson(0.5)
                )
                
                self.retails[node_id] = retail
                self._retail_id_counter += 1
        
        print(f"  生成零售节点: {len(self.retails)} 个")
    
    def _build_supply_chain_edges(self):
        """构建供应链关系边（10种边类型）"""
        
        # 1. 企业-原料: PURCHASES (enterprise --purchases--> raw_material)
        for raw in self.raw_materials.values():
            for batch in self.batches.values():
                if raw.node_id in batch.raw_material_ids:
                    edge = Edge(
                        src_id=batch.enterprise_id,
                        dst_id=raw.node_id,
                        edge_type=EdgeType.PURCHASES,
                        features={
                            "purchase_volume": self.rng.uniform(100, 10000),
                            "purchase_frequency": self.rng.randint(1, 30),
                            "price": self.rng.uniform(3, 8),
                            "quality_score": self.rng.uniform(0.7, 1.0)
                        },
                        weight=self.rng.uniform(0.5, 1.0)
                    )
                    self.edges.append(edge)
        
        # 2. 企业-生产线: OWNS (enterprise --owns--> production_line)
        for line in self.production_lines.values():
            edge = Edge(
                src_id=line.enterprise_id,
                dst_id=line.node_id,
                edge_type=EdgeType.OWNS,
                features={"ownership_ratio": 1.0},
                weight=1.0
            )
            self.edges.append(edge)
        
        # 3. 生产线-批次: PRODUCES (production_line --produces--> batch)
        for batch in self.batches.values():
            if batch.production_line_id:
                edge = Edge(
                    src_id=batch.production_line_id,
                    dst_id=batch.node_id,
                    edge_type=EdgeType.PRODUCES,
                    features={
                        "production_volume": self.rng.uniform(1000, 100000),
                        "efficiency": self.rng.uniform(0.7, 0.95)
                    },
                    weight=self.rng.uniform(0.8, 1.0),
                    risk_transmission_coeff=0.75
                )
                self.edges.append(edge)
        
        # 4. 原料-批次: USED_IN (raw_material --used_in--> batch)
        for batch in self.batches.values():
            for raw_id in batch.raw_material_ids:
                edge = Edge(
                    src_id=raw_id,
                    dst_id=batch.node_id,
                    edge_type=EdgeType.USED_IN,
                    features={
                        "usage_ratio": self.rng.uniform(0.2, 0.5),
                        "raw_quality": self.rng.uniform(0.7, 1.0)
                    },
                    weight=self.rng.uniform(0.6, 1.0),
                    risk_transmission_coeff=0.8  # 原料风险传导系数
                )
                self.edges.append(edge)
        
        # 5. 企业-批次: MANUFACTURES (enterprise --manufactures--> batch)
        for batch in self.batches.values():
            edge = Edge(
                src_id=batch.enterprise_id,
                dst_id=batch.node_id,
                edge_type=EdgeType.MANUFACTURES,
                features={"manufacture_date_encoded": self.rng.uniform(0, 365)},
                weight=1.0
            )
            self.edges.append(edge)
        
        # 6. 批次-物流: TRANSPORTED_BY (batch --transported_by--> logistics)
        logistics_list = list(self.logistics.values())
        for i, batch in enumerate(self.batches.values()):
            if i < len(logistics_list):
                logistics = logistics_list[i]
                edge = Edge(
                    src_id=batch.node_id,
                    dst_id=logistics.node_id,
                    edge_type=EdgeType.TRANSPORTED_BY,
                    features={
                        "transport_volume": self.rng.uniform(1000, 50000),
                        "transport_duration": logistics.transport_duration if logistics.transport_duration else 4.0,
                        "distance": logistics.transport_distance if logistics.transport_distance else 50.0,
                        "temp_control": 1.0 if logistics.vehicle_type == "refrigerated" else 0.0
                    },
                    weight=0.8 if logistics.vehicle_type == "refrigerated" else 0.5,
                    risk_transmission_coeff=0.6 if logistics.cold_chain_break else 0.3
                )
                self.edges.append(edge)
        
        # 7. 物流-零售: DELIVERS_TO (logistics --delivers_to--> retail)
        for logistics in self.logistics.values():
            # 随机选择零售点
            retail = self.rng.choice(list(self.retails.values()))
            edge = Edge(
                src_id=logistics.node_id,
                dst_id=retail.node_id,
                edge_type=EdgeType.DELIVERS_TO,
                features={
                    "delivery_volume": self.rng.uniform(100, 5000),
                    "delivery_frequency": self.rng.randint(1, 7)
                },
                weight=self.rng.uniform(0.5, 0.9)
            )
            self.edges.append(edge)
        
        # 8. 批次-零售: SOLD_AT (batch --sold_at--> retail)
        for batch in self.batches.values():
            # 每个批次销售到1-3个零售点
            num_retails = self.rng.randint(1, 4)
            selected_retails = self.rng.choice(
                list(self.retails.values()), 
                size=min(num_retails, len(self.retails)),
                replace=False
            )
            
            for retail in selected_retails:
                edge = Edge(
                    src_id=batch.node_id,
                    dst_id=retail.node_id,
                    edge_type=EdgeType.SOLD_AT,
                    features={
                        "sales_volume": self.rng.uniform(100, 10000),
                        "sales_speed": self.rng.uniform(0.3, 0.9),
                        "inventory_turnover": retail.turnover_rate if retail.turnover_rate else 0.5
                    },
                    weight=self.rng.uniform(0.4, 0.8)
                )
                self.edges.append(edge)
        
        # 9. 企业间关系: SUPPLIES (enterprise --supplies--> enterprise)
        distributors = [e for e in self.enterprises.values() if e.enterprise_type == "distributor"]
        retailers = [e for e in self.enterprises.values() if e.enterprise_type == "retailer"]
        
        for retailer in retailers:
            # 每个零售商从1-3个分销商进货
            num_suppliers = self.rng.randint(1, 4)
            if len(distributors) > 0:
                selected_suppliers = self.rng.choice(
                    distributors,
                    size=min(num_suppliers, len(distributors)),
                    replace=False
                )
                
                for supplier in selected_suppliers:
                    edge = Edge(
                        src_id=supplier.node_id,
                        dst_id=retailer.node_id,
                        edge_type=EdgeType.SUPPLIES,
                        features={
                            "supply_volume": self.rng.uniform(1000, 50000),
                            "supply_frequency": self.rng.randint(1, 30),
                            "cooperation_duration": self.rng.randint(1, 10)
                        },
                        weight=self.rng.uniform(0.5, 0.9),
                        risk_transmission_coeff=0.7
                    )
                    self.edges.append(edge)
        
        # 10. 时序关系: TEMPORAL_NEXT (batch --temporal_next--> batch)
        for line in self.production_lines.values():
            line_batches = [
                b for b in self.batches.values()
                if b.production_line_id == line.node_id
            ]
            
            # 按生产日期排序
            line_batches.sort(key=lambda x: x.production_date or "")
            
            # 连接相邻批次
            for i in range(len(line_batches) - 1):
                edge = Edge(
                    src_id=line_batches[i].node_id,
                    dst_id=line_batches[i + 1].node_id,
                    edge_type=EdgeType.TEMPORAL_NEXT,
                    features={
                        "time_interval": self.rng.uniform(1, 24)  # 小时
                    },
                    weight=0.5,
                    risk_transmission_coeff=0.5
                )
                self.edges.append(edge)
        
        print(f"  生成边: {len(self.edges)} 条")
        
        # 统计各类型边数量
        edge_type_counts = {}
        for edge in self.edges:
            et = edge.edge_type.canonical_name
            edge_type_counts[et] = edge_type_counts.get(et, 0) + 1
        
        for et, count in sorted(edge_type_counts.items()):
            print(f"    - {et}: {count} 条")
    
    def _build_hetero_graph(self) -> HeteroData:
        """构建PyTorch Geometric异构图"""
        data = HeteroData()
        
        # 1. 添加企业节点
        if self.enterprises:
            ent_features = []
            for e in self.enterprises.values():
                feat = e.get_feature_vector()
                # 确保特征维度一致
                if feat.shape[0] < 20:
                    feat = torch.cat([feat, torch.zeros(20 - feat.shape[0])])
                elif feat.shape[0] > 20:
                    feat = feat[:20]
                ent_features.append(feat)
            
            data["enterprise"].x = torch.stack(ent_features)
            data["enterprise"].node_ids = list(self.enterprises.keys())
            data["enterprise"].scale = torch.tensor([
                1.0 if e.scale == EnterpriseScale.LARGE else (0.6 if e.scale == EnterpriseScale.MEDIUM else 0.3)
                for e in self.enterprises.values()
            ], dtype=torch.float32)
        
        # 2. 添加原料节点
        if self.raw_materials:
            raw_features = torch.stack([
                r.get_feature_vector() for r in self.raw_materials.values()
            ])
            data["raw_material"].x = raw_features
            data["raw_material"].node_ids = list(self.raw_materials.keys())
        
        # 3. 添加生产线节点
        if self.production_lines:
            line_features = torch.stack([
                l.get_feature_vector() for l in self.production_lines.values()
            ])
            data["production_line"].x = line_features
            data["production_line"].node_ids = list(self.production_lines.keys())
        
        # 4. 添加批次节点（包含标签）
        if self.batches:
            batch_features = torch.stack([
                b.get_feature_vector() for b in self.batches.values()
            ])
            data["batch"].x = batch_features
            data["batch"].node_ids = list(self.batches.keys())
            
            # 添加连续风险标签（0-1）
            risk_labels = torch.tensor([
                b.get_risk_label() for b in self.batches.values()
            ], dtype=torch.float32)
            data["batch"].y_risk = risk_labels
            
            # 添加二分类标签（0=合格, 1=不合格）
            binary_labels = torch.tensor([
                b.get_binary_label() for b in self.batches.values()
            ], dtype=torch.long)
            data["batch"].y_binary = binary_labels
            
            # 添加QC菌落数作为回归目标
            qc_counts = torch.tensor([
                b.qc_colony_count if b.qc_colony_count else 50000.0
                for b in self.batches.values()
            ], dtype=torch.float32)
            data["batch"].y_qc_count = qc_counts
        
        # 5. 添加物流节点
        if self.logistics:
            log_features = torch.stack([
                l.get_feature_vector() for l in self.logistics.values()
            ])
            data["logistics"].x = log_features
            data["logistics"].node_ids = list(self.logistics.keys())
        
        # 6. 添加零售节点
        if self.retails:
            ret_features = torch.stack([
                r.get_feature_vector() for r in self.retails.values()
            ])
            data["retail"].x = ret_features
            data["retail"].node_ids = list(self.retails.keys())
        
        # 7. 添加边
        node_type_to_idx = {
            "enterprise": {nid: i for i, nid in enumerate(self.enterprises.keys())},
            "raw_material": {nid: i for i, nid in enumerate(self.raw_materials.keys())},
            "production_line": {nid: i for i, nid in enumerate(self.production_lines.keys())},
            "batch": {nid: i for i, nid in enumerate(self.batches.keys())},
            "logistics": {nid: i for i, nid in enumerate(self.logistics.keys())},
            "retail": {nid: i for i, nid in enumerate(self.retails.keys())},
        }
        
        # 按边类型分组
        edge_groups: Dict[str, List[Edge]] = {}
        for edge in self.edges:
            et_name = edge.edge_type.canonical_name
            if et_name not in edge_groups:
                edge_groups[et_name] = []
            edge_groups[et_name].append(edge)
        
        # 添加每种边类型到HeteroData
        for edge_name, edges in edge_groups.items():
            edge_type = edges[0].edge_type
            src_type = edge_type.src
            rel_type = edge_type.rel
            dst_type = edge_type.dst
            
            src_indices = []
            dst_indices = []
            edge_attrs = []
            
            for edge in edges:
                src_idx = node_type_to_idx[src_type].get(edge.src_id)
                dst_idx = node_type_to_idx[dst_type].get(edge.dst_id)
                
                if src_idx is not None and dst_idx is not None:
                    src_indices.append(src_idx)
                    dst_indices.append(dst_idx)
                    edge_attrs.append(edge.get_feature_vector())
            
            if src_indices:
                edge_index = torch.tensor([src_indices, dst_indices], dtype=torch.long)
                data[src_type, rel_type, dst_type].edge_index = edge_index
                
                # 堆叠边特征
                if edge_attrs:
                    edge_attr = torch.stack(edge_attrs)
                    data[src_type, rel_type, dst_type].edge_attr = edge_attr
        
        return data
    
    def _print_statistics(self):
        """打印统计信息"""
        print("\n" + "=" * 60)
        print("供应链数据统计")
        print("=" * 60)
        
        total_nodes = sum([
            len(self.enterprises), len(self.raw_materials), 
            len(self.production_lines), len(self.batches), 
            len(self.logistics), len(self.retails)
        ])
        
        print(f"\n节点统计 (总计: {total_nodes} 个):")
        print(f"  企业节点: {len(self.enterprises)} 个")
        for scale in EnterpriseScale:
            count = sum(1 for e in self.enterprises.values() if e.scale == scale)
            print(f"    - {scale.value}: {count} 个")
        print(f"  原料节点: {len(self.raw_materials)} 个")
        print(f"  生产线节点: {len(self.production_lines)} 个")
        print(f"  批次节点: {len(self.batches)} 个")
        print(f"  物流节点: {len(self.logistics)} 个")
        print(f"  零售节点: {len(self.retails)} 个")
        
        print(f"\n边统计:")
        print(f"  总边数: {len(self.edges)} 条")
        
        # 各类型边统计
        edge_type_counts = {}
        for edge in self.edges:
            et = edge.edge_type.canonical_name
            edge_type_counts[et] = edge_type_counts.get(et, 0) + 1
        
        for et, count in sorted(edge_type_counts.items()):
            print(f"    - {et}: {count} 条")
        
        # 正样本统计（基于质检结果）
        if self.batches:
            fail_batches = sum(1 for b in self.batches.values() if b.qc_result == "fail")
            pending_batches = sum(1 for b in self.batches.values() if b.qc_result == "pending")
            pass_batches = len(self.batches) - fail_batches - pending_batches
            
            print(f"\n风险批次统计:")
            print(f"  不合格批次: {fail_batches} ({fail_batches/len(self.batches)*100:.2f}%)")
            print(f"  待检批次: {pending_batches} ({pending_batches/len(self.batches)*100:.2f}%)")
            print(f"  合格批次: {pass_batches} ({pass_batches/len(self.batches)*100:.2f}%)")
        
        print("=" * 60)
    
    def save_to_file(self, data: HeteroData, filepath: str):
        """
        保存生成的异构图到文件
        
        Args:
            data: HeteroData对象
            filepath: 保存路径（.pt文件）
        """
        torch.save(data, filepath)
        print(f"\n数据已保存到: {filepath}")
    
    def get_nodes_by_scale(self, scale: EnterpriseScale) -> List[EnterpriseNode]:
        """获取指定规模的企业节点"""
        return [e for e in self.enterprises.values() if e.scale == scale]
    
    def get_high_risk_batches(self, threshold: float = 0.5) -> List[BatchNode]:
        """获取高风险批次"""
        return [b for b in self.batches.values() if b.get_risk_label() >= threshold]


def main():
    """主函数 - 生成示例数据"""
    # 创建生成器
    generator = SupplyChainDataGenerator(random_seed=42)
    
    # 生成供应链数据
    # 配置: 10大企业 + 50中型企业 + 100小企业，每个企业5个批次
    hetero_data = generator.generate_supply_chain(
        num_enterprises={"large": 10, "medium": 50, "small": 100},
        num_batches_per_enterprise=5,
        time_span_days=30
    )
    
    # 保存数据
    output_path = "/home/yarizakurahime/data/dairy_supply_chain_risk/data/supply_chain_graph.pt"
    generator.save_to_file(hetero_data, output_path)
    
    print("\n异构图结构:")
    print(hetero_data)
    
    return hetero_data


if __name__ == "__main__":
    main()
