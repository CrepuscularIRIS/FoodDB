"""
风险传导建模测试脚本

验证Phase 5实现的所有功能：
1. 风险传导系数计算
2. 蒙特卡洛传播模拟
3. 边级风险预测
4. 预警生成
5. API路由
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, '/home/yarizakurahime/data/dairy_supply_chain_risk')

import numpy as np
from datetime import datetime

# 导入测试的模块
from dairyrisk.graph.edges import EdgeType, Edge
from dairyrisk.graph.nodes import NodeType
from dairyrisk.risk.transmission import (
    RiskTransmissionModel,
    RISK_TRANSMISSION_COEFFICIENTS,
    create_transmission_model
)
from dairyrisk.risk.simulation import (
    RiskPropagationSimulator,
    SimulationConfig,
    SimulationMode,
    create_simulator
)
from dairyrisk.risk.edge_predictor import (
    EdgeRiskPredictor,
    create_edge_predictor
)
from dairyrisk.risk.alerts import (
    AlertGenerator,
    AlertSeverity,
    AlertCategory,
    create_alert_generator
)


def test_transmission_coefficients():
    """测试风险传导系数"""
    print("\n=== 测试风险传导系数 ===")
    
    model = create_transmission_model()
    
    # 测试各边类型的传导系数
    test_cases = [
        (EdgeType.SUPPLIES, 0.7, "供应关系"),
        (EdgeType.USED_IN, 0.8, "原料到批次"),
        (EdgeType.PRODUCES, 0.75, "生产线到批次"),
        (EdgeType.TRANSPORTED_BY, 0.6, "物流风险"),
        (EdgeType.TEMPORAL_NEXT, 0.5, "时序传导"),
    ]
    
    all_passed = True
    for edge_type, expected, desc in test_cases:
        coeff = model.get_transmission_coefficient(edge_type)
        passed = abs(coeff - expected) < 0.01
        status = "✓" if passed else "✗"
        print(f"  {status} {desc}: {coeff:.2f} (期望 {expected:.2f})")
        all_passed = all_passed and passed
    
    # 测试动态调整
    edge = Edge(
        src_id="src1",
        dst_id="dst1",
        edge_type=EdgeType.SUPPLIES,
        weight=1.0,
        features={"supply_volume": 0.9, "supply_frequency": 0.8}
    )
    adjusted_coeff = model.get_transmission_coefficient(
        EdgeType.SUPPLIES, edge.features
    )
    print(f"  {'✓' if adjusted_coeff > 0.7 else '✗'} 动态调整: {adjusted_coeff:.4f}")
    
    return all_passed


def test_risk_propagation():
    """测试风险传播计算"""
    print("\n=== 测试风险传播计算 ===")
    
    model = create_transmission_model()
    
    # 测试传导计算
    source_risk = 0.8
    propagated = model.calculate_propagated_risk(
        source_risk, EdgeType.USED_IN, distance=1
    )
    expected = source_risk * 0.8  # USED_IN系数为0.8
    print(f"  ✓ 单步传导: {source_risk} → {propagated:.4f} (期望 ~{expected:.4f})")
    
    # 测试衰减
    propagated_d2 = model.calculate_propagated_risk(
        source_risk, EdgeType.USED_IN, distance=2
    )
    print(f"  ✓ 两步衰减: {source_risk} → {propagated_d2:.4f} (应有衰减)")
    
    return propagated < source_risk and propagated_d2 < propagated


def test_monte_carlo_simulation():
    """测试蒙特卡洛模拟"""
    print("\n=== 测试蒙特卡洛模拟 ===")
    
    # 创建测试图结构
    edges = [
        Edge("A", "B", EdgeType.SUPPLIES, weight=1.0),
        Edge("A", "C", EdgeType.SUPPLIES, weight=0.8),
        Edge("B", "D", EdgeType.USED_IN, weight=1.0),
        Edge("C", "D", EdgeType.USED_IN, weight=0.9),
        Edge("D", "E", EdgeType.TRANSPORTED_BY, weight=1.0),
    ]
    
    config = SimulationConfig(
        mode=SimulationMode.MONTE_CARLO,
        num_rounds=50,  # 测试用较少的轮次
        max_steps=5,
        random_seed=42
    )
    
    simulator = create_simulator(config)
    simulator.set_graph_structure(edges)
    
    # 运行蒙特卡洛模拟
    result = simulator.run_monte_carlo("A", 0.8, num_rounds=50)
    
    print(f"  ✓ 模拟轮次: {len(result.simulation_results)}")
    print(f"  ✓ 平均影响节点: {result.mean_affected_nodes:.2f}")
    print(f"  ✓ 标准差: {result.std_affected_nodes:.2f}")
    print(f"  ✓ 95%置信区间: [{result.confidence_interval_95[0]:.2f}, {result.confidence_interval_95[1]:.2f}]")
    
    return result.mean_affected_nodes > 0 and len(result.simulation_results) == 50


def test_cascade_failure():
    """测试级联失效模拟"""
    print("\n=== 测试级联失效模拟 ===")
    
    edges = [
        Edge("A", "B", EdgeType.SUPPLIES, weight=1.0),
        Edge("B", "C", EdgeType.USED_IN, weight=1.0),
        Edge("C", "D", EdgeType.PRODUCES, weight=1.0),
        Edge("D", "E", EdgeType.TRANSPORTED_BY, weight=1.0),
    ]
    
    simulator = create_simulator()
    simulator.set_graph_structure(edges)
    
    result = simulator.run_cascade_failure(["A"], initial_risk=1.0)
    
    print(f"  ✓ 级联步数: {len(result.steps)}")
    print(f"  ✓ 最终影响: {result.final_affected_count} 节点")
    print(f"  ✓ 失效节点: {result.final_failure_count} 个")
    
    return len(result.steps) > 0


def test_edge_prediction():
    """测试边级风险预测"""
    print("\n=== 测试边级风险预测 ===")
    
    predictor = create_edge_predictor(model_type="logistic_regression")
    
    # 创建测试边
    edge = Edge(
        src_id="raw_mat_1",
        dst_id="batch_1",
        edge_type=EdgeType.USED_IN,
        weight=1.0,
        features={"usage_ratio": 0.8, "raw_quality": 0.7}
    )
    
    # 预测
    source_risk = 0.9
    result = predictor.predict(edge, source_risk)
    
    print(f"  ✓ 边ID: {result.edge_id}")
    print(f"  ✓ 传导概率: {result.transmission_probability:.4f}")
    print(f"  ✓ 风险等级: {result.risk_level}")
    print(f"  ✓ 置信度: {result.confidence:.4f}")
    
    # 测试不同风险水平的预测
    test_risks = [0.2, 0.5, 0.8, 0.95]
    print(f"  ✓ 不同源风险下的预测:")
    for risk in test_risks:
        r = predictor.predict(edge, risk)
        print(f"      源风险 {risk:.2f} → 传导概率 {r.transmission_probability:.4f}")
    
    return result.transmission_probability > 0


def test_alert_generation():
    """测试预警生成"""
    print("\n=== 测试预警生成 ===")
    
    generator = create_alert_generator()
    
    # 从传导结果创建预警
    from dairyrisk.risk.transmission import RiskTransmissionResult
    
    transmission = RiskTransmissionResult(
        source_node_id="raw_mat_1",
        source_risk_level=0.9,
        target_node_id="batch_1",
        edge_type=EdgeType.USED_IN,
        transmission_coeff=0.8,
        propagated_risk=0.75
    )
    
    alert1 = generator.create_transmission_alert(transmission)
    print(f"  ✓ 传导预警: {alert1.alert_id if alert1 else 'None'}")
    print(f"      严重级别: {alert1.severity.value if alert1 else 'N/A'}")
    
    # 创建级联预警
    alert2 = generator.create_cascade_alert(
        source_node_id="batch_1",
        affected_count=15,
        failure_count=3
    )
    print(f"  ✓ 级联预警: {alert2.alert_id}")
    print(f"      严重级别: {alert2.severity.value}")
    
    # 创建阈值预警
    alert3 = generator.create_threshold_alert(
        node_id="enterprise_1",
        node_risk=0.85,
        threshold=0.7
    )
    print(f"  ✓ 阈值预警: {alert3.alert_id}")
    print(f"      严重级别: {alert3.severity.value}")
    
    # 获取预警摘要
    summary = generator.get_summary()
    print(f"  ✓ 预警总数: {summary.total_count}")
    print(f"  ✓ 活跃预警: {summary.active_count}")
    
    return summary.total_count >= 2


def test_what_if_analysis():
    """测试What-if分析"""
    print("\n=== 测试What-if分析 ===")
    
    edges = [
        Edge("A", "B", EdgeType.SUPPLIES, weight=1.0),
        Edge("A", "C", EdgeType.SUPPLIES, weight=0.9),
        Edge("B", "D", EdgeType.USED_IN, weight=1.0),
        Edge("C", "D", EdgeType.USED_IN, weight=0.8),
        Edge("D", "E", EdgeType.TRANSPORTED_BY, weight=1.0),
    ]
    
    simulator = create_simulator()
    simulator.set_graph_structure(edges)
    
    scenarios = [
        {
            "name": "baseline",
            "initial_risk": 0.8,
            "blocked_edges": [],
            "boosted_nodes": []
        },
        {
            "name": "block_B_to_D",
            "initial_risk": 0.8,
            "blocked_edges": [("B", "D")],
            "boosted_nodes": []
        },
        {
            "name": "boost_protection",
            "initial_risk": 0.8,
            "blocked_edges": [],
            "boosted_nodes": [("D", 0.5)]  # 降低D的传导系数
        }
    ]
    
    result = simulator.run_what_if_analysis("A", scenarios)
    
    print(f"  ✓ 场景数量: {result['scenario_count']}")
    print(f"  ✓ 场景对比:")
    for name, data in result['results'].items():
        print(f"      {name}: 影响 {data['affected_count']} 节点")
    
    comparison = result['comparison']
    print(f"  ✓ 最佳情况: {comparison['best_case']['scenario']} ({comparison['best_case']['affected']} 节点)")
    print(f"  ✓ 最坏情况: {comparison['worst_case']['scenario']} ({comparison['worst_case']['affected']} 节点)")
    
    return result['scenario_count'] == 3


def test_integration():
    """测试整体集成"""
    print("\n=== 测试整体集成 ===")
    
    # 创建完整工作流
    edges = [
        Edge("原料A", "批次1", EdgeType.USED_IN, weight=1.0, features={"usage_ratio": 0.9}),
        Edge("批次1", "物流1", EdgeType.TRANSPORTED_BY, weight=1.0, features={"transport_duration": 4}),
        Edge("物流1", "零售1", EdgeType.DELIVERS_TO, weight=1.0),
        Edge("批次1", "批次2", EdgeType.TEMPORAL_NEXT, weight=0.8),
    ]
    
    # 1. 传导模型
    transmission_model = create_transmission_model()
    
    # 2. 模拟器
    simulator = create_simulator()
    simulator.set_graph_structure(edges)
    
    # 3. 边预测器
    predictor = create_edge_predictor()
    
    # 4. 预警生成器
    alert_generator = create_alert_generator()
    
    # 运行模拟
    sim_result = simulator.run_single_simulation("原料A", 0.9)
    print(f"  ✓ 模拟完成: {len(sim_result.steps)} 步")
    
    # 预测各边风险
    for edge in edges:
        pred = predictor.predict(edge, 0.9)
        if pred.risk_level in ["high", "critical"]:
            # 从预测结果创建预警
            alert_generator.create_prediction_alert(pred)
    
    summary = alert_generator.get_summary()
    print(f"  ✓ 生成预警: {summary.total_count} 个")
    
    return True


def run_all_tests():
    """运行所有测试"""
    print("=" * 50)
    print("风险传导建模模块测试")
    print("=" * 50)
    
    tests = [
        ("传导系数", test_transmission_coefficients),
        ("风险传播", test_risk_propagation),
        ("蒙特卡洛模拟", test_monte_carlo_simulation),
        ("级联失效", test_cascade_failure),
        ("边级预测", test_edge_prediction),
        ("预警生成", test_alert_generation),
        ("What-if分析", test_what_if_analysis),
        ("整体集成", test_integration),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"  ✗ 测试失败: {e}")
            results.append((name, False))
    
    # 打印汇总
    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    
    passed_count = sum(1 for _, p in results if p)
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {status}: {name}")
    
    print(f"\n  总计: {passed_count}/{len(results)} 通过")
    
    return passed_count == len(results)


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
