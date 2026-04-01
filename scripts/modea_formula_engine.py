"""Mode A formula engine: qualitative -> quantitative scoring (auditable)."""

from __future__ import annotations

import copy
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


RISK_KEYS_DEFAULT = [
    "non_food_additives",
    "pesticide_vet_residue",
    "food_additive_excess",
    "microbial_contamination",
    "heavy_metal",
    "biotoxin",
    "other_contaminants",
]


def _clip01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        s = str(v).strip()
        if not s:
            return default
        return float(s)
    except Exception:
        return default


def _quantile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    arr = sorted(float(v) for v in values)
    if len(arr) == 1:
        return arr[0]
    q = _clip01(q)
    idx = int(round((len(arr) - 1) * q))
    return arr[max(0, min(len(arr) - 1, idx))]


def _winsor(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _robust_norm(v: float, values: List[float], ql: float = 0.05, qh: float = 0.95) -> float:
    if not values:
        return _clip01(v)
    lo = _quantile(values, ql)
    hi = _quantile(values, qh)
    vv = _winsor(v, lo, hi)
    den = (hi - lo) if hi > lo else 1e-6
    return _clip01((vv - lo) / den)


def _parse_ts(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    s = str(ts).strip().replace("/", "-")
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        try:
            dt = datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _stage_weight(src_type: str, dst_type: str) -> float:
    pair = (str(src_type or ""), str(dst_type or ""))
    mapping = {
        ("原奶供应商", "乳制品加工厂"): 1.00,
        ("乳制品加工厂", "冷链仓储中心"): 0.92,
        ("冷链仓储中心", "零售终端"): 0.88,
    }
    return mapping.get(pair, 0.85)


def _node_group_key(node: Dict[str, Any]) -> str:
    return f"{node.get('node_type','未知')}|{node.get('enterprise_scale','未知')}"


def _scale_cost(scale: str) -> float:
    s = str(scale or "")
    if "大" in s:
        return 1.6
    if "中" in s:
        return 1.25
    if "小" in s:
        return 1.0
    return 1.15


def _type_cost_mult(node_type: str) -> float:
    t = str(node_type or "")
    if "加工" in t:
        return 1.35
    if "仓储" in t:
        return 1.20
    if "物流" in t:
        return 1.15
    if "零售" in t:
        return 0.95
    return 1.00


def _missing_rate(node: Dict[str, Any]) -> float:
    checks = [
        node.get("longitude"),
        node.get("latitude"),
        node.get("node_type"),
        node.get("enterprise_scale"),
        node.get("region"),
    ]
    profile = node.get("profile_features", {}) or {}
    profile_keys = [
        "历史抽检次数",
        "历史不合格次数",
        "冷链断链次数",
        "平均在途小时",
        "合作物流企业数",
        "品类覆盖数",
        "近30天舆情指数",
        "设备老化指数",
        "合规证照完备度",
        "企业画像风险指数",
    ]
    checks.extend(profile.get(k) for k in profile_keys)
    missing = 0
    for v in checks:
        if v is None:
            missing += 1
            continue
        s = str(v).strip().lower()
        if not s or s in {"nan", "none", "null", "unknown", "未知"}:
            missing += 1
    return round(_clip01(missing / max(len(checks), 1)), 6)


def _profile_risk(node: Dict[str, Any], risk_idx_fallback: float = 0.2) -> float:
    profile = node.get("profile_features", {}) or {}
    direct = profile.get("企业画像风险指数")
    if direct is not None:
        return _clip01(_to_float(direct, risk_idx_fallback))

    inspections = _to_float(profile.get("历史抽检次数"), 0.0)
    fails = _to_float(profile.get("历史不合格次数"), 0.0)
    cold_breaks = _to_float(profile.get("冷链断链次数"), 0.0)
    opinion = _to_float(profile.get("近30天舆情指数"), 0.0) / 100.0
    aging = _to_float(profile.get("设备老化指数"), 0.0) / 100.0
    license_ok = _to_float(profile.get("合规证照完备度"), 80.0) / 100.0

    fail_rate = fails / max(inspections, 1.0)
    score = (
        0.35 * _clip01(fail_rate)
        + 0.25 * _clip01(cold_breaks / 20.0)
        + 0.15 * _clip01(opinion)
        + 0.15 * _clip01(aging)
        + 0.10 * _clip01(1.0 - license_ok)
    )
    return round(_clip01(score), 6)


def _source_quality(source_mix: Dict[str, float]) -> float:
    q = {
        "public_record": 1.00,
        "rule_inferred": 0.75,
        "prior_assumed": 0.55,
        "simulated": 0.35,
    }
    return _clip01(sum(float(source_mix.get(k, 0.0)) * q[k] for k in q))


def _norm_weights(vals: Dict[str, float]) -> Dict[str, float]:
    s = sum(max(0.0, float(v)) for v in vals.values())
    if s <= 0:
        k = len(vals)
        return {kk: round(1.0 / max(k, 1), 6) for kk in vals}
    return {kk: round(max(0.0, float(v)) / s, 6) for kk, v in vals.items()}


def _safe_std(vals: List[float]) -> float:
    if not vals:
        return 0.0
    m = sum(vals) / len(vals)
    return math.sqrt(sum((x - m) ** 2 for x in vals) / len(vals))


def compute_formula_scores(
    view: Dict[str, Any],
    query_context: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Compute node/edge formula scores on a view subgraph and return enriched view."""

    p = {
        "gamma_cat": 0.30,
        "a_n": 0.45,
        "a_x": 0.25,
        "a_p": 0.20,
        "a_h": 0.10,
        "b_s": 0.40,
        "b_f": 0.25,
        "b_d": 0.20,
        "b_c": 0.15,
        "c_m": 0.35,
        "c_w": 0.20,
        "c_v": 0.25,
        "c_r": 0.20,
        "lambda": 0.75,
        "eta_0": 0.50,
        "eta_1": 0.50,
        "xi_0": 0.30,
        "xi_1": 0.70,
        "b_top": 0.05,
        "delta_t": 0.20,
        "half_life_days": 180.0,
        "edge_a_n": 0.65,
        "edge_a_t": 0.25,
        "edge_a_h": 0.10,
        "edge_theta_1": 0.60,
        "edge_theta_2": 0.30,
        "edge_theta_3": 0.10,
        "budget_rho": 0.20,
        "budget_tau": 0.10,
        "piece_theta_a": 0.85,
        "piece_theta_b": 0.80,
        "kqv_mu": 0.30,
        "kqv_tau": 0.60,
    }
    if params:
        p.update(params)

    out = copy.deepcopy(view)
    nodes = out.get("nodes", [])
    edges = out.get("edges", [])
    if not nodes:
        out.setdefault("meta", {})["formula"] = {
            "formula_version": "modea_formula_v1",
            "params": p,
            "query_context": query_context or {},
        }
        return out

    risk_keys = out.get("meta", {}).get("risk_dimensions") or RISK_KEYS_DEFAULT
    risk_dim = min(7, len(risk_keys))

    node_by_id: Dict[str, Dict[str, Any]] = {n.get("node_id"): n for n in nodes if n.get("node_id")}
    edge_by_id: Dict[str, Dict[str, Any]] = {e.get("edge_id"): e for e in edges if e.get("edge_id")}

    incident_edges: Dict[str, List[str]] = defaultdict(list)
    neighbors: Dict[str, List[str]] = defaultdict(list)
    for e in edges:
        s = e.get("source")
        t = e.get("target")
        eid = e.get("edge_id")
        if not s or not t or not eid:
            continue
        incident_edges[s].append(eid)
        incident_edges[t].append(eid)
        neighbors[s].append(t)
        neighbors[t].append(s)

    # Time normalization pools for edges
    trans_vals = [_to_float(e.get("transit_hours"), 0.0) for e in edges]
    org_vals = [_to_float(e.get("origin_stay_hours"), 0.0) for e in edges]
    tar_vals = [_to_float(e.get("target_stay_hours"), 0.0) for e in edges]
    ret_vals = [_to_float(e.get("retail_stay_hours"), 0.0) for e in edges]

    edge_age_days: Dict[str, float] = {}
    ts_list = [_parse_ts(str(e.get("timestamp") or "")) for e in edges]
    ts_non_null = [x for x in ts_list if x is not None]
    ref_ts = max(ts_non_null) if ts_non_null else None

    edge_time_fragility: Dict[str, float] = {}
    edge_rule_hit_ratio: Dict[str, float] = {}
    edge_risk_vec: Dict[str, List[float]] = {}

    for e in edges:
        eid = e.get("edge_id")
        if not eid:
            continue
        t_frag = (
            0.40 * _robust_norm(_to_float(e.get("transit_hours"), 0.0), trans_vals)
            + 0.20 * _robust_norm(_to_float(e.get("origin_stay_hours"), 0.0), org_vals)
            + 0.20 * _robust_norm(_to_float(e.get("target_stay_hours"), 0.0), tar_vals)
            + 0.20 * _robust_norm(_to_float(e.get("retail_stay_hours"), 0.0), ret_vals)
        )
        edge_time_fragility[eid] = round(_clip01(t_frag), 6)

        flags = e.get("top5_flags", {}) or {}
        hit_ratio = sum(1.0 for rk in risk_keys[:risk_dim] if bool(flags.get(rk))) / max(risk_dim, 1)
        edge_rule_hit_ratio[eid] = round(_clip01(hit_ratio), 6)

        vec = e.get("view_risk_probabilities") or e.get("risk_probabilities") or []
        vec = [
            _clip01(_to_float(vec[i], 0.0)) if i < len(vec) else 0.0
            for i in range(risk_dim)
        ]
        edge_risk_vec[eid] = vec

        if ref_ts is not None:
            dt = _parse_ts(str(e.get("timestamp") or ""))
            if dt is None:
                edge_age_days[eid] = p["half_life_days"]
            else:
                edge_age_days[eid] = max(0.0, (ref_ts - dt).total_seconds() / 86400.0)
        else:
            edge_age_days[eid] = p["half_life_days"]

    # Node group stats
    node_missing: Dict[str, float] = {}
    node_evidence_m: Dict[str, float] = {}
    node_profile_risk: Dict[str, float] = {}
    node_group: Dict[str, str] = {}

    for n in nodes:
        nid = n.get("node_id")
        if not nid:
            continue
        node_group[nid] = _node_group_key(n)
        node_missing[nid] = _missing_rate(n)
        inspection = _to_float((n.get("profile_features") or {}).get("历史抽检次数"), 0.0)
        node_evidence_m[nid] = inspection + len(incident_edges.get(nid, []))
        node_profile_risk[nid] = _profile_risk(n)

    group_missing_vals: Dict[str, List[float]] = defaultdict(list)
    group_evidence_vals: Dict[str, List[float]] = defaultdict(list)
    for nid, g in node_group.items():
        group_missing_vals[g].append(node_missing.get(nid, 0.0))
        group_evidence_vals[g].append(node_evidence_m.get(nid, 0.0))

    group_missing_med = {g: _quantile(vs, 0.5) for g, vs in group_missing_vals.items()}
    group_evidence_p95 = {g: max(1.0, _quantile(vs, 0.95)) for g, vs in group_evidence_vals.items()}

    # Pass1: base risk and credibility
    node_intrinsic: Dict[str, List[float]] = {}
    node_exposure: Dict[str, List[float]] = {}
    node_rule: Dict[str, List[float]] = {}
    node_risk_vec: Dict[str, List[float]] = {}
    node_risk_proxy: Dict[str, float] = {}

    node_source_quality: Dict[str, float] = {}
    node_freshness: Dict[str, float] = {}
    node_evidence_density: Dict[str, float] = {}
    node_consistency: Dict[str, float] = {}
    node_credibility: Dict[str, float] = {}
    node_source_mix: Dict[str, Dict[str, float]] = {}

    deg = {nid: len(neighbors.get(nid, [])) for nid in node_by_id}

    for nid, n in node_by_id.items():
        base_vec = n.get("view_risk_probabilities") or n.get("risk_probabilities") or []
        n_vec = [
            _clip01(_to_float(base_vec[i], 0.0)) if i < len(base_vec) else 0.0
            for i in range(risk_dim)
        ]

        # one-hop exposure
        x_vec = [0.0] * risk_dim
        den_vec = [0.0] * risk_dim
        for eid in incident_edges.get(nid, []):
            e = edge_by_id.get(eid)
            if not e:
                continue
            other = e.get("target") if e.get("source") == nid else e.get("source")
            other_deg = max(1, deg.get(other, 1))
            eta = _stage_weight(e.get("source_type", ""), e.get("target_type", ""))
            eta *= (1.0 + p["delta_t"] * edge_time_fragility.get(eid, 0.0))
            eta /= (1.0 + math.log1p(other_deg))
            vec_e = edge_risk_vec.get(eid, [0.0] * risk_dim)
            for i in range(risk_dim):
                x_vec[i] += eta * vec_e[i]
                den_vec[i] += eta
        x_vec = [
            _clip01(x_vec[i] / den_vec[i]) if den_vec[i] > 0 else 0.0
            for i in range(risk_dim)
        ]

        flags_node = n.get("top5_flags", {}) or {}
        h_vec = []
        for i in range(risk_dim):
            rk = risk_keys[i]
            hit = bool(flags_node.get(rk, False))
            for eid in incident_edges.get(nid, []):
                ef = (edge_by_id.get(eid, {}) or {}).get("top5_flags", {}) or {}
                if bool(ef.get(rk, False)):
                    hit = True
                    break
            h_vec.append(1.0 if hit else 0.0)

        p_i = node_profile_risk.get(nid, 0.2)
        risk_vec = [
            _clip01(p["a_n"] * n_vec[i] + p["a_x"] * x_vec[i] + p["a_p"] * p_i + p["a_h"] * h_vec[i])
            for i in range(risk_dim)
        ]
        risk_proxy = sum(risk_vec) / max(risk_dim, 1)

        node_intrinsic[nid] = n_vec
        node_exposure[nid] = x_vec
        node_rule[nid] = h_vec
        node_risk_vec[nid] = risk_vec
        node_risk_proxy[nid] = round(risk_proxy, 6)

        # credibility
        miss = node_missing.get(nid, 0.0)
        inspect = _to_float((n.get("profile_features") or {}).get("历史抽检次数"), 0.0)
        inspect_norm = _clip01(inspect / 80.0)
        rule_signal = sum(h_vec) / max(risk_dim, 1)

        mix = _norm_weights(
            {
                "public_record": 0.20 + 0.60 * inspect_norm,
                "rule_inferred": 0.20 + 0.50 * rule_signal,
                "prior_assumed": 0.20 + 0.40 * miss,
                "simulated": 0.15 + 0.55 * miss * (1.0 - inspect_norm),
            }
        )
        s_i = _source_quality(mix)

        ages = [edge_age_days.get(eid, p["half_life_days"]) for eid in incident_edges.get(nid, [])]
        if ages:
            f_i = sum(math.exp(-a / p["half_life_days"]) for a in ages) / len(ages)
        else:
            f_i = 0.5

        g = node_group.get(nid, "unknown")
        p95_m = group_evidence_p95.get(g, 1.0)
        d_i = _clip01(math.log1p(node_evidence_m.get(nid, 0.0)) / max(math.log1p(p95_m), 1e-6))
        c_i = _clip01(1.0 - miss * 0.8)

        cred = _clip01(
            p["b_s"] * s_i + p["b_f"] * f_i + p["b_d"] * d_i + p["b_c"] * c_i
        )

        node_source_mix[nid] = mix
        node_source_quality[nid] = round(s_i, 6)
        node_freshness[nid] = round(_clip01(f_i), 6)
        node_evidence_density[nid] = round(d_i, 6)
        node_consistency[nid] = round(c_i, 6)
        node_credibility[nid] = round(cred, 6)

    # Pass2: uncertainty and priority (base -> piecewise -> KQV overlay)
    pattern_counter = Counter()
    node_pattern: Dict[str, str] = {}
    node_neighbor_std: Dict[str, float] = {}

    for nid, n in node_by_id.items():
        top_bucket = min(3, int(_to_float(n.get("top5_count"), 0.0)))
        pattern = f"{n.get('node_type','未知')}|{n.get('enterprise_scale','未知')}|{top_bucket}"
        node_pattern[nid] = pattern
        pattern_counter[pattern] += 1

        neigh_scores = [node_risk_proxy.get(nb, 0.0) for nb in neighbors.get(nid, []) if nb in node_risk_proxy]
        node_neighbor_std[nid] = _safe_std(neigh_scores)

    group_neighbor_std_vals: Dict[str, List[float]] = defaultdict(list)
    for nid, g in node_group.items():
        group_neighbor_std_vals[g].append(node_neighbor_std.get(nid, 0.0))
    group_neighbor_q95 = {g: max(1e-6, _quantile(vs, 0.95)) for g, vs in group_neighbor_std_vals.items()}

    node_uncertainty: Dict[str, float] = {}
    node_priority: Dict[str, float] = {}
    node_priority_base: Dict[str, float] = {}
    node_priority_piece: Dict[str, float] = {}
    node_priority_kqv_delta: Dict[str, float] = {}
    node_exploit: Dict[str, float] = {}
    node_explore: Dict[str, float] = {}
    node_top5_bonus: Dict[str, float] = {}
    node_u_comp: Dict[str, Tuple[float, float, float, float]] = {}

    n_total = max(len(node_by_id), 2)
    for nid, n in node_by_id.items():
        g = node_group.get(nid, "unknown")
        miss = node_missing.get(nid, 0.0)
        med_m = group_missing_med.get(g, miss)

        u_miss = _clip01(max(0.0, miss - med_m) / max(1.0 - med_m, 1e-6))
        u_weak = _clip01(1.0 - node_source_quality.get(nid, 0.0))
        u_var = _clip01(node_neighbor_std.get(nid, 0.0) / group_neighbor_q95.get(g, 1e-6))

        freq = pattern_counter.get(node_pattern.get(nid, ""), 1) / n_total
        u_rare = _clip01(-math.log(freq + 1e-9) / max(math.log(n_total), 1e-6))

        unc = _clip01(
            p["c_m"] * u_miss + p["c_w"] * u_weak + p["c_v"] * u_var + p["c_r"] * u_rare
        )

        risk_proxy = node_risk_proxy.get(nid, 0.0)
        cred = node_credibility.get(nid, 0.0)
        top5_bonus = min(1.0, _to_float(n.get("top5_count"), 0.0) / 3.0)

        exploit = risk_proxy * (p["eta_0"] + p["eta_1"] * cred)
        explore = unc * (p["xi_0"] + p["xi_1"] * risk_proxy)
        priority = _clip01(p["lambda"] * exploit + (1.0 - p["lambda"]) * explore + p["b_top"] * top5_bonus)

        node_uncertainty[nid] = round(unc, 6)
        node_exploit[nid] = round(_clip01(exploit), 6)
        node_explore[nid] = round(_clip01(explore), 6)
        node_priority[nid] = round(priority, 6)
        node_priority_base[nid] = round(priority, 6)
        node_top5_bonus[nid] = round(top5_bonus, 6)
        node_u_comp[nid] = (u_miss, u_weak, u_var, u_rare)

    # Piecewise override: strong rule hit lift
    fail_rates: Dict[str, float] = {}
    fail_rate_vals: List[float] = []
    fail_cnt_vals: List[float] = []
    cold_break_vals: List[float] = []
    transit_vals: List[float] = []
    microbial_vals: List[float] = []
    microbial_idx = 3
    for i, rk in enumerate(risk_keys[:risk_dim]):
        if "micro" in rk.lower() or "微生物" in rk:
            microbial_idx = i
            break

    for nid, n in node_by_id.items():
        pf = n.get("profile_features", {}) or {}
        inspections = _to_float(pf.get("历史抽检次数"), 0.0)
        fails = _to_float(pf.get("历史不合格次数"), 0.0)
        cold_breaks = _to_float(pf.get("冷链断链次数"), 0.0)
        avg_transit = _to_float(pf.get("平均在途小时"), 0.0)
        fail_rate = fails / max(inspections, 1.0)
        fail_rates[nid] = _clip01(fail_rate)
        fail_rate_vals.append(_clip01(fail_rate))
        fail_cnt_vals.append(max(0.0, fails))
        cold_break_vals.append(max(0.0, cold_breaks))
        transit_vals.append(max(0.0, avg_transit))
        microbial_vals.append(node_intrinsic.get(nid, [0.0] * risk_dim)[microbial_idx])

    fail_rate_p95 = _quantile(fail_rate_vals, 0.95) if fail_rate_vals else 1.0
    microbial_p90 = _quantile(microbial_vals, 0.90) if microbial_vals else 1.0

    theta_a = _clip01(_to_float(p.get("piece_theta_a"), 0.85))
    theta_b = _clip01(_to_float(p.get("piece_theta_b"), 0.80))
    for nid, n in node_by_id.items():
        base = node_priority_base.get(nid, 0.0)
        top5_cnt = _to_float(n.get("top5_count"), 0.0)
        fail_rate = fail_rates.get(nid, 0.0)
        micro = node_intrinsic.get(nid, [0.0] * risk_dim)[microbial_idx]
        override_a = theta_a if top5_cnt >= 2.0 else 0.0
        override_b = theta_b if (fail_rate > fail_rate_p95 and micro > microbial_p90) else 0.0
        node_priority_piece[nid] = round(max(base, override_a, override_b), 6)

    # Static KQV overlay
    q_ctx = query_context or {}
    kqv_keys = ["rule", "exposure", "history", "coldchain", "profile", "dataquality"]
    base_beta = {
        "rule": 0.15,
        "exposure": 0.25,
        "history": 0.15,
        "coldchain": 0.10,
        "profile": 0.20,
        "dataquality": 0.15,
    }
    stage_text = str(q_ctx.get("stage") or "").lower()
    node_text = str(q_ctx.get("node_type") or "").lower()
    product_text = str(q_ctx.get("product_type") or "").lower()
    risk_text = str(q_ctx.get("risk_dimension") or "").lower()

    g_map: Dict[str, float] = {}
    for k in kqv_keys:
        g = base_beta[k]
        if ("micro" in risk_text or "微生物" in risk_text) and k in {"rule", "coldchain"}:
            g += 0.20
        if ("cold" in stage_text or "冷链" in stage_text) and k == "coldchain":
            g += 0.35
        if ("加工" in node_text or "processor" in node_text) and k in {"rule", "exposure"}:
            g += 0.10
        if ("物流" in node_text or "仓储" in node_text) and k == "coldchain":
            g += 0.12
        if ("巴氏" in product_text or "pasteurized" in product_text) and k in {"coldchain", "rule"}:
            g += 0.10
        if ("婴" in product_text or "infant" in product_text) and k == "rule":
            g += 0.15
        g_map[k] = g

    tau = max(1e-3, _to_float(p.get("kqv_tau"), 0.60))
    exp_map = {k: math.exp(g / tau) for k, g in g_map.items()}
    exp_sum = sum(exp_map.values()) or 1.0
    alpha = {k: exp_map[k] / exp_sum for k in kqv_keys}
    mu = _clip01(_to_float(p.get("kqv_mu"), 0.30))

    for nid, n in node_by_id.items():
        pf = n.get("profile_features", {}) or {}
        fail_rate_norm = _robust_norm(fail_rates.get(nid, 0.0), fail_rate_vals)
        fail_cnt_norm = _robust_norm(_to_float(pf.get("历史不合格次数"), 0.0), fail_cnt_vals)
        hist_event_score = _clip01(0.70 * fail_rate_norm + 0.30 * fail_cnt_norm)

        cold_break_norm = _robust_norm(_to_float(pf.get("冷链断链次数"), 0.0), cold_break_vals)
        transit_norm = _robust_norm(_to_float(pf.get("平均在途小时"), 0.0), transit_vals)
        coldchain_fragility = _clip01(0.60 * cold_break_norm + 0.40 * transit_norm)

        v_map = {
            "rule": _clip01(p["a_h"] * (sum(node_rule.get(nid, [0.0] * risk_dim)) / max(risk_dim, 1))),
            "exposure": _clip01(p["a_x"] * (sum(node_exposure.get(nid, [0.0] * risk_dim)) / max(risk_dim, 1))),
            "history": hist_event_score,
            "coldchain": coldchain_fragility,
            "profile": _clip01(node_profile_risk.get(nid, 0.0)),
            "dataquality": _clip01(node_explore.get(nid, 0.0)),
        }
        delta = _clip01(sum(alpha[k] * v_map[k] for k in kqv_keys))
        base_piece = node_priority_piece.get(nid, node_priority_base.get(nid, 0.0))
        enhanced = _clip01((1.0 - mu) * base_piece + mu * delta)

        node_priority_kqv_delta[nid] = round(delta, 6)
        node_priority[nid] = round(enhanced, 6)

        u_miss, u_weak, u_var, u_rare = node_u_comp.get(nid, (0.0, 0.0, 0.0, 0.0))
        n["risk_proxy"] = node_risk_proxy[nid]
        n["credibility_proxy"] = node_credibility[nid]
        n["uncertainty_proxy"] = node_uncertainty[nid]
        n["priority_base_score"] = node_priority_base[nid]
        n["priority_piecewise_score"] = node_priority_piece[nid]
        n["priority_score"] = node_priority[nid]
        n["exploit_score"] = node_exploit[nid]
        n["explore_score"] = node_explore[nid]
        n["budget_cost"] = round(_scale_cost(n.get("enterprise_scale")) * _type_cost_mult(n.get("node_type")), 6)
        n["source_mix"] = node_source_mix.get(nid, {})
        n["kqv_overlay"] = {
            "enabled": True,
            "base": node_priority_piece[nid],
            "delta": round(delta, 6),
            "enhanced": node_priority[nid],
            "mu": round(mu, 6),
            "tau": round(tau, 6),
            "weights": {k: round(alpha[k], 6) for k in kqv_keys},
            "values": {k: round(v_map[k], 6) for k in kqv_keys},
        }
        n["formula_contrib"] = {
            "risk": {
                "intrinsic": round(sum(node_intrinsic.get(nid, [0.0] * risk_dim)) / max(risk_dim, 1), 6),
                "exposure": round(sum(node_exposure.get(nid, [0.0] * risk_dim)) / max(risk_dim, 1), 6),
                "profile": round(node_profile_risk.get(nid, 0.0), 6),
                "rule_hit": round(sum(node_rule.get(nid, [0.0] * risk_dim)) / max(risk_dim, 1), 6),
            },
            "credibility": {
                "source_quality": node_source_quality.get(nid, 0.0),
                "freshness": node_freshness.get(nid, 0.0),
                "evidence_density": node_evidence_density.get(nid, 0.0),
                "consistency": node_consistency.get(nid, 0.0),
            },
            "uncertainty": {
                "unexpected_missing": round(u_miss, 6),
                "source_weakness": round(u_weak, 6),
                "neighbor_variance": round(u_var, 6),
                "rarity": round(u_rare, 6),
            },
            "priority": {
                "base": node_priority_base[nid],
                "piecewise": node_priority_piece[nid],
                "kqv_delta": round(delta, 6),
                "enhanced": node_priority[nid],
            },
        }

    # Edge scores
    for e in edges:
        eid = e.get("edge_id")
        if not eid:
            continue
        vec = edge_risk_vec.get(eid, [0.0] * risk_dim)
        hit_flags = e.get("top5_flags", {}) or {}
        edge_vec_score = []
        for i in range(risk_dim):
            rk = risk_keys[i]
            hit = 1.0 if bool(hit_flags.get(rk, False)) else 0.0
            s = _clip01(p["edge_a_n"] * vec[i] + p["edge_a_t"] * edge_time_fragility.get(eid, 0.0) + p["edge_a_h"] * hit)
            edge_vec_score.append(s)
        edge_risk = sum(edge_vec_score) / max(risk_dim, 1)

        src = e.get("source")
        dst = e.get("target")
        src_pri = node_priority.get(src, 0.0)
        dst_pri = node_priority.get(dst, 0.0)
        src_unc = node_uncertainty.get(src, 0.0)
        dst_unc = node_uncertainty.get(dst, 0.0)
        edge_unc = _clip01(0.5 * (src_unc + dst_unc) + 0.5 * (1.0 - edge_rule_hit_ratio.get(eid, 0.0)))

        edge_pri = _clip01(
            p["edge_theta_1"] * edge_risk
            + p["edge_theta_2"] * 0.5 * (src_pri + dst_pri)
            + p["edge_theta_3"] * edge_unc
        )

        e["time_fragility"] = round(edge_time_fragility.get(eid, 0.0), 6)
        e["edge_risk_proxy"] = round(edge_risk, 6)
        e["edge_uncertainty"] = round(edge_unc, 6)
        e["edge_priority"] = round(edge_pri, 6)

    out.setdefault("meta", {})["formula"] = {
        "formula_version": "modea_formula_v1",
        "parameter_set_id": "default_v1",
        "data_version": out.get("meta", {}).get("version", "modelA_v2"),
        "query_context": query_context or {},
        "piecewise_enabled": True,
        "kqv_enabled": True,
        "params": p,
    }
    return out


def rank_nodes_by_priority(
    scored_view: Dict[str, Any],
    node_type: Optional[str] = None,
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    nodes = scored_view.get("nodes", [])
    out = []
    for n in nodes:
        if node_type and n.get("node_type") != node_type:
            continue
        out.append(n)
    out.sort(key=lambda x: float(x.get("priority_score", 0.0)), reverse=True)
    return out[: max(1, int(top_n))]


def build_budget_plan(
    scored_view: Dict[str, Any],
    budget: float,
    max_enterprises: int = 20,
    node_type: Optional[str] = None,
    rho: float = 0.20,
    tau: float = 0.10,
) -> Dict[str, Any]:
    nodes = scored_view.get("nodes", [])
    edges = scored_view.get("edges", [])

    candidates = [n for n in nodes if (not node_type or n.get("node_type") == node_type)]
    candidates.sort(key=lambda x: float(x.get("priority_score", 0.0)), reverse=True)

    incident: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in edges:
        incident[e.get("source")].append(e)
        incident[e.get("target")].append(e)

    uncovered_nodes = {n.get("node_id") for n in candidates if n.get("node_id")}
    uncovered_edges = {e.get("edge_id") for e in edges if e.get("edge_id")}

    selected: List[Dict[str, Any]] = []
    selected_ids = set()
    left = float(budget)

    def coverage_gain(node: Dict[str, Any]) -> float:
        nid = node.get("node_id")
        node_gain = 1.0 if nid in uncovered_nodes else 0.0
        inc = incident.get(nid, [])
        if not inc:
            return _clip01(node_gain)
        total = sum(float(x.get("edge_risk_proxy", 0.0)) for x in inc)
        uncovered = sum(float(x.get("edge_risk_proxy", 0.0)) for x in inc if x.get("edge_id") in uncovered_edges)
        edge_gain = 0.0 if total <= 0 else uncovered / total
        return _clip01(0.7 * node_gain + 0.3 * edge_gain)

    while len(selected) < max_enterprises:
        feasible = []
        for n in candidates:
            nid = n.get("node_id")
            if nid in selected_ids:
                continue
            cost = _to_float(n.get("budget_cost"), 1.0)
            if cost > left:
                continue
            gain = coverage_gain(n)
            utility = (
                _to_float(n.get("priority_score"), 0.0) * (1.0 + rho * gain)
                + tau * _to_float(n.get("uncertainty_proxy"), 0.0)
            ) / max(cost, 1e-6)
            feasible.append((utility, gain, cost, n))

        if not feasible:
            break

        feasible.sort(key=lambda x: x[0], reverse=True)
        utility, gain, cost, best = feasible[0]
        nid = best.get("node_id")

        item = copy.deepcopy(best)
        item["budget_utility"] = round(float(utility), 6)
        item["coverage_gain"] = round(float(gain), 6)
        item["sample_cost"] = round(float(cost), 6)
        selected.append(item)
        selected_ids.add(nid)
        left -= cost

        if nid in uncovered_nodes:
            uncovered_nodes.remove(nid)
        for e in incident.get(nid, []):
            eid = e.get("edge_id")
            if eid in uncovered_edges:
                uncovered_edges.remove(eid)

    return {
        "budget": float(budget),
        "budget_used": round(float(budget) - left, 6),
        "budget_left": round(left, 6),
        "selected_count": len(selected),
        "expected_risk_covered": round(sum(_to_float(x.get("priority_score"), 0.0) for x in selected), 6),
        "items": selected,
    }
