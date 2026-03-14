#!/usr/bin/env python3
"""Deterministic GB text processing agent for `knowledge/standard_txt/`."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import textwrap
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = ROOT / "knowledge"
STANDARD_TXT_DIR = KNOWLEDGE_DIR / "standard_txt"
DEFAULT_OUTPUT_DIR = KNOWLEDGE_DIR / "derived" / "gb_agent"

GB_ID_RE = re.compile(r"GB[T]?\s*\d+(?:\.\d+)?(?:\s*[-—]\s*\d{4})?")
DATE_RE = re.compile(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})")
SECTION_RE = re.compile(r"^(\d+(?:\s*\.\s*\d+)*)\s+(.+)$")
METHOD_RE = re.compile(r"^第\s*[一二三四五六七八九十]+\s*法\s*(.*)$")
APPENDIX_RE = re.compile(r"^附\s*录\s*([A-ZＡ-Ｚ一二三四五六七八九十])\s*(.*)$")
TABLE_RE = re.compile(r"^表\s*([A-Za-z0-9一二三四五六七八九十()（）\-]+)\s*(.*)$")
STD_REF_RE = re.compile(r"GB[T]?\s*\d+(?:\.\d+)?(?:\s*[-—]\s*\d{4})?")


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


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


def _normalize_standard_id(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.replace("—", "-")).strip()
    normalized = re.sub(r"\s*-\s*", "-", normalized)
    normalized = re.sub(r"GBT", "GBT", normalized)
    return normalized


def _compact_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\ufeff", "")
    text = text.replace("．", ".").replace("。", "。").replace("：", "：")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"(?<=\d)\s*\.\s*(?=\d)", ".", text)
    text = re.sub(r"(?<=GB)\s+(?=\d)", " ", text)
    text = re.sub(r"(?<=\d)\s*[-—]\s*(?=\d{4})", "-", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


def _slugify_filename(path: Path) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff\-\.]+", "_", path.stem).strip("_")


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。；;])\s*|\n+", text)
    return [part.strip() for part in parts if part.strip()]


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _safe_write_json(path: Path, data: Any) -> None:
    path.write_text(_json_dumps(data) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_json_dumps(row) + "\n")


def _strip_think_blocks(text: str) -> str:
    text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def _extract_json_text(text: str) -> str:
    text = _strip_think_blocks(text)
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()
    brace_match = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    if brace_match:
        return brace_match.group(1).strip()
    return text.strip()


def _looks_like_title(line: str) -> bool:
    if not line:
        return False
    generic = {
        "中华人民共和国国家标准",
        "食品安全国家标准",
        "发布",
        "实施",
        "前言",
    }
    if line in generic:
        return False
    if line.startswith(("本标准", "——", "—", "a)", "b)", "c)", "d)")):
        return False
    if "相比" in line or "主要变化如下" in line:
        return False
    if DATE_RE.search(line):
        return False
    if GB_ID_RE.search(line):
        return False
    return len(line) >= 2


def _role_labels(text: str) -> list[str]:
    labels: list[str] = []
    checks = [
        ("scope", ["范围", "适用范围", "适用于"]),
        ("definition", ["术语和定义", "定义"]),
        ("requirement", ["技术要求", "要求", "感官要求", "理化指标"]),
        ("limit_rule", ["限量", "最大使用量", "最大残留量", "指标"]),
        ("method", ["检验方法", "操作步骤", "检验程序", "培养基和试剂"]),
        ("classification", ["分类", "类别", "编码"]),
        ("labeling", ["标识", "标签", "应标明"]),
        ("process_control", ["生产", "卫生规范", "清洗", "杀菌", "贮存", "运输"]),
        ("reference", ["应符合 GB", "按 GB", "见 A.", "引用"]),
        ("table", ["表 ", "|"]),
    ]
    for label, patterns in checks:
        if any(pattern in text for pattern in patterns):
            labels.append(label)
    return labels


def _classify_standard(standard_id: str, title: str, raw_text: str) -> tuple[str, str]:
    title_text = f"{standard_id} {title}".strip()
    prefix = standard_id.replace(" ", "")
    text = f"{title_text}\n{raw_text[:3000]}"

    if prefix.startswith(("GB5009", "GB4789", "GBT317", "GB5413")) or "检验" in title_text:
        return "method_standard", "method_standard"
    if "生产卫生规范" in text or prefix.startswith("GB12693"):
        return "process_control", "process_control"
    if any(token in text for token in ["限量", "使用标准", "污染物", "食品添加剂", "真菌毒素"]):
        return "gb_rule", "gb_rule"
    if any(token in text for token in ["乳粉", "灭菌乳", "巴氏杀菌乳", "调制乳", "发酵乳", "乳制品"]):
        return "product_standard", "product_standard"
    return "gb_text", "gb_text"


def _infer_product_domain(title: str, raw_text: str) -> str:
    dairy_tokens = ["乳", "奶", "婴幼儿配方", "发酵乳", "乳粉", "乳制品", "生乳"]
    general_rule_tokens = ["污染物限量", "食品添加剂使用标准", "良好生产规范", "检验", "微生物学检验"]
    if any(token in title for token in general_rule_tokens) and not any(token in title for token in dairy_tokens):
        return "general_food"
    title_hits = sum(token in title for token in dairy_tokens)
    body_hits = sum(raw_text[:4000].count(token) for token in dairy_tokens)
    if title_hits >= 1 or body_hits >= 8:
        return "dairy"
    return "general_food"


def _extract_authority(raw_text: str) -> list[str]:
    authorities: list[str] = []
    candidates = [
        "中华人民共和国国家卫生健康委员会",
        "国家卫生健康委员会",
        "国家卫生和计划生育委员会",
        "国家市场监督管理总局",
        "中华人民共和国农业农村部",
    ]
    for item in candidates:
        if item in raw_text:
            authorities.append(item)
    return _dedupe(authorities)


def _extract_standard_refs(text: str) -> list[str]:
    return _dedupe([_normalize_standard_id(match.group(0)) for match in STD_REF_RE.finditer(text)])


def _extract_replaces(text: str) -> list[str]:
    hits: list[str] = []
    for line in text.splitlines()[:40]:
        if "代替" not in line:
            continue
        refs = _extract_standard_refs(line)
        for ref in refs:
            hits.append(ref)
    return _dedupe(hits)


def _extract_dates(raw_text: str) -> dict[str, str | None]:
    found = [match.groups() for match in DATE_RE.finditer(raw_text[:2000])]
    normalized = [f"{year}-{int(month):02d}-{int(day):02d}" for year, month, day in found]
    issue_date = normalized[0] if normalized else None
    effective_date = normalized[1] if len(normalized) > 1 else None
    return {"issue_date": issue_date, "effective_date": effective_date}


def _extract_standard_id(filename: str, raw_text: str) -> str:
    filename_hit = GB_ID_RE.search(filename)
    if filename_hit:
        return _normalize_standard_id(filename_hit.group(0))
    for line in raw_text.splitlines()[:15]:
        hit = GB_ID_RE.search(line)
        if hit:
            return _normalize_standard_id(hit.group(0))
    return _normalize_standard_id(filename.replace(".txt", ""))


def _extract_title(lines: list[str], standard_id: str) -> str:
    standard_token = standard_id.replace(" ", "")
    for line in lines[:10]:
        cleaned = _clean_line(line)
        if standard_token and standard_token in cleaned.replace(" ", ""):
            suffix = cleaned.replace(standard_id, "").strip(" 《》()（）-")
            if suffix and _looks_like_title(suffix):
                return suffix[:200]

    standard_idx = 0
    for idx, line in enumerate(lines[:30]):
        cleaned = _clean_line(line)
        if standard_id and standard_token in cleaned.replace(" ", ""):
            standard_idx = idx
            break

    for idx, line in enumerate(lines[:80]):
        cleaned = _clean_line(line)
        if cleaned == "食品安全国家标准" and idx + 1 < len(lines):
            next_line = _clean_line(lines[idx + 1])
            if _looks_like_title(next_line):
                return f"{cleaned}{next_line}"[:200]
        if cleaned.startswith("食品安全国家标准") and len(cleaned) > len("食品安全国家标准"):
            return cleaned[:200]

    prefix = ""
    candidates: list[str] = []
    for line in lines[standard_idx + 1: standard_idx + 15]:
        cleaned = _clean_line(line)
        if not cleaned:
            continue
        if cleaned == "食品安全国家标准":
            prefix = cleaned
            continue
        if cleaned.startswith("食品安全国家标准") and len(cleaned) > len("食品安全国家标准"):
            return cleaned[:200]
        if cleaned in {"前言", "发布", "实施"}:
            break
        if SECTION_RE.match(cleaned):
            break
        if _looks_like_title(cleaned):
            title = f"{prefix}{cleaned}" if prefix and not cleaned.startswith(prefix) else cleaned
            candidates.append(title)
            if len(candidates) >= 2:
                break
    if candidates:
        return candidates[0][:200].strip()
    for line in lines[:20]:
        cleaned = _clean_line(line)
        if _looks_like_title(cleaned):
            return cleaned[:200]
    return standard_id


@dataclass
class Section:
    section_id: str
    heading: str
    heading_level: int
    role_labels: list[str]
    text: str
    table_blocks: list[str]


class MinimaxClient:
    def __init__(self, env_path: Path, model: str, cache_path: Path, enabled: bool = True) -> None:
        env = _read_env(env_path)
        self.enabled = enabled
        self.model = model
        self.api_key = env.get("minimaxi-api-key") or os.environ.get("MINIMAX_API_KEY", "")
        self.base_url = env.get("url") or os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.chat/v1/openai")
        self.cache_path = cache_path
        self.cache = self._load_cache()
        self.request_timeout = 8

    def _candidate_base_urls(self) -> list[str]:
        candidates = [self.base_url]
        normalized = self.base_url.rstrip("/")
        if normalized.endswith("/openai"):
            candidates.append(normalized[: -len("/openai")])
        if "api.minimax.chat" in normalized:
            candidates.append("https://api.minimaxi.com/v1")
            candidates.append("https://api.minimax.io/v1")
        elif "api.minimaxi.com" in normalized:
            candidates.append("https://api.minimax.io/v1")
        else:
            candidates.append("https://api.minimaxi.com/v1")
            candidates.append("https://api.minimax.io/v1")
        return _dedupe([item.rstrip("/") for item in candidates if item])

    def _extract_content(self, body: dict[str, Any]) -> str:
        content = (
            body.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "{}")
        )
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
            return "".join(parts)
        return "{}"

    def _request_annotation(self, payload: dict[str, Any]) -> dict[str, Any]:
        preferred: list[str] = [self.base_url.rstrip("/")]
        for candidate in self._candidate_base_urls():
            if candidate not in preferred:
                preferred.append(candidate)

        for base_url in preferred:
            request = urllib.request.Request(
                f"{base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.request_timeout) as response:
                    body = json.loads(response.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
                continue

            content = _extract_json_text(self._extract_content(body))
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and parsed:
                return parsed
        return {}

    def _load_cache(self) -> dict[str, Any]:
        if not self.cache_path.exists():
            return {}
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def save_cache(self) -> None:
        if not self.enabled:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        _safe_write_json(self.cache_path, self.cache)

    def annotate_standard(self, metadata: dict[str, Any], sections: list[Section]) -> dict[str, Any]:
        if not self.enabled or not self.api_key:
            return {}

        section_digest = [
            {
                "heading": s.heading[:40],
                "roles": s.role_labels[:4],
                "preview": _clean_line(s.text)[:120],
            }
            for s in sections[:6]
        ]
        prompt = textwrap.dedent(
            f"""
            你是食品国标标准化助手，只输出一个 JSON 对象，不要输出思考过程，不要输出 <think> 标签。
            字段要求：
            - category: gb_rule | gb_text | method_standard | process_control | product_standard
            - product_domain: dairy | general_food
            - status: current | amendment | unknown
            - tags: 最多 5 个短标签

            输入元信息：
            {json.dumps(metadata, ensure_ascii=False)}

            输入章节摘要：
            {json.dumps(section_digest, ensure_ascii=False)}
            """
        ).strip()
        key = _sha1(prompt)
        if key in self.cache:
            return self.cache[key]

        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 900,
            "messages": [
                {"role": "system", "content": "你只输出最终 JSON，不要输出思考过程，不要输出 <think> 标签。"},
                {"role": "user", "content": prompt},
            ],
        }
        parsed = self._request_annotation(payload)
        if parsed:
            self.cache[key] = parsed
        return parsed


class GBProcessingAgent:
    def __init__(
        self,
        input_dir: Path = STANDARD_TXT_DIR,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        model: str = "MiniMax-M2.5",
        use_llm: bool = True,
    ) -> None:
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.llm = MinimaxClient(
            env_path=ROOT / ".env",
            model=model,
            cache_path=self.output_dir / "llm_cache.json",
            enabled=use_llm,
        )

    def process_all(self, max_files: int | None = None) -> dict[str, Any]:
        metadata_rows: list[dict[str, Any]] = []
        section_rows: list[dict[str, Any]] = []
        chunk_rows: list[dict[str, Any]] = []
        rule_rows: list[dict[str, Any]] = []

        files = sorted(self.input_dir.glob("*.txt"))
        if max_files is not None:
            files = files[:max_files]

        for path in files:
            result = self.process_file(path)
            metadata_rows.append(result["metadata"])
            section_rows.extend(result["sections"])
            chunk_rows.extend(result["chunks"])
            rule_rows.extend(result["rules"])

        manifest = {
            "generated_at": datetime.now(UTC).isoformat(),
            "input_dir": str(self.input_dir),
            "output_dir": str(self.output_dir),
            "files_processed": len(files),
            "metadata_rows": len(metadata_rows),
            "section_rows": len(section_rows),
            "chunk_rows": len(chunk_rows),
            "rule_rows": len(rule_rows),
            "llm_enabled": self.llm.enabled and bool(self.llm.api_key),
        }

        _write_jsonl(self.output_dir / "gb_standard_metadata.jsonl", metadata_rows)
        _write_jsonl(self.output_dir / "gb_standard_sections.jsonl", section_rows)
        _write_jsonl(self.output_dir / "gb_standard_chunks.jsonl", chunk_rows)
        _write_jsonl(self.output_dir / "gb_standard_rules.jsonl", rule_rows)
        _safe_write_json(self.output_dir / "build_manifest.json", manifest)
        self.llm.save_cache()
        return manifest

    def process_file(self, path: Path) -> dict[str, Any]:
        raw_text = _compact_text(path.read_text(encoding="utf-8", errors="ignore"))
        lines = [line.rstrip() for line in raw_text.splitlines()]
        standard_id = _extract_standard_id(path.name, raw_text)
        title = _extract_title(lines, standard_id)
        category, knowledge_type = _classify_standard(standard_id, title, raw_text)
        references = _extract_standard_refs(raw_text[:12000])
        replaces = _extract_replaces(raw_text)
        dates = _extract_dates(raw_text)
        sections = self._parse_sections(raw_text)
        llm_annotation = self.llm.annotate_standard(
            metadata={
                "standard_id": standard_id,
                "title": title,
                "category": category,
                "knowledge_type": knowledge_type,
            },
            sections=sections,
        )

        category = llm_annotation.get("category", category)
        product_domain = llm_annotation.get("product_domain", _infer_product_domain(title, raw_text))
        status = llm_annotation.get("status") or (
            "amendment" if "修改单" in title or "修改单" in path.name else "current"
        )

        metadata = {
            "id": f"meta::{_slugify_filename(path)}",
            "record_type": "gb_standard_metadata",
            "source_file": path.name,
            "source_path": str(path),
            "standard_id": standard_id,
            "title": title,
            "year": standard_id.split("-")[-1] if "-" in standard_id else None,
            "status": status,
            "category": category,
            "product_domain": product_domain,
            "knowledge_type": knowledge_type,
            "authority": _extract_authority(raw_text),
            "issue_date": dates["issue_date"],
            "effective_date": dates["effective_date"],
            "references_standards": [ref for ref in references if ref != standard_id],
            "replaces_standards": [ref for ref in replaces if ref != standard_id],
            "llm_tags": llm_annotation.get("tags", []),
        }

        section_rows = self._build_section_rows(path, standard_id, sections)
        chunk_rows = self._build_chunks(path, standard_id, title, category, sections)
        rule_rows = self._build_rules(path, standard_id, title, category, sections)
        return {
            "metadata": metadata,
            "sections": section_rows,
            "chunks": chunk_rows,
            "rules": rule_rows,
        }

    def _parse_sections(self, raw_text: str) -> list[Section]:
        sections: list[Section] = []
        current_heading = "全文概览"
        current_level = 0
        current_id = "overview"
        body_lines: list[str] = []
        section_counter = 0

        def flush() -> None:
            nonlocal section_counter, body_lines, current_heading, current_level, current_id
            text = "\n".join(line for line in body_lines if line.strip()).strip()
            if not text and current_heading == "全文概览" and sections:
                body_lines = []
                return
            table_blocks = self._extract_table_blocks(text)
            sections.append(
                Section(
                    section_id=current_id or f"section_{section_counter}",
                    heading=current_heading,
                    heading_level=current_level,
                    role_labels=_role_labels(f"{current_heading}\n{text}"),
                    text=text,
                    table_blocks=table_blocks,
                )
            )
            section_counter += 1
            body_lines = []

        for raw_line in raw_text.splitlines():
            line = _clean_line(raw_line)
            if not line:
                body_lines.append("")
                continue

            heading_match = SECTION_RE.match(line)
            method_match = METHOD_RE.match(line)
            appendix_match = APPENDIX_RE.match(line)
            table_match = TABLE_RE.match(line)

            if heading_match:
                flush()
                raw_no = heading_match.group(1).replace(" ", "")
                current_id = raw_no
                current_heading = f"{raw_no} {heading_match.group(2).strip()}".strip()
                current_level = raw_no.count(".") + 1
                continue
            if method_match:
                flush()
                current_id = f"method_{section_counter}"
                suffix = method_match.group(1).strip()
                current_heading = f"第法 {suffix}".strip()
                current_level = 1
                continue
            if appendix_match:
                flush()
                appendix_id = appendix_match.group(1)
                suffix = appendix_match.group(2).strip()
                current_id = f"appendix_{appendix_id}"
                current_heading = f"附录{appendix_id} {suffix}".strip()
                current_level = 1
                continue
            if table_match and body_lines:
                flush()
                table_id = table_match.group(1)
                suffix = table_match.group(2).strip()
                current_id = f"table_{table_id}"
                current_heading = f"表{table_id} {suffix}".strip()
                current_level = 2
                continue

            body_lines.append(line)

        flush()
        return [section for section in sections if section.text or section.heading]

    def _extract_table_blocks(self, text: str) -> list[str]:
        blocks: list[str] = []
        current: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if "|" in stripped or stripped.startswith("表 "):
                current.append(stripped)
                continue
            if current:
                blocks.append("\n".join(current))
                current = []
        if current:
            blocks.append("\n".join(current))
        return blocks

    def _build_section_rows(
        self,
        path: Path,
        standard_id: str,
        sections: list[Section],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index, section in enumerate(sections):
            rows.append(
                {
                    "id": f"section::{_slugify_filename(path)}::{index}",
                    "record_type": "gb_standard_section",
                    "source_file": path.name,
                    "standard_id": standard_id,
                    "section_id": section.section_id,
                    "heading": section.heading,
                    "heading_level": section.heading_level,
                    "role_labels": section.role_labels,
                    "table_blocks": section.table_blocks,
                    "content": section.text,
                }
            )
        return rows

    def _build_chunks(
        self,
        path: Path,
        standard_id: str,
        title: str,
        category: str,
        sections: list[Section],
        chunk_size: int = 1200,
        overlap: int = 180,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for section_index, section in enumerate(sections):
            if not section.text:
                continue
            payload = (
                f"[GB_STANDARD]\n"
                f"standard_id={standard_id}\n"
                f"title={title}\n"
                f"section={section.heading}\n"
                f"category={category}\n"
                f"roles={','.join(section.role_labels)}\n"
                f"{section.text}"
            )
            start = 0
            chunk_index = 0
            while start < len(payload):
                end = min(len(payload), start + chunk_size)
                chunk_text = payload[start:end].strip()
                if chunk_text:
                    rows.append(
                        {
                            "id": f"chunk::{_slugify_filename(path)}::{section_index}::{chunk_index}",
                            "record_type": "gb_standard_chunk",
                            "source": "standard_txt_agent",
                            "source_file": path.name,
                            "source_url": f"file://standard/txt/{path.name}",
                            "standard_id": standard_id,
                            "chunk_index": chunk_index,
                            "section_index": section_index,
                            "chunk_text": chunk_text,
                            "metadata": {
                                "title": title,
                                "category": category,
                                "section_heading": section.heading,
                                "section_id": section.section_id,
                                "role_labels": section.role_labels,
                                "record_type": "gb_text",
                            },
                        }
                    )
                    chunk_index += 1
                if end >= len(payload):
                    break
                start = max(end - overlap, start + 1)
        return rows

    def _build_rules(
        self,
        path: Path,
        standard_id: str,
        title: str,
        category: str,
        sections: list[Section],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rule_index = 0
        seen_keys: set[str] = set()

        def append_rule(row: dict[str, Any]) -> None:
            nonlocal rule_index
            key = _sha1(
                "||".join(
                    [
                        row.get("source_file", ""),
                        row.get("section_heading", ""),
                        row.get("rule_type", ""),
                        row.get("text", ""),
                    ]
                )
            )
            if key in seen_keys:
                return
            seen_keys.add(key)
            row["id"] = f"rule::{_slugify_filename(path)}::{rule_index}"
            rows.append(row)
            rule_index += 1

        for section in sections:
            if not section.text:
                continue
            for sentence in _split_sentences(section.text):
                if not any(
                    token in sentence
                    for token in [
                        "应符合",
                        "不应",
                        "不得",
                        "限量",
                        "最大使用量",
                        "最大残留量",
                        "适用于",
                        "应标明",
                        "应按",
                    ]
                ):
                    continue
                append_rule(
                    {
                        "record_type": "gb_standard_rule",
                        "source_file": path.name,
                        "standard_id": standard_id,
                        "title": title,
                        "category": category,
                        "section_heading": section.heading,
                        "rule_type": "sentence_rule",
                        "role_labels": _dedupe(section.role_labels + _role_labels(sentence)),
                        "text": sentence,
                        "references_standards": _extract_standard_refs(sentence),
                    }
                )

            for table_block in section.table_blocks:
                for row in self._table_rules(
                    path=path,
                    standard_id=standard_id,
                    title=title,
                    category=category,
                    section=section,
                    table_block=table_block,
                ):
                    append_rule(row)

            if "限量" in section.heading and not section.table_blocks:
                for line in section.text.splitlines():
                    stripped = line.strip()
                    if not stripped:
                        continue
                    if re.search(r"\d+(?:\.\d+)?\s*(?:mg/kg|g/kg|mg/L|CFU/g|CFU/mL|%)?", stripped):
                        append_rule(
                            {
                                "record_type": "gb_standard_rule",
                                "source_file": path.name,
                                "standard_id": standard_id,
                                "title": title,
                                "category": category,
                                "section_heading": section.heading,
                                "rule_type": "limit_line",
                                "role_labels": _dedupe(section.role_labels + ["limit_rule"]),
                                "text": stripped,
                                "references_standards": _extract_standard_refs(stripped),
                            }
                        )
        return rows

    def _table_rules(
        self,
        path: Path,
        standard_id: str,
        title: str,
        category: str,
        section: Section,
        table_block: str,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for line in table_block.splitlines():
            stripped = line.strip()
            if "|" not in stripped:
                continue
            cells = [cell.strip() for cell in stripped.split("|") if cell.strip()]
            if not cells:
                continue
            if len(cells) >= 2 and any(char.isdigit() for char in stripped):
                rows.append(
                    {
                        "record_type": "gb_standard_rule",
                        "source_file": path.name,
                        "standard_id": standard_id,
                        "title": title,
                        "category": category,
                        "section_heading": section.heading,
                        "rule_type": "table_row",
                        "role_labels": _dedupe(section.role_labels + ["table", "limit_rule"]),
                        "text": stripped,
                        "table_cells": cells,
                        "references_standards": _extract_standard_refs(stripped),
                    }
                )
        return rows


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build GB structured assets from knowledge/standard_txt.")
    parser.add_argument(
        "--input-dir",
        default=str(STANDARD_TXT_DIR),
        help="Input directory of GB txt files.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for structured assets.",
    )
    parser.add_argument(
        "--model",
        default="MiniMax-M2.5",
        help="OpenAI-compatible model name for MiniMax.",
    )
    parser.add_argument(
        "--disable-llm",
        action="store_true",
        help="Disable MiniMax annotation and run deterministic parsing only.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Only process the first N files for debugging.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    agent = GBProcessingAgent(
        input_dir=Path(args.input_dir),
        output_dir=Path(args.output_dir),
        model=args.model,
        use_llm=not args.disable_llm,
    )
    manifest = agent.process_all(max_files=args.max_files)
    print(_json_dumps(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
