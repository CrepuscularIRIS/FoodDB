"""
训练回调模块 (5.8节)

包含:
- ModelCheckpoint: 模型检查点
- EarlyStopping: 早停
- LRScheduler: 学习率调度

作者: DairyRisk Team
日期: 2025-03
"""

import os
import torch
import numpy as np
from typing import Dict, Optional, Any, Callable, List
from pathlib import Path
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class ModelCheckpoint:
    """
    模型检查点
    
    保存训练过程中表现最好的模型
    """
    
    def __init__(
        self,
        filepath: str = "checkpoints/best_model.pt",
        monitor: str = "val_loss",
        mode: str = "min",
        save_best_only: bool = True,
        save_weights_only: bool = False,
        verbose: int = 1
    ):
        """
        初始化
        
        Args:
            filepath: 保存路径
            monitor: 监控指标
            mode: 优化模式 ("min" 或 "max")
            save_best_only: 只保存最好的模型
            save_weights_only: 只保存权重（不保存优化器状态）
            verbose: 日志详细程度
        """
        self.filepath = Path(filepath)
        self.monitor = monitor
        self.mode = mode
        self.save_best_only = save_best_only
        self.save_weights_only = save_weights_only
        self.verbose = verbose
        
        # 创建目录
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # 最佳值追踪
        self.best_value = float('inf') if mode == "min" else float('-inf')
        self.best_epoch = 0
        
        # 历史记录
        self.history: List[Dict[str, Any]] = []
    
    def step(
        self,
        model: torch.nn.Module,
        epoch: int,
        metrics: Dict[str, float],
        optimizer: Optional[torch.optim.Optimizer] = None,
        scheduler: Optional[Any] = None
    ) -> bool:
        """
        检查并保存模型
        
        Args:
            model: 模型
            epoch: 当前epoch
            metrics: 指标字典
            optimizer: 优化器（可选）
            scheduler: 学习率调度器（可选）
            
        Returns:
            是否保存了模型
        """
        current_value = metrics.get(self.monitor)
        if current_value is None:
            logger.warning(f"指标 {self.monitor} 不在metrics中")
            return False
        
        # 记录历史
        self.history.append({
            "epoch": epoch,
            "value": current_value,
            "metrics": metrics.copy()
        })
        
        # 判断是否是最佳
        is_best = False
        if self.mode == "min":
            is_best = current_value < self.best_value
        else:
            is_best = current_value > self.best_value
        
        if is_best:
            self.best_value = current_value
            self.best_epoch = epoch
            
            if self.save_best_only:
                self._save_checkpoint(
                    model, epoch, metrics, optimizer, scheduler
                )
                if self.verbose > 0:
                    logger.info(
                        f"Epoch {epoch}: {self.monitor} improved to {current_value:.4f}, "
                        f"saving model to {self.filepath}"
                    )
                return True
        
        if not self.save_best_only:
            # 保存每个epoch的模型
            filepath = self.filepath.parent / f"model_epoch_{epoch}.pt"
            self._save_checkpoint(
                model, epoch, metrics, optimizer, scheduler, filepath
            )
            return True
        
        if self.verbose > 1:
            logger.info(
                f"Epoch {epoch}: {self.monitor} = {current_value:.4f}, "
                f"best = {self.best_value:.4f} (epoch {self.best_epoch})"
            )
        
        return False
    
    def _save_checkpoint(
        self,
        model: torch.nn.Module,
        epoch: int,
        metrics: Dict[str, float],
        optimizer: Optional[torch.optim.Optimizer] = None,
        scheduler: Optional[Any] = None,
        filepath: Optional[Path] = None
    ):
        """保存检查点"""
        filepath = filepath or self.filepath
        
        checkpoint = {
            "epoch": epoch,
            "metrics": metrics,
            "monitor": self.monitor,
            "best_value": self.best_value,
            "timestamp": datetime.now().isoformat()
        }
        
        if self.save_weights_only:
            checkpoint["state_dict"] = model.state_dict()
        else:
            checkpoint["model"] = model
        
        if optimizer is not None:
            checkpoint["optimizer_state_dict"] = optimizer.state_dict()
        
        if scheduler is not None:
            checkpoint["scheduler_state_dict"] = scheduler.state_dict()
        
        torch.save(checkpoint, filepath)
    
    def load_best_checkpoint(
        self,
        model: torch.nn.Module,
        optimizer: Optional[torch.optim.Optimizer] = None,
        scheduler: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        加载最佳检查点
        
        Args:
            model: 模型
            optimizer: 优化器（可选）
            scheduler: 学习率调度器（可选）
            
        Returns:
            检查点信息
        """
        if not self.filepath.exists():
            logger.warning(f"检查点文件不存在: {self.filepath}")
            return {}
        
        checkpoint = torch.load(self.filepath, map_location='cpu')
        
        if "state_dict" in checkpoint:
            model.load_state_dict(checkpoint["state_dict"])
        elif "model" in checkpoint:
            model.load_state_dict(checkpoint["model"].state_dict())
        
        if optimizer is not None and "optimizer_state_dict" in checkpoint:
            optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        
        if scheduler is not None and "scheduler_state_dict" in checkpoint:
            scheduler.load_state_dict(checkpoint["scheduler_state_dict"])
        
        logger.info(
            f"加载最佳模型 (epoch {checkpoint.get('epoch', 'unknown')}, "
            f"{self.monitor}={checkpoint.get('best_value', 'unknown'):.4f})"
        )
        
        return checkpoint
    
    def get_history(self) -> List[Dict[str, Any]]:
        """获取保存历史"""
        return self.history.copy()


class EarlyStopping:
    """
    早停
    
    当验证指标不再改善时提前停止训练
    """
    
    def __init__(
        self,
        monitor: str = "val_loss",
        mode: str = "min",
        patience: int = 10,
        min_delta: float = 0.0,
        restore_best_weights: bool = True,
        verbose: int = 1
    ):
        """
        初始化
        
        Args:
            monitor: 监控指标
            mode: 优化模式 ("min" 或 "max")
            patience: 容忍epoch数
            min_delta: 最小改善量
            restore_best_weights: 恢复最佳权重
            verbose: 日志详细程度
        """
        self.monitor = monitor
        self.mode = mode
        self.patience = patience
        self.min_delta = min_delta
        self.restore_best_weights = restore_best_weights
        self.verbose = verbose
        
        # 内部状态
        self.best_value = float('inf') if mode == "min" else float('-inf')
        self.best_epoch = 0
        self.wait = 0
        self.stopped_epoch = 0
        self.should_stop = False
        self.best_weights = None
    
    def step(
        self,
        epoch: int,
        metrics: Dict[str, float],
        model: Optional[torch.nn.Module] = None
    ) -> bool:
        """
        检查是否需要早停
        
        Args:
            epoch: 当前epoch
            metrics: 指标字典
            model: 模型（用于恢复权重）
            
        Returns:
            是否应该停止训练
        """
        current_value = metrics.get(self.monitor)
        if current_value is None:
            logger.warning(f"指标 {self.monitor} 不在metrics中")
            return False
        
        # 判断是否有改善
        if self.mode == "min":
            improved = current_value < (self.best_value - self.min_delta)
        else:
            improved = current_value > (self.best_value + self.min_delta)
        
        if improved:
            self.best_value = current_value
            self.best_epoch = epoch
            self.wait = 0
            
            # 保存最佳权重
            if self.restore_best_weights and model is not None:
                self.best_weights = {
                    name: param.clone().detach()
                    for name, param in model.state_dict().items()
                }
            
            if self.verbose > 1:
                logger.info(
                    f"Epoch {epoch}: {self.monitor} improved to {current_value:.4f}"
                )
        else:
            self.wait += 1
            
            if self.wait >= self.patience:
                self.should_stop = True
                self.stopped_epoch = epoch
                
                if self.verbose > 0:
                    logger.info(
                        f"Epoch {epoch}: Early stopping triggered. "
                        f"Best {self.monitor}: {self.best_value:.4f} at epoch {self.best_epoch}"
                    )
                
                # 恢复最佳权重
                if self.restore_best_weights and self.best_weights is not None and model is not None:
                    model.load_state_dict(self.best_weights)
                    if self.verbose > 0:
                        logger.info("Restored model weights from best epoch")
        
        return self.should_stop
    
    def reset(self):
        """重置状态"""
        self.best_value = float('inf') if self.mode == "min" else float('-inf')
        self.best_epoch = 0
        self.wait = 0
        self.stopped_epoch = 0
        self.should_stop = False
        self.best_weights = None


class LRScheduler:
    """
    学习率调度器包装
    
    支持多种调度策略
    """
    
    def __init__(
        self,
        optimizer: torch.optim.Optimizer,
        mode: str = "reduce_on_plateau",
        **kwargs
    ):
        """
        初始化
        
        Args:
            optimizer: 优化器
            mode: 调度模式
            **kwargs: 调度器参数
        """
        self.optimizer = optimizer
        self.mode = mode
        
        if mode == "reduce_on_plateau":
            self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
                optimizer,
                mode=kwargs.get('scheduler_mode', 'min'),
                factor=kwargs.get('factor', 0.5),
                patience=kwargs.get('patience', 5),
                verbose=kwargs.get('verbose', True),
                min_lr=kwargs.get('min_lr', 1e-7)
            )
        elif mode == "cosine":
            self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
                optimizer,
                T_max=kwargs.get('T_max', 100),
                eta_min=kwargs.get('eta_min', 0)
            )
        elif mode == "cosine_warm_restarts":
            self.scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
                optimizer,
                T_0=kwargs.get('T_0', 10),
                T_mult=kwargs.get('T_mult', 2),
                eta_min=kwargs.get('eta_min', 0)
            )
        elif mode == "step":
            self.scheduler = torch.optim.lr_scheduler.StepLR(
                optimizer,
                step_size=kwargs.get('step_size', 30),
                gamma=kwargs.get('gamma', 0.1)
            )
        elif mode == "exponential":
            self.scheduler = torch.optim.lr_scheduler.ExponentialLR(
                optimizer,
                gamma=kwargs.get('gamma', 0.95)
            )
        elif mode == "one_cycle":
            # 需要知道总epoch数，这里只是占位
            self.scheduler = None
            self.scheduler_config = kwargs
        else:
            raise ValueError(f"未知的调度模式: {mode}")
    
    def step(self, metric: Optional[float] = None):
        """
        执行调度步骤
        
        Args:
            metric: 监控指标（用于ReduceLROnPlateau）
        """
        if self.scheduler is None:
            return
        
        if self.mode == "reduce_on_plateau":
            if metric is not None:
                self.scheduler.step(metric)
        else:
            self.scheduler.step()
    
    def get_last_lr(self) -> List[float]:
        """获取当前学习率"""
        return [group['lr'] for group in self.optimizer.param_groups]
    
    def state_dict(self) -> Dict[str, Any]:
        """获取状态字典"""
        if self.scheduler:
            return self.scheduler.state_dict()
        return {}
    
    def load_state_dict(self, state_dict: Dict[str, Any]):
        """加载状态字典"""
        if self.scheduler:
            self.scheduler.load_state_dict(state_dict)


class TrainingLogger:
    """
    训练日志记录器
    
    记录训练过程中的指标和进度
    """
    
    def __init__(
        self,
        log_dir: str = "logs",
        experiment_name: Optional[str] = None
    ):
        """
        初始化
        
        Args:
            log_dir: 日志目录
            experiment_name: 实验名称
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        if experiment_name is None:
            experiment_name = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.experiment_name = experiment_name
        self.log_file = self.log_dir / f"{experiment_name}.jsonl"
        
        # 训练历史
        self.history: List[Dict[str, Any]] = []
    
    def log_epoch(
        self,
        epoch: int,
        train_metrics: Dict[str, float],
        val_metrics: Optional[Dict[str, float]] = None,
        lr: Optional[float] = None
    ):
        """
        记录一个epoch
        
        Args:
            epoch: epoch数
            train_metrics: 训练指标
            val_metrics: 验证指标
            lr: 学习率
        """
        record = {
            "epoch": epoch,
            "timestamp": datetime.now().isoformat(),
            "train": train_metrics
        }
        
        if val_metrics:
            record["val"] = val_metrics
        
        if lr:
            record["lr"] = lr
        
        self.history.append(record)
        
        # 写入文件
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    def get_history(self) -> List[Dict[str, Any]]:
        """获取训练历史"""
        return self.history.copy()
    
    def get_best_epoch(
        self,
        metric: str = "val_loss",
        mode: str = "min"
    ) -> Optional[Dict[str, Any]]:
        """
        获取最佳epoch
        
        Args:
            metric: 指标名称
            mode: 优化模式
            
        Returns:
            最佳epoch记录
        """
        if not self.history:
            return None
        
        # 找出包含该指标的epoch
        valid_epochs = [
            h for h in self.history
            if metric in h.get("val", {}) or metric in h.get("train", {})
        ]
        
        if not valid_epochs:
            return None
        
        # 获取指标值
        def get_metric(h):
            if metric in h.get("val", {}):
                return h["val"][metric]
            return h["train"][metric]
        
        if mode == "min":
            return min(valid_epochs, key=get_metric)
        else:
            return max(valid_epochs, key=get_metric)


class CallbackList:
    """
    回调列表
    
    管理多个回调函数
    """
    
    def __init__(self, callbacks: Optional[List] = None):
        """
        初始化
        
        Args:
            callbacks: 回调列表
        """
        self.callbacks = callbacks or []
    
    def append(self, callback):
        """添加回调"""
        self.callbacks.append(callback)
    
    def on_epoch_end(
        self,
        epoch: int,
        model: torch.nn.Module,
        metrics: Dict[str, float],
        optimizer: Optional[torch.optim.Optimizer] = None
    ):
        """
        Epoch结束回调
        
        Returns:
            是否应该停止训练
        """
        should_stop = False
        
        for callback in self.callbacks:
            if isinstance(callback, ModelCheckpoint):
                callback.step(model, epoch, metrics, optimizer)
            elif isinstance(callback, EarlyStopping):
                if callback.step(epoch, metrics, model):
                    should_stop = True
            elif isinstance(callback, LRScheduler):
                # LRScheduler需要特殊处理
                pass
            elif isinstance(callback, TrainingLogger):
                # TrainingLogger需要特殊处理
                pass
        
        return should_stop
    
    def on_train_end(self):
        """训练结束回调"""
        for callback in self.callbacks:
            if hasattr(callback, 'on_train_end'):
                callback.on_train_end()


# 便捷函数
__all__ = [
    'ModelCheckpoint',
    'EarlyStopping',
    'LRScheduler',
    'TrainingLogger',
    'CallbackList'
]
