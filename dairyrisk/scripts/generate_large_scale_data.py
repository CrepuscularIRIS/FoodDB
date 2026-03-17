#!/usr/bin/env python3
"""
大规模乳制品供应链数据生成脚本 V2
生成 500-1000 个节点的异构图数据，包含丰富的供应链关系
"""

import csv
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple

# ============ 配置参数 ============
TOTAL_NODES = 800  # 目标节点数量
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "v2_scale"

# 节点类型分布 (按需求：小企业是重点监管对象，大量)
NODE_TYPE_DIST = {
    "牧场": 0.20,      # 20% - 源头
    "乳企": 0.15,      # 15% - 加工
    "物流": 0.18,      # 18% - 运输
    "仓储": 0.15,      # 15% - 存储
    "零售": 0.20,      # 20% - 销售
    "质检": 0.07,      # 7%  - 检测
    "饲料": 0.05,      # 5%  - 上游
}

# 企业规模分布 (小企业占大多数)
SCALE_DIST = {
    "large": 0.08,     # 大企业 8%
    "medium": 0.22,    # 中企业 22%
    "small": 0.50,     # 小企业 50% - 重点监管
    "micro": 0.20,     # 微企业 20%
}

# 信用评级分布
CREDIT_RATING_DIST = {
    "A": 0.30,
    "B": 0.45,
    "C": 0.20,
    "D": 0.05,
}

# 风险因子定义
RISK_FACTORS = [
    {"id": "RF001", "name": "微生物污染", "category": "生物性", "base_risk": 0.15},
    {"id": "RF002", "name": "添加剂超标", "category": "化学性", "base_risk": 0.12},
    {"id": "RF003", "name": "兽药残留", "category": "化学性", "base_risk": 0.18},
    {"id": "RF004", "name": "重金属污染", "category": "化学性", "base_risk": 0.08},
    {"id": "RF005", "name": "包装破损", "category": "物理性", "base_risk": 0.10},
    {"id": "RF006", "name": "冷链断裂", "category": "过程控制", "base_risk": 0.25},
    {"id": "RF007", "name": "标签虚假", "category": "标识欺诈", "base_risk": 0.20},
    {"id": "RF008", "name": "过期产品", "category": "质量管理", "base_risk": 0.22},
    {"id": "RF009", "name": "生产许可缺失", "category": "资质合规", "base_risk": 0.35},
    {"id": "RF010", "name": "卫生条件差", "category": "现场管理", "base_risk": 0.28},
]

# 供应链边类型
EDGE_TYPES = [
    "raw_material",    # 原料供应
    "production",       # 委托加工
    "transport",       # 运输服务
    "storage",         # 仓储服务
    "sale",            # 销售关系
    "supply",          # 原料调拨
    "inspection",      # 质检服务
    "feed_supply",     # 饲料供应
]

# 省份和城市
PROVINCES = [
    ("上海", 31.2304, 121.4737),
    ("江苏", 32.0603, 118.7969),
    ("浙江", 30.2873, 120.1536),
    ("安徽", 31.8612, 117.2830),
    ("山东", 36.6512, 117.1205),
    ("河南", 34.7466, 113.6254),
    ("河北", 38.0428, 114.5149),
    ("内蒙古", 40.8180, 111.6708),
    ("黑龙江", 45.8038, 126.5340),
    ("吉林", 43.8968, 125.3245),
]

DISTRICTS = ["浦东新区", "徐汇区", "黄浦区", "静安区", "长宁区", "普陀区", "杨浦区", "虹口区", "闵行区", "宝山区", "嘉定区", "金山区", "松江区", "青浦区", "奉贤区", "崇明区"]

# 产品类型
PRODUCTS = {
    "牧场": ["生鲜牛奶", "原奶", "奶油", "酸奶基料"],
    "乳企": ["巴氏杀菌乳", "超高温灭菌乳", "酸奶", "乳酪", "黄油", "奶粉", "冰淇淋", "含乳饮料"],
    "饲料": ["奶牛精饲料", "粗饲料", "预混料", "饲料添加剂"],
}

# ============ 辅助函数 ============

def weighted_choice(choices: Dict[str, float]) -> str:
    """根据权重选择"""
    items = list(choices.keys())
    weights = list(choices.values())
    return random.choices(items, weights=weights, k=1)[0]

def generate_enterprise_id(node_type: str, index: int) -> str:
    """生成企业ID"""
    prefix_map = {
        "牧场": "PAST",
        "乳企": "DAIR",
        "物流": "LOGI",
        "仓储": "WARE",
        "零售": "RETA",
        "质检": "TEST",
        "饲料": "FEED",
    }
    return f"ENT-{prefix_map.get(node_type, 'ENT')}-{index:05d}"

def generate_license_no() -> str:
    """生成食品经营许可证号"""
    return f"SC{random.randint(100000, 999999)}{random.randint(10000000, 99999999)}"

def generate_date(start_year: int = 2000, end_year: int = 2023) -> str:
    """生成随机日期"""
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    random_days = random.randint(0, delta.days)
    return (start + timedelta(days=random_days)).strftime("%Y-%m-%d")

def generate_coordinates() -> Tuple[float, float]:
    """生成上海及周边坐标"""
    province, lat, lon = random.choice(PROVINCES)
    # 添加随机偏移
    lat += random.uniform(-0.5, 0.5)
    lon += random.uniform(-0.5, 0.5)
    return round(lat, 6), round(lon, 6)

def calculate_base_risk(scale: str, credit_rating: str, node_type: str, target_risk_level: str = None) -> Tuple[float, str]:
    """计算基础风险值，返回(风险值, 风险等级)"""
    # 规模因子：小企业风险更高
    scale_risk = {"large": 0.25, "medium": 0.40, "small": 0.55, "micro": 0.70}[scale]
    
    # 信用因子
    credit_risk = {"A": 0.20, "B": 0.40, "C": 0.60, "D": 0.85}[credit_rating]
    
    # 类型因子
    type_risk = {
        "牧场": 0.40, "乳企": 0.45, "物流": 0.50, 
        "仓储": 0.45, "零售": 0.55, "质检": 0.25, "饲料": 0.50
    }.get(node_type, 0.45)
    
    # 综合风险
    base_risk = (scale_risk * 0.35 + credit_risk * 0.35 + type_risk * 0.3)
    
    # 添加随机波动
    base_risk += random.uniform(-0.08, 0.12)
    base_risk = max(0.10, min(0.90, base_risk))
    
    # 确定风险等级
    if base_risk < 0.30:
        risk_level = "low"
    elif base_risk < 0.70:
        risk_level = "medium"
    else:
        risk_level = "high"
    
    return base_risk, risk_level

def assign_risk_factors(node_type: str, base_risk: float, target_risk_level: str = None) -> List[Dict]:
    """为节点分配风险因子"""
    # 根据目标风险等级决定因子数量
    if target_risk_level == "low":
        num_factors = random.choices([0, 1], weights=[0.6, 0.4])[0]
    elif target_risk_level == "high":
        num_factors = random.choices([1, 2, 3], weights=[0.2, 0.4, 0.4])[0]
    else:
        num_factors = random.choices([0, 1, 2], weights=[0.3, 0.4, 0.3])[0]
    
    selected = random.sample(RISK_FACTORS, min(num_factors, len(RISK_FACTORS)))
    
    factors = []
    for rf in selected:
        # 风险因子会提高节点风险
        factor_risk = rf["base_risk"] * random.uniform(0.5, 1.5)
        factors.append({
            "risk_factor_id": rf["id"],
            "name": rf["name"],
            "category": rf["category"],
            "present": True,
            "severity": round(factor_risk, 3),
            "detection_prob": round(random.uniform(0.3, 0.9), 2)
        })
    
    return factors

# ============ 主生成逻辑 ============

def generate_nodes() -> Tuple[List[Dict], Dict]:
    """生成所有节点，确保风险等级均衡分布"""
    nodes = []
    node_counts = {nt: 0 for nt in NODE_TYPE_DIST}
    risk_level_counts = {"low": 0, "medium": 0, "high": 0}
    
    # 目标风险等级分布 (均衡)
    target_risk_distribution = {"low": 0.30, "medium": 0.40, "high": 0.30}
    
    # 第一轮：确保每种类型都有，并尽量均衡风险等级
    for node_type in NODE_TYPE_DIST:
        count = max(10, int(TOTAL_NODES * NODE_TYPE_DIST[node_type] * 0.3))
        for i in range(count):
            # 轮转选择风险等级
            remaining_slots = {
                "low": int(count * target_risk_distribution["low"]) - risk_level_counts["low"],
                "medium": int(count * target_risk_distribution["medium"]) - risk_level_counts["medium"],
                "high": int(count * target_risk_distribution["high"]) - risk_level_counts["high"],
            }
            # 选择当前最少的风险等级
            target_level = min(remaining_slots, key=remaining_slots.get)
            node = create_node(node_type, node_counts[node_type] + 1, target_level)
            nodes.append(node)
            node_counts[node_type] += 1
            risk_level_counts[node["risk_level"]] += 1
    
    # 第二轮：补齐到目标数量，继续保持均衡
    current_total = len(nodes)
    remaining = TOTAL_NODES - current_total
    
    while current_total < TOTAL_NODES:
        node_type = weighted_choice(NODE_TYPE_DIST)
        # 选择当前最少的风险等级
        target_level = min(risk_level_counts, key=risk_level_counts.get)
        node = create_node(node_type, node_counts[node_type] + 1, target_level)
        nodes.append(node)
        node_counts[node_type] += 1
        risk_level_counts[node["risk_level"]] += 1
        current_total += 1
    
    return nodes, node_counts

def create_node(node_type: str, index: int, target_risk_level: str = None) -> Dict:
    """创建单个节点
    
    Args:
        node_type: 节点类型
        index: 序号
        target_risk_level: 目标风险等级 (low/medium/high)，如果为None则自动计算
    """
    enterprise_id = generate_enterprise_id(node_type, index)
    scale = weighted_choice(SCALE_DIST)
    credit_rating = weighted_choice(CREDIT_RATING_DIST)
    lat, lon = generate_coordinates()
    
    province, _, _ = random.choice(PROVINCES)
    district = random.choice(DISTRICTS) if province == "上海" else f"{province}市辖区"
    
    # 企业名称生成
    prefixes = {
        "牧场": ["光明", "现代", "蒙牛", "伊利", "三元", "辉山", "飞鹤", "君乐宝", "澳优", "天润", "圣湖", "红星"],
        "乳企": ["光明", "蒙牛", "伊利", "三元", "飞鹤", "君乐宝", "澳优", "完达山", "贝因美", "雅士利", "明一", "合生元"],
        "物流": ["顺丰", "京东", "菜鸟", "中通", "圆通", "韵达", "德邦", "安能", "远成", "恒路"],
        "仓储": ["冷链", "菜鸟", "京东", "安井", "鲜生活", "每日", "盒马", "大润发", "永辉"],
        "零售": ["盒马", "大润发", "永辉", "沃尔玛", "家乐福", "华润", "物美", "苏宁", "京东到家", "饿了么"],
        "质检": ["华测", "谱尼", "SGS", "Intertek", "BV", "中检", "上海质检", "江苏质检"],
        "饲料": ["安迪苏", "帝斯曼", "蓝星", "新希望", "通威", "海大", "大北农", "正大"],
    }
    
    suffixes = {
        "牧场": ["牧场", "奶牛场", "乳牛场", "养殖基地"],
        "乳企": ["乳业有限公司", "乳制品有限公司", "食品有限公司", "乳品加工厂"],
        "物流": ["物流有限公司", "冷链物流有限公司", "运输有限公司", "供应链管理有限公司"],
        "仓储": ["仓储有限公司", "冷链仓储有限公司", "物流中心", "配送中心"],
        "零售": ["超市", "便利店", "门店", "旗舰店", "专营店"],
        "质检": ["检测技术有限公司", "检测中心", "质量检验有限公司", "认证服务有限公司"],
        "饲料": ["饲料有限公司", "饲料科技有限公司", "饲料加工厂", "畜牧科技有限公司"],
    }
    
    prefix = random.choice(prefixes.get(node_type, ["企业"]))
    suffix = random.choice(suffixes.get(node_type, ["有限公司"]))
    enterprise_name = f"{prefix}{suffix}"
    
    # 产品
    main_products = random.choice(PRODUCTS.get(node_type, ["乳制品"])) if node_type in PRODUCTS else "乳制品"
    
    # 认证状态 (根据目标风险调整)
    if target_risk_level == "low":
        haccp_certified = random.choices([True, False], weights=[0.7, 0.3])[0]
        iso22000_certified = random.choices([True, False], weights=[0.6, 0.4])[0]
    elif target_risk_level == "high":
        haccp_certified = random.choices([True, False], weights=[0.2, 0.8])[0]
        iso22000_certified = random.choices([True, False], weights=[0.1, 0.9])[0]
    else:
        haccp_certified = random.choices([True, False], weights=[0.4, 0.6])[0]
        iso22000_certified = random.choices([True, False], weights=[0.25, 0.75])[0]
    
    # 历史违规和检查次数 (根据目标风险调整)
    if credit_rating == "A":
        historical_violation_count = random.choices([0, 1, 2], weights=[0.7, 0.25, 0.05])[0]
    elif credit_rating == "B":
        historical_violation_count = random.choices([0, 1, 2, 3], weights=[0.4, 0.35, 0.2, 0.05])[0]
    else:
        historical_violation_count = random.choices([1, 2, 3, 4, 5], weights=[0.2, 0.3, 0.25, 0.15, 0.1])[0]
    
    inspection_count = random.randint(1, 15)
    
    # 监督频次 (根据目标风险调整)
    if target_risk_level == "low":
        supervision_freq = random.choice([2, 3, 4])
    elif target_risk_level == "high":
        supervision_freq = random.choice([6, 7, 8])
    else:
        supervision_freq = random.choice([4, 5, 6])
    
    # 计算基础风险
    base_risk, _ = calculate_base_risk(scale, credit_rating, node_type)
    
    # 分配风险因子 (高风险企业更容易有问题因子)
    risk_factors = assign_risk_factors(node_type, base_risk, target_risk_level)
    
    # 实际风险标签 (用于训练)
    # 策略：根据目标风险等级生成风险值，确保特征与风险有相关性
    
    if target_risk_level == "low":
        # 低风险企业
        actual_risk = random.uniform(0.08, 0.25)
        risk_level = "low"
    elif target_risk_level == "medium":
        # 中风险企业
        actual_risk = random.uniform(0.35, 0.62)
        risk_level = "medium"
    else:
        # 高风险企业
        actual_risk = random.uniform(0.72, 0.95)
        risk_level = "high"
    
    # 限制范围
    actual_risk = max(0.08, min(0.95, actual_risk))
    
    # 产能 (乳企和牧场)
    if node_type in ["乳企", "牧场"]:
        production_capacity_daily = round(random.uniform(50, 500), 2)
    else:
        production_capacity_daily = None
    
    node = {
        "enterprise_id": enterprise_id,
        "enterprise_name": enterprise_name,
        "data_source": "v2_simulation",
        "address": f"{province}省{district}{random.randint(1, 999)}号",
        "credit_rating": credit_rating,
        "enterprise_type": scale,
        "enterprise_type_detail": node_type,
        "establishment_date": generate_date(2000, 2020),
        "haccp_certified": haccp_certified,
        "iso22000_certified": iso22000_certified,
        "historical_violation_count": historical_violation_count,
        "inspection_count": inspection_count,
        "latitude": lat,
        "longitude": lon,
        "license_no": generate_license_no(),
        "main_products": main_products,
        "node_type": node_type,
        "production_capacity_daily": production_capacity_daily,
        "supervision_freq": supervision_freq,
        # 风险相关
        "base_risk_score": round(base_risk, 4),
        "actual_risk_score": round(actual_risk, 4),
        "risk_level": risk_level,
        "risk_factors": risk_factors,
    }
    
    return node

def generate_edges(nodes: List[Dict]) -> List[Dict]:
    """生成供应链边关系"""
    edges = []
    edge_index = 1
    
    # 按类型分组节点
    nodes_by_type = {}
    for node in nodes:
        nt = node["node_type"]
        if nt not in nodes_by_type:
            nodes_by_type[nt] = []
        nodes_by_type[nt].append(node)
    
    # 1. 牧场 -> 乳企 (原料供应)
    print("  生成牧场 -> 乳企 边...")
    pastures = nodes_by_type.get("牧场", [])
    dairies = nodes_by_type.get("乳企", [])
    
    for dairy in dairies:
        # 每个乳企连接 2-5 个牧场
        num_sources = random.randint(2, 5)
        selected_pastures = random.sample(pastures, min(num_sources, len(pastures)))
        
        for pasture in selected_pastures:
            edge = create_edge(
                edge_index, pasture, dairy, "raw_material",
                {"cold_chain_maintained": True, "frequency_monthly": random.randint(10, 30)}
            )
            edges.append(edge)
            edge_index += 1
    
    # 2. 乳企 -> 物流 (运输)
    print("  生成乳企 -> 物流 边...")
    logistics = nodes_by_type.get("物流", [])
    
    for dairy in dairies:
        num_logistics = random.randint(1, 3)
        selected = random.sample(logistics, min(num_logistics, len(logistics)))
        
        for log in selected:
            edge = create_edge(
                edge_index, dairy, log, "transport",
                {"cold_chain_maintained": True, "frequency_monthly": random.randint(20, 50)}
            )
            edges.append(edge)
            edge_index += 1
    
    # 3. 物流 -> 仓储 (仓储服务)
    print("  生成物流 -> 仓储 边...")
    warehouses = nodes_by_type.get("仓储", [])
    
    for log in logistics:
        num_warehouses = random.randint(1, 4)
        selected = random.sample(warehouses, min(num_warehouses, len(warehouses)))
        
        for wh in selected:
            edge = create_edge(
                edge_index, log, wh, "storage",
                {"cold_chain_maintained": True, "frequency_monthly": random.randint(30, 80)}
            )
            edges.append(edge)
            edge_index += 1
    
    # 4. 仓储 -> 零售 (销售)
    print("  生成仓储 -> 零售 边...")
    retailers = nodes_by_type.get("零售", [])
    
    for wh in warehouses:
        num_retailers = random.randint(2, 8)
        selected = random.sample(retailers, min(num_retailers, len(retailers)))
        
        for retail in selected:
            edge = create_edge(
                edge_index, wh, retail, "sale",
                {"cold_chain_maintained": random.choices([True, False], weights=[0.85, 0.15])[0],
                 "frequency_monthly": random.randint(10, 40)}
            )
            edges.append(edge)
            edge_index += 1
    
    # 5. 乳企 -> 乳企 (供应/调拨)
    print("  生成乳企 -> 乳企 边...")
    for dairy in dairies:
        # 30% 概率有调拨关系
        if random.random() < 0.3:
            other_dairies = [d for d in dairies if d["enterprise_id"] != dairy["enterprise_id"]]
            if other_dairies:
                target = random.choice(other_dairies)
                edge = create_edge(
                    edge_index, dairy, target, "supply",
                    {"frequency_monthly": random.randint(5, 20)}
                )
                edges.append(edge)
                edge_index += 1
    
    # 6. 牧场 -> 饲料 (饲料供应)
    print("  生成牧场 -> 饲料 边...")
    feeds = nodes_by_type.get("饲料", [])
    
    for pasture in pastures:
        if feeds and random.random() < 0.7:
            feed = random.choice(feeds)
            edge = create_edge(
                edge_index, feed, pasture, "feed_supply",
                {"cold_chain_maintained": False, "frequency_monthly": random.randint(2, 8)}
            )
            edges.append(edge)
            edge_index += 1
    
    # 7. 各类型 -> 质检 (质检服务)
    print("  生成 -> 质检 边...")
    testers = nodes_by_type.get("质检", [])
    
    if testers:
        for node_type, type_nodes in nodes_by_type.items():
            if node_type == "质检":
                continue
            for node in type_nodes:
                # 20% 概率有质检关系
                if random.random() < 0.2 and testers:
                    tester = random.choice(testers)
                    edge = create_edge(
                        edge_index, node, tester, "inspection",
                        {"frequency_monthly": random.randint(1, 4)}
                    )
                    edges.append(edge)
                    edge_index += 1
    
    # 8. 跨境/区域调拨边 (增加多样性)
    print("  生成跨区域边...")
    for _ in range(50):
        # 随机选择两种不同类型
        type1, type2 = random.sample(list(nodes_by_type.keys()), 2)
        if nodes_by_type[type1] and nodes_by_type[type2]:
            src = random.choice(nodes_by_type[type1])
            tgt = random.choice(nodes_by_type[type2])
            
            # 检查是否已存在边
            exists = any(
                e["source_id"] == src["enterprise_id"] and e["target_id"] == tgt["enterprise_id"]
                for e in edges
            )
            
            if not exists:
                edge_type = random.choice(EDGE_TYPES)
                edge = create_edge(
                    edge_index, src, tgt, edge_type,
                    {"frequency_monthly": random.randint(5, 20)}
                )
                edges.append(edge)
                edge_index += 1
    
    return edges

def create_edge(edge_index: int, source: Dict, target: Dict, edge_type: str, extra_attrs: Dict = None) -> Dict:
    """创建单条边"""
    edge = {
        "edge_id": f"EDGE-{edge_index:06d}",
        "data_source": "v2_simulation",
        "edge_type": edge_type,
        "source_id": source["enterprise_id"],
        "source_type": source["node_type"],
        "target_id": target["enterprise_id"],
        "target_type": target["node_type"],
        "start_date": generate_date(2020, 2022),
        "end_date": "",
        "weight": round(random.uniform(0.3, 1.0), 2),
    }
    
    # 添加类型特定属性
    if extra_attrs:
        edge.update(extra_attrs)
    
    if edge_type in ["transport", "storage"]:
        edge["transport_distance_km"] = round(random.uniform(10, 500), 1)
        edge["transport_duration_hours"] = round(random.uniform(0.5, 12), 1)
    
    if edge_type in ["raw_material", "supply"]:
        edge["transaction_volume"] = round(random.uniform(10, 100), 2)
    
    return edge

def generate_inspection_records(nodes: List[Dict], count: int = 2000) -> List[Dict]:
    """生成抽检记录"""
    records = []
    
    inspection_results = ["合格", "不合格", "待定"]
    result_weights = [0.75, 0.20, 0.05]
    
    unqualified_items_list = [
        "菌落总数超标", "大肠杆菌群超标", "三聚氰胺检出", "防腐剂超标",
        "甜蜜素检出", "标签不合格", "脂肪含量不足", "蛋白质含量不足",
        "感官指标不合格", "重金属超标", "兽药残留超标"
    ]
    
    for i in range(count):
        node = random.choice(nodes)
        
        result = random.choices(inspection_results, weights=result_weights)[0]
        unqualified_items = []
        
        if result == "不合格":
            num_issues = random.randint(1, 3)
            unqualified_items = random.sample(unqualified_items_list, min(num_issues, len(unqualified_items_list)))
        
        record = {
            "record_id": f"INS-{i+1:06d}",
            "enterprise_id": node["enterprise_id"],
            "enterprise_name": node["enterprise_name"],
            "node_type": node["node_type"],
            "inspection_date": generate_date(2020, 2024),
            "inspection_type": random.choice(["定期", "专项", "突击", "投诉举报"]),
            "inspection_authority": random.choice(["上海市监局", "江苏省监局", "浙江省监局", "总局"]),
            "result": result,
            "unqualified_items": "|".join(unqualified_items) if unqualified_items else "",
            "sample_count": random.randint(1, 10),
            "violation_count": len(unqualified_items) if unqualified_items else 0,
        }
        records.append(record)
    
    return records

def generate_regulatory_events(nodes: List[Dict], count: int = 300) -> List[Dict]:
    """生成监管事件"""
    events = []
    
    event_types = [
        "行政处罚", "责令整改", "暂停生产", "吊销许可证", 
        "召回产品", "警告", "罚款", "没收违法所得"
    ]
    
    for i in range(count):
        node = random.choice(nodes)
        
        event = {
            "event_id": f"EVT-{i+1:05d}",
            "enterprise_id": node["enterprise_id"],
            "enterprise_name": node["enterprise_name"],
            "node_type": node["node_type"],
            "event_date": generate_date(2019, 2024),
            "event_type": random.choice(event_types),
            "authority": random.choice(["上海市监局", "江苏省监局", "浙江省监局", "总局"]),
            "description": f"因{random.choice(['产品质量问题', '违规生产', '许可证过期', '卫生不达标'])}被监管处理",
            "severity": random.choice(["轻微", "一般", "严重"]),
            "penalty_amount": round(random.uniform(0, 50), 2) if "罚款" in event_types else 0,
        }
        events.append(event)
    
    return events

def save_data(nodes: List[Dict], edges: List[Dict], inspections: List[Dict], events: List[Dict]):
    """保存所有数据到文件"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. 企业主数据
    print(f"\n保存企业数据到 {OUTPUT_DIR}/enterprises.csv...")
    fieldnames = [
        "enterprise_id", "enterprise_name", "data_source", "address",
        "credit_rating", "enterprise_type", "enterprise_type_detail",
        "establishment_date", "haccp_certified", "iso22000_certified",
        "historical_violation_count", "inspection_count", "latitude", "longitude",
        "license_no", "main_products", "node_type", "production_capacity_daily",
        "supervision_freq", "base_risk_score", "actual_risk_score", "risk_level"
    ]
    
    with open(OUTPUT_DIR / "enterprises.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for node in nodes:
            row = {k: node.get(k, "") for k in fieldnames}
            # 处理布尔值
            row["haccp_certified"] = "True" if row["haccp_certified"] else "False"
            row["iso22000_certified"] = "True" if row["iso22000_certified"] else "False"
            writer.writerow(row)
    
    # 2. 供应链边
    print(f"保存供应链边到 {OUTPUT_DIR}/supply_edges.csv...")
    edge_fields = [
        "edge_id", "data_source", "edge_type", "source_id", "source_type",
        "target_id", "target_type", "start_date", "end_date", "weight",
        "cold_chain_maintained", "frequency_monthly", "transaction_volume",
        "transport_distance_km", "transport_duration_hours"
    ]
    
    with open(OUTPUT_DIR / "supply_edges.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=edge_fields)
        writer.writeheader()
        
        for edge in edges:
            row = {k: edge.get(k, "") for k in edge_fields}
            if "cold_chain_maintained" in row:
                row["cold_chain_maintained"] = "True" if row["cold_chain_maintained"] else "False"
            writer.writerow(row)
    
    # 3. 抽检记录
    print(f"保存抽检记录到 {OUTPUT_DIR}/inspection_records.csv...")
    ins_fields = [
        "record_id", "enterprise_id", "enterprise_name", "node_type",
        "inspection_date", "inspection_type", "inspection_authority",
        "result", "unqualified_items", "sample_count", "violation_count"
    ]
    
    with open(OUTPUT_DIR / "inspection_records.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ins_fields)
        writer.writeheader()
        writer.writerows(inspections)
    
    # 4. 监管事件
    print(f"保存监管事件到 {OUTPUT_DIR}/regulatory_events.csv...")
    evt_fields = [
        "event_id", "enterprise_id", "enterprise_name", "node_type",
        "event_date", "event_type", "authority", "description",
        "severity", "penalty_amount"
    ]
    
    with open(OUTPUT_DIR / "regulatory_events.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=evt_fields)
        writer.writeheader()
        writer.writerows(events)
    
    # 5. 风险因子详情 (JSON)
    print(f"保存风险因子到 {OUTPUT_DIR}/risk_factors.json...")
    risk_data = {}
    for node in nodes:
        risk_data[node["enterprise_id"]] = {
            "enterprise_name": node["enterprise_name"],
            "risk_level": node["risk_level"],
            "actual_risk_score": node["actual_risk_score"],
            "risk_factors": node.get("risk_factors", [])
        }
    
    with open(OUTPUT_DIR / "risk_factors.json", "w", encoding="utf-8") as f:
        json.dump(risk_data, f, ensure_ascii=False, indent=2)
    
    # 6. 数据摘要
    print(f"保存数据摘要到 {OUTPUT_DIR}/data_summary.json...")
    summary = {
        "generated_at": datetime.now().isoformat(),
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "total_inspection_records": len(inspections),
        "total_regulatory_events": len(events),
        "node_type_counts": {},
        "scale_counts": {},
        "risk_level_counts": {"low": 0, "medium": 0, "high": 0},
    }
    
    for node in nodes:
        nt = node["node_type"]
        summary["node_type_counts"][nt] = summary["node_type_counts"].get(nt, 0) + 1
        
        st = node["enterprise_type"]
        summary["scale_counts"][st] = summary["scale_counts"].get(st, 0) + 1
        
        rl = node["risk_level"]
        summary["risk_level_counts"][rl] += 1
    
    with open(OUTPUT_DIR / "data_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    return summary

# ============ 主函数 ============

def main():
    print("=" * 60)
    print("乳制品供应链大规模数据生成器 V2")
    print(f"目标节点数: {TOTAL_NODES}")
    print("=" * 60)
    
    # 设置随机种子以保证可复现
    random.seed(42)
    
    # 1. 生成节点
    print("\n[1/5] 生成节点数据...")
    nodes, node_counts = generate_nodes()
    print(f"  完成! 共生成 {len(nodes)} 个节点")
    for nt, cnt in node_counts.items():
        print(f"    - {nt}: {cnt}")
    
    # 2. 生成边
    print("\n[2/5] 生成供应链边关系...")
    edges = generate_edges(nodes)
    print(f"  完成! 共生成 {len(edges)} 条边")
    
    # 3. 生成抽检记录
    print("\n[3/5] 生成抽检记录...")
    inspections = generate_inspection_records(nodes)
    print(f"  完成! 共生成 {len(inspections)} 条记录")
    
    # 4. 生成监管事件
    print("\n[4/5] 生成监管事件...")
    events = generate_regulatory_events(nodes)
    print(f"  完成! 共生成 {len(events)} 条事件")
    
    # 5. 保存数据
    print("\n[5/5] 保存数据文件...")
    summary = save_data(nodes, edges, inspections, events)
    
    print("\n" + "=" * 60)
    print("数据生成完成!")
    print("=" * 60)
    print(f"\n数据摘要:")
    print(f"  - 总节点数: {summary['total_nodes']}")
    print(f"  - 总边数: {summary['total_edges']}")
    print(f"  - 抽检记录: {summary['total_inspection_records']}")
    print(f"  - 监管事件: {summary['total_regulatory_events']}")
    print(f"\n风险等级分布:")
    for level, count in summary['risk_level_counts'].items():
        pct = count / summary['total_nodes'] * 100
        print(f"  - {level}: {count} ({pct:.1f}%)")
    print(f"\n数据保存位置: {OUTPUT_DIR}")
    
    return summary

if __name__ == "__main__":
    main()
