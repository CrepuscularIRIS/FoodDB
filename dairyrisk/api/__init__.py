"""
API路由模块

包含:
- temporal_routes: 时序图API
- risk_routes: 风险预警API
- graph_routes: 图数据API
"""

try:
    from dairyrisk.api.temporal_routes import setup_temporal_routes
    TEMPORAL_AVAILABLE = True
except ImportError:
    TEMPORAL_AVAILABLE = False

try:
    from dairyrisk.api.risk_routes import setup_risk_routes
    RISK_AVAILABLE = True
except ImportError:
    RISK_AVAILABLE = False

try:
    from dairyrisk.api.graph_routes import setup_graph_routes
    GRAPH_AVAILABLE = True
except ImportError:
    GRAPH_AVAILABLE = False

__all__ = []

if TEMPORAL_AVAILABLE:
    __all__.append('setup_temporal_routes')

if RISK_AVAILABLE:
    __all__.append('setup_risk_routes')

if GRAPH_AVAILABLE:
    __all__.append('setup_graph_routes')
