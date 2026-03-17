"""
风险传导建模 - 使用示例

演示如何使用Phase 5实现的风险传导功能。
"""

import sys
sys.path.insert(0, '/home/yarizakurahime/data/dairy_supply_chain_risk')

from dairyrisk.graph.edges import EdgeType, Edge
from dairyrisk.risk.transmission import create_transmission_model
from dairyrisk.risk.simulation import create_simulator, SimulationConfig
from dairyrisk.risk.edge_predictor import create_edge_predictor
from dairyrisk.risk.alerts import create_alert_generator


def example_1_basic_transmission():
    """示例1: 基础风险传导计算"""
    print("\n=== 示例1: 基础风险传导计算 ===")
    
    # 创建传导模型
    model = create_transmission_model()
    
    # 查看各边类型的传导系数
    print("\n边类型传导系数:")
    edge_types = [
        (EdgeType.SUPPLIES, "供应关系"),
        (EdgeType.USED_IN, "原料到批次"),
        (EdgeType.PRODUCES, "生产线到批次"),
        (EdgeType.TRANSPORTED_BY, "物流风险"),
        (EdgeType.TEMPORAL_NEXT, "时序传导"),
    ]
    
    for edge_type, desc in edge_types:
        coeff = model.get_transmission_coefficient(edge_type)
        print(f"  {desc}: {coeff:.2f}")
    
    # 计算风险传导
    source_risk = 0.8
    propagated = model.calculate_propagated_risk(
        source_risk, EdgeType.USED_IN, distance=1
    )
    print(f"\n风险传导示例:")
    print(f"  源风险: {source_risk}")
    print(f"  边类型: USED_IN (原料到批次)")
    print(f"  传导后风险: {propagated:.4f}")


def example_2_monte_carlo_simulation():
    """示例2: 蒙特卡洛模拟"""
    print("\n=== 示例2: 蒙特卡洛模拟 ===")
    
    # 构建测试图
    edges = [
        Edge("原料供应商", "原料A", EdgeType.SUPPLIES, weight=1.0),
        Edge("原料A", "批次1", EdgeType.USED_IN, weight=1.0),
        Edge("原料A", "批次2", EdgeType.USED_IN, weight=0.8),
        Edge("生产线1", "批次1", EdgeType.PRODUCES, weight=1.0),
        Edge("批次1", "物流1", EdgeType.TRANSPORTED_BY, weight=1.0),
        Edge("批次2", "物流1", EdgeType.TRANSPORTED_BY, weight=0.9),
        Edge("物流1", "零售店1", EdgeType.DELIVERS_TO, weight=1.0),
        Edge("批次1", "批次2", EdgeType.TEMPORAL_NEXT, weight=0.5),
    ]
    
    # 创建模拟器
    simulator = create_simulator()
    simulator.set_graph_structure(edges)
    
    # 运行蒙特卡洛模拟
    print("\n运行蒙特卡洛模拟 (50轮)...")
    result = simulator.run_monte_carlo("原料A", 0.9, num_rounds=50)
    
    print(f"  平均影响节点: {result.mean_affected_nodes:.2f}")
    print(f"  标准差: {result.std_affected_nodes:.2f}")
    print(f"  95%置信区间: [{result.confidence_interval_95[0]:.2f}, {result.confidence_interval_95[1]:.2f}]")
    print(f"  平均失效数: {result.mean_failure_count:.2f}")


def example_3_edge_prediction():
    """示例3: 边级风险预测"""
    print("\n=== 示例3: 边级风险预测 ===")
    
    # 创建预测器
    predictor = create_edge_predictor(model_type="neural_network")
    
    # 创建测试边
    edge = Edge(
        src_id="原料A",
        dst_id="批次1",
        edge_type=EdgeType.USED_IN,
        weight=1.0,
        features={"usage_ratio": 0.85, "raw_quality": 0.7}
    )
    
    # 预测不同源风险下的传导概率
    print("\n不同源风险下的传导概率:")
    for risk in [0.2, 0.5, 0.8, 0.95]:
        result = predictor.predict(edge, risk)
        print(f"  源风险 {risk:.2f} → 传导概率 {result.transmission_probability:.2%} ({result.risk_level})")


def example_4_alert_generation():
    """示例4: 预警生成"""
    print("\n=== 示例4: 预警生成 ===")
    
    generator = create_alert_generator()
    
    # 创建传导预警
    from dairyrisk.risk.transmission import RiskTransmissionResult
    
    transmission = RiskTransmissionResult(
        source_node_id="原料A",
        source_risk_level=0.9,
        target_node_id="批次1",
        edge_type=EdgeType.USED_IN,
        transmission_coeff=0.8,
        propagated_risk=0.75
    )
    
    alert1 = generator.create_transmission_alert(transmission)
    if alert1:
        print(f"\n传导预警:")
        print(f"  ID: {alert1.alert_id}")
        print(f"  标题: {alert1.title}")
        print(f"  严重级别: {alert1.severity.value}")
        print(f"  风险分数: {alert1.risk_score:.2f}")
    
    # 创建级联预警
    alert2 = generator.create_cascade_alert(
        source_node_id="批次1",
        affected_count=15,
        failure_count=5
    )
    print(f"\n级联失效预警:")
    print(f"  ID: {alert2.alert_id}")
    print(f"  标题: {alert2.title}")
    print(f"  严重级别: {alert2.severity.value}")
    
    # 获取预警摘要
    summary = generator.get_summary()
    print(f"\n预警摘要:")
    print(f"  总数: {summary.total_count}")
    print(f"  活跃: {summary.active_count}")
    print(f"  按严重级别: {summary.by_severity}")


def example_5_what_if_analysis():
    """示例5: What-if分析"""
    print("\n=== 示例5: What-if分析 ===")
    
    # 构建测试图
    edges = [
        Edge("A", "B", EdgeType.SUPPLIES, weight=1.0),
        Edge("A", "C", EdgeType.SUPPLIES, weight=0.9),
        Edge("B", "D", EdgeType.USED_IN, weight=1.0),
        Edge("C", "D", EdgeType.USED_IN, weight=0.8),
        Edge("D", "E", EdgeType.TRANSPORTED_BY, weight=1.0),
    ]
    
    simulator = create_simulator()
    simulator.set_graph_structure(edges)
    
    # 定义场景
    scenarios = [
        {
            "name": "基准情况",
            "initial_risk": 0.8,
            "blocked_edges": [],
            "boosted_nodes": []
        },
        {
            "name": "阻断B到D的传导",
            "initial_risk": 0.8,
            "blocked_edges": [("B", "D")],
            "boosted_nodes": []
        },
        {
            "name": "增强D的防护",
            "initial_risk": 0.8,
            "blocked_edges": [],
            "boosted_nodes": [("D", 0.3)]  # 降低传导系数到30%
        }
    ]
    
    result = simulator.run_what_if_analysis("A", scenarios)
    
    print("\n场景对比:")
    for name, data in result['results'].items():
        print(f"  {name}: 影响 {data['affected_count']} 节点")
    
    comparison = result['comparison']
    print(f"\n最优情况: {comparison['best_case']['scenario']}")
    print(f"最差情况: {comparison['worst_case']['scenario']}")


def example_6_propagation_path():
    """示例6: 传播路径分析"""
    print("\n=== 示例6: 传播路径分析 ===")
    
    edges = [
        Edge("原料", "批次1", EdgeType.USED_IN, weight=1.0),
        Edge("批次1", "物流", EdgeType.TRANSPORTED_BY, weight=1.0),
        Edge("物流", "零售", EdgeType.DELIVERS_TO, weight=1.0),
        Edge("原料", "批次2", EdgeType.USED_IN, weight=0.8),
        Edge("批次2", "物流", EdgeType.TRANSPORTED_BY, weight=0.9),
    ]
    
    model = create_transmission_model()
    simulator = create_simulator()
    simulator.set_graph_structure(edges)
    
    # 向下游追踪
    downstream = model.trace_downstream(
        "原料", simulator._graph_edges, max_depth=3
    )
    
    print("\n从'原料'向下游传播路径:")
    for i, path in enumerate(downstream[:5], 1):
        nodes = ["原料"] + [p[0] for p in path]
        coeffs = [p[2] for p in path]
        print(f"  路径{i}: {' → '.join(nodes)}")
        print(f"         传导系数: {[f'{c:.2f}' for c in coeffs]}")


def main():
    """运行所有示例"""
    print("=" * 60)
    print("风险传导建模 - 使用示例")
    print("=" * 60)
    
    example_1_basic_transmission()
    example_2_monte_carlo_simulation()
    example_3_edge_prediction()
    example_4_alert_generation()
    example_5_what_if_analysis()
    example_6_propagation_path()
    
    print("\n" + "=" * 60)
    print("所有示例运行完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
