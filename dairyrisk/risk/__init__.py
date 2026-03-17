"""
风险传导建模模块 (Risk Transmission Modeling)

实现边级风险预测与风险扩散模拟。
包含以下子模块：
- transmission: 风险传导模型
- simulation: 传播模拟引擎
- edge_predictor: 边级风险预测
- alerts: 预警生成器
"""

from dairyrisk.risk.transmission import (
    RISK_TRANSMISSION_COEFFICIENTS,
    RiskTransmissionResult,
    NodeRiskState,
    RiskTransmissionModel,
    create_transmission_model,
)

from dairyrisk.risk.simulation import (
    SimulationMode,
    SimulationConfig,
    SimulationStep,
    SimulationResult,
    MonteCarloResult,
    RiskPropagationSimulator,
    create_simulator,
)

from dairyrisk.risk.edge_predictor import (
    EdgeFeatureVector,
    EdgePredictionResult,
    EdgeRiskNN,
    EdgeRiskPredictor,
    create_edge_predictor,
)

from dairyrisk.risk.alerts import (
    AlertSeverity,
    AlertStatus,
    AlertCategory,
    RiskAlert,
    AlertSummary,
    AlertGenerator,
    create_alert_generator,
)

__all__ = [
    # Transmission
    'RISK_TRANSMISSION_COEFFICIENTS',
    'RiskTransmissionResult',
    'NodeRiskState',
    'RiskTransmissionModel',
    'create_transmission_model',
    # Simulation
    'SimulationMode',
    'SimulationConfig',
    'SimulationStep',
    'SimulationResult',
    'MonteCarloResult',
    'RiskPropagationSimulator',
    'create_simulator',
    # Edge Predictor
    'EdgeFeatureVector',
    'EdgePredictionResult',
    'EdgeRiskNN',
    'EdgeRiskPredictor',
    'create_edge_predictor',
    # Alerts
    'AlertSeverity',
    'AlertStatus',
    'AlertCategory',
    'RiskAlert',
    'AlertSummary',
    'AlertGenerator',
    'create_alert_generator',
]
