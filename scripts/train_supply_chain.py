#!/usr/bin/env python3
"""
供应链风险预测训练脚本

使用示例:
    python scripts/train_supply_chain.py --config configs/supply_chain.yaml --data data/processed/train.pt

作者: DairyRisk Team
日期: 2025-03
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torch_geometric.data import HeteroData

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dairyrisk.utils.config import load_config, create_default_config
from dairyrisk.utils.logging import setup_logger, log_metrics_table
from dairyrisk.training.losses import get_loss_function
from dairyrisk.training.callbacks import (
    ModelCheckpoint,
    EarlyStopping,
    LRScheduler,
    TrainingLogger
)
from dairyrisk.evaluation.metrics import calculate_metrics_at_thresholds


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='乳制品供应链风险预测模型训练'
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        default='configs/supply_chain.yaml',
        help='配置文件路径'
    )
    
    parser.add_argument(
        '--train-data',
        type=str,
        required=True,
        help='训练数据路径'
    )
    
    parser.add_argument(
        '--val-data',
        type=str,
        default=None,
        help='验证数据路径（可选）'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default='outputs',
        help='输出目录'
    )
    
    parser.add_argument(
        '--experiment-name',
        type=str,
        default=None,
        help='实验名称'
    )
    
    parser.add_argument(
        '--device',
        type=str,
        default='auto',
        help='计算设备 (auto/cpu/cuda)'
    )
    
    parser.add_argument(
        '--epochs',
        type=int,
        default=None,
        help='训练轮数（覆盖配置）'
    )
    
    parser.add_argument(
        '--lr',
        type=float,
        default=None,
        help='学习率（覆盖配置）'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=None,
        help='批次大小（覆盖配置）'
    )
    
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='随机种子'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='详细输出'
    )
    
    return parser.parse_args()


class MockGNN(nn.Module):
    """
    Mock GNN模型
    
    由于GNN模型本身不实现，这里提供一个Mock模型用于演示训练流程
    """
    
    def __init__(
        self,
        in_channels: int = 10,
        hidden_channels: int = 128,
        num_layers: int = 2,
        dropout: float = 0.1,
        **kwargs
    ):
        super().__init__()
        
        self.input_proj = nn.Linear(in_channels, hidden_channels)
        
        layers = []
        for _ in range(num_layers):
            layers.extend([
                nn.Linear(hidden_channels, hidden_channels),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.BatchNorm1d(hidden_channels)
            ])
        self.layers = nn.Sequential(*layers)
        
        # 风险预测头
        self.risk_head = nn.Sequential(
            nn.Linear(hidden_channels, hidden_channels // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_channels // 2, 1)
        )
        
        # 置信度估计头
        self.confidence_head = nn.Sequential(
            nn.Linear(hidden_channels, hidden_channels // 2),
            nn.ReLU(),
            nn.Linear(hidden_channels // 2, 1),
            nn.Softplus()
        )
    
    def forward(self, x):
        """前向传播"""
        x = self.input_proj(x)
        x = self.layers(x)
        
        risk_logits = self.risk_head(x).squeeze(-1)
        confidence = 1 / (1 + self.confidence_head(x).squeeze(-1))
        
        return {
            "risk_logits": risk_logits,
            "risk_probability": torch.sigmoid(risk_logits),
            "confidence": confidence
        }


def load_data(data_path: str, device: str):
    """加载数据"""
    data_path = Path(data_path)
    
    if not data_path.exists():
        raise FileNotFoundError(f"数据文件不存在: {data_path}")
    
    logger.info(f"加载数据: {data_path}")
    
    data = torch.load(data_path, map_location=device)
    
    if isinstance(data, dict):
        return data
    elif isinstance(data, HeteroData):
        # 从异构图中提取数据
        target_type = 'batch'
        if hasattr(data[target_type], 'x'):
            x = data[target_type].x
        else:
            # 生成随机特征
            x = torch.randn(data[target_type].num_nodes, 10)
        
        if hasattr(data[target_type], 'y'):
            y = data[target_type].y
        else:
            y = torch.zeros(data[target_type].num_nodes)
        
        return {'x': x, 'y': y}
    else:
        raise ValueError(f"不支持的数据格式: {type(data)}")


def train_epoch(
    model: nn.Module,
    train_data: Dict[str, torch.Tensor],
    optimizer: torch.optim.Optimizer,
    loss_fn: nn.Module,
    config: Dict[str, Any]
) -> Dict[str, float]:
    """
    训练一个epoch
    
    Args:
        model: 模型
        train_data: 训练数据
        optimizer: 优化器
        loss_fn: 损失函数
        config: 配置
        
    Returns:
        训练指标
    """
    model.train()
    
    x = train_data['x']
    y = train_data['y'].float()
    
    # 前向传播
    predictions = model(x)
    
    # 计算损失
    loss_dict = loss_fn(predictions, y)
    
    # 反向传播
    optimizer.zero_grad()
    loss_dict['total_loss'].backward()
    
    # 梯度裁剪
    if config.get('training', {}).get('gradient_clip', {}).get('enabled', True):
        max_norm = config.get('training', {}).get('gradient_clip', {}).get('max_norm', 1.0)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm)
    
    optimizer.step()
    
    return {
        'loss': loss_dict['total_loss'].item(),
        'regression_loss': loss_dict['regression_loss'].item(),
        'classification_loss': loss_dict['classification_loss'].item(),
        'confidence_loss': loss_dict['confidence_loss'].item()
    }


def validate(
    model: nn.Module,
    val_data: Dict[str, torch.Tensor],
    loss_fn: nn.Module
) -> Dict[str, float]:
    """
    验证
    
    Args:
        model: 模型
        val_data: 验证数据
        loss_fn: 损失函数
        
    Returns:
        验证指标
    """
    model.eval()
    
    with torch.no_grad():
        x = val_data['x']
        y = val_data['y'].float()
        
        predictions = model(x)
        loss_dict = loss_fn(predictions, y)
        
        # 计算分类指标
        y_pred = (predictions['risk_probability'] >= 0.5).cpu().numpy()
        y_true = y.cpu().numpy()
        
        accuracy = np.mean(y_pred == y_true)
    
    return {
        'val_loss': loss_dict['total_loss'].item(),
        'val_accuracy': accuracy
    }


def main():
    """主函数"""
    global logger
    
    # 解析参数
    args = parse_args()
    
    # 设置日志
    logger = setup_logger(
        name='train',
        level='DEBUG' if args.verbose else 'INFO',
        use_color=True
    )
    
    logger.info("=" * 60)
    logger.info("乳制品供应链风险预测模型训练")
    logger.info("=" * 60)
    
    # 设置随机种子
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    
    # 加载配置
    if Path(args.config).exists():
        config = load_config(args.config)
    else:
        logger.warning(f"配置文件不存在，使用默认配置: {args.config}")
        config = create_default_config()
    
    # 命令行参数覆盖配置
    num_epochs = args.epochs or config.get('training', {}).get('num_epochs', 100)
    learning_rate = args.lr or config.get('training', {}).get('learning_rate', 0.001)
    batch_size = args.batch_size or config.get('data', {}).get('batch_size', 32)
    
    # 确定设备
    if args.device == 'auto':
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    else:
        device = torch.device(args.device)
    
    logger.info(f"使用设备: {device}")
    logger.info(f"训练轮数: {num_epochs}")
    logger.info(f"学习率: {learning_rate}")
    logger.info(f"批次大小: {batch_size}")
    
    try:
        # 加载数据
        train_data = load_data(args.train_data, device)
        train_data['x'] = train_data['x'].to(device)
        train_data['y'] = train_data['y'].to(device)
        
        logger.info(f"训练样本数: {len(train_data['y'])}")
        logger.info(f"正样本数: {(train_data['y'] > 0.5).sum().item()}")
        
        val_data = None
        if args.val_data:
            val_data = load_data(args.val_data, device)
            val_data['x'] = val_data['x'].to(device)
            val_data['y'] = val_data['y'].to(device)
            logger.info(f"验证样本数: {len(val_data['y'])}")
        
        # 创建模型（使用Mock）
        in_channels = train_data['x'].shape[1]
        hidden_dim = config.get('model', {}).get('hidden_dim', 128)
        
        model = MockGNN(
            in_channels=in_channels,
            hidden_channels=hidden_dim,
            num_layers=config.get('model', {}).get('num_layers', 2),
            dropout=config.get('model', {}).get('dropout', 0.1)
        ).to(device)
        
        logger.info(f"模型参数数: {sum(p.numel() for p in model.parameters())}")
        
        # 创建优化器
        optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=learning_rate,
            weight_decay=config.get('training', {}).get('weight_decay', 0.0001)
        )
        
        # 创建损失函数
        loss_config = config.get('training', {}).get('loss', {})
        loss_fn = get_loss_function(
            loss_type=loss_config.get('type', 'supply_chain_risk'),
            **{k: v for k, v in loss_config.items() if k != 'type'}
        )
        
        # 创建回调
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        checkpoint = ModelCheckpoint(
            filepath=str(output_dir / 'best_model.pt'),
            monitor='val_loss' if val_data else 'loss',
            mode='min',
            verbose=1
        )
        
        early_stopping = None
        if config.get('training', {}).get('early_stopping', {}).get('enabled', True):
            early_stopping = EarlyStopping(
                monitor='val_loss' if val_data else 'loss',
                patience=config.get('training', {}).get('early_stopping', {}).get('patience', 10),
                verbose=1
            )
        
        scheduler = LRScheduler(
            optimizer,
            mode=config.get('training', {}).get('scheduler', {}).get('type', 'cosine'),
            T_max=num_epochs
        )
        
        train_logger = TrainingLogger(
            log_dir=str(output_dir / 'logs'),
            experiment_name=args.experiment_name or 'train'
        )
        
        # 训练循环
        logger.info("\n开始训练...")
        logger.info("=" * 60)
        
        for epoch in range(1, num_epochs + 1):
            # 训练
            train_metrics = train_epoch(model, train_data, optimizer, loss_fn, config)
            
            # 验证
            val_metrics = {}
            if val_data:
                val_metrics = validate(model, val_data, loss_fn)
            
            # 记录日志
            train_logger.log_epoch(epoch, train_metrics, val_metrics)
            
            # 打印进度
            if epoch % 10 == 0 or epoch == 1:
                msg = f"Epoch {epoch}/{num_epochs} - Loss: {train_metrics['loss']:.4f}"
                if val_metrics:
                    msg += f", Val Loss: {val_metrics['val_loss']:.4f}"
                logger.info(msg)
            
            # 检查点
            all_metrics = {**train_metrics, **val_metrics}
            checkpoint.step(model, epoch, all_metrics, optimizer)
            
            # 早停
            if early_stopping and early_stopping.step(epoch, all_metrics, model):
                break
            
            # 学习率调度
            if val_data:
                scheduler.step(val_metrics.get('val_loss'))
            else:
                scheduler.step(train_metrics['loss'])
        
        # 保存最终模型
        final_path = output_dir / 'final_model.pt'
        torch.save({
            'model_state_dict': model.state_dict(),
            'config': config,
            'epoch': epoch
        }, final_path)
        
        logger.info(f"\n训练完成！")
        logger.info(f"最佳模型: {checkpoint.filepath}")
        logger.info(f"最终模型: {final_path}")
        
        # 打印最终指标
        final_metrics = checkpoint.get_history()[-1]['metrics'] if checkpoint.get_history() else train_metrics
        log_metrics_table(logger, final_metrics, title="最终训练指标")
        
        return 0
    
    except Exception as e:
        logger.exception(f"训练失败: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
