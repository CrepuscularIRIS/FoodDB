#!/usr/bin/env python3
"""
风险评分引擎测试
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from rules.engine import RiskScoringEngine


def test_basic_scoring():
    """测试基本评分功能"""
    print("=" * 60)
    print("风险评分引擎测试")
    print("=" * 60)

    # 初始化引擎
    engine = RiskScoringEngine()
    print(f"\n✓ 引擎初始化成功")
    print(f"  - 企业数据: {len(engine.enterprises)} 条")
    print(f"  - 批次数据: {len(engine.batches)} 条")
    print(f"  - 检验数据: {len(engine.inspections)} 条")
    print(f"  - GB规则: {len(engine.gb_rules)} 条")

    # 测试企业风险评分
    print("\n" + "-" * 60)
    print("测试1: 企业风险评分")
    print("-" * 60)

    for enterprise_id in ["ENT-0001", "ENT-0005", "ENT-0009"]:
        try:
            score = engine.calculate_node_risk(enterprise_id=enterprise_id)
            print(f"\n企业 {enterprise_id}:")
            print(f"  总分: {score.total_score} ({score.risk_level})")
            print(f"  产品风险: {score.product_risk}")
            print(f"  抽检风险: {score.inspection_risk}")
            print(f"  监管风险: {score.regulatory_risk}")
            print(f"  冷链风险: {score.cold_chain_risk}")
            if score.triggered_rules:
                print(f"  触发规则: {len(score.triggered_rules)} 条")
        except Exception as e:
            print(f"  错误: {e}")

    # 测试批次风险评分
    print("\n" + "-" * 60)
    print("测试2: 批次风险评分")
    print("-" * 60)

    for batch_id in ["BATCH-000001", "BATCH-000050", "BATCH-000100"]:
        try:
            score = engine.calculate_node_risk(batch_id=batch_id)
            batch = engine.batch_by_id.get(batch_id)
            print(f"\n批次 {batch_id}:")
            print(f"  产品: {batch.get('product_name', '未知')}")
            print(f"  总分: {score.total_score} ({score.risk_level})")
            print(f"  冷链风险: {score.cold_chain_risk}")
            print(f"  追溯风险: {score.traceability_risk}")
        except Exception as e:
            print(f"  错误: {e}")

    # 测试GB合规检查
    print("\n" + "-" * 60)
    print("测试3: GB合规检查")
    print("-" * 60)

    # 找一个不合格的检验记录
    unqualified_inspections = [
        ins for ins in engine.inspections
        if ins.get("test_result") == "unqualified"
    ]

    if unqualified_inspections:
        test_ins = unqualified_inspections[0]
        print(f"\n检验记录 {test_ins.get('inspection_id')}:")
        print(f"  结果: {test_ins.get('test_result')}")
        print(f"  不合格项: {test_ins.get('unqualified_items')}")

        violations = engine.check_gb_compliance(test_ins)
        if violations:
            print(f"  违规规则:")
            for v in violations[:3]:
                print(f"    - {v['gb_no']} {v['check_item']}: {v['actual_value']} > {v['threshold']}")
                print(f"      建议: {v['action_suggestion']}")
        else:
            print("  未匹配到具体GB规则")

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    test_basic_scoring()
