"""
验收标准验证脚本

验证Phase 1任务的所有验收标准是否满足：
1. 运行生成器可以成功生成500-1000节点的异构图
2. 生成的数据可以保存为 `.pt` 文件
3. 包含数据完整性差异（大/中/小企业）
4. 批次节点有合理的风险标签（基于qc_colony_count）
5. 代码通过基础测试
"""

import sys
import os
sys.path.insert(0, '/home/yarizakurahime/data/dairy_supply_chain_risk')

import torch
from dairyrisk.data.supply_chain_generator import SupplyChainDataGenerator


def run_all_checks():
    """运行所有验收标准检查"""
    print("=" * 70)
    print("Phase 1 验收标准验证")
    print("=" * 70)
    
    results = []
    
    # 标准1: 生成500-1000节点的异构图
    print("\n[标准1] 验证节点数量...")
    generator = SupplyChainDataGenerator(random_seed=42)
    data = generator.generate_supply_chain(
        num_enterprises={"large": 8, "medium": 30, "small": 60},
        num_batches_per_enterprise=4
    )
    
    total_nodes = sum(data[nt].x.shape[0] for nt in data.node_types)
    check1 = 500 <= total_nodes <= 1000
    results.append(("节点数量 (500-1000)", check1, f"实际: {total_nodes}"))
    print(f"  {'✓' if check1 else '✗'} 总节点数: {total_nodes}")
    
    # 标准2: 生成的数据可以保存为 .pt 文件
    print("\n[标准2] 验证数据保存...")
    output_path = "/home/yarizakurahime/data/dairy_supply_chain_risk/data/validation_test.pt"
    try:
        generator.save_to_file(data, output_path)
        check2 = os.path.exists(output_path)
        if check2:
            file_size = os.path.getsize(output_path)
            # PyTorch 2.6+ compatibility
            try:
                loaded_data = torch.load(output_path, weights_only=False)
            except TypeError:
                loaded_data = torch.load(output_path)
            check2 = check2 and hasattr(loaded_data, 'node_types')
    except Exception as e:
        check2 = False
        print(f"  错误: {e}")
    
    results.append(("数据保存 (.pt文件)", check2, f"文件大小: {file_size/1024:.1f}KB"))
    print(f"  {'✓' if check2 else '✗'} 数据可保存并加载")
    
    # 标准3: 包含数据完整性差异
    print("\n[标准3] 验证数据完整性差异...")
    completeness_diff = True
    feature_counts = {}
    for scale in ["large", "medium", "small"]:
        enterprises = [e for e in generator.enterprises.values() 
                      if e.scale.value == scale]
        if enterprises:
            avg_features = sum(len(e.features) for e in enterprises) / len(enterprises)
            feature_counts[scale] = avg_features
    
    # 验证大企业特征数 > 中企业 > 小企业
    if feature_counts.get("large", 0) <= feature_counts.get("medium", 0):
        completeness_diff = False
    if feature_counts.get("medium", 0) <= feature_counts.get("small", 0):
        completeness_diff = False
    
    results.append(("数据完整性差异", completeness_diff, 
                   f"大:{feature_counts.get('large', 0):.1f} 中:{feature_counts.get('medium', 0):.1f} 小:{feature_counts.get('small', 0):.1f}"))
    print(f"  {'✓' if completeness_diff else '✗'} 大:{feature_counts.get('large', 0):.1f} > 中:{feature_counts.get('medium', 0):.1f} > 小:{feature_counts.get('small', 0):.1f}")
    
    # 标准4: 批次节点有合理的风险标签
    print("\n[标准4] 验证批次风险标签...")
    batch_check = True
    
    # 检查标签存在
    if "batch" not in data.node_types:
        batch_check = False
    elif "y_risk" not in data["batch"] or "y_binary" not in data["batch"]:
        batch_check = False
    else:
        risk_labels = data["batch"].y_risk
        binary_labels = data["batch"].y_binary
        
        # 风险标签在0-1范围内
        if risk_labels.min() < 0 or risk_labels.max() > 1:
            batch_check = False
        
        # 有二分类标签
        if len(torch.unique(binary_labels)) < 2:
            batch_check = False
        
        # 检查qc_colony_count与标签的对应关系
        qc_counts = data["batch"].y_qc_count
        for i in range(len(qc_counts)):
            expected_risk = min(1.0, qc_counts[i].item() / 100000)
            if abs(expected_risk - risk_labels[i].item()) > 0.1:
                batch_check = False
                break
    
    results.append(("批次风险标签", batch_check, 
                   f"风险范围: [{risk_labels.min():.3f}, {risk_labels.max():.3f}]"))
    print(f"  {'✓' if batch_check else '✗'} 风险标签合理")
    
    # 标准5: 代码通过基础测试
    print("\n[标准5] 验证节点和边类型...")
    
    # 检查6种节点类型
    expected_nodes = ["enterprise", "raw_material", "production_line", "batch", "logistics", "retail"]
    node_check = all(nt in data.node_types for nt in expected_nodes)
    
    # 检查10种边类型
    expected_edges = [
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
    edge_check = all(et in data.edge_types for et in expected_edges)
    
    structure_check = node_check and edge_check
    results.append(("6种节点 + 10种边", structure_check, 
                   f"节点: {len(data.node_types)}/6, 边: {len(data.edge_types)}/10"))
    print(f"  {'✓' if structure_check else '✗'} 6种节点类型, 10种边类型")
    
    # 打印总结
    print("\n" + "=" * 70)
    print("验收标准总结")
    print("=" * 70)
    print(f"{'标准':<30} {'状态':<8} {'详情'}")
    print("-" * 70)
    
    all_passed = True
    for name, passed, detail in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{name:<30} {status:<8} {detail}")
        if not passed:
            all_passed = False
    
    print("=" * 70)
    if all_passed:
        print("🎉 所有验收标准通过！Phase 1 完成！")
    else:
        print("❌ 部分验收标准未通过，请检查代码")
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    success = run_all_checks()
    sys.exit(0 if success else 1)
