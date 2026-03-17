"""
供应链异构图数据生成器使用示例

演示如何使用 SupplyChainDataGenerator 生成虚拟供应链异构图数据。
"""

import sys
import os
sys.path.insert(0, '/home/yarizakurahime/data/dairy_supply_chain_risk')

from dairyrisk.data.supply_chain_generator import SupplyChainDataGenerator


def example_basic_usage():
    """基本使用示例"""
    print("=" * 60)
    print("示例1: 基本使用")
    print("=" * 60)
    
    # 创建生成器
    generator = SupplyChainDataGenerator(random_seed=42)
    
    # 生成数据
    data = generator.generate_supply_chain(
        num_enterprises={"large": 5, "medium": 10, "small": 20},
        num_batches_per_enterprise=3,
        time_span_days=30
    )
    
    # 查看数据结构
    print(f"\n生成的异构图包含以下节点类型:")
    for node_type in data.node_types:
        num_nodes = data[node_type].x.shape[0]
        num_features = data[node_type].x.shape[1]
        print(f"  - {node_type}: {num_nodes} 个节点, {num_features} 维特征")
    
    print(f"\n生成的异构图包含以下边类型:")
    for edge_type in data.edge_types:
        num_edges = data[edge_type].edge_index.shape[1]
        print(f"  - {edge_type}: {num_edges} 条边")
    
    return data


def example_risk_analysis():
    """风险分析示例"""
    print("\n" + "=" * 60)
    print("示例2: 风险分析")
    print("=" * 60)
    
    generator = SupplyChainDataGenerator(random_seed=42)
    data = generator.generate_supply_chain(
        num_enterprises={"large": 8, "medium": 20, "small": 40},
        num_batches_per_enterprise=5
    )
    
    # 获取批次风险标签
    risk_labels = data["batch"].y_risk
    binary_labels = data["batch"].y_binary
    qc_counts = data["batch"].y_qc_count
    
    print(f"\n批次风险分析:")
    print(f"  总批次数: {len(risk_labels)}")
    print(f"  平均风险分数: {risk_labels.mean():.4f}")
    print(f"  高风险批次(>0.5): {(risk_labels > 0.5).sum().item()}")
    print(f"  低风险批次(≤0.5): {(risk_labels <= 0.5).sum().item()}")
    
    print(f"\n质检菌落数统计:")
    print(f"  平均值: {qc_counts.mean():.0f} CFU/mL")
    print(f"  最大值: {qc_counts.max():.0f} CFU/mL")
    print(f"  最小值: {qc_counts.min():.0f} CFU/mL")
    
    # 按企业规模分析风险
    print(f"\n按企业规模分析风险:")
    for scale in ["large", "medium", "small"]:
        scale_enterprises = [e for e in generator.enterprises.values() 
                            if e.scale.value == scale]
        scale_batches = [b for b in generator.batches.values() 
                        if b.enterprise_id in [e.node_id for e in scale_enterprises]]
        if scale_batches:
            fail_rate = sum(1 for b in scale_batches if b.qc_result == "fail") / len(scale_batches)
            print(f"  {scale}: 不合格率 = {fail_rate*100:.1f}%")


def example_data_completeness():
    """数据完整性差异示例"""
    print("\n" + "=" * 60)
    print("示例3: 数据完整性差异")
    print("=" * 60)
    
    generator = SupplyChainDataGenerator(random_seed=42)
    generator.generate_supply_chain(
        num_enterprises={"large": 10, "medium": 10, "small": 10},
        num_batches_per_enterprise=2
    )
    
    print("\n不同规模企业的数据完整性对比:")
    print("-" * 60)
    print(f"{'企业规模':<12} {'企业数':<8} {'平均特征数':<12} {'数据完整性':<12}")
    print("-" * 60)
    
    for scale in ["large", "medium", "small"]:
        scale_enterprises = [e for e in generator.enterprises.values() 
                            if e.scale.value == scale]
        if scale_enterprises:
            avg_features = sum(len(e.features) for e in scale_enterprises) / len(scale_enterprises)
            completeness = {
                "large": 0.95,
                "medium": 0.80,
                "small": 0.50
            }[scale]
            print(f"{scale:<12} {len(scale_enterprises):<8} {avg_features:<12.1f} {completeness:<12.0%}")
    
    print("-" * 60)
    print("\n说明:")
    print("  - 大企业: 95%数据完整度，有全面的质量监控")
    print("  - 中企业: 80%数据完整度，有部分监控缺失")
    print("  - 小企业: 50%数据完整度，是重点监管对象")


def example_save_and_load():
    """保存和加载示例"""
    print("\n" + "=" * 60)
    print("示例4: 保存和加载数据")
    print("=" * 60)
    
    # 生成数据
    generator = SupplyChainDataGenerator(random_seed=42)
    data = generator.generate_supply_chain(
        num_enterprises={"large": 3, "medium": 5, "small": 10},
        num_batches_per_enterprise=2
    )
    
    # 保存数据
    output_path = "/tmp/supply_chain_example.pt"
    generator.save_to_file(data, output_path)
    
    # 加载数据
    import torch
    loaded_data = torch.load(output_path)
    
    print(f"\n数据已保存到: {output_path}")
    print(f"数据已从文件加载")
    print(f"\n验证数据一致性:")
    print(f"  原始数据节点数: {sum(data[nt].x.shape[0] for nt in data.node_types)}")
    print(f"  加载数据节点数: {sum(loaded_data[nt].x.shape[0] for nt in loaded_data.node_types)}")
    
    # 清理
    os.remove(output_path)
    print(f"\n临时文件已清理")


def example_custom_generation():
    """自定义生成参数示例"""
    print("\n" + "=" * 60)
    print("示例5: 自定义生成参数")
    print("=" * 60)
    
    # 大规模数据生成
    print("\n生成大规模数据 (1000+ 节点)...")
    generator = SupplyChainDataGenerator(random_seed=42)
    data = generator.generate_supply_chain(
        num_enterprises={"large": 15, "medium": 60, "small": 150},
        num_batches_per_enterprise=5,
        time_span_days=60
    )
    
    total_nodes = sum(data[nt].x.shape[0] for nt in data.node_types)
    total_edges = sum(data[et].edge_index.shape[1] for et in data.edge_types)
    
    print(f"\n大规模数据统计:")
    print(f"  总节点数: {total_nodes}")
    print(f"  总边数: {total_edges}")
    print(f"  平均每个节点连接数: {total_edges * 2 / total_nodes:.1f}")


if __name__ == "__main__":
    # 运行所有示例
    example_basic_usage()
    example_risk_analysis()
    example_data_completeness()
    example_save_and_load()
    example_custom_generation()
    
    print("\n" + "=" * 60)
    print("所有示例运行完成!")
    print("=" * 60)
