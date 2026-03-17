"""
分层验证器模块 (5.10节)

支持按企业规模、风险类型进行分层验证，生成验证报告

作者: DairyRisk Team
日期: 2025-03
"""

import numpy as np
import torch
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging

from .metrics import (
    calculate_recall,
    calculate_precision,
    calculate_f1,
    calculate_auc_roc,
    calculate_auc_pr,
    calculate_brier_score,
    calculate_top_k_accuracy,
    evaluate_all_metrics
)

logger = logging.getLogger(__name__)


class EnterpriseScale:
    """企业规模分类"""
    LARGE = "large"      # 大型企业
    MEDIUM = "medium"    # 中型企业
    SMALL = "small"      # 小微企业


class RiskType:
    """风险类型分类"""
    COMPLIANCE = "compliance"      # 合规风险
    MICROBIAL = "microbial"        # 微生物风险
    SEASONAL = "seasonal"          # 季节性风险
    TRANSPORT = "transport"        # 运输风险
    PRODUCTION = "production"      # 生产风险


@dataclass
class ValidationResult:
    """验证结果数据类"""
    metric_name: str
    value: float
    target_value: Optional[float] = None
    status: str = "unknown"  # "passed", "warning", "failed"
    
    def __post_init__(self):
        if self.target_value is not None:
            if self.metric_name in ["brier_score", "expected_calibration_error"]:
                # 越低越好的指标
                if self.value <= self.target_value:
                    self.status = "passed"
                elif self.value <= self.target_value * 1.5:
                    self.status = "warning"
                else:
                    self.status = "failed"
            else:
                # 越高越好的指标
                if self.value >= self.target_value:
                    self.status = "passed"
                elif self.value >= self.target_value * 0.8:
                    self.status = "warning"
                else:
                    self.status = "failed"


@dataclass
class LayerValidationReport:
    """分层验证报告"""
    layer_name: str
    layer_type: str  # "enterprise_scale", "risk_type"
    sample_count: int
    positive_count: int
    metrics: Dict[str, ValidationResult] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer_name": self.layer_name,
            "layer_type": self.layer_type,
            "sample_count": self.sample_count,
            "positive_count": self.positive_count,
            "positive_rate": self.positive_count / self.sample_count if self.sample_count > 0 else 0,
            "metrics": {
                name: {
                    "value": result.value,
                    "target": result.target_value,
                    "status": result.status
                }
                for name, result in self.metrics.items()
            }
        }


class StratifiedValidator:
    """
    分层验证器
    
    支持按企业规模、风险类型等维度进行分层验证
    """
    
    # 各分层的指标目标值
    TARGET_METRICS = {
        EnterpriseScale.LARGE: {
            "auc_pr": 0.75,
            "brier_score": 0.10,
            "recall": 0.80
        },
        EnterpriseScale.MEDIUM: {
            "auc_pr": 0.65,
            "brier_score": 0.15,
            "recall": 0.75
        },
        EnterpriseScale.SMALL: {
            "auc_pr": 0.55,
            "brier_score": 0.20,
            "recall": 0.70
        }
    }
    
    def __init__(self, target_metrics: Optional[Dict[str, Dict[str, float]]] = None):
        """
        初始化分层验证器
        
        Args:
            target_metrics: 各分层的指标目标值
        """
        self.target_metrics = target_metrics or self.TARGET_METRICS
        self.validation_reports: List[LayerValidationReport] = []
    
    def validate_by_enterprise_scale(
        self,
        y_true: np.ndarray,
        y_score: np.ndarray,
        enterprise_scales: List[str],
        node_ids: Optional[List[str]] = None
    ) -> Dict[str, LayerValidationReport]:
        """
        按企业规模分层验证
        
        Args:
            y_true: 真实标签
            y_score: 预测概率
            enterprise_scales: 每个样本对应的企业规模列表
            node_ids: 节点ID列表（可选）
            
        Returns:
            各规模的验证报告
        """
        reports = {}
        unique_scales = set(enterprise_scales)
        
        for scale in unique_scales:
            # 筛选该规模的样本
            mask = np.array([s == scale for s in enterprise_scales])
            
            if np.sum(mask) == 0:
                continue
            
            y_true_scale = y_true[mask]
            y_score_scale = y_score[mask]
            
            # 计算指标
            report = self._compute_layer_metrics(
                layer_name=scale,
                layer_type="enterprise_scale",
                y_true=y_true_scale,
                y_score=y_score_scale,
                target_metrics=self.target_metrics.get(scale, {})
            )
            
            reports[scale] = report
            self.validation_reports.append(report)
        
        return reports
    
    def validate_by_risk_type(
        self,
        y_true: np.ndarray,
        y_score: np.ndarray,
        risk_types: List[str],
        risk_features: Optional[Dict[str, np.ndarray]] = None
    ) -> Dict[str, LayerValidationReport]:
        """
        按风险类型分层验证
        
        Args:
            y_true: 真实标签
            y_score: 预测概率
            risk_types: 每个样本对应的风险类型列表
            risk_features: 风险特征字典（用于推断风险类型）
            
        Returns:
            各风险类型的验证报告
        """
        reports = {}
        unique_types = set(risk_types)
        
        # 各风险类型的目标值
        type_targets = {
            RiskType.COMPLIANCE: {"f1": 0.70, "recall": 0.80},
            RiskType.MICROBIAL: {"top_50_hit_rate": 0.30, "auc_pr": 0.60},
            RiskType.SEASONAL: {"recall": 0.75, "precision": 0.50},
            RiskType.TRANSPORT: {"auc_pr": 0.55, "brier_score": 0.18},
            RiskType.PRODUCTION: {"f1": 0.65, "recall": 0.75}
        }
        
        for risk_type in unique_types:
            mask = np.array([t == risk_type for t in risk_types])
            
            if np.sum(mask) == 0:
                continue
            
            y_true_type = y_true[mask]
            y_score_type = y_score[mask]
            
            report = self._compute_layer_metrics(
                layer_name=risk_type,
                layer_type="risk_type",
                y_true=y_true_type,
                y_score=y_score_type,
                target_metrics=type_targets.get(risk_type, {})
            )
            
            reports[risk_type] = report
            self.validation_reports.append(report)
        
        return reports
    
    def _compute_layer_metrics(
        self,
        layer_name: str,
        layer_type: str,
        y_true: np.ndarray,
        y_score: np.ndarray,
        target_metrics: Dict[str, float]
    ) -> LayerValidationReport:
        """
        计算分层指标
        
        Args:
            layer_name: 层名称
            layer_type: 层类型
            y_true: 真实标签
            y_score: 预测分数
            target_metrics: 目标指标值
            
        Returns:
            验证报告
        """
        n_samples = len(y_true)
        n_positives = np.sum(y_true)
        
        metrics = {}
        
        # 基本分类指标
        y_pred = (y_score >= 0.5).astype(int)
        
        metrics["recall"] = ValidationResult(
            metric_name="recall",
            value=calculate_recall(y_true, y_pred),
            target_value=target_metrics.get("recall")
        )
        
        metrics["precision"] = ValidationResult(
            metric_name="precision",
            value=calculate_precision(y_true, y_pred),
            target_value=target_metrics.get("precision")
        )
        
        metrics["f1"] = ValidationResult(
            metric_name="f1",
            value=calculate_f1(y_true, y_pred),
            target_value=target_metrics.get("f1")
        )
        
        # 排序指标
        if len(np.unique(y_true)) > 1:
            metrics["auc_roc"] = ValidationResult(
                metric_name="auc_roc",
                value=calculate_auc_roc(y_true, y_score),
                target_value=target_metrics.get("auc_roc")
            )
            
            metrics["auc_pr"] = ValidationResult(
                metric_name="auc_pr",
                value=calculate_auc_pr(y_true, y_score),
                target_value=target_metrics.get("auc_pr")
            )
        
        # 概率校准指标
        metrics["brier_score"] = ValidationResult(
            metric_name="brier_score",
            value=calculate_brier_score(y_true, y_score),
            target_value=target_metrics.get("brier_score")
        )
        
        # Top-K命中率
        for k in [10, 50, 100]:
            if n_samples >= k:
                top_k_result = calculate_top_k_accuracy(y_true, y_score, k=k)
                metrics[f"top_{k}_hit_rate"] = ValidationResult(
                    metric_name=f"top_{k}_hit_rate",
                    value=top_k_result["top_k_hit_rate"],
                    target_value=target_metrics.get(f"top_{k}_hit_rate")
                )
        
        return LayerValidationReport(
            layer_name=layer_name,
            layer_type=layer_type,
            sample_count=n_samples,
            positive_count=int(n_positives),
            metrics=metrics
        )
    
    def generate_summary(self) -> Dict[str, Any]:
        """
        生成验证摘要
        
        Returns:
            摘要字典
        """
        total_samples = sum(r.sample_count for r in self.validation_reports)
        total_positives = sum(r.positive_count for r in self.validation_reports)
        
        # 统计通过/警告/失败的指标
        status_counts = {"passed": 0, "warning": 0, "failed": 0}
        
        for report in self.validation_reports:
            for metric in report.metrics.values():
                status_counts[metric.status] += 1
        
        # 计算整体通过率
        total_metrics = sum(status_counts.values())
        pass_rate = status_counts["passed"] / total_metrics if total_metrics > 0 else 0
        
        return {
            "total_samples": total_samples,
            "total_positives": total_positives,
            "positive_rate": total_positives / total_samples if total_samples > 0 else 0,
            "num_layers": len(self.validation_reports),
            "status_summary": status_counts,
            "pass_rate": pass_rate,
            "overall_rating": self._calculate_rating(pass_rate)
        }
    
    def _calculate_rating(self, pass_rate: float) -> str:
        """计算总体评级"""
        if pass_rate >= 0.9:
            return "A+ (优秀)"
        elif pass_rate >= 0.8:
            return "A (良好)"
        elif pass_rate >= 0.7:
            return "B+ (较好)"
        elif pass_rate >= 0.6:
            return "B (合格)"
        elif pass_rate >= 0.5:
            return "C (待改进)"
        else:
            return "D (需重大改进)"


class ValidationReportGenerator:
    """验证报告生成器"""
    
    def __init__(self, validator: StratifiedValidator):
        """
        初始化
        
        Args:
            validator: 分层验证器
        """
        self.validator = validator
    
    def generate_markdown_report(
        self,
        model_name: str = "SupplyChainRiskPredictor",
        dataset_name: str = "Shanghai Dairy Supply Chain"
    ) -> str:
        """
        生成Markdown格式验证报告
        
        Args:
            model_name: 模型名称
            dataset_name: 数据集名称
            
        Returns:
            Markdown格式的报告
        """
        summary = self.validator.generate_summary()
        
        lines = [
            "=" * 70,
            "          乳制品供应链风险预测模型验证报告",
            "=" * 70,
            "",
            f"**模型名称**: {model_name}",
            f"**数据集**: {dataset_name}",
            f"**验证时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "-" * 70,
            "## 一、数据概况",
            "-" * 70,
            "",
            f"- **总样本数**: {summary['total_samples']:,}",
            f"- **正样本数**: {summary['total_positives']:,}",
            f"- **正样本率**: {summary['positive_rate']*100:.2f}%",
            f"- **分层数量**: {summary['num_layers']}",
            "",
            "-" * 70,
            "## 二、核心指标验证",
            "-" * 70,
            "",
        ]
        
        # 指标验证状态
        status_summary = summary['status_summary']
        lines.extend([
            "| 状态 | 数量 | 占比 |",
            "|------|------|------|",
            f"| ✅ 通过 | {status_summary['passed']} | {status_summary['passed']/sum(status_summary.values())*100:.1f}% |",
            f"| ⚠️ 警告 | {status_summary['warning']} | {status_summary['warning']/sum(status_summary.values())*100:.1f}% |",
            f"| ❌ 失败 | {status_summary['failed']} | {status_summary['failed']/sum(status_summary.values())*100:.1f}% |",
            "",
        ])
        
        # 分层验证结果
        lines.extend([
            "-" * 70,
            "## 三、分层验证结果",
            "-" * 70,
            "",
        ])
        
        for report in self.validator.validation_reports:
            lines.extend([
                f"### {report.layer_name} ({report.layer_type})",
                "",
                f"- **样本数**: {report.sample_count:,}",
                f"- **正样本数**: {report.positive_count:,}",
                f"- **正样本率**: {report.positive_count/report.sample_count*100:.2f}%" if report.sample_count > 0 else "- **正样本率**: N/A",
                "",
                "| 指标 | 得分 | 目标值 | 状态 |",
                "|------|------|--------|------|",
            ])
            
            for metric_name, result in report.metrics.items():
                status_icon = "✅" if result.status == "passed" else "⚠️" if result.status == "warning" else "❌"
                target_str = f"{result.target_value:.3f}" if result.target_value else "-"
                lines.append(
                    f"| {metric_name} | {result.value:.3f} | {target_str} | {status_icon} |"
                )
            
            lines.append("")
        
        # 综合评估
        lines.extend([
            "-" * 70,
            "## 四、综合评估",
            "-" * 70,
            "",
            f"**总体评级**: {summary['overall_rating']}",
            f"**指标通过率**: {summary['pass_rate']*100:.1f}%",
            "",
        ])
        
        # 生成改进建议
        suggestions = self._generate_suggestions()
        if suggestions:
            lines.extend([
                "-" * 70,
                "## 五、改进建议",
                "-" * 70,
                "",
            ])
            for i, suggestion in enumerate(suggestions, 1):
                lines.append(f"{i}. {suggestion}")
            lines.append("")
        
        lines.extend([
            "",
            "=" * 70,
            "                          报告结束",
            "=" * 70,
        ])
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> Dict[str, Any]:
        """
        生成JSON格式验证报告
        
        Returns:
            JSON格式的报告字典
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "summary": self.validator.generate_summary(),
            "layer_reports": [
                report.to_dict() for report in self.validator.validation_reports
            ]
        }
    
    def _generate_suggestions(self) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        for report in self.validator.validation_reports:
            failed_metrics = [
                name for name, result in report.metrics.items()
                if result.status == "failed"
            ]
            
            if failed_metrics:
                suggestions.append(
                    f"{report.layer_name}层面: 需改进指标 - {', '.join(failed_metrics)}"
                )
            
            # 特定建议
            if report.layer_name == EnterpriseScale.SMALL:
                recall_result = report.metrics.get("recall")
                if recall_result and recall_result.status in ["warning", "failed"]:
                    suggestions.append(
                        f"小微企业召回率较低，建议增加小微企业训练样本或使用迁移学习"
                    )
        
        # 总体建议
        summary = self.validator.generate_summary()
        if summary['positive_rate'] < 0.001:
            suggestions.append(
                "正样本率过低，建议增加弱监督标签或使用过采样技术"
            )
        
        return suggestions
    
    def save_report(
        self,
        output_path: str,
        format: str = "markdown"
    ):
        """
        保存报告到文件
        
        Args:
            output_path: 输出路径
            format: 格式 ("markdown", "json")
        """
        if format == "markdown":
            content = self.generate_markdown_report()
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
        elif format == "json":
            content = self.generate_json_report()
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
        else:
            raise ValueError(f"不支持的格式: {format}")
        
        logger.info(f"验证报告已保存到: {output_path}")


def validate_model_performance(
    y_true: np.ndarray,
    y_score: np.ndarray,
    enterprise_scales: Optional[List[str]] = None,
    risk_types: Optional[List[str]] = None,
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    便捷函数：验证模型性能
    
    Args:
        y_true: 真实标签
        y_score: 预测概率
        enterprise_scales: 企业规模列表
        risk_types: 风险类型列表
        output_path: 报告输出路径
        
    Returns:
        验证结果字典
    """
    validator = StratifiedValidator()
    
    # 按企业规模验证
    if enterprise_scales:
        scale_reports = validator.validate_by_enterprise_scale(
            y_true, y_score, enterprise_scales
        )
    
    # 按风险类型验证
    if risk_types:
        type_reports = validator.validate_by_risk_type(
            y_true, y_score, risk_types
        )
    
    # 生成报告
    report_gen = ValidationReportGenerator(validator)
    
    if output_path:
        if output_path.endswith('.json'):
            report_gen.save_report(output_path, format="json")
        else:
            report_gen.save_report(output_path, format="markdown")
    
    return report_gen.generate_json_report()


# 便捷函数
__all__ = [
    'EnterpriseScale',
    'RiskType',
    'ValidationResult',
    'LayerValidationReport',
    'StratifiedValidator',
    'ValidationReportGenerator',
    'validate_model_performance'
]
