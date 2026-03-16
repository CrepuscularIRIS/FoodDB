#!/usr/bin/env python3
"""Merge raw risk evidence sources into a unified schema."""

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

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = ROOT / "knowledge"
DEFAULT_OUTPUT_DIR = KNOWLEDGE_DIR / "derived" / "risk_taxonomy_raw_merged"

RAW_FOOD_WIDE_DIR = KNOWLEDGE_DIR / "derived" / "risk_taxonomy_raw_food_wide"
RAW_EVENTS_DIR = KNOWLEDGE_DIR / "derived" / "risk_taxonomy_raw_events"
RAW_PUBLIC_DIR = KNOWLEDGE_DIR / "derived" / "risk_taxonomy_raw_public_sources"
RAW_HF_DIR = KNOWLEDGE_DIR / "derived" / "risk_taxonomy_raw_huggingface"

HAZARD_CLASS_KEYWORDS = {
    "microbial": [
        "salmonella",
        "listeria",
        "cronobacter",
        "campylobacter",
        "staphylococcus",
        "bacillus cereus",
        "clostridium",
        "vibrio",
        "brucella",
        "norovirus",
        "hepatitis a",
        "giardia",
        "e. coli",
        "escherichia coli",
        "stec",
    ],
    "toxin": [
        "aflatoxin",
        "ochratoxin",
        "patulin",
        "fumonisin",
        "deoxynivalenol",
        "vomitoxin",
        "zearalenone",
        "toxin",
    ],
    "residue": [
        "residue",
        "nitrofuran",
        "chloramphenicol",
        "veterinary drug",
        "pesticide",
    ],
    "allergen": [
        "allergen",
        "undeclared milk",
        "undeclared egg",
        "undeclared soy",
        "undeclared wheat",
        "undeclared peanut",
        "undeclared tree nut",
        "milk allergen",
    ],
    "physical": [
        "glass",
        "metal",
        "plastic",
        "foreign material",
        "foreign object",
        "burn",
        "injury",
    ],
    "chemical": [
        "arsenic",
        "cadmium",
        "lead",
        "mercury",
        "melamine",
        "bpa",
        "phthalate",
        "pfas",
        "dioxin",
        "pcb",
        "nitrite",
        "nitrate",
    ],
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
    if not path.exists():
        return []
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
    bracket_match = re.search(r"(\[.*\])", text, flags=re.DOTALL)
    if bracket_match:
        return bracket_match.group(1).strip()
    brace_match = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    if brace_match:
        return brace_match.group(1).strip()
    return text


def _infer_hazard_class(text: str) -> str:
    lowered = text.lower()
    for hazard_class, keywords in HAZARD_CLASS_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return hazard_class
    return "unknown"


def _clean_list(items: list[str]) -> list[str]:
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
    return cleaned


class MiniMaxNormalizer:
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

    def normalize(self, row: dict[str, Any]) -> dict[str, Any]:
        prompt = f"""
请根据下面的食品风险原始证据，提取一个简短的标准化结果。
只输出 JSON 对象，不要解释。

字段必须包含：
- hazard_name
- hazard_class
- typical_products
- summary

约束：
- hazard_class 仅可用：microbial, chemical, toxin, residue, allergen, physical, unknown
- typical_products 输出数组
- 如果无法可靠判断 hazard_name，就输出空字符串
- summary 用 1 句中文概括这条证据

source: {row.get("source")}
evidence_type: {row.get("evidence_type")}
title: {row.get("title")}
text_payload: {row.get("text_payload")}
existing_hazard_name: {row.get("hazard_name")}
existing_hazard_hint: {row.get("hazard_hint")}
""".strip()

        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 500,
            "messages": [
                {
                    "role": "system",
                    "content": "你是食品风险知识标准化助手。只输出 JSON 对象，不要输出思考过程。",
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
            now = time.time()
            wait = self.min_interval_seconds - (now - self.last_request_ts)
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
        if last_error is not None:
            return {"error": str(last_error)}
        return {}


class RiskTaxonomyRawMerger:
    def __init__(self, output_dir: Path = DEFAULT_OUTPUT_DIR, enable_llm: bool = True) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.enable_llm = enable_llm
        self.normalizer = MiniMaxNormalizer() if enable_llm else None

    def build(self) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        source_counts: dict[str, int] = {}

        for row in self._merge_pubmed():
            rows.append(row)
            source_counts[row["source"]] = source_counts.get(row["source"], 0) + 1
        for row in self._merge_europe_pmc():
            rows.append(row)
            source_counts[row["source"]] = source_counts.get(row["source"], 0) + 1
        for row in self._merge_pubtator():
            rows.append(row)
            source_counts[row["source"]] = source_counts.get(row["source"], 0) + 1
        for row in self._merge_openfda():
            rows.append(row)
            source_counts[row["source"]] = source_counts.get(row["source"], 0) + 1
        for row in self._merge_cdc_nors():
            rows.append(row)
            source_counts[row["source"]] = source_counts.get(row["source"], 0) + 1
        for row in self._merge_fda_outbreaks():
            rows.append(row)
            source_counts[row["source"]] = source_counts.get(row["source"], 0) + 1
        for row in self._merge_warning_letters():
            rows.append(row)
            source_counts[row["source"]] = source_counts.get(row["source"], 0) + 1
        for row in self._merge_jecfa():
            rows.append(row)
            source_counts[row["source"]] = source_counts.get(row["source"], 0) + 1
        for row in self._merge_openfoodtox():
            rows.append(row)
            source_counts[row["source"]] = source_counts.get(row["source"], 0) + 1
        for row in self._merge_huggingface():
            rows.append(row)
            source_counts[row["source"]] = source_counts.get(row["source"], 0) + 1

        if self.normalizer is not None:
            self._apply_llm_normalization(rows)

        manifest = {
            "generated_at": datetime.now(UTC).isoformat(),
            "output_dir": str(self.output_dir),
            "records": len(rows),
            "source_counts": source_counts,
            "llm_enabled": bool(self.normalizer),
        }
        _write_jsonl(self.output_dir / "risk_taxonomy_raw_merged.jsonl", rows)
        _write_json(self.output_dir / "risk_taxonomy_raw_merged_manifest.json", manifest)
        return manifest

    def _base_row(self, *, source: str, source_record_id: str, source_url_or_id: str, authority: str, evidence_type: str) -> dict[str, Any]:
        return {
            "record_type": "raw_risk_evidence",
            "source": source,
            "source_record_id": source_record_id,
            "source_url_or_id": source_url_or_id,
            "authority": authority,
            "evidence_type": evidence_type,
            "hazard_name": "",
            "hazard_class": "unknown",
            "hazard_hint": "",
            "symptoms": [],
            "vulnerable_group": [],
            "typical_products": [],
            "product_domain": "",
            "title": "",
            "summary": "",
            "text_payload": "",
            "year": "",
            "pmid": "",
            "pmcid": "",
            "doi": "",
        }

    def _merge_pubmed(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in _read_jsonl(RAW_FOOD_WIDE_DIR / "pubmed_records.jsonl"):
            row = self._base_row(
                source="pubmed",
                source_record_id=str(item.get("pmid", "")),
                source_url_or_id=item.get("source_url") or str(item.get("pmid", "")),
                authority="PubMed",
                evidence_type="literature",
            )
            row.update(
                {
                    "hazard_hint": item.get("hazard_hint", ""),
                    "hazard_class": _infer_hazard_class(item.get("hazard_hint", "")),
                    "product_domain": item.get("product_domain", ""),
                    "title": item.get("title", ""),
                    "summary": item.get("abstract", ""),
                    "text_payload": f"title: {item.get('title', '')}\nabstract: {item.get('abstract', '')}",
                    "year": str(item.get("year", "") or ""),
                    "pmid": str(item.get("pmid", "") or ""),
                    "doi": item.get("doi", ""),
                }
            )
            rows.append(row)
        return rows

    def _merge_europe_pmc(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in _read_jsonl(RAW_FOOD_WIDE_DIR / "europe_pmc_records.jsonl"):
            row = self._base_row(
                source="europe_pmc",
                source_record_id=str(item.get("pmid") or item.get("pmcid") or item.get("doi") or ""),
                source_url_or_id=item.get("source_url") or str(item.get("pmid") or item.get("pmcid") or ""),
                authority="Europe PMC",
                evidence_type="literature",
            )
            row.update(
                {
                    "hazard_hint": item.get("hazard_hint", ""),
                    "hazard_class": _infer_hazard_class(item.get("hazard_hint", "")),
                    "product_domain": item.get("product_domain", ""),
                    "title": item.get("title", ""),
                    "summary": item.get("abstract", ""),
                    "text_payload": f"title: {item.get('title', '')}\nabstract: {item.get('abstract', '')}",
                    "year": str(item.get("year", "") or ""),
                    "pmid": str(item.get("pmid", "") or ""),
                    "pmcid": item.get("pmcid", ""),
                    "doi": item.get("doi", ""),
                }
            )
            rows.append(row)
        return rows

    def _merge_pubtator(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in _read_jsonl(RAW_FOOD_WIDE_DIR / "pubtator_annotations.jsonl"):
            annotations = item.get("annotations", []) or []
            hazard_names = _clean_list(
                [ann.get("text", "") for ann in annotations if ann.get("type") in {"Chemical", "Species"}]
            )
            symptoms = _clean_list(
                [ann.get("text", "") for ann in annotations if ann.get("type") == "Disease"]
            )
            joined = " ".join(hazard_names + symptoms)
            row = self._base_row(
                source="pubtator_central",
                source_record_id=str(item.get("pmid", "")),
                source_url_or_id=item.get("source_url") or str(item.get("pmid", "")),
                authority="PubTator Central",
                evidence_type="annotation",
            )
            row.update(
                {
                    "hazard_name": hazard_names[0] if hazard_names else "",
                    "hazard_class": _infer_hazard_class(joined),
                    "symptoms": symptoms,
                    "summary": f"PubTator annotations: {item.get('annotation_count', 0)}",
                    "text_payload": joined,
                    "pmid": str(item.get("pmid", "") or ""),
                }
            )
            rows.append(row)
        return rows

    def _merge_openfda(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in _read_jsonl(RAW_EVENTS_DIR / "openfda_food_enforcement.jsonl"):
            text = "\n".join(
                [
                    item.get("reason_for_recall", ""),
                    item.get("product_description", ""),
                    item.get("hazard_hint", ""),
                ]
            )
            row = self._base_row(
                source="openfda_food_enforcement",
                source_record_id=item.get("recall_number") or item.get("event_id") or "",
                source_url_or_id=item.get("source_url_or_id") or item.get("recall_number") or "",
                authority=item.get("authority", "FDA"),
                evidence_type=item.get("evidence_type", "recall"),
            )
            row.update(
                {
                    "hazard_hint": item.get("hazard_hint", ""),
                    "hazard_class": _infer_hazard_class(text),
                    "hazard_name": item.get("hazard_hint", ""),
                    "title": item.get("product_description", ""),
                    "summary": item.get("reason_for_recall", ""),
                    "text_payload": text,
                    "year": str(item.get("report_date", ""))[:4],
                    "typical_products": _clean_list([item.get("product_description", "")]),
                }
            )
            rows.append(row)
        return rows

    def _merge_cdc_nors(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in _read_jsonl(RAW_PUBLIC_DIR / "cdc_nors" / "cdc_nors_foodborne.jsonl"):
            hazard_text = item.get("etiology", "")
            product_candidates = [item.get("food_vehicle", ""), item.get("food_contaminated_ingredient", ""), item.get("ifsac_category", "")]
            text = "\n".join(product_candidates + [hazard_text, item.get("setting", "")])
            row = self._base_row(
                source="cdc_nors",
                source_record_id=item.get("source_url_or_id", ""),
                source_url_or_id=item.get("source_url_or_id", ""),
                authority=item.get("authority", "CDC"),
                evidence_type=item.get("evidence_type", "outbreak"),
            )
            row.update(
                {
                    "hazard_name": hazard_text,
                    "hazard_class": _infer_hazard_class(hazard_text),
                    "title": item.get("food_vehicle", "") or item.get("ifsac_category", ""),
                    "summary": f"{item.get('state', '')} {item.get('year', '')} outbreak; illnesses={item.get('illnesses', '')}, hospitalizations={item.get('hospitalizations', '')}, deaths={item.get('deaths', '')}",
                    "text_payload": text,
                    "year": str(item.get("year", "") or ""),
                    "typical_products": _clean_list(product_candidates),
                }
            )
            rows.append(row)
        return rows

    def _merge_fda_outbreaks(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in _read_jsonl(RAW_PUBLIC_DIR / "fda_outbreaks" / "fda_outbreak_reports.jsonl"):
            row = self._base_row(
                source="fda_core_outbreak",
                source_record_id=item.get("source_url_or_id", ""),
                source_url_or_id=item.get("source_url_or_id", ""),
                authority=item.get("authority", "FDA"),
                evidence_type=item.get("evidence_type", "outbreak_report"),
            )
            text = "\n".join([item.get("title", ""), item.get("description", ""), item.get("body_excerpt", "")])
            row.update(
                {
                    "title": item.get("title", ""),
                    "summary": item.get("description", ""),
                    "text_payload": text,
                    "hazard_class": _infer_hazard_class(text),
                }
            )
            rows.append(row)
        core_index_path = RAW_PUBLIC_DIR / "fda_outbreaks" / "fda_core_outbreak_table.json"
        if core_index_path.exists():
            item = json.loads(core_index_path.read_text(encoding="utf-8"))
            row = self._base_row(
                source="fda_core_outbreak",
                source_record_id=item.get("source_url_or_id", ""),
                source_url_or_id=item.get("source_url_or_id", ""),
                authority=item.get("authority", "FDA"),
                evidence_type=item.get("evidence_type", "outbreak_table"),
            )
            text = "\n".join([item.get("title", ""), item.get("body_excerpt", "")])
            row.update(
                {
                    "title": item.get("title", ""),
                    "summary": item.get("title", ""),
                    "text_payload": text,
                    "hazard_class": _infer_hazard_class(text),
                }
            )
            rows.append(row)
        return rows

    def _merge_warning_letters(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in _read_jsonl(RAW_PUBLIC_DIR / "fda_warning_letters" / "warning_letters_food_related.jsonl"):
            raw = item.get("raw", {}) or {}
            text = " ".join(
                [
                    str(raw.get("company_name", "") or ""),
                    str(raw.get("issuing_office", "") or ""),
                    str(raw.get("subject", "") or ""),
                ]
            )
            row = self._base_row(
                source="fda_warning_letters",
                source_record_id=item.get("source_url_or_id", ""),
                source_url_or_id=item.get("source_url_or_id", ""),
                authority=item.get("authority", "FDA"),
                evidence_type=item.get("evidence_type", "warning_letter"),
            )
            row.update(
                {
                    "title": raw.get("company_name", ""),
                    "summary": raw.get("subject", ""),
                    "text_payload": text,
                    "year": str(raw.get("letter_issue_date", "") or "")[-4:],
                    "hazard_class": _infer_hazard_class(text),
                }
            )
            rows.append(row)
        return rows

    def _merge_jecfa(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in _read_jsonl(RAW_PUBLIC_DIR / "jecfa" / "jecfa_records.jsonl"):
            text = " ".join(
                [
                    str(item.get("name", "") or ""),
                    str(item.get("functional_class", "") or ""),
                    str(item.get("adi", "") or ""),
                ]
            )
            row = self._base_row(
                source="jecfa",
                source_record_id=item.get("source_url_or_id", ""),
                source_url_or_id=item.get("source_url_or_id", ""),
                authority=item.get("authority", "WHO/JECFA"),
                evidence_type=item.get("evidence_type", "toxicology"),
            )
            row.update(
                {
                    "hazard_name": item.get("name", ""),
                    "hazard_class": _infer_hazard_class(text),
                    "title": item.get("name", ""),
                    "summary": f"Functional class: {str(item.get('functional_class', '') or '')}; ADI: {str(item.get('adi', '') or '')}",
                    "text_payload": text,
                }
            )
            rows.append(row)
        return rows

    def _merge_openfoodtox(self) -> list[dict[str, Any]]:
        path = RAW_PUBLIC_DIR / "openfoodtox" / "openfoodtox_index.json"
        if not path.exists():
            return []
        item = json.loads(path.read_text(encoding="utf-8"))
        row = self._base_row(
            source="openfoodtox",
            source_record_id=item.get("source_url_or_id", ""),
            source_url_or_id=item.get("source_url_or_id", ""),
            authority=item.get("authority", "EFSA"),
            evidence_type=item.get("evidence_type", "toxicology_index"),
        )
        row.update(
            {
                "title": item.get("title", ""),
                "summary": item.get("description", ""),
                "text_payload": " ".join(item.get("related_links", [])),
                "hazard_class": "chemical",
            }
        )
        return [row]

    def _merge_huggingface(self) -> list[dict[str, Any]]:
        path = RAW_HF_DIR / "huggingface_manifest.json"
        if not path.exists():
            return []
        manifest = json.loads(path.read_text(encoding="utf-8"))
        rows: list[dict[str, Any]] = []
        for item in manifest.get("datasets", []):
            repo_id = item.get("repo_id", "")
            row = self._base_row(
                source="huggingface_dataset",
                source_record_id=repo_id,
                source_url_or_id=f"https://huggingface.co/datasets/{repo_id}",
                authority="Hugging Face",
                evidence_type="training_corpus",
            )
            row.update(
                {
                    "title": repo_id,
                    "summary": f"Downloaded support dataset with {item.get('file_count', 0)} files",
                    "text_payload": item.get("local_dir", ""),
                }
            )
            rows.append(row)
        return rows

    def _apply_llm_normalization(self, rows: list[dict[str, Any]]) -> None:
        targets = {"fda_core_outbreak", "jecfa", "openfoodtox", "huggingface_dataset"}
        total = sum(1 for row in rows if row["source"] in targets)
        done = 0
        for row in rows:
            if row["source"] not in targets:
                continue
            row["text_payload"] = row.get("text_payload", "")[:2000]
            done += 1
            normalized = self.normalizer.normalize(row)
            if normalized:
                if not row.get("hazard_name"):
                    row["hazard_name"] = normalized.get("hazard_name", "") or row.get("hazard_name", "")
                hazard_class = normalized.get("hazard_class", "")
                if hazard_class in {"microbial", "chemical", "toxin", "residue", "allergen", "physical", "unknown"}:
                    row["hazard_class"] = hazard_class
                row["typical_products"] = _clean_list(row.get("typical_products", []) + normalized.get("typical_products", []))
                if normalized.get("summary"):
                    row["summary"] = normalized["summary"]
                row["llm_normalized"] = normalized
            print(_json_dumps({"source": row["source"], "done": done, "total": total}), flush=True)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merge raw risk evidence into a unified schema.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for merged risk taxonomy raw rows.",
    )
    parser.add_argument(
        "--disable-llm",
        action="store_true",
        help="Disable MiniMax normalization for small, weakly-structured sources.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    merger = RiskTaxonomyRawMerger(output_dir=Path(args.output_dir), enable_llm=not args.disable_llm)
    manifest = merger.build()
    print(_json_dumps(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
