"""ModelA + risk_visualization integrated closed-loop engine.

Pipeline:
1) risk prediction on heterogeneous graph entities (nodes/edges)
2) intelligent inspection optimization (risk elimination vs cost)
3) feedback update from inspection labels
4) 12-hour propagation simulation (predicted links + real future links)

This module is intentionally auditable and deterministic (seed + hash based).
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


RISK_NAMES_ZH = [
    "非食用添加剂",
    "农药兽药残留",
    "食品添加剂",
    "微生物",
    "重金属污染物",
    "生物毒素",
    "其他污染物",
]
RISK_DIM = len(RISK_NAMES_ZH)
MICRO_IDX = 3


def _clip01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _parse_ts(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    s = s.replace("/", "-")
    try:
        return datetime.fromisoformat(s)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s[: len(fmt)], fmt)
        except Exception:
            continue
    return None


def _hash01(key: str) -> float:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return int(h, 16) / float(16**16 - 1)


def _risk_level(score: float) -> str:
    if score >= 0.72:
        return "high"
    if score >= 0.42:
        return "medium"
    return "low"


def _vec7(vec: Any) -> List[float]:
    if not isinstance(vec, list):
        return [0.0] * RISK_DIM
    out = [_clip01(_to_float(vec[i], 0.0)) if i < len(vec) else 0.0 for i in range(RISK_DIM)]
    return out


def _node_score(n: Dict[str, Any]) -> float:
    return _clip01(
        _to_float(
            n.get("priority_score", n.get("risk_proxy", n.get("view_risk_score", n.get("risk_score", 0.0)))),
            0.0,
        )
    )


def _edge_score(e: Dict[str, Any]) -> float:
    if e.get("edge_priority") is not None:
        return _clip01(_to_float(e.get("edge_priority"), 0.0))
    if e.get("edge_risk_proxy") is not None:
        return _clip01(_to_float(e.get("edge_risk_proxy"), 0.0))
    if e.get("view_risk_score") is not None:
        return _clip01(_to_float(e.get("view_risk_score"), 0.0))
    return _clip01(max(_vec7(e.get("risk_probabilities"))))


def _node_uncertainty(n: Dict[str, Any]) -> float:
    return _clip01(_to_float(n.get("uncertainty_proxy", 0.25), 0.25))


def _edge_uncertainty(e: Dict[str, Any]) -> float:
    if e.get("edge_uncertainty") is not None:
        return _clip01(_to_float(e.get("edge_uncertainty"), 0.2))
    top5 = _to_float(e.get("top5_count"), 0.0)
    transit = _to_float(e.get("transit_hours"), 0.0)
    return _clip01(0.08 * top5 + min(transit / 72.0, 0.45) + 0.08)


def _scale_cost(scale: str) -> float:
    s = str(scale or "")
    if "大" in s:
        return 1.6
    if "中" in s:
        return 1.25
    if "小" in s:
        return 1.0
    return 1.15


def _node_type_cost(node_type: str) -> float:
    t = str(node_type or "")
    if "加工" in t:
        return 1.35
    if "仓储" in t:
        return 1.2
    if "物流" in t:
        return 1.15
    if "零售" in t:
        return 0.95
    return 1.0


def _node_cost(n: Dict[str, Any]) -> float:
    return round(_scale_cost(str(n.get("enterprise_scale", "中型企业"))) * _node_type_cost(str(n.get("node_type", ""))), 6)


def _edge_cost(e: Dict[str, Any]) -> float:
    logistics_scale = str(e.get("logistics_scale", "中型企业"))
    base = _scale_cost(logistics_scale)
    transit = _to_float(e.get("transit_hours"), 0.0)
    dwell = _to_float(e.get("target_stay_hours"), 0.0) + _to_float(e.get("retail_stay_hours"), 0.0)
    return round(base * (0.85 + min(transit / 96.0, 0.45) + min(dwell / 240.0, 0.4)), 6)


def _dominant_risk(vec: List[float]) -> Tuple[int, str, float]:
    if not vec:
        return 0, RISK_NAMES_ZH[0], 0.0
    idx = max(range(min(len(vec), RISK_DIM)), key=lambda i: vec[i])
    return idx, RISK_NAMES_ZH[idx], _to_float(vec[idx], 0.0)


def _topk_predictions(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    node_top_n: int = 200,
    edge_top_n: int = 300,
) -> Dict[str, Any]:
    node_items: List[Dict[str, Any]] = []
    for n in nodes:
        vec = _vec7(n.get("view_risk_probabilities") or n.get("risk_probabilities") or n.get("category_risk_probabilities"))
        score = _node_score(n)
        unc = _node_uncertainty(n)
        idx, risk_name, risk_val = _dominant_risk(vec)
        node_items.append(
            {
                "node_id": str(n.get("node_id")),
                "name": n.get("name", ""),
                "node_type": n.get("node_type", ""),
                "enterprise_scale": n.get("enterprise_scale", ""),
                "score": round(score, 6),
                "uncertainty": round(unc, 6),
                "risk_level": _risk_level(score),
                "risk_probabilities": [round(x, 6) for x in vec],
                "top5_count": int(_to_float(n.get("top5_count"), 0.0)),
                "dominant_risk": {"idx": idx, "name": risk_name, "prob": round(risk_val, 6)},
            }
        )
    node_items.sort(key=lambda x: x["score"], reverse=True)

    edge_items: List[Dict[str, Any]] = []
    for e in edges:
        vec = _vec7(e.get("view_risk_probabilities") or e.get("risk_probabilities"))
        score = _edge_score(e)
        unc = _edge_uncertainty(e)
        idx, risk_name, risk_val = _dominant_risk(vec)
        edge_items.append(
            {
                "edge_id": str(e.get("edge_id")),
                "source": str(e.get("source")),
                "target": str(e.get("target")),
                "source_name": e.get("source_name", ""),
                "target_name": e.get("target_name", ""),
                "source_type": e.get("source_type", ""),
                "target_type": e.get("target_type", ""),
                "dairy_product_type": e.get("dairy_product_type", ""),
                "score": round(score, 6),
                "uncertainty": round(unc, 6),
                "risk_level": _risk_level(score),
                "risk_probabilities": [round(x, 6) for x in vec],
                "top5_count": int(_to_float(e.get("top5_count"), 0.0)),
                "dominant_risk": {"idx": idx, "name": risk_name, "prob": round(risk_val, 6)},
            }
        )
    edge_items.sort(key=lambda x: x["score"], reverse=True)

    return {
        "nodes_top": node_items[: max(1, node_top_n)],
        "edges_top": edge_items[: max(1, edge_top_n)],
        "node_count": len(node_items),
        "edge_count": len(edge_items),
    }


def _precision_recall_at_k(ranked_ids: List[str], labels: Dict[str, int], k: int) -> Dict[str, float]:
    if k <= 0:
        return {
            "top_k": 0,
            "positive_total": int(sum(labels.values())),
            "positive_in_top_k": 0,
            "precision_at_k": 0.0,
            "recall_at_k": 0.0,
        }
    use_k = min(k, len(ranked_ids))
    top_ids = ranked_ids[:use_k]
    pos_total = int(sum(1 for v in labels.values() if int(v) == 1))
    pos_top = int(sum(1 for eid in top_ids if int(labels.get(eid, 0)) == 1))
    precision = pos_top / max(use_k, 1)
    recall = pos_top / max(pos_total, 1)
    return {
        "top_k": int(use_k),
        "positive_total": int(pos_total),
        "positive_in_top_k": int(pos_top),
        "precision_at_k": round(precision, 6),
        "recall_at_k": round(recall, 6),
    }


def _transmit(src_vec: List[float], edge_vec: List[float], edge: Dict[str, Any]) -> List[float]:
    transit = _to_float(edge.get("transit_hours"), 0.0)
    origin_stay = _to_float(edge.get("origin_stay_hours"), 0.0)
    target_stay = _to_float(edge.get("target_stay_hours"), 0.0)
    retail_stay = _to_float(edge.get("retail_stay_hours"), 0.0)

    time_term = min((target_stay + retail_stay) / 48.0, 1.0)
    transit_term = min(transit / 96.0, 1.0)
    origin_term = min(origin_stay / 24.0, 1.0)

    out: List[float] = [0.0] * RISK_DIM
    for i in range(RISK_DIM):
        base = 0.11 if i != MICRO_IDX else 0.22
        dynamic = 1.0 + 0.32 * time_term + 0.18 * transit_term + 0.08 * origin_term
        if i == MICRO_IDX:
            dynamic *= 1.16
        out[i] = _clip01(_to_float(src_vec[i], 0.0) * _to_float(edge_vec[i], 0.0) * base * dynamic)
    return out


def _vec_max(a: List[float], b: List[float]) -> List[float]:
    return [_clip01(max(_to_float(a[i], 0.0), _to_float(b[i], 0.0))) for i in range(RISK_DIM)]


def _vec_decay_growth(v: List[float], node_type: str) -> List[float]:
    growth_map = {
        "原奶供应商": 0.004,
        "乳制品加工厂": 0.006,
        "冷链仓储中心": 0.007,
        "物流公司": 0.005,
        "零售终端": 0.009,
    }
    g = growth_map.get(str(node_type or ""), 0.005)
    out = [0.0] * RISK_DIM
    for i in range(RISK_DIM):
        p = 0.975 if i != MICRO_IDX else 0.986
        out[i] = _clip01(_to_float(v[i], 0.0) * p + g)
    return out


def _score_from_vec(v: List[float]) -> float:
    weights = [1.0, 1.05, 1.0, 1.2, 1.1, 1.0, 0.9]
    den = sum(weights)
    return _clip01(sum(_to_float(v[i], 0.0) * weights[i] for i in range(RISK_DIM)) / den)


def run_integrated_closed_loop(
    scored_view: Dict[str, Any],
    inspect_time: Optional[str] = None,
    forecast_hours: int = 12,
    inspect_budget: int = 120,
    edge_inspect_ratio: float = 0.50,
    explore_weight: float = 0.35,
    feedback_strength: float = 0.80,
    seed: int = 42,
) -> Dict[str, Any]:
    nodes = [dict(x) for x in scored_view.get("nodes", [])]
    edges = [dict(x) for x in scored_view.get("edges", [])]

    if not nodes:
        return {
            "config": {
                "forecast_hours": int(forecast_hours),
                "inspect_budget": int(inspect_budget),
                "edge_inspect_ratio": float(edge_inspect_ratio),
                "explore_weight": float(explore_weight),
                "feedback_strength": float(feedback_strength),
                "seed": int(seed),
            },
            "message": "当前视图没有可用节点，无法执行闭环整合模拟。",
        }

    # timestamp parsing
    ts_values: List[datetime] = []
    for e in edges:
        ts = _parse_ts(e.get("timestamp"))
        if ts is not None:
            e["_ts"] = ts
            ts_values.append(ts)

    if inspect_time:
        inspect_dt = _parse_ts(inspect_time)
    else:
        inspect_dt = None

    if inspect_dt is None:
        if ts_values:
            ts_sorted = sorted(ts_values)
            inspect_dt = ts_sorted[int(0.55 * (len(ts_sorted) - 1))]
        else:
            inspect_dt = datetime(2025, 1, 1, 12, 0, 0)
    forecast_hours = max(1, min(int(forecast_hours), 72))
    inspect_budget = max(5, min(int(inspect_budget), 2000))
    edge_inspect_ratio = _clip01(edge_inspect_ratio)
    explore_weight = _clip01(explore_weight)
    feedback_strength = _clip01(feedback_strength)
    end_dt = inspect_dt + timedelta(hours=forecast_hours)

    node_map: Dict[str, Dict[str, Any]] = {str(n.get("node_id")): n for n in nodes if n.get("node_id") is not None}
    edge_map: Dict[str, Dict[str, Any]] = {str(e.get("edge_id")): e for e in edges if e.get("edge_id") is not None}

    # prediction (before feedback)
    pre = _topk_predictions(nodes, edges)

    # optimization candidates
    node_quota = max(1, int(round(inspect_budget * (1.0 - edge_inspect_ratio))))
    edge_quota = max(1, inspect_budget - node_quota)

    node_candidates: List[Dict[str, Any]] = []
    for n in nodes:
        nid = str(n.get("node_id"))
        score = _node_score(n)
        unc = _node_uncertainty(n)
        vec = _vec7(n.get("view_risk_probabilities") or n.get("risk_probabilities") or n.get("category_risk_probabilities"))
        cost = _node_cost(n)
        top5_bonus = 1.0 + 0.10 * min(3.0, _to_float(n.get("top5_count"), 0.0))
        utility = score * (1.0 + explore_weight * unc) * top5_bonus
        efficacy = min(1.0, 0.55 * score + 0.45 * max(vec))
        objective = (0.65 * utility + 0.35 * efficacy) / max(cost, 1e-6)
        freq = 3 if score >= 0.75 else (2 if score >= 0.55 else 1)
        node_candidates.append(
            {
                "entity_id": f"node:{nid}",
                "kind": "node",
                "raw_id": nid,
                "name": n.get("name", ""),
                "node_type": n.get("node_type", ""),
                "score": round(score, 6),
                "uncertainty": round(unc, 6),
                "risk_probabilities": vec,
                "cost": round(cost, 6),
                "inspect_frequency": int(freq),
                "objective": round(objective, 6),
                "utility": round(utility, 6),
            }
        )
    node_candidates.sort(key=lambda x: x["objective"], reverse=True)

    edge_candidates: List[Dict[str, Any]] = []
    for e in edges:
        eid = str(e.get("edge_id"))
        score = _edge_score(e)
        unc = _edge_uncertainty(e)
        vec = _vec7(e.get("view_risk_probabilities") or e.get("risk_probabilities"))
        cost = _edge_cost(e)
        top5_bonus = 1.0 + 0.10 * min(3.0, _to_float(e.get("top5_count"), 0.0))
        utility = score * (1.0 + explore_weight * unc) * top5_bonus
        efficacy = min(1.0, 0.55 * score + 0.45 * max(vec))
        objective = (0.65 * utility + 0.35 * efficacy) / max(cost, 1e-6)
        freq = 2 if score >= 0.70 else 1
        edge_candidates.append(
            {
                "entity_id": f"edge:{eid}",
                "kind": "edge",
                "raw_id": eid,
                "source": str(e.get("source")),
                "target": str(e.get("target")),
                "source_name": e.get("source_name", ""),
                "target_name": e.get("target_name", ""),
                "dairy_product_type": e.get("dairy_product_type", ""),
                "score": round(score, 6),
                "uncertainty": round(unc, 6),
                "risk_probabilities": vec,
                "cost": round(cost, 6),
                "inspect_frequency": int(freq),
                "objective": round(objective, 6),
                "utility": round(utility, 6),
            }
        )
    edge_candidates.sort(key=lambda x: x["objective"], reverse=True)

    selected_nodes = node_candidates[: min(node_quota, len(node_candidates))]
    selected_edges = edge_candidates[: min(edge_quota, len(edge_candidates))]

    selected_all: List[Dict[str, Any]] = []
    for i, item in enumerate(selected_nodes + selected_edges, start=1):
        rec = dict(item)
        rec["order"] = int(i)
        selected_all.append(rec)

    # weak-truth simulation + feedback
    feedback_rows: List[Dict[str, Any]] = []
    positive_entities = set()

    node_post_vec: Dict[str, List[float]] = {}
    for n in nodes:
        nid = str(n.get("node_id"))
        node_post_vec[nid] = _vec7(n.get("view_risk_probabilities") or n.get("risk_probabilities") or n.get("category_risk_probabilities"))

    edge_post_vec: Dict[str, List[float]] = {}
    for e in edges:
        eid = str(e.get("edge_id"))
        edge_post_vec[eid] = _vec7(e.get("view_risk_probabilities") or e.get("risk_probabilities"))

    for item in selected_all:
        vec = _vec7(item.get("risk_probabilities"))
        score = _to_float(item.get("score"), 0.0)
        unc = _to_float(item.get("uncertainty"), 0.0)
        p_true = _clip01(0.03 + 0.72 * score + 0.16 * unc + (_hash01(f"truth-bias|{seed}|{item['entity_id']}") - 0.5) * 0.18)
        y = 1 if _hash01(f"truth-draw|{seed}|{item['entity_id']}") < p_true else 0
        dom_idx, dom_name, _ = _dominant_risk(vec)

        if y == 1:
            observed = vec[:]
            observed[dom_idx] = _clip01(max(observed[dom_idx], 0.86))
            observed = [_clip01(x + 0.05 * feedback_strength) for x in observed]
            positive_entities.add(item["entity_id"])
        else:
            damp = 1.0 - 0.85 * feedback_strength
            observed = [_clip01(x * damp) for x in vec]

        feedback_rows.append(
            {
                "entity_id": item["entity_id"],
                "kind": item["kind"],
                "raw_id": item["raw_id"],
                "order": item["order"],
                "predicted_score": round(score, 6),
                "uncertainty": round(unc, 6),
                "inspection_label": int(y),
                "dominant_risk": dom_name,
                "feedback_score": float(y),
                "risk_probabilities_after_feedback": [round(x, 6) for x in observed],
            }
        )

        if item["kind"] == "node":
            nid = str(item["raw_id"])
            node_post_vec[nid] = observed
        else:
            eid = str(item["raw_id"])
            edge_post_vec[eid] = observed

    # graph neighborhood propagation from feedback
    incident_edges: Dict[str, List[str]] = {}
    for e in edges:
        s = str(e.get("source"))
        t = str(e.get("target"))
        eid = str(e.get("edge_id"))
        incident_edges.setdefault(s, []).append(eid)
        incident_edges.setdefault(t, []).append(eid)

    for rec in feedback_rows:
        if rec["inspection_label"] == 0:
            continue
        if rec["kind"] == "node":
            nid = str(rec["raw_id"])
            for eid in incident_edges.get(nid, []):
                v = edge_post_vec.get(eid, [0.0] * RISK_DIM)
                edge_post_vec[eid] = [_clip01(x + 0.08 * rec["risk_probabilities_after_feedback"][i]) for i, x in enumerate(v)]
        else:
            eid = str(rec["raw_id"])
            edge = edge_map.get(eid)
            if edge:
                s = str(edge.get("source"))
                t = str(edge.get("target"))
                ev = edge_post_vec.get(eid, [0.0] * RISK_DIM)
                for nid in (s, t):
                    cur = node_post_vec.get(nid, [0.0] * RISK_DIM)
                    node_post_vec[nid] = [_clip01(cur[i] + 0.08 * ev[i]) for i in range(RISK_DIM)]

    # ranking eval before/after
    labels_node: Dict[str, int] = {}
    for n in nodes:
        nid = str(n.get("node_id"))
        score = _node_score(n)
        unc = _node_uncertainty(n)
        p_true = _clip01(0.02 + 0.70 * score + 0.20 * unc + (_hash01(f"node-lab-bias|{seed}|{nid}") - 0.5) * 0.15)
        labels_node[nid] = 1 if _hash01(f"node-lab-draw|{seed}|{nid}") < p_true else 0

    labels_edge: Dict[str, int] = {}
    for e in edges:
        eid = str(e.get("edge_id"))
        score = _edge_score(e)
        unc = _edge_uncertainty(e)
        p_true = _clip01(0.03 + 0.68 * score + 0.22 * unc + (_hash01(f"edge-lab-bias|{seed}|{eid}") - 0.5) * 0.15)
        labels_edge[eid] = 1 if _hash01(f"edge-lab-draw|{seed}|{eid}") < p_true else 0

    k_node = min(100, max(20, len(nodes) // 20))
    k_edge = min(200, max(30, len(edges) // 30))

    ranked_node_before = sorted([str(n.get("node_id")) for n in nodes], key=lambda nid: _node_score(node_map.get(nid, {})), reverse=True)
    ranked_node_after = sorted(node_post_vec.keys(), key=lambda nid: _score_from_vec(node_post_vec[nid]), reverse=True)
    ranked_edge_before = sorted([str(e.get("edge_id")) for e in edges], key=lambda eid: _edge_score(edge_map.get(eid, {})), reverse=True)
    ranked_edge_after = sorted(edge_post_vec.keys(), key=lambda eid: _score_from_vec(edge_post_vec[eid]), reverse=True)

    eval_before = {
        "node": _precision_recall_at_k(ranked_node_before, labels_node, k_node),
        "edge": _precision_recall_at_k(ranked_edge_before, labels_edge, k_edge),
    }
    eval_after = {
        "node": _precision_recall_at_k(ranked_node_after, labels_node, k_node),
        "edge": _precision_recall_at_k(ranked_edge_after, labels_edge, k_edge),
    }

    # seed nodes for propagation
    seed_nodes = set()
    for rec in feedback_rows:
        if rec["inspection_label"] != 1:
            continue
        if rec["kind"] == "node":
            seed_nodes.add(str(rec["raw_id"]))
        else:
            edge = edge_map.get(str(rec["raw_id"]))
            if edge:
                seed_nodes.add(str(edge.get("source")))
                seed_nodes.add(str(edge.get("target")))
    if not seed_nodes:
        seed_nodes.add(ranked_node_before[0])

    # build historical transition stats (<= inspect_dt)
    hist_pairs: Dict[str, Dict[str, Dict[str, Any]]] = {}
    future_by_hour: Dict[int, List[Dict[str, Any]]] = {}

    for e in edges:
        ts = e.get("_ts")
        if ts is None:
            continue
        s = str(e.get("source"))
        t = str(e.get("target"))
        vec = edge_post_vec.get(str(e.get("edge_id")), _vec7(e.get("risk_probabilities")))
        if ts <= inspect_dt:
            src_map = hist_pairs.setdefault(s, {})
            p = src_map.get(t)
            if p is None:
                src_map[t] = {
                    "count": 1.0,
                    "vec_sum": vec[:],
                    "transit_sum": _to_float(e.get("transit_hours"), 0.0),
                    "origin_sum": _to_float(e.get("origin_stay_hours"), 0.0),
                    "target_sum": _to_float(e.get("target_stay_hours"), 0.0),
                    "retail_sum": _to_float(e.get("retail_stay_hours"), 0.0),
                }
            else:
                p["count"] += 1.0
                for i in range(RISK_DIM):
                    p["vec_sum"][i] += vec[i]
                p["transit_sum"] += _to_float(e.get("transit_hours"), 0.0)
                p["origin_sum"] += _to_float(e.get("origin_stay_hours"), 0.0)
                p["target_sum"] += _to_float(e.get("target_stay_hours"), 0.0)
                p["retail_sum"] += _to_float(e.get("retail_stay_hours"), 0.0)
        elif inspect_dt < ts <= end_dt:
            h = int((ts - inspect_dt).total_seconds() // 3600) + 1
            if 1 <= h <= forecast_hours:
                future_by_hour.setdefault(h, []).append(e)

    top_targets: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    for s, dst_map in hist_pairs.items():
        arr = sorted(dst_map.items(), key=lambda x: x[1].get("count", 0.0), reverse=True)
        top_targets[s] = arr[:6]

    predicted_state: Dict[str, List[float]] = {}
    real_state: Dict[str, List[float]] = {}
    for nid in seed_nodes:
        vec = node_post_vec.get(nid, _vec7(node_map.get(nid, {}).get("risk_probabilities")))
        predicted_state[nid] = vec[:]
        real_state[nid] = vec[:]

    predicted_paths: List[Dict[str, Any]] = []
    real_paths: List[Dict[str, Any]] = []
    frames: List[Dict[str, Any]] = []

    for h in range(1, forecast_hours + 1):
        cur_ts = inspect_dt + timedelta(hours=h)

        # predicted links from historical transition table
        pred_next = {nid: _vec_decay_growth(v, str(node_map.get(nid, {}).get("node_type", ""))) for nid, v in predicted_state.items()}
        pred_edges_hour = []

        for src, src_vec in list(predicted_state.items()):
            src_score = _score_from_vec(src_vec)
            if src_score < 0.12:
                continue
            candidates = top_targets.get(src, [])[:3]
            if not candidates:
                continue
            total_count = sum(_to_float(stat.get("count"), 0.0) for _, stat in candidates)
            if total_count <= 0:
                continue
            for dst, stat in candidates:
                cnt = _to_float(stat.get("count"), 0.0)
                frac = cnt / total_count
                prob = _clip01(0.18 + 0.55 * frac + 0.30 * src_score)
                if _hash01(f"pred-link|{seed}|{src}|{dst}|{h}") > prob:
                    continue
                c = max(1.0, cnt)
                avg_vec = [_clip01(_to_float(stat["vec_sum"][i], 0.0) / c) for i in range(RISK_DIM)]
                pseudo_edge = {
                    "transit_hours": _to_float(stat.get("transit_sum"), 0.0) / c,
                    "origin_stay_hours": _to_float(stat.get("origin_sum"), 0.0) / c,
                    "target_stay_hours": _to_float(stat.get("target_sum"), 0.0) / c,
                    "retail_stay_hours": _to_float(stat.get("retail_sum"), 0.0) / c,
                }
                transfer = _transmit(src_vec, avg_vec, pseudo_edge)
                prev = pred_next.get(dst, [0.0] * RISK_DIM)
                pred_next[dst] = _vec_max(prev, transfer)
                tr_score = _score_from_vec(transfer)
                rec = {
                    "hour": h,
                    "timestamp": cur_ts.isoformat(sep=" "),
                    "source": src,
                    "target": dst,
                    "risk_score": round(tr_score, 6),
                    "risk_level": _risk_level(tr_score),
                    "dominant_risk": _dominant_risk(transfer)[1],
                    "kind": "predicted",
                }
                pred_edges_hour.append(rec)
                predicted_paths.append(rec)

        predicted_state = {nid: [_clip01(x) for x in v] for nid, v in pred_next.items() if _score_from_vec(v) >= 0.015}

        # real future links
        real_next = {nid: _vec_decay_growth(v, str(node_map.get(nid, {}).get("node_type", ""))) for nid, v in real_state.items()}
        real_edges_hour = []
        for e in future_by_hour.get(h, []):
            src = str(e.get("source"))
            dst = str(e.get("target"))
            src_vec = real_state.get(src)
            if src_vec is None:
                continue
            if _score_from_vec(src_vec) < 0.12:
                continue
            ev = edge_post_vec.get(str(e.get("edge_id")), _vec7(e.get("risk_probabilities")))
            transfer = _transmit(src_vec, ev, e)
            prev = real_next.get(dst, [0.0] * RISK_DIM)
            real_next[dst] = _vec_max(prev, transfer)
            tr_score = _score_from_vec(transfer)
            rec = {
                "hour": h,
                "timestamp": cur_ts.isoformat(sep=" "),
                "source": src,
                "target": dst,
                "edge_id": str(e.get("edge_id")),
                "risk_score": round(tr_score, 6),
                "risk_level": _risk_level(tr_score),
                "dominant_risk": _dominant_risk(transfer)[1],
                "kind": "real",
            }
            real_edges_hour.append(rec)
            real_paths.append(rec)

        real_state = {nid: [_clip01(x) for x in v] for nid, v in real_next.items() if _score_from_vec(v) >= 0.015}

        pred_scores = [_score_from_vec(v) for v in predicted_state.values()]
        real_scores = [_score_from_vec(v) for v in real_state.values()]

        frames.append(
            {
                "hour": int(h),
                "timestamp": cur_ts.isoformat(sep=" "),
                "predicted_active_nodes": int(len(predicted_state)),
                "predicted_active_edges": int(len(pred_edges_hour)),
                "predicted_max_score": round(max(pred_scores) if pred_scores else 0.0, 6),
                "real_active_nodes": int(len(real_state)),
                "real_active_edges": int(len(real_edges_hour)),
                "real_max_score": round(max(real_scores) if real_scores else 0.0, 6),
            }
        )

    # post top tensors
    node_post_rows = []
    for nid, vec in node_post_vec.items():
        score = _score_from_vec(vec)
        n = node_map.get(nid, {})
        node_post_rows.append(
            {
                "node_id": nid,
                "name": n.get("name", ""),
                "node_type": n.get("node_type", ""),
                "score": round(score, 6),
                "risk_level": _risk_level(score),
                "risk_probabilities": [round(x, 6) for x in vec],
            }
        )
    node_post_rows.sort(key=lambda x: x["score"], reverse=True)

    edge_post_rows = []
    for eid, vec in edge_post_vec.items():
        score = _score_from_vec(vec)
        e = edge_map.get(eid, {})
        edge_post_rows.append(
            {
                "edge_id": eid,
                "source": str(e.get("source", "")),
                "target": str(e.get("target", "")),
                "source_name": e.get("source_name", ""),
                "target_name": e.get("target_name", ""),
                "score": round(score, 6),
                "risk_level": _risk_level(score),
                "risk_probabilities": [round(x, 6) for x in vec],
            }
        )
    edge_post_rows.sort(key=lambda x: x["score"], reverse=True)

    pos_found = int(sum(1 for r in feedback_rows if int(r["inspection_label"]) == 1))
    hit_rate = pos_found / max(len(feedback_rows), 1)

    expected_reduction = 0.0
    for r in feedback_rows:
        before = _to_float(r.get("predicted_score"), 0.0)
        after = _score_from_vec(_vec7(r.get("risk_probabilities_after_feedback")))
        expected_reduction += max(0.0, before - after)

    predicted_paths.sort(key=lambda x: x["risk_score"], reverse=True)
    real_paths.sort(key=lambda x: x["risk_score"], reverse=True)

    return {
        "config": {
            "inspect_time": inspect_dt.isoformat(sep=" "),
            "forecast_hours": int(forecast_hours),
            "inspect_budget": int(inspect_budget),
            "edge_inspect_ratio": round(float(edge_inspect_ratio), 6),
            "explore_weight": round(float(explore_weight), 6),
            "feedback_strength": round(float(feedback_strength), 6),
            "seed": int(seed),
        },
        "prediction_before": {
            "node_count": int(pre["node_count"]),
            "edge_count": int(pre["edge_count"]),
            "nodes_top": pre["nodes_top"][:100],
            "edges_top": pre["edges_top"][:80],
        },
        "inspection_strategy": {
            "selected_count": int(len(selected_all)),
            "node_selected": int(len(selected_nodes)),
            "edge_selected": int(len(selected_edges)),
            "expected_risk_reduction_proxy": round(expected_reduction, 6),
            "items": selected_all[:200],
        },
        "feedback": {
            "positive_found": int(pos_found),
            "hit_rate": round(hit_rate, 6),
            "items": feedback_rows[:200],
        },
        "optimization": {
            "before": eval_before,
            "after": eval_after,
            "gain_pp": {
                "node_precision_pp": round((eval_after["node"]["precision_at_k"] - eval_before["node"]["precision_at_k"]) * 100.0, 4),
                "node_recall_pp": round((eval_after["node"]["recall_at_k"] - eval_before["node"]["recall_at_k"]) * 100.0, 4),
                "edge_precision_pp": round((eval_after["edge"]["precision_at_k"] - eval_before["edge"]["precision_at_k"]) * 100.0, 4),
                "edge_recall_pp": round((eval_after["edge"]["recall_at_k"] - eval_before["edge"]["recall_at_k"]) * 100.0, 4),
            },
        },
        "propagation": {
            "seed_nodes": sorted(seed_nodes),
            "frames": frames,
            "predicted_paths_top": predicted_paths[:80],
            "real_paths_top": real_paths[:80],
        },
        "post_feedback": {
            "nodes_top": node_post_rows[:100],
            "edges_top": edge_post_rows[:80],
            "risk_tensor": {
                "node": node_post_rows[:200],
                "edge": edge_post_rows[:120],
            },
        },
        "recommendations": [
            "优先抽检高目标函数值对象（风险高、单位成本低、且不确定性适中偏高）。",
            "将抽检阳性样本作为强反馈回写，下一轮重新计算优先级与传播起点。",
            "传播链路同时展示预测路径与未来真实路径，用于检验链接预测与传播机制偏差。",
            "对微生物风险单独监控（更高传播系数），其余六类共享统一扩散框架。",
        ],
    }
