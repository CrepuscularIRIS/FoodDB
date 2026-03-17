"""
评估模块

提供风险预测模型的评估指标和分层验证功能
"""

from .metrics import (
    calculate_recall,
    calculate_precision,
    calculate_f1,
    calculate_f1_score,
    calculate_auc_roc,
    calculate_auc_pr,
    calculate_brier_score,
    calculate_top_k_accuracy,
    calculate_metrics_at_thresholds,
    find_optimal_threshold,
    calculate_pr_curve,
    calculate_roc_curve,
    calculate_all_metrics,
    evaluate_all_metrics,
    RiskMetricsResult
)

from .validator import (
    EnterpriseScale,
    RiskType,
    ValidationResult,
    LayerValidationReport,
    StratifiedValidator,
    ValidationReportGenerator
)

__all__ = [
    # 指标函数
    'calculate_recall',
    'calculate_precision',
    'calculate_f1',
    'calculate_f1_score',
    'calculate_auc_roc',
    'calculate_auc_pr',
    'calculate_brier_score',
    'calculate_top_k_accuracy',
    'calculate_metrics_at_thresholds',
    'find_optimal_threshold',
    'calculate_pr_curve',
    'calculate_roc_curve',
    'calculate_all_metrics',
    'evaluate_all_metrics',
    'RiskMetricsResult',
    # 验证器
    'EnterpriseScale',
    'RiskType',
    'ValidationResult',
    'LayerValidationReport',
    'StratifiedValidator',
    'ValidationReportGenerator'
]
