#!/usr/bin/env python3
"""
风险预测器 - 基于规则引擎计算风险分数
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


# 风险计算规则权重
RISK_WEIGHTS = {
    'small_enterprise': 0.3,      # 小企业
    'violation_record': 0.2,       # 违规记录
    'dairy_enterprise': 0.1,       # 乳企
    'logistics_warehouse': 0.05,    # 物流/仓储
}

# 节点类型标签
DAIRY_TYPES = {'乳企', '牧场'}
LOGISTICS_WAREHOUSE_TYPES = {'物流', '仓储'}

# 规模标签
SMALL_SCALE = '小型'


@dataclass
class RiskPrediction:
    """风险预测结果"""
    node_id: str
    enterprise_name: str
    node_type: str
    scale: str
    region: str
    risk_probability: float
    risk_level: str
    confidence: float
    risk_factors: List[str]


class RiskPredictor:
    """风险预测器"""
    
    def __init__(self, features_path: Optional[str] = None):
        """初始化预测器"""
        if features_path is None:
            # 默认使用 data/v2/node_features_64d.json
            base_dir = Path(__file__).parent.parent
            features_path = base_dir / "data" / "v2" / "node_features_64d.json"
        
        self.features_path = Path(features_path)
        self.node_features: Dict[str, Any] = {}
        self._load_features()
    
    def _load_features(self):
        """加载节点特征"""
        if not self.features_path.exists():
            raise FileNotFoundError(f"特征文件不存在: {self.features_path}")
        
        with open(self.features_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.node_features = data.get('features', {})
        print(f"✓ 已加载 {len(self.node_features)} 个节点特征")
    
    def _calculate_confidence(self, node_data: Dict[str, Any]) -> float:
        """
        计算置信度 - 基于数据完整度
        """
        # 检查可用字段
        fields_to_check = ['features', 'node_type', 'enterprise_name', 'scale', 'region']
        
        present_count = sum(1 for field in fields_to_check if node_data.get(field) is not None)
        
        # 基础置信度
        base_confidence = present_count / len(fields_to_check)
        
        # 检查64维特征是否完整
        features = node_data.get('features', [])
        feature_completeness = len(features) / 64 if features else 0
        
        # 综合置信度
        confidence = (base_confidence * 0.4 + feature_completeness * 0.6)
        
        return round(min(confidence, 1.0), 3)
    
    def _calculate_risk(self, node_data: Dict[str, Any]) -> tuple[float, List[str]]:
        """
        基于规则计算风险概率
        
        规则:
        - 小企业: +0.3
        - 有违规记录: +0.2
        - 乳企: +0.1
        - 物流/仓储: +0.05
        """
        risk_score = 0.0  # 基础风险
        risk_factors = []
        
        node_type = node_data.get('node_type', '')
        scale = node_data.get('scale', '')
        
        # 小企业
        if scale == SMALL_SCALE:
            risk_score += RISK_WEIGHTS['small_enterprise']
            risk_factors.append('小企业')
        
        # 违规记录 - 通过特征向量推断 (第39个特征如果 > 0.5 表示有违规)
        features = node_data.get('features', [])
        if len(features) > 38 and features[38] > 0.5:
            risk_score += RISK_WEIGHTS['violation_record']
            risk_factors.append('有违规记录')
        
        # 乳企
        if node_type in DAIRY_TYPES:
            risk_score += RISK_WEIGHTS['dairy_enterprise']
            risk_factors.append('乳制品企业')
        
        # 物流/仓储
        if node_type in LOGISTICS_WAREHOUSE_TYPES:
            risk_score += RISK_WEIGHTS['logistics_warehouse']
            risk_factors.append('物流/仓储')
        
        # 限制在 0-1 范围内
        risk_probability = min(max(risk_score, 0.0), 1.0)
        
        return risk_probability, risk_factors
    
    def _get_risk_level(self, risk_probability: float) -> str:
        """根据风险概率确定风险等级"""
        if risk_probability >= 0.7:
            return "高风险"
        elif risk_probability >= 0.4:
            return "中风险"
        else:
            return "低风险"
    
    def predict(self, node_id: str) -> Optional[RiskPrediction]:
        """
        预测单个节点的风险
        
        Args:
            node_id: 节点ID
            
        Returns:
            RiskPrediction 对象，如果节点不存在则返回 None
        """
        if node_id not in self.node_features:
            return None
        
        node_data = self.node_features[node_id]
        
        # 计算风险
        risk_probability, risk_factors = self._calculate_risk(node_data)
        
        # 计算置信度
        confidence = self._calculate_confidence(node_data)
        
        # 确定风险等级
        risk_level = self._get_risk_level(risk_probability)
        
        return RiskPrediction(
            node_id=node_id,
            enterprise_name=node_data.get('enterprise_name', ''),
            node_type=node_data.get('node_type', ''),
            scale=node_data.get('scale', ''),
            region=node_data.get('region', ''),
            risk_probability=risk_probability,
            risk_level=risk_level,
            confidence=confidence,
            risk_factors=risk_factors
        )
    
    def predict_batch(self, node_ids: List[str]) -> List[RiskPrediction]:
        """批量预测多个节点的风险"""
        results = []
        for node_id in node_ids:
            pred = self.predict(node_id)
            if pred:
                results.append(pred)
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取风险统计信息
        
        Returns:
            包含各类统计数据的字典
        """
        if not self.node_features:
            return {}
        
        # 统计各类型节点数量
        type_count = {}
        scale_count = {}
        risk_level_count = {"高风险": 0, "中风险": 0, "低风险": 0}
        total_risk = 0.0
        
        for node_id, node_data in self.node_features.items():
            # 类型统计
            node_type = node_data.get('node_type', '未知')
            type_count[node_type] = type_count.get(node_type, 0) + 1
            
            # 规模统计
            scale = node_data.get('scale', '未知')
            scale_count[scale] = scale_count.get(scale, 0) + 1
            
            # 风险计算
            risk_prob, _ = self._calculate_risk(node_data)
            risk_level = self._get_risk_level(risk_prob)
            risk_level_count[risk_level] += 1
            total_risk += risk_prob
        
        node_count = len(self.node_features)
        
        return {
            "total_nodes": node_count,
            "type_distribution": type_count,
            "scale_distribution": scale_count,
            "risk_level_distribution": risk_level_count,
            "average_risk_probability": round(total_risk / node_count, 4) if node_count > 0 else 0,
            "high_risk_count": risk_level_count["高风险"],
            "medium_risk_count": risk_level_count["中风险"],
            "low_risk_count": risk_level_count["低风险"],
        }


# 全局预测器实例
_predictor: Optional[RiskPredictor] = None


def get_risk_predictor() -> RiskPredictor:
    """获取全局风险预测器实例"""
    global _predictor
    if _predictor is None:
        _predictor = RiskPredictor()
    return _predictor


if __name__ == "__main__":
    # 测试代码
    predictor = RiskPredictor()
    
    # 测试单个预测
    print("\n=== 单个节点预测测试 ===")
    result = predictor.predict("ENT-牧-0001")
    if result:
        print(f"节点: {result.node_id}")
        print(f"企业: {result.enterprise_name}")
        print(f"类型: {result.node_type}, 规模: {result.scale}")
        print(f"风险概率: {result.risk_probability}")
        print(f"风险等级: {result.risk_level}")
        print(f"置信度: {result.confidence}")
        print(f"风险因素: {result.risk_factors}")
    
    # 测试统计
    print("\n=== 风险统计 ===")
    stats = predictor.get_statistics()
    print(f"总节点数: {stats['total_nodes']}")
    print(f"类型分布: {stats['type_distribution']}")
    print(f"规模分布: {stats['scale_distribution']}")
    print(f"风险等级分布: {stats['risk_level_distribution']}")
    print(f"平均风险概率: {stats['average_risk_probability']}")
