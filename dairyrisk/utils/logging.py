"""
日志工具模块

提供统一的日志配置和管理

作者: DairyRisk Team
日期: 2025-03
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import json


class ColoredFormatter(logging.Formatter):
    """
    彩色日志格式化器
    
    在终端中输出带颜色的日志
    """
    
    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',     # 青色
        'INFO': '\033[32m',      # 绿色
        'WARNING': '\033[33m',   # 黄色
        'ERROR': '\033[31m',     # 红色
        'CRITICAL': '\033[35m',  # 紫色
        'RESET': '\033[0m'       # 重置
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录"""
        # 保存原始levelname
        original_levelname = record.levelname
        
        # 添加颜色
        if record.levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[record.levelname]}"
                f"{original_levelname}"
                f"{self.COLORS['RESET']}"
            )
        
        # 格式化
        result = super().format(record)
        
        # 恢复原始levelname
        record.levelname = original_levelname
        
        return result


class JSONFormatter(logging.Formatter):
    """
    JSON格式日志格式化器
    
    将日志输出为JSON格式，便于机器解析
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化为JSON"""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # 添加额外字段
        if hasattr(record, 'extras'):
            log_data.update(record.extras)
        
        return json.dumps(log_data, ensure_ascii=False)


def setup_logger(
    name: str = "dairyrisk",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    log_dir: str = "logs",
    format_string: Optional[str] = None,
    use_color: bool = True,
    use_json: bool = False,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志器名称
        level: 日志级别
        log_file: 日志文件名（可选）
        log_dir: 日志目录
        format_string: 格式字符串
        use_color: 是否使用彩色输出
        use_json: 是否使用JSON格式
        max_bytes: 单个日志文件最大大小
        backup_count: 保留的备份文件数
        
    Returns:
        配置好的日志记录器
    """
    # 创建日志器
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 清除现有处理器
    logger.handlers.clear()
    
    # 默认格式
    if format_string is None:
        if use_json:
            format_string = "%(message)s"  # JSON格式器会处理所有字段
        else:
            format_string = (
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
            )
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    if use_json:
        console_formatter = JSONFormatter()
    elif use_color and sys.stdout.isatty():
        console_formatter = ColoredFormatter(format_string)
    else:
        console_formatter = logging.Formatter(format_string)
    
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器
    if log_file:
        log_path = Path(log_dir) / log_file
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        
        if use_json:
            file_formatter = JSONFormatter()
        else:
            file_formatter = logging.Formatter(format_string)
        
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def setup_experiment_logger(
    experiment_name: str,
    log_dir: str = "logs",
    **kwargs
) -> logging.Logger:
    """
    设置实验日志记录器
    
    Args:
        experiment_name: 实验名称
        log_dir: 日志目录
        **kwargs: 其他参数传递给setup_logger
        
    Returns:
        配置好的日志记录器
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"{experiment_name}_{timestamp}.log"
    
    return setup_logger(
        name=experiment_name,
        log_file=log_file,
        log_dir=log_dir,
        **kwargs
    )


def get_logger(name: str = "dairyrisk") -> logging.Logger:
    """
    获取日志记录器
    
    如果记录器未配置，会进行默认配置
    
    Args:
        name: 日志器名称
        
    Returns:
        日志记录器
    """
    logger = logging.getLogger(name)
    
    # 如果没有处理器，进行默认配置
    if not logger.handlers:
        setup_logger(name)
    
    return logger


class LogContext:
    """
    日志上下文管理器
    
    用于添加临时日志字段
    
    示例:
        with LogContext(logger, request_id="123"):
            logger.info("处理请求")
    """
    
    def __init__(self, logger: logging.Logger, **extras):
        """
        初始化
        
        Args:
            logger: 日志记录器
            **extras: 额外字段
        """
        self.logger = logger
        self.extras = extras
        self.original_filters = []
    
    def __enter__(self):
        """进入上下文"""
        # 创建过滤器添加额外字段
        class ExtraFilter(logging.Filter):
            def filter(self, record):
                for key, value in self.extras.items():
                    setattr(record, key, value)
                return True
        
        self.filter = ExtraFilter()
        self.logger.addFilter(self.filter)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文"""
        self.logger.removeFilter(self.filter)


class MetricsLogger:
    """
    指标日志记录器
    
    用于记录训练过程中的指标
    """
    
    def __init__(
        self,
        log_file: str,
        log_dir: str = "logs"
    ):
        """
        初始化
        
        Args:
            log_file: 日志文件名
            log_dir: 日志目录
        """
        self.log_path = Path(log_dir) / log_file
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def log_metrics(
        self,
        epoch: int,
        metrics: Dict[str, float],
        phase: str = "train"
    ):
        """
        记录指标
        
        Args:
            epoch: epoch数
            metrics: 指标字典
            phase: 阶段（train/val/test）
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            "epoch": epoch,
            "phase": phase,
            "metrics": metrics
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    def log_hyperparameters(self, hparams: Dict[str, Any]):
        """
        记录超参数
        
        Args:
            hparams: 超参数字典
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            "type": "hyperparameters",
            "hparams": hparams
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    def read_metrics(self) -> list:
        """
        读取所有指标记录
        
        Returns:
            指标记录列表
        """
        if not self.log_path.exists():
            return []
        
        records = []
        with open(self.log_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        
        return records


def log_metrics_table(
    logger: logging.Logger,
    metrics: Dict[str, float],
    title: str = "Metrics",
    precision: int = 4
):
    """
    以表格形式记录指标
    
    Args:
        logger: 日志记录器
        metrics: 指标字典
        title: 标题
        precision: 小数精度
    """
    # 计算列宽
    max_key_len = max(len(str(k)) for k in metrics.keys())
    max_val_len = max(len(f"{v:.{precision}f}") for v in metrics.values())
    
    # 构建表格
    lines = [
        f"\n{'=' * (max_key_len + max_val_len + 7)}",
        f"  {title}",
        f"{'=' * (max_key_len + max_val_len + 7)}",
    ]
    
    for key, value in metrics.items():
        lines.append(f"  {key:<{max_key_len}} | {value:>{max_val_len}.{precision}f}")
    
    lines.append(f"{'=' * (max_key_len + max_val_len + 7)}\n")
    
    logger.info('\n'.join(lines))


# 便捷函数
__all__ = [
    'ColoredFormatter',
    'JSONFormatter',
    'setup_logger',
    'setup_experiment_logger',
    'get_logger',
    'LogContext',
    'MetricsLogger',
    'log_metrics_table'
]
