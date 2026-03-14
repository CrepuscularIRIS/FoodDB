#!/usr/bin/env python3
"""Rebuild stage_rules.yaml from formalized risk taxonomy with MiniMax-assisted drafting."""

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
INPUT_PATH = ROOT / "knowledge" / "configs" / "risk_taxonomy.yaml"
OUTPUT_PATH = ROOT / "knowledge" / "configs" / "stage_rules.yaml"
MANIFEST_PATH = ROOT / "knowledge" / "derived" / "risk_taxonomy_vnext" / "stage_rules_rebuild_manifest.json"
INTERMEDIATE_PATH = ROOT / "knowledge" / "derived" / "risk_taxonomy_vnext" / "stage_rules_rebuild_intermediate.jsonl"

STAGES = [
    {
        "id": "farm_and_raw_milk",
        "name": "牧场与原料乳",
        "description": "奶源养殖、饲料饮水、动物健康、挤奶与原奶暂存。",
        "records_to_check": ["奶源验收记录", "原料乳检测记录", "动物健康与用药记录", "挤奶与暂存卫生记录"],
    },
    {
        "id": "raw_material_and_ingredients",
        "name": "原辅料与供应商",
        "description": "非乳原料、添加剂、包材、供应商来料与合格证明。",
        "records_to_check": ["供应商资质与审核记录", "原辅料COA", "来料验收与抽检记录", "包材合规文件"],
    },
    {
        "id": "production_and_processing",
        "name": "生产加工",
        "description": "配料、混合、杀菌、发酵、干燥、清洗消毒等厂内工艺。",
        "records_to_check": ["工艺参数记录", "CIP/SIP记录", "关键控制点监控记录", "环境监测记录"],
    },
    {
        "id": "packaging_and_filling",
        "name": "包装与灌装",
        "description": "灌装、封口、贴标、包材接触与成品放行。",
        "records_to_check": ["灌装与封口记录", "包材批次与放行记录", "在线异物检测记录", "成品放行记录"],
    },
    {
        "id": "cold_chain_and_logistics",
        "name": "冷链与物流",
        "description": "成品暂存、冷链运输、仓储与配送。",
        "records_to_check": ["冷库温度记录", "运输温度记录", "收发货交接记录", "仓储巡检记录"],
    },
    {
        "id": "retail_and_terminal_storage",
        "name": "零售与终端储存",
        "description": "门店陈列、消费端储存、终端开封与效期管理。",
        "records_to_check": ["终端巡检记录", "效期与退货记录", "消费者投诉记录", "门店温控记录"],
    },
]

STAGE_NAME_TO_ID = {row["name"]: row["id"] for row in STAGES}
ALLOWED_PRIORITIES = {"high", "medium", "low"}


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


def _clean_text(text: str, max_len: int = 40) -> str:
    value = " ".join(str(text or "").split()).strip(" ,;，；。")
    if len(value) > max_len:
        value = value[:max_len].rstrip(" ,;，；。")
    return value


def _clean_list(items: list[str], limit: int, max_len: int = 40) -> list[str]:
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


class MiniMaxStageRulesDrafter:
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

    def draft_batch(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        compact_entries = []
        for entry in entries:
            compact_entries.append(
                {
                    "risk_factor_id": entry["id"],
                    "name": entry["name"],
                    "category": entry["category"],
                    "description": entry.get("description", ""),
                    "applicable_products": entry.get("applicable_products", [])[:6],
                    "typical_symptoms": entry.get("typical_symptoms", [])[:6],
                    "vulnerable_groups": entry.get("vulnerable_groups", [])[:4],
                }
            )
        prompt = """
请为每个食品风险因子生成第一版 stage rules。
只输出 JSON 数组，不要解释，不要输出 Markdown。

每个数组元素必须包含：
- risk_factor_id
- stage_candidates
- typical_failure_points
- evidence_requirements
- records_to_check

约束：
- stage_candidates 最多 4 个
- stage_candidates 每项字段必须包含：stage_name, priority, rationale
- stage_name 只能从以下枚举中选择：
  1. 牧场与原料乳
  2. 原辅料与供应商
  3. 生产加工
  4. 包装与灌装
  5. 冷链与物流
  6. 零售与终端储存
- priority 只能是 high / medium / low
- rationale、typical_failure_points、evidence_requirements、records_to_check 都必须用短中文短语
- typical_failure_points 最多 6 个
- evidence_requirements 最多 6 个
- records_to_check 最多 6 个
- 目标是用于乳制品风险排查，不要写医学科普

entries:
""".strip() + "\n" + json.dumps(compact_entries, ensure_ascii=False)
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 1600,
            "messages": [
                {
                    "role": "system",
                    "content": "你是食品安全 stage rules 结构化助手。只输出 JSON，不输出思考过程。",
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


def _category_default(entry: dict[str, Any]) -> tuple[list[dict[str, str]], list[str], list[str], list[str]]:
    category = entry.get("category", "")
    name = str(entry.get("name", "")).lower()
    if category == "microbial":
        if any(token in name for token in ("listeria", "norovirus", "vibrio", "campylobacter", "clostridium perfringens")):
            stages = [
                {"stage": "production_and_processing", "priority": "high", "rationale": "工艺卫生失控或后污染"},
                {"stage": "cold_chain_and_logistics", "priority": "medium", "rationale": "温控失效导致存活或扩增"},
                {"stage": "retail_and_terminal_storage", "priority": "low", "rationale": "终端储存不当放大风险"},
            ]
        elif any(token in name for token in ("cronobacter", "sakazakii", "salmonella", "staphylococcus")):
            stages = [
                {"stage": "production_and_processing", "priority": "high", "rationale": "干法区或加工区交叉污染"},
                {"stage": "raw_material_and_ingredients", "priority": "medium", "rationale": "原辅料或包材带入"},
                {"stage": "packaging_and_filling", "priority": "low", "rationale": "灌装接触面或密封缺陷"},
            ]
        elif any(token in name for token in ("brucella", "escherichia coli", "stec")):
            stages = [
                {"stage": "farm_and_raw_milk", "priority": "high", "rationale": "原料乳或动物源污染带入"},
                {"stage": "production_and_processing", "priority": "medium", "rationale": "杀菌不足或二次污染"},
                {"stage": "retail_and_terminal_storage", "priority": "low", "rationale": "终端卫生管理不足"},
            ]
        else:
            stages = [
                {"stage": "production_and_processing", "priority": "high", "rationale": "生产环境与工艺卫生问题"},
                {"stage": "raw_material_and_ingredients", "priority": "medium", "rationale": "原辅料带入污染"},
            ]
        return (
            stages,
            ["清洗消毒不到位", "环境监测失控", "交叉污染", "温控管理不足"],
            ["环境监测结果", "关键工艺记录", "成品微生物检测", "偏差与纠正记录"],
            ["CIP/SIP记录", "EMP监测记录", "成品放行记录", "偏差处置记录"],
        )
    if category in {"chemical", "toxin", "residue"}:
        if any(token in name for token in ("melamine", "veterinary", "nitrite", "nitrate")):
            stages = [
                {"stage": "raw_material_and_ingredients", "priority": "high", "rationale": "原料或外购物料带入"},
                {"stage": "production_and_processing", "priority": "medium", "rationale": "配料使用或清场管理失控"},
                {"stage": "farm_and_raw_milk", "priority": "low", "rationale": "源头用药或饲养管理问题"},
            ]
        elif any(token in name for token in ("heavy metals", "arsenic", "mercury", "lead", "cadmium")):
            stages = [
                {"stage": "farm_and_raw_milk", "priority": "high", "rationale": "环境介质或饲料水源污染"},
                {"stage": "raw_material_and_ingredients", "priority": "medium", "rationale": "原辅料污染带入"},
                {"stage": "packaging_and_filling", "priority": "low", "rationale": "包材迁移或设备接触污染"},
            ]
        else:
            stages = [
                {"stage": "raw_material_and_ingredients", "priority": "high", "rationale": "原料与供应商风险主导"},
                {"stage": "production_and_processing", "priority": "medium", "rationale": "工艺控制或配料失误"},
                {"stage": "packaging_and_filling", "priority": "low", "rationale": "包材接触或标签失真"},
            ]
        return (
            stages,
            ["供应商审核不足", "来料验收不充分", "限量控制缺失", "标签与实际不符"],
            ["批次检测结果", "供应商COA", "原料限量合规证明", "偏差调查报告"],
            ["来料验收记录", "供应商审核记录", "实验室检测记录", "召回与投诉记录"],
        )
    return (
        [
            {"stage": "packaging_and_filling", "priority": "high", "rationale": "包材或异物控制失效"},
            {"stage": "production_and_processing", "priority": "medium", "rationale": "设备磨损或人员操作失误"},
            {"stage": "retail_and_terminal_storage", "priority": "low", "rationale": "终端破损或二次混入"},
        ],
        ["异物拦截失效", "设备部件脱落", "包材破损", "终端开封污染"],
        ["在线异物检测记录", "设备点检记录", "投诉样品核查", "成品外观检查记录"],
        ["金探/X光记录", "设备维护记录", "投诉处置记录", "成品放行记录"],
    )


def _sanitize_stage_candidates(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        stage_name = _clean_text(item.get("stage_name") or item.get("stage") or "", max_len=20)
        stage_id = STAGE_NAME_TO_ID.get(stage_name, stage_name)
        if stage_id not in {stage["id"] for stage in STAGES}:
            continue
        if stage_id in seen:
            continue
        seen.add(stage_id)
        priority = str(item.get("priority", "medium")).lower()
        if priority not in ALLOWED_PRIORITIES:
            priority = "medium"
        out.append(
            {
                "stage": stage_id,
                "priority": priority,
                "rationale": _clean_text(item.get("rationale", ""), max_len=28),
            }
        )
        if len(out) >= 4:
            break
    return out


class StageRulesRebuilder:
    def __init__(
        self,
        input_path: Path = INPUT_PATH,
        output_path: Path = OUTPUT_PATH,
        model: str = "MiniMax-M2.5",
        resume: bool = True,
        batch_size: int = 3,
    ) -> None:
        self.input_path = input_path
        self.output_path = output_path
        self.drafter = MiniMaxStageRulesDrafter(model=model)
        self.resume = resume
        self.batch_size = max(1, batch_size)

    def build(self) -> dict[str, Any]:
        taxonomy = yaml.safe_load(self.input_path.read_text(encoding="utf-8"))
        risk_factors = taxonomy.get("risk_factors", [])
        intermediate_rows = _read_jsonl(INTERMEDIATE_PATH) if self.resume else []
        rules: list[dict[str, Any]] = list(intermediate_rows)
        completed_ids = {row.get("risk_factor_id") for row in intermediate_rows}
        for start in range(0, len(risk_factors), self.batch_size):
            batch = [entry for entry in risk_factors[start:start + self.batch_size] if entry["id"] not in completed_ids]
            if not batch:
                continue
            llm_rows = self.drafter.draft_batch(batch)
            llm_by_id = {
                row.get("risk_factor_id"): row
                for row in llm_rows
                if isinstance(row, dict) and row.get("risk_factor_id")
            }
            for entry in batch:
                fallback_stages, fallback_failures, fallback_evidence, fallback_records = _category_default(entry)
                llm_row = llm_by_id.get(entry["id"], {})
                stage_candidates = _sanitize_stage_candidates(llm_row.get("stage_candidates", [])) or fallback_stages
                typical_failure_points = _clean_list(llm_row.get("typical_failure_points", []) or fallback_failures, 6)
                evidence_requirements = _clean_list(llm_row.get("evidence_requirements", []) or fallback_evidence, 6)
                records_to_check = _clean_list(llm_row.get("records_to_check", []) or fallback_records, 6)
                rule = {
                    "risk_factor_id": entry["id"],
                    "risk_factor_name": entry["name"],
                    "hazard_class": entry.get("category", ""),
                    "applicable_products": entry.get("applicable_products", [])[:6],
                    "stage_candidates": stage_candidates,
                    "typical_failure_points": typical_failure_points,
                    "evidence_requirements": evidence_requirements,
                    "records_to_check": records_to_check,
                    "source_basis": "minimax_assisted" if llm_row else "fallback_rule_based",
                }
                rules.append(rule)
                intermediate_rows.append(rule)
                completed_ids.add(entry["id"])
                self._write_intermediate(intermediate_rows)

        document = {
            "version": "vnext-stage-rules",
            "generated_at": datetime.now(UTC).isoformat(),
            "source": {
                "risk_taxonomy": str(self.input_path),
                "builder": "backend/stage_rules_rebuilder.py",
                "model": self.drafter.model,
            },
            "stages": STAGES,
            "default_rule": {
                "stage_candidates": [
                    {
                        "stage": "production_and_processing",
                        "priority": "medium",
                        "rationale": "默认先查生产加工环节",
                    }
                ],
                "evidence_requirements": ["需补充风险因子对应证据"],
                "records_to_check": ["原始检验与追溯记录"],
            },
            "stage_rules": rules,
        }
        self.output_path.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
        manifest = {
            "generated_at": datetime.now(UTC).isoformat(),
            "output_path": str(self.output_path),
            "risk_factor_count": len(rules),
            "stage_count": len(STAGES),
            "minimax_enabled": True,
        }
        MANIFEST_PATH.write_text(_json_dumps(manifest) + "\n", encoding="utf-8")
        return manifest

    def _write_intermediate(self, rows: list[dict[str, Any]]) -> None:
        INTERMEDIATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with INTERMEDIATE_PATH.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(_json_dumps(row) + "\n")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild stage_rules.yaml from formal risk taxonomy.")
    parser.add_argument("--input-path", default=str(INPUT_PATH))
    parser.add_argument("--output-path", default=str(OUTPUT_PATH))
    parser.add_argument("--model", default="MiniMax-M2.5")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--batch-size", type=int, default=3)
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    rebuilder = StageRulesRebuilder(
        input_path=Path(args.input_path),
        output_path=Path(args.output_path),
        model=args.model,
        resume=not args.no_resume,
        batch_size=args.batch_size,
    )
    manifest = rebuilder.build()
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
