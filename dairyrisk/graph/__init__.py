"""
Graph module for dairy supply chain heterogeneous graph.
"""

from dairyrisk.graph.nodes import (
    NodeType,
    EnterpriseScale,
    EnterpriseNode,
    RawMaterialNode,
    ProductionLineNode,
    BatchNode,
    LogisticsNode,
    RetailNode,
    NODE_FEATURE_DIMS,
)

from dairyrisk.graph.edges import (
    EdgeType,
    Edge,
    EDGE_FEATURE_DIMS,
    RISK_TRANSMISSION_CONFIG,
    calculate_risk_transmission_coeff,
    REQUIRED_EDGES,
)

# 时序图模块
try:
    from dairyrisk.graph.temporal import (
        TemporalGraphBuilder,
        TemporalNode,
        TemporalEdge,
        TimeWindow,
        TimeGranularity,
        create_temporal_builder,
    )
    from dairyrisk.graph.incremental import (
        IncrementalUpdateEngine,
        UpdateEvent,
        UpdateEventType,
        IncrementalUpdateResult,
        DataValidationResult,
    )
    TEMPORAL_AVAILABLE = True
except ImportError:
    TEMPORAL_AVAILABLE = False

__all__ = [
    # Nodes
    'NodeType',
    'EnterpriseScale',
    'EnterpriseNode',
    'RawMaterialNode',
    'ProductionLineNode',
    'BatchNode',
    'LogisticsNode',
    'RetailNode',
    'NODE_FEATURE_DIMS',
    # Edges
    'EdgeType',
    'Edge',
    'EDGE_FEATURE_DIMS',
    'RISK_TRANSMISSION_CONFIG',
    'calculate_risk_transmission_coeff',
    'REQUIRED_EDGES',
]

# 时序图导出（如果可用）
if TEMPORAL_AVAILABLE:
    __all__.extend([
        # Temporal
        'TemporalGraphBuilder',
        'TemporalNode',
        'TemporalEdge',
        'TimeWindow',
        'TimeGranularity',
        'create_temporal_builder',
        # Incremental
        'IncrementalUpdateEngine',
        'UpdateEvent',
        'UpdateEventType',
        'IncrementalUpdateResult',
        'DataValidationResult',
    ])
