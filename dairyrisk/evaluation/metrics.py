"""
评估指标模块 (Evaluation Metrics)

实现方案文档4.1节要求的所有评估指标。
不使用sklearn，纯numpy实现避免依赖问题。
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass


@dataclass
class RiskMetricsResult:
    """风险评估指标结果"""
    recall: float                    # 召回率
    precision: float                 # 精确率
    f1_score: float                  # F1分数
    auc_roc: float                   # ROC曲线下面积
    auc_pr: float                    # PR曲线下面积 (关键指标)
    brier_score: float               # Brier分数
    top_k_accuracy: Dict[int, float] # Top-K命中率
    confusion_matrix: np.ndarray     # 混淆矩阵
    
    def to_dict(self) -> Dict[str, Union[float, Dict, np.ndarray]]:
        """转换为字典格式"""
        return {
            'recall': self.recall,
            'precision': self.precision,
            'f1_score': self.f1_score,
            'auc_roc': self.auc_roc,
            'auc_pr': self.auc_pr,
            'brier_score': self.brier_score,
            'top_k_accuracy': self.top_k_accuracy,
            'confusion_matrix': self.confusion_matrix.tolist(),
        }


def calculate_confusion_matrix(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    num_classes: int = 2
) -> np.ndarray:
    """计算混淆矩阵"""
    cm = np.zeros((num_classes, num_classes), dtype=int)
    for true, pred in zip(y_true, y_pred):
        cm[int(true), int(pred)] += 1
    return cm


def calculate_recall(y_true: np.ndarray, y_pred: np.ndarray, average: str = 'binary') -> float:
    """计算召回率 Recall = TP / (TP + FN)"""
    if average == 'binary':
        tp = np.sum((y_true == 1) & (y_pred == 1))
        fn = np.sum((y_true == 1) & (y_pred == 0))
        return tp / (tp + fn) if (tp + fn) > 0 else 0.0
    else:
        classes = np.unique(y_true)
        recalls = []
        for c in classes:
            tp = np.sum((y_true == c) & (y_pred == c))
            fn = np.sum((y_true == c) & (y_pred != c))
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            recalls.append(recall)
        return np.mean(recalls)


def calculate_precision(y_true: np.ndarray, y_pred: np.ndarray, average: str = 'binary') -> float:
    """计算精确率 Precision = TP / (TP + FP)"""
    if average == 'binary':
        tp = np.sum((y_true == 1) & (y_pred == 1))
        fp = np.sum((y_true == 0) & (y_pred == 1))
        return tp / (tp + fp) if (tp + fp) > 0 else 0.0
    else:
        classes = np.unique(y_true)
        precisions = []
        for c in classes:
            tp = np.sum((y_true == c) & (y_pred == c))
            fp = np.sum((y_true != c) & (y_pred == c))
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            precisions.append(precision)
        return np.mean(precisions)


def calculate_f1_score(y_true: np.ndarray, y_pred: np.ndarray, average: str = 'binary') -> float:
    """计算F1分数 F1 = 2 * (Precision * Recall) / (Precision + Recall)"""
    precision = calculate_precision(y_true, y_pred, average)
    recall = calculate_recall(y_true, y_pred, average)
    if precision + recall == 0:
        return 0.0
    return 2 * (precision * recall) / (precision + recall)


def calculate_auc_roc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """计算AUC-ROC"""
    desc_order = np.argsort(y_score)[::-1]
    y_true_sorted = y_true[desc_order]
    n_pos = np.sum(y_true == 1)
    n_neg = np.sum(y_true == 0)
    if n_pos == 0 or n_neg == 0:
        return 0.5
    tps = np.cumsum(y_true_sorted)
    fps = np.cumsum(1 - y_true_sorted)
    tpr = tps / n_pos
    fpr = fps / n_neg
    tpr = np.concatenate([[0], tpr])
    fpr = np.concatenate([[0], fpr])
    return np.trapz(tpr, fpr)


def calculate_auc_pr(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """计算AUC-PR (关键指标)"""
    desc_order = np.argsort(y_score)[::-1]
    y_true_sorted = y_true[desc_order]
    n_pos = np.sum(y_true == 1)
    if n_pos == 0:
        return 0.0
    tps = np.cumsum(y_true_sorted)
    precisions = tps / np.arange(1, len(y_true_sorted) + 1)
    recalls = tps / n_pos
    precisions = np.concatenate([[1], precisions])
    recalls = np.concatenate([[0], recalls])
    return np.trapz(precisions, recalls)


def calculate_brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """计算Brier分数"""
    return np.mean((y_prob - y_true) ** 2)


def calculate_top_k_accuracy(y_true: np.ndarray, y_score: np.ndarray, k_values: List[int] = [5, 10, 20, 50]) -> Dict[int, float]:
    """计算Top-K命中率"""
    sorted_indices = np.argsort(y_score)[::-1]
    y_true_sorted = y_true[sorted_indices]
    n_pos = np.sum(y_true == 1)
    if n_pos == 0:
        return {k: 0.0 for k in k_values}
    results = {}
    for k in k_values:
        top_k_true = y_true_sorted[:k]
        hits = np.sum(top_k_true == 1)
        results[k] = hits / min(k, len(y_true))
    return results


def calculate_all_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_score: np.ndarray, y_prob: Optional[np.ndarray] = None) -> RiskMetricsResult:
    """计算所有评估指标"""
    if y_prob is None:
        y_prob = y_score
    cm = calculate_confusion_matrix(y_true, y_pred)
    return RiskMetricsResult(
        recall=calculate_recall(y_true, y_pred),
        precision=calculate_precision(y_true, y_pred),
        f1_score=calculate_f1_score(y_true, y_pred),
        auc_roc=calculate_auc_roc(y_true, y_score),
        auc_pr=calculate_auc_pr(y_true, y_score),
        brier_score=calculate_brier_score(y_true, y_prob),
        top_k_accuracy=calculate_top_k_accuracy(y_true, y_score),
        confusion_matrix=cm,
    )


def calculate_metrics_at_thresholds(y_true: np.ndarray, y_score: np.ndarray, thresholds: List[float] = None) -> Dict[str, List[float]]:
    """计算不同阈值下的指标"""
    if thresholds is None:
        thresholds = [i * 0.1 for i in range(1, 10)]
    results = {'thresholds': thresholds, 'recall': [], 'precision': [], 'f1': []}
    for threshold in thresholds:
        y_pred = (y_score >= threshold).astype(int)
        results['recall'].append(calculate_recall(y_true, y_pred))
        results['precision'].append(calculate_precision(y_true, y_pred))
        results['f1'].append(calculate_f1_score(y_true, y_pred))
    return results


def find_optimal_threshold(y_true: np.ndarray, y_score: np.ndarray, metric: str = 'f1') -> Tuple[float, float]:
    """找到最优阈值"""
    thresholds = np.linspace(0.1, 0.9, 17)
    best_threshold = 0.5
    best_score = 0.0
    for threshold in thresholds:
        y_pred = (y_score >= threshold).astype(int)
        if metric == 'f1':
            score = calculate_f1_score(y_true, y_pred)
        elif metric == 'recall':
            score = calculate_recall(y_true, y_pred)
        elif metric == 'precision':
            score = calculate_precision(y_true, y_pred)
        else:
            score = calculate_f1_score(y_true, y_pred)
        if score > best_score:
            best_score = score
            best_threshold = threshold
    return best_threshold, best_score


# 别名，保持向后兼容
calculate_f1 = calculate_f1_score
evaluate_all_metrics = calculate_all_metrics



def calculate_pr_curve(y_true, y_score):
    """计算PR曲线的precision和recall数组"""
    desc_order = np.argsort(y_score)[::-1]
    y_true_sorted = y_true[desc_order]
    n_pos = np.sum(y_true == 1)
    if n_pos == 0:
        return np.array([1.0]), np.array([0.0])
    tps = np.cumsum(y_true_sorted)
    precisions = tps / np.arange(1, len(y_true_sorted) + 1)
    recalls = tps / n_pos
    precisions = np.concatenate([[1], precisions])
    recalls = np.concatenate([[0], recalls])
    return precisions, recalls


def calculate_roc_curve(y_true, y_score):
    """计算ROC曲线的fpr和tpr数组"""
    desc_order = np.argsort(y_score)[::-1]
    y_true_sorted = y_true[desc_order]
    n_pos = np.sum(y_true == 1)
    n_neg = np.sum(y_true == 0)
    if n_pos == 0 or n_neg == 0:
        return np.array([0.0, 1.0]), np.array([0.0, 1.0])
    tps = np.cumsum(y_true_sorted)
    fps = np.cumsum(1 - y_true_sorted)
    tpr = tps / n_pos
    fpr = fps / n_neg
    tpr = np.concatenate([[0], tpr])
    fpr = np.concatenate([[0], fpr])
    return fpr, tpr
