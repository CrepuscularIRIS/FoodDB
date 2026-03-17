"""
边级风险预测 (Edge-level Risk Prediction)

预测边是否会发生风险传导，使用逻辑回归和小神经网络模型。
输入：边特征 + 源节点风险
输出：传导概率
"""

import torch
import torch.nn as nn
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import numpy as np
import pickle
import os

from dairyrisk.graph.edges import EdgeType, Edge, EDGE_FEATURE_DIMS

# 尝试导入sklearn，如果失败则使用替代方案
try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    # 简单的替代实现
    class StandardScaler:
        def __init__(self):
            self.mean_ = None
            self.scale_ = None
        
        def fit(self, X):
            self.mean_ = np.mean(X, axis=0)
            self.scale_ = np.std(X, axis=0) + 1e-8
            return self
        
        def transform(self, X):
            return (X - self.mean_) / self.scale_
        
        def fit_transform(self, X):
            return self.fit(X).transform(X)


@dataclass
class EdgeFeatureVector:
    """边特征向量"""
    edge_type_encoded: int
    weight: float
    source_risk: float
    edge_features: List[float]
    
    def to_array(self) -> np.ndarray:
        """转换为numpy数组"""
        return np.array([
            self.edge_type_encoded,
            self.weight,
            self.source_risk,
            *self.edge_features
        ])
    
    @property
    def dim(self) -> int:
        return 3 + len(self.edge_features)


@dataclass
class EdgePredictionResult:
    """边风险预测结果"""
    edge_id: str
    source_node_id: str
    target_node_id: str
    edge_type: EdgeType
    transmission_probability: float      # 传导概率
    risk_level: str                      # 风险等级 (low/medium/high/critical)
    confidence: float                    # 置信度
    feature_importance: Dict[str, float] = None  # 特征重要性
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "edge_type": self.edge_type.name if isinstance(self.edge_type, EdgeType) else str(self.edge_type),
            "transmission_probability": round(self.transmission_probability, 4),
            "risk_level": self.risk_level,
            "confidence": round(self.confidence, 4),
            "feature_importance": self.feature_importance
        }


class EdgeRiskNN(nn.Module):
    """
    边风险预测神经网络
    
    小型MLP网络，用于预测边风险传导概率
    """
    
    def __init__(self, input_dim: int, hidden_dim: int = 64, dropout: float = 0.2):
        super().__init__()
        
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
            nn.Sigmoid()
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)


class EdgeRiskPredictor:
    """
    边级风险预测器
    
    支持两种模型：
    1. 逻辑回归 - 轻量级，可解释性强
    2. 小神经网络 - 精度更高，支持复杂模式
    """
    
    # 边类型编码映射
    EDGE_TYPE_ENCODING = {
        EdgeType.SUPPLIES: 0,
        EdgeType.USED_IN: 1,
        EdgeType.PRODUCES: 2,
        EdgeType.TRANSPORTED_BY: 3,
        EdgeType.TEMPORAL_NEXT: 4,
        EdgeType.PURCHASES: 5,
        EdgeType.OWNS: 6,
        EdgeType.MANUFACTURES: 7,
        EdgeType.DELIVERS_TO: 8,
        EdgeType.SOLD_AT: 9,
        EdgeType.COMPETES: 10,
        EdgeType.COOPERATES: 11,
    }
    
    # 风险等级阈值
    RISK_THRESHOLDS = {
        "low": 0.3,
        "medium": 0.5,
        "high": 0.7,
        "critical": 0.9
    }
    
    def __init__(
        self,
        model_type: str = "logistic_regression",
        feature_dim: int = 10,
        model_path: Optional[str] = None
    ):
        """
        初始化边风险预测器
        
        Args:
            model_type: 模型类型 (logistic_regression / neural_network)
            feature_dim: 特征维度
            model_path: 预训练模型路径
        """
        self.model_type = model_type
        self.feature_dim = feature_dim
        self.scaler = StandardScaler()
        self._is_fitted = False
        
        # 初始化模型
        if model_type == "logistic_regression":
            if SKLEARN_AVAILABLE:
                self.model = LogisticRegression(
                    max_iter=1000,
                    class_weight='balanced',
                    random_state=42
                )
            else:
                # 如果没有sklearn，回退到神经网络
                print("Warning: sklearn not available, falling back to neural network")
                self.model_type = "neural_network"
                self.model = EdgeRiskNN(input_dim=feature_dim)
                self.optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)
                self.criterion = nn.BCELoss()
        elif model_type == "neural_network":
            self.model = EdgeRiskNN(input_dim=feature_dim)
            self.optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)
            self.criterion = nn.BCELoss()
        else:
            raise ValueError(f"不支持的模型类型: {model_type}")
        
        # 加载预训练模型
        if model_path and os.path.exists(model_path):
            self.load_model(model_path)
    
    def _encode_edge_type(self, edge_type: EdgeType) -> int:
        """编码边类型"""
        return self.EDGE_TYPE_ENCODING.get(edge_type, 0)
    
    def _extract_edge_features(
        self,
        edge: Edge,
        source_risk: float
    ) -> EdgeFeatureVector:
        """
        提取边特征
        
        Args:
            edge: 边对象
            source_risk: 源节点风险
            
        Returns:
            边特征向量
        """
        edge_type_encoded = self._encode_edge_type(edge.edge_type)
        
        # 获取边特征
        if edge.features:
            edge_features = [
                float(edge.features.get(k, 0.0))
                for k in sorted(edge.features.keys())
            ]
        else:
            # 默认特征
            edge_features = [edge.weight, 0.5, 0.5]
        
        # 填充或截断到固定维度
        target_dim = self.feature_dim - 3
        if len(edge_features) < target_dim:
            edge_features.extend([0.0] * (target_dim - len(edge_features)))
        else:
            edge_features = edge_features[:target_dim]
        
        return EdgeFeatureVector(
            edge_type_encoded=edge_type_encoded,
            weight=edge.weight,
            source_risk=source_risk,
            edge_features=edge_features
        )
    
    def _get_risk_level(self, probability: float) -> str:
        """根据概率确定风险等级"""
        if probability >= self.RISK_THRESHOLDS["critical"]:
            return "critical"
        elif probability >= self.RISK_THRESHOLDS["high"]:
            return "high"
        elif probability >= self.RISK_THRESHOLDS["medium"]:
            return "medium"
        elif probability >= self.RISK_THRESHOLDS["low"]:
            return "low"
        else:
            return "minimal"
    
    def predict(
        self,
        edge: Edge,
        source_risk: float
    ) -> EdgePredictionResult:
        """
        预测单条边的风险传导
        
        Args:
            edge: 边对象
            source_risk: 源节点风险值
            
        Returns:
            预测结果
        """
        # 提取特征
        feature_vector = self._extract_edge_features(edge, source_risk)
        X = feature_vector.to_array().reshape(1, -1)
        
        # 标准化
        if self._is_fitted and hasattr(self.scaler, 'mean_'):
            X = self.scaler.transform(X)
        
        # 预测
        if self.model_type == "logistic_regression":
            probability = self.model.predict_proba(X)[0][1]
            confidence = max(self.model.predict_proba(X)[0])
        else:  # neural_network
            with torch.no_grad():
                X_tensor = torch.FloatTensor(X)
                probability = self.model(X_tensor).item()
                confidence = probability if probability > 0.5 else 1 - probability
        
        # 特征重要性（仅逻辑回归支持）
        feature_importance = None
        if self.model_type == "logistic_regression" and hasattr(self.model, 'coef_'):
            feature_names = ['edge_type', 'weight', 'source_risk'] + [f'feature_{i}' for i in range(len(feature_vector.edge_features))]
            feature_importance = {
                name: float(importance)
                for name, importance in zip(feature_names, self.model.coef_[0])
            }
        
        edge_id = f"{edge.src_id}_{edge.edge_type.name}_{edge.dst_id}"
        
        return EdgePredictionResult(
            edge_id=edge_id,
            source_node_id=edge.src_id,
            target_node_id=edge.dst_id,
            edge_type=edge.edge_type,
            transmission_probability=probability,
            risk_level=self._get_risk_level(probability),
            confidence=confidence,
            feature_importance=feature_importance
        )
    
    def predict_batch(
        self,
        edges: List[Edge],
        source_risks: Dict[str, float]
    ) -> List[EdgePredictionResult]:
        """
        批量预测边风险
        
        Args:
            edges: 边列表
            source_risks: 源节点风险映射
            
        Returns:
            预测结果列表
        """
        results = []
        for edge in edges:
            source_risk = source_risks.get(edge.src_id, 0.5)
            result = self.predict(edge, source_risk)
            results.append(result)
        return results
    
    def train(
        self,
        edges: List[Edge],
        source_risks: List[float],
        labels: List[int],  # 0: 无传导, 1: 有传导
        epochs: int = 100,
        validation_split: float = 0.2
    ) -> Dict[str, float]:
        """
        训练模型
        
        Args:
            edges: 边列表
            source_risks: 源节点风险列表
            labels: 标签列表
            epochs: 训练轮数（仅神经网络）
            validation_split: 验证集比例
            
        Returns:
            训练指标
        """
        # 准备数据
        X_list = []
        for edge, risk in zip(edges, source_risks):
            feature_vector = self._extract_edge_features(edge, risk)
            X_list.append(feature_vector.to_array())
        
        X = np.array(X_list)
        y = np.array(labels)
        
        # 分割训练集和验证集
        n_samples = len(X)
        n_val = int(n_samples * validation_split)
        indices = np.random.permutation(n_samples)
        
        train_idx = indices[n_val:]
        val_idx = indices[:n_val]
        
        X_train, X_val = X[train_idx], X[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]
        
        # 标准化
        X_train = self.scaler.fit_transform(X_train)
        X_val = self.scaler.transform(X_val)
        self._is_fitted = True
        
        if self.model_type == "logistic_regression" and SKLEARN_AVAILABLE:
            self.model.fit(X_train, y_train)
            train_acc = self.model.score(X_train, y_train)
            val_acc = self.model.score(X_val, y_val)
            
            return {
                "train_accuracy": train_acc,
                "val_accuracy": val_acc,
                "train_samples": len(X_train),
                "val_samples": len(X_val)
            }
        
        else:  # neural_network or sklearn not available
            X_train_tensor = torch.FloatTensor(X_train)
            y_train_tensor = torch.FloatTensor(y_train).unsqueeze(1)
            X_val_tensor = torch.FloatTensor(X_val)
            y_val_tensor = torch.FloatTensor(y_val).unsqueeze(1)
            
            best_val_loss = float('inf')
            metrics = {"train_losses": [], "val_losses": []}
            
            for epoch in range(epochs):
                # 训练
                self.model.train()
                self.optimizer.zero_grad()
                outputs = self.model(X_train_tensor)
                loss = self.criterion(outputs, y_train_tensor)
                loss.backward()
                self.optimizer.step()
                
                # 验证
                self.model.eval()
                with torch.no_grad():
                    val_outputs = self.model(X_val_tensor)
                    val_loss = self.criterion(val_outputs, y_val_tensor)
                
                metrics["train_losses"].append(loss.item())
                metrics["val_losses"].append(val_loss.item())
                
                if val_loss.item() < best_val_loss:
                    best_val_loss = val_loss.item()
            
            # 计算准确率
            self.model.eval()
            with torch.no_grad():
                train_pred = (self.model(X_train_tensor) > 0.5).float()
                train_acc = (train_pred == y_train_tensor).float().mean().item()
                
                val_pred = (self.model(X_val_tensor) > 0.5).float()
                val_acc = (val_pred == y_val_tensor).float().mean().item()
            
            return {
                "train_accuracy": train_acc,
                "val_accuracy": val_acc,
                "best_val_loss": best_val_loss,
                "final_train_loss": metrics["train_losses"][-1],
                "epochs": epochs
            }
    
    def evaluate(
        self,
        edges: List[Edge],
        source_risks: List[float],
        labels: List[int]
    ) -> Dict[str, float]:
        """
        评估模型
        
        Args:
            edges: 边列表
            source_risks: 源节点风险列表
            labels: 真实标签
            
        Returns:
            评估指标
        """
        # 准备数据
        X_list = []
        for edge, risk in zip(edges, source_risks):
            feature_vector = self._extract_edge_features(edge, risk)
            X_list.append(feature_vector.to_array())
        
        X = np.array(X_list)
        y = np.array(labels)
        
        if self._is_fitted:
            X = self.scaler.transform(X)
        
        if self.model_type == "logistic_regression" and SKLEARN_AVAILABLE:
            accuracy = self.model.score(X, y)
            y_pred = self.model.predict(X)
        else:
            X_tensor = torch.FloatTensor(X)
            y_tensor = torch.FloatTensor(y).unsqueeze(1)
            
            self.model.eval()
            with torch.no_grad():
                outputs = self.model(X_tensor)
                y_pred = (outputs > 0.5).float()
                accuracy = (y_pred == y_tensor).float().mean().item()
                y_pred = y_pred.numpy().flatten()
        
        # 计算其他指标
        if SKLEARN_AVAILABLE:
            from sklearn.metrics import precision_score, recall_score, f1_score
            precision = precision_score(y, y_pred, zero_division=0)
            recall = recall_score(y, y_pred, zero_division=0)
            f1 = f1_score(y, y_pred, zero_division=0)
        else:
            # 简单的指标计算
            tp = np.sum((y_pred == 1) & (y == 1))
            fp = np.sum((y_pred == 1) & (y == 0))
            fn = np.sum((y_pred == 0) & (y == 1))
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        return {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "samples": len(y)
        }
    
    def save_model(self, path: str):
        """保存模型"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        if self.model_type == "logistic_regression":
            with open(path, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'scaler': self.scaler,
                    'is_fitted': self._is_fitted
                }, f)
        else:
            torch.save({
                'model_state_dict': self.model.state_dict(),
                'scaler': self.scaler,
                'is_fitted': self._is_fitted
            }, path)
    
    def load_model(self, path: str):
        """加载模型"""
        if self.model_type == "logistic_regression":
            with open(path, 'rb') as f:
                data = pickle.load(f)
                self.model = data['model']
                self.scaler = data['scaler']
                self._is_fitted = data['is_fitted']
        else:
            checkpoint = torch.load(path, map_location='cpu')
            self.model.load_state_dict(checkpoint['model_state_dict'])
            self.scaler = checkpoint['scaler']
            self._is_fitted = checkpoint['is_fitted']


def create_edge_predictor(
    model_type: str = "logistic_regression",
    feature_dim: int = 10,
    model_path: Optional[str] = None
) -> EdgeRiskPredictor:
    """
    创建边级风险预测器
    
    Args:
        model_type: 模型类型
        feature_dim: 特征维度
        model_path: 预训练模型路径
        
    Returns:
        EdgeRiskPredictor实例
    """
    return EdgeRiskPredictor(
        model_type=model_type,
        feature_dim=feature_dim,
        model_path=model_path
    )


# 导出
__all__ = [
    'EdgeFeatureVector',
    'EdgePredictionResult',
    'EdgeRiskNN',
    'EdgeRiskPredictor',
    'create_edge_predictor'
]
