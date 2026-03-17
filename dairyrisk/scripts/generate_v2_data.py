#!/usr/bin/env python3
"""
乳制品供应链 V2 大规模数据生成脚本
生成 500-1000 节点用于模型训练
"""

import csv
import random
import json
from pathlib import Path
from datetime import datetime, timedelta

# 配置
NUM_NODES = 800  # 可调整 500-1000
NUM_EDGES_FACTOR = 3  # 边约为节点的3倍

# 节点类型分布
NODE_TYPE_DIST = {
    '牧场': 0.15,
    '乳企': 0.10,
    '物流': 0.15,
    '仓储': 0.15,
    '零售': 0.35,
    '质检机构': 0.10,
}

# 企业规模分布
SCALE_DIST = {
    '大型': 0.05,
    '中型': 0.25,
    '小型': 0.70,
}

# 地区
REGIONS = [
    '上海', '江苏', '浙江', '安徽', '山东', '广东', '河南', '四川', '湖北', '河北'
]

# 产品类型
PRODUCTS = {
    '牧场': ['生鲜乳', '原奶'],
    '乳企': ['巴氏杀菌乳', '灭菌乳', '酸奶', '乳粉', '奶油', '奶酪'],
    '物流': ['冷链运输', '常温运输'],
    '仓储': ['冷藏仓储', '冷冻仓储', '常温仓储'],
    '零售': ['超市', '便利店', '电商', '专卖店'],
    '质检机构': ['抽检', '送检', '委托检验'],
}

# 风险因子
RISK_FACTORS = [
    '微生物污染', '化学残留', '添加剂超标', '标签不规范', 
    '冷链断链', '过期销售', '源头污染', '加工卫生',
    '仓储温控', '运输污染', '假冒伪劣', '虚假宣传'
]

def generate_nodes(num_nodes):
    """生成节点数据"""
    nodes = []
    node_ids = {'牧场': [], '乳企': [], '物流': [], '仓储': [], '零售': [], '质检机构': []}
    
    # 按比例分配节点类型
    for node_type, ratio in NODE_TYPE_DIST.items():
        count = int(num_nodes * ratio)
        for i in range(count):
            node_id = f"ENT-{node_type[0]}-{i+1:04d}"
            
            # 企业规模
            scale = random.choices(
                list(SCALE_DIST.keys()), 
                weights=list(SCALE_DIST.values())
            )[0]
            
            # 地区
            region = random.choice(REGIONS)
            
            # 基础风险评分（小型企业风险更高）
            base_risk = {
                '大型': random.uniform(0.1, 0.3),
                '中型': random.uniform(0.2, 0.5),
                '小型': random.uniform(0.4, 0.8),
            }[scale]
            
            # 随机波动
            risk_probability = min(0.99, base_risk + random.uniform(-0.1, 0.1))
            
            # 风险等级
            if risk_probability < 0.3:
                risk_level = 'low'
            elif risk_probability < 0.7:
                risk_level = 'medium'
            else:
                risk_level = 'high'
            
            # 置信度
            confidence = random.uniform(0.7, 0.95)
            
            node = {
                'node_id': node_id,
                'node_type': node_type,
                'enterprise_name': f"{region}{node_type}{i+1}号",
                'scale': scale,
                'region': region,
                'address': f"{region}市{random.choice(['浦东', '浦西', '南山', '福田', '朝阳'])}区",
                'license_no': f"SC{random.randint(100000, 999999)}",
                'credit_rating': random.choice(['A', 'B', 'C', 'D']),
                'employees': random.randint(10, 500) if scale == '小型' else random.randint(100, 2000),
                'annual_revenue': random.randint(100, 10000) if scale == '小型' else random.randint(5000, 100000),
                'products': ','.join(random.sample(PRODUCTS[node_type], min(2, len(PRODUCTS[node_type])))),
                'risk_probability': round(risk_probability, 4),
                'risk_level': risk_level,
                'confidence': round(confidence, 4),
                'historical_violations': random.randint(0, 5) if scale == '小型' else random.randint(0, 2),
            }
            nodes.append(node)
            node_ids[node_type].append(node_id)
    
    return nodes, node_ids

def generate_edges(nodes, node_ids, num_edges_factor):
    """生成边数据"""
    edges = []
    edge_id = 1
    
    # 定义边生成规则
    edge_rules = [
        ('牧场', '乳企', 'supply', 0.8),
        ('乳企', '乳企', 'process', 0.3),
        ('乳企', '物流', 'transport', 0.7),
        ('物流', '仓储', 'storage', 0.6),
        ('乳企', '仓储', 'storage', 0.4),
        ('仓储', '零售', 'sale', 0.7),
        ('乳企', '零售', 'sale', 0.5),
        ('物流', '零售', 'sale', 0.3),
        ('乳企', '质检机构', 'inspect', 0.6),
        ('牧场', '质检机构', 'inspect', 0.4),
    ]
    
    # 按规则生成边
    for source_type, target_type, edge_type, prob in edge_rules:
        if source_type in node_ids and target_type in node_ids:
            source_ids = node_ids[source_type]
            target_ids = node_ids[target_type]
            
            for source in source_ids:
                for target in target_ids:
                    if random.random() < prob * num_edges_factor / len(node_ids[target_type]):
                        edge = {
                            'edge_id': f"EDGE-{edge_id:05d}",
                            'source_id': source,
                            'target_id': target,
                            'edge_type': edge_type,
                            'source_type': source_type,
                            'target_type': target_type,
                            'weight': round(random.uniform(0.5, 1.0), 2),
                            'distance_km': random.randint(10, 1000),
                            'transport_time_hours': random.randint(1, 48),
                            'cost_per_unit': round(random.uniform(0.1, 2.0), 2),
                        }
                        edges.append(edge)
                        edge_id += 1
    
    return edges

def main():
    print(f"生成乳制品供应链数据...")
    print(f"目标节点数: {NUM_NODES}")
    
    # 生成目录
    output_dir = Path('data/v2')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成节点
    print("生成节点数据...")
    nodes, node_ids = generate_nodes(NUM_NODES)
    
    # 生成边
    print("生成边数据...")
    edges = generate_edges(nodes, node_ids, NUM_EDGES_FACTOR)
    
    # 保存节点
    nodes_file = output_dir / 'enterprise_nodes.csv'
    with open(nodes_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=nodes[0].keys())
        writer.writeheader()
        writer.writerows(nodes)
    print(f"✓ 节点: {len(nodes)} 个 -> {nodes_file}")
    
    # 保存边
    edges_file = output_dir / 'supply_edges.csv'
    with open(edges_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=edges[0].keys())
        writer.writeheader()
        writer.writerows(edges)
    print(f"✓ 边: {len(edges)} 条 -> {edges_file}")
    
    # 统计
    print("\n=== 数据统计 ===")
    print(f"总节点: {len(nodes)}")
    print(f"总边: {len(edges)}")
    
    # 节点类型统计
    type_counts = {}
    for node in nodes:
        t = node['node_type']
        type_counts[t] = type_counts.get(t, 0) + 1
    print("\n节点类型分布:")
    for t, c in type_counts.items():
        print(f"  {t}: {c}")
    
    # 风险分布
    risk_counts = {'low': 0, 'medium': 0, 'high': 0}
    for node in nodes:
        risk_counts[node['risk_level']] += 1
    print("\n风险等级分布:")
    for r, c in risk_counts.items():
        print(f"  {r}: {c} ({c/len(nodes)*100:.1f}%)")

if __name__ == '__main__':
    main()
