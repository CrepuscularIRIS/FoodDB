#!/usr/bin/env python3
"""Fetch dairy-focused medical literature for future risk taxonomy rebuilding."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import time
import urllib.parse
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import ParseError

import yaml

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = ROOT / "knowledge"
CONFIG_PATH = KNOWLEDGE_DIR / "configs" / "source_registry.yaml"
DEFAULT_OUTPUT_DIR = KNOWLEDGE_DIR / "derived" / "risk_taxonomy_raw"


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
        except (urllib.error.URLError, TimeoutError, http.client.RemoteDisconnected, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(1.0 + attempt * 1.5)
    if last_error is not None:
        raise last_error
    raise RuntimeError("JSON request failed without exception")


def _request_text(url: str, timeout: int = 60) -> str:
    last_error: Exception | None = None
    for attempt in range(4):
        request = urllib.request.Request(url, headers={"User-Agent": "standalone-food-risk-kb/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, http.client.RemoteDisconnected) as exc:
            last_error = exc
            time.sleep(1.0 + attempt * 1.5)
    if last_error is not None:
        raise last_error
    raise RuntimeError("Text request failed without exception")


def _chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def _pmid_url(pmid: str) -> str:
    return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"


def _pmcid_url(pmcid: str) -> str:
    return f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"


@dataclass
class QuerySpec:
    query_id: str
    query: str
    hazard_hint: str
    product_domain: str


class MedicalLiteratureFetcher:
    def __init__(
        self,
        config_path: Path = CONFIG_PATH,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        pubmed_retmax: int = 200,
        europe_pmc_page_size: int = 200,
    ) -> None:
        self.config_path = config_path
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        self.env = _read_env(ROOT / ".env")
        self.pubmed_api_key = (
            os.environ.get("PUBMED_API_KEY")
            or os.environ.get("PubMed-API-KEY")
            or self.env.get("PUBMED_API_KEY")
            or self.env.get("PubMed-API-KEY")
        )
        self.pubmed_retmax = pubmed_retmax
        self.europe_pmc_page_size = europe_pmc_page_size
        self.query_specs = [
            QuerySpec(
                query_id=item["id"],
                query=item["query"],
                hazard_hint=item["hazard_hint"],
                product_domain=item["product_domain"],
            )
            for item in self.config.get("medical_literature_queries", [])
        ]

    def fetch_all(self) -> dict[str, Any]:
        pubmed_records = self.fetch_pubmed_records()
        europe_pmc_records = self.fetch_europe_pmc_records()

        pmids: list[str] = []
        for row in pubmed_records:
            if row.get("pmid"):
                pmids.append(str(row["pmid"]))
        for row in europe_pmc_records:
            if row.get("pmid"):
                pmids.append(str(row["pmid"]))
        pmids = list(dict.fromkeys(pmids))

        pubtator_rows = self.fetch_pubtator_annotations(pmids)

        manifest = {
            "generated_at": datetime.now(UTC).isoformat(),
            "output_dir": str(self.output_dir),
            "query_count": len(self.query_specs),
            "pubmed_records": len(pubmed_records),
            "europe_pmc_records": len(europe_pmc_records),
            "pubtator_rows": len(pubtator_rows),
            "unique_pmids": len(pmids),
            "pubmed_api_key_configured": bool(self.pubmed_api_key),
        }

        _write_jsonl(self.output_dir / "pubmed_records.jsonl", pubmed_records)
        _write_jsonl(self.output_dir / "europe_pmc_records.jsonl", europe_pmc_records)
        _write_jsonl(self.output_dir / "pubtator_annotations.jsonl", pubtator_rows)
        _write_json(self.output_dir / "fetch_manifest.json", manifest)
        return manifest

    def fetch_pubmed_records(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_pmids: set[str] = set()

        for spec in self.query_specs:
            ids = self._pubmed_search(spec.query)
            if not ids:
                continue
            for batch in _chunked(ids, 100):
                rows.extend(self._pubmed_fetch_batch(batch, spec, seen_pmids))
                time.sleep(0.34 if self.pubmed_api_key else 0.5)
        return rows

    def _pubmed_search(self, query: str) -> list[str]:
        params = {
            "db": "pubmed",
            "retmode": "json",
            "sort": "relevance",
            "retmax": str(self.pubmed_retmax),
            "term": query,
        }
        if self.pubmed_api_key:
            params["api_key"] = self.pubmed_api_key
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode(params)
        payload = _request_json(url)
        return payload.get("esearchresult", {}).get("idlist", [])

    def _pubmed_fetch_batch(
        self,
        pmids: list[str],
        spec: QuerySpec,
        seen_pmids: set[str],
    ) -> list[dict[str, Any]]:
        params = {
            "db": "pubmed",
            "retmode": "xml",
            "id": ",".join(pmids),
        }
        if self.pubmed_api_key:
            params["api_key"] = self.pubmed_api_key
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(params)
        last_error: Exception | None = None
        root: ET.Element | None = None
        for attempt in range(3):
            try:
                xml_text = _request_text(url)
                root = ET.fromstring(xml_text)
                break
            except ParseError as exc:
                last_error = exc
                time.sleep(1.0 + attempt)
                continue
        if root is None:
            if last_error is not None:
                raise last_error
            return []

        rows: list[dict[str, Any]] = []
        for article in root.findall(".//PubmedArticle"):
            pmid = article.findtext(".//MedlineCitation/PMID", default="").strip()
            if not pmid or pmid in seen_pmids:
                continue
            seen_pmids.add(pmid)
            title = "".join(article.findtext(".//ArticleTitle", default="").split())
            abstract_parts: list[str] = []
            for node in article.findall(".//Abstract/AbstractText"):
                label = node.attrib.get("Label")
                text = "".join(node.itertext()).strip()
                if not text:
                    continue
                abstract_parts.append(f"{label}: {text}" if label else text)
            pub_year = (
                article.findtext(".//PubDate/Year")
                or article.findtext(".//ArticleDate/Year")
                or article.findtext(".//PubMedPubDate[@PubStatus='pubmed']/Year")
            )
            journal = article.findtext(".//Journal/Title", default="").strip()
            doi = ""
            for id_node in article.findall(".//ArticleId"):
                if id_node.attrib.get("IdType") == "doi":
                    doi = (id_node.text or "").strip()
                    if doi:
                        break
            mesh_terms = [
                "".join(node.itertext()).strip()
                for node in article.findall(".//MeshHeading/DescriptorName")
                if "".join(node.itertext()).strip()
            ]
            rows.append(
                {
                    "record_type": "medical_literature",
                    "source": "pubmed",
                    "query_id": spec.query_id,
                    "query": spec.query,
                    "hazard_hint": spec.hazard_hint,
                    "product_domain": spec.product_domain,
                    "pmid": pmid,
                    "pmcid": "",
                    "title": title,
                    "abstract": "\n".join(abstract_parts).strip(),
                    "journal": journal,
                    "year": pub_year,
                    "doi": doi,
                    "mesh_terms": mesh_terms,
                    "source_url": _pmid_url(pmid),
                }
            )
        return rows

    def fetch_europe_pmc_records(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        for spec in self.query_specs:
            params = {
                "query": spec.query,
                "format": "json",
                "pageSize": str(self.europe_pmc_page_size),
                "resultType": "core",
            }
            url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode(params)
            payload = _request_json(url)
            for item in payload.get("resultList", {}).get("result", []):
                pmid = str(item.get("pmid", "")).strip()
                pmcid = str(item.get("pmcid", "")).strip()
                dedupe_key = pmid or pmcid or str(item.get("id", "")).strip()
                if not dedupe_key or dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)
                source_url = _pmid_url(pmid) if pmid else (_pmcid_url(pmcid) if pmcid else item.get("fullTextUrl", ""))
                rows.append(
                    {
                        "record_type": "medical_literature",
                        "source": "europe_pmc",
                        "query_id": spec.query_id,
                        "query": spec.query,
                        "hazard_hint": spec.hazard_hint,
                        "product_domain": spec.product_domain,
                        "pmid": pmid,
                        "pmcid": pmcid,
                        "title": item.get("title", ""),
                        "abstract": item.get("abstractText", ""),
                        "journal": item.get("journalTitle", ""),
                        "year": str(item.get("pubYear", "")).strip(),
                        "doi": item.get("doi", ""),
                        "mesh_terms": [],
                        "source_url": source_url,
                    }
                )
            time.sleep(0.2)
        return rows

    def fetch_pubtator_annotations(self, pmids: list[str]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for batch in _chunked(pmids, 100):
            url = (
                "https://www.ncbi.nlm.nih.gov/research/pubtator-api/publications/export/biocjson?"
                + urllib.parse.urlencode({"pmids": ",".join(batch)})
            )
            try:
                payload = _request_json(url)
            except Exception:
                continue
            if isinstance(payload, dict):
                documents = payload.get("documents", []) or payload.get("PubTator3", [])
            else:
                documents = []
            for document in documents:
                pmid = str(document.get("id", "")).strip()
                passages = document.get("passages", []) or []
                annotations: list[dict[str, Any]] = []
                for passage in passages:
                    for annotation in passage.get("annotations", []) or []:
                        infons = annotation.get("infons", {}) or {}
                        text = annotation.get("text", "")
                        annotations.append(
                            {
                                "text": text,
                                "type": infons.get("type", ""),
                                "identifier": infons.get("identifier", ""),
                            }
                        )
                rows.append(
                    {
                        "record_type": "medical_annotation",
                        "source": "pubtator_central",
                        "pmid": pmid,
                        "annotation_count": len(annotations),
                        "annotations": annotations,
                        "source_url": _pmid_url(pmid) if pmid else "",
                    }
                )
            time.sleep(0.2)
        return rows


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch dairy medical literature for future risk taxonomy.")
    parser.add_argument(
        "--config",
        default=str(CONFIG_PATH),
        help="Path to source registry config.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for raw fetched materials.",
    )
    parser.add_argument(
        "--pubmed-retmax",
        type=int,
        default=200,
        help="Max PubMed search results per query.",
    )
    parser.add_argument(
        "--europe-pmc-page-size",
        type=int,
        default=200,
        help="Europe PMC page size per query.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    fetcher = MedicalLiteratureFetcher(
        config_path=Path(args.config),
        output_dir=Path(args.output_dir),
        pubmed_retmax=args.pubmed_retmax,
        europe_pmc_page_size=args.europe_pmc_page_size,
    )
    manifest = fetcher.fetch_all()
    print(_json_dumps(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
