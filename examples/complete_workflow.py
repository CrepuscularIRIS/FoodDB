#!/usr/bin/env python3
"""
完整工作流程示例

演示如何使用dairyrisk框架进行完整的供应链风险预测流程：
1. 数据生成
2. 弱监督标签生成
3. 模型训练（使用Mock）
4. 模型评估
5. 生成报告

作者: DairyRisk Team
日期: 2025-03
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import torch
import json

from dairyrisk.utils.config import load_config, create_default_config
from dairyrisk.utils.logging import setup_logger, log_metrics_table
from dairyrisk.data.labels import RuleEngine, fuse_labels, LabelSource
from dairyrisk.evaluation.metrics import evaluate_all_metrics
from dairyrisk.evaluation.validator import StratifiedValidator, ValidationReportGenerator


def step1_generate_data(config, logger):
    """
    步骤1: 生成/加载数据
    
    在实际应用中，这里会加载真实的供应链数据
    """
    logger.info("\n" + "=" * 60)
    logger.info("步骤 1: 数据生成")
    logger.info("=" * 60)
    
    # 生成模拟数据（在实际应用中替换为真实数据加载）
    np.random.seed(42)
    n_samples = 1000
    
    data = []
    for i in range(n_samples):
        # 生成特征
        sample = {
            'node_id': f'BATCH_{i:05d}',
            'enterprise_scale': np.random.choice(['large', 'medium', 'small']),
            'transport_temp': np.random.normal(4, 2),
            'transport_duration': np.random.uniform(1, 10),
            'cleanliness_level': np.random.choice(['A', 'B', 'C', 'D']),
            'pasteurization_temp': np.random.normal(72, 2),
            'pasteurization_temp_std': np.random.uniform(0.5, 3.0),
            'month': np.random.randint(1, 13),
            'raw_colony_count': np.random.lognormal(10, 0.5),
        }
        data.append(sample)
    
    logger.info(f"生成了 {len(data)} 个样本")
    logger.info(f"企业规模分布: {np.unique([d['enterprise_scale'] for d in data], return_counts=True)}")
    
    return data


def step2_generate_weak_labels(data, config, logger):
    """
    步骤2: 生成弱监督标签
    
    使用规则引擎基于微生物生长机理生成标签
    """
    logger.info("\n" + "=" * 60)
    logger.info("步骤 2: 弱监督标签生成")
    logger.info("=" * 60)
    
    # 创建规则引擎
    engine = RuleEngine()
    
    # 为每个样本生成标签
    labeled_data = []
    all_labels = {source.value: [] for source in LabelSource}
    
    for sample in data:
        # 应用规则引擎
        rule_results = engine.evaluate(sample)
        
        # 收集标签
        labels_for_fusion = {}
        for rule_type, label in rule_results.items():
            labels_for_fusion[label.source.value] = labels_for_fusion.get(label.source.value, [])
            labels_for_fusion[label.source.value].append(label)
        
        # 融合标签
        if labels_for_fusion:
            fused_score = fuse_labels(labels_for_fusion)
            final_score = fused_score.get('global', 0.5)
        else:
            final_score = 0.1  # 默认低风险
        
        # 保存标签
        sample['weak_label'] = final_score
        sample['rule_details'] = {k.value: v.risk_score for k, v in rule_results.items()}
        labeled_data.append(sample)
        
        # 统计
        all_labels[LabelSource.WEAK_SUPERVISION.value].append(final_score)
    
    # 打印统计
    risk_scores = [d['weak_label'] for d in labeled_data]
    logger.info(f"弱监督标签统计:")
    logger.info(f"  平均风险得分: {np.mean(risk_scores):.3f}")
    logger.info(f"  高风险样本 (>0.7): {sum(1 for s in risk_scores if s > 0.7)}")
    logger.info(f"  中风险样本 (0.3-0.7): {sum(1 for s in risk_scores if 0.3 <= s <= 0.7)}")
    logger.info(f"  低风险样本 (<0.3): {sum(1 for s in risk_scores if s < 0.3)}")
    
    # 基于风险得分生成真实标签（用于评估）
    # 实际应用中，这部分应该是真实的抽检结果
    for sample in labeled_data:
        # 根据风险得分以一定概率标记为正样本
        # 风险越高，越可能为正样本
        sample['true_label'] = 1.0 if np.random.random() < sample['weak_label'] * 0.3 else 0.0
    
    positive_rate = np.mean([d['true_label'] for d in labeled_data])
    logger.info(f"  真实正样本率: {positive_rate*100:.2f}%")
    
    return labeled_data


def step3_prepare_features(data, config, logger):
    """
    步骤3: 特征工程
    
    将原始数据转换为模型输入特征
    """
    logger.info("\n" + "=" * 60)
    logger.info("步骤 3: 特征工程")
    logger.info("=" * 60)
    
    # 定义特征列表
    feature_keys = [
        'transport_temp',
        'transport_duration',
        'pasteurization_temp',
        'pasteurization_temp_std',
        'raw_colony_count'
    ]
    
    # 编码类别特征
    cleanliness_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
    scale_map = {'large': 0, 'medium': 1, 'small': 2}
    
    features = []
    labels = []
    metadata = {'enterprise_scales': []}
    
    for sample in data:
        feat = []
        
        # 数值特征
        for key in feature_keys:
            val = sample.get(key, 0)
            feat.append(float(val) if val is not None else 0)
        
        # 类别特征编码
        feat.append(cleanliness_map.get(sample.get('cleanliness_level', 'C'), 2))
        feat.append(scale_map.get(sample.get('enterprise_scale', 'medium'), 1))
        feat.append(float(sample.get('month', 6)) / 12.0)  # 归一化
        
        features.append(feat)
        labels.append(sample['true_label'])
        metadata['enterprise_scales'].append(sample['enterprise_scale'])
    
    features = np.array(features)
    labels = np.array(labels)
    
    # 特征归一化
    feature_mean = features.mean(axis=0)
    feature_std = features.std(axis=0) + 1e-8
    features = (features - feature_mean) / feature_std
    
    logger.info(f"特征矩阵形状: {features.shape}")
    logger.info(f"特征数量: {features.shape[1]}")
    
    return features, labels, metadata


def step4_train_model(features, labels, config, logger):
    """
    步骤4: 模型训练
    
    使用Mock模型演示训练流程
    """
    logger.info("\n" + "=" * 60)
    logger.info("步骤 4: 模型训练")
    logger.info("=" * 60)
    
    from dairyrisk.training.losses import SupplyChainRiskLoss
    
    # 简单线性模型（Mock）
    n_features = features.shape[1]
    weights = np.random.randn(n_features) * 0.1
    bias = -1.0  # 初始偏置倾向于预测低风险
    
    # 简单的梯度下降训练
    lr = 0.01
    n_epochs = 100
    
    loss_fn = SupplyChainRiskLoss(pos_weight=10.0)
    
    for epoch in range(n_epochs):
        # 前向传播
        logits = features @ weights + bias
        probs = 1 / (1 + np.exp(-logits))
        
        # 计算损失（简化的BCE）
        eps = 1e-7
        loss = -np.mean(
            labels * np.log(probs + eps) * 10 +  # 正样本加权
            (1 - labels) * np.log(1 - probs + eps)
        )
        
        # 梯度计算
        error = probs - labels
        error = np.where(labels > 0.5, error * 10, error)  # 正样本梯度加权
        
        grad_w = features.T @ error / len(labels)
        grad_b = np.mean(error)
        
        # 更新
        weights -= lr * grad_w
        bias -= lr * grad_b
        
        if (epoch + 1) % 20 == 0:
            logger.info(f"  Epoch {epoch+1}/{n_epochs}, Loss: {loss:.4f}")
    
    # 最终预测
    logits = features @ weights + bias
    predictions = 1 / (1 + np.exp(-logits))
    
    logger.info(f"训练完成")
    logger.info(f"预测概率范围: [{predictions.min():.3f}, {predictions.max():.3f}]")
    
    return predictions


def step5_evaluate(predictions, labels, metadata, config, logger):
    """
    步骤5: 模型评估
    
    计算各项指标并生成验证报告
    """
    logger.info("\n" + "=" * 60)
    logger.info("步骤 5: 模型评估")
    logger.info("=" * 60)
    
    # 计算所有指标
    metrics = evaluate_all_metrics(
        y_true=labels,
        y_score=predictions,
        threshold=config.get('evaluation', {}).get('threshold', 0.5),
        k_values=config.get('evaluation', {}).get('top_k', [10, 50, 100])
    )
    
    # 打印核心指标
    logger.info("\n分类性能:")
    log_metrics_table(logger, metrics['classification'], title="分类性能指标")
    
    logger.info("\n排序性能:")
    log_metrics_table(logger, metrics['ranking'], title="排序性能指标")
    
    logger.info("\n概率校准:")
    log_metrics_table(logger, metrics['probability'], title="概率校准指标")
    
    logger.info("\nTop-K命中率:")
    top_k_flat = {k: v['hit_rate'] for k, v in metrics['top_k'].items()}
    log_metrics_table(logger, top_k_flat, title="Top-K命中率")
    
    # 分层验证
    logger.info("\n分层验证:")
    validator = StratifiedValidator()
    validator.validate_by_enterprise_scale(
        y_true=labels,
        y_score=predictions,
        enterprise_scales=metadata['enterprise_scales']
    )
    
    summary = validator.generate_summary()
    logger.info(f"分层验证摘要:")
    logger.info(f"  总样本数: {summary['total_samples']}")
    logger.info(f"  正样本数: {summary['total_positives']}")
    logger.info(f"  正样本率: {summary['positive_rate']*100:.2f}%")
    logger.info(f"  指标通过率: {summary['pass_rate']*100:.1f}%")
    logger.info(f"  总体评级: {summary['overall_rating']}")
    
    return metrics, validator


def step6_generate_report(metrics, validator, config, logger):
    """
    步骤6: 生成评估报告
    """
    logger.info("\n" + "=" * 60)
    logger.info("步骤 6: 生成评估报告")
    logger.info("=" * 60)
    
    report_gen = ValidationReportGenerator(validator)
    
    # Markdown报告
    md_report = report_gen.generate_markdown_report()
    
    # 保存报告
    report_dir = Path('reports')
    report_dir.mkdir(exist_ok=True)
    
    md_path = report_dir / 'evaluation_report_example.md'
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_report)
    
    logger.info(f"Markdown报告已保存: {md_path}")
    
    # JSON报告
    json_report = report_gen.generate_json_report()
    json_path = report_dir / 'evaluation_report_example.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_report, f, indent=2, ensure_ascii=False)
    
    logger.info(f"JSON报告已保存: {json_path}")
    
    return md_report


def main():
    """主函数"""
    # 设置日志
    logger = setup_logger(
        name='complete_workflow',
        level='INFO',
        use_color=True
    )
    
    logger.info("=" * 60)
    logger.info("乳制品供应链风险预测 - 完整工作流程示例")
    logger.info("=" * 60)
    
    # 加载配置
    config_path = project_root / 'configs' / 'supply_chain.yaml'
    if config_path.exists():
        config = load_config(str(config_path))
        logger.info(f"配置已加载: {config_path}")
    else:
        config = create_default_config()
        logger.info("使用默认配置")
    
    try:
        # 步骤1: 数据生成
        data = step1_generate_data(config, logger)
        
        # 步骤2: 弱监督标签生成
        labeled_data = step2_generate_weak_labels(data, config, logger)
        
        # 步骤3: 特征工程
        features, labels, metadata = step3_prepare_features(labeled_data, config, logger)
        
        # 步骤4: 模型训练
        predictions = step4_train_model(features, labels, config, logger)
        
        # 步骤5: 模型评估
        metrics, validator = step5_evaluate(predictions, labels, metadata, config, logger)
        
        # 步骤6: 生成报告
        report = step6_generate_report(metrics, validator, config, logger)
        
        logger.info("\n" + "=" * 60)
        logger.info("工作流程完成！")
        logger.info("=" * 60)
        
        # 打印报告摘要
        logger.info("\n报告摘要:")
        for line in report.split('\n')[:30]:
            if line.strip():
                logger.info(line)
        logger.info("...")
        
        return 0
    
    except Exception as e:
        logger.exception(f"工作流程失败: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
