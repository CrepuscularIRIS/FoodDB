"""
弱监督标签生成模块 (2.3节)

基于微生物生长机理的多层次标签融合系统
- 显式标签 (强监督)
- 弱监督标签 (规则引擎)
- 自监督信号
- 生成式标签

作者: DairyRisk Team
日期: 2025-03
"""

import numpy as np
import torch
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class LabelSource(Enum):
    """标签来源类型"""
    EXPLICIT = "explicit"           # 显式标签（政府抽检、企业自检）
    WEAK_SUPERVISION = "weak"       # 弱监督标签（规则引擎）
    SELF_SUPERVISED = "self"        # 自监督信号
    GENERATIVE = "generative"       # 生成式标签


class RiskRule(Enum):
    """风险规则类型"""
    HIGH_TEMP_REPRODUCTION = "high_temp_reproduction"      # 高温繁殖
    DURATION_RISK = "duration_risk"                        # 时长风险
    CLEANLINESS_RISK = "cleanliness_risk"                  # 洁净度风险
    STERILIZATION_FLUCTUATION = "sterilization_fluctuation" # 杀菌波动
    SUMMER_RISK = "summer_risk"                            # 夏季风险
    RAW_MATERIAL_CONTAMINATION = "raw_material_contamination" # 原料污染


@dataclass
class RiskLabel:
    """风险标签数据类"""
    risk_score: float              # 风险得分 (0-1)
    confidence: float              # 置信度 (0-1)
    source: LabelSource            # 标签来源
    rule_name: Optional[str] = None  # 规则名称（如果是规则生成）
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    
    def __post_init__(self):
        """验证数据范围"""
        self.risk_score = np.clip(self.risk_score, 0.0, 1.0)
        self.confidence = np.clip(self.confidence, 0.0, 1.0)


class RuleEngine:
    """
    基于微生物生长机理的规则引擎
    
    规则依据:
    - 微生物最适生长温度: 20-37°C
    - 微生物对数生长期: 4-6h
    - GMP洁净度标准
    - D值与温度负相关
    - HACCP原理
    """
    
    # 规则参数配置
    RULE_PARAMS = {
        RiskRule.HIGH_TEMP_REPRODUCTION: {
            "temp_threshold": 8.0,          # 温度阈值(°C)
            "temp_max": 18.0,               # 最大计算温度
            "description": "运输温度>8°C时微生物繁殖风险"
        },
        RiskRule.DURATION_RISK: {
            "temp_threshold": 6.0,          # 温度阈值(°C)
            "duration_threshold": 4.0,      # 时长阈值(h)
            "duration_max": 8.0,            # 最大计算时长
            "description": "运输时间>4h且温度>6°C"
        },
        RiskRule.CLEANLINESS_RISK: {
            "level_a": 0.0,                 # A级风险
            "level_b": 0.1,                 # B级风险
            "level_c": 0.5,                 # C级风险
            "level_d": 0.8,                 # D级风险
            "description": "基于GMP洁净度等级"
        },
        RiskRule.STERILIZATION_FLUCTUATION: {
            "fluctuation_threshold": 3.0,   # 温度波动阈值(°C)
            "fluctuation_max": 6.0,         # 最大波动
            "description": "杀菌温度波动>3°C"
        },
        RiskRule.SUMMER_RISK: {
            "summer_months": [6, 7, 8],     # 夏季月份
            "base_risk": 0.3,               # 基础风险
            "description": "6-8月高温高湿利于繁殖"
        },
        RiskRule.RAW_MATERIAL_CONTAMINATION: {
            "colony_threshold": 50000,      # 菌落阈值
            "colony_max": 100000,           # 最大菌落数
            "description": "原料菌落>50000"
        }
    }
    
    def __init__(self):
        """初始化规则引擎"""
        self.rules = {
            RiskRule.HIGH_TEMP_REPRODUCTION: self._high_temp_reproduction,
            RiskRule.DURATION_RISK: self._duration_risk,
            RiskRule.CLEANLINESS_RISK: self._cleanliness_risk,
            RiskRule.STERILIZATION_FLUCTUATION: self._sterilization_fluctuation,
            RiskRule.SUMMER_RISK: self._summer_risk,
            RiskRule.RAW_MATERIAL_CONTAMINATION: self._raw_material_contamination
        }
    
    def evaluate(self, data: Dict[str, Any]) -> Dict[RiskRule, RiskLabel]:
        """
        评估所有规则
        
        Args:
            data: 输入数据字典，包含各种特征
            
        Returns:
            各规则的风险标签字典
        """
        results = {}
        for rule_type, rule_func in self.rules.items():
            try:
                label = rule_func(data)
                if label is not None:
                    results[rule_type] = label
            except Exception as e:
                logger.warning(f"规则 {rule_type.value} 评估失败: {e}")
        return results
    
    def _high_temp_reproduction(self, data: Dict[str, Any]) -> Optional[RiskLabel]:
        """
        高温繁殖风险
        
        机理: 微生物最适生长温度20-37°C，温度越高繁殖越快
        """
        params = self.RULE_PARAMS[RiskRule.HIGH_TEMP_REPRODUCTION]
        
        # 获取运输温度
        temp = data.get('transport_temp') or data.get('storage_temp')
        if temp is None:
            return None
        
        temp_threshold = params["temp_threshold"]
        temp_max = params["temp_max"]
        
        if temp <= temp_threshold:
            return RiskLabel(
                risk_score=0.0,
                confidence=0.8,
                source=LabelSource.WEAK_SUPERVISION,
                rule_name=RiskRule.HIGH_TEMP_REPRODUCTION.value,
                metadata={"temp": temp, "threshold": temp_threshold}
            )
        
        # 风险计算: min(1.0, (T-8)/10)
        risk = min(1.0, (temp - temp_threshold) / (temp_max - temp_threshold))
        confidence = 0.7 if temp < 20 else 0.9  # 高温时置信度更高
        
        return RiskLabel(
            risk_score=risk,
            confidence=confidence,
            source=LabelSource.WEAK_SUPERVISION,
            rule_name=RiskRule.HIGH_TEMP_REPRODUCTION.value,
            metadata={"temp": temp, "calculation": f"min(1, ({temp}-{temp_threshold})/10)"}
        )
    
    def _duration_risk(self, data: Dict[str, Any]) -> Optional[RiskLabel]:
        """
        时长风险
        
        机理: 微生物对数生长期4-6h，超过阈值时长风险增加
        """
        params = self.RULE_PARAMS[RiskRule.DURATION_RISK]
        
        duration = data.get('transport_duration') or data.get('storage_duration')
        temp = data.get('transport_temp') or data.get('storage_temp')
        
        if duration is None or temp is None:
            return None
        
        temp_threshold = params["temp_threshold"]
        duration_threshold = params["duration_threshold"]
        duration_max = params["duration_max"]
        
        # 只有温度超过阈值且时长超过阈值才计算风险
        if temp <= temp_threshold or duration <= duration_threshold:
            return None
        
        # 风险计算: min(1.0, 时长/8)
        risk = min(1.0, duration / duration_max)
        confidence = 0.75
        
        return RiskLabel(
            risk_score=risk,
            confidence=confidence,
            source=LabelSource.WEAK_SUPERVISION,
            rule_name=RiskRule.DURATION_RISK.value,
            metadata={"duration": duration, "temp": temp}
        )
    
    def _cleanliness_risk(self, data: Dict[str, Any]) -> Optional[RiskLabel]:
        """
        洁净度风险
        
        机理: 基于GMP洁净度标准，A级最安全，D级风险最高
        """
        params = self.RULE_PARAMS[RiskRule.CLEANLINESS_RISK]
        
        cleanliness = data.get('cleanliness_level') or data.get('cleanliness')
        if cleanliness is None:
            return None
        
        cleanliness = str(cleanliness).upper()
        
        risk_map = {
            'A': params["level_a"],
            'B': params["level_b"],
            'C': params["level_c"],
            'D': params["level_d"]
        }
        
        risk = risk_map.get(cleanliness, 0.5)
        confidence = 0.85
        
        return RiskLabel(
            risk_score=risk,
            confidence=confidence,
            source=LabelSource.WEAK_SUPERVISION,
            rule_name=RiskRule.CLEANLINESS_RISK.value,
            metadata={"cleanliness_level": cleanliness}
        )
    
    def _sterilization_fluctuation(self, data: Dict[str, Any]) -> Optional[RiskLabel]:
        """
        杀菌波动风险
        
        机理: D值与温度负相关，温度波动导致杀菌不彻底
        """
        params = self.RULE_PARAMS[RiskRule.STERILIZATION_FLUCTUATION]
        
        temp_std = data.get('pasteurization_temp_std') or data.get('temp_fluctuation')
        if temp_std is None:
            return None
        
        fluctuation_threshold = params["fluctuation_threshold"]
        fluctuation_max = params["fluctuation_max"]
        
        if temp_std <= fluctuation_threshold:
            return RiskLabel(
                risk_score=0.0,
                confidence=0.8,
                source=LabelSource.WEAK_SUPERVISION,
                rule_name=RiskRule.STERILIZATION_FLUCTUATION.value,
                metadata={"temp_std": temp_std}
            )
        
        # 风险计算: min(1.0, 波动/6)
        risk = min(1.0, temp_std / fluctuation_max)
        confidence = 0.8
        
        return RiskLabel(
            risk_score=risk,
            confidence=confidence,
            source=LabelSource.WEAK_SUPERVISION,
            rule_name=RiskRule.STERILIZATION_FLUCTUATION.value,
            metadata={"temp_std": temp_std}
        )
    
    def _summer_risk(self, data: Dict[str, Any]) -> Optional[RiskLabel]:
        """
        夏季风险
        
        机理: 6-8月高温高湿环境利于微生物繁殖
        """
        params = self.RULE_PARAMS[RiskRule.SUMMER_RISK]
        
        month = data.get('month')
        if month is None:
            # 尝试从日期解析
            date = data.get('date') or data.get('production_date')
            if date and isinstance(date, str):
                try:
                    month = int(date.split('-')[1]) if '-' in date else None
                except:
                    pass
        
        if month is None:
            return None
        
        summer_months = params["summer_months"]
        base_risk = params["base_risk"]
        
        if month in summer_months:
            return RiskLabel(
                risk_score=base_risk,
                confidence=0.6,  # 季节性风险置信度相对较低
                source=LabelSource.WEAK_SUPERVISION,
                rule_name=RiskRule.SUMMER_RISK.value,
                metadata={"month": month, "is_summer": True}
            )
        
        return RiskLabel(
            risk_score=0.0,
            confidence=0.7,
            source=LabelSource.WEAK_SUPERVISION,
            rule_name=RiskRule.SUMMER_RISK.value,
            metadata={"month": month, "is_summer": False}
        )
    
    def _raw_material_contamination(self, data: Dict[str, Any]) -> Optional[RiskLabel]:
        """
        原料污染风险
        
        机理: 基于HACCP原理，原料菌落数越高风险越大
        """
        params = self.RULE_PARAMS[RiskRule.RAW_MATERIAL_CONTAMINATION]
        
        colony_count = data.get('raw_colony_count') or data.get('colony_count')
        if colony_count is None:
            return None
        
        colony_threshold = params["colony_threshold"]
        colony_max = params["colony_max"]
        
        if colony_count <= colony_threshold:
            return RiskLabel(
                risk_score=0.0,
                confidence=0.85,
                source=LabelSource.WEAK_SUPERVISION,
                rule_name=RiskRule.RAW_MATERIAL_CONTAMINATION.value,
                metadata={"colony_count": colony_count}
            )
        
        # 风险计算: min(1.0, 菌落/100000)
        risk = min(1.0, colony_count / colony_max)
        confidence = 0.9 if colony_count > 80000 else 0.75
        
        return RiskLabel(
            risk_score=risk,
            confidence=confidence,
            source=LabelSource.WEAK_SUPERVISION,
            rule_name=RiskRule.RAW_MATERIAL_CONTAMINATION.value,
            metadata={"colony_count": colony_count}
        )


class SelfSupervisedSignalGenerator:
    """
    自监督信号生成器
    
    基于以下假设:
    1. 相似节点应有相似风险 (对比学习)
    2. 相邻时间风险应连续 (时序一致性)
    3. 相邻节点风险应相关 (图结构一致性)
    """
    
    def __init__(self, similarity_threshold: float = 0.8):
        """
        初始化
        
        Args:
            similarity_threshold: 相似度阈值
        """
        self.similarity_threshold = similarity_threshold
    
    def generate_contrastive_signals(
        self,
        features: np.ndarray,
        node_ids: List[str]
    ) -> Dict[str, RiskLabel]:
        """
        生成对比学习信号
        
        相似节点应该有相似的风险得分
        
        Args:
            features: 节点特征矩阵 [N, D]
            node_ids: 节点ID列表
            
        Returns:
            自监督标签字典
        """
        labels = {}
        n = len(node_ids)
        
        # 计算余弦相似度
        normalized = features / (np.linalg.norm(features, axis=1, keepdims=True) + 1e-8)
        similarity = np.dot(normalized, normalized.T)
        
        for i, node_id in enumerate(node_ids):
            # 找到相似节点
            similar_indices = np.where(
                (similarity[i] > self.similarity_threshold) & 
                (similarity[i] < 0.999)  # 排除自己
            )[0]
            
            if len(similar_indices) > 0:
                # 相似节点的风险应该相似（这里用特征距离推断）
                # 距离越大，风险差异可能越大
                avg_similarity = np.mean(similarity[i, similar_indices])
                inferred_risk = 1 - avg_similarity  # 相似度高则风险低（假设）
                
                labels[node_id] = RiskLabel(
                    risk_score=inferred_risk,
                    confidence=avg_similarity * 0.5,  # 自监督置信度较低
                    source=LabelSource.SELF_SUPERVISED,
                    rule_name="contrastive_similarity",
                    metadata={
                        "num_similar_nodes": len(similar_indices),
                        "avg_similarity": avg_similarity
                    }
                )
        
        return labels
    
    def generate_temporal_signals(
        self,
        risk_history: Dict[str, List[float]],
        timestamps: List[str]
    ) -> Dict[str, RiskLabel]:
        """
        生成时序一致性信号
        
        相邻时间的风险应该连续
        
        Args:
            risk_history: 节点历史风险 {node_id: [risk_t1, risk_t2, ...]}
            timestamps: 时间戳列表
            
        Returns:
            时序自监督标签
        """
        labels = {}
        
        for node_id, history in risk_history.items():
            if len(history) < 2:
                continue
            
            # 计算风险变化率
            changes = np.diff(history)
            avg_change = np.mean(np.abs(changes))
            
            # 变化太大可能异常
            if avg_change > 0.5:
                inferred_risk = np.mean(history)  # 用均值平滑
                confidence = 0.4
            else:
                inferred_risk = history[-1]  # 延续最后一个值
                confidence = 0.6
            
            labels[node_id] = RiskLabel(
                risk_score=inferred_risk,
                confidence=confidence,
                source=LabelSource.SELF_SUPERVISED,
                rule_name="temporal_consistency",
                metadata={
                    "avg_change": avg_change,
                    "history_length": len(history)
                }
            )
        
        return labels
    
    def generate_graph_signals(
        self,
        adjacency: np.ndarray,
        neighbor_risks: Dict[str, List[float]]
    ) -> Dict[str, RiskLabel]:
        """
        生成图结构一致性信号
        
        相邻节点的风险应该相关
        
        Args:
            adjacency: 邻接矩阵 [N, N]
            neighbor_risks: 邻居风险 {node_id: [risk1, risk2, ...]}
            
        Returns:
            图结构自监督标签
        """
        labels = {}
        
        for node_id, risks in neighbor_risks.items():
            if not risks:
                continue
            
            # 邻居风险的加权平均
            avg_neighbor_risk = np.mean(risks)
            
            # 节点风险应该与邻居相关
            labels[node_id] = RiskLabel(
                risk_score=avg_neighbor_risk,
                confidence=0.5,
                source=LabelSource.SELF_SUPERVISED,
                rule_name="graph_consistency",
                metadata={
                    "num_neighbors": len(risks),
                    "neighbor_risk_variance": np.var(risks)
                }
            )
        
        return labels


class GenerativeLabelGenerator:
    """
    生成式标签生成器
    
    使用数据增强和反事实推理生成标签
    """
    
    def __init__(self, augmentation_factor: float = 0.1):
        """
        初始化
        
        Args:
            augmentation_factor: 数据增强强度
        """
        self.augmentation_factor = augmentation_factor
    
    def augment_positive_samples(
        self,
        positive_samples: List[Dict[str, Any]],
        num_augmented: int
    ) -> List[RiskLabel]:
        """
        对正样本进行数据增强
        
        Args:
            positive_samples: 正样本列表
            num_augmented: 需要生成的样本数
            
        Returns:
            增强后的标签列表
        """
        labels = []
        n_original = len(positive_samples)
        
        if n_original == 0:
            return labels
        
        for i in range(num_augmented):
            # 随机选择一个正样本
            sample = positive_samples[i % n_original]
            
            # 添加噪声进行增强
            noise = np.random.normal(0, self.augmentation_factor)
            risk = np.clip(0.7 + noise, 0.5, 1.0)  # 保持高风险
            
            labels.append(RiskLabel(
                risk_score=risk,
                confidence=0.5,  # 生成标签置信度较低
                source=LabelSource.GENERATIVE,
                rule_name="data_augmentation",
                metadata={"original_sample_id": i % n_original}
            ))
        
        return labels
    
    def counterfactual_inference(
        self,
        base_features: Dict[str, Any],
        intervention: Dict[str, Any]
    ) -> RiskLabel:
        """
        反事实推理
        
        预测: 如果条件改变，风险会如何变化
        
        Args:
            base_features: 基础特征
            intervention: 干预条件
            
        Returns:
            反事实风险标签
        """
        # 创建干预后的特征
        modified = {**base_features, **intervention}
        
        # 使用规则引擎评估反事实情况
        engine = RuleEngine()
        rule_results = engine.evaluate(modified)
        
        if rule_results:
            # 取最大风险作为反事实预测
            max_risk = max(r.risk_score for r in rule_results.values())
            return RiskLabel(
                risk_score=max_risk,
                confidence=0.4,
                source=LabelSource.GENERATIVE,
                rule_name="counterfactual",
                metadata={"intervention": intervention}
            )
        
        return RiskLabel(
            risk_score=0.5,
            confidence=0.3,
            source=LabelSource.GENERATIVE,
            rule_name="counterfactual_fallback"
        )


def fuse_labels(
    labels: Dict[str, List[RiskLabel]],
    layer_weights: Optional[Dict[str, float]] = None,
    fusion_method: str = "weighted_average"
) -> Dict[str, float]:
    """
    多层次标签融合
    
    Args:
        labels: 分层标签 {layer_name: [RiskLabel, ...]}
        layer_weights: 层级权重 {layer_name: weight}
        fusion_method: 融合方法 ("weighted_average", "max", "bayesian")
        
    Returns:
        融合后的风险得分 {node_id: risk_score}
    """
    # 默认权重（层级越高，权重越大）
    if layer_weights is None:
        layer_weights = {
            LabelSource.EXPLICIT.value: 1.0,      # 显式标签最可靠
            LabelSource.WEAK_SUPERVISION.value: 0.6,  # 弱监督次之
            LabelSource.SELF_SUPERVISED.value: 0.4,   # 自监督再次
            LabelSource.GENERATIVE.value: 0.3     # 生成式最低
        }
    
    fused_scores = {}
    
    # 按节点分组
    node_labels: Dict[str, List[Tuple[RiskLabel, float]]] = {}
    for layer_name, label_list in labels.items():
        weight = layer_weights.get(layer_name, 0.5)
        for label in label_list:
            node_id = label.metadata.get('node_id', 'global')
            if node_id not in node_labels:
                node_labels[node_id] = []
            node_labels[node_id].append((label, weight))
    
    # 融合
    for node_id, label_weights in node_labels.items():
        if fusion_method == "weighted_average":
            weighted_sum = 0.0
            total_weight = 0.0
            
            for label, layer_weight in label_weights:
                effective_weight = layer_weight * label.confidence
                weighted_sum += label.risk_score * effective_weight
                total_weight += effective_weight
            
            fused_scores[node_id] = weighted_sum / total_weight if total_weight > 0 else 0.5
        
        elif fusion_method == "max":
            # 取最大风险（保守策略）
            max_risk = max(
                label.risk_score * weight 
                for label, weight in label_weights
            )
            fused_scores[node_id] = min(max_risk, 1.0)
        
        elif fusion_method == "bayesian":
            # 贝叶斯融合（简化版）
            # 假设每个标签是高斯分布，融合后验
            precisions = []
            means = []
            
            for label, layer_weight in label_weights:
                # 精度 = 置信度 * 层级权重
                precision = label.confidence * layer_weight
                precisions.append(precision)
                means.append(label.risk_score)
            
            # 后验均值
            total_precision = sum(precisions)
            if total_precision > 0:
                fused_scores[node_id] = sum(
                    m * p for m, p in zip(means, precisions)
                ) / total_precision
            else:
                fused_scores[node_id] = 0.5
    
    return fused_scores


def generate_weak_labels(
    data: List[Dict[str, Any]],
    use_rules: bool = True,
    use_self_supervised: bool = False,
    use_generative: bool = False
) -> List[Dict[str, Any]]:
    """
    生成弱监督标签（便捷函数）
    
    Args:
        data: 数据列表
        use_rules: 是否使用规则引擎
        use_self_supervised: 是否使用自监督信号
        use_generative: 是否使用生成式标签
        
    Returns:
        带标签的数据列表
    """
    engine = RuleEngine()
    results = []
    
    for item in data:
        item_result = {**item, 'labels': {}}
        
        # 规则引擎标签
        if use_rules:
            rule_labels = engine.evaluate(item)
            if rule_labels:
                # 取最大风险
                max_risk = max(l.risk_score for l in rule_labels.values())
                item_result['labels']['weak_supervision'] = {
                    'risk_score': max_risk,
                    'confidence': 0.7,
                    'rule_details': {k.value: v.risk_score for k, v in rule_labels.items()}
                }
        
        results.append(item_result)
    
    return results


# 便捷函数
__all__ = [
    'LabelSource',
    'RiskRule',
    'RiskLabel',
    'RuleEngine',
    'SelfSupervisedSignalGenerator',
    'GenerativeLabelGenerator',
    'fuse_labels',
    'generate_weak_labels'
]
