#!/usr/bin/env python3
"""Finalize risk_taxonomy.yaml from vnext entries with MiniMax-assisted cleanup."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = ROOT / "knowledge"
INPUT_PATH = KNOWLEDGE_DIR / "derived" / "risk_taxonomy_vnext" / "risk_taxonomy_vnext.jsonl"
OUTPUT_PATH = KNOWLEDGE_DIR / "configs" / "risk_taxonomy.yaml"
MANIFEST_PATH = KNOWLEDGE_DIR / "derived" / "risk_taxonomy_vnext" / "risk_taxonomy_final_manifest.json"
INTERMEDIATE_JSONL_PATH = KNOWLEDGE_DIR / "derived" / "risk_taxonomy_vnext" / "risk_taxonomy_final_intermediate.jsonl"

MAX_ALIAS = 6
MAX_PRODUCTS = 8
MAX_SYMPTOMS = 8
MAX_GROUPS = 6


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dumps(data) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_json_dumps(row) + "\n")


def _read_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip("'").strip('"')
    return env


def _extract_json_text(text: str) -> str:
    text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()
    brace_match = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    if brace_match:
        return brace_match.group(1).strip()
    return text


def _clean_list(items: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for item in items:
        value = " ".join(str(item or "").split()).strip(" ,;")
        if not value:
            continue
        if len(value) > 80:
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(value)
        if len(cleaned) >= limit:
            break
    return cleaned


def _fallback_products(entry: dict[str, Any]) -> list[str]:
    return _clean_list(entry.get("applicable_products", []), MAX_PRODUCTS)


def _fallback_symptoms(entry: dict[str, Any]) -> list[str]:
    return _clean_list(entry.get("typical_symptoms", []), MAX_SYMPTOMS)


def _fallback_groups(entry: dict[str, Any]) -> list[str]:
    return _clean_list(entry.get("vulnerable_groups", []), MAX_GROUPS)


class MiniMaxFinalizer:
    def __init__(self, model: str = "MiniMax-M2.5", timeout: int = 90) -> None:
        env = _read_env(ROOT / ".env")
        self.api_key = (
            os.environ.get("MINIMAX_API_KEY")
            or os.environ.get("minimaxi-api-key")
            or env.get("MINIMAX_API_KEY")
            or env.get("minimaxi-api-key")
        )
        self.base_url = (
            os.environ.get("MINIMAX_BASE_URL")
            or env.get("url")
            or "https://api.minimax.chat/v1"
        ).rstrip("/")
        self.model = model
        self.timeout = timeout
        self.min_interval_seconds = 1.2
        self.last_request_ts = 0.0
        if not self.api_key:
            raise RuntimeError("Missing MiniMax API key")

    def refine_batch(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        compact_entries = [
            {
                "id": entry.get("id"),
                "name": entry.get("name"),
                "category": entry.get("category"),
                "aliases": entry.get("aliases", [])[:4],
                "description": entry.get("description", ""),
                "applicable_products": entry.get("applicable_products", [])[:8],
                "typical_symptoms": entry.get("typical_symptoms", [])[:8],
                "vulnerable_groups": entry.get("vulnerable_groups", [])[:6],
                "evidence_strength": entry.get("evidence_strength", "medium"),
                "source_count": entry.get("source_count", 0),
                "evidence_count": entry.get("evidence_count", 0),
                "notes": entry.get("notes", ""),
            }
            for entry in entries
        ]
        prompt = """
请把下面一批食品风险 taxonomy 条目压缩成更低熵、更适合正式配置文件的版本。
只输出 JSON 数组，不要解释。

数组中的每个元素必须包含：
- id
- name
- aliases
- description
- applicable_products
- typical_symptoms
- vulnerable_groups
- evidence_strength
- notes

约束：
- aliases / applicable_products / typical_symptoms / vulnerable_groups 都输出数组
- aliases 最多 6 个
- applicable_products 最多 8 个，必须是短词或短短语，不能保留召回原文长句
- typical_symptoms 最多 8 个
- vulnerable_groups 最多 6 个
- evidence_strength 仅可用：high, medium, low
- description 控制在 1 句
- notes 控制在 1 句
- 必须逐条返回所有输入 id，不能漏项

entries:
""".strip() + "\n" + json.dumps(compact_entries, ensure_ascii=False)

        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 1400,
            "messages": [
                {
                    "role": "system",
                    "content": "你是食品风险配置清洗助手。只输出 JSON 对象，不要输出思考过程。",
                },
                {"role": "user", "content": prompt},
            ],
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(6):
            wait = self.min_interval_seconds - (time.time() - self.last_request_ts)
            if wait > 0:
                time.sleep(wait)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    body = json.loads(response.read().decode("utf-8"))
                self.last_request_ts = time.time()
                content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
                parsed = json.loads(_extract_json_text(content))
                return parsed if isinstance(parsed, list) else []
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code == 429:
                    time.sleep(2.5 * (attempt + 1))
                    continue
                break
            except Exception as exc:
                last_error = exc
                time.sleep(1.5 * (attempt + 1))
        return [{"error": str(last_error)}] if last_error else []


class RiskTaxonomyConfigFinalizer:
    def __init__(self, input_path: Path = INPUT_PATH, output_path: Path = OUTPUT_PATH) -> None:
        self.input_path = input_path
        self.output_path = output_path
        self.finalizer = MiniMaxFinalizer()

    def build(self) -> dict[str, Any]:
        entries = _read_jsonl(self.input_path)
        finalized: list[dict[str, Any]] = []
        batch_size = 3

        for batch_start in range(0, len(entries), batch_size):
            batch = entries[batch_start:batch_start + batch_size]
            batch_payload = [
                {
                    "id": entry["id"],
                    "name": entry["name"],
                    "category": entry["category"],
                    "aliases": entry.get("aliases", []),
                    "description": entry.get("description", ""),
                    "applicable_products": entry.get("applicable_products", []),
                    "typical_symptoms": entry.get("typical_symptoms", []),
                    "vulnerable_groups": entry.get("vulnerable_groups", []),
                    "evidence_strength": entry.get("evidence_strength", "medium"),
                    "authority_sources": entry.get("authority_sources", []),
                    "evidence_types": entry.get("evidence_types", []),
                    "source_count": entry.get("source_count", 0),
                    "evidence_count": entry.get("evidence_count", 0),
                    "notes": entry.get("notes", ""),
                }
                for entry in batch
            ]
            refined_rows = self.finalizer.refine_batch(batch_payload)
            refined_by_id = {
                row.get("id"): row
                for row in refined_rows
                if isinstance(row, dict) and row.get("id")
            }

            for offset, entry in enumerate(batch, 1):
                refined = refined_by_id.get(entry["id"], {})
                final_entry = {
                    "id": entry["id"],
                    "name": refined.get("name") or entry["name"],
                    "category": entry["category"],
                    "aliases": _clean_list(refined.get("aliases", []) + entry.get("aliases", []), MAX_ALIAS),
                    "description": refined.get("description") or entry.get("description", ""),
                    "applicable_products": _clean_list(
                        refined.get("applicable_products", []) + _fallback_products(entry),
                        MAX_PRODUCTS,
                    ),
                    "typical_symptoms": _clean_list(
                        refined.get("typical_symptoms", []) + _fallback_symptoms(entry),
                        MAX_SYMPTOMS,
                    ),
                    "vulnerable_groups": _clean_list(
                        refined.get("vulnerable_groups", []) + _fallback_groups(entry),
                        MAX_GROUPS,
                    ),
                    "evidence_strength": refined.get("evidence_strength") or entry.get("evidence_strength", "medium"),
                    "authority_sources": _clean_list(entry.get("authority_sources", []), 10),
                    "evidence_types": _clean_list(entry.get("evidence_types", []), 10),
                    "source_count": entry.get("source_count", 0),
                    "evidence_count": entry.get("evidence_count", 0),
                    "sample_source_ids": entry.get("sample_source_ids", [])[:10],
                    "notes": refined.get("notes") or entry.get("notes", ""),
                }
                finalized.append(final_entry)
                print(_json_dumps({"done": batch_start + offset, "total": len(entries), "id": entry["id"]}), flush=True)
            _write_jsonl(INTERMEDIATE_JSONL_PATH, finalized)

        payload = {
            "version": "vnext-formalized",
            "generated_at": datetime.now(UTC).isoformat(),
            "source": str(self.input_path),
            "risk_factors": finalized,
        }
        self.output_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")

        manifest = {
            "generated_at": datetime.now(UTC).isoformat(),
            "input_path": str(self.input_path),
            "output_path": str(self.output_path),
            "entries": len(finalized),
            "model": self.finalizer.model,
        }
        _write_json(MANIFEST_PATH, manifest)
        return manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Finalize formal risk_taxonomy.yaml with MiniMax sequential cleanup.")
    parser.add_argument("--input-path", default=str(INPUT_PATH), help="Input jsonl path from vnext taxonomy.")
    parser.add_argument("--output-path", default=str(OUTPUT_PATH), help="Final config YAML output path.")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    manifest = RiskTaxonomyConfigFinalizer(
        input_path=Path(args.input_path),
        output_path=Path(args.output_path),
    ).build()
    print(_json_dumps(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
