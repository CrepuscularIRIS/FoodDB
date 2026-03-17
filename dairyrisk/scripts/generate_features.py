#!/usr/bin/env python3
"""
特征工程脚本 - 为乳制品供应链节点生成64维特征
"""

import json
import csv
import hashlib
from pathlib import Path
from typing import Dict, List, Any
import numpy as np

# 项目路径
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "v2"
OUTPUT_DIR = DATA_DIR

# 特征维度
FEATURE_DIM = 64


def load_enterprise_nodes(csv_path: Path) -> List[Dict[str, Any]]:
    """加载企业节点数据"""
    nodes = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            nodes.append(row)
    return nodes


def load_supply_edges(csv_path: Path) -> List[Dict[str, Any]]:
    """加载供应链边数据"""
    edges = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            edges.append(row)
    return edges


def encode_node_type(node_type: str) -> List[float]:
    """节点类型编码 (5维) - 独热编码"""
    types = ['牧场', '乳企', '物流', '仓储', '零售']
    encoding = [0.0] * 5
    if node_type in types:
        encoding[types.index(node_type)] = 1.0
    return encoding


def encode_scale(scale: str) -> List[float]:
    """规模编码 (4维) - 大型/中型/小型/微型"""
    scales = ['大型', '中型', '小型', '微型']
    encoding = [0.0] * 4
    if scale in scales:
        encoding[scales.index(scale)] = 1.0
    return encoding


def encode_credit_rating(rating: str) -> float:
    """信用评级编码 (1维) - A/B/C/D -> 1.0/0.67/0.33/0.0"""
    rating_map = {'A': 1.0, 'B': 0.67, 'C': 0.33, 'D': 0.0}
    return rating_map.get(rating, 0.5)


def encode_region(region: str) -> List[float]:
    """地区编码 (8维) - 基于省份哈希"""
    # 简化的地区编码
    regions = ['安徽', '四川', '河北', '内蒙古', '黑龙江', '山东', '江苏', '河南']
    encoding = [0.0] * 8
    
    # 尝试精确匹配
    if region in regions:
        encoding[regions.index(region)] = 1.0
    else:
        # 哈希映射到其他省份
        hash_val = int(hashlib.md5(region.encode()).hexdigest(), 16) % 8
        encoding[hash_val] = 0.5
    
    return encoding


def compute_employees_feature(employees: str) -> float:
    """员工数特征 (1维) - 归一化"""
    try:
        emp = float(employees)
        # 使用对数归一化 (假设最大10000人)
        return np.log1p(emp) / np.log1p(10000)
    except:
        return 0.5


def compute_revenue_feature(revenue: str) -> float:
    """年产值特征 (1维) - 归一化"""
    try:
        rev = float(revenue)
        # 使用对数归一化 (假设最大10亿)
        return np.log1p(rev) / np.log1p(1e9)
    except:
        return 0.5


def compute_violations_feature(violations: str) -> float:
    """历史违规特征 (1维) - 归一化"""
    try:
        viol = int(violations)
        # 归一化到 0-1，违规越多越接近 1.0
        return min(viol / 10.0, 1.0)
    except:
        return 0.0


def compute_risk_features(node: Dict[str, Any]) -> List[float]:
    """风险特征 (8维)"""
    features = []
    
    # 1. 风险概率 (已有)
    try:
        risk_prob = float(node.get('risk_probability', 0.5))
    except:
        risk_prob = 0.5
    features.append(risk_prob)
    
    # 2. 风险等级编码
    risk_level_map = {'high': 1.0, 'medium': 0.5, 'low': 0.0}
    risk_level = risk_level_map.get(node.get('risk_level', 'medium'), 0.5)
    features.append(risk_level)
    
    # 3. 置信度
    try:
        confidence = float(node.get('confidence', 0.5))
    except:
        confidence = 0.5
    features.append(confidence)
    
    # 4. 历史违规次数 (归一化)
    features.append(compute_violations_feature(node.get('historical_violations', '0')))
    
    # 5. 抽检不合格率 (基于风险概率估算)
    features.append(risk_prob * 0.8)
    
    # 6. 监管频次 (基于规模估算)
    scale_map = {'大型': 0.3, '中型': 0.5, '小型': 0.7, '微型': 0.9}
    features.append(scale_map.get(node.get('scale', '中型'), 0.5))
    
    # 7. HACCP认证 (基于名称哈希估算)
    name_hash = int(hashlib.md5(node.get('enterprise_name', '').encode()).hexdigest(), 16) % 10
    features.append(1.0 if name_hash < 3 else 0.0)  # 30%概率有HACCP
    
    # 8. ISO22000认证
    features.append(1.0 if name_hash < 2 else 0.0)  # 20%概率有ISO
    
    return features


def compute_temporal_features(node: Dict[str, Any]) -> List[float]:
    """时序特征 (8维)"""
    features = []
    
    # 1. 经营时长 (基于名称中的编号估算)
    node_id = node.get('node_id', '')
    try:
        # 从 ID 中提取编号，如 ENT-牧-0001 -> 1
        num = int(node_id.split('-')[-1]) if node_id else 1
        # 经营时长: 编号越小，经营时间越长
        years = (800 - num) / 800 * 20 + 1  # 1-21年
    except:
        years = 10
    features.append(min(years / 20.0, 1.0))
    
    # 2. 活跃度 (基于风险概率的反向估算)
    try:
        risk_prob = float(node.get('risk_probability', 0.5))
    except:
        risk_prob = 0.5
    features.append(1.0 - risk_prob * 0.5)
    
    # 3. 最近监管评分 (模拟)
    features.append(1.0 - risk_prob * 0.3)
    
    # 4. 违规趋势 (基于历史违规)
    try:
        violations = int(node.get('historical_violations', 0))
        features.append(min(violations / 5.0, 1.0))
    except:
        features.append(0.0)
    
    # 5. 投诉趋势 (模拟)
    name_hash = int(hashlib.md5(node.get('enterprise_name', '').encode()).hexdigest(), 16) % 100
    features.append(name_hash / 100.0)
    
    # 6. 产品多样性
    products = node.get('products', '')
    product_count = len(products.split(',')) if products else 1
    features.append(min(product_count / 5.0, 1.0))
    
    # 7. 地区风险水平
    region = node.get('region', '')
    region_risk = {'安徽': 0.4, '四川': 0.5, '河北': 0.6, '内蒙古': 0.3, 
                   '黑龙江': 0.35, '山东': 0.45, '江苏': 0.4, '河南': 0.55}
    features.append(region_risk.get(region, 0.5))
    
    # 8. 供应链位置风险
    node_type = node.get('node_type', '')
    type_risk = {'牧场': 0.6, '乳企': 0.5, '物流': 0.4, '仓储': 0.35, '零售': 0.3}
    features.append(type_risk.get(node_type, 0.5))
    
    return features


def build_graph(edges: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """构建邻接表"""
    graph = {}
    for edge in edges:
        source = edge.get('source_id')
        target = edge.get('target_id')
        
        if source not in graph:
            graph[source] = {'in': set(), 'out': set()}
        if target not in graph:
            graph[target] = {'in': set(), 'out': set()}
        
        graph[source]['out'].add(target)
        graph[target]['in'].add(source)
    
    return graph


def compute_graph_features(nodes: List[Dict], edges: List[Dict]) -> Dict[str, Dict[str, float]]:
    """计算图结构特征"""
    graph = build_graph(edges)
    
    # 计算 PageRank (简化版本)
    node_list = list(graph.keys())
    n = len(node_list)
    pagerank = {node: 1.0 / n for node in node_list}
    
    # 迭代计算 PageRank (简化)
    damping = 0.85
    for _ in range(20):
        new_pagerank = {}
        for node in node_list:
            rank = (1 - damping) / n
            # 聚合入边的 PageRank
            in_neighbors = graph[node]['in']
            if in_neighbors:
                rank += damping * sum(pagerank.get(neighbor, 0) / len(graph[neighbor]['out']) 
                                     for neighbor in in_neighbors if neighbor in graph)
            new_pagerank[node] = rank
        pagerank = new_pagerank
    
    # 归一化 PageRank
    max_pr = max(pagerank.values()) if pagerank else 1
    pagerank = {k: v / max_pr for k, v in pagerank.items()}
    
    # 计算度中心性
    degree_centrality = {}
    for node in node_list:
        in_deg = len(graph[node]['in'])
        out_deg = len(graph[node]['out'])
        degree_centrality[node] = (in_deg + out_deg) / (2 * n)
    
    # 归一化
    max_degree = max(degree_centrality.values()) if degree_centrality else 1
    degree_centrality = {k: v / max_degree for k, v in degree_centrality.items()}
    
    # 计算入度和出度 (归一化)
    max_in = max(len(graph[n]['in']) for n in node_list) if node_list else 1
    max_out = max(len(graph[n]['out']) for n in node_list) if node_list else 1
    
    in_degree = {n: len(graph[n]['in']) / max_in for n in node_list}
    out_degree = {n: len(graph[n]['out']) / max_out for n in node_list}
    
    # 计算聚类系数 (简化)
    clustering = {}
    for node in node_list:
        neighbors = graph[node]['in'] | graph[node]['out']
        k = len(neighbors)
        if k < 2:
            clustering[node] = 0.0
        else:
            # 统计邻居之间的边数
            edges_between = 0
            for n1 in neighbors:
                for n2 in neighbors:
                    if n1 != n2:
                        if n2 in graph[n1]['out'] or n1 in graph[n1]['out']:
                            edges_between += 1
            clustering[node] = edges_between / (k * (k - 1)) if k > 1 else 0.0
    
    # 介数中心性 (简化采样)
    betweenness = {n: degree_centrality.get(n, 0) * 0.5 for n in node_list}
    
    # 特征向量中心性 (简化)
    eigenvector = {n: pagerank.get(n, 0) for n in node_list}
    
    return {
        'pagerank': pagerank,
        'degree_centrality': degree_centrality,
        'in_degree': in_degree,
        'out_degree': out_degree,
        'clustering': clustering,
        'betweenness': betweenness,
        'eigenvector': eigenvector
    }


def generate_node_features(nodes: List[Dict], edges: List[Dict]) -> Dict[str, Any]:
    """为所有节点生成64维特征"""
    
    # 计算图特征
    graph_features = compute_graph_features(nodes, edges)
    
    node_features = {}
    for node in nodes:
        node_id = node.get('node_id', '')
        features = []
        
        # ========== 基础属性 (16维) ==========
        # 1. 节点类型编码 (5维)
        features.extend(encode_node_type(node.get('node_type', '')))
        
        # 2. 规模编码 (4维)
        features.extend(encode_scale(node.get('scale', '')))
        
        # 3. 信用评级 (1维)
        features.append(encode_credit_rating(node.get('credit_rating', 'C')))
        
        # 4. 地区编码 (8维) - 实际上只需要前6维
        region_enc = encode_region(node.get('region', ''))
        features.extend(region_enc[:6])  # 取前6维
        
        # ========== 规模特征 (4维) ==========
        # 5. 员工数 (1维)
        features.append(compute_employees_feature(node.get('employees', '0')))
        
        # 6. 年产值 (1维)
        features.append(compute_revenue_feature(node.get('annual_revenue', '0')))
        
        # 7. 日产能 (模拟，基于年产值)
        try:
            rev = float(node.get('annual_revenue', 0))
            daily_cap = rev / 365
            features.append(np.log1p(daily_cap) / np.log1p(1e8))
        except:
            features.append(0.5)
        
        # 8. 交易量 (模拟)
        name_hash = int(hashlib.md5(node.get('enterprise_name', '').encode()).hexdigest(), 16) % 1000
        features.append(name_hash / 1000.0)
        
        # ========== 风险特征 (8维 - 补充到16维) ==========
        risk_feats = compute_risk_features(node)
        features.extend(risk_feats[:8])
        
        # 填充到16维
        features.extend([0.5] * 8)
        
        # ========== 图结构特征 (16维) ==========
        # 1. 入度
        features.append(graph_features['in_degree'].get(node_id, 0.0))
        
        # 2. 出度
        features.append(graph_features['out_degree'].get(node_id, 0.0))
        
        # 3. PageRank
        features.append(graph_features['pagerank'].get(node_id, 0.0))
        
        # 4. 聚类系数
        features.append(graph_features['clustering'].get(node_id, 0.0))
        
        # 5. 介数中心性
        features.append(graph_features['betweenness'].get(node_id, 0.0))
        
        # 6. 特征向量中心性
        features.append(graph_features['eigenvector'].get(node_id, 0.0))
        
        # 7. 度中心性
        features.append(graph_features['degree_centrality'].get(node_id, 0.0))
        
        # 8. 填充
        for _ in range(8):
            features.append(0.5)
        
        # ========== 时序特征 (8维) ==========
        temporal_feats = compute_temporal_features(node)
        features.extend(temporal_feats)
        
        # 确保特征维度为64
        if len(features) != FEATURE_DIM:
            print(f"警告: 节点 {node_id} 特征维度为 {len(features)}，调整为 {FEATURE_DIM}")
            if len(features) < FEATURE_DIM:
                features.extend([0.0] * (FEATURE_DIM - len(features)))
            else:
                features = features[:FEATURE_DIM]
        
        node_features[node_id] = {
            'features': features,
            'node_type': node.get('node_type', ''),
            'enterprise_name': node.get('enterprise_name', ''),
            'scale': node.get('scale', ''),
            'region': node.get('region', ''),
            'risk_probability': float(node.get('risk_probability', 0.5))
        }
    
    return node_features


def main():
    """主函数"""
    print("=" * 60)
    print("乳制品供应链节点特征生成")
    print("=" * 60)
    
    # 加载数据
    nodes_path = DATA_DIR / "enterprise_nodes.csv"
    edges_path = DATA_DIR / "supply_edges.csv"
    
    print(f"\n1. 加载企业节点数据: {nodes_path}")
    nodes = load_enterprise_nodes(nodes_path)
    print(f"   - 加载了 {len(nodes)} 个企业节点")
    
    print(f"\n2. 加载供应链边数据: {edges_path}")
    edges = load_supply_edges(edges_path)
    print(f"   - 加载了 {len(edges)} 条供应链边")
    
    # 生成特征
    print(f"\n3. 生成64维节点特征...")
    node_features = generate_node_features(nodes, edges)
    print(f"   - 生成了 {len(node_features)} 个节点的特征")
    
    # 输出到JSON
    output_path = OUTPUT_DIR / "node_features_64d.json"
    print(f"\n4. 保存特征到: {output_path}")
    
    # 转换为可JSON序列化的格式
    output_data = {
        'feature_dim': FEATURE_DIM,
        'node_count': len(node_features),
        'features': {k: {
            'features': [float(x) for x in v['features']],
            'node_type': v['node_type'],
            'enterprise_name': v['enterprise_name'],
            'scale': v['scale'],
            'region': v['region'],
            'risk_probability': v['risk_probability']
        } for k, v in node_features.items()}
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ 特征生成完成!")
    print(f"  - 特征维度: {FEATURE_DIM}")
    print(f"  - 节点数量: {len(node_features)}")
    print(f"  - 输出文件: {output_path}")
    
    return FEATURE_DIM


if __name__ == "__main__":
    main()
