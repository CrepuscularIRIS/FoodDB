from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MEDIA_ROOT = Path("/home/yarizakurahime/Agents/winteragent/MediaCrawler/data")
DEFAULT_ENTERPRISE_CSV = PROJECT_ROOT / "data" / "merged" / "enterprise_master.csv"
OPINION_DIR = PROJECT_ROOT / "data" / "opinion"
PROCESSED_DIR = OPINION_DIR / "processed"
RAW_DIR = OPINION_DIR / "raw"
FEATURE_CSV = PROCESSED_DIR / "enterprise_opinion_features.csv"
SUMMARY_JSON = PROCESSED_DIR / "opinion_import_summary.json"


NEGATIVE_WORDS = [
    "变质", "异味", "酸败", "腹泻", "呕吐", "拉肚子", "恶心", "中毒", "霉", "发霉",
    "过期", "召回", "投诉", "问题奶", "黑心", "污染", "不合格", "致病", "细菌", "发热",
]
POSITIVE_WORDS = [
    "放心", "安全", "可靠", "合规", "优质", "好评", "推荐", "达标", "通过", "满意",
]
RISK_KEYWORDS = [
    "召回", "不合格", "污染", "致病", "细菌", "霉菌", "过期", "异物", "投诉", "中毒",
    "变质", "异味", "腹泻", "呕吐", "黑榜", "处罚",
]

QINGMING_KEYWORDS = [
    "清明",
    "清明节",
    "祭扫",
    "踏青",
    "小长假",
]

DAIRY_OPINION_KEYWORDS = [
    "牛奶",
    "乳制品",
    "奶粉",
    "酸奶",
    "巴氏",
    "生乳",
    "变质",
    "异味",
    "腹泻",
    "投诉",
    "不合格",
    "召回",
]


ENTERPRISE_SUFFIXES = [
    "股份有限公司",
    "有限责任公司",
    "有限公司",
    "公司",
    "集团",
    "（集团）",
    "(集团)",
]

ALIAS_STOPWORDS = {
    "上海", "北京", "天津", "重庆", "南京", "苏州", "无锡", "常州", "合肥",
    "有限公司", "公司", "集团", "食品", "乳业", "乳品", "牧场", "物流", "冷链",
}

PLATFORM_ALIASES = {
    "wb": ["wb", "weibo"],
    "weibo": ["weibo", "wb"],
    "dy": ["dy", "douyin"],
    "douyin": ["douyin", "dy"],
    "ks": ["ks", "kuaishou"],
    "kuaishou": ["kuaishou", "ks"],
    "xhs": ["xhs"],
    "bili": ["bili", "bilibili"],
    "bilibili": ["bilibili", "bili"],
    "zhihu": ["zhihu"],
    "tieba": ["tieba"],
}


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", "", text)
    return text.strip().lower()


def _build_aliases(name: str) -> List[str]:
    base = _normalize_text(name)
    if not base:
        return []
    aliases = {base}
    for suffix in ENTERPRISE_SUFFIXES:
        s = _normalize_text(suffix)
        if base.endswith(s) and len(base) - len(s) >= 3:
            aliases.add(base[: -len(s)])

    # 去地名后生成核心别名，例如 "上海光明乳业股份有限公司" -> "光明乳业"、"光明"
    core_candidates = set(aliases)
    for a in list(aliases):
        stripped = re.sub(r"^(上海|北京|天津|重庆|南京|苏州|无锡|常州|合肥)", "", a)
        if len(stripped) >= 2:
            core_candidates.add(stripped)

    for a in list(core_candidates):
        for kw in ("乳业", "乳品", "奶粉", "奶业", "食品", "牧场", "物流", "冷链"):
            if kw in a:
                left = a.split(kw)[0]
                if len(left) >= 2:
                    core_candidates.add(left)
                    core_candidates.add(left + kw)

    cleaned = []
    for a in core_candidates:
        if len(a) < 2:
            continue
        if a in ALIAS_STOPWORDS:
            continue
        cleaned.append(a)
    return sorted(set(cleaned), key=len, reverse=True)


def _parse_timestamp(item: Dict[str, Any]) -> Optional[datetime]:
    v = item.get("create_time")
    if isinstance(v, (int, float)):
        try:
            return datetime.fromtimestamp(float(v), tz=timezone.utc)
        except Exception:
            pass
    if isinstance(v, str) and v.strip().isdigit():
        try:
            return datetime.fromtimestamp(float(v), tz=timezone.utc)
        except Exception:
            pass
    for key in ("create_date_time", "last_modify_ts"):
        s = item.get(key)
        if not isinstance(s, str) or not s.strip():
            continue
        s = s.strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(s, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
    return None


def _safe_int(v: Any) -> int:
    try:
        return int(float(v))
    except Exception:
        return 0


def _record_text(item: Dict[str, Any]) -> str:
    return str(item.get("content") or item.get("text") or item.get("desc") or item.get("title") or "")


def _engagement(item: Dict[str, Any], is_comment: bool) -> int:
    if is_comment:
        return _safe_int(item.get("comment_like_count"))
    return (
        _safe_int(item.get("liked_count"))
        + _safe_int(item.get("comments_count") or item.get("comment_count"))
        + _safe_int(item.get("shared_count") or item.get("share_count"))
    )


def _keyword_hits(text: str, words: Iterable[str]) -> int:
    if not text:
        return 0
    hits = 0
    for w in words:
        if w in text:
            hits += 1
    return hits


def _sentiment_score(text: str) -> float:
    t = _normalize_text(text)
    neg = _keyword_hits(t, NEGATIVE_WORDS)
    pos = _keyword_hits(t, POSITIVE_WORDS)
    if neg == 0 and pos == 0:
        return 0.0
    return (pos - neg) / max(pos + neg, 1)


@dataclass
class MatchedRecord:
    enterprise_id: str
    enterprise_name: str
    platform: str
    record_type: str
    text: str
    ts: Optional[datetime]
    engagement: int
    sentiment_score: float
    risk_keyword_hits: int
    is_negative: bool


def _load_enterprises(enterprise_csv: Path) -> Tuple[List[Dict[str, str]], List[Tuple[str, str, str]]]:
    enterprises: List[Dict[str, str]] = []
    aliases: List[Tuple[str, str, str]] = []
    with enterprise_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            eid = str(row.get("enterprise_id") or "").strip()
            name = str(row.get("enterprise_name") or "").strip()
            if not eid or not name:
                continue
            enterprises.append({"enterprise_id": eid, "enterprise_name": name})
            for a in _build_aliases(name):
                aliases.append((a, eid, name))
    aliases.sort(key=lambda x: len(x[0]), reverse=True)
    return enterprises, aliases


def _match_enterprise(text: str, source_keyword: str, aliases: List[Tuple[str, str, str]]) -> Optional[Tuple[str, str]]:
    haystack = _normalize_text(f"{source_keyword} {text}")
    if not haystack:
        return None
    for alias, eid, name in aliases:
        if alias and alias in haystack:
            return eid, name
    return None


def _iter_media_records(media_root: Path, platform: str) -> Iterable[Tuple[str, str, Dict[str, Any], bool, Path]]:
    if platform in ("all", "*"):
        platforms = [d.name for d in media_root.iterdir() if d.is_dir() and (d / "json").exists()]
    else:
        p = str(platform or "").strip().lower()
        platforms = PLATFORM_ALIASES.get(p, [p])

    dedup_platforms: List[str] = []
    seen_platforms = set()
    for pf in platforms:
        if not pf or pf in seen_platforms:
            continue
        seen_platforms.add(pf)
        dedup_platforms.append(pf)

    for pf in dedup_platforms:
        base = media_root / pf / "json"
        if not base.exists():
            continue
        for p in sorted(base.glob("search_*_*.json")):
            is_comment = "comments" in p.name
            record_type = "comment" if is_comment else "content"
            try:
                obj = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(obj, list):
                continue
            for item in obj:
                if isinstance(item, dict):
                    yield pf, record_type, item, is_comment, p


def _percentile(values: List[int], q: float) -> int:
    if not values:
        return 0
    arr = sorted(values)
    idx = min(len(arr) - 1, max(0, int(round((len(arr) - 1) * q))))
    return arr[idx]


def build_opinion_features(
    media_root: Path = DEFAULT_MEDIA_ROOT,
    enterprise_csv: Path = DEFAULT_ENTERPRISE_CSV,
    platform: str = "weibo",
    days: int = 30,
) -> Dict[str, Any]:
    enterprises, aliases = _load_enterprises(enterprise_csv)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(1, days))

    matched: List[MatchedRecord] = []
    scanned = 0
    files_seen = set()
    platforms_scanned = set()
    for rec_platform, record_type, item, is_comment, file_path in _iter_media_records(media_root, platform):
        platforms_scanned.add(rec_platform)
        files_seen.add(str(file_path))
        scanned += 1
        text = _record_text(item)
        if not text:
            continue
        ts = _parse_timestamp(item)
        if ts and ts < cutoff:
            continue
        source_keyword = str(item.get("source_keyword") or "")
        m = _match_enterprise(text, source_keyword, aliases)
        if not m:
            continue
        eid, ename = m
        risk_hits = _keyword_hits(text, RISK_KEYWORDS)
        senti = _sentiment_score(text)
        is_negative = senti < 0 or risk_hits > 0
        matched.append(
            MatchedRecord(
                enterprise_id=eid,
                enterprise_name=ename,
                platform=rec_platform,
                record_type=record_type,
                text=text,
                ts=ts,
                engagement=_engagement(item, is_comment),
                sentiment_score=senti,
                risk_keyword_hits=risk_hits,
                is_negative=is_negative,
            )
        )

    neg_eng = [x.engagement for x in matched if x.is_negative]
    hot_threshold = _percentile(neg_eng, 0.9) if neg_eng else 0

    agg: Dict[str, Dict[str, Any]] = {}
    for ent in enterprises:
        agg[ent["enterprise_id"]] = {
            "enterprise_id": ent["enterprise_id"],
            "enterprise_name": ent["enterprise_name"],
            "platform": platform,
            "mention_count_30d": 0,
            "post_count_30d": 0,
            "comment_count_30d": 0,
            "total_engagement_30d": 0,
            "negative_count_30d": 0,
            "negative_ratio_30d": 0.0,
            "risk_keyword_hits_30d": 0,
            "hot_negative_count_30d": 0,
            "opinion_risk_index": 0.0,
            "latest_mention_time": "",
        }

    for x in matched:
        cur = agg.get(x.enterprise_id)
        if not cur:
            continue
        cur["mention_count_30d"] += 1
        if x.record_type == "comment":
            cur["comment_count_30d"] += 1
        else:
            cur["post_count_30d"] += 1
        cur["total_engagement_30d"] += x.engagement
        if x.is_negative:
            cur["negative_count_30d"] += 1
            if x.engagement >= hot_threshold and hot_threshold > 0:
                cur["hot_negative_count_30d"] += 1
        cur["risk_keyword_hits_30d"] += x.risk_keyword_hits
        if x.ts:
            ts_text = x.ts.strftime("%Y-%m-%d %H:%M:%S")
            if not cur["latest_mention_time"] or ts_text > cur["latest_mention_time"]:
                cur["latest_mention_time"] = ts_text

    max_eng = max((v["total_engagement_30d"] for v in agg.values()), default=0)
    denom_eng = math.log1p(max(max_eng, 1))

    for cur in agg.values():
        mention = max(int(cur["mention_count_30d"]), 1)
        neg_ratio = float(cur["negative_count_30d"]) / mention
        cur["negative_ratio_30d"] = round(neg_ratio, 6)
        eng_norm = math.log1p(max(0, int(cur["total_engagement_30d"]))) / denom_eng
        risk_hit_ratio = min(1.0, float(cur["risk_keyword_hits_30d"]) / mention)
        hot_ratio = min(1.0, float(cur["hot_negative_count_30d"]) / 3.0)
        opinion_idx = (
            0.35 * neg_ratio
            + 0.25 * eng_norm
            + 0.25 * risk_hit_ratio
            + 0.15 * hot_ratio
        )
        cur["opinion_risk_index"] = round(max(0.0, min(1.0, opinion_idx)), 6)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    raw_jsonl = RAW_DIR / f"{platform}_matched_records.jsonl"
    with raw_jsonl.open("w", encoding="utf-8") as f:
        for x in matched:
            f.write(
                json.dumps(
                    {
                        "enterprise_id": x.enterprise_id,
                        "enterprise_name": x.enterprise_name,
                        "platform": x.platform,
                        "record_type": x.record_type,
                        "text": x.text[:240],
                        "ts": x.ts.isoformat() if x.ts else None,
                        "engagement": x.engagement,
                        "sentiment_score": round(x.sentiment_score, 6),
                        "risk_keyword_hits": x.risk_keyword_hits,
                        "is_negative": x.is_negative,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    rows = list(agg.values())
    rows.sort(key=lambda x: float(x["opinion_risk_index"]), reverse=True)
    csv_fields = [
        "enterprise_id",
        "enterprise_name",
        "platform",
        "mention_count_30d",
        "post_count_30d",
        "comment_count_30d",
        "total_engagement_30d",
        "negative_count_30d",
        "negative_ratio_30d",
        "risk_keyword_hits_30d",
        "hot_negative_count_30d",
        "opinion_risk_index",
        "latest_mention_time",
    ]
    with FEATURE_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "platform": platform,
        "platforms_scanned": sorted(platforms_scanned),
        "days_window": days,
        "scanned_records": scanned,
        "matched_records": len(matched),
        "matched_enterprises": sum(1 for v in rows if int(v["mention_count_30d"]) > 0),
        "files_scanned": sorted(files_seen),
        "media_root": str(media_root),
        "enterprise_csv": str(enterprise_csv),
        "outputs": {
            "feature_csv": str(FEATURE_CSV),
            "summary_json": str(SUMMARY_JSON),
            "raw_jsonl": str(raw_jsonl),
        },
        "top_enterprises": rows[:20],
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def load_opinion_feature_map(path: Path = FEATURE_CSV) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    by_name: Dict[str, Dict[str, Any]] = {}
    if not path.exists():
        return by_id, by_name
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            eid = str(row.get("enterprise_id") or "").strip()
            name = str(row.get("enterprise_name") or "").strip()
            if eid:
                by_id[eid] = row
            if name:
                by_name[name] = row
    return by_id, by_name


def build_qingming_brief(
    media_root: Path = DEFAULT_MEDIA_ROOT,
    platform: str = "all",
    days: int = 15,
    top_n: int = 20,
) -> Dict[str, Any]:
    """
    清明节舆情快速简报（轻量版）：
    - 统计“清明关键词 + 乳制品相关词”命中的帖子/评论数量
    - 输出平台分布、关键词热度、样本文本
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(1, int(days)))

    scanned_records = 0
    qingming_hits = 0
    qingming_dairy_hits = 0
    by_platform: Dict[str, int] = {}
    keyword_counter: Dict[str, int] = {}
    risk_counter: Dict[str, int] = {}
    samples: List[Dict[str, Any]] = []

    for pf, record_type, item, is_comment, _ in _iter_media_records(media_root, platform):
        scanned_records += 1
        text = _record_text(item)
        if not text:
            continue
        ts = _parse_timestamp(item)
        if ts and ts < cutoff:
            continue

        hits_qingming = [w for w in QINGMING_KEYWORDS if w in text]
        if not hits_qingming:
            continue
        qingming_hits += 1
        by_platform[pf] = by_platform.get(pf, 0) + 1

        for w in hits_qingming:
            keyword_counter[w] = keyword_counter.get(w, 0) + 1

        hits_dairy = [w for w in DAIRY_OPINION_KEYWORDS if w in text]
        hits_risk = [w for w in RISK_KEYWORDS if w in text]
        if hits_dairy:
            qingming_dairy_hits += 1
        for w in hits_risk:
            risk_counter[w] = risk_counter.get(w, 0) + 1

        if len(samples) < max(5, min(top_n, 30)):
            samples.append(
                {
                    "platform": pf,
                    "record_type": record_type,
                    "create_time": ts.isoformat() if ts else None,
                    "text": text[:180],
                    "qingming_keywords": hits_qingming,
                    "dairy_keywords": hits_dairy[:6],
                    "risk_keywords": hits_risk[:6],
                    "engagement": _engagement(item, is_comment),
                }
            )

    # engagement 排序样本
    samples.sort(key=lambda x: int(x.get("engagement") or 0), reverse=True)
    samples = samples[:top_n]

    return {
        "platform": platform,
        "days_window": int(days),
        "scanned_records": int(scanned_records),
        "qingming_hits": int(qingming_hits),
        "qingming_dairy_hits": int(qingming_dairy_hits),
        "platform_distribution": dict(sorted(by_platform.items(), key=lambda kv: kv[1], reverse=True)),
        "top_qingming_keywords": sorted(keyword_counter.items(), key=lambda kv: kv[1], reverse=True)[:10],
        "top_risk_keywords": sorted(risk_counter.items(), key=lambda kv: kv[1], reverse=True)[:10],
        "samples": samples,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
