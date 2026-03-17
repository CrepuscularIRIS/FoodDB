"""
数据质量报告生成模块

生成markdown格式的数据质量报告，包括：
- 缺失值统计
- 数据完整性评分
- 风险标签分布
- 图结构分析
"""

import os
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime


class DataReportGenerator:
    """数据报告生成器"""
    
    def __init__(self, output_dir: str = 'reports'):
        """
        初始化报告生成器
        
        Args:
            output_dir: 报告输出目录
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_missing_value_report(self, stats: Dict) -> Dict[str, Any]:
        """
        生成缺失值统计报告
        
        Args:
            stats: 图分析统计信息
            
        Returns:
            缺失值统计结果
        """
        report = {
            'summary': {},
            'details': {},
            'recommendations': []
        }
        
        node_dist = stats.get('node_distribution', {})
        total_missing_ratio = 0
        
        for node_type, info in node_dist.items():
            missing_ratio = info.get('missing_ratio', 0)
            total_missing_ratio += missing_ratio
            
            report['details'][node_type] = {
                'count': info['count'],
                'feature_dim': info['feature_dim'],
                'missing_ratio': missing_ratio,
                'missing_count': int(info['count'] * info['feature_dim'] * missing_ratio)
            }
            
            # 根据缺失率给出建议
            if missing_ratio > 0.3:
                report['recommendations'].append(
                    f"⚠️ {node_type}: 缺失率较高({missing_ratio:.1%})，建议检查数据源"
                )
            elif missing_ratio > 0.1:
                report['recommendations'].append(
                    f"ℹ️ {node_type}: 缺失率中等({missing_ratio:.1%})，可考虑插值填充"
                )
        
        avg_missing = total_missing_ratio / len(node_dist) if node_dist else 0
        report['summary'] = {
            'total_node_types': len(node_dist),
            'average_missing_ratio': avg_missing,
            'overall_grade': self._grade_missing_ratio(avg_missing)
        }
        
        return report
    
    def _grade_missing_ratio(self, ratio: float) -> str:
        """根据缺失率给出等级"""
        if ratio < 0.05:
            return "A (优秀)"
        elif ratio < 0.15:
            return "B (良好)"
        elif ratio < 0.30:
            return "C (一般)"
        else:
            return "D (较差)"
    
    def calculate_data_quality_score(self, stats: Dict) -> Dict[str, Any]:
        """
        计算数据完整性评分
        
        Args:
            stats: 图分析统计信息
            
        Returns:
            数据质量评分
        """
        scores = {}
        
        # 1. 节点完整性 (25分)
        node_dist = stats.get('node_distribution', {})
        expected_node_types = 6
        actual_node_types = len(node_dist)
        node_score = min(25, 25 * actual_node_types / expected_node_types)
        scores['node_completeness'] = {
            'score': node_score,
            'max': 25,
            'description': f'包含{actual_node_types}/{expected_node_types}种节点类型'
        }
        
        # 2. 边完整性 (25分)
        edge_dist = stats.get('edge_distribution', {})
        expected_edge_types = 10
        actual_edge_types = len(edge_dist)
        edge_score = min(25, 25 * actual_edge_types / expected_edge_types)
        scores['edge_completeness'] = {
            'score': edge_score,
            'max': 25,
            'description': f'包含{actual_edge_types}/{expected_edge_types}种边类型'
        }
        
        # 3. 特征完整性 (25分)
        feat_stats = stats.get('feature_statistics', {})
        total_missing = sum(node_dist.get(nt, {}).get('missing_ratio', 0) 
                           for nt in node_dist)
        avg_missing = total_missing / len(node_dist) if node_dist else 0
        feature_score = 25 * (1 - avg_missing)
        scores['feature_completeness'] = {
            'score': feature_score,
            'max': 25,
            'description': f'平均缺失率: {avg_missing:.2%}'
        }
        
        # 4. 标签完整性 (25分)
        risk_labels = stats.get('risk_labels', {})
        label_count = len(risk_labels)
        label_score = min(25, 25 * label_count / 3)  # 期望3种标签
        scores['label_completeness'] = {
            'score': label_score,
            'max': 25,
            'description': f'包含{label_count}种风险标签'
        }
        
        # 总分
        total_score = sum(s['score'] for s in scores.values())
        scores['total'] = {
            'score': total_score,
            'max': 100,
            'grade': self._get_grade(total_score)
        }
        
        return scores
    
    def _get_grade(self, score: float) -> str:
        """根据分数给出等级"""
        if score >= 90:
            return "A (优秀)"
        elif score >= 80:
            return "B (良好)"
        elif score >= 70:
            return "C (一般)"
        elif score >= 60:
            return "D (及格)"
        else:
            return "F (不及格)"
    
    def analyze_risk_label_distribution(self, stats: Dict) -> Dict[str, Any]:
        """
        分析风险标签分布
        
        Args:
            stats: 图分析统计信息
            
        Returns:
            风险标签分析报告
        """
        report = {
            'summary': {},
            'imbalance_warnings': [],
            'recommendations': []
        }
        
        risk_labels = stats.get('risk_labels', {})
        risk_buckets = stats.get('risk_buckets', {})
        
        # 二分类标签分析
        if 'y_binary' in risk_labels:
            y_binary = risk_labels['y_binary']
            pos_ratio = y_binary['positive_ratio']
            
            report['summary']['binary'] = {
                'positive_count': y_binary['positive'],
                'negative_count': y_binary['negative'],
                'positive_ratio': pos_ratio,
                'balance_score': 1 - abs(0.5 - pos_ratio) * 2  # 越接近0.5越好
            }
            
            if pos_ratio < 0.1 or pos_ratio > 0.9:
                report['imbalance_warnings'].append(
                    f"⚠️ 二分类标签严重不平衡: 阳性率={pos_ratio:.2%}"
                )
                report['recommendations'].append(
                    "建议使用过采样/欠采样技术平衡训练数据"
                )
            elif pos_ratio < 0.3 or pos_ratio > 0.7:
                report['imbalance_warnings'].append(
                    f"ℹ️ 二分类标签轻微不平衡: 阳性率={pos_ratio:.2%}"
                )
        
        # 风险分桶分析
        if risk_buckets:
            buckets = risk_buckets.get('buckets', [])
            counts = risk_buckets.get('counts', [])
            percentages = risk_buckets.get('percentages', [])
            
            report['summary']['buckets'] = {
                'low_risk': {'count': counts[0] if len(counts) > 0 else 0,
                           'percentage': percentages[0] if len(percentages) > 0 else 0},
                'medium_risk': {'count': counts[1] if len(counts) > 1 else 0,
                              'percentage': percentages[1] if len(percentages) > 1 else 0},
                'high_risk': {'count': counts[2] if len(counts) > 2 else 0,
                            'percentage': percentages[2] if len(percentages) > 2 else 0}
            }
            
            # 检查是否存在类别不平衡
            max_pct = max(percentages) if percentages else 0
            if max_pct > 60:
                dominant_idx = percentages.index(max_pct)
                report['imbalance_warnings'].append(
                    f"⚠️ 风险分桶不平衡: {buckets[dominant_idx]}占{max_pct:.1f}%"
                )
        
        return report
    
    def generate_markdown_report(self, stats: Dict, 
                                  figure_paths: List[str] = None) -> str:
        """
        生成Markdown格式报告
        
        Args:
            stats: 图分析统计信息
            figure_paths: 图表路径列表
            
        Returns:
            Markdown报告内容
        """
        lines = []
        
        # 报告头
        lines.append("# 供应链异构图数据质量报告")
        lines.append("")
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # 1. 数据概览
        lines.append("## 1. 数据概览")
        lines.append("")
        
        metrics = stats.get('graph_metrics', {})
        lines.append("### 1.1 图基本统计")
        lines.append("")
        lines.append(f"- **总节点数**: {metrics.get('total_nodes', 'N/A')}")
        lines.append(f"- **总边数**: {metrics.get('total_edges', 'N/A')}")
        lines.append(f"- **节点类型数**: {metrics.get('num_node_types', 'N/A')}")
        lines.append(f"- **边类型数**: {metrics.get('num_edge_types', 'N/A')}")
        lines.append(f"- **整体密度**: {metrics.get('overall_density', 'N/A'):.4f}")
        lines.append(f"- **平均度数**: {metrics.get('avg_degree', 'N/A'):.2f}")
        lines.append("")
        
        # 2. 节点分布
        lines.append("## 2. 节点分布分析")
        lines.append("")
        
        node_dist = stats.get('node_distribution', {})
        lines.append("| 节点类型 | 数量 | 占比 | 特征维度 | 缺失率 |")
        lines.append("|---------|------|------|---------|--------|")
        
        for node_type, info in sorted(node_dist.items(), 
                                       key=lambda x: x[1]['count'], 
                                       reverse=True):
            lines.append(
                f"| {node_type} | {info['count']} | {info['percentage']:.1f}% | "
                f"{info['feature_dim']} | {info['missing_ratio']:.2%} |"
            )
        lines.append("")
        
        # 3. 边分布
        lines.append("## 3. 边分布分析")
        lines.append("")
        
        edge_dist = stats.get('edge_distribution', {})
        lines.append("| 边类型 | 数量 | 占比 | 密度 |")
        lines.append("|--------|------|------|------|")
        
        for edge_type, info in sorted(edge_dist.items(),
                                       key=lambda x: x[1]['count'],
                                       reverse=True):
            rel = f"{info['src_type']} → {info['dst_type']}"
            lines.append(
                f"| {rel} | {info['count']} | {info['percentage']:.1f}% | "
                f"{info['density']:.4f} |"
            )
        lines.append("")
        
        # 4. 数据质量评分
        lines.append("## 4. 数据完整性评分")
        lines.append("")
        
        quality_scores = self.calculate_data_quality_score(stats)
        
        lines.append("### 4.1 评分详情")
        lines.append("")
        lines.append("| 维度 | 得分 | 满分 | 说明 |")
        lines.append("|------|------|------|------|")
        
        for key, score_info in quality_scores.items():
            if key != 'total':
                lines.append(
                    f"| {key.replace('_', ' ').title()} | "
                    f"{score_info['score']:.1f} | {score_info['max']} | "
                    f"{score_info['description']} |"
                )
        
        total = quality_scores.get('total', {})
        lines.append("")
        lines.append(f"### 4.2 总评分: {total.get('score', 0):.1f}/100")
        lines.append("")
        lines.append(f"**等级**: {total.get('grade', 'N/A')}")
        lines.append("")
        
        # 5. 缺失值统计
        lines.append("## 5. 缺失值统计")
        lines.append("")
        
        missing_report = self.generate_missing_value_report(stats)
        summary = missing_report.get('summary', {})
        
        lines.append(f"- **总体缺失率等级**: {summary.get('overall_grade', 'N/A')}")
        lines.append(f"- **平均缺失率**: {summary.get('average_missing_ratio', 0):.2%}")
        lines.append("")
        
        if missing_report.get('recommendations'):
            lines.append("### 5.1 缺失值处理建议")
            lines.append("")
            for rec in missing_report['recommendations']:
                lines.append(f"- {rec}")
            lines.append("")
        
        # 6. 风险标签分析
        lines.append("## 6. 风险标签分布")
        lines.append("")
        
        risk_analysis = self.analyze_risk_label_distribution(stats)
        
        # 二分类
        if 'binary' in risk_analysis.get('summary', {}):
            binary = risk_analysis['summary']['binary']
            lines.append("### 6.1 二分类标签")
            lines.append("")
            lines.append(f"- **正样本**: {binary['positive_count']} ({binary['positive_ratio']:.2%})")
            lines.append(f"- **负样本**: {binary['negative_count']} ({1-binary['positive_ratio']:.2%})")
            lines.append(f"- **平衡分数**: {binary['balance_score']:.2f}")
            lines.append("")
        
        # 风险分桶
        if 'buckets' in risk_analysis.get('summary', {}):
            buckets = risk_analysis['summary']['buckets']
            lines.append("### 6.2 风险等级分桶")
            lines.append("")
            lines.append("| 风险等级 | 数量 | 占比 |")
            lines.append("|---------|------|------|")
            
            risk_buckets = stats.get('risk_buckets', {})
            bucket_names = risk_buckets.get('buckets', ['Low', 'Medium', 'High'])
            bucket_counts = risk_buckets.get('counts', [0, 0, 0])
            bucket_pcts = risk_buckets.get('percentages', [0, 0, 0])
            
            for name, count, pct in zip(bucket_names, bucket_counts, bucket_pcts):
                lines.append(f"| {name} | {count} | {pct:.1f}% |")
            lines.append("")
        
        if risk_analysis.get('imbalance_warnings'):
            lines.append("### 6.3 标签平衡性警告")
            lines.append("")
            for warning in risk_analysis['imbalance_warnings']:
                lines.append(f"- {warning}")
            lines.append("")
        
        if risk_analysis.get('recommendations'):
            lines.append("### 6.4 标签处理建议")
            lines.append("")
            for rec in risk_analysis['recommendations']:
                lines.append(f"- {rec}")
            lines.append("")
        
        # 7. 可视化图表
        if figure_paths:
            lines.append("## 7. 可视化图表")
            lines.append("")
            
            for path in figure_paths:
                filename = os.path.basename(path)
                lines.append(f"### {filename}")
                lines.append("")
                lines.append(f"![{filename}]({path})")
                lines.append("")
        
        # 8. 总结与建议
        lines.append("## 8. 总结与建议")
        lines.append("")
        
        # 根据评分给出建议
        total_score = quality_scores.get('total', {}).get('score', 0)
        
        if total_score >= 90:
            lines.append("✅ **数据质量优秀** - 数据完整、标签平衡，可直接用于模型训练")
        elif total_score >= 80:
            lines.append("✅ **数据质量良好** - 整体可用，建议关注以下方面：")
        elif total_score >= 70:
            lines.append("⚠️ **数据质量一般** - 需要进行数据清洗：")
        else:
            lines.append("❌ **数据质量较差** - 建议重新采集或处理数据：")
        
        lines.append("")
        
        # 通用建议
        recommendations = []
        
        # 根据缺失值
        if summary.get('average_missing_ratio', 0) > 0.1:
            recommendations.append("考虑使用均值/中位数填充或更复杂的插值方法处理缺失值")
        
        # 根据标签平衡性
        if risk_analysis.get('imbalance_warnings'):
            recommendations.append("使用SMOTE等过采样技术或调整类别权重处理标签不平衡")
        
        # 根据图密度
        if metrics.get('overall_density', 0) < 0.001:
            recommendations.append("图密度较低，考虑增加边关系或检查数据采集完整性")
        
        if not recommendations:
            recommendations.append("数据整体质量良好，可直接用于后续建模")
        
        for rec in recommendations:
            lines.append(f"- {rec}")
        
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("*报告由 DairyRisk 数据分析模块自动生成*")
        
        return "\n".join(lines)
    
    def save_report(self, content: str, filename: str = 'data_quality_report.md') -> str:
        """
        保存报告到文件
        
        Args:
            content: 报告内容
            filename: 文件名
            
        Returns:
            保存的文件路径
        """
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✓ 报告已保存: {filepath}")
        return filepath
    
    def generate_full_report(self, stats: Dict, 
                            figure_paths: List[str] = None) -> str:
        """
        生成完整报告并保存
        
        Args:
            stats: 图分析统计信息
            figure_paths: 图表路径列表
            
        Returns:
            报告文件路径
        """
        print("=" * 60)
        print("开始生成数据质量报告...")
        print("=" * 60)
        
        # 生成报告内容
        content = self.generate_markdown_report(stats, figure_paths)
        
        # 保存报告
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'data_quality_report_{timestamp}.md'
        filepath = self.save_report(content, filename)
        
        # 同时保存为最新版本
        self.save_report(content, 'data_quality_report_latest.md')
        
        print("\n✓ 报告生成完成!")
        print("=" * 60)
        
        return filepath


if __name__ == '__main__':
    # 测试报告生成器
    import os
    os.chdir('/home/yarizakurahime/data/dairy_supply_chain_risk')
    
    # 运行分析
    from graph_analyzer import GraphAnalyzer
    analyzer = GraphAnalyzer()
    stats = analyzer.run_full_analysis()
    
    # 生成报告
    generator = DataReportGenerator()
    report_path = generator.generate_full_report(stats)
    
    print(f"\n报告已生成: {report_path}")
