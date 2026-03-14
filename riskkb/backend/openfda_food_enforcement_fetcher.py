#!/usr/bin/env python3
"""Fetch openFDA food enforcement recall records for risk taxonomy evidence."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = ROOT / "knowledge"
DEFAULT_OUTPUT_DIR = KNOWLEDGE_DIR / "derived" / "risk_taxonomy_raw_events"

BASE_URL = "https://api.fda.gov/food/enforcement.json"

FOOD_SEARCH_TERMS = [
    "milk",
    "dairy",
    "cheese",
    "yogurt",
    "yoghurt",
    "butter",
    "cream",
    "ice cream",
    "whey",
    "infant formula",
    "formula",
    "egg",
    "meat",
    "poultry",
    "chicken",
    "beef",
    "pork",
    "fish",
    "seafood",
    "shellfish",
    "shrimp",
    "oyster",
    "vegetable",
    "fruit",
    "juice",
    "rice",
    "grain",
    "cereal",
    "salad",
    "sprout",
    "nut",
    "peanut",
]


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


def _request_json(url: str, timeout: int = 60) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(4):
        request = urllib.request.Request(url, headers={"User-Agent": "standalone-food-risk-kb/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {"meta": {"results": {"total": 0}}, "results": []}
            last_error = exc
            time.sleep(1.0 + attempt * 1.5)
        except (
            urllib.error.URLError,
            TimeoutError,
            http.client.RemoteDisconnected,
            json.JSONDecodeError,
        ) as exc:
            last_error = exc
            time.sleep(1.0 + attempt * 1.5)
    if last_error is not None:
        raise last_error
    raise RuntimeError("openFDA request failed without exception")


def _looks_food_related(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in FOOD_SEARCH_TERMS)


class OpenFDAFoodEnforcementFetcher:
    def __init__(self, output_dir: Path = DEFAULT_OUTPUT_DIR) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        env = _read_env(ROOT / ".env")
        self.api_key = (
            os.environ.get("OPENFDA_API_KEY")
            or os.environ.get("openFDA-API-KEY")
            or env.get("OPENFDA_API_KEY")
            or env.get("openFDA-API-KEY")
        )
        if not self.api_key:
            raise RuntimeError("Missing openFDA API key")

    def fetch_all(self, limit_per_call: int = 1000, start_year: int = 2004) -> dict[str, Any]:
        records: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        current_year = datetime.now(UTC).year
        total_api_records = 0
        processed_records = 0

        for year in range(start_year, current_year + 1):
            skip = 0
            while True:
                base_params = urllib.parse.urlencode(
                    {
                        "api_key": self.api_key,
                        "limit": str(limit_per_call),
                        "skip": str(skip),
                    }
                )
                search_expr = f"report_date:[{year}0101+TO+{year}1231]"
                url = f"{BASE_URL}?{base_params}&search={search_expr}"
                payload = _request_json(url)
                meta = payload.get("meta", {}) or {}
                results = payload.get("results", []) or []
                year_total = int(meta.get("results", {}).get("total", 0) or 0)
                total_api_records += year_total if skip == 0 else 0
                processed_records += len(results)

                batch_rows = [self._normalize_result(item) for item in results]
                for row in batch_rows:
                    dedupe_id = row.get("recall_number") or row.get("event_id")
                    if not dedupe_id or dedupe_id in seen_ids:
                        continue
                    if not self._is_food_taxonomy_candidate(row):
                        continue
                    seen_ids.add(dedupe_id)
                    records.append(row)

                manifest = {
                    "generated_at": datetime.now(UTC).isoformat(),
                    "output_dir": str(self.output_dir),
                    "api_total_records": total_api_records,
                    "processed_records": processed_records,
                    "stored_records": len(records),
                    "limit_per_call": limit_per_call,
                    "current_year": year,
                }
                _write_jsonl(self.output_dir / "openfda_food_enforcement.jsonl", records)
                _write_json(self.output_dir / "openfda_food_enforcement_manifest.json", manifest)

                print(
                    _json_dumps(
                        {
                            "year": year,
                            "processed_records": processed_records,
                            "api_total_records": total_api_records,
                            "stored_records": len(records),
                        }
                    ),
                    flush=True,
                )

                if not results or skip + len(results) >= year_total:
                    break
                skip += len(results)
                time.sleep(0.25)

        return manifest

    def _normalize_result(self, item: dict[str, Any]) -> dict[str, Any]:
        reason = item.get("reason_for_recall", "") or ""
        description = item.get("product_description", "") or ""
        classification = item.get("classification", "") or ""
        distribution = item.get("distribution_pattern", "") or ""
        hazard_hint = self._infer_hazard_hint(f"{reason}\n{description}")
        return {
            "record_type": "event_evidence",
            "source": "openfda_food_enforcement",
            "event_id": item.get("event_id", ""),
            "recall_number": item.get("recall_number", ""),
            "classification": classification,
            "status": item.get("status", ""),
            "recalling_firm": item.get("recalling_firm", ""),
            "product_type": item.get("product_type", ""),
            "product_description": description,
            "reason_for_recall": reason,
            "distribution_pattern": distribution,
            "report_date": item.get("report_date", ""),
            "recall_initiation_date": item.get("recall_initiation_date", ""),
            "center_classification_date": item.get("center_classification_date", ""),
            "termination_date": item.get("termination_date", ""),
            "voluntary_mandated": item.get("voluntary_mandated", ""),
            "state": item.get("state", ""),
            "country": item.get("country", ""),
            "product_quantity": item.get("product_quantity", ""),
            "code_info": item.get("code_info", ""),
            "more_code_info": item.get("more_code_info", ""),
            "hazard_hint": hazard_hint,
            "authority": "FDA",
            "evidence_type": "recall",
            "source_url_or_id": item.get("recall_number", "") or item.get("event_id", ""),
        }

    def _is_food_taxonomy_candidate(self, row: dict[str, Any]) -> bool:
        product_type = (row.get("product_type") or "").lower()
        text = "\n".join(
            [
                row.get("product_description", ""),
                row.get("reason_for_recall", ""),
                row.get("distribution_pattern", ""),
            ]
        )
        if product_type and product_type != "food":
            return False
        return _looks_food_related(text) or bool(row.get("hazard_hint"))

    def _infer_hazard_hint(self, text: str) -> str:
        lowered = text.lower()
        checks = [
            ("listeria", ["listeria"]),
            ("salmonella", ["salmonella"]),
            ("ecoli", ["e. coli", "escherichia coli", "stec"]),
            ("cronobacter", ["cronobacter"]),
            ("campylobacter", ["campylobacter"]),
            ("staphylococcus_aureus", ["staphylococcus", "staph"]),
            ("bacillus_cereus", ["bacillus cereus"]),
            ("clostridium_botulinum", ["botulism", "clostridium botulinum"]),
            ("allergen", ["undeclared", "allergen", "milk", "egg", "soy", "wheat", "peanut", "tree nut"]),
            ("foreign_matter", ["foreign material", "foreign object", "metal fragment", "glass", "plastic"]),
            ("aflatoxin", ["aflatoxin"]),
            ("lead", ["lead"]),
            ("arsenic", ["arsenic"]),
            ("cadmium", ["cadmium"]),
        ]
        for label, patterns in checks:
            if any(pattern in lowered for pattern in patterns):
                return label
        return ""


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch openFDA food enforcement recall records.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for openFDA recall evidence.",
    )
    parser.add_argument(
        "--limit-per-call",
        type=int,
        default=1000,
        help="Maximum records per openFDA API call. openFDA allows up to 1000.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    fetcher = OpenFDAFoodEnforcementFetcher(output_dir=Path(args.output_dir))
    manifest = fetcher.fetch_all(limit_per_call=args.limit_per_call)
    print(_json_dumps(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
