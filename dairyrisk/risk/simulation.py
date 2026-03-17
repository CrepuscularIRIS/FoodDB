"""
风险传播模拟引擎 (Risk Propagation Simulation Engine)

实现蒙特卡洛传播模拟、级联失效模型和时间步进模拟。
支持多轮次模拟和What-if假设分析。
"""

import numpy as np
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import random
from datetime import datetime, timedelta

from dairyrisk.graph.edges import EdgeType, Edge
from dairyrisk.graph.nodes import NodeType
from dairyrisk.risk.transmission import (
    RiskTransmissionModel,
    RiskTransmissionResult,
    NodeRiskState,
    RISK_TRANSMISSION_COEFFICIENTS
)


class SimulationMode(Enum):
    """模拟模式"""
    MONTE_CARLO = "monte_carlo"           # 蒙特卡洛模拟
    CASCADE_FAILURE = "cascade_failure"   # 级联失效模型
    TIME_STEP = "time_step"               # 时间步进模拟
    WHAT_IF = "what_if"                   # 假设分析


@dataclass
class SimulationConfig:
    """模拟配置"""
    mode: SimulationMode = SimulationMode.MONTE_CARLO
    num_rounds: int = 100                   # 模拟轮次
    max_steps: int = 10                     # 最大传播步数
    time_step_hours: int = 1                # 时间步长（小时）
    risk_threshold: float = 0.5             # 风险阈值
    failure_threshold: float = 0.8          # 失效阈值
    random_seed: Optional[int] = None       # 随机种子
    enable_decay: bool = True               # 启用风险衰减
    decay_factor: float = 0.9               # 衰减因子
    noise_std: float = 0.05                 # 噪声标准差


@dataclass
class SimulationStep:
    """模拟单步结果"""
    step: int                               # 步数
    timestamp: Optional[datetime]           # 时间戳
    affected_nodes: Dict[str, float]        # 受影响节点 {node_id: risk_level}
    new_failures: List[str]                 # 新失效节点
    transmission_events: List[RiskTransmissionResult] = field(default_factory=list)


@dataclass
class SimulationResult:
    """模拟结果"""
    simulation_id: str                      # 模拟ID
    config: SimulationConfig                # 配置
    source_node_id: str                     # 源节点
    initial_risk: float                     # 初始风险
    steps: List[SimulationStep]             # 各步结果
    final_affected_count: int = 0           # 最终受影响节点数
    final_failure_count: int = 0            # 最终失效节点数
    total_transmissions: int = 0            # 总传导事件数
    simulation_time_ms: float = 0.0         # 模拟耗时
    
    def __post_init__(self):
        if self.steps:
            last_step = self.steps[-1]
            self.final_affected_count = len(last_step.affected_nodes)
            self.final_failure_count = len(last_step.new_failures)
            self.total_transmissions = sum(
                len(step.transmission_events) for step in self.steps
            )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "source_node_id": self.source_node_id,
            "initial_risk": round(self.initial_risk, 4),
            "config": {
                "mode": self.config.mode.value,
                "num_rounds": self.config.num_rounds,
                "max_steps": self.config.max_steps
            },
            "results": {
                "final_affected_count": self.final_affected_count,
                "final_failure_count": self.final_failure_count,
                "total_transmissions": self.total_transmissions,
                "simulation_time_ms": round(self.simulation_time_ms, 2)
            },
            "steps": [
                {
                    "step": step.step,
                    "affected_count": len(step.affected_nodes),
                    "new_failures": len(step.new_failures),
                    "avg_risk": round(np.mean(list(step.affected_nodes.values())), 4) if step.affected_nodes else 0
                }
                for step in self.steps
            ]
        }


@dataclass
class MonteCarloResult:
    """蒙特卡洛模拟结果"""
    simulation_results: List[SimulationResult] = field(default_factory=list)
    mean_affected_nodes: float = 0.0
    std_affected_nodes: float = 0.0
    mean_failure_count: float = 0.0
    confidence_interval_95: Tuple[float, float] = (0.0, 0.0)
    probability_distribution: Dict[int, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mean_affected_nodes": round(self.mean_affected_nodes, 2),
            "std_affected_nodes": round(self.std_affected_nodes, 2),
            "mean_failure_count": round(self.mean_failure_count, 2),
            "confidence_interval_95": [
                round(self.confidence_interval_95[0], 2),
                round(self.confidence_interval_95[1], 2)
            ],
            "probability_distribution": {
                str(k): round(v, 4) for k, v in self.probability_distribution.items()
            },
            "simulation_count": len(self.simulation_results)
        }


class RiskPropagationSimulator:
    """
    风险传播模拟器
    
    支持多种模拟模式：
    1. 蒙特卡洛模拟 - 多轮次随机模拟，评估统计分布
    2. 级联失效模型 - 模拟节点失效的连锁反应
    3. 时间步进模拟 - 按时间传播风险
    4. What-if分析 - 假设场景模拟
    """
    
    def __init__(
        self,
        transmission_model: Optional[RiskTransmissionModel] = None,
        config: Optional[SimulationConfig] = None
    ):
        """
        初始化模拟器
        
        Args:
            transmission_model: 风险传导模型
            config: 模拟配置
        """
        self.transmission_model = transmission_model or RiskTransmissionModel()
        self.config = config or SimulationConfig()
        
        # 图结构缓存
        self._graph_edges: Dict[str, List[Tuple[str, EdgeType, float]]] = {}
        self._node_risks: Dict[str, float] = {}
        
        # 随机数生成器
        self.rng = np.random.RandomState(self.config.random_seed)
    
    def set_graph_structure(
        self,
        edges: List[Edge],
        node_risks: Optional[Dict[str, float]] = None
    ):
        """
        设置图结构
        
        Args:
            edges: 边列表
            node_risks: 节点风险映射
        """
        self._graph_edges = self.transmission_model.build_transmission_graph(edges)
        if node_risks:
            self._node_risks = node_risks
    
    def _add_noise(self, risk_value: float) -> float:
        """添加随机噪声"""
        noise = self.rng.normal(0, self.config.noise_std)
        return np.clip(risk_value + noise, 0, 1)
    
    def _should_transmit(
        self,
        source_risk: float,
        coeff: float,
        distance: int
    ) -> bool:
        """判断是否发生传导"""
        # 基础概率
        prob = source_risk * coeff
        
        # 距离衰减
        if self.config.enable_decay:
            prob *= (self.config.decay_factor ** (distance - 1))
        
        # 随机判断
        return self.rng.random() < prob
    
    def run_single_simulation(
        self,
        source_node_id: str,
        initial_risk: float,
        start_time: Optional[datetime] = None
    ) -> SimulationResult:
        """
        运行单次模拟
        
        Args:
            source_node_id: 源节点ID
            initial_risk: 初始风险值
            start_time: 开始时间
            
        Returns:
            模拟结果
        """
        import time
        start_time_perf = time.time()
        
        simulation_id = f"sim_{source_node_id}_{int(start_time_perf * 1000)}"
        
        steps = []
        affected_nodes = {source_node_id: initial_risk}
        failed_nodes = set()
        current_step = 0
        
        if start_time is None:
            start_time = datetime.now()
        
        # BFS传播
        queue = [(source_node_id, initial_risk, 0)]  # (node_id, risk, distance)
        visited = {source_node_id}
        
        while queue and current_step < self.config.max_steps:
            new_queue = []
            step_affected = {}
            step_failures = []
            step_transmissions = []
            
            for node_id, node_risk, distance in queue:
                if distance >= self.config.max_steps:
                    continue
                
                # 获取出边
                outgoing = self._graph_edges.get(node_id, [])
                
                for dst_id, edge_type, coeff in outgoing:
                    # 添加噪声
                    noisy_risk = self._add_noise(node_risk)
                    
                    # 判断是否传导
                    if self._should_transmit(noisy_risk, coeff, distance + 1):
                        propagated_risk = self.transmission_model.calculate_propagated_risk(
                            noisy_risk, edge_type, distance=distance + 1
                        )
                        
                        # 累积风险
                        if dst_id in affected_nodes:
                            affected_nodes[dst_id] = min(1.0, affected_nodes[dst_id] + propagated_risk * 0.3)
                        else:
                            affected_nodes[dst_id] = propagated_risk
                        
                        step_affected[dst_id] = affected_nodes[dst_id]
                        
                        # 记录传导事件
                        transmission = RiskTransmissionResult(
                            source_node_id=node_id,
                            source_risk_level=node_risk,
                            target_node_id=dst_id,
                            edge_type=edge_type,
                            transmission_coeff=coeff,
                            propagated_risk=propagated_risk,
                            path_length=distance + 1
                        )
                        step_transmissions.append(transmission)
                        
                        # 检查是否失效
                        if affected_nodes[dst_id] >= self.config.failure_threshold:
                            if dst_id not in failed_nodes:
                                failed_nodes.add(dst_id)
                                step_failures.append(dst_id)
                        
                        # 继续传播
                        if dst_id not in visited:
                            visited.add(dst_id)
                            new_queue.append((dst_id, affected_nodes[dst_id], distance + 1))
            
            # 记录本步结果
            step_result = SimulationStep(
                step=current_step,
                timestamp=start_time + timedelta(hours=current_step * self.config.time_step_hours),
                affected_nodes=step_affected.copy(),
                new_failures=step_failures.copy(),
                transmission_events=step_transmissions
            )
            steps.append(step_result)
            
            current_step += 1
            queue = new_queue
        
        simulation_time = (time.time() - start_time_perf) * 1000
        
        return SimulationResult(
            simulation_id=simulation_id,
            config=self.config,
            source_node_id=source_node_id,
            initial_risk=initial_risk,
            steps=steps,
            simulation_time_ms=simulation_time
        )
    
    def run_monte_carlo(
        self,
        source_node_id: str,
        initial_risk: float,
        num_rounds: Optional[int] = None
    ) -> MonteCarloResult:
        """
        运行蒙特卡洛模拟
        
        Args:
            source_node_id: 源节点ID
            initial_risk: 初始风险值
            num_rounds: 模拟轮次（覆盖配置）
            
        Returns:
            蒙特卡洛结果
        """
        rounds = num_rounds or self.config.num_rounds
        
        results = []
        affected_counts = []
        failure_counts = []
        
        for i in range(rounds):
            # 每轮使用不同的随机种子
            self.rng = np.random.RandomState(self.config.random_seed or 42 + i)
            
            sim_result = self.run_single_simulation(source_node_id, initial_risk)
            results.append(sim_result)
            affected_counts.append(sim_result.final_affected_count)
            failure_counts.append(sim_result.final_failure_count)
        
        # 统计分析
        affected_array = np.array(affected_counts)
        mean_affected = np.mean(affected_array)
        std_affected = np.std(affected_array)
        mean_failures = np.mean(failure_counts)
        
        # 95%置信区间
        ci_lower = np.percentile(affected_array, 2.5)
        ci_upper = np.percentile(affected_array, 97.5)
        
        # 概率分布
        unique, counts = np.unique(affected_counts, return_counts=True)
        prob_dist = {int(u): c / rounds for u, c in zip(unique, counts)}
        
        return MonteCarloResult(
            simulation_results=results,
            mean_affected_nodes=mean_affected,
            std_affected_nodes=std_affected,
            mean_failure_count=mean_failures,
            confidence_interval_95=(ci_lower, ci_upper),
            probability_distribution=prob_dist
        )
    
    def run_cascade_failure(
        self,
        initial_failures: List[str],
        initial_risk: float = 1.0
    ) -> SimulationResult:
        """
        运行级联失效模拟
        
        Args:
            initial_failures: 初始失效节点列表
            initial_risk: 初始风险值
            
        Returns:
            级联失效结果
        """
        import time
        start_time_perf = time.time()
        
        simulation_id = f"cascade_{'_'.join(initial_failures)}_{int(start_time_perf * 1000)}"
        
        steps = []
        affected_nodes = {node_id: initial_risk for node_id in initial_failures}
        failed_nodes = set(initial_failures)
        current_step = 0
        
        queue = [(node_id, initial_risk, 0) for node_id in initial_failures]
        
        while queue and current_step < self.config.max_steps:
            new_queue = []
            step_affected = {}
            step_failures = []
            step_transmissions = []
            
            for node_id, node_risk, distance in queue:
                outgoing = self._graph_edges.get(node_id, [])
                
                for dst_id, edge_type, coeff in outgoing:
                    # 级联失效使用更高的传导概率
                    cascade_coeff = min(1.0, coeff * 1.2)
                    
                    if self._should_transmit(node_risk, cascade_coeff, distance + 1):
                        propagated_risk = self.transmission_model.calculate_propagated_risk(
                            node_risk, edge_type, distance=distance + 1
                        )
                        
                        if dst_id not in affected_nodes:
                            affected_nodes[dst_id] = propagated_risk
                            step_affected[dst_id] = propagated_risk
                            
                            # 级联失效更容易触发
                            if propagated_risk >= self.config.failure_threshold * 0.8:
                                if dst_id not in failed_nodes:
                                    failed_nodes.add(dst_id)
                                    step_failures.append(dst_id)
                                    new_queue.append((dst_id, propagated_risk, distance + 1))
            
            step_result = SimulationStep(
                step=current_step,
                timestamp=datetime.now() + timedelta(hours=current_step),
                affected_nodes=step_affected,
                new_failures=step_failures
            )
            steps.append(step_result)
            
            current_step += 1
            queue = new_queue
        
        simulation_time = (time.time() - start_time_perf) * 1000
        
        return SimulationResult(
            simulation_id=simulation_id,
            config=self.config,
            source_node_id="cascade_init",
            initial_risk=initial_risk,
            steps=steps,
            simulation_time_ms=simulation_time
        )
    
    def run_what_if_analysis(
        self,
        source_node_id: str,
        scenarios: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        What-if假设分析
        
        Args:
            source_node_id: 源节点ID
            scenarios: 场景列表，每个场景包含参数
                - initial_risk: 初始风险
                - blocked_edges: 阻断的边 [(src, dst), ...]
                - boosted_nodes: 增强的节点 [(node_id, boost_factor), ...]
                
        Returns:
            各场景对比结果
        """
        results = {}
        
        # 保存原始配置
        original_edges = self._graph_edges.copy()
        
        for i, scenario in enumerate(scenarios):
            scenario_name = scenario.get("name", f"scenario_{i}")
            initial_risk = scenario.get("initial_risk", 0.5)
            blocked_edges = scenario.get("blocked_edges", [])
            boosted_nodes = scenario.get("boosted_nodes", [])
            
            # 应用场景修改
            modified_edges = self._apply_scenario_modifications(
                original_edges, blocked_edges, boosted_nodes
            )
            self._graph_edges = modified_edges
            
            # 运行模拟
            sim_result = self.run_single_simulation(source_node_id, initial_risk)
            
            results[scenario_name] = {
                "config": scenario,
                "affected_count": sim_result.final_affected_count,
                "failure_count": sim_result.final_failure_count,
                "steps_count": len(sim_result.steps)
            }
        
        # 恢复原始配置
        self._graph_edges = original_edges
        
        return {
            "source_node_id": source_node_id,
            "scenario_count": len(scenarios),
            "results": results,
            "comparison": self._compare_scenarios(results)
        }
    
    def _apply_scenario_modifications(
        self,
        original_edges: Dict[str, List[Tuple[str, EdgeType, float]]],
        blocked_edges: List[Tuple[str, str]],
        boosted_nodes: List[Tuple[str, float]]
    ) -> Dict[str, List[Tuple[str, EdgeType, float]]]:
        """应用场景修改到图结构"""
        modified = defaultdict(list)
        
        blocked_set = set(blocked_edges)
        boost_map = {node_id: factor for node_id, factor in boosted_nodes}
        
        for src_id, targets in original_edges.items():
            for dst_id, edge_type, coeff in targets:
                # 检查是否被阻断
                if (src_id, dst_id) in blocked_set:
                    continue
                
                # 应用节点增强
                modified_coeff = coeff
                if src_id in boost_map:
                    modified_coeff = min(1.0, coeff * boost_map[src_id])
                
                modified[src_id].append((dst_id, edge_type, modified_coeff))
        
        return dict(modified)
    
    def _compare_scenarios(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """对比不同场景的结果"""
        affected_counts = [r["affected_count"] for r in results.values()]
        failure_counts = [r["failure_count"] for r in results.values()]
        
        return {
            "best_case": {
                "scenario": min(results.items(), key=lambda x: x[1]["affected_count"])[0],
                "affected": min(affected_counts)
            },
            "worst_case": {
                "scenario": max(results.items(), key=lambda x: x[1]["affected_count"])[0],
                "affected": max(affected_counts)
            },
            "average_affected": np.mean(affected_counts),
            "average_failures": np.mean(failure_counts)
        }
    
    def get_propagation_path(
        self,
        source_node_id: str,
        target_node_id: str,
        max_depth: int = 10
    ) -> Optional[List[Tuple[str, EdgeType, float]]]:
        """
        获取从源到目标的传播路径
        
        Args:
            source_node_id: 源节点
            target_node_id: 目标节点
            max_depth: 最大深度
            
        Returns:
            传播路径，如果不存在则返回None
        """
        # BFS寻找路径
        from collections import deque
        
        queue = deque([(source_node_id, [])])
        visited = {source_node_id}
        
        while queue:
            current_id, path = queue.popleft()
            
            if current_id == target_node_id and path:
                return path
            
            if len(path) >= max_depth:
                continue
            
            for dst_id, edge_type, coeff in self._graph_edges.get(current_id, []):
                if dst_id not in visited:
                    visited.add(dst_id)
                    new_path = path + [(dst_id, edge_type, coeff)]
                    queue.append((dst_id, new_path))
        
        return None


def create_simulator(
    config: Optional[SimulationConfig] = None
) -> RiskPropagationSimulator:
    """
    创建风险传播模拟器
    
    Args:
        config: 模拟配置
        
    Returns:
        RiskPropagationSimulator实例
    """
    return RiskPropagationSimulator(config=config)


# 导出
__all__ = [
    'SimulationMode',
    'SimulationConfig',
    'SimulationStep',
    'SimulationResult',
    'MonteCarloResult',
    'RiskPropagationSimulator',
    'create_simulator'
]
