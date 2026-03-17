#!/usr/bin/env python3
"""
供应链风险预测评估脚本

使用示例:
    python scripts/evaluate_supply_chain.py --config configs/supply_chain.yaml --data data/processed/test.pt

作者: DairyRisk Team
日期: 2025-03
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import torch
from torch_geometric.data import HeteroData

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dairyrisk.utils.config import load_config, create_default_config
from dairyrisk.utils.logging import setup_logger, log_metrics_table
from dairyrisk.evaluation.metrics import evaluate_all_metrics
from dairyrisk.evaluation.validator import (
    StratifiedValidator,
    ValidationReportGenerator
)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='乳制品供应链风险预测模型评估'
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        default='configs/supply_chain.yaml',
        help='配置文件路径'
    )
    
    parser.add_argument(
        '--data', '-d',
        type=str,
        required=True,
        help='测试数据路径 (.pt 或 .npy 格式)'
    )
    
    parser.add_argument(
        '--model', '-m',
        type=str,
        default=None,
        help='模型检查点路径（可选，如果不提供则生成随机预测）'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='reports/evaluation_report.md',
        help='评估报告输出路径'
    )
    
    parser.add_argument(
        '--format', '-f',
        type=str,
        choices=['markdown', 'json'],
        default='markdown',
        help='报告格式'
    )
    
    parser.add_argument(
        '--device',
        type=str,
        default='auto',
        help='计算设备 (auto/cpu/cuda)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='详细输出'
    )
    
    return parser.parse_args()


def load_data(data_path: str, device: str) -> tuple:
    """
    加载测试数据
    
    Args:
        data_path: 数据路径
        device: 设备
        
    Returns:
        (y_true, y_score, metadata) 元组
    """
    data_path = Path(data_path)
    
    if not data_path.exists():
        raise FileNotFoundError(f"数据文件不存在: {data_path}")
    
    logger.info(f"加载数据: {data_path}")
    
    # 根据后缀加载
    if data_path.suffix == '.pt':
        data = torch.load(data_path, map_location=device)
        
        if isinstance(data, dict):
            y_true = data.get('y_true')
            y_score = data.get('y_score')
            metadata = data.get('metadata', {})
        elif isinstance(data, HeteroData):
            # 从异构图中提取标签
            target_type = 'batch'
            if hasattr(data[target_type], 'y'):
                y_true = data[target_type].y.cpu().numpy()
            else:
                raise ValueError("数据中未找到标签")
            
            # 如果没有预测分数，生成随机预测
            y_score = np.random.random(len(y_true))
            metadata = {'node_type': target_type}
        else:
            raise ValueError(f"不支持的数据格式: {type(data)}")
    
    elif data_path.suffix == '.npy':
        data = np.load(data_path, allow_pickle=True).item()
        y_true = data.get('y_true')
        y_score = data.get('y_score')
        metadata = data.get('metadata', {})
    
    else:
        raise ValueError(f"不支持的文件格式: {data_path.suffix}")
    
    # 确保是numpy数组
    if isinstance(y_true, torch.Tensor):
        y_true = y_true.cpu().numpy()
    if isinstance(y_score, torch.Tensor):
        y_score = y_score.cpu().numpy()
    
    logger.info(f"数据加载完成: {len(y_true)} 个样本")
    logger.info(f"正样本数: {np.sum(y_true > 0.5)} ({np.sum(y_true > 0.5)/len(y_true)*100:.2f}%)")
    
    return y_true, y_score, metadata


def run_evaluation(
    y_true: np.ndarray,
    y_score: np.ndarray,
    metadata: Dict[str, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    运行评估
    
    Args:
        y_true: 真实标签
        y_score: 预测分数
        metadata: 元数据
        config: 配置
        
    Returns:
        评估结果字典
    """
    logger.info("=" * 60)
    logger.info("开始评估")
    logger.info("=" * 60)
    
    # 1. 计算所有指标
    logger.info("\n[1/3] 计算评估指标...")
    metrics = evaluate_all_metrics(
        y_true=y_true,
        y_score=y_score,
        threshold=config.get('evaluation', {}).get('threshold', 0.5),
        k_values=config.get('evaluation', {}).get('top_k', [10, 50, 100])
    )
    
    # 2. 分层验证
    logger.info("\n[2/3] 分层验证...")
    validator = StratifiedValidator()
    
    # 按企业规模验证（如果有元数据）
    if 'enterprise_scales' in metadata:
        validator.validate_by_enterprise_scale(
            y_true=y_true,
            y_score=y_score,
            enterprise_scales=metadata['enterprise_scales']
        )
    
    # 按风险类型验证
    if 'risk_types' in metadata:
        validator.validate_by_risk_type(
            y_true=y_true,
            y_score=y_score,
            risk_types=metadata['risk_types']
        )
    
    # 3. 生成验证报告
    logger.info("\n[3/3] 生成验证报告...")
    report_gen = ValidationReportGenerator(validator)
    
    # 打印核心指标
    logger.info("\n核心指标:")
    log_metrics_table(
        logger,
        {
            "Recall": metrics['classification']['recall'],
            "Precision": metrics['classification']['precision'],
            "F1-Score": metrics['classification']['f1'],
            "AUC-ROC": metrics['ranking']['auc_roc'],
            "AUC-PR": metrics['ranking']['auc_pr'],
            "Brier Score": metrics['probability']['brier_score']
        },
        title="核心评估指标"
    )
    
    # 打印Top-K命中率
    logger.info("\nTop-K命中率:")
    top_k_metrics = {
        f"Top-{k}": v['hit_rate']
        for k, v in metrics['top_k'].items()
    }
    log_metrics_table(logger, top_k_metrics, title="Top-K命中率")
    
    return {
        'metrics': metrics,
        'validator': validator,
        'report_generator': report_gen
    }


def main():
    """主函数"""
    global logger
    
    # 解析参数
    args = parse_args()
    
    # 设置日志
    logger = setup_logger(
        name='evaluate',
        level='DEBUG' if args.verbose else 'INFO',
        use_color=True
    )
    
    logger.info("=" * 60)
    logger.info("乳制品供应链风险预测模型评估")
    logger.info("=" * 60)
    
    # 加载配置
    if Path(args.config).exists():
        config = load_config(args.config)
    else:
        logger.warning(f"配置文件不存在，使用默认配置: {args.config}")
        config = create_default_config()
    
    # 确定设备
    if args.device == 'auto':
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    else:
        device = args.device
    
    logger.info(f"使用设备: {device}")
    
    try:
        # 加载数据
        y_true, y_score, metadata = load_data(args.data, device)
        
        # 运行评估
        results = run_evaluation(y_true, y_score, metadata, config)
        
        # 保存报告
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if args.format == 'markdown':
            results['report_generator'].save_report(output_path, format='markdown')
        else:
            results['report_generator'].save_report(output_path, format='json')
        
        logger.info(f"\n评估报告已保存到: {output_path}")
        
        # 返回退出码
        summary = results['validator'].generate_summary()
        if summary['pass_rate'] >= 0.8:
            logger.info("\n✅ 评估通过！")
            return 0
        elif summary['pass_rate'] >= 0.6:
            logger.warning("\n⚠️ 评估警告，部分指标未达标")
            return 1
        else:
            logger.error("\n❌ 评估失败，多项指标未达标")
            return 2
    
    except Exception as e:
        logger.exception(f"评估失败: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
