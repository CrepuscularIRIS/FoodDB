"""时序风险传播模型。"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


class TemporalRiskPropagator:
    """基于供应链边的时序风险传播器。"""

    def __init__(self, retriever, scoring_engine=None):
        self.retriever = retriever
        self.scoring_engine = scoring_engine

    def time_decay(self, step: int, decay_rate: float = 0.55) -> float:
        """时间衰减函数: exp(-lambda * t)。"""
        return math.exp(-max(decay_rate, 0.0) * max(step, 0))

    def edge_risk_score(self, edge: Dict[str, Any]) -> float:
        """边级风险分数，结合权重、冷链、距离、时长、频次。"""
        base_weight = self._safe_float(edge.get("weight"), 0.5)
        cold_chain_ok = str(edge.get("cold_chain_maintained", "")).lower() == "true"
        cold_chain_factor = 0.9 if cold_chain_ok else 1.25

        distance_km = self._safe_float(edge.get("transport_distance_km"), 0.0)
        distance_factor = min(1.35, 1.0 + distance_km / 1000.0)

        duration_h = self._safe_float(edge.get("transport_duration_hours"), 0.0)
        duration_factor = min(1.3, 1.0 + duration_h / 48.0)

        freq_monthly = self._safe_float(edge.get("frequency_monthly"), 0.0)
        freq_factor = min(1.2, 0.9 + freq_monthly / 100.0)

        score = base_weight * cold_chain_factor * distance_factor * duration_factor * freq_factor
        return max(0.0, min(score, 1.0))

    def propagate(
        self,
        node_id: str,
        max_steps: int = 3,
        initial_risk: Optional[float] = None,
        decay_rate: float = 0.55,
        min_risk_threshold: float = 0.03,
    ) -> Dict[str, Any]:
        """执行时序风险传播 (t0, t1, t2...)。"""
        if not node_id:
            raise ValueError("node_id 不能为空")

        init_risk = self._resolve_initial_risk(node_id, initial_risk)

        timeline: List[Dict[str, Any]] = []
        edge_impacts: List[Dict[str, Any]] = []

        visited_best: Dict[str, float] = {node_id: init_risk}
        frontier: List[Dict[str, Any]] = [{"node_id": node_id, "risk": init_risk, "path": [node_id]}]

        timeline.append(
            {
                "t": 0,
                "decay": self.time_decay(0, decay_rate),
                "nodes": [{"node_id": node_id, "risk": round(init_risk, 4), "path": [node_id]}],
            }
        )

        for step in range(1, max_steps + 1):
            decay = self.time_decay(step, decay_rate)
            next_frontier: List[Dict[str, Any]] = []
            step_nodes: List[Dict[str, Any]] = []

            for item in frontier:
                current = item["node_id"]
                current_risk = item["risk"]
                current_path = item["path"]

                for neighbor in self._iter_neighbors(current):
                    edge = neighbor["edge"]
                    edge_score = self.edge_risk_score(edge)
                    direction_factor = 1.0 if neighbor["direction"] == "downstream" else 0.75
                    transmitted = current_risk * edge_score * decay * direction_factor

                    if transmitted < min_risk_threshold:
                        continue

                    nid = neighbor["node_id"]
                    if transmitted <= visited_best.get(nid, 0.0):
                        continue
                    visited_best[nid] = transmitted

                    node_item = {
                        "node_id": nid,
                        "risk": round(transmitted, 4),
                        "parent": current,
                        "direction": neighbor["direction"],
                        "edge_id": edge.get("edge_id"),
                        "edge_risk_score": round(edge_score, 4),
                        "path": current_path + [nid],
                    }
                    step_nodes.append(node_item)
                    next_frontier.append({"node_id": nid, "risk": transmitted, "path": current_path + [nid]})

                    edge_impacts.append(
                        {
                            "t": step,
                            "edge_id": edge.get("edge_id"),
                            "source_id": edge.get("source_id"),
                            "target_id": edge.get("target_id"),
                            "direction": neighbor["direction"],
                            "edge_risk_score": round(edge_score, 4),
                            "transmitted_risk": round(transmitted, 4),
                        }
                    )

            timeline.append({"t": step, "decay": round(decay, 4), "nodes": step_nodes})
            if not next_frontier:
                break
            frontier = next_frontier

        active_steps = [frame for frame in timeline if frame["nodes"]]
        summary = {
            "source_node": node_id,
            "initial_risk": round(init_risk, 4),
            "max_steps": max_steps,
            "executed_steps": len(active_steps) - 1,
            "affected_nodes": max(len(visited_best) - 1, 0),
            "peak_risk": round(max(visited_best.values()), 4),
            "timeline": timeline,
            "edge_impacts": edge_impacts,
        }
        return summary

    def _iter_neighbors(self, node_id: str) -> List[Dict[str, Any]]:
        neighbors = []
        for edge in self.retriever.edges_from.get(node_id, []):
            neighbors.append({"node_id": edge.get("target_id"), "edge": edge, "direction": "downstream"})
        for edge in self.retriever.edges_to.get(node_id, []):
            neighbors.append({"node_id": edge.get("source_id"), "edge": edge, "direction": "upstream"})
        return neighbors

    def _resolve_initial_risk(self, node_id: str, initial_risk: Optional[float]) -> float:
        if initial_risk is not None:
            return max(0.0, min(float(initial_risk), 1.0))

        if not self.scoring_engine:
            return 0.5

        try:
            if node_id.startswith("ENT-"):
                score = self.scoring_engine.calculate_node_risk(enterprise_id=node_id)
                return max(0.0, min(score.total_score / 100.0, 1.0))
            if node_id.startswith("BATCH-"):
                score = self.scoring_engine.calculate_node_risk(batch_id=node_id)
                return max(0.0, min(score.total_score / 100.0, 1.0))
        except Exception:
            pass
        return 0.5

    @staticmethod
    def _safe_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
