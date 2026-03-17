"""
风险预警生成器 (Risk Alert Generator)

生成高风险预警、预警等级评估和预警聚合。
支持实时预警和历史预警查询。
"""

from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import uuid
import json
from collections import defaultdict

from dairyrisk.graph.edges import EdgeType
from dairyrisk.graph.nodes import NodeType
from dairyrisk.risk.transmission import RiskTransmissionResult
from dairyrisk.risk.edge_predictor import EdgePredictionResult


class AlertSeverity(Enum):
    """预警严重级别"""
    INFO = "info"                 # 信息提示
    LOW = "low"                   # 低风险
    MEDIUM = "medium"             # 中风险
    HIGH = "high"                 # 高风险
    CRITICAL = "critical"         # 严重


class AlertStatus(Enum):
    """预警状态"""
    ACTIVE = "active"             # 活跃
    ACKNOWLEDGED = "acknowledged" # 已确认
    RESOLVED = "resolved"         # 已解决
    EXPIRED = "expired"           # 已过期


class AlertCategory(Enum):
    """预警类别"""
    TRANSMISSION = "transmission"     # 风险传导
    CASCADE = "cascade"               # 级联失效
    THRESHOLD = "threshold"           # 阈值突破
    PATTERN = "pattern"               # 模式异常
    PREDICTION = "prediction"         # 预测预警


@dataclass
class RiskAlert:
    """风险预警"""
    alert_id: str
    title: str
    description: str
    severity: AlertSeverity
    category: AlertCategory
    status: AlertStatus
    
    # 关联节点
    source_node_id: Optional[str] = None
    target_node_id: Optional[str] = None
    affected_nodes: List[str] = field(default_factory=list)
    
    # 风险指标
    risk_score: float = 0.0
    risk_probability: float = 0.0
    
    # 时间信息
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    
    # 附加数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.expires_at is None:
            # 默认24小时后过期
            self.expires_at = self.created_at + timedelta(hours=24)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "category": self.category.value,
            "status": self.status.value,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "affected_nodes": self.affected_nodes,
            "risk_score": round(self.risk_score, 4),
            "risk_probability": round(self.risk_probability, 4),
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata
        }
    
    def acknowledge(self):
        """确认预警"""
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.now()
    
    def resolve(self):
        """解决预警"""
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.now()
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.expires_at:
            return datetime.now() > self.expires_at
        return False


@dataclass
class AlertSummary:
    """预警摘要"""
    total_count: int = 0
    active_count: int = 0
    by_severity: Dict[str, int] = field(default_factory=dict)
    by_category: Dict[str, int] = field(default_factory=dict)
    recent_alerts: List[RiskAlert] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_count": self.total_count,
            "active_count": self.active_count,
            "by_severity": self.by_severity,
            "by_category": self.by_category,
            "recent_alerts": [alert.to_dict() for alert in self.recent_alerts]
        }


class AlertGenerator:
    """
    预警生成器
    
    根据风险传导结果、预测结果和模拟结果生成预警。
    支持预警聚合、去重和升级。
    """
    
    # 严重级别阈值
    SEVERITY_THRESHOLDS = {
        AlertSeverity.CRITICAL: 0.9,
        AlertSeverity.HIGH: 0.7,
        AlertSeverity.MEDIUM: 0.5,
        AlertSeverity.LOW: 0.3,
    }
    
    def __init__(self, alert_ttl_hours: int = 24):
        """
        初始化预警生成器
        
        Args:
            alert_ttl_hours: 预警默认存活时间（小时）
        """
        self.alert_ttl_hours = alert_ttl_hours
        self._alerts: Dict[str, RiskAlert] = {}
        self._alert_history: List[RiskAlert] = []
        
        # 用于去重的集合
        self._active_signatures: Set[str] = set()
    
    def _generate_alert_id(self) -> str:
        """生成预警ID"""
        return f"alert_{uuid.uuid4().hex[:12]}_{int(datetime.now().timestamp())}"
    
    def _get_severity(self, risk_score: float) -> AlertSeverity:
        """根据风险分数确定严重级别"""
        for severity, threshold in sorted(
            self.SEVERITY_THRESHOLDS.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            if risk_score >= threshold:
                return severity
        return AlertSeverity.INFO
    
    def _generate_signature(
        self,
        source_node_id: str,
        target_node_id: Optional[str],
        category: AlertCategory
    ) -> str:
        """生成预警签名（用于去重）"""
        return f"{source_node_id}:{target_node_id or 'none'}:{category.value}"
    
    def create_transmission_alert(
        self,
        transmission_result: RiskTransmissionResult,
        additional_context: Optional[Dict] = None
    ) -> Optional[RiskAlert]:
        """
        从传导结果创建预警
        
        Args:
            transmission_result: 风险传导结果
            additional_context: 附加上下文
            
        Returns:
            预警对象（如达到阈值）
        """
        risk_score = transmission_result.propagated_risk
        
        if risk_score < 0.3:  # 低于最低阈值
            return None
        
        severity = self._get_severity(risk_score)
        
        # 检查重复
        signature = self._generate_signature(
            transmission_result.source_node_id,
            transmission_result.target_node_id,
            AlertCategory.TRANSMISSION
        )
        
        if signature in self._active_signatures:
            return None  # 已存在相同预警
        
        alert = RiskAlert(
            alert_id=self._generate_alert_id(),
            title=f"风险传导预警: {transmission_result.source_node_id} → {transmission_result.target_node_id}",
            description=f"检测到从 {transmission_result.source_node_id} 到 {transmission_result.target_node_id} 的风险传导，传导系数 {transmission_result.transmission_coeff:.2f}",
            severity=severity,
            category=AlertCategory.TRANSMISSION,
            status=AlertStatus.ACTIVE,
            source_node_id=transmission_result.source_node_id,
            target_node_id=transmission_result.target_node_id,
            risk_score=risk_score,
            risk_probability=transmission_result.transmission_coeff,
            metadata={
                "transmission": transmission_result.to_dict(),
                "context": additional_context or {}
            }
        )
        
        self._alerts[alert.alert_id] = alert
        self._active_signatures.add(signature)
        
        return alert
    
    def create_prediction_alert(
        self,
        prediction_result: EdgePredictionResult,
        additional_context: Optional[Dict] = None
    ) -> Optional[RiskAlert]:
        """
        从预测结果创建预警
        
        Args:
            prediction_result: 边预测结果
            additional_context: 附加上下文
            
        Returns:
            预警对象
        """
        probability = prediction_result.transmission_probability
        
        if probability < 0.5:  # 低于50%不预警
            return None
        
        severity = self._get_severity(probability)
        
        alert = RiskAlert(
            alert_id=self._generate_alert_id(),
            title=f"风险预测预警: {prediction_result.source_node_id} → {prediction_result.target_node_id}",
            description=f"预测边 {prediction_result.edge_id} 有风险传导可能，概率 {probability:.2%}",
            severity=severity,
            category=AlertCategory.PREDICTION,
            status=AlertStatus.ACTIVE,
            source_node_id=prediction_result.source_node_id,
            target_node_id=prediction_result.target_node_id,
            risk_score=probability,
            risk_probability=prediction_result.confidence,
            metadata={
                "prediction": prediction_result.to_dict(),
                "context": additional_context or {}
            }
        )
        
        self._alerts[alert.alert_id] = alert
        
        return alert
    
    def create_cascade_alert(
        self,
        source_node_id: str,
        affected_count: int,
        failure_count: int,
        simulation_result: Optional[Dict] = None
    ) -> RiskAlert:
        """
        创建级联失效预警
        
        Args:
            source_node_id: 源节点ID
            affected_count: 受影响节点数
            failure_count: 失效节点数
            simulation_result: 模拟结果
            
        Returns:
            预警对象
        """
        # 根据影响程度确定严重性
        if failure_count >= 10:
            severity = AlertSeverity.CRITICAL
        elif failure_count >= 5:
            severity = AlertSeverity.HIGH
        elif failure_count >= 2:
            severity = AlertSeverity.MEDIUM
        else:
            severity = AlertSeverity.LOW
        
        risk_score = min(1.0, failure_count / 10 + affected_count / 100)
        
        alert = RiskAlert(
            alert_id=self._generate_alert_id(),
            title=f"级联失效预警: {source_node_id}",
            description=f"节点 {source_node_id} 可能引发级联失效，预计影响 {affected_count} 个节点，{failure_count} 个失效",
            severity=severity,
            category=AlertCategory.CASCADE,
            status=AlertStatus.ACTIVE,
            source_node_id=source_node_id,
            affected_nodes=[source_node_id],
            risk_score=risk_score,
            risk_probability=min(1.0, affected_count / 50),
            metadata={
                "affected_count": affected_count,
                "failure_count": failure_count,
                "simulation": simulation_result or {}
            }
        )
        
        self._alerts[alert.alert_id] = alert
        
        return alert
    
    def create_threshold_alert(
        self,
        node_id: str,
        node_risk: float,
        threshold: float,
        metric_name: str = "risk_score"
    ) -> RiskAlert:
        """
        创建阈值突破预警
        
        Args:
            node_id: 节点ID
            node_risk: 节点风险值
            threshold: 阈值
            metric_name: 指标名称
            
        Returns:
            预警对象
        """
        severity = self._get_severity(node_risk)
        
        alert = RiskAlert(
            alert_id=self._generate_alert_id(),
            title=f"阈值突破预警: {node_id}",
            description=f"节点 {node_id} 的 {metric_name} 达到 {node_risk:.2f}，超过阈值 {threshold:.2f}",
            severity=severity,
            category=AlertCategory.THRESHOLD,
            status=AlertStatus.ACTIVE,
            source_node_id=node_id,
            risk_score=node_risk,
            risk_probability=1.0,
            metadata={
                "threshold": threshold,
                "metric_name": metric_name,
                "excess_ratio": node_risk / threshold if threshold > 0 else 0
            }
        )
        
        self._alerts[alert.alert_id] = alert
        
        return alert
    
    def get_alert(self, alert_id: str) -> Optional[RiskAlert]:
        """获取单个预警"""
        return self._alerts.get(alert_id)
    
    def get_active_alerts(
        self,
        severity_filter: Optional[List[AlertSeverity]] = None,
        category_filter: Optional[List[AlertCategory]] = None
    ) -> List[RiskAlert]:
        """
        获取活跃预警列表
        
        Args:
            severity_filter: 严重级别过滤
            category_filter: 类别过滤
            
        Returns:
            预警列表
        """
        alerts = [
            alert for alert in self._alerts.values()
            if alert.status == AlertStatus.ACTIVE and not alert.is_expired()
        ]
        
        if severity_filter:
            alerts = [a for a in alerts if a.severity in severity_filter]
        
        if category_filter:
            alerts = [a for a in alerts if a.category in category_filter]
        
        # 按严重级别和时间排序
        severity_order = {
            AlertSeverity.CRITICAL: 0,
            AlertSeverity.HIGH: 1,
            AlertSeverity.MEDIUM: 2,
            AlertSeverity.LOW: 3,
            AlertSeverity.INFO: 4
        }
        alerts.sort(key=lambda a: (severity_order.get(a.severity, 5), a.created_at), reverse=False)
        
        return alerts
    
    def get_alert_history(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[RiskAlert]:
        """
        获取历史预警
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            limit: 限制数量
            
        Returns:
            历史预警列表
        """
        history = list(self._alerts.values())
        
        if start_time:
            history = [a for a in history if a.created_at >= start_time]
        
        if end_time:
            history = [a for a in history if a.created_at <= end_time]
        
        history.sort(key=lambda a: a.created_at, reverse=True)
        
        return history[:limit]
    
    def get_summary(self) -> AlertSummary:
        """获取预警摘要"""
        all_alerts = list(self._alerts.values())
        active_alerts = self.get_active_alerts()
        
        by_severity = defaultdict(int)
        by_category = defaultdict(int)
        
        for alert in all_alerts:
            by_severity[alert.severity.value] += 1
            by_category[alert.category.value] += 1
        
        return AlertSummary(
            total_count=len(all_alerts),
            active_count=len(active_alerts),
            by_severity=dict(by_severity),
            by_category=dict(by_category),
            recent_alerts=active_alerts[:10]
        )
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认预警"""
        alert = self._alerts.get(alert_id)
        if alert and alert.status == AlertStatus.ACTIVE:
            alert.acknowledge()
            return True
        return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """解决预警"""
        alert = self._alerts.get(alert_id)
        if alert:
            alert.resolve()
            # 从活跃签名中移除
            signature = self._generate_signature(
                alert.source_node_id,
                alert.target_node_id,
                alert.category
            )
            self._active_signatures.discard(signature)
            return True
        return False
    
    def cleanup_expired_alerts(self) -> int:
        """
        清理过期预警
        
        Returns:
            清理数量
        """
        expired_ids = [
            alert_id for alert_id, alert in self._alerts.items()
            if alert.is_expired() and alert.status == AlertStatus.ACTIVE
        ]
        
        for alert_id in expired_ids:
            alert = self._alerts[alert_id]
            alert.status = AlertStatus.EXPIRED
            
            # 从活跃签名中移除
            signature = self._generate_signature(
                alert.source_node_id,
                alert.target_node_id,
                alert.category
            )
            self._active_signatures.discard(signature)
        
        return len(expired_ids)
    
    def export_alerts(self, filepath: str):
        """导出预警到文件"""
        data = {
            "export_time": datetime.now().isoformat(),
            "alerts": [alert.to_dict() for alert in self._alerts.values()]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def import_alerts(self, filepath: str):
        """从文件导入预警"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 这里可以实现导入逻辑
        # 为简化，目前只返回导入的预警数量
        return len(data.get("alerts", []))


def create_alert_generator(alert_ttl_hours: int = 24) -> AlertGenerator:
    """
    创建预警生成器
    
    Args:
        alert_ttl_hours: 预警存活时间
        
    Returns:
        AlertGenerator实例
    """
    return AlertGenerator(alert_ttl_hours=alert_ttl_hours)


# 导出
__all__ = [
    'AlertSeverity',
    'AlertStatus',
    'AlertCategory',
    'RiskAlert',
    'AlertSummary',
    'AlertGenerator',
    'create_alert_generator'
]
