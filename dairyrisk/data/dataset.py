"""
PyTorch Dataset封装模块

提供:
- SupplyChainDataset: 供应链数据集
- HeteroGraphDataset: 异构图数据集
- DataLoader构建工具

作者: DairyRisk Team
日期: 2025-03
"""

import torch
from torch.utils.data import Dataset, DataLoader
from torch_geometric.data import HeteroData, Batch
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
import numpy as np
import logging

logger = logging.getLogger(__name__)


class SupplyChainDataset(Dataset):
    """
    供应链数据集
    
    用于加载和处理供应链风险预测数据
    """
    
    def __init__(
        self,
        data: List[Dict[str, Any]],
        feature_keys: List[str],
        label_key: str = 'risk_label',
        transform: Optional[Callable] = None
    ):
        """
        初始化数据集
        
        Args:
            data: 数据列表，每个元素是一个字典
            feature_keys: 特征字段名列表
            label_key: 标签字段名
            transform: 数据转换函数
        """
        self.data = data
        self.feature_keys = feature_keys
        self.label_key = label_key
        self.transform = transform
        
        # 验证数据
        if data:
            self._validate_data()
    
    def _validate_data(self):
        """验证数据格式"""
        sample = self.data[0]
        missing_keys = [k for k in self.feature_keys if k not in sample]
        if missing_keys:
            logger.warning(f"数据缺少特征字段: {missing_keys}")
        
        if self.label_key not in sample:
            logger.warning(f"数据缺少标签字段: {self.label_key}")
    
    def __len__(self) -> int:
        """返回数据集大小"""
        return len(self.data)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        获取单个样本
        
        Returns:
            (features, label) 元组
        """
        item = self.data[idx]
        
        # 提取特征
        features = []
        for key in self.feature_keys:
            value = item.get(key, 0.0)
            if value is None:
                value = 0.0
            features.append(float(value))
        
        # 提取标签
        label = item.get(self.label_key, 0.0)
        if label is None:
            label = 0.0
        
        features = torch.tensor(features, dtype=torch.float32)
        label = torch.tensor([label], dtype=torch.float32)
        
        # 应用变换
        if self.transform:
            features, label = self.transform(features, label)
        
        return features, label
    
    def get_feature_dim(self) -> int:
        """获取特征维度"""
        return len(self.feature_keys)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取数据集统计信息
        
        Returns:
            统计信息字典
        """
        if not self.data:
            return {}
        
        # 获取所有标签
        labels = [item.get(self.label_key, 0) for item in self.data]
        labels = [l if l is not None else 0 for l in labels]
        
        # 统计
        n_samples = len(self.data)
        n_positives = sum(1 for l in labels if l > 0.5)
        
        return {
            "n_samples": n_samples,
            "n_features": len(self.feature_keys),
            "n_positives": n_positives,
            "positive_rate": n_positives / n_samples if n_samples > 0 else 0,
            "label_mean": np.mean(labels),
            "label_std": np.std(labels)
        }


class HeteroGraphDataset(Dataset):
    """
    异构图数据集
    
    用于加载和处理异构图数据（支持PyTorch Geometric）
    """
    
    def __init__(
        self,
        graphs: List[HeteroData],
        target_node_type: str = 'batch',
        transform: Optional[Callable] = None
    ):
        """
        初始化
        
        Args:
            graphs: 异构图列表
            target_node_type: 目标节点类型
            transform: 数据转换函数
        """
        self.graphs = graphs
        self.target_node_type = target_node_type
        self.transform = transform
    
    def __len__(self) -> int:
        """返回数据集大小"""
        return len(self.graphs)
    
    def __getitem__(self, idx: int) -> HeteroData:
        """获取单个图"""
        graph = self.graphs[idx]
        
        if self.transform:
            graph = self.transform(graph)
        
        return graph
    
    def collate(self, batch: List[HeteroData]) -> Batch:
        """
        批处理函数
        
        Args:
            batch: 图列表
            
        Returns:
            批处理后的图
        """
        return Batch.from_data_list(batch)


class TemporalGraphDataset(Dataset):
    """
    时序图数据集
    
    用于加载和处理时序图数据
    """
    
    def __init__(
        self,
        snapshots: List[HeteroData],
        prediction_horizon: int = 1,
        history_length: int = 3,
        target_node_type: str = 'batch'
    ):
        """
        初始化
        
        Args:
            snapshots: 图快照列表
            prediction_horizon: 预测horizon（快照数）
            history_length: 历史序列长度
            target_node_type: 目标节点类型
        """
        self.snapshots = snapshots
        self.prediction_horizon = prediction_horizon
        self.history_length = history_length
        self.target_node_type = target_node_type
        
        # 确保有足够的历史数据
        self.valid_indices = self._get_valid_indices()
    
    def _get_valid_indices(self) -> List[int]:
        """获取有效的起始索引"""
        valid = []
        for i in range(len(self.snapshots) - self.prediction_horizon):
            if i >= self.history_length - 1:
                valid.append(i)
        return valid
    
    def __len__(self) -> int:
        """返回有效样本数"""
        return len(self.valid_indices)
    
    def __getitem__(self, idx: int) -> Tuple[List[HeteroData], HeteroData]:
        """
        获取单个样本
        
        Returns:
            (历史图列表, 目标图) 元组
        """
        actual_idx = self.valid_indices[idx]
        
        # 历史图
        start_idx = max(0, actual_idx - self.history_length + 1)
        history_graphs = self.snapshots[start_idx:actual_idx + 1]
        
        # 目标图
        target_graph = self.snapshots[actual_idx + self.prediction_horizon]
        
        return history_graphs, target_graph


class BalancedBatchSampler:
    """
    平衡批次采样器
    
    用于处理类别不平衡数据，确保每个批次包含正负样本
    """
    
    def __init__(
        self,
        labels: List[float],
        batch_size: int,
        positive_ratio: float = 0.3,
        shuffle: bool = True
    ):
        """
        初始化
        
        Args:
            labels: 标签列表
            batch_size: 批次大小
            positive_ratio: 正样本比例
            shuffle: 是否打乱
        """
        self.labels = np.array(labels)
        self.batch_size = batch_size
        self.positive_ratio = positive_ratio
        self.shuffle = shuffle
        
        # 分离正负样本索引
        self.positive_indices = np.where(self.labels > 0.5)[0].tolist()
        self.negative_indices = np.where(self.labels <= 0.5)[0].tolist()
        
        # 计算每批次的正负样本数
        self.n_positive_per_batch = int(batch_size * positive_ratio)
        self.n_negative_per_batch = batch_size - self.n_positive_per_batch
        
        # 计算批次数
        n_batches_pos = len(self.positive_indices) // max(1, self.n_positive_per_batch)
        n_batches_neg = len(self.negative_indices) // max(1, self.n_negative_per_batch)
        self.n_batches = max(1, min(n_batches_pos, n_batches_neg))
    
    def __iter__(self):
        """迭代器"""
        if self.shuffle:
            np.random.shuffle(self.positive_indices)
            np.random.shuffle(self.negative_indices)
        
        for i in range(self.n_batches):
            # 采样正样本
            pos_start = i * self.n_positive_per_batch
            pos_end = pos_start + self.n_positive_per_batch
            batch_pos = self.positive_indices[pos_start:pos_end]
            
            # 采样负样本
            neg_start = i * self.n_negative_per_batch
            neg_end = neg_start + self.n_negative_per_batch
            batch_neg = self.negative_indices[neg_start:neg_end]
            
            # 合并并打乱
            batch_indices = batch_pos + batch_neg
            if self.shuffle:
                np.random.shuffle(batch_indices)
            
            yield batch_indices
    
    def __len__(self) -> int:
        """返回批次数"""
        return self.n_batches


def create_dataloader(
    dataset: Dataset,
    batch_size: int = 32,
    shuffle: bool = True,
    num_workers: int = 0,
    pin_memory: bool = True,
    drop_last: bool = False,
    sampler: Optional[Any] = None
) -> DataLoader:
    """
    创建DataLoader
    
    Args:
        dataset: 数据集
        batch_size: 批次大小
        shuffle: 是否打乱
        num_workers: 工作进程数
        pin_memory: 是否锁页内存
        drop_last: 是否丢弃最后不完整的批次
        sampler: 采样器
        
    Returns:
        DataLoader实例
    """
    # 如果是异构图数据集，使用特殊的collate函数
    collate_fn = None
    if isinstance(dataset, HeteroGraphDataset):
        collate_fn = dataset.collate
    
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle if sampler is None else False,
        num_workers=num_workers,
        pin_memory=pin_memory,
        drop_last=drop_last,
        sampler=sampler,
        collate_fn=collate_fn
    )


def create_balanced_dataloader(
    dataset: SupplyChainDataset,
    batch_size: int = 32,
    positive_ratio: float = 0.3,
    num_workers: int = 0
) -> DataLoader:
    """
    创建平衡的DataLoader
    
    Args:
        dataset: 供应链数据集
        batch_size: 批次大小
        positive_ratio: 正样本比例
        num_workers: 工作进程数
        
    Returns:
        DataLoader实例
    """
    # 获取所有标签
    labels = []
    for i in range(len(dataset)):
        _, label = dataset[i]
        labels.append(label.item())
    
    # 创建平衡采样器
    sampler = BalancedBatchSampler(
        labels=labels,
        batch_size=batch_size,
        positive_ratio=positive_ratio,
        shuffle=True
    )
    
    return DataLoader(
        dataset,
        batch_sampler=sampler,
        num_workers=num_workers
    )


class DataAugmentation:
    """
    数据增强
    
    用于扩充训练数据
    """
    
    def __init__(
        self,
        noise_std: float = 0.01,
        drop_prob: float = 0.1,
        mixup_alpha: float = 0.2
    ):
        """
        初始化
        
        Args:
            noise_std: 噪声标准差
            drop_prob: 特征丢弃概率
            mixup_alpha: Mixup参数
        """
        self.noise_std = noise_std
        self.drop_prob = drop_prob
        self.mixup_alpha = mixup_alpha
    
    def add_noise(
        self,
        features: torch.Tensor,
        labels: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """添加高斯噪声"""
        noise = torch.randn_like(features) * self.noise_std
        return features + noise, labels
    
    def random_drop(
        self,
        features: torch.Tensor,
        labels: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """随机丢弃特征"""
        mask = torch.rand_like(features) > self.drop_prob
        return features * mask, labels
    
    def mixup(
        self,
        features: torch.Tensor,
        labels: torch.Tensor,
        features2: torch.Tensor,
        labels2: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Mixup数据增强"""
        lam = np.random.beta(self.mixup_alpha, self.mixup_alpha)
        mixed_features = lam * features + (1 - lam) * features2
        mixed_labels = lam * labels + (1 - lam) * labels2
        return mixed_features, mixed_labels


__all__ = [
    'SupplyChainDataset',
    'HeteroGraphDataset',
    'TemporalGraphDataset',
    'BalancedBatchSampler',
    'create_dataloader',
    'create_balanced_dataloader',
    'DataAugmentation'
]
