#!/usr/bin/env python3
"""Build a first-pass risk taxonomy YAML from high-confidence candidates."""

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
INPUT_PATH = (
    KNOWLEDGE_DIR
    / "derived"
    / "risk_taxonomy_candidates_structured"
    / "risk_taxonomy_candidates_structured_high_confidence.jsonl"
)
DEFAULT_OUTPUT_DIR = KNOWLEDGE_DIR / "derived" / "risk_taxonomy_yaml_builder"

CATEGORY_MAP = {
    "microbial": "microbial",
    "chemical": "chemical",
    "toxin": "toxin",
    "residue": "residue",
    "allergen": "allergen",
    "physical": "physical",
    "unknown": "unknown",
}


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dumps(data) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_json_dumps(row) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


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


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "hazard"


def _clean_list(items: list[str], limit: int | None = None) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for item in items:
        value = " ".join(str(item or "").split()).strip(" ,;")
        if not value:
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(value)
        if limit is not None and len(cleaned) >= limit:
            break
    return cleaned


def _dedupe_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in entries:
        key = (entry["category"], entry["name"])
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = dict(entry)
            continue
        existing["aliases"] = _clean_list(existing["aliases"] + entry["aliases"], limit=12)
        existing["applicable_products"] = _clean_list(existing["applicable_products"] + entry["applicable_products"], limit=16)
        existing["typical_symptoms"] = _clean_list(existing["typical_symptoms"] + entry["typical_symptoms"], limit=16)
        existing["vulnerable_groups"] = _clean_list(existing["vulnerable_groups"] + entry["vulnerable_groups"], limit=16)
        existing["authority_sources"] = _clean_list(existing["authority_sources"] + entry["authority_sources"], limit=12)
        existing["evidence_types"] = _clean_list(existing["evidence_types"] + entry["evidence_types"], limit=12)
        existing["sample_source_ids"] = _clean_list(existing["sample_source_ids"] + entry["sample_source_ids"], limit=20)
        existing["source_count"] = max(existing["source_count"], entry["source_count"])
        existing["evidence_count"] += entry["evidence_count"]
        if len(existing.get("description", "")) < len(entry.get("description", "")):
            existing["description"] = entry["description"]
        if len(existing.get("notes", "")) < len(entry.get("notes", "")):
            existing["notes"] = entry["notes"]
    deduped = list(grouped.values())
    deduped.sort(key=lambda item: (-item["evidence_count"], item["id"]))
    return deduped


class MiniMaxTaxonomyFormatter:
    def __init__(self, model: str = "MiniMax-M2.5", timeout: int = 60) -> None:
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

    def format_entry(self, candidate: dict[str, Any]) -> dict[str, Any]:
        prompt = f"""
请把下面的食品风险候选整理成一个简洁、稳定的 taxonomy 条目。
只输出 JSON 对象，不要解释。

字段必须包含：
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
- evidence_strength 仅可用：high, medium, low
- description 控制在 1-2 句
- 不要杜撰监管限量或年份

hazard_name: {candidate.get("hazard_name")}
hazard_class: {candidate.get("hazard_class")}
evidence_count: {candidate.get("evidence_count")}
source_count: {candidate.get("source_count")}
authorities: {candidate.get("authorities")}
evidence_types: {candidate.get("evidence_types")}
typical_products: {candidate.get("typical_products")}
symptoms: {candidate.get("symptoms")}
vulnerable_group: {candidate.get("vulnerable_group")}
summary: {candidate.get("summary")}
supporting_summaries:
{chr(10).join(candidate.get("supporting_summaries", [])[:5])}
""".strip()

        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800,
            "messages": [
                {
                    "role": "system",
                    "content": "你是食品风险 taxonomy 编排助手。只输出 JSON 对象，不要输出思考过程。",
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
                return parsed if isinstance(parsed, dict) else {}
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code == 429:
                    time.sleep(2.5 * (attempt + 1))
                    continue
                break
            except Exception as exc:
                last_error = exc
                time.sleep(1.5 * (attempt + 1))
        return {"error": str(last_error)} if last_error else {}


class RiskTaxonomyYamlBuilder:
    def __init__(self, input_path: Path = INPUT_PATH, output_dir: Path = DEFAULT_OUTPUT_DIR) -> None:
        self.input_path = input_path
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.formatter = MiniMaxTaxonomyFormatter()

    def build(self) -> dict[str, Any]:
        candidates = _read_jsonl(self.input_path)
        entries: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for index, candidate in enumerate(candidates, 1):
            llm = self.formatter.format_entry(candidate)
            name = llm.get("name") or candidate["hazard_name"]
            category = CATEGORY_MAP.get(candidate.get("hazard_class", "unknown"), "unknown")
            entry_id = f"{category}_{_slugify(name)}"
            if entry_id in seen_ids:
                entry_id = f"{entry_id}_{index}"
            seen_ids.add(entry_id)

            entry = {
                "id": entry_id,
                "name": name,
                "category": category,
                "aliases": _clean_list(llm.get("aliases", []) + [candidate["hazard_name"]], limit=8),
                "description": llm.get("description") or candidate.get("summary", ""),
                "applicable_products": _clean_list(llm.get("applicable_products", []) + candidate.get("typical_products", []), limit=12),
                "typical_symptoms": _clean_list(llm.get("typical_symptoms", []) + candidate.get("symptoms", []), limit=12),
                "vulnerable_groups": _clean_list(llm.get("vulnerable_groups", []) + candidate.get("vulnerable_group", []), limit=12),
                "evidence_strength": llm.get("evidence_strength", "medium"),
                "authority_sources": candidate.get("authorities", []),
                "evidence_types": candidate.get("evidence_types", []),
                "source_count": candidate.get("source_count", 0),
                "evidence_count": candidate.get("evidence_count", 0),
                "sample_source_ids": candidate.get("source_ids", [])[:10],
                "notes": llm.get("notes", ""),
                "llm_entry": llm,
            }
            entries.append(entry)
            print(_json_dumps({"done": index, "total": len(candidates), "id": entry_id}), flush=True)

        entries = _dedupe_entries(entries)

        yaml_payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "source": str(self.input_path),
            "risk_factors": entries,
        }

        yaml_path = self.output_dir / "risk_taxonomy_vnext.yaml"
        yaml_path.write_text(yaml.safe_dump(yaml_payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
        _write_jsonl(self.output_dir / "risk_taxonomy_vnext.jsonl", entries)
        manifest = {
            "generated_at": datetime.now(UTC).isoformat(),
            "input_path": str(self.input_path),
            "output_dir": str(self.output_dir),
            "entries": len(entries),
            "model": self.formatter.model,
        }
        _write_json(self.output_dir / "risk_taxonomy_vnext_manifest.json", manifest)
        return manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build vnext risk taxonomy YAML with MiniMax sequential formatting.")
    parser.add_argument("--input-path", default=str(INPUT_PATH), help="High-confidence candidate jsonl path.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output dir for vnext taxonomy files.")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    manifest = RiskTaxonomyYamlBuilder(input_path=Path(args.input_path), output_dir=Path(args.output_dir)).build()
    print(_json_dumps(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
