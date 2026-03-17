"""
异构图可视化模块

提供多种图表生成功能：
- 节点类型分布饼图
- 风险分布直方图
- 企业规模与风险关系图
- 供应链网络拓扑可视化
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import rcParams
from typing import Dict, List, Optional, Tuple, Any
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


class GraphVisualizer:
    """图数据可视化器"""
    
    def __init__(self, output_dir: str = 'reports/figures'):
        """
        初始化可视化器
        
        Args:
            output_dir: 图表输出目录
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # 配色方案
        self.colors = {
            'enterprise': '#FF6B6B',
            'raw_material': '#4ECDC4',
            'production_line': '#45B7D1',
            'batch': '#96CEB4',
            'logistics': '#FFEAA7',
            'retail': '#DDA0DD',
            'low_risk': '#2ECC71',
            'medium_risk': '#F39C12',
            'high_risk': '#E74C3C',
        }
        
        # 节点类型中文名
        self.node_type_names = {
            'enterprise': '企业',
            'raw_material': '原料',
            'production_line': '生产线',
            'batch': '批次',
            'logistics': '物流',
            'retail': '零售',
        }
    
    def plot_node_distribution(self, node_stats: Dict[str, Dict], 
                               save_path: Optional[str] = None,
                               figsize: Tuple[int, int] = (12, 6)) -> str:
        """
        绘制节点类型分布饼图
        
        Args:
            node_stats: 节点统计信息
            save_path: 保存路径
            figsize: 图像尺寸
            
        Returns:
            保存的文件路径
        """
        if save_path is None:
            save_path = os.path.join(self.output_dir, 'node_distribution.png')
        
        fig, axes = plt.subplots(1, 2, figsize=figsize)
        
        # 饼图
        labels = []
        sizes = []
        colors = []
        
        for node_type, info in node_stats.items():
            labels.append(self.node_type_names.get(node_type, node_type))
            sizes.append(info['count'])
            colors.append(self.colors.get(node_type, '#808080'))
        
        # 按大小排序
        sorted_data = sorted(zip(sizes, labels, colors), reverse=True)
        sizes, labels, colors = zip(*sorted_data)
        
        wedges, texts, autotexts = axes[0].pie(
            sizes, labels=labels, colors=colors, autopct='%1.1f%%',
            startangle=90, textprops={'fontsize': 10}
        )
        axes[0].set_title('Node Type Distribution', fontsize=14, fontweight='bold')
        
        # 柱状图
        bars = axes[1].bar(range(len(labels)), sizes, color=colors)
        axes[1].set_xticks(range(len(labels)))
        axes[1].set_xticklabels(labels, rotation=45, ha='right')
        axes[1].set_ylabel('Count')
        axes[1].set_title('Node Count by Type', fontsize=14, fontweight='bold')
        
        # 添加数值标签
        for bar, size in zip(bars, sizes):
            height = bar.get_height()
            axes[1].text(bar.get_x() + bar.get_width()/2., height,
                        f'{int(size)}',
                        ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ 节点分布图已保存: {save_path}")
        return save_path
    
    def plot_risk_distribution(self, risk_stats: Dict[str, Any],
                               save_path: Optional[str] = None,
                               figsize: Tuple[int, int] = (14, 5)) -> str:
        """
        绘制风险分布直方图
        
        Args:
            risk_stats: 风险标签统计信息
            save_path: 保存路径
            figsize: 图像尺寸
            
        Returns:
            保存的文件路径
        """
        if save_path is None:
            save_path = os.path.join(self.output_dir, 'risk_distribution.png')
        
        num_plots = len(risk_stats)
        fig, axes = plt.subplots(1, num_plots, figsize=figsize)
        
        if num_plots == 1:
            axes = [axes]
        
        for idx, (key, stats) in enumerate(risk_stats.items()):
            ax = axes[idx]
            
            if 'histogram' in stats:
                # 连续值直方图
                hist_data = stats['histogram']
                bin_centers = [(h['bin_start'] + h['bin_end']) / 2 for h in hist_data]
                bin_counts = [h['count'] for h in hist_data]
                bin_widths = [h['bin_end'] - h['bin_start'] for h in hist_data]
                
                bars = ax.bar(bin_centers, bin_counts, width=bin_widths, 
                             alpha=0.7, edgecolor='black', linewidth=0.5)
                
                # 着色
                for bar, center in zip(bars, bin_centers):
                    if center < 0.33:
                        bar.set_color(self.colors['low_risk'])
                    elif center < 0.66:
                        bar.set_color(self.colors['medium_risk'])
                    else:
                        bar.set_color(self.colors['high_risk'])
                
                ax.set_xlabel('Risk Score')
                ax.set_ylabel('Frequency')
                ax.set_title(f'{stats["name"]} Distribution\nμ={stats["mean"]:.3f}, σ={stats["std"]:.3f}',
                           fontsize=12, fontweight='bold')
                
                # 添加分桶线
                ax.axvline(x=0.33, color='orange', linestyle='--', alpha=0.7, label='Medium threshold')
                ax.axvline(x=0.66, color='red', linestyle='--', alpha=0.7, label='High threshold')
                ax.legend(fontsize=8)
                
            elif 'distribution' in stats:
                # 二分类饼图
                labels = ['Negative', 'Positive']
                sizes = [stats['negative'], stats['positive']]
                colors_pie = [self.colors['low_risk'], self.colors['high_risk']]
                
                ax.pie(sizes, labels=labels, colors=colors_pie, autopct='%1.1f%%',
                      startangle=90)
                ax.set_title(f'{stats["name"]} Distribution\nTotal: {stats["count"]}',
                           fontsize=12, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ 风险分布图已保存: {save_path}")
        return save_path
    
    def plot_risk_buckets(self, bucket_stats: Dict[str, Any],
                         save_path: Optional[str] = None,
                         figsize: Tuple[int, int] = (10, 6)) -> str:
        """
        绘制风险分桶图
        
        Args:
            bucket_stats: 风险分桶统计
            save_path: 保存路径
            figsize: 图像尺寸
            
        Returns:
            保存的文件路径
        """
        if save_path is None:
            save_path = os.path.join(self.output_dir, 'risk_buckets.png')
        
        fig, axes = plt.subplots(1, 2, figsize=figsize)
        
        buckets = bucket_stats['buckets']
        counts = bucket_stats['counts']
        percentages = bucket_stats['percentages']
        colors_list = [self.colors['low_risk'], self.colors['medium_risk'], self.colors['high_risk']]
        
        # 饼图
        wedges, texts, autotexts = axes[0].pie(
            counts, labels=buckets, colors=colors_list,
            autopct='%1.1f%%', startangle=90,
            explode=[0.02, 0.02, 0.02]
        )
        axes[0].set_title('Risk Level Distribution', fontsize=14, fontweight='bold')
        
        # 柱状图
        bars = axes[1].bar(buckets, counts, color=colors_list, edgecolor='black', linewidth=1)
        axes[1].set_ylabel('Count')
        axes[1].set_title('Risk Level Count', fontsize=14, fontweight='bold')
        
        # 添加数值标签
        for bar, count, pct in zip(bars, counts, percentages):
            height = bar.get_height()
            axes[1].text(bar.get_x() + bar.get_width()/2., height,
                        f'{int(count)}\n({pct:.1f}%)',
                        ha='center', va='bottom', fontsize=10)
        
        # 添加风险等级说明
        axes[1].text(0.5, -0.15, 
                    f'Boundary: [{bucket_stats["boundaries"][0]}, {bucket_stats["boundaries"][1]}, {bucket_stats["boundaries"][2]}, {bucket_stats["boundaries"][3]}]',
                    transform=axes[1].transAxes, ha='center', fontsize=9, style='italic')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ 风险分桶图已保存: {save_path}")
        return save_path
    
    def plot_scale_risk_relation(self, data,
                                 save_path: Optional[str] = None,
                                 figsize: Tuple[int, int] = (12, 5)) -> str:
        """
        绘制企业规模与风险关系图
        
        Args:
            data: PyG HeteroData对象
            save_path: 保存路径
            figsize: 图像尺寸
            
        Returns:
            保存的文件路径
        """
        if save_path is None:
            save_path = os.path.join(self.output_dir, 'scale_risk_relation.png')
        
        # 从企业节点特征中提取规模信息
        import torch
        enterprise_feat = data['enterprise'].x.numpy()
        
        # 假设最后一维是规模编码 (根据nodes.py中的get_feature_vector)
        # scale_encoded: LARGE=1.0, MEDIUM=0.6, SMALL=0.3
        scale_encoded = enterprise_feat[:, -1]
        
        # 获取风险标签（如果存在）
        if hasattr(data, 'y_risk'):
            # 需要找到batch节点对应的企业风险
            # 这里简化处理：显示规模分布
            has_risk = True
        else:
            has_risk = False
        
        fig, axes = plt.subplots(1, 2 if has_risk else 1, figsize=figsize)
        if not has_risk:
            axes = [axes]
        
        # 规模分布直方图
        scale_names = {1.0: 'Large', 0.6: 'Medium', 0.3: 'Small'}
        scale_counts = {}
        for val in scale_encoded:
            closest = min(scale_names.keys(), key=lambda x: abs(x - val))
            scale_counts[closest] = scale_counts.get(closest, 0) + 1
        
        labels = [scale_names[k] for k in sorted(scale_counts.keys())]
        counts = [scale_counts[k] for k in sorted(scale_counts.keys())]
        colors_scale = ['#2ECC71', '#F39C12', '#E74C3C']
        
        bars = axes[0].bar(labels, counts, color=colors_scale, edgecolor='black')
        axes[0].set_ylabel('Count')
        axes[0].set_title('Enterprise Scale Distribution', fontsize=14, fontweight='bold')
        
        for bar, count in zip(bars, counts):
            height = bar.get_height()
            axes[0].text(bar.get_x() + bar.get_width()/2., height,
                        f'{count}',
                        ha='center', va='bottom', fontsize=10)
        
        # 风险关联分析（如果有风险标签）
        if has_risk and len(axes) > 1:
            # 计算每个规模等级的平均风险
            # 注意：这需要企业-批次的边关系，这里简化展示
            axes[1].text(0.5, 0.5, 'Risk-Scale Analysis\n(See full report)',
                        ha='center', va='center', transform=axes[1].transAxes,
                        fontsize=12)
            axes[1].set_title('Scale vs Risk', fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ 企业规模-风险关系图已保存: {save_path}")
        return save_path
    
    def plot_network_topology(self, data,
                             save_path: Optional[str] = None,
                             figsize: Tuple[int, int] = (16, 12),
                             max_nodes_per_type: int = 20) -> str:
        """
        绘制供应链网络拓扑可视化
        
        Args:
            data: PyG HeteroData对象
            save_path: 保存路径
            figsize: 图像尺寸
            max_nodes_per_type: 每种节点类型显示的最大数量
            
        Returns:
            保存的文件路径
        """
        if save_path is None:
            save_path = os.path.join(self.output_dir, 'network_topology.png')
        
        try:
            import networkx as nx
        except ImportError:
            print("警告: networkx未安装，使用简化拓扑图")
            return self._plot_simple_topology(data, save_path, figsize)
        
        G = nx.DiGraph()
        
        # 节点位置布局（按类型分层）
        node_positions = {}
        layer_y = {
            'enterprise': 0,
            'raw_material': 1,
            'production_line': 2,
            'batch': 3,
            'logistics': 4,
            'retail': 5
        }
        
        node_offset = {}
        
        # 添加节点
        for node_type in data.node_types:
            num_nodes = min(data[node_type].num_nodes, max_nodes_per_type)
            node_offset[node_type] = 0
            
            for i in range(num_nodes):
                node_id = f"{node_type}_{i}"
                G.add_node(node_id, node_type=node_type)
                
                # 计算位置
                x = (i - num_nodes / 2) * 2
                y = layer_y.get(node_type, 0) * 2
                node_positions[node_id] = (x, y)
        
        # 添加边
        edge_colors = []
        for edge_type in data.edge_types:
            src_type, rel, dst_type = edge_type
            edge_index = data[edge_type].edge_index
            
            max_edges = 50  # 限制边数量
            for i in range(min(edge_index.shape[1], max_edges)):
                src_idx = int(edge_index[0, i])
                dst_idx = int(edge_index[1, i])
                
                if src_idx < max_nodes_per_type and dst_idx < max_nodes_per_type:
                    src_id = f"{src_type}_{src_idx}"
                    dst_id = f"{dst_type}_{dst_idx}"
                    
                    if src_id in G.nodes and dst_id in G.nodes:
                        G.add_edge(src_id, dst_id, relation=rel)
                        edge_colors.append(self.colors.get(src_type, '#808080'))
        
        # 绘制
        fig, ax = plt.subplots(figsize=figsize)
        
        # 按类型分组绘制节点
        for node_type in data.node_types:
            nodes = [n for n in G.nodes if n.startswith(f"{node_type}_")]
            if nodes:
                nx.draw_networkx_nodes(G, node_positions, 
                                      nodelist=nodes,
                                      node_color=self.colors.get(node_type, '#808080'),
                                      node_size=300,
                                      alpha=0.8,
                                      ax=ax)
        
        nx.draw_networkx_edges(G, node_positions, 
                              arrowsize=10,
                              arrowstyle='->',
                              alpha=0.5,
                              width=0.5,
                              ax=ax)
        
        # 添加图例
        legend_elements = [
            mpatches.Patch(color=self.colors.get(nt, '#808080'), 
                          label=self.node_type_names.get(nt, nt))
            for nt in data.node_types
        ]
        ax.legend(handles=legend_elements, loc='upper right')
        
        ax.set_title('Supply Chain Network Topology\n(Sampled View)', 
                    fontsize=16, fontweight='bold')
        ax.axis('off')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ 网络拓扑图已保存: {save_path}")
        return save_path
    
    def _plot_simple_topology(self, data, save_path: str, figsize: Tuple[int, int]) -> str:
        """简化版拓扑图（无networkx时）"""
        fig, ax = plt.subplots(figsize=figsize)
        
        # 绘制层次结构示意
        layers = {
            'Enterprise': 5,
            'Raw Material': 4,
            'Production Line': 3,
            'Batch': 2,
            'Logistics': 1,
            'Retail': 0
        }
        
        y_pos = 0
        for layer_name, count in layers.items():
            # 绘制层标签
            ax.text(-2, y_pos, layer_name, fontsize=12, fontweight='bold',
                   va='center', ha='right')
            
            # 绘制节点示意
            for i in range(min(count, 8)):
                circle = plt.Circle((i * 1.5, y_pos), 0.3, 
                                   color=self.colors.get(layer_name.lower().replace(' ', '_'), '#808080'),
                                   alpha=0.7)
                ax.add_patch(circle)
            
            if count > 8:
                ax.text(12, y_pos, f'...({count} total)', fontsize=10, va='center')
            
            y_pos += 2
        
        # 绘制连接线示意
        for i in range(5):
            ax.annotate('', xy=(6, i * 2), xytext=(6, (i + 1) * 2 - 0.5),
                       arrowprops=dict(arrowstyle='->', color='gray', alpha=0.5))
        
        ax.set_xlim(-4, 16)
        ax.set_ylim(-1, 11)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.set_title('Supply Chain Network Structure\n(Simplified View)', 
                    fontsize=16, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ 简化拓扑图已保存: {save_path}")
        return save_path
    
    def plot_feature_heatmap(self, data,
                            save_path: Optional[str] = None,
                            figsize: Tuple[int, int] = (14, 10)) -> str:
        """
        绘制特征热力图
        
        Args:
            data: PyG HeteroData对象
            save_path: 保存路径
            figsize: 图像尺寸
            
        Returns:
            保存的文件路径
        """
        if save_path is None:
            save_path = os.path.join(self.output_dir, 'feature_heatmap.png')
        
        import numpy as np
        
        # 选择代表性的节点类型
        selected_types = ['enterprise', 'raw_material', 'production_line', 'batch']
        
        fig, axes = plt.subplots(2, 2, figsize=figsize)
        axes = axes.flatten()
        
        for idx, node_type in enumerate(selected_types):
            if node_type not in data.node_types:
                continue
                
            ax = axes[idx]
            feat = data[node_type].x.numpy()
            
            # 标准化特征用于可视化
            feat_norm = (feat - feat.mean(axis=0)) / (feat.std(axis=0) + 1e-8)
            
            # 限制显示节点数
            max_display = min(50, feat.shape[0])
            
            im = ax.imshow(feat_norm[:max_display], aspect='auto', 
                          cmap='RdYlBu_r', vmin=-2, vmax=2)
            ax.set_title(f'{self.node_type_names.get(node_type, node_type)} Features\n'
                        f'({feat.shape[0]} nodes × {feat.shape[1]} dims)',
                        fontsize=11, fontweight='bold')
            ax.set_xlabel('Feature Dimension')
            ax.set_ylabel('Node Index')
            
            plt.colorbar(im, ax=ax, label='Normalized Value')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ 特征热力图已保存: {save_path}")
        return save_path
    
    def plot_edge_statistics(self, edge_stats: Dict,
                            save_path: Optional[str] = None,
                            figsize: Tuple[int, int] = (14, 6)) -> str:
        """
        绘制边统计图
        
        Args:
            edge_stats: 边统计信息
            save_path: 保存路径
            figsize: 图像尺寸
            
        Returns:
            保存的文件路径
        """
        if save_path is None:
            save_path = os.path.join(self.output_dir, 'edge_statistics.png')
        
        fig, axes = plt.subplots(1, 2, figsize=figsize)
        
        # 边数量柱状图
        edge_types = []
        edge_counts = []
        
        for edge_type, info in edge_stats.items():
            rel_name = f"{info['src_type']}\n→\n{info['dst_type']}"
            edge_types.append(rel_name)
            edge_counts.append(info['count'])
        
        # 按数量排序
        sorted_data = sorted(zip(edge_counts, edge_types), reverse=True)
        edge_counts, edge_types = zip(*sorted_data)
        
        bars = axes[0].barh(range(len(edge_types)), edge_counts, color='steelblue')
        axes[0].set_yticks(range(len(edge_types)))
        axes[0].set_yticklabels(edge_types, fontsize=9)
        axes[0].set_xlabel('Edge Count')
        axes[0].set_title('Edge Count by Type', fontsize=14, fontweight='bold')
        axes[0].invert_yaxis()
        
        # 添加数值标签
        for bar, count in zip(bars, edge_counts):
            width = bar.get_width()
            axes[0].text(width, bar.get_y() + bar.get_height()/2.,
                        f' {int(count)}',
                        ha='left', va='center', fontsize=9)
        
        # 边密度图
        densities = [edge_stats[et]['density'] for et in edge_stats]
        axes[1].scatter(range(len(edge_types)), densities, s=100, alpha=0.6)
        axes[1].set_xticks(range(len(edge_types)))
        axes[1].set_xticklabels(edge_types, rotation=45, ha='right', fontsize=8)
        axes[1].set_ylabel('Edge Density')
        axes[1].set_title('Edge Density by Type', fontsize=14, fontweight='bold')
        axes[1].set_ylim(0, max(densities) * 1.1)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ 边统计图已保存: {save_path}")
        return save_path
    
    def generate_all_visualizations(self, data, stats: Dict) -> List[str]:
        """
        生成所有可视化图表
        
        Args:
            data: PyG HeteroData对象
            stats: 分析统计信息
            
        Returns:
            生成的文件路径列表
        """
        print("=" * 60)
        print("开始生成可视化图表...")
        print("=" * 60)
        
        generated_files = []
        
        # 节点分布
        if 'node_distribution' in stats:
            path = self.plot_node_distribution(stats['node_distribution'])
            generated_files.append(path)
        
        # 风险分布
        if 'risk_labels' in stats:
            path = self.plot_risk_distribution(stats['risk_labels'])
            generated_files.append(path)
        
        # 风险分桶
        if 'risk_buckets' in stats:
            path = self.plot_risk_buckets(stats['risk_buckets'])
            generated_files.append(path)
        
        # 企业规模与风险
        path = self.plot_scale_risk_relation(data)
        generated_files.append(path)
        
        # 网络拓扑
        path = self.plot_network_topology(data)
        generated_files.append(path)
        
        # 特征热力图
        path = self.plot_feature_heatmap(data)
        generated_files.append(path)
        
        # 边统计
        if 'edge_distribution' in stats:
            path = self.plot_edge_statistics(stats['edge_distribution'])
            generated_files.append(path)
        
        print("\n✓ 所有可视化图表生成完成!")
        print("=" * 60)
        
        return generated_files


if __name__ == '__main__':
    # 测试可视化器
    import os
    os.chdir('/home/yarizakurahime/data/dairy_supply_chain_risk')
    
    # 加载数据
    import torch
    data = torch.load('data/supply_chain_graph.pt', weights_only=False)
    
    # 创建可视化器
    viz = GraphVisualizer()
    
    # 生成示例图表
    from graph_analyzer import GraphAnalyzer
    analyzer = GraphAnalyzer()
    stats = analyzer.run_full_analysis()
    
    viz.generate_all_visualizations(data, stats)
