# Phase 5: 风险传导建模 (Risk Transmission Modeling)

实现边级风险预测与风险扩散模拟，基于方案文档5.7章节和中期工作建议。

## 模块结构

```
dairyrisk/risk/
├── __init__.py           # 模块导出
├── transmission.py       # 风险传导模型
├── simulation.py         # 传播模拟引擎
├── edge_predictor.py     # 边级风险预测
├── alerts.py             # 预警生成器
├── examples.py           # 使用示例
└── test_risk_transmission.py  # 测试脚本

dairyrisk/api/
└── risk_routes.py        # 风险预警API
```

## 核心功能

### 1. 风险传导系数计算

```python
from dairyrisk.risk.transmission import RISK_TRANSMISSION_COEFFICIENTS

# 边类型到传导系数的映射
RISK_TRANSMISSION_COEFFICIENTS = {
    EdgeType.SUPPLIES: 0.7,          # 供应关系
    EdgeType.USED_IN: 0.8,           # 原料到批次
    EdgeType.PRODUCES: 0.75,         # 生产线到批次
    EdgeType.TRANSPORTED_BY: 0.6,    # 物流风险
    EdgeType.TEMPORAL_NEXT: 0.5,     # 时序传导
}
```

### 2. 传播模拟引擎

```python
from dairyrisk.risk.simulation import create_simulator, SimulationConfig

# 创建模拟器
config = SimulationConfig(num_rounds=100, max_steps=10)
simulator = create_simulator(config)

# 运行蒙特卡洛模拟
result = simulator.run_monte_carlo("source_node", 0.8, num_rounds=100)
print(f"平均影响节点: {result.mean_affected_nodes}")
print(f"95%置信区间: {result.confidence_interval_95}")
```

### 3. 边级风险预测

```python
from dairyrisk.risk.edge_predictor import create_edge_predictor
from dairyrisk.graph.edges import Edge, EdgeType

# 创建预测器
predictor = create_edge_predictor(model_type="neural_network")

# 预测边风险
edge = Edge("src", "dst", EdgeType.USED_IN, weight=1.0)
result = predictor.predict(edge, source_risk=0.9)
print(f"传导概率: {result.transmission_probability}")
print(f"风险等级: {result.risk_level}")
```

### 4. 预警生成

```python
from dairyrisk.risk.alerts import create_alert_generator

generator = create_alert_generator()

# 从传导结果创建预警
alert = generator.create_transmission_alert(transmission_result)

# 创建级联预警
alert = generator.create_cascade_alert(node_id, affected_count, failure_count)

# 获取活跃预警
active_alerts = generator.get_active_alerts()
```

## API接口

### 风险模拟

- `POST /api/risk/simulate` - 模拟风险传播
  ```json
  {
    "source_node_id": "node_1",
    "initial_risk": 0.8,
    "mode": "monte_carlo",
    "num_rounds": 100,
    "max_steps": 10
  }
  ```

### 传播路径

- `GET /api/risk/propagation/{node_id}?direction=downstream&max_depth=5` - 获取传播路径

### 影响评估

- `GET /api/risk/impact/{node_id}?node_risk=0.8&max_depth=3` - 影响范围评估

### 边风险预测

- `POST /api/risk/edge/predict` - 预测边风险传导
  ```json
  {
    "edge_type": "USED_IN",
    "source_node_id": "raw_mat_1",
    "target_node_id": "batch_1",
    "source_risk": 0.9
  }
  ```

### 预警管理

- `GET /api/risk/alert?severity=high,critical` - 获取预警列表
- `GET /api/risk/alert/summary` - 预警摘要
- `POST /api/risk/alert/{id}/acknowledge` - 确认预警
- `POST /api/risk/alert/{id}/resolve` - 解决预警

### WebSocket

- `WS /api/risk/ws` - 实时预警推送

### What-if分析

- `POST /api/risk/what-if` - 假设场景分析
  ```json
  {
    "source_node_id": "node_1",
    "scenarios": [
      {
        "name": "阻断关键边",
        "initial_risk": 0.8,
        "blocked_edges": [["A", "B"]],
        "boosted_nodes": []
      }
    ]
  }
  ```

## 风险传导路径

```
原料风险 ──[0.8]──→ 批次风险 ──[0.6]──→ 物流风险 ──[0.5]──→ 零售风险
    │                      │
    │                      ↓
生产线风险 ──[0.75]──→ 批次风险
```

## 验收标准检查

- [x] 风险传导系数正确计算（按边类型）
- [x] 传播模拟支持多轮次（默认100轮）
- [x] 边级风险预测（神经网络/逻辑回归模型）
- [x] 预警API正常工作（实时/历史查询）
- [x] WebSocket推送高风险预警
- [x] 支持"What-if"假设分析
- [x] 与现有异构图兼容
- [x] 与时序模块联动（传播模拟考虑时间）

## 使用示例

运行示例脚本:

```bash
cd /home/yarizakurahime/data/dairy_supply_chain_risk
python dairyrisk/risk/examples.py
```

## 依赖

- PyTorch (神经网络模型)
- NumPy (数值计算)
- scikit-learn (可选，逻辑回归模型)
- FastAPI (API服务)
