#!/usr/bin/env python3
"""
图特征计算脚本 - 使用 NetworkX 计算图结构特征
"""

import json
import csv
from pathlib import Path
from typing import Dict, List, Any
import networkx as nx

# 项目路径
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "v2"
OUTPUT_DIR = DATA_DIR


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


def build_networkx_graph(edges: List[Dict[str, Any]]) -> nx.DiGraph:
    """构建 NetworkX 有向图"""
    G = nx.DiGraph()
    
    # 添加边
    for edge in edges:
        source = edge.get('source_id')
        target = edge.get('target_id')
        weight = float(edge.get('weight', 1.0))
        
        G.add_edge(source, target, 
                   weight=weight,
                   distance_km=float(edge.get('distance_km', 0)),
                   transport_time_hours=float(edge.get('transport_time_hours', 0)),
                   cost_per_unit=float(edge.get('cost_per_unit', 0)))
    
    return G


def compute_graph_statistics(G: nx.DiGraph) -> Dict[str, Any]:
    """计算图的整体统计信息"""
    stats = {
        'node_count': G.number_of_nodes(),
        'edge_count': G.number_of_edges(),
        'density': nx.density(G),
        'is_directed': G.is_directed(),
    }
    
    # 转换为无向图计算连通性
    undirected = G.to_undirected()
    stats['is_connected'] = nx.is_connected(undirected)
    if nx.is_connected(undirected):
        stats['diameter'] = nx.diameter(undirected)
        stats['avg_path_length'] = nx.average_shortest_path_length(undirected)
    else:
        # 获取最大连通分量
        largest_cc = max(nx.connected_components(undirected), key=len)
        subgraph = undirected.subgraph(largest_cc)
        stats['largest_cc_size'] = len(largest_cc)
        stats['diameter'] = nx.diameter(subgraph)
        stats['avg_path_length'] = nx.average_shortest_path_length(subgraph)
    
    # 度统计
    in_degrees = [d for n, d in G.in_degree()]
    out_degrees = [d for n, d in G.out_degree()]
    stats['avg_in_degree'] = sum(in_degrees) / len(in_degrees) if in_degrees else 0
    stats['avg_out_degree'] = sum(out_degrees) / len(out_degrees) if out_degrees else 0
    stats['max_in_degree'] = max(in_degrees) if in_degrees else 0
    stats['max_out_degree'] = max(out_degrees) if out_degrees else 0
    
    # 平均聚类系数
    stats['avg_clustering'] = nx.average_clustering(undirected)
    
    return stats


def compute_node_centrality(G: nx.DiGraph) -> Dict[str, Dict[str, float]]:
    """计算节点中心性指标"""
    print("  - 计算度中心性...")
    degree_centrality = nx.degree_centrality(G)
    
    print("  - 计算入度中心性...")
    in_degree_centrality = nx.in_degree_centrality(G)
    
    print("  - 计算出度中心性...")
    out_degree_centrality = nx.out_degree_centrality(G)
    
    print("  - 计算PageRank...")
    try:
        pagerank = nx.pagerank(G, alpha=0.85)
    except:
        pagerank = {n: 1.0/G.number_of_nodes() for n in G.nodes()}
    
    print("  - 计算介数中心性...")
    # 对于大型图使用近似算法
    if G.number_of_nodes() > 500:
        betweenness = nx.betweenness_centrality(G, k=min(100, G.number_of_nodes()))
    else:
        betweenness = nx.betweenness_centrality(G)
    
    print("  - 计算接近中心性...")
    # 只对连通分量计算
    try:
        closeness = nx.closeness_centrality(G)
    except:
        closeness = {n: 0.0 for n in G.nodes()}
    
    print("  - 计算特征向量中心性...")
    try:
        eigenvector = nx.eigenvector_centrality(G, max_iter=1000)
    except:
        eigenvector = {n: 0.0 for n in G.nodes()}
    
    # 组装结果
    node_features = {}
    for node in G.nodes():
        node_features[node] = {
            'degree_centrality': degree_centrality.get(node, 0.0),
            'in_degree_centrality': in_degree_centrality.get(node, 0.0),
            'out_degree_centrality': out_degree_centrality.get(node, 0.0),
            'pagerank': pagerank.get(node, 0.0),
            'betweenness_centrality': betweenness.get(node, 0.0),
            'closeness_centrality': closeness.get(node, 0.0),
            'eigenvector_centrality': eigenvector.get(node, 0.0),
            'in_degree': G.in_degree(node),
            'out_degree': G.out_degree(node),
        }
    
    return node_features


def compute_structural_features(G: nx.DiGraph) -> Dict[str, Dict[str, Any]]:
    """计算节点的结构特征"""
    print("  - 计算聚类系数...")
    undirected = G.to_undirected()
    clustering = nx.clustering(undirected)
    
    print("  - 计算邻居数量...")
    neighbor_counts = {}
    for node in G.nodes():
        neighbors = list(G.predecessors(node)) + list(G.successors(node))
        neighbor_counts[node] = len(set(neighbors))
    
    print("  - 识别关键节点（高介数中心性）...")
    top_betweenness = sorted(
        nx.betweenness_centrality(G).items(),
        key=lambda x: x[1], reverse=True
    )[:10]
    
    print("  - 识别核心节点（高PageRank）...")
    top_pagerank = sorted(
        nx.pagerank(G).items(),
        key=lambda x: x[1], reverse=True
    )[:10]
    
    # 组装结构特征
    structural_features = {}
    for node in G.nodes():
        structural_features[node] = {
            'clustering_coefficient': clustering.get(node, 0.0),
            'neighbor_count': neighbor_counts.get(node, 0),
            'is_top_betweenness': node in [n for n, _ in top_betweenness],
            'is_top_pagerank': node in [n for n, _ in top_pagerank],
        }
    
    return structural_features


def main():
    """主函数"""
    print("=" * 60)
    print("乳制品供应链图特征计算")
    print("=" * 60)
    
    # 加载数据
    nodes_path = DATA_DIR / "enterprise_nodes.csv"
    edges_path = DATA_DIR / "supply_edges.csv"
    
    print(f"\n1. 加载数据...")
    nodes = load_enterprise_nodes(nodes_path)
    edges = load_supply_edges(edges_path)
    print(f"   - 企业节点: {len(nodes)}")
    print(f"   - 供应链边: {len(edges)}")
    
    # 构建 NetworkX 图
    print(f"\n2. 构建 NetworkX 图...")
    G = build_networkx_graph(edges)
    print(f"   - 节点数: {G.number_of_nodes()}")
    print(f"   - 边数: {G.number_of_edges()}")
    
    # 计算图统计
    print(f"\n3. 计算图统计信息...")
    stats = compute_graph_statistics(G)
    print(f"   - 节点数: {stats['node_count']}")
    print(f"   - 边数: {stats['edge_count']}")
    print(f"   - 图密度: {stats['density']:.4f}")
    print(f"   - 平均聚类系数: {stats['avg_clustering']:.4f}")
    print(f"   - 平均路径长度: {stats['avg_path_length']:.2f}")
    
    # 计算节点中心性
    print(f"\n4. 计算节点中心性特征...")
    node_centrality = compute_node_centrality(G)
    print(f"   - 计算了 {len(node_centrality)} 个节点的中心性")
    
    # 计算结构特征
    print(f"\n5. 计算节点结构特征...")
    structural_features = compute_structural_features(G)
    
    # 合并所有特征
    print(f"\n6. 合并特征...")
    all_features = {}
    for node_id in node_centrality.keys():
        all_features[node_id] = {
            **node_centrality.get(node_id, {}),
            **structural_features.get(node_id, {})
        }
    
    # 保存图统计
    stats_output = OUTPUT_DIR / "graph_statistics.json"
    print(f"\n7. 保存图统计到: {stats_output}")
    with open(stats_output, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    # 保存节点特征
    features_output = OUTPUT_DIR / "graph_node_features.json"
    print(f"   保存节点特征到: {features_output}")
    with open(features_output, 'w', encoding='utf-8') as f:
        json.dump({
            'feature_count': len(all_features),
            'features': all_features
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ 图特征计算完成!")
    print(f"  - 图统计: {stats_output}")
    print(f"  - 节点特征: {features_output}")
    
    return stats, all_features


if __name__ == "__main__":
    main()
