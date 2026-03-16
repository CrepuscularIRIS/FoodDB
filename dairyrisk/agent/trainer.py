#!/usr/bin/env python3
"""
乳制品供应链风险预测模型训练器 V2
- 回归任务：预测 0-1 连续风险概率
- 输出：概率值、风险等级、置信度
"""

import pandas as pd
import numpy as np
import json
import pickle
from pathlib import Path
from typing import Dict, List, Tuple
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    mean_squared_error, mean_absolute_error, r2_score,
    precision_score, recall_score, f1_score, accuracy_score,
    confusion_matrix, classification_report
)
import warnings
warnings.filterwarnings('ignore')

# ============ 配置 ============
DATA_DIR = Path(__file__).parent.parent / "data" / "v2_scale"
OUTPUT_DIR = Path(__file__).parent.parent / "model"
MODEL_FILE = OUTPUT_DIR / "risk_model.pkl"
SCALER_FILE = OUTPUT_DIR / "scaler.pkl"
ENCODERS_FILE = OUTPUT_DIR / "encoders.pkl"
METRICS_FILE = OUTPUT_DIR / "metrics.json"

# 业务阈值
RISK_THRESHOLDS = {
    "low": 0.3,
    "medium": 0.7
}

# ============ 数据加载 ============

def load_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """加载数据"""
    print("加载数据...")
    
    # 加载企业数据
    enterprises = pd.read_csv(DATA_DIR / "enterprises.csv")
    print(f"  企业数据: {len(enterprises)} 条")
    
    # 加载边数据
    edges = pd.read_csv(DATA_DIR / "supply_edges.csv")
    print(f"  供应链边: {len(edges)} 条")
    
    return enterprises, edges

def engineer_features(enterprises: pd.DataFrame, edges: pd.DataFrame) -> pd.DataFrame:
    """特征工程"""
    print("\n特征工程...")
    
    df = enterprises.copy()
    
    # 1. 基本特征编码
    # 节点类型编码
    node_type_map = {"牧场": 0, "乳企": 1, "物流": 2, "仓储": 3, "零售": 4, "质检": 5, "饲料": 6}
    df["node_type_encoded"] = df["node_type"].map(node_type_map)
    
    # 企业规模编码
    scale_map = {"large": 0, "medium": 1, "small": 2, "micro": 3}
    df["scale_encoded"] = df["enterprise_type"].map(scale_map)
    
    # 信用评级编码
    credit_map = {"A": 0, "B": 1, "C": 2, "D": 3}
    df["credit_encoded"] = df["credit_rating"].map(credit_map)
    
    # 2. 布尔特征转换
    df["haccp_encoded"] = df["haccp_certified"].map({True: 1, False: 0, "True": 1, "False": 0})
    df["iso_encoded"] = df["iso22000_certified"].map({True: 1, False: 0, "True": 1, "False": 0})
    
    # 3. 数值特征处理
    df["historical_violation_count"] = pd.to_numeric(df["historical_violation_count"], errors='coerce').fillna(0)
    df["inspection_count"] = pd.to_numeric(df["inspection_count"], errors='coerce').fillna(0)
    df["supervision_freq"] = pd.to_numeric(df["supervision_freq"], errors='coerce').fillna(4)
    df["latitude"] = pd.to_numeric(df["latitude"], errors='coerce').fillna(31.0)
    df["longitude"] = pd.to_numeric(df["longitude"], errors='coerce').fillna(121.0)
    
    # 4. 衍生特征
    # 企业年龄
    df["establishment_date"] = pd.to_datetime(df["establishment_date"], errors='coerce')
    df["enterprise_age"] = 2024 - df["establishment_date"].dt.year.fillna(2015)
    
    # 违规率
    df["violation_rate"] = df["historical_violation_count"] / (df["inspection_count"] + 1)
    
    # 违规密度 (违规次数/企业年龄)
    df["violation_density"] = df["historical_violation_count"] / (df["enterprise_age"] + 1)
    
    # 检查强度 (检查次数/企业年龄)
    df["inspection_density"] = df["inspection_count"] / (df["enterprise_age"] + 1)
    
    # 认证得分 (有认证为0，无认证扣分)
    df["cert_score"] = df["haccp_encoded"] + df["iso_encoded"]
    
    # 5. 图特征：计算每个节点的度中心性
    print("  计算图特征...")
    
    # 入度 (有多少企业供应给它)
    in_degree = edges.groupby("target_id").size().reset_index(name="in_degree")
    df = df.merge(in_degree, left_on="enterprise_id", right_on="target_id", how="left")
    df["in_degree"] = df["in_degree"].fillna(0)
    
    # 出度 (它供应给多少企业)
    out_degree = edges.groupby("source_id").size().reset_index(name="out_degree")
    df = df.merge(out_degree, left_on="enterprise_id", right_on="source_id", how="left")
    df["out_degree"] = df["out_degree"].fillna(0)
    
    # 总度
    df["total_degree"] = df["in_degree"] + df["out_degree"]
    
    # 度比率 (入度/总度)
    df["degree_ratio"] = df["in_degree"] / (df["total_degree"] + 1)
    
    # 6. 供应链位置特征
    # 是否是源头 (有出度无入度)
    df["is_source"] = ((df["in_degree"] == 0) & (df["out_degree"] > 0)).astype(int)
    # 是否有下游
    df["has_downstream"] = (df["out_degree"] > 0).astype(int)
    # 是否有上游
    df["has_upstream"] = (df["in_degree"] > 0).astype(int)
    # 是否是终端 (仅有入度)
    df["is_terminal"] = ((df["in_degree"] > 0) & (df["out_degree"] == 0)).astype(int)
    
    # 7. 冷链特征 (针对物流和仓储)
    cold_chain_edges = edges[edges["cold_chain_maintained"] == True]
    cold_chain_sources = set(cold_chain_edges["source_id"])
    cold_chain_targets = set(cold_chain_edges["target_id"])
    
    df["in_cold_chain"] = df["enterprise_id"].isin(cold_chain_targets).astype(int)
    df["out_cold_chain"] = df["enterprise_id"].isin(cold_chain_sources).astype(int)
    df["full_cold_chain"] = ((df["in_cold_chain"] == 1) & (df["out_cold_chain"] == 1)).astype(int)
    
    # 8. 边权重特征
    edge_weight_stats = edges.groupby("source_id")["weight"].agg(["mean", "sum", "count", "std"]).reset_index()
    edge_weight_stats.columns = ["enterprise_id", "avg_edge_weight", "total_edge_weight", "edge_count", "edge_weight_std"]
    edge_weight_stats["edge_weight_std"] = edge_weight_stats["edge_weight_std"].fillna(0)
    df = df.merge(edge_weight_stats, on="enterprise_id", how="left")
    df["avg_edge_weight"] = df["avg_edge_weight"].fillna(0)
    df["total_edge_weight"] = df["total_edge_weight"].fillna(0)
    df["edge_count"] = df["edge_count"].fillna(0)
    df["edge_weight_std"] = df["edge_weight_std"].fillna(0)
    
    # 9. 边类型多样性
    edge_type_diversity = edges.groupby("source_id")["edge_type"].nunique().reset_index()
    edge_type_diversity.columns = ["enterprise_id", "edge_type_diversity"]
    df = df.merge(edge_type_diversity, on="enterprise_id", how="left")
    df["edge_type_diversity"] = df["edge_type_diversity"].fillna(0)
    
    # 10. 交互特征
    df["scale_credit_interact"] = df["scale_encoded"] * df["credit_encoded"]
    df["violation_inspect_interact"] = df["historical_violation_count"] * df["inspection_count"]
    df["age_violation_interact"] = df["enterprise_age"] * df["historical_violation_count"]
    
    # 11. 地理特征
    # 计算与上海中心的距离
    shanghai_lat, shanghai_lon = 31.2304, 121.4737
    df["dist_to_shanghai"] = np.sqrt(
        (df["latitude"] - shanghai_lat)**2 + (df["longitude"] - shanghai_lon)**2
    )
    
    print(f"  特征工程完成，共 {len(df.columns)} 列")
    
    return df

def prepare_features(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """准备训练数据"""
    print("\n准备训练数据...")
    
    # 选择特征列 (排除与目标直接相关的特征)
    feature_cols = [
        "node_type_encoded",
        "scale_encoded", 
        "credit_encoded",
        "haccp_encoded",
        "iso_encoded",
        "historical_violation_count",
        "inspection_count",
        "enterprise_age",
        "violation_rate",
        "violation_density",
        "inspection_density",
        "cert_score",
        "in_degree",
        "out_degree",
        "total_degree",
        "degree_ratio",
        "is_source",
        "has_downstream",
        "has_upstream",
        "is_terminal",
        "in_cold_chain",
        "out_cold_chain",
        "full_cold_chain",
        "avg_edge_weight",
        "total_edge_weight",
        "edge_count",
        "edge_weight_std",
        "edge_type_diversity",
        "scale_credit_interact",
        "violation_inspect_interact",
        "age_violation_interact",
        "dist_to_shanghai",
    ]
    
    # 处理缺失值
    X = df[feature_cols].fillna(0).values
    
    # 目标变量：实际风险分数
    y = df["actual_risk_score"].values
    
    print(f"  特征矩阵: {X.shape}")
    print(f"  目标变量: {y.shape}, 范围: [{y.min():.3f}, {y.max():.3f}]")
    
    return X, y, feature_cols

def convert_to_class(y_prob: np.ndarray, thresholds: Dict = None) -> np.ndarray:
    """将概率转换为分类标签"""
    if thresholds is None:
        thresholds = RISK_THRESHOLDS
    
    y_class = np.zeros(len(y_prob), dtype=int)
    for i, prob in enumerate(y_prob):
        if prob >= thresholds["medium"]:
            y_class[i] = 2  # high
        elif prob >= thresholds["low"]:
            y_class[i] = 1  # medium
        else:
            y_class[i] = 0  # low
    return y_class

def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray, task: str = "regression") -> Dict:
    """计算评估指标"""
    metrics = {}
    
    if task == "regression":
        # 回归指标
        metrics["mse"] = mean_squared_error(y_true, y_pred)
        metrics["rmse"] = np.sqrt(metrics["mse"])
        metrics["mae"] = mean_absolute_error(y_true, y_pred)
        metrics["r2"] = r2_score(y_true, y_pred)
        
        # 转换为分类进行评估
        y_true_class = convert_to_class(y_true)
        y_pred_class = convert_to_class(y_pred)
        
        # 分类指标
        metrics["accuracy"] = accuracy_score(y_true_class, y_pred_class)
        metrics["precision"] = precision_score(y_true_class, y_pred_class, average='weighted', zero_division=0)
        metrics["recall"] = recall_score(y_true_class, y_pred_class, average='weighted', zero_division=0)
        metrics["f1"] = f1_score(y_true_class, y_pred_class, average='weighted', zero_division=0)
        
        # 每个类别的指标
        for i, level in enumerate(["low", "medium", "high"]):
            y_true_binary = (y_true_class == i).astype(int)
            y_pred_binary = (y_pred_class == i).astype(int)
            
            metrics[f"precision_{level}"] = precision_score(y_true_binary, y_pred_binary, zero_division=0)
            metrics[f"recall_{level}"] = recall_score(y_true_binary, y_pred_binary, zero_division=0)
            metrics[f"f1_{level}"] = f1_score(y_true_binary, y_pred_binary, zero_division=0)
    
    return metrics

def train_model(X: np.ndarray, y: np.ndarray) -> Tuple:
    """训练模型"""
    print("\n训练模型...")
    
    # 划分训练集和测试集
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    print(f"  训练集: {len(X_train)}, 测试集: {len(X_test)}")
    
    # 标准化
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # 训练多个模型并选择最佳
    models = {
        "RandomForest": RandomForestRegressor(
            n_estimators=200,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        ),
        "GradientBoosting": GradientBoostingRegressor(
            n_estimators=200,
            max_depth=8,
            learning_rate=0.1,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42
        ),
    }
    
    best_model = None
    best_score = -float('inf')
    best_name = None
    
    for name, model in models.items():
        print(f"\n  训练 {name}...")
        model.fit(X_train_scaled, y_train)
        
        # 预测
        y_pred = model.predict(X_test_scaled)
        
        # 计算指标
        metrics = calculate_metrics(y_test, y_pred, "regression")
        print(f"    RMSE: {metrics['rmse']:.4f}")
        print(f"    R2: {metrics['r2']:.4f}")
        print(f"    分类 F1: {metrics['f1']:.4f}")
        
        # 选择最佳模型 (基于R2)
        if metrics['r2'] > best_score:
            best_score = metrics['r2']
            best_model = model
            best_name = name
    
    print(f"\n  最佳模型: {best_name}")
    
    # 使用最佳模型进行最终评估
    y_pred_final = best_model.predict(X_test_scaled)
    final_metrics = calculate_metrics(y_test, y_pred_final, "regression")
    
    # 交叉验证
    print("\n  交叉验证...")
    X_scaled = scaler.fit_transform(X)
    cv_scores = cross_val_score(best_model, X_scaled, y, cv=5, scoring='r2')
    final_metrics["cv_r2_mean"] = cv_scores.mean()
    final_metrics["cv_r2_std"] = cv_scores.std()
    
    return best_model, scaler, final_metrics, X_test, y_test, y_pred_final

def analyze_feature_importance(model, feature_cols: List[str]) -> Dict:
    """分析特征重要性"""
    print("\n特征重要性分析...")
    
    if hasattr(model, 'feature_importances_'):
        importances = model.feature_importances_
        feature_imp = dict(zip(feature_cols, importances))
        
        # 排序
        sorted_imp = sorted(feature_imp.items(), key=lambda x: x[1], reverse=True)
        
        print("  Top 10 重要特征:")
        for feat, imp in sorted_imp[:10]:
            print(f"    {feat}: {imp:.4f}")
        
        return feature_imp
    
    return {}

def save_model(model, scaler, metrics: Dict, feature_importance: Dict):
    """保存模型"""
    print("\n保存模型...")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 保存模型
    with open(MODEL_FILE, 'wb') as f:
        pickle.dump(model, f)
    print(f"  模型保存至: {MODEL_FILE}")
    
    # 保存scaler
    with open(SCALER_FILE, 'wb') as f:
        pickle.dump(scaler, f)
    print(f"  Scaler保存至: {SCALER_FILE}")
    
    # 保存指标
    with open(METRICS_FILE, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"  指标保存至: {METRICS_FILE}")
    
    # 保存特征重要性
    if feature_importance:
        importance_file = OUTPUT_DIR / "feature_importance.json"
        with open(importance_file, 'w') as f:
            json.dump(feature_importance, f, indent=2)
        print(f"  特征重要性保存至: {importance_file}")

def print_summary(metrics: Dict):
    """打印摘要"""
    print("\n" + "=" * 60)
    print("模型评估结果摘要")
    print("=" * 60)
    
    print("\n【回归指标】")
    print(f"  RMSE (均方根误差): {metrics['rmse']:.4f}")
    print(f"  MAE (平均绝对误差): {metrics['mae']:.4f}")
    print(f"  R² (决定系数): {metrics['r2']:.4f}")
    
    print("\n【三分类指标】(阈值: low<0.3, 0.3<=medium<0.7, high>=0.7)")
    print(f"  准确率 (Accuracy): {metrics['accuracy']*100:.2f}%")
    print(f"  精确率 (Precision): {metrics['precision']*100:.2f}%")
    print(f"  召回率 (Recall): {metrics['recall']*100:.2f}%")
    print(f"  F1 Score: {metrics['f1']*100:.2f}%")
    
    print("\n【各类别召回率】(重点关注)")
    print(f"  低风险召回率: {metrics.get('recall_low', 0)*100:.2f}%")
    print(f"  中风险召回率: {metrics.get('recall_medium', 0)*100:.2f}%")
    print(f"  高风险召回率: {metrics.get('recall_high', 0)*100:.2f}%")
    
    print("\n【交叉验证】")
    print(f"  R² 均值: {metrics.get('cv_r2_mean', 0):.4f} ± {metrics.get('cv_r2_std', 0):.4f}")
    
    # 目标检查
    print("\n【目标达成情况】")
    recall = metrics['recall'] * 100
    f1 = metrics['f1'] * 100
    precision = metrics['precision'] * 100
    
    print(f"  Recall >= 95%: {'✓ 达成' if recall >= 95 else '✗ 未达成'} (当前: {recall:.2f}%)")
    print(f"  F1 >= 93%: {'✓ 达成' if f1 >= 93 else '✗ 未达成'} (当前: {f1:.2f}%)")
    print(f"  Precision >= 92%: {'✓ 达成' if precision >= 92 else '✗ 未达成'} (当前: {precision:.2f}%)")

def predict_risk(enterprise_data: Dict, model, scaler, feature_cols: List[str]) -> Dict:
    """预测单个企业风险"""
    # 构建特征向量
    features = []
    for col in feature_cols:
        features.append(enterprise_data.get(col, 0))
    
    # 标准化
    X = np.array(features).reshape(1, -1)
    X_scaled = scaler.transform(X)
    
    # 预测
    risk_prob = model.predict(X_scaled)[0]
    risk_prob = max(0.0, min(1.0, risk_prob))
    
    # 确定等级
    if risk_prob < 0.3:
        risk_level = "low"
    elif risk_prob < 0.7:
        risk_level = "medium"
    else:
        risk_level = "high"
    
    # 计算置信度 (基于预测值与阈值的距离)
    if risk_level == "low":
        confidence = 1 - risk_prob / 0.3
    elif risk_level == "medium":
        confidence = 1 - abs(risk_prob - 0.5) / 0.2
    else:
        confidence = (risk_prob - 0.7) / 0.3
    
    confidence = max(0.5, min(1.0, confidence))
    
    return {
        "risk_probability": round(risk_prob, 4),
        "risk_level": risk_level,
        "confidence": round(confidence, 4)
    }

# ============ 主函数 ============

def main():
    print("=" * 60)
    print("乳制品供应链风险预测模型训练器 V2")
    print("=" * 60)
    
    # 1. 加载数据
    enterprises, edges = load_data()
    
    # 2. 特征工程
    df = engineer_features(enterprises, edges)
    
    # 3. 准备训练数据
    X, y, feature_cols = prepare_features(df)
    
    # 4. 训练模型
    model, scaler, metrics, X_test, y_test, y_pred = train_model(X, y)
    
    # 5. 特征重要性分析
    feature_importance = analyze_feature_importance(model, feature_cols)
    
    # 6. 保存模型
    save_model(model, scaler, metrics, feature_importance)
    
    # 7. 打印摘要
    print_summary(metrics)
    
    # 8. 演示预测
    print("\n" + "=" * 60)
    print("演示预测")
    print("=" * 60)
    
    # 取几个测试样本
    sample_enterprises = df.head(5)
    for _, ent in sample_enterprises.iterrows():
        ent_data = {col: ent[col] for col in feature_cols}
        result = predict_risk(ent_data, model, scaler, feature_cols)
        
        print(f"\n{ent['enterprise_name']} ({ent['node_type']})")
        print(f"  实际风险: {ent['actual_risk_score']:.4f} ({ent['risk_level']})")
        print(f"  预测风险: {result['risk_probability']:.4f} ({result['risk_level']})")
        print(f"  置信度: {result['confidence']:.2%}")
    
    print("\n训练完成!")
    
    return metrics

if __name__ == "__main__":
    metrics = main()
