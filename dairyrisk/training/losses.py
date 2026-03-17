"""
训练损失模块 (5.8节)

包含:
- SupplyChainRiskLoss: 供应链风险预测综合损失
- BCEWithLogitsLoss: 带正样本权重的BCE损失
- MSELoss: 均方误差损失

作者: DairyRisk Team
日期: 2025-03
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor
from typing import Dict, List, Optional, Tuple, Union
import logging

logger = logging.getLogger(__name__)


class SupplyChainRiskLoss(nn.Module):
    """
    供应链风险预测综合损失函数
    
    结合:
    1. 回归损失 (BCE) - 预测连续风险概率
    2. 分类损失 (CE) - 风险等级分类
    3. 置信度损失 - 校准预测置信度
    4. 正样本权重 - 处理类别不平衡
    
    适用于食品安全风险预测场景，其中:
    - 正样本（风险事件）极度稀少
    - 需要同时预测概率和等级
    - 需要输出预测置信度
    """
    
    def __init__(
        self,
        regression_weight: float = 1.0,
        classification_weight: float = 0.5,
        confidence_weight: float = 0.1,
        pos_weight: float = 10.0,
        risk_thresholds: Optional[List[float]] = None,
        label_smoothing: float = 0.0
    ):
        """
        初始化损失函数
        
        Args:
            regression_weight: 回归损失权重
            classification_weight: 分类损失权重
            confidence_weight: 置信度损失权重
            pos_weight: 正样本权重（处理类别不平衡）
            risk_thresholds: 风险等级阈值 [低-中阈值, 中-高阈值]
            label_smoothing: 标签平滑系数
        """
        super().__init__()
        
        self.regression_weight = regression_weight
        self.classification_weight = classification_weight
        self.confidence_weight = confidence_weight
        self.label_smoothing = label_smoothing
        
        self.risk_thresholds = risk_thresholds or [0.30, 0.70]
        
        # BCE损失（带正样本权重）
        self.bce_loss = nn.BCEWithLogitsLoss(
            pos_weight=torch.tensor([pos_weight]),
            reduction='mean'
        )
        
        # MSE损失
        self.mse_loss = nn.MSELoss(reduction='mean')
        
        # 交叉熵损失（用于三分类）
        self.ce_loss = nn.CrossEntropyLoss(reduction='mean')
    
    def forward(
        self,
        predictions: Dict[str, Tensor],
        targets: Tensor
    ) -> Dict[str, Tensor]:
        """
        计算损失
        
        Args:
            predictions: 预测结果字典，包含:
                - risk_probability: 风险概率 [batch_size]
                - risk_level: 风险等级 [batch_size] (可选)
                - confidence: 预测置信度 [batch_size] (可选)
                - risk_logits: 风险logits [batch_size] (可选)
            targets: 目标标签 [batch_size]，0-1连续值
            
        Returns:
            损失字典，包含:
                - total_loss: 总损失
                - regression_loss: 回归损失
                - classification_loss: 分类损失
                - confidence_loss: 置信度损失
        """
        risk_prob = predictions.get("risk_probability")
        risk_level = predictions.get("risk_level")
        confidence = predictions.get("confidence")
        risk_logits = predictions.get("risk_logits")
        
        if risk_prob is None:
            raise ValueError("predictions必须包含'risk_probability'")
        
        # 确保维度一致
        targets = targets.float().flatten()
        risk_prob = risk_prob.flatten()
        
        # 1. 回归损失 (BCE)
        if risk_logits is not None:
            # 使用logits计算BCE（数值更稳定）
            regression_loss = F.binary_cross_entropy_with_logits(
                risk_logits.flatten(),
                targets,
                reduction='mean'
            )
        else:
            # 使用概率计算BCE
            regression_loss = F.binary_cross_entropy(
                risk_prob,
                targets,
                reduction='mean'
            )
        
        # 2. 分类损失（将风险概率转换为类别）
        classification_loss = self._compute_classification_loss(
            risk_prob, targets
        )
        
        # 3. 置信度损失（预测置信度应与预测误差负相关）
        confidence_loss = self._compute_confidence_loss(
            risk_prob, targets, confidence
        )
        
        # 4. 总损失
        total_loss = (
            self.regression_weight * regression_loss +
            self.classification_weight * classification_loss +
            self.confidence_weight * confidence_loss
        )
        
        return {
            "total_loss": total_loss,
            "regression_loss": regression_loss,
            "classification_loss": classification_loss,
            "confidence_loss": confidence_loss
        }
    
    def _compute_classification_loss(
        self,
        risk_prob: Tensor,
        targets: Tensor
    ) -> Tensor:
        """
        计算分类损失
        
        将连续风险概率转换为三分类问题
        """
        # 目标类别
        target_levels = torch.zeros_like(targets, dtype=torch.long)
        target_levels[targets >= self.risk_thresholds[0]] = 1  # 中风险
        target_levels[targets >= self.risk_thresholds[1]] = 2  # 高风险
        
        # 预测类别概率（从风险概率推导）
        # 使用soft的方式：低风险概率递减，中风险概率先增后减，高风险概率递增
        batch_size = len(risk_prob)
        level_probs = torch.zeros(
            (batch_size, 3),
            device=risk_prob.device,
            dtype=risk_prob.dtype
        )
        
        # 基于阈值计算各类别概率
        # 类别0（低风险）：prob < 0.3
        # 类别1（中风险）：0.3 <= prob < 0.7
        # 类别2（高风险）：prob >= 0.7
        
        low_mask = risk_prob < self.risk_thresholds[0]
        med_mask = (risk_prob >= self.risk_thresholds[0]) & (risk_prob < self.risk_thresholds[1])
        high_mask = risk_prob >= self.risk_thresholds[1]
        
        level_probs[low_mask, 0] = 1.0 - risk_prob[low_mask]
        level_probs[med_mask, 1] = risk_prob[med_mask]
        level_probs[high_mask, 2] = risk_prob[high_mask]
        
        # 添加平滑
        level_probs = level_probs + 0.01
        level_probs = level_probs / level_probs.sum(dim=1, keepdim=True)
        
        # 计算交叉熵
        log_probs = torch.log(level_probs + 1e-8)
        classification_loss = F.nll_loss(log_probs, target_levels)
        
        return classification_loss
    
    def _compute_confidence_loss(
        self,
        risk_prob: Tensor,
        targets: Tensor,
        confidence: Optional[Tensor]
    ) -> Tensor:
        """
        计算置信度损失
        
        预测置信度应与预测误差负相关：
        - 预测误差小 → 置信度高
        - 预测误差大 → 置信度低
        """
        if confidence is None:
            return torch.tensor(0.0, device=risk_prob.device)
        
        confidence = confidence.flatten()
        
        # 计算预测误差
        prediction_error = torch.abs(risk_prob - targets)
        
        # 目标置信度：误差越小，置信度越高
        # 使用指数衰减
        confidence_target = torch.exp(-prediction_error * 5.0)
        
        # MSE损失
        confidence_loss = F.mse_loss(confidence, confidence_target)
        
        return confidence_loss
    
    def get_config(self) -> Dict[str, float]:
        """获取损失函数配置"""
        return {
            "regression_weight": self.regression_weight,
            "classification_weight": self.classification_weight,
            "confidence_weight": self.confidence_weight,
            "risk_thresholds": self.risk_thresholds
        }


class FocalLoss(nn.Module):
    """
    Focal Loss
    
    解决类别不平衡问题，关注难分类样本
    
    Reference: Lin et al., "Focal Loss for Dense Object Detection", ICCV 2017
    """
    
    def __init__(
        self,
        alpha: float = 0.25,
        gamma: float = 2.0,
        reduction: str = 'mean'
    ):
        """
        初始化
        
        Args:
            alpha: 正样本权重
            gamma: 聚焦参数
            reduction: 降维方法
        """
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction
    
    def forward(
        self,
        inputs: Tensor,
        targets: Tensor
    ) -> Tensor:
        """
        计算Focal Loss
        
        Args:
            inputs: 预测logits
            targets: 目标标签
            
        Returns:
            Focal loss值
        """
        # Sigmoid + BCE
        bce_loss = F.binary_cross_entropy_with_logits(
            inputs, targets, reduction='none'
        )
        
        # 计算概率
        probs = torch.sigmoid(inputs)
        
        # 根据目标选择概率
        pt = torch.where(targets > 0.5, probs, 1 - probs)
        
        # Focal weight
        focal_weight = (1 - pt) ** self.gamma
        
        # 应用alpha权重
        alpha_weight = torch.where(
            targets > 0.5,
            torch.tensor(self.alpha),
            torch.tensor(1 - self.alpha)
        )
        
        loss = alpha_weight * focal_weight * bce_loss
        
        if self.reduction == 'mean':
            return loss.mean()
        elif self.reduction == 'sum':
            return loss.sum()
        else:
            return loss


class DiceLoss(nn.Module):
    """
    Dice Loss
    
    适合处理类别不平衡的语义分割任务，也可用于分类
    """
    
    def __init__(
        self,
        smooth: float = 1.0,
        reduction: str = 'mean'
    ):
        """
        初始化
        
        Args:
            smooth: 平滑系数
            reduction: 降维方法
        """
        super().__init__()
        self.smooth = smooth
        self.reduction = reduction
    
    def forward(
        self,
        inputs: Tensor,
        targets: Tensor
    ) -> Tensor:
        """
        计算Dice Loss
        
        Args:
            inputs: 预测概率
            targets: 目标标签
            
        Returns:
            Dice loss值
        """
        # 确保范围在[0,1]
        inputs = torch.sigmoid(inputs) if inputs.min() < 0 else inputs
        
        # 展平
        inputs = inputs.flatten()
        targets = targets.flatten()
        
        # 计算交集和并集
        intersection = (inputs * targets).sum()
        union = inputs.sum() + targets.sum()
        
        # Dice系数
        dice = (2.0 * intersection + self.smooth) / (union + self.smooth)
        
        # Dice Loss = 1 - Dice
        loss = 1.0 - dice
        
        return loss


class WeightedBCELoss(nn.Module):
    """
    带正样本权重的BCE损失
    
    用于处理类别不平衡的二分类问题
    """
    
    def __init__(
        self,
        pos_weight: float = 10.0,
        reduction: str = 'mean'
    ):
        """
        初始化
        
        Args:
            pos_weight: 正样本权重
            reduction: 降维方法
        """
        super().__init__()
        self.pos_weight = pos_weight
        self.reduction = reduction
    
    def forward(
        self,
        inputs: Tensor,
        targets: Tensor
    ) -> Tensor:
        """
        计算加权BCE Loss
        
        Args:
            inputs: 预测logits或概率
            targets: 目标标签
            
        Returns:
            损失值
        """
        # 判断输入是logits还是概率
        if inputs.min() < 0 or inputs.max() > 1:
            # logits
            loss = F.binary_cross_entropy_with_logits(
                inputs, targets, reduction='none'
            )
        else:
            # 概率
            loss = F.binary_cross_entropy(
                inputs, targets, reduction='none'
            )
        
        # 应用正样本权重
        weights = torch.where(
            targets > 0.5,
            torch.tensor(self.pos_weight),
            torch.tensor(1.0)
        )
        
        weighted_loss = loss * weights
        
        if self.reduction == 'mean':
            return weighted_loss.mean()
        elif self.reduction == 'sum':
            return weighted_loss.sum()
        else:
            return weighted_loss


class TverskyLoss(nn.Module):
    """
    Tversky Loss
    
    可调整对假阳性和假阴性的关注程度
    
    当 beta > 0.5 时，更关注假阴性（漏报）
    适合食品安全场景，需要减少漏报
    """
    
    def __init__(
        self,
        alpha: float = 0.3,  # 假阳性权重
        beta: float = 0.7,   # 假阴性权重（更高以关注漏报）
        smooth: float = 1.0
    ):
        """
        初始化
        
        Args:
            alpha: 假阳性权重
            beta: 假阴性权重
            smooth: 平滑系数
        """
        super().__init__()
        self.alpha = alpha
        self.beta = beta
        self.smooth = smooth
    
    def forward(
        self,
        inputs: Tensor,
        targets: Tensor
    ) -> Tensor:
        """
        计算Tversky Loss
        
        Args:
            inputs: 预测logits
            targets: 目标标签
            
        Returns:
            Tversky loss值
        """
        # Sigmoid
        inputs = torch.sigmoid(inputs)
        
        # 展平
        inputs = inputs.flatten()
        targets = targets.flatten()
        
        # 计算TP, FP, FN
        TP = (inputs * targets).sum()
        FP = (inputs * (1 - targets)).sum()
        FN = ((1 - inputs) * targets).sum()
        
        # Tversky指数
        tversky = (TP + self.smooth) / (
            TP + self.alpha * FP + self.beta * FN + self.smooth
        )
        
        return 1.0 - tversky


def get_loss_function(
    loss_type: str = "supply_chain_risk",
    **kwargs
) -> nn.Module:
    """
    获取损失函数（工厂函数）
    
    Args:
        loss_type: 损失函数类型
        **kwargs: 损失函数参数
        
    Returns:
        损失函数实例
    """
    loss_map = {
        "supply_chain_risk": SupplyChainRiskLoss,
        "focal": FocalLoss,
        "dice": DiceLoss,
        "weighted_bce": WeightedBCELoss,
        "tversky": TverskyLoss,
        "bce": nn.BCEWithLogitsLoss,
        "mse": nn.MSELoss,
        "cross_entropy": nn.CrossEntropyLoss
    }
    
    if loss_type not in loss_map:
        raise ValueError(f"未知的损失函数类型: {loss_type}")
    
    return loss_map[loss_type](**kwargs)


# 便捷函数
__all__ = [
    'SupplyChainRiskLoss',
    'FocalLoss',
    'DiceLoss',
    'WeightedBCELoss',
    'TverskyLoss',
    'get_loss_function'
]
