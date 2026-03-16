#!/usr/bin/env python3
"""Build a known-risk evaluation testset with MiniMax-assisted case generation."""

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
TAXONOMY_PATH = ROOT / "knowledge" / "configs" / "risk_taxonomy.yaml"
STAGE_RULES_PATH = ROOT / "knowledge" / "configs" / "stage_rules.yaml"
OUTPUT_DIR = ROOT / "knowledge" / "derived" / "known_risk_testset"
OUTPUT_JSONL = OUTPUT_DIR / "known_risk_testset.jsonl"
OUTPUT_YAML = OUTPUT_DIR / "known_risk_testset.yaml"
MANIFEST_PATH = OUTPUT_DIR / "known_risk_testset_manifest.json"
INTERMEDIATE_PATH = OUTPUT_DIR / "known_risk_testset_intermediate.jsonl"

CASE_STYLE_HINTS = [
    "症状主导型",
    "产品主导型",
    "人群脆弱型",
    "检验项主导型",
    "召回/投诉型",
    "冷链失控型",
    "原料污染型",
    "非法添加型",
]


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


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _extract_json_text(text: str) -> str:
    text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()
    brace_match = re.search(r"(\[.*\]|\{.*\})", text, flags=re.DOTALL)
    if brace_match:
        return brace_match.group(1).strip()
    return text


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _clean_text(text: str, max_len: int = 80) -> str:
    return " ".join(str(text or "").split()).strip(" ,;，；。")[:max_len].strip(" ,;，；。")


def _clean_list(items: list[str], limit: int, max_len: int = 60) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        value = _clean_text(item, max_len=max_len)
        if not value:
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(value)
        if len(out) >= limit:
            break
    return out


def _slug(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", text.lower())
    return re.sub(r"_+", "_", base).strip("_") or "case"


class MiniMaxCaseGenerator:
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

    def generate_cases(self, batch: list[dict[str, Any]], cases_per_factor: int) -> list[dict[str, Any]]:
        prompt_entries = []
        for item in batch:
            prompt_entries.append(
                {
                    "risk_factor_id": item["risk_factor_id"],
                    "risk_factor_name": item["risk_factor_name"],
                    "hazard_class": item["hazard_class"],
                    "description": item.get("description", ""),
                    "symptoms": item.get("typical_symptoms", [])[:6],
                    "vulnerable_groups": item.get("vulnerable_groups", [])[:4],
                    "products": item.get("applicable_products", [])[:6],
                    "stage_candidates": item.get("stage_candidates", [])[:4],
                    "evidence_requirements": item.get("evidence_requirements", [])[:4],
                    "records_to_check": item.get("records_to_check", [])[:4],
                }
            )
        prompt = f"""
请为下面每个食品风险因子生成 {cases_per_factor} 条“已知风险模式测试集”案例。
只输出 JSON 数组，不要解释，不要 Markdown。

每条案例必须包含：
- case_id
- style
- user_query
- symptoms
- vulnerable_group
- product
- indicative_tests
- expected_risk_factor_id
- expected_risk_factor_name
- acceptable_alternatives
- expected_stage_ids
- gb_main_basis
- method_basis
- evidence_type
- should_not_recall
- notes

约束：
- 输出总条数必须等于 输入风险因子数 * {cases_per_factor}
- user_query 必须像真实业务查询，中文，1-3句
- symptoms 数组 1-5 项
- indicative_tests 数组 1-4 项，可以为空但尽量给
- acceptable_alternatives 最多 3 个风险因子 id
- expected_stage_ids 取值只能来自：farm_and_raw_milk, raw_material_and_ingredients, production_and_processing, packaging_and_filling, cold_chain_and_logistics, retail_and_terminal_storage
- gb_main_basis 和 method_basis 写成短中文线索，不要伪造具体标准号
- evidence_type 只能用：medical_literature, outbreak_event, recall_event, toxicology, expert_rule
- should_not_recall 必须给 2-4 个跨品类或低相关干扰项，写风险因子名称或短语
- notes 写简短判题说明

案例风格可参考：{", ".join(CASE_STYLE_HINTS)}

entries:
{json.dumps(prompt_entries, ensure_ascii=False)}
""".strip()
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "max_tokens": 1800,
            "messages": [
                {
                    "role": "system",
                    "content": "你是食品安全评测集构造助手。只输出 JSON，不输出思考过程。",
                },
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
        for attempt in range(8):
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


class KnownRiskTestsetBuilder:
    def __init__(
        self,
        taxonomy_path: Path = TAXONOMY_PATH,
        stage_rules_path: Path = STAGE_RULES_PATH,
        output_dir: Path = OUTPUT_DIR,
        model: str = "MiniMax-M2.5",
        cases_per_factor: int = 6,
        batch_size: int = 2,
        resume: bool = True,
        risk_factor_limit: int | None = None,
    ) -> None:
        self.taxonomy_path = taxonomy_path
        self.stage_rules_path = stage_rules_path
        self.output_dir = output_dir
        self.output_jsonl = output_dir / OUTPUT_JSONL.name
        self.output_yaml = output_dir / OUTPUT_YAML.name
        self.manifest_path = output_dir / MANIFEST_PATH.name
        self.intermediate_path = output_dir / INTERMEDIATE_PATH.name
        self.generator = MiniMaxCaseGenerator(model=model)
        self.cases_per_factor = max(1, cases_per_factor)
        self.batch_size = max(1, batch_size)
        self.resume = resume
        self.risk_factor_limit = risk_factor_limit

    def build(self) -> dict[str, Any]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        taxonomy = yaml.safe_load(self.taxonomy_path.read_text(encoding="utf-8"))
        rules_doc = yaml.safe_load(self.stage_rules_path.read_text(encoding="utf-8"))
        stage_rule_map = {row["risk_factor_id"]: row for row in rules_doc.get("stage_rules", [])}
        risk_factors = taxonomy.get("risk_factors", [])
        if self.risk_factor_limit:
            risk_factors = risk_factors[: self.risk_factor_limit]
        enriched = []
        for rf in risk_factors:
            merged = dict(rf)
            merged.update(stage_rule_map.get(rf["id"], {}))
            merged["risk_factor_id"] = rf["id"]
            merged["risk_factor_name"] = rf["name"]
            merged["hazard_class"] = rf.get("category", "")
            enriched.append(merged)

        existing = _read_jsonl(self.intermediate_path) if self.resume else []
        if not self.intermediate_path.exists():
            self.intermediate_path.write_text("", encoding="utf-8")
        by_case_id = {row["case_id"]: row for row in existing if row.get("case_id")}
        completed_factor_counts: dict[str, int] = {}
        for row in existing:
            factor_id = row.get("expected_risk_factor_id")
            if factor_id:
                completed_factor_counts[factor_id] = completed_factor_counts.get(factor_id, 0) + 1

        self.manifest_path.write_text(
            _json_dumps(
                {
                    "generated_at": datetime.now(UTC).isoformat(),
                    "status": "running",
                    "cases": len(by_case_id),
                    "risk_factor_count": len(risk_factors),
                    "cases_per_factor_target": self.cases_per_factor,
                    "output_jsonl": str(self.output_jsonl),
                    "output_yaml": str(self.output_yaml),
                }
            )
            + "\n",
            encoding="utf-8",
        )

        for start in range(0, len(enriched), self.batch_size):
            batch = []
            for item in enriched[start:start + self.batch_size]:
                if completed_factor_counts.get(item["risk_factor_id"], 0) >= self.cases_per_factor:
                    continue
                batch.append(item)
            if not batch:
                continue
            llm_rows = self.generator.generate_cases(batch, self.cases_per_factor)
            for row in llm_rows:
                clean = self._normalize_case(row, enriched, completed_factor_counts)
                if not clean:
                    continue
                factor_id = clean["expected_risk_factor_id"]
                if completed_factor_counts.get(factor_id, 0) >= self.cases_per_factor:
                    continue
                by_case_id[clean["case_id"]] = clean
                completed_factor_counts[factor_id] = completed_factor_counts.get(factor_id, 0) + 1
            self._write_intermediate(list(by_case_id.values()))
            self.manifest_path.write_text(
                _json_dumps(
                    {
                        "generated_at": datetime.now(UTC).isoformat(),
                        "status": "running",
                        "cases": len(by_case_id),
                        "risk_factor_count": len(risk_factors),
                        "cases_per_factor_target": self.cases_per_factor,
                        "output_jsonl": str(self.output_jsonl),
                        "output_yaml": str(self.output_yaml),
                    }
                )
                + "\n",
                encoding="utf-8",
            )

        cases = list(by_case_id.values())
        cases.sort(key=lambda row: row["case_id"])
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with self.output_jsonl.open("w", encoding="utf-8") as handle:
            for row in cases:
                handle.write(_json_dumps(row) + "\n")
        yaml_doc = {
            "version": "known-risk-testset-v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "source": {
                "risk_taxonomy": str(self.taxonomy_path),
                "stage_rules": str(self.stage_rules_path),
                "builder": "backend/known_risk_testset_builder.py",
                "model": self.generator.model,
            },
            "cases": cases,
        }
        self.output_yaml.write_text(yaml.safe_dump(yaml_doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
        manifest = {
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "completed",
            "cases": len(cases),
            "risk_factor_count": len(risk_factors),
            "cases_per_factor_target": self.cases_per_factor,
            "output_jsonl": str(self.output_jsonl),
            "output_yaml": str(self.output_yaml),
        }
        self.manifest_path.write_text(_json_dumps(manifest) + "\n", encoding="utf-8")
        return manifest

    def _normalize_case(
        self,
        row: dict[str, Any],
        enriched: list[dict[str, Any]],
        completed_factor_counts: dict[str, int],
    ) -> dict[str, Any] | None:
        factor_id = _clean_text(row.get("expected_risk_factor_id", ""), max_len=64)
        factor = next((item for item in enriched if item["risk_factor_id"] == factor_id), None)
        if not factor:
            return None
        stage_ids = []
        valid_stage_ids = {candidate.get("stage") for candidate in factor.get("stage_candidates", [])}
        for stage_id in row.get("expected_stage_ids", []):
            value = _clean_text(stage_id, max_len=40)
            if value in valid_stage_ids and value not in stage_ids:
                stage_ids.append(value)
        if not stage_ids:
            stage_ids = [candidate.get("stage") for candidate in factor.get("stage_candidates", [])[:2] if candidate.get("stage")]
        style = _clean_text(row.get("style", ""), max_len=20) or "综合型"
        symptoms = _clean_list(row.get("symptoms", []) or factor.get("typical_symptoms", [])[:3], 5)
        tests = _clean_list(row.get("indicative_tests", []) or factor.get("evidence_requirements", [])[:2], 4)
        alternatives = []
        valid_factor_ids = {item["risk_factor_id"] for item in enriched}
        for alt in row.get("acceptable_alternatives", []):
            value = _clean_text(alt, max_len=64)
            if value in valid_factor_ids and value != factor_id and value not in alternatives:
                alternatives.append(value)
            if len(alternatives) >= 3:
                break
        if not alternatives:
            for item in enriched:
                if item["hazard_class"] == factor["hazard_class"] and item["risk_factor_id"] != factor_id:
                    alternatives.append(item["risk_factor_id"])
                if len(alternatives) >= 2:
                    break
        case_id = _clean_text(row.get("case_id", ""), max_len=80)
        if not case_id:
            case_id = f"{factor_id}_{completed_factor_counts.get(factor_id, 0) + 1:03d}"
        else:
            case_id = _slug(case_id)
        return {
            "case_id": case_id,
            "style": style,
            "user_query": _clean_text(row.get("user_query", ""), max_len=220),
            "symptoms": symptoms,
            "vulnerable_group": _clean_text(row.get("vulnerable_group", ""), max_len=40),
            "product": _clean_text(row.get("product", ""), max_len=50),
            "indicative_tests": tests,
            "expected_risk_factor_id": factor_id,
            "expected_risk_factor_name": factor["risk_factor_name"],
            "acceptable_alternatives": alternatives[:3],
            "expected_stage_ids": stage_ids[:4],
            "gb_main_basis": _clean_text(row.get("gb_main_basis", ""), max_len=40) or "需回查对应GB主依据",
            "method_basis": _clean_text(row.get("method_basis", ""), max_len=40) or "需回查对应方法标准",
            "evidence_type": _clean_text(row.get("evidence_type", ""), max_len=30) or "expert_rule",
            "should_not_recall": _clean_list(row.get("should_not_recall", []), 4, max_len=40),
            "notes": _clean_text(row.get("notes", ""), max_len=120),
        }

    def _write_intermediate(self, rows: list[dict[str, Any]]) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        rows.sort(key=lambda row: row["case_id"])
        with self.intermediate_path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(_json_dumps(row) + "\n")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build known-risk evaluation testset with MiniMax.")
    parser.add_argument("--taxonomy-path", default=str(TAXONOMY_PATH))
    parser.add_argument("--stage-rules-path", default=str(STAGE_RULES_PATH))
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--model", default="MiniMax-M2.5")
    parser.add_argument("--cases-per-factor", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--risk-factor-limit", type=int, default=0)
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    builder = KnownRiskTestsetBuilder(
        taxonomy_path=Path(args.taxonomy_path),
        stage_rules_path=Path(args.stage_rules_path),
        output_dir=Path(args.output_dir),
        model=args.model,
        cases_per_factor=args.cases_per_factor,
        batch_size=args.batch_size,
        resume=not args.no_resume,
        risk_factor_limit=args.risk_factor_limit or None,
    )
    manifest = builder.build()
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
