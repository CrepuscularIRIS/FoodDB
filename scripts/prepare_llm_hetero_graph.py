#!/usr/bin/env python3
"""
Prepare heterogeneous graph artifacts for ModeA without model training.

Inputs:
- dataset_3_18.zip (or extracted folder)

Outputs:
- graph_llm_ready.json
- node_risk_summary.csv
- edge_risk_summary.csv

This script standardizes the raw dataset into a single graph object and
computes rule/statistics-based node risk priors for immediate LLM usage.
"""

from __future__ import annotations

import argparse
import json
import math
import tempfile
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

RISK_TYPES = [
    "non_food_additives",
    "pesticide_vet_residue",
    "food_additive_excess",
    "microbial_contamination",
    "heavy_metal",
    "physical_damage",
    "other_contaminants",
]

# GB 2760-2024 dairy product category mapping per processor brand
# Keys are substrings of processor names (乳制品加工厂 nodes)
PROCESSOR_PRODUCT_MAP: list[tuple[str, str]] = [
    ("萨普托", "cheese"),          # 01.06 干酪
    ("菲仕兰辉山", "UHT"),         # 01.01.02 灭菌乳 + 乳粉
    ("蒙牛", "yogurt"),            # 01.02.01 发酵乳 / UHT
    ("纽仕兰", "pasteurized"),     # 01.01.01 巴氏杀菌乳
    ("光明", "pasteurized"),       # 01.01.01/02/03 液体乳系列
]
_DEFAULT_PRODUCT_TAG = "UHT"       # 01.01.02 灭菌乳 as fallback


def _resolve_processor_tag(processor_name: str) -> str:
    for keyword, tag in PROCESSOR_PRODUCT_MAP:
        if keyword in processor_name:
            return tag
    return _DEFAULT_PRODUCT_TAG


def _build_node_product_tags(edges_df: "pd.DataFrame") -> dict[str, str]:
    """Derive product_tag for every node based on which processor handles its batches."""
    # batch_id → product_tag via processor lookup
    proc_rows = edges_df[edges_df["dst_type"] == "乳制品加工厂"][["batch_id", "dst_name"]].drop_duplicates("batch_id")
    batch_tag: dict[int, str] = {
        int(row["batch_id"]): _resolve_processor_tag(str(row["dst_name"]))
        for _, row in proc_rows.iterrows()
    }

    # node_name → most-frequent product_tag across all its batches
    from collections import Counter, defaultdict
    node_tags: defaultdict[str, Counter] = defaultdict(Counter)
    for _, row in edges_df[["batch_id", "src_name", "dst_name"]].iterrows():
        bid = int(row["batch_id"])
        tag = batch_tag.get(bid, _DEFAULT_PRODUCT_TAG)
        if pd.notna(row["src_name"]):
            node_tags[str(row["src_name"])][tag] += 1
        if pd.notna(row["dst_name"]):
            node_tags[str(row["dst_name"])][tag] += 1

    return {name: counter.most_common(1)[0][0] for name, counter in node_tags.items()}


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        if isinstance(value, str) and not value.strip():
            return None
        val = float(value)
        if math.isnan(val):
            return None
        return val
    except Exception:
        return None


def _risk_level_from_quantiles(score: float, q1: float, q2: float) -> str:
    if score >= q2:
        return "high"
    if score >= q1:
        return "medium"
    return "low"


def _load_dataset(input_path: Path) -> Path:
    if input_path.is_dir():
        return input_path

    if input_path.suffix.lower() != ".zip":
        raise ValueError(f"Unsupported input path: {input_path}")

    tmp_dir = Path(tempfile.mkdtemp(prefix="llm_hetero_graph_"))
    with ZipFile(input_path, "r") as zf:
        zf.extractall(tmp_dir)

    # Common layout: <tmp>/dataset_3_18/*
    nested = list(tmp_dir.glob("*/graph_edges_sorted_with_logistics_scale.csv"))
    if nested:
        return nested[0].parent

    if (tmp_dir / "graph_edges_sorted_with_logistics_scale.csv").exists():
        return tmp_dir

    raise FileNotFoundError("Cannot locate graph_edges_sorted_with_logistics_scale.csv in extracted files")


def prepare_graph(data_dir: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    nodes_df = pd.read_csv(data_dir / "enterprise_node.csv")
    edges_df = pd.read_csv(data_dir / "graph_edges_sorted_with_logistics_scale.csv")
    edge_labels = np.load(data_dir / "edge_labels_sorted.npy")  # (N, 7)
    node_labels = np.load(data_dir / "node_labels_sorted.npy")  # (N, 2, 7)

    if len(edges_df) != edge_labels.shape[0] or len(edges_df) != node_labels.shape[0]:
        raise ValueError(
            f"Length mismatch: edges={len(edges_df)} edge_labels={edge_labels.shape[0]} node_labels={node_labels.shape[0]}"
        )

    # --- Pre-compute product_tag per node from processor→GB-category mapping ---
    node_product_tags = _build_node_product_tags(edges_df)

    # --- Build node registry ---
    node_info = {}
    for _, row in nodes_df.iterrows():
        name = str(row.get("名称", "")).strip()
        if not name:
            continue
        node_info[name] = {
            "node_name": name,
            "node_type": str(row.get("节点类型", "未知")),
            "longitude": _safe_float(row.get("经度")),
            "latitude": _safe_float(row.get("纬度")),
            "enterprise_scale": str(row.get("企业规模", "未知")),
            "region": "上海",  # dataset scope
            "district": None,
            "product_tag": node_product_tags.get(name, "dairy_general"),
        }

    # include nodes appearing only in edges
    for col, type_col in (("src_name", "src_type"), ("dst_name", "dst_type")):
        for _, row in edges_df[[col, type_col]].dropna().iterrows():
            name = str(row[col]).strip()
            if not name:
                continue
            if name not in node_info:
                node_info[name] = {
                    "node_name": name,
                    "node_type": str(row[type_col]) if pd.notna(row[type_col]) else "未知",
                    "longitude": None,
                    "latitude": None,
                    "enterprise_scale": "未知",
                    "region": "上海",
                    "district": None,
                    "product_tag": node_product_tags.get(name, "dairy_general"),
                }

    node_names = sorted(node_info.keys())
    node_id_map = {name: f"N-{idx + 1:05d}" for idx, name in enumerate(node_names)}

    node_stats = {
        name: {
            "edge_count": 0,
            "risk_sum": np.zeros(7, dtype=np.float64),
        }
        for name in node_names
    }

    edges = []
    for i, row in edges_df.iterrows():
        src = str(row.get("src_name", "")).strip()
        dst = str(row.get("dst_name", "")).strip()
        if not src or not dst or src not in node_id_map or dst not in node_id_map:
            continue

        label_vec = edge_labels[i].astype(int).tolist()
        edge_id = f"E-{i + 1:06d}"

        edge_obj = {
            "edge_id": edge_id,
            "source": node_id_map[src],
            "target": node_id_map[dst],
            "source_name": src,
            "target_name": dst,
            "source_type": str(row.get("src_type", "未知")),
            "target_type": str(row.get("dst_type", "未知")),
            "timestamp": str(row.get("edge_event_time", row.get("timestamp", ""))),
            "transit_hours": _safe_float(row.get("在途小时")),
            "source_stay_hours": _safe_float(row.get("起点停留小时")),
            "target_stay_hours": _safe_float(row.get("终点停留小时")),
            "retail_stay_hours": _safe_float(row.get("零售端停留小时")),
            "logistics_company": str(row.get("物流公司", "")),
            "logistics_scale": str(row.get("物流企业规模", "")),
            "risk_labels": label_vec,
            "risk_positive_count": int(np.sum(edge_labels[i])),
            "edge_type": "flow",
        }
        edges.append(edge_obj)

        node_stats[src]["edge_count"] += 1
        node_stats[dst]["edge_count"] += 1

        # use per-edge node labels if available
        src_label = node_labels[i, 0].astype(np.float64)
        dst_label = node_labels[i, 1].astype(np.float64)
        node_stats[src]["risk_sum"] += src_label
        node_stats[dst]["risk_sum"] += dst_label

    # compute node risk priors
    raw_scores = []
    for name in node_names:
        cnt = max(node_stats[name]["edge_count"], 1)
        risk_vec = node_stats[name]["risk_sum"] / cnt
        # hand-crafted weights to emphasize microbial/heavy-metal/other
        weights = np.array([1.1, 1.2, 1.0, 1.4, 1.3, 0.9, 1.0], dtype=np.float64)
        score = float(np.clip(np.dot(risk_vec, weights) / weights.sum(), 0.0, 1.0))
        node_stats[name]["risk_vec"] = risk_vec
        node_stats[name]["risk_score"] = score
        raw_scores.append(score)

    q1, q2 = np.quantile(raw_scores, [0.6, 0.85]) if raw_scores else (0.33, 0.66)

    nodes = []
    for name in node_names:
        info = node_info[name]
        stats = node_stats[name]
        risk_vec = stats["risk_vec"]
        risk_level = _risk_level_from_quantiles(stats["risk_score"], q1, q2)

        nodes.append(
            {
                "node_id": node_id_map[name],
                "name": name,
                "node_type": info["node_type"],
                "longitude": info["longitude"],
                "latitude": info["latitude"],
                "enterprise_scale": info["enterprise_scale"],
                "region": info["region"],
                "district": info["district"],
                "product_tag": info["product_tag"],
                "observed_edge_count": int(stats["edge_count"]),
                "risk_score": round(float(stats["risk_score"]), 6),
                "risk_level": risk_level,
                "risk_vector": {k: round(float(v), 6) for k, v in zip(RISK_TYPES, risk_vec.tolist())},
            }
        )

    graph = {
        "meta": {
            "source": str(data_dir),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "risk_types": RISK_TYPES,
            "mode": "no_training_llm_ready",
            "notes": [
                "risk_score is rule/statistics-derived prior, not a trained model output",
                "region fixed to 上海 due to dataset scope",
            ],
        },
        "nodes": nodes,
        "edges": edges,
    }

    (output_dir / "graph_llm_ready.json").write_text(
        json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    node_export = pd.DataFrame(
        [
            {
                "node_id": n["node_id"],
                "name": n["name"],
                "node_type": n["node_type"],
                "risk_level": n["risk_level"],
                "risk_score": n["risk_score"],
                "observed_edge_count": n["observed_edge_count"],
            }
            for n in nodes
        ]
    )
    node_export.to_csv(output_dir / "node_risk_summary.csv", index=False, encoding="utf-8")

    edge_export = pd.DataFrame(
        [
            {
                "edge_id": e["edge_id"],
                "source": e["source_name"],
                "target": e["target_name"],
                "timestamp": e["timestamp"],
                "risk_positive_count": e["risk_positive_count"],
            }
            for e in edges
        ]
    )
    edge_export.to_csv(output_dir / "edge_risk_summary.csv", index=False, encoding="utf-8")

    return graph


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare LLM-ready hetero graph without training")
    parser.add_argument(
        "--input",
        required=True,
        help="Path to dataset zip or extracted directory",
    )
    parser.add_argument(
        "--output-dir",
        default="data/llm_graph",
        help="Output directory (default: data/llm_graph)",
    )
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()

    data_dir = _load_dataset(input_path)
    graph = prepare_graph(data_dir, output_dir)

    print("\n[OK] LLM-ready graph generated")
    print(f"  - output: {output_dir}")
    print(f"  - nodes: {graph['meta']['node_count']}")
    print(f"  - edges: {graph['meta']['edge_count']}")


if __name__ == "__main__":
    main()
