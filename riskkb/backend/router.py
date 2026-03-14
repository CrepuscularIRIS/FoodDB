#!/usr/bin/env python3
"""Layered routing entrypoint for the standalone food risk knowledge base.

Flow:
1. Query text -> symptoms / test items / product terms
2. Rule layer (`configs`) -> risk factors -> stage candidates
3. Management layer -> likely production issues / control gaps
4. Standard layer -> GB evidence
5. Method layer -> test method evidence
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = ROOT / "knowledge"
CONFIG_DIR = KNOWLEDGE_DIR / "configs"
CORPUS_DIR = KNOWLEDGE_DIR / "corpora"


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _load_jsonl_first_existing(paths: list[Path]) -> list[dict[str, Any]]:
    for path in paths:
        if path.exists():
            return _load_jsonl(path)
    return []


def _extract_text(row: dict[str, Any]) -> str:
    return (
        row.get("chunk_text")
        or row.get("content")
        or row.get("raw_line")
        or row.get("text")
        or ""
    )


def _metadata_text(row: dict[str, Any]) -> str:
    metadata = row.get("metadata", {})
    if not isinstance(metadata, dict):
        return ""
    values: list[str] = []
    for value in metadata.values():
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            values.extend(str(item) for item in value)
    return " ".join(values)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _hit_terms(text: str, candidates: list[str]) -> list[str]:
    hits: list[str] = []
    lowered = text.lower()
    for item in candidates:
        if item and item.lower() in lowered:
            hits.append(item)
    return list(dict.fromkeys(hits))


def _expand_keyword_variants(keywords: list[str]) -> list[str]:
    expanded: list[str] = []
    for kw in keywords:
        if not kw:
            continue
        expanded.append(kw)
        if "奶" in kw:
            expanded.append(kw.replace("奶", "乳"))
        if "乳" in kw:
            expanded.append(kw.replace("乳", "奶"))
        for token in re.split(r"[/,，；;（）()\s>\-_:]+", kw):
            token = token.strip()
            if len(token) >= 2:
                expanded.append(token)
                if "奶" in token:
                    expanded.append(token.replace("奶", "乳"))
                if "乳" in token:
                    expanded.append(token.replace("乳", "奶"))
    return list(dict.fromkeys(expanded))


def _score_text(text: str, keywords: list[str]) -> float:
    if not text:
        return 0.0

    score = 0.0
    lowered = text.lower()
    for kw in keywords:
        if not kw:
            continue
        if kw.lower() in lowered:
            score += max(1.0, min(6.0, len(kw) / 4))
    return score


@dataclass
class SearchHit:
    score: float
    text: str
    metadata: dict[str, Any]
    source_file: str


class LayeredFoodRiskKB:
    def __init__(self) -> None:
        self.risk_taxonomy = _load_yaml(CONFIG_DIR / "risk_taxonomy.yaml")
        self.stage_rules = _load_yaml(CONFIG_DIR / "stage_rules.yaml")
        self.gb_dairy_rules = _load_yaml(CONFIG_DIR / "gb_dairy_rules.yaml")
        self.gb2762_rules = _load_yaml(CONFIG_DIR / "gb2762_contaminant_limits.yaml")

        self.management_corpus = _load_jsonl(CORPUS_DIR / "rag_corpus_management_v2.jsonl")
        self.standard_corpus = _load_jsonl(CORPUS_DIR / "rag_corpus_standard_txt.jsonl")
        self.methods_corpus_file = "rag_corpus_methods_standards.jsonl"
        if (CORPUS_DIR / "rag_corpus_methods_standards_v2.jsonl").exists():
            self.methods_corpus_file = "rag_corpus_methods_standards_v2.jsonl"
        self.methods_corpus = _load_jsonl_first_existing(
            [
                CORPUS_DIR / "rag_corpus_methods_standards_v2.jsonl",
                CORPUS_DIR / "rag_corpus_methods_standards.jsonl",
            ]
        )
        self.config_corpus = _load_jsonl(CORPUS_DIR / "rag_corpus_config_rules.jsonl")

        self.stages_by_id = {
            item["id"]: item for item in self.stage_rules.get("stages", [])
        }
        self.stage_rules_by_risk = {
            item["risk_factor"]: item for item in self.stage_rules.get("stage_rules", [])
        }
        self.risk_factor_defs = {
            item["id"]: item for item in self.risk_taxonomy.get("risk_factors", [])
        }

    def analyze_query(self, query: str) -> dict[str, Any]:
        text = _normalize_text(query)

        symptoms_mapping = self.risk_taxonomy.get("symptoms_mapping", {})
        symptom_hits = [
            {
                "term": term,
                "symptom_id": symptom_id,
            }
            for term, symptom_id in symptoms_mapping.items()
            if term.lower() in text
        ]

        test_item_mapping = self.risk_taxonomy.get("test_item_mapping", {})
        test_hits = [
            {
                "term": term,
                "risk_factor_id": risk_id,
            }
            for term, risk_id in test_item_mapping.items()
            if term.lower() in text
        ]

        product_terms = []
        for lang_terms in self.risk_taxonomy.get("dairy_product_terms", {}).values():
            product_terms.extend(lang_terms)
        product_hits = _hit_terms(query, product_terms)

        return {
            "symptoms": symptom_hits,
            "test_items": test_hits,
            "products": product_hits,
        }

    def infer_risk_factors(self, query: str, query_signals: dict[str, Any], top_k: int = 6) -> list[dict[str, Any]]:
        scores: dict[str, float] = defaultdict(float)
        reasons: dict[str, list[str]] = defaultdict(list)

        symptom_to_risk = self.risk_taxonomy.get("symptom_to_risk_factors", {})
        for item in query_signals["symptoms"]:
            symptom_id = item["symptom_id"]
            for mapping in symptom_to_risk.get(symptom_id, []):
                risk_id = mapping["risk_factor"]
                weight = float(mapping.get("weight", 0.1))
                scores[risk_id] += weight
                reasons[risk_id].append(f"symptom:{item['term']} weight={weight}")

        for item in query_signals["test_items"]:
            risk_id = item["risk_factor_id"]
            scores[risk_id] += 1.2
            reasons[risk_id].append(f"test_item:{item['term']}")

        lowered = query.lower()
        for risk_id, risk_def in self.risk_factor_defs.items():
            risk_name = str(risk_def.get("name", ""))
            description = str(risk_def.get("description", ""))
            applicable_products = risk_def.get("applicable_products", []) or []
            direct_score = 0.0

            if risk_name and risk_name.lower() in lowered:
                direct_score += 1.5
            for product in applicable_products:
                if product and product.lower() in lowered:
                    direct_score += 0.15

            if description:
                for token in re.split(r"[/,，；;（）()\s]+", risk_name):
                    if token and len(token) >= 2 and token.lower() in lowered:
                        direct_score += 0.25

            if direct_score > 0:
                scores[risk_id] += direct_score
                reasons[risk_id].append(f"direct_match:{direct_score:.2f}")

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        output: list[dict[str, Any]] = []
        for risk_id, score in ranked:
            risk_def = self.risk_factor_defs.get(risk_id, {})
            output.append(
                {
                    "risk_factor_id": risk_id,
                    "score": round(score, 4),
                    "name": risk_def.get("name"),
                    "category": risk_def.get("category"),
                    "description": risk_def.get("description"),
                    "applicable_products": risk_def.get("applicable_products", []),
                    "reasons": reasons[risk_id],
                }
            )
        return output

    def infer_stages(self, risk_candidates: list[dict[str, Any]], top_k: int = 5) -> list[dict[str, Any]]:
        stage_scores: dict[str, float] = defaultdict(float)
        stage_reasons: dict[str, list[str]] = defaultdict(list)

        default_rule = self.stage_rules.get("default_rule", {})
        for risk in risk_candidates:
            risk_id = risk["risk_factor_id"]
            base_score = float(risk["score"])
            rule = self.stage_rules_by_risk.get(risk_id)
            if rule:
                for cand in rule.get("stage_candidates", []):
                    stage_id = cand["stage"]
                    probability = float(cand.get("probability", 0.0))
                    stage_scores[stage_id] += base_score * probability
                    rationale = cand.get("rationale") or cand.get("basis") or "rule_based"
                    stage_reasons[stage_id].append(
                        f"{risk_id} * {probability:.2f}: {rationale}"
                    )
            else:
                for cand in default_rule.get("stage_candidates", []):
                    stage_id = cand["stage"]
                    probability = float(cand.get("probability", 0.0))
                    stage_scores[stage_id] += base_score * probability
                    stage_reasons[stage_id].append(
                        f"default_for:{risk_id} * {probability:.2f}"
                    )

        ranked = sorted(stage_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        results: list[dict[str, Any]] = []
        for stage_id, score in ranked:
            stage_meta = self.stages_by_id.get(stage_id, {})
            results.append(
                {
                    "stage_id": stage_id,
                    "score": round(score, 4),
                    "name": stage_meta.get("name"),
                    "description": stage_meta.get("description"),
                    "evidence_types": stage_meta.get("evidence_types", []),
                    "reasons": stage_reasons[stage_id],
                }
            )
        return results

    def _search_corpus(
        self,
        rows: list[dict[str, Any]],
        keywords: list[str],
        top_k: int,
        source_file: str,
    ) -> list[dict[str, Any]]:
        hits: list[SearchHit] = []
        for row in rows:
            text = _extract_text(row)
            search_text = f"{text}\n{_metadata_text(row)}"
            score = _score_text(search_text, keywords)
            if score <= 0:
                continue
            hits.append(
                SearchHit(
                    score=score,
                    text=text[:1200],
                    metadata=row.get("metadata", {}),
                    source_file=source_file,
                )
            )
        hits.sort(key=lambda x: x.score, reverse=True)
        return [
            {
                "score": round(hit.score, 4),
                "text": hit.text,
                "metadata": hit.metadata,
                "source_file": hit.source_file,
            }
            for hit in hits[:top_k]
        ]

    def _build_keywords(
        self,
        query: str,
        query_signals: dict[str, Any],
        risk_candidates: list[dict[str, Any]],
        stage_candidates: list[dict[str, Any]],
    ) -> list[str]:
        keywords = [query]
        keywords.extend(item["term"] for item in query_signals["symptoms"])
        keywords.extend(item["term"] for item in query_signals["test_items"])
        keywords.extend(query_signals["products"])
        keywords.extend(item["risk_factor_id"] for item in risk_candidates)
        keywords.extend(filter(None, (item.get("name") for item in risk_candidates)))
        keywords.extend(filter(None, (item.get("description") for item in risk_candidates)))
        keywords.extend(item["stage_id"] for item in stage_candidates)
        keywords.extend(filter(None, (item.get("name") for item in stage_candidates)))
        for item in stage_candidates:
            keywords.extend(item.get("evidence_types", []))
        return _expand_keyword_variants([kw for kw in keywords if kw])

    def retrieve_evidence(
        self,
        query: str,
        query_signals: dict[str, Any],
        risk_candidates: list[dict[str, Any]],
        stage_candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        keywords = self._build_keywords(query, query_signals, risk_candidates, stage_candidates)
        return {
            "rule_layer": {
                "matched_config_entries": self._search_corpus(
                    self.config_corpus,
                    keywords,
                    top_k=6,
                    source_file="rag_corpus_config_rules.jsonl",
                )
            },
            "management_layer": {
                "production_issue_hits": self._search_corpus(
                    self.management_corpus,
                    keywords,
                    top_k=6,
                    source_file="rag_corpus_management_v2.jsonl",
                )
            },
            "standard_layer": {
                "gb_hits": self._search_corpus(
                    self.standard_corpus,
                    keywords,
                    top_k=6,
                    source_file="rag_corpus_standard_txt.jsonl",
                )
            },
            "method_layer": {
                "test_method_hits": self._search_corpus(
                    self.methods_corpus,
                    keywords,
                    top_k=6,
                    source_file=self.methods_corpus_file,
                )
            },
        }

    def query(self, query: str) -> dict[str, Any]:
        query_signals = self.analyze_query(query)
        risk_candidates = self.infer_risk_factors(query, query_signals)
        stage_candidates = self.infer_stages(risk_candidates)
        evidence = self.retrieve_evidence(query, query_signals, risk_candidates, stage_candidates)

        return {
            "query": query,
            "routing_strategy": {
                "step_1": "symptom/test_item/product detection from rules",
                "step_2": "risk factor inference from configs/risk_taxonomy.yaml",
                "step_3": "stage inference from configs/stage_rules.yaml",
                "step_4": "management corpus retrieval for production issues",
                "step_5": "GB standard retrieval for regulatory evidence",
                "step_6": "method corpus retrieval for test methods",
            },
            "signals": query_signals,
            "risk_candidates": risk_candidates,
            "stage_candidates": stage_candidates,
            "evidence": evidence,
        }
