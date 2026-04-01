"""ModelA v2 graph builder (pure Python CSV implementation)."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zipfile import ZipFile

RISK_KEYS = [
    "non_food_additives",
    "pesticide_vet_residue",
    "food_additive_excess",
    "microbial_contamination",
    "heavy_metal",
    "biotoxin",
    "other_contaminants",
]
RISK_KEYS_ZH = ["非食用添加剂", "农药兽药残留", "食品添加剂", "微生物", "重金属污染物", "生物毒素", "其他污染物"]

SHELF_LIFE_HOURS = {
    "生乳": 72,
    "风味发酵乳": 21 * 24,
    "巴氏杀菌乳": 7 * 24,
    "稀奶油": 15 * 24,
    "奶油": 30 * 24,
    "再制干酪": 90 * 24,
    "干酪": 90 * 24,
    "调制乳": 180 * 24,
    "淡炼乳": 180 * 24,
    "加糖炼乳": 180 * 24,
    "灭菌乳": 180 * 24,
    "调制乳粉": 540 * 24,
    "全脂乳粉": 540 * 24,
}
LOGISTICS_SCALE_RISK = {"大型企业": 0.08, "中型企业": 0.18, "小型企业": 0.30, "无法判断": 0.24, "需要补充信息": 0.26}
PRODUCT_SENSITIVITY = {
    "生乳": [0.14, 0.24, 0.07, 0.16, 0.12, 0.22, 0.05],
    "风味发酵乳": [0.10, 0.06, 0.12, 0.28, 0.08, 0.04, 0.10],
    "巴氏杀菌乳": [0.08, 0.07, 0.10, 0.34, 0.07, 0.04, 0.08],
    "稀奶油": [0.12, 0.06, 0.16, 0.16, 0.08, 0.04, 0.12],
    "奶油": [0.10, 0.06, 0.16, 0.14, 0.08, 0.04, 0.12],
    "再制干酪": [0.10, 0.04, 0.18, 0.18, 0.06, 0.03, 0.10],
    "干酪": [0.10, 0.04, 0.12, 0.20, 0.06, 0.03, 0.10],
    "调制乳": [0.12, 0.05, 0.18, 0.12, 0.06, 0.03, 0.12],
    "淡炼乳": [0.12, 0.05, 0.18, 0.10, 0.06, 0.03, 0.12],
    "加糖炼乳": [0.14, 0.05, 0.22, 0.10, 0.06, 0.03, 0.12],
    "灭菌乳": [0.10, 0.05, 0.10, 0.08, 0.06, 0.03, 0.10],
    "调制乳粉": [0.08, 0.08, 0.10, 0.08, 0.12, 0.05, 0.10],
    "全脂乳粉": [0.08, 0.08, 0.08, 0.08, 0.12, 0.05, 0.10],
}
STAGE_FACTOR = {("原奶供应商", "乳制品加工厂"): 0.28, ("乳制品加工厂", "冷链仓储中心"): 0.20, ("冷链仓储中心", "零售终端"): 0.24}


def _stable_rand_01(*parts: str) -> float:
    digest = hashlib.md5("||".join(parts).encode("utf-8")).hexdigest()  # nosec B303
    return int(digest[:8], 16) / 0xFFFFFFFF


def _clip01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        s = "" if v is None else str(v).strip()
        if not s or s.lower() == "nan":
            return default
        return float(s)
    except Exception:
        return default


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(float(str(v).strip()))
    except Exception:
        return default


def _to_risk_level(score: float) -> str:
    if score >= 0.66:
        return "high"
    if score >= 0.38:
        return "medium"
    return "low"


def _quantile(values: List[float], q: float) -> float:
    if not values:
        return 1.0
    arr = sorted(float(v) for v in values)
    if len(arr) == 1:
        return arr[0]
    q = _clip01(q)
    idx = int(round((len(arr) - 1) * q))
    return arr[max(0, min(len(arr) - 1, idx))]


def _compute_top_ratio_thresholds(vectors: List[List[float]], top_ratio: float = 0.05) -> List[float]:
    if not vectors:
        return [1.0] * 7
    top_ratio = min(0.5, max(0.001, float(top_ratio)))
    q = 1.0 - top_ratio
    thresholds: List[float] = []
    for i in range(7):
        values = [float(v[i]) for v in vectors if len(v) > i]
        thresholds.append(round(_quantile(values, q), 6))
    return thresholds


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _resolve_data_dir(input_path: Path) -> Path:
    if input_path.is_dir():
        return input_path
    if input_path.suffix.lower() != ".zip":
        raise ValueError(f"Unsupported input: {input_path}")
    extract_dir = input_path.parent / "_tmp_extract_modela_v2"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(input_path, "r") as zf:
        zf.extractall(extract_dir)
    candidates = list(extract_dir.rglob("dataset_3_24"))
    if candidates:
        return candidates[0]
    if (extract_dir / "enterprise_node.csv").exists():
        return extract_dir
    raise FileNotFoundError(f"Cannot locate dataset_3_24 under {extract_dir}")


def _edge_risk_probs(row: Dict[str, Any], src_profile: float, dst_profile: float) -> List[float]:
    product = str(row.get("dairy_product_type", "")).strip()
    src_type = str(row.get("src_type", "")).strip()
    dst_type = str(row.get("dst_type", "")).strip()
    scale = str(row.get("物流企业规模", "")).strip()
    transit_h = _to_float(row.get("在途小时"), 0.0)
    retail_h = _to_float(row.get("零售端停留小时"), 0.0)
    shelf_h = SHELF_LIFE_HOURS.get(product, 15 * 24)
    freshness = transit_h / max(24.0, shelf_h)
    retail_pressure = retail_h / max(24.0, shelf_h)
    scale_risk = LOGISTICS_SCALE_RISK.get(scale, 0.20)
    stage = STAGE_FACTOR.get((src_type, dst_type), 0.18)
    product_bias = PRODUCT_SENSITIVITY.get(product, [0.10] * 7)

    base = 0.30 * src_profile + 0.30 * dst_profile + 0.16 * min(1.0, freshness) + 0.12 * min(1.0, retail_pressure) + 0.12 * scale_risk + 0.08 * stage
    edge_key = f"{row.get('src_name','')}->{row.get('dst_name','')}|{row.get('batch_id','')}|{product}"

    out: List[float] = []
    for i in range(7):
        noise = (_stable_rand_01(edge_key, str(i)) - 0.5) * 0.12
        out.append(round(_clip01(_sigmoid((base + product_bias[i] + noise - 0.35) * 3.1)), 6))
    return out


def _aggregate_node_probs(prob_vectors: List[List[float]]) -> List[float]:
    if not prob_vectors:
        return [0.0] * 7
    out = []
    for i in range(7):
        prod = 1.0
        for vec in prob_vectors:
            prod *= 1.0 - _clip01(float(vec[i]))
        out.append(round(1.0 - prod, 6))
    return out


def build_modela_v2_graph(input_path: Path, output_dir: Path) -> Dict[str, Any]:
    data_dir = _resolve_data_dir(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    nodes_rows = _read_csv(data_dir / "enterprise_node.csv")
    edge_rows = _read_csv(data_dir / "graph_edges_reformatted_with_product.csv")

    usage = defaultdict(int)
    logistic_counter = defaultdict(set)
    avg_transit = defaultdict(list)
    cat_counter = defaultdict(set)
    for r in edge_rows:
        src = str(r.get("src_name", "")).strip()
        dst = str(r.get("dst_name", "")).strip()
        company = str(r.get("物流公司", "")).strip()
        product = str(r.get("dairy_product_type", "")).strip()
        transit = _to_float(r.get("在途小时"), 0.0)
        for n in [src, dst]:
            if not n:
                continue
            usage[n] += 1
            if company:
                logistic_counter[n].add(company)
            avg_transit[n].append(transit)
            if product:
                cat_counter[n].add(product)

    node_by_name: Dict[str, Dict[str, Any]] = {}
    profile_map: Dict[str, float] = {}
    for r in nodes_rows:
        name = str(r.get("名称", "")).strip()
        if not name:
            continue
        node_type = str(r.get("节点类型", "未知")).strip()
        scale = str(r.get("企业规模", "未知")).strip()
        avg_t = sum(avg_transit.get(name, [])) / max(len(avg_transit.get(name, [])), 1)

        risk_seed = _stable_rand_01(name, node_type, scale, "risk_seed")
        inspection_count = int(4 + usage.get(name, 0) * 0.02 + 60 * _stable_rand_01(name, "inspection"))
        fail_count = int(max(0, round(inspection_count * (0.02 + 0.20 * risk_seed))))
        cold_break_count = int((avg_t / 18.0) + 6.0 * _stable_rand_01(name, "cold"))
        media_index = round(10 + 70 * _stable_rand_01(name, "media"), 2)
        equip_index = round(5 + 85 * _stable_rand_01(name, "equip"), 2)
        compliance = round(40 + 60 * (1 - risk_seed), 2)
        profile_index = round(_clip01(0.35 * (fail_count / max(inspection_count, 1)) + 0.25 * min(1.0, cold_break_count / 20.0) + 0.20 * min(1.0, media_index / 100.0) + 0.20 * (1 - compliance / 100.0)), 6)

        node_by_name[name] = {
            "node_id": f"N-{(len(node_by_name)+1):05d}",
            "name": name,
            "node_type": node_type,
            "enterprise_scale": scale,
            "longitude": _to_float(r.get("经度"), 0.0) if str(r.get("经度", "")).strip() else None,
            "latitude": _to_float(r.get("纬度"), 0.0) if str(r.get("纬度", "")).strip() else None,
            "region": "上海",
            "profile_features": {
                "历史抽检次数": inspection_count,
                "历史不合格次数": fail_count,
                "冷链断链次数": cold_break_count,
                "平均在途小时": round(avg_t, 3),
                "合作物流企业数": len(logistic_counter.get(name, set())),
                "品类覆盖数": len(cat_counter.get(name, set())),
                "近30天舆情指数": media_index,
                "设备老化指数": equip_index,
                "合规证照完备度": compliance,
                "企业画像风险指数": profile_index,
            },
        }
        profile_map[name] = profile_index

    for r in edge_rows:
        for col, type_col in [("src_name", "src_type"), ("dst_name", "dst_type")]:
            name = str(r.get(col, "")).strip()
            if not name or name in node_by_name:
                continue
            node_by_name[name] = {
                "node_id": f"N-{(len(node_by_name)+1):05d}",
                "name": name,
                "node_type": str(r.get(type_col, "未知")).strip() or "未知",
                "enterprise_scale": "未知",
                "longitude": None,
                "latitude": None,
                "region": "上海",
                "profile_features": {
                    "历史抽检次数": 5,
                    "历史不合格次数": 1,
                    "冷链断链次数": 0,
                    "平均在途小时": 0.0,
                    "合作物流企业数": 0,
                    "品类覆盖数": 1,
                    "近30天舆情指数": 20.0,
                    "设备老化指数": 20.0,
                    "合规证照完备度": 80.0,
                    "企业画像风险指数": 0.2,
                },
            }
            profile_map[name] = 0.2

    categories = sorted({str(r.get("dairy_product_type", "")).strip() for r in edge_rows if str(r.get("dairy_product_type", "")).strip()})

    node_cat_probs: Dict[str, Dict[str, List[List[float]]]] = defaultdict(lambda: defaultdict(list))
    edge_records: List[Dict[str, Any]] = []
    for idx, r in enumerate(edge_rows):
        src = str(r.get("src_name", "")).strip()
        dst = str(r.get("dst_name", "")).strip()
        product = str(r.get("dairy_product_type", "")).strip()
        if not src or not dst or not product or src not in node_by_name or dst not in node_by_name:
            continue
        probs = _edge_risk_probs(r, profile_map.get(src, 0.2), profile_map.get(dst, 0.2))
        node_cat_probs[src][product].append(probs)
        node_cat_probs[dst][product].append(probs)
        edge_records.append({
            "edge_id": f"E-{idx+1:06d}",
            "batch_id": _to_int(r.get("batch_id"), -1),
            "source": node_by_name[src]["node_id"],
            "target": node_by_name[dst]["node_id"],
            "source_name": src,
            "target_name": dst,
            "source_type": str(r.get("src_type", "")),
            "target_type": str(r.get("dst_type", "")),
            "timestamp": str(r.get("edge_event_time") or r.get("timestamp") or ""),
            "dairy_product_type": product,
            "transit_hours": _to_float(r.get("在途小时"), 0.0),
            "origin_stay_hours": _to_float(r.get("起点停留小时"), 0.0),
            "target_stay_hours": _to_float(r.get("终点停留小时"), 0.0),
            "retail_stay_hours": _to_float(r.get("零售端停留小时"), 0.0),
            "logistics_company": str(r.get("物流公司", "")),
            "logistics_scale": str(r.get("物流企业规模", "")),
            "risk_probabilities": probs,
            "risk_vector": dict(zip(RISK_KEYS, probs)),
            "risk_vector_zh": dict(zip(RISK_KEYS_ZH, probs)),
        })

    node_records: List[Dict[str, Any]] = []
    for name, base in node_by_name.items():
        cat_vectors = {c: _aggregate_node_probs(node_cat_probs[name].get(c, [])) for c in categories}
        overall = _aggregate_node_probs([v for v in cat_vectors.values() if sum(v) > 0])
        score = max(overall) if overall else 0.0
        node_records.append({
            **base,
            "risk_score": round(float(score), 6),
            "risk_level": _to_risk_level(float(score)),
            "risk_probabilities": overall,
            "risk_vector": dict(zip(RISK_KEYS, overall)),
            "risk_vector_zh": dict(zip(RISK_KEYS_ZH, overall)),
            "category_risk_probabilities": {c: v for c, v in cat_vectors.items() if sum(v) > 0},
        })

    node_thresholds = _compute_top_ratio_thresholds(
        [n.get("risk_probabilities", [0.0] * 7) for n in node_records],
        top_ratio=0.05,
    )
    edge_thresholds = _compute_top_ratio_thresholds(
        [e.get("risk_probabilities", [0.0] * 7) for e in edge_records],
        top_ratio=0.05,
    )
    for n in node_records:
        vec = n.get("risk_probabilities", [0.0] * 7)
        flags = {RISK_KEYS[i]: bool(float(vec[i]) >= float(node_thresholds[i])) for i in range(7)}
        flags_zh = {RISK_KEYS_ZH[i]: flags[RISK_KEYS[i]] for i in range(7)}
        n["top5_flags"] = flags
        n["top5_flags_zh"] = flags_zh
        n["top5_count"] = int(sum(1 for v in flags.values() if v))
        n["is_top5_any"] = bool(n["top5_count"] > 0)
    for e in edge_records:
        vec = e.get("risk_probabilities", [0.0] * 7)
        flags = {RISK_KEYS[i]: bool(float(vec[i]) >= float(edge_thresholds[i])) for i in range(7)}
        flags_zh = {RISK_KEYS_ZH[i]: flags[RISK_KEYS[i]] for i in range(7)}
        e["top5_flags"] = flags
        e["top5_flags_zh"] = flags_zh
        e["top5_count"] = int(sum(1 for v in flags.values() if v))
        e["is_top5_any"] = bool(e["top5_count"] > 0)

    graph = {
        "meta": {
            "version": "modelA_v2",
            "source_dataset": str(data_dir),
            "node_count": len(node_records),
            "edge_count": len(edge_records),
            "risk_dimensions": RISK_KEYS,
            "risk_dimensions_zh": RISK_KEYS_ZH,
            "product_categories": categories,
            "top5_thresholds": {
                "node": dict(zip(RISK_KEYS, node_thresholds)),
                "edge": dict(zip(RISK_KEYS, edge_thresholds)),
                "node_zh": dict(zip(RISK_KEYS_ZH, node_thresholds)),
                "edge_zh": dict(zip(RISK_KEYS_ZH, edge_thresholds)),
                "ratio": 0.05,
            },
            "notes": [
                "Node features are auto-generated enterprise profile features for cold-start modeling.",
                "Risk probabilities are deterministic synthetic outputs built from graph structure + profile features.",
                "Node aggregated risk uses noisy-or over category risk contributions.",
            ],
        },
        "nodes": node_records,
        "edges": edge_records,
    }

    feature_fields = ["名称", "经度", "纬度", "节点类型", "企业规模", "历史抽检次数", "历史不合格次数", "冷链断链次数", "平均在途小时", "合作物流企业数", "品类覆盖数", "近30天舆情指数", "设备老化指数", "合规证照完备度", "企业画像风险指数"]
    with (output_dir / "enterprise_node_features_generated.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=feature_fields)
        w.writeheader()
        for n in node_records:
            p = n["profile_features"]
            w.writerow({
                "名称": n["name"],
                "经度": "" if n["longitude"] is None else n["longitude"],
                "纬度": "" if n["latitude"] is None else n["latitude"],
                "节点类型": n["node_type"],
                "企业规模": n["enterprise_scale"],
                "历史抽检次数": p["历史抽检次数"],
                "历史不合格次数": p["历史不合格次数"],
                "冷链断链次数": p["冷链断链次数"],
                "平均在途小时": p["平均在途小时"],
                "合作物流企业数": p["合作物流企业数"],
                "品类覆盖数": p["品类覆盖数"],
                "近30天舆情指数": p["近30天舆情指数"],
                "设备老化指数": p["设备老化指数"],
                "合规证照完备度": p["合规证照完备度"],
                "企业画像风险指数": p["企业画像风险指数"],
            })

    with (output_dir / "edge_risk_probabilities.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["edge_id", "dairy_product_type", "source_name", "target_name"] + RISK_KEYS_ZH + [f"{x}_top5" for x in RISK_KEYS_ZH]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for e in edge_records:
            row = {"edge_id": e["edge_id"], "dairy_product_type": e["dairy_product_type"], "source_name": e["source_name"], "target_name": e["target_name"]}
            row.update(e["risk_vector_zh"])
            for x in RISK_KEYS_ZH:
                row[f"{x}_top5"] = int(bool(e.get("top5_flags_zh", {}).get(x, False)))
            w.writerow(row)

    with (output_dir / "node_risk_probabilities.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["node_id", "name", "node_type", "risk_level", "risk_score"] + RISK_KEYS_ZH + [f"{x}_top5" for x in RISK_KEYS_ZH]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for n in node_records:
            row = {"node_id": n["node_id"], "name": n["name"], "node_type": n["node_type"], "risk_level": n["risk_level"], "risk_score": n["risk_score"]}
            row.update(n["risk_vector_zh"])
            for x in RISK_KEYS_ZH:
                row[f"{x}_top5"] = int(bool(n.get("top5_flags_zh", {}).get(x, False)))
            w.writerow(row)

    (output_dir / "modela_v2_graph.json").write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    return graph


def extract_category_subgraph(
    graph: Dict[str, Any],
    product_type: str,
    k_hop: int = 0,
    seed_node: Optional[str] = None,
    max_nodes: int = 500,
    max_edges: int = 2000,
) -> Dict[str, Any]:
    node_by_id = {n["node_id"]: n for n in graph.get("nodes", [])}
    node_by_name = {n["name"]: n for n in graph.get("nodes", [])}
    edges = [e for e in graph.get("edges", []) if e.get("dairy_product_type") == product_type]

    selected_edge_ids = set()
    selected_node_ids = set()
    if seed_node:
        seed_id = node_by_name.get(seed_node, {}).get("node_id") if seed_node in node_by_name else seed_node
        if seed_id not in node_by_id:
            raise ValueError(f"seed_node 不存在: {seed_node}")
        adjacency: Dict[str, set] = defaultdict(set)
        edge_bucket: Dict[Tuple[str, str], List[int]] = defaultdict(list)
        for i, e in enumerate(edges):
            s, t = e["source"], e["target"]
            adjacency[s].add(t)
            adjacency[t].add(s)
            edge_bucket[(s, t)].append(i)
            edge_bucket[(t, s)].append(i)
        frontier = [(seed_id, 0)]
        visited = {seed_id}
        selected_node_ids.add(seed_id)
        while frontier:
            cur, depth = frontier.pop(0)
            if depth >= max(1, k_hop):
                continue
            for nxt in adjacency.get(cur, set()):
                if nxt not in visited:
                    visited.add(nxt)
                    selected_node_ids.add(nxt)
                    frontier.append((nxt, depth + 1))
                    for idx in edge_bucket.get((cur, nxt), []):
                        selected_edge_ids.add(idx)
    else:
        for i, e in enumerate(edges):
            selected_edge_ids.add(i)
            selected_node_ids.add(e["source"])
            selected_node_ids.add(e["target"])

    out_edges = [edges[i] for i in sorted(selected_edge_ids)][:max_edges]
    keep_nodes = set()
    for e in out_edges:
        keep_nodes.add(e["source"])
        keep_nodes.add(e["target"])
    for nid in selected_node_ids:
        if len(keep_nodes) >= max_nodes:
            break
        keep_nodes.add(nid)

    out_nodes = [node_by_id[nid] for nid in keep_nodes if nid in node_by_id]
    out_nodes_view = []
    for n in out_nodes:
        cat_vec = n.get("category_risk_probabilities", {}).get(product_type, [0.0] * 7)
        score = max(cat_vec) if cat_vec else 0.0
        out_nodes_view.append({
            **n,
            "category": product_type,
            "category_risk_probabilities": cat_vec,
            "category_risk_vector": dict(zip(RISK_KEYS, cat_vec)),
            "category_risk_vector_zh": dict(zip(RISK_KEYS_ZH, cat_vec)),
            "category_risk_score": round(float(score), 6),
            "category_risk_level": _to_risk_level(float(score)),
        })

    node_thresholds = _compute_top_ratio_thresholds(
        [n.get("category_risk_probabilities", [0.0] * 7) for n in out_nodes_view],
        top_ratio=0.05,
    )
    edge_thresholds = _compute_top_ratio_thresholds(
        [e.get("risk_probabilities", [0.0] * 7) for e in out_edges],
        top_ratio=0.05,
    )
    for n in out_nodes_view:
        vec = n.get("category_risk_probabilities", [0.0] * 7)
        flags = {RISK_KEYS[i]: bool(float(vec[i]) >= float(node_thresholds[i])) for i in range(7)}
        n["category_top5_flags"] = flags
        n["category_top5_flags_zh"] = {RISK_KEYS_ZH[i]: flags[RISK_KEYS[i]] for i in range(7)}
        n["category_top5_count"] = int(sum(1 for v in flags.values() if v))
        n["is_category_top5_any"] = bool(n["category_top5_count"] > 0)

    out_edges_view: List[Dict[str, Any]] = []
    for e in out_edges:
        vec = e.get("risk_probabilities", [0.0] * 7)
        flags = {RISK_KEYS[i]: bool(float(vec[i]) >= float(edge_thresholds[i])) for i in range(7)}
        out_edges_view.append(
            {
                **e,
                "category_top5_flags": flags,
                "category_top5_flags_zh": {RISK_KEYS_ZH[i]: flags[RISK_KEYS[i]] for i in range(7)},
                "category_top5_count": int(sum(1 for v in flags.values() if v)),
                "is_category_top5_any": bool(sum(1 for v in flags.values() if v) > 0),
            }
        )

    return {
        "meta": {
            "product_type": product_type,
            "k_hop": k_hop,
            "seed_node": seed_node,
            "node_count": len(out_nodes_view),
            "edge_count": len(out_edges_view),
            "risk_dimensions": RISK_KEYS,
            "risk_dimensions_zh": RISK_KEYS_ZH,
            "top5_thresholds": {
                "node": dict(zip(RISK_KEYS, node_thresholds)),
                "edge": dict(zip(RISK_KEYS, edge_thresholds)),
                "ratio": 0.05,
            },
        },
        "nodes": out_nodes_view,
        "edges": out_edges_view,
    }
