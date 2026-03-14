#!/usr/bin/env python3
"""Rebuild methods layer corpus from GB agent structured outputs.

Primary source:
- knowledge/derived/gb_agent_minimax/gb_standard_metadata.jsonl
- knowledge/derived/gb_agent_minimax/gb_standard_chunks.jsonl

Output:
- knowledge/corpora/rag_corpus_methods_standards_v2.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DERIVED_DIR = ROOT / "knowledge" / "derived" / "gb_agent_minimax"
CORPUS_DIR = ROOT / "knowledge" / "corpora"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _guess_method_type(title: str) -> str:
    if "微生物学检验" in title:
        return "微生物学检验"
    if "测定" in title or "检验" in title:
        return "理化测定方法"
    return "食品安全检测方法"


def _keywords_from_text(text: str) -> list[str]:
    terms = [
        "液相色谱",
        "气相色谱",
        "质谱",
        "原子吸收",
        "荧光",
        "分光光度",
        "菌落总数",
        "大肠菌群",
        "沙门氏菌",
        "李斯特",
        "铅",
        "镉",
        "汞",
        "黄曲霉毒素",
        "维生素",
    ]
    return [term for term in terms if term in text]


def build_methods_corpus(
    metadata_rows: list[dict[str, Any]],
    chunk_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    method_meta_by_id: dict[str, dict[str, Any]] = {}
    for row in metadata_rows:
        if row.get("knowledge_type") == "method_standard":
            standard_id = str(row.get("standard_id", "")).strip()
            if standard_id:
                method_meta_by_id[standard_id] = row

    chunks_by_standard: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in chunk_rows:
        standard_id = str(row.get("standard_id", "")).strip()
        if standard_id in method_meta_by_id:
            chunks_by_standard[standard_id].append(row)

    corpus: list[dict[str, Any]] = []
    for standard_id, chunks in sorted(chunks_by_standard.items()):
        meta = method_meta_by_id[standard_id]
        title = str(meta.get("title", "")).strip()
        source_file = str(meta.get("source_file", "")).strip()
        product_domain = str(meta.get("product_domain", "")).strip()
        method_type = _guess_method_type(title)

        chunks.sort(key=lambda x: (int(x.get("section_index", 0)), int(x.get("chunk_index", 0))))
        for idx, chunk in enumerate(chunks):
            raw_text = str(chunk.get("chunk_text", "")).strip()
            text = _normalize_text(raw_text)
            if len(text) < 80:
                continue

            source_url = str(chunk.get("source_url") or f"file://standard/txt/{source_file}")
            row_id = hashlib.sha1(f"{standard_id}:{idx}:{text[:160]}".encode("utf-8")).hexdigest()[:12]

            corpus.append(
                {
                    "id": f"method_v2_{row_id}",
                    "source": standard_id,
                    "method_type": method_type,
                    "source_url": source_url,
                    "chunk_index": idx,
                    "chunk_text": text,
                    "entities": [],
                    "keywords": _keywords_from_text(text),
                    "metadata": {
                        "domain": "food_safety_methods",
                        "source_type": "gb_agent_minimax",
                        "standard_id": standard_id,
                        "title": title,
                        "product_domain": product_domain,
                        "source_file": source_file,
                    },
                }
            )
    return corpus


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild methods layer corpus from gb_agent_minimax outputs.")
    parser.add_argument(
        "--output",
        default=str(CORPUS_DIR / "rag_corpus_methods_standards_v2.jsonl"),
        help="Output JSONL path.",
    )
    parser.add_argument(
        "--manifest-output",
        default=str(ROOT / "knowledge" / "derived" / "methods_layer_rebuild_manifest.json"),
        help="Manifest JSON path.",
    )
    args = parser.parse_args()

    metadata_path = DERIVED_DIR / "gb_standard_metadata.jsonl"
    chunks_path = DERIVED_DIR / "gb_standard_chunks.jsonl"
    output_path = Path(args.output)
    manifest_output = Path(args.manifest_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.parent.mkdir(parents=True, exist_ok=True)

    metadata_rows = _read_jsonl(metadata_path)
    chunk_rows = _read_jsonl(chunks_path)
    corpus = build_methods_corpus(metadata_rows, chunk_rows)

    with output_path.open("w", encoding="utf-8") as f:
        for row in corpus:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "output": str(output_path),
        "records": len(corpus),
        "method_standard_count": len({r["source"] for r in corpus}),
        "source_metadata": str(metadata_path),
        "source_chunks": str(chunks_path),
        "status": "completed",
    }
    manifest_output.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
