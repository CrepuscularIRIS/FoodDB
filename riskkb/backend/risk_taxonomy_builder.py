#!/usr/bin/env python3
"""Build raw structured risk taxonomy candidates with MiniMax-M2.5."""

from __future__ import annotations

import argparse
import json
import os
import re
import textwrap
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = ROOT / "knowledge"
DEFAULT_OUTPUT_DIR = KNOWLEDGE_DIR / "derived" / "risk_taxonomy_candidates"
LITERATURE_DIR = KNOWLEDGE_DIR / "derived" / "risk_taxonomy_raw_food_wide"
EVENTS_DIR = KNOWLEDGE_DIR / "derived" / "risk_taxonomy_raw_events"


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


class MiniMaxExtractor:
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

    def extract(self, prompt: str) -> list[dict[str, Any]]:
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 1400,
            "messages": [
                {
                    "role": "system",
                    "content": "你是食品风险知识结构化助手。只输出 JSON 数组，不要输出思考过程，不要输出 <think> 标签。",
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
                break
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code == 429:
                    time.sleep(2.5 * (attempt + 1))
                    continue
                raise
            except Exception as exc:
                last_error = exc
                time.sleep(1.5 * (attempt + 1))
        else:
            if last_error is not None:
                raise last_error
            raise RuntimeError("MiniMax extraction failed without exception")
        content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = json.loads(_extract_json_text(content))
        return parsed if isinstance(parsed, list) else []


@dataclass
class SourceRecord:
    source: str
    source_file: str
    record_id: str
    text_payload: str
    metadata: dict[str, Any]


class RiskTaxonomyBuilder:
    def __init__(
        self,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        model: str = "MiniMax-M2.5",
    ) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.extractor = MiniMaxExtractor(model=model)

    def build(
        self,
        max_literature: int = 50,
        max_events: int = 50,
        literature_offset: int = 0,
        event_offset: int = 0,
    ) -> dict[str, Any]:
        source_records = self._load_records(
            max_literature=max_literature,
            max_events=max_events,
            literature_offset=literature_offset,
            event_offset=event_offset,
        )
        rows: list[dict[str, Any]] = []
        for index, record in enumerate(source_records, 1):
            extracted = self._extract_record(record)
            rows.extend(extracted)
            print(_json_dumps({"done": index, "total": len(source_records), "source": record.source, "record_id": record.record_id, "extracted": len(extracted)}), flush=True)

        manifest = {
            "generated_at": datetime.now(UTC).isoformat(),
            "output_dir": str(self.output_dir),
            "input_literature_limit": max_literature,
            "input_event_limit": max_events,
            "literature_offset": literature_offset,
            "event_offset": event_offset,
            "source_records": len(source_records),
            "taxonomy_rows": len(rows),
            "model": self.extractor.model,
        }
        _write_jsonl(self.output_dir / "risk_taxonomy_candidates.jsonl", rows)
        _write_json(self.output_dir / "risk_taxonomy_candidates_manifest.json", manifest)
        return manifest

    def _load_records(
        self,
        max_literature: int,
        max_events: int,
        literature_offset: int,
        event_offset: int,
    ) -> list[SourceRecord]:
        records: list[SourceRecord] = []

        pubmed_path = LITERATURE_DIR / "pubmed_records.jsonl"
        if pubmed_path.exists():
            with pubmed_path.open(encoding="utf-8") as handle:
                for i, line in enumerate(handle):
                    if i < literature_offset:
                        continue
                    if i >= literature_offset + max_literature:
                        break
                    row = json.loads(line)
                    records.append(
                        SourceRecord(
                            source="pubmed",
                            source_file=pubmed_path.name,
                            record_id=row.get("pmid", f"pubmed_{i}"),
                            text_payload=textwrap.dedent(
                                f"""
                                title: {row.get('title', '')}
                                abstract: {row.get('abstract', '')}
                                journal: {row.get('journal', '')}
                                year: {row.get('year', '')}
                                hazard_hint: {row.get('hazard_hint', '')}
                                mesh_terms: {", ".join(row.get('mesh_terms', []))}
                                """
                            ).strip(),
                            metadata=row,
                        )
                    )

        events_path = EVENTS_DIR / "openfda_food_enforcement.jsonl"
        if events_path.exists():
            with events_path.open(encoding="utf-8") as handle:
                for i, line in enumerate(handle):
                    if i < event_offset:
                        continue
                    if i >= event_offset + max_events:
                        break
                    row = json.loads(line)
                    records.append(
                        SourceRecord(
                            source="openfda_food_enforcement",
                            source_file=events_path.name,
                            record_id=row.get("recall_number", f"event_{i}"),
                            text_payload=textwrap.dedent(
                                f"""
                                product_description: {row.get('product_description', '')}
                                reason_for_recall: {row.get('reason_for_recall', '')}
                                classification: {row.get('classification', '')}
                                recalling_firm: {row.get('recalling_firm', '')}
                                distribution_pattern: {row.get('distribution_pattern', '')}
                                hazard_hint: {row.get('hazard_hint', '')}
                                """
                            ).strip(),
                            metadata=row,
                        )
                    )
        return records

    def _extract_record(self, record: SourceRecord) -> list[dict[str, Any]]:
        if record.source == "pubmed":
            prompt = textwrap.dedent(
                f"""
                下面是一篇食品风险相关医学文献。请基于标题、摘要、mesh词和 hazard_hint，抽取 1 到 3 条风险模式候选。
                只输出 JSON 数组，不要解释。

                每个元素必须包含：
                - hazard_name
                - hazard_class
                - symptoms
                - vulnerable_group
                - typical_products
                - evidence_type
                - source_url_or_id
                - authority
                - confidence
                - rationale

                约束：
                - `hazard_class` 仅可用：microbial, chemical, toxin, residue, allergen, physical, unknown
                - 文献类 `evidence_type` 固定写 `literature`
                - `source_url_or_id` 直接写 PMID 或 source_url
                - 如果摘要提到致病菌/化学物但未明写症状，可根据该危害在食品安全领域的典型临床表现给出 1 到 5 个常见症状
                - 如果摘要提到婴儿、孕妇、免疫低下等，优先填入 `vulnerable_group`
                - 必须至少返回 1 条，不要空数组

                source: {record.source}
                record_id: {record.record_id}
                metadata:
                {json.dumps(record.metadata, ensure_ascii=False)}

                evidence_text:
                {record.text_payload}
                """
            ).strip()
        else:
            prompt = textwrap.dedent(
                f"""
                请根据下面的食品风险证据，抽取 0 到 3 条风险模式候选。
                只输出 JSON 数组。每个元素必须包含以下字段：
                - hazard_name
                - hazard_class
                - symptoms
                - vulnerable_group
                - typical_products
                - evidence_type
                - source_url_or_id
                - authority
                - confidence
                - rationale

                规则：
                - `hazard_class` 仅可用：microbial, chemical, toxin, residue, allergen, physical, unknown
                - `symptoms` / `vulnerable_group` / `typical_products` 都输出数组
                - 如果证据里没有明确症状，可输出空数组
                - 不要编造 source id，直接复用给定 metadata 中的 PMID 或 recall number
                - `confidence` 仅可用：high, medium, low
                - 输出必须是中文或中英混合可读，不要写解释文字

                source: {record.source}
                record_id: {record.record_id}
                metadata:
                {json.dumps(record.metadata, ensure_ascii=False)}

                evidence_text:
                {record.text_payload}
                """
            ).strip()
        try:
            result = self.extractor.extract(prompt)
        except Exception:
            return []

        normalized: list[dict[str, Any]] = []
        for item in result:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "record_type": "risk_taxonomy_candidate",
                    "source": record.source,
                    "source_file": record.source_file,
                    "source_record_id": record.record_id,
                    "hazard_name": item.get("hazard_name", ""),
                    "hazard_class": item.get("hazard_class", "unknown"),
                    "symptoms": item.get("symptoms", []) if isinstance(item.get("symptoms", []), list) else [],
                    "vulnerable_group": item.get("vulnerable_group", []) if isinstance(item.get("vulnerable_group", []), list) else [],
                    "typical_products": item.get("typical_products", []) if isinstance(item.get("typical_products", []), list) else [],
                    "evidence_type": item.get("evidence_type", ""),
                    "source_url_or_id": item.get("source_url_or_id") or record.metadata.get("source_url") or record.metadata.get("source_url_or_id") or record.record_id,
                    "authority": item.get("authority") or ("FDA" if record.source == "openfda_food_enforcement" else "literature"),
                    "confidence": item.get("confidence", "low"),
                    "rationale": item.get("rationale", ""),
                }
            )
        return normalized


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build raw risk taxonomy candidates with MiniMax-M2.5.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for structured risk taxonomy candidates.",
    )
    parser.add_argument(
        "--model",
        default="MiniMax-M2.5",
        help="MiniMax model name.",
    )
    parser.add_argument(
        "--max-literature",
        type=int,
        default=50,
        help="Number of literature records to process.",
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=50,
        help="Number of openFDA event records to process.",
    )
    parser.add_argument(
        "--literature-offset",
        type=int,
        default=0,
        help="Start offset in PubMed records.",
    )
    parser.add_argument(
        "--event-offset",
        type=int,
        default=0,
        help="Start offset in openFDA event records.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    builder = RiskTaxonomyBuilder(output_dir=Path(args.output_dir), model=args.model)
    manifest = builder.build(
        max_literature=args.max_literature,
        max_events=args.max_events,
        literature_offset=args.literature_offset,
        event_offset=args.event_offset,
    )
    print(_json_dumps(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
