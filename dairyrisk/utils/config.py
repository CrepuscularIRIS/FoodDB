"""
配置加载工具

支持Hydra/OmegaConf风格的配置管理

作者: DairyRisk Team
日期: 2025-03
"""

import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, field, asdict
import os
import logging

logger = logging.getLogger(__name__)


class Config(dict):
    """
    配置类
    
    支持字典风格的点号访问
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 递归转换嵌套字典
        for key, value in self.items():
            if isinstance(value, dict):
                self[key] = Config(value)
    
    def __getattr__(self, key: str) -> Any:
        """支持点号访问"""
        try:
            return self[key]
        except KeyError:
            raise AttributeError(f"Config has no attribute '{key}'")
    
    def __setattr__(self, key: str, value: Any):
        """支持点号设置"""
        self[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值，支持嵌套键（如 "model.hidden_dim"）
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """
        设置配置值，支持嵌套键
        
        Args:
            key: 配置键
            value: 配置值
        """
        keys = key.split('.')
        config = self
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = Config()
            config = config[k]
        
        config[keys[-1]] = value
    
    def merge(self, other: Union[Dict, 'Config']):
        """
        合并配置
        
        Args:
            other: 另一个配置
        """
        for key, value in other.items():
            if key in self and isinstance(self[key], dict) and isinstance(value, dict):
                self[key].merge(value)
            else:
                self[key] = Config(value) if isinstance(value, dict) else value
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为普通字典"""
        result = {}
        for key, value in self.items():
            if isinstance(value, Config):
                result[key] = value.to_dict()
            else:
                result[key] = value
        return result
    
    def copy(self) -> 'Config':
        """深拷贝"""
        return Config(self.to_dict())


def load_yaml_config(path: Union[str, Path]) -> Config:
    """
    加载YAML配置文件
    
    Args:
        path: 配置文件路径
        
    Returns:
        Config对象
    """
    path = Path(path)
    
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    return Config(data)


def load_json_config(path: Union[str, Path]) -> Config:
    """
    加载JSON配置文件
    
    Args:
        path: 配置文件路径
        
    Returns:
        Config对象
    """
    path = Path(path)
    
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return Config(data)


def load_config(
    path: Union[str, Path],
    default_path: Optional[Union[str, Path]] = None
) -> Config:
    """
    加载配置文件（自动识别格式）
    
    Args:
        path: 主配置文件路径
        default_path: 默认配置文件路径（可选，会先加载默认值再覆盖）
        
    Returns:
        Config对象
    """
    # 加载默认配置
    config = Config()
    if default_path is not None:
        config = load_config(default_path)
    
    # 加载主配置
    path = Path(path)
    
    if path.suffix in ['.yaml', '.yml']:
        main_config = load_yaml_config(path)
    elif path.suffix == '.json':
        main_config = load_json_config(path)
    else:
        raise ValueError(f"不支持的配置文件格式: {path.suffix}")
    
    # 合并配置
    config.merge(main_config)
    
    return config


def save_config(
    config: Union[Config, Dict],
    path: Union[str, Path],
    format: str = 'yaml'
):
    """
    保存配置到文件
    
    Args:
        config: 配置对象
        path: 保存路径
        format: 格式 ('yaml' 或 'json')
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    if isinstance(config, Config):
        config = config.to_dict()
    
    if format == 'yaml':
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    elif format == 'json':
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    else:
        raise ValueError(f"不支持的格式: {format}")
    
    logger.info(f"配置已保存到: {path}")


def merge_configs(*configs: Union[Config, Dict]) -> Config:
    """
    合并多个配置
    
    Args:
        *configs: 配置对象列表
        
    Returns:
        合并后的Config对象
    """
    result = Config()
    
    for config in configs:
        result.merge(config)
    
    return result


def load_config_from_env(
    prefix: str = "DAIRYRISK_",
    base_config: Optional[Config] = None
) -> Config:
    """
    从环境变量加载配置
    
    环境变量名格式: DAIRYRISK_MODEL_HIDDEN_DIM=128
    会被解析为: config.model.hidden_dim = 128
    
    Args:
        prefix: 环境变量前缀
        base_config: 基础配置
        
    Returns:
        Config对象
    """
    config = base_config.copy() if base_config else Config()
    
    for key, value in os.environ.items():
        if key.startswith(prefix):
            # 移除前缀
            config_key = key[len(prefix):].lower().replace('_', '.')
            
            # 尝试解析值类型
            try:
                # 尝试整数
                parsed_value = int(value)
            except ValueError:
                try:
                    # 尝试浮点数
                    parsed_value = float(value)
                except ValueError:
                    # 布尔值
                    if value.lower() in ['true', 'false']:
                        parsed_value = value.lower() == 'true'
                    else:
                        # 列表
                        if ',' in value:
                            parsed_value = [v.strip() for v in value.split(',')]
                        else:
                            parsed_value = value
            
            config.set(config_key, parsed_value)
    
    return config


def create_default_config() -> Config:
    """
    创建默认配置
    
    Returns:
        默认Config对象
    """
    return Config({
        # 数据配置
        "data": {
            "raw_data_path": "data/raw",
            "processed_data_path": "data/processed",
            "batch_size": 32,
            "num_workers": 4,
            "train_ratio": 0.7,
            "val_ratio": 0.15,
            "test_ratio": 0.15,
            "positive_ratio": 0.3,  # 平衡采样时的正样本比例
        },
        
        # 图结构配置
        "graph": {
            "node_types": ["enterprise", "raw_material", "production_line", "batch", "logistics", "retail"],
            "edge_types": [
                "supplies", "purchases", "produces", "used_in",
                "transported_by", "delivers_to", "sold_at", "temporal_next"
            ],
            "temporal_window": 7,  # 时间窗口大小（天）
        },
        
        # 模型配置（占位，GNN模型本身不实现）
        "model": {
            "type": "MockGNN",  # 使用Mock模型
            "hidden_dim": 128,
            "num_layers": 2,
            "num_heads": 4,
            "dropout": 0.1,
            "target_node_type": "batch",
        },
        
        # 训练配置
        "training": {
            "num_epochs": 100,
            "learning_rate": 0.001,
            "weight_decay": 0.0001,
            "optimizer": "adamw",
            "scheduler": "cosine",
            "early_stopping_patience": 10,
            "gradient_clip": 1.0,
            "loss": {
                "type": "supply_chain_risk",
                "regression_weight": 1.0,
                "classification_weight": 0.5,
                "confidence_weight": 0.1,
                "pos_weight": 10.0,
            }
        },
        
        # 评估配置
        "evaluation": {
            "metrics": ["recall", "precision", "f1", "auc_roc", "auc_pr", "brier_score"],
            "threshold": 0.5,
            "top_k": [10, 50, 100],
            "risk_thresholds": [0.3, 0.7],
        },
        
        # 风险预测配置
        "risk_prediction": {
            "low_risk_threshold": 0.3,
            "high_risk_threshold": 0.7,
            "confidence_threshold": 0.6,
            "use_weak_supervision": True,
            "use_self_supervised": False,
            "use_generative": False,
        },
        
        # 输出配置
        "output": {
            "checkpoint_dir": "checkpoints",
            "log_dir": "logs",
            "result_dir": "results",
            "save_best_only": True,
        }
    })


# 便捷函数
__all__ = [
    'Config',
    'load_yaml_config',
    'load_json_config',
    'load_config',
    'save_config',
    'merge_configs',
    'load_config_from_env',
    'create_default_config'
]
