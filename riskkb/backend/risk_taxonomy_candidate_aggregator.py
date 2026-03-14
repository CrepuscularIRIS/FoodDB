#!/usr/bin/env python3
"""Aggregate merged raw evidence into structured risk taxonomy candidates."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = ROOT / "knowledge"
INPUT_PATH = KNOWLEDGE_DIR / "derived" / "risk_taxonomy_raw_merged" / "risk_taxonomy_raw_merged.jsonl"
DEFAULT_OUTPUT_DIR = KNOWLEDGE_DIR / "derived" / "risk_taxonomy_candidates_structured"

ALIAS_RULES = [
    (re.compile(r"\bcronobacter\b|\benterobacter sakazakii\b", re.I), ("Cronobacter", "microbial")),
    (re.compile(r"\blisteria\b", re.I), ("Listeria monocytogenes", "microbial")),
    (re.compile(r"\bsalmonella\b", re.I), ("Salmonella", "microbial")),
    (re.compile(r"\be(\.|scherichia )? ?coli\b|\bstec\b|o157:h7", re.I), ("Escherichia coli / STEC", "microbial")),
    (re.compile(r"\bcampylobacter\b", re.I), ("Campylobacter", "microbial")),
    (re.compile(r"\bstaphylococcus aureus\b|\bstaph", re.I), ("Staphylococcus aureus", "microbial")),
    (re.compile(r"\bbacillus cereus\b|\bcereulide\b", re.I), ("Bacillus cereus", "microbial")),
    (re.compile(r"\bclostridium perfringens\b", re.I), ("Clostridium perfringens", "microbial")),
    (re.compile(r"\bclostridium botulinum\b|\bbotulism\b", re.I), ("Clostridium botulinum", "microbial")),
    (re.compile(r"\bvibrio\b", re.I), ("Vibrio", "microbial")),
    (re.compile(r"\bbrucella\b", re.I), ("Brucella", "microbial")),
    (re.compile(r"\bnorovirus\b", re.I), ("Norovirus", "microbial")),
    (re.compile(r"\bhepatitis a\b", re.I), ("Hepatitis A virus", "microbial")),
    (re.compile(r"\bgiardia\b", re.I), ("Giardia", "microbial")),
    (re.compile(r"\baflatoxin m1\b|\bafm1\b", re.I), ("Aflatoxin M1", "toxin")),
    (re.compile(r"\baflatoxin b1\b", re.I), ("Aflatoxin B1", "toxin")),
    (re.compile(r"\baflatoxin", re.I), ("Aflatoxins", "toxin")),
    (re.compile(r"\bochratoxin a\b", re.I), ("Ochratoxin A", "toxin")),
    (re.compile(r"\bpatulin\b", re.I), ("Patulin", "toxin")),
    (re.compile(r"\bfumonisin", re.I), ("Fumonisins", "toxin")),
    (re.compile(r"\bdeoxynivalenol\b|\bdon\b|\bvomitoxin\b", re.I), ("Deoxynivalenol", "toxin")),
    (re.compile(r"\bzearalenone\b", re.I), ("Zearalenone", "toxin")),
    (re.compile(r"\bmelamine\b", re.I), ("Melamine", "chemical")),
    (re.compile(r"\barsenic\b", re.I), ("Arsenic", "chemical")),
    (re.compile(r"\bcadmium\b", re.I), ("Cadmium", "chemical")),
    (re.compile(r"\blead\b", re.I), ("Lead", "chemical")),
    (re.compile(r"\bmercury\b", re.I), ("Mercury", "chemical")),
    (re.compile(r"\bpfas\b|\bper- and polyfluoroalkyl substances\b", re.I), ("PFAS", "chemical")),
    (re.compile(r"\bdioxin", re.I), ("Dioxins", "chemical")),
    (re.compile(r"\bpcb\b", re.I), ("PCBs", "chemical")),
    (re.compile(r"\bnitrite\b|\bnitrate\b", re.I), ("Nitrite / Nitrate", "chemical")),
    (re.compile(r"\bpesticide residue\b", re.I), ("Pesticide residues", "residue")),
    (re.compile(r"\bveterinary drug residue\b|\bnitrofuran\b|\bchloramphenicol\b", re.I), ("Veterinary drug residues", "residue")),
    (re.compile(r"\ballergen\b|\bundeclared milk\b|\bmilk allergen\b", re.I), ("Undeclared allergen", "allergen")),
    (re.compile(r"\bforeign_matter\b|\bforeign matter\b|\bmetal\b|\bglass\b|\bplastic\b", re.I), ("Foreign material", "physical")),
    (re.compile(r"\bheavy[_ ]?metals?\b", re.I), ("Heavy metals", "chemical")),
    (re.compile(r"\bpackaging[_ ]?contaminants?\b|\bbpa\b|\bphthalate", re.I), ("Packaging contaminants", "chemical")),
]
GENERIC_REJECTS = {
    "",
    "human",
    "humans",
    "patients",
    "apple",
    "cattle",
    "other - chemical/toxin",
    "other - bacterium",
    "other - virus",
}
LLM_REFINEMENT_NAMES = {
    "Undeclared allergen",
    "Foreign material",
    "Heavy metals",
    "Packaging contaminants",
    "Pesticide residues",
    "Veterinary drug residues",
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


def _extract_json_text(text: str) -> str:
    text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()
    brace_match = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    if brace_match:
        return brace_match.group(1).strip()
    return text


def _canonicalize_name(name: str, fallback_class: str) -> tuple[str, str]:
    lowered = name.strip().lower()
    if lowered in GENERIC_REJECTS:
        return "", fallback_class
    for pattern, result in ALIAS_RULES:
        if pattern.search(lowered):
            return result
    return name.strip(), fallback_class


class MiniMaxRefiner:
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

    def refine(self, row: dict[str, Any]) -> dict[str, Any]:
        prompt = f"""
下面是一条聚合后的食品风险候选，请把名称和摘要修正得更适合作为 taxonomy 候选。
只输出 JSON 对象，不要解释。

字段必须包含：
- hazard_name
- hazard_class
- summary
- typical_products

约束：
- hazard_class 仅可用：microbial, chemical, toxin, residue, allergen, physical, unknown
- typical_products 输出数组
- hazard_name 要简洁、标准，不要写一整句

candidate_name: {row.get("hazard_name")}
hazard_class: {row.get("hazard_class")}
source_count: {row.get("source_count")}
evidence_count: {row.get("evidence_count")}
top_products: {row.get("typical_products")}
evidence_types: {row.get("evidence_types")}
authorities: {row.get("authorities")}
sample_summaries:
{chr(10).join(row.get("supporting_summaries", [])[:5])}
""".strip()

        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 500,
            "messages": [
                {"role": "system", "content": "你是食品风险 taxonomy 标准化助手。只输出 JSON 对象。"},
                {"role": "user", "content": prompt},
            ],
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
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


class RiskTaxonomyCandidateAggregator:
    def __init__(self, input_path: Path = INPUT_PATH, output_dir: Path = DEFAULT_OUTPUT_DIR, enable_llm: bool = True) -> None:
        self.input_path = input_path
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.refiner = MiniMaxRefiner() if enable_llm else None

    def build(self) -> dict[str, Any]:
        groups: dict[tuple[str, str], dict[str, Any]] = {}

        for row in _read_jsonl(self.input_path):
            if row.get("evidence_type") == "training_corpus":
                continue
            seed = row.get("hazard_name") or row.get("hazard_hint") or ""
            canonical_name, canonical_class = _canonicalize_name(seed, row.get("hazard_class", "unknown"))
            if not canonical_name:
                continue
            key = (canonical_name, canonical_class)
            group = groups.setdefault(
                key,
                {
                    "record_type": "risk_taxonomy_candidate",
                    "hazard_name": canonical_name,
                    "hazard_class": canonical_class,
                    "symptoms": [],
                    "vulnerable_group": [],
                    "typical_products": [],
                    "authorities": [],
                    "evidence_types": [],
                    "source_count": 0,
                    "evidence_count": 0,
                    "source_ids": [],
                    "supporting_summaries": [],
                    "source_breakdown": defaultdict(int),
                },
            )
            group["evidence_count"] += 1
            group["source_breakdown"][row["source"]] += 1
            group["authorities"].append(row.get("authority", ""))
            group["evidence_types"].append(row.get("evidence_type", ""))
            group["typical_products"].extend(row.get("typical_products", []))
            group["symptoms"].extend(row.get("symptoms", []))
            group["vulnerable_group"].extend(row.get("vulnerable_group", []))
            group["source_ids"].append(row.get("source_url_or_id", ""))
            if row.get("summary"):
                group["supporting_summaries"].append(row["summary"][:300])

        candidates: list[dict[str, Any]] = []
        for group in groups.values():
            row = dict(group)
            row["authorities"] = _clean_list(row["authorities"], limit=10)
            row["evidence_types"] = _clean_list(row["evidence_types"], limit=10)
            row["typical_products"] = _clean_list(row["typical_products"], limit=12)
            row["symptoms"] = _clean_list(row["symptoms"], limit=12)
            row["vulnerable_group"] = _clean_list(row["vulnerable_group"], limit=12)
            row["source_ids"] = _clean_list(row["source_ids"], limit=20)
            row["supporting_summaries"] = _clean_list(row["supporting_summaries"], limit=8)
            row["source_breakdown"] = dict(row["source_breakdown"])
            row["source_count"] = len(row["source_breakdown"])
            row["summary"] = row["supporting_summaries"][0] if row["supporting_summaries"] else ""
            candidates.append(row)

        candidates.sort(key=lambda item: (-item["evidence_count"], item["hazard_name"]))

        if self.refiner is not None:
            refine_targets = [row for row in candidates if row["hazard_name"] in LLM_REFINEMENT_NAMES]
            for index, row in enumerate(refine_targets, 1):
                refined = self.refiner.refine(row)
                if refined:
                    row["hazard_name"] = refined.get("hazard_name", "") or row["hazard_name"]
                    row["hazard_class"] = refined.get("hazard_class", "") or row["hazard_class"]
                    row["summary"] = refined.get("summary", "") or row["summary"]
                    row["typical_products"] = _clean_list(row["typical_products"] + refined.get("typical_products", []), limit=12)
                    row["llm_refined"] = refined
                print(_json_dumps({"done": index, "total": len(refine_targets), "hazard_name": row["hazard_name"]}), flush=True)

        high_confidence = [
            row
            for row in candidates
            if row["hazard_class"] != "unknown" and row["evidence_count"] >= 5 and row["source_count"] >= 2
        ]

        manifest = {
            "generated_at": datetime.now(UTC).isoformat(),
            "input_path": str(self.input_path),
            "output_dir": str(self.output_dir),
            "candidates": len(candidates),
            "high_confidence_candidates": len(high_confidence),
            "llm_enabled": bool(self.refiner),
        }
        _write_jsonl(self.output_dir / "risk_taxonomy_candidates_structured.jsonl", candidates)
        _write_jsonl(self.output_dir / "risk_taxonomy_candidates_structured_high_confidence.jsonl", high_confidence)
        _write_json(self.output_dir / "risk_taxonomy_candidates_structured_manifest.json", manifest)
        return manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate merged raw evidence into structured risk taxonomy candidates.")
    parser.add_argument("--input-path", default=str(INPUT_PATH), help="Merged raw input jsonl.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Structured candidate output dir.")
    parser.add_argument("--disable-llm", action="store_true", help="Disable MiniMax refinement on generic candidates.")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    aggregator = RiskTaxonomyCandidateAggregator(
        input_path=Path(args.input_path),
        output_dir=Path(args.output_dir),
        enable_llm=not args.disable_llm,
    )
    manifest = aggregator.build()
    print(_json_dumps(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
