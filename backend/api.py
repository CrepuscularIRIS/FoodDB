#!/usr/bin/env python3
"""
FastAPI 后端服务
为前端提供 RESTful API 接口
"""

import os
import sys
import json
import asyncio
import csv
import math
import hashlib
import base64
import re
import subprocess
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import asdict

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
# 添加 scripts 路径（用于子图模块导入）
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# 加载环境变量
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✓ 已加载环境变量: {env_path}")

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent.workflow import RiskAssessmentAgent
from agent.symptom_router import get_symptom_router, SymptomRiskResult

# 检查 LLM 提取器是否可用
try:
    from agent.symptom_extractor import LLMSymptomExtractor, get_symptom_extractor
    LLM_EXTRACTOR_AVAILABLE = True
except ImportError:
    LLM_EXTRACTOR_AVAILABLE = False
from agent.orchestrator import Orchestrator

# 导入图数据路由
try:
    from dairyrisk.api.graph_routes import setup_graph_routes
    GRAPH_ROUTES_AVAILABLE = True
except ImportError as e:
    GRAPH_ROUTES_AVAILABLE = False
    print(f"⚠ 图数据路由导入失败: {e}")

try:
    from modela_v2_pipeline import (
        build_modela_v2_graph,
        extract_category_subgraph,
    )
    MODELA_V2_AVAILABLE = True
except ImportError as e:
    MODELA_V2_AVAILABLE = False
    print(f"⚠ ModelA v2 模块导入失败: {e}")

try:
    from modea_formula_engine import (
        compute_formula_scores,
        rank_nodes_by_priority,
        build_budget_plan,
    )
    MODELA_FORMULA_AVAILABLE = True
except ImportError as e:
    MODELA_FORMULA_AVAILABLE = False
    print(f"⚠ ModeA 公式引擎导入失败: {e}")

try:
    from backend.opinion_module import (
        DEFAULT_ENTERPRISE_CSV,
        DEFAULT_MEDIA_ROOT,
        SUMMARY_JSON as OPINION_SUMMARY_JSON,
        FEATURE_CSV as OPINION_FEATURE_CSV,
        build_opinion_features,
        build_qingming_brief,
        load_opinion_feature_map,
    )
    MODEB_OPINION_AVAILABLE = True
except ImportError as e:
    try:
        from opinion_module import (
            DEFAULT_ENTERPRISE_CSV,
            DEFAULT_MEDIA_ROOT,
            SUMMARY_JSON as OPINION_SUMMARY_JSON,
            FEATURE_CSV as OPINION_FEATURE_CSV,
            build_opinion_features,
            build_qingming_brief,
            load_opinion_feature_map,
        )
        MODEB_OPINION_AVAILABLE = True
    except ImportError:
        MODEB_OPINION_AVAILABLE = False
        print(f"⚠ ModeB 舆情模块导入失败: {e}")

# 创建FastAPI应用
app = FastAPI(
    title="乳制品供应链风险研判智能体 API",
    description="基于知识驱动与规则增强的乳制品供应链风险研判系统（Mode A/B 联动版）",
    version="1.2.0"
)

# 注册图数据路由（在CORS之前）
if GRAPH_ROUTES_AVAILABLE:
    try:
        setup_graph_routes(app)
        print("✓ 图数据API路由已预注册")
    except Exception as e:
        print(f"⚠ 图数据API路由预注册失败: {e}")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js 默认端口
        "http://localhost:3001",  # 备用端口
        "http://localhost:3002",  # 备用端口
        "http://localhost:3003",
        "http://localhost:3004",
        "http://localhost:3005",
        "http://localhost:3006",
        "http://localhost:3007",
        "http://localhost:3008",
        "http://localhost:3009",
        "http://localhost:3010",
        "http://localhost:3011",
        "http://localhost:3012",
        "http://localhost:13000",
        "http://127.0.0.1:13000",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局Agent实例
agent: Optional[RiskAssessmentAgent] = None
symptom_router = None
orchestrator: Optional[Orchestrator] = None

# LLM 子图评估全局状态
LLM_GRAPH_PATH = PROJECT_ROOT / "data" / "llm_graph" / "graph_llm_ready.json"
llm_graph: Optional[Dict[str, Any]] = None

# ModelA v2 全局状态
MODELA_V2_GRAPH_PATH = PROJECT_ROOT / "data" / "modela_v2" / "modela_v2_graph.json"
MODELA_V2_DEFAULT_INPUT = PROJECT_ROOT.parent / "HandOff" / "乳制品供应链异构图数据和国标语料.zip"
modela_v2_graph: Optional[Dict[str, Any]] = None

# ModeB 舆情全局状态
opinion_feature_by_id: Dict[str, Dict[str, Any]] = {}
opinion_feature_by_name: Dict[str, Dict[str, Any]] = {}
MODEB_CRAWLER_DEFAULT_ROOT = Path("/home/yarizakurahime/Agents/winteragent/MediaCrawler")
MODEB_CRAWL_LOG_DIR = PROJECT_ROOT / "data" / "opinion" / "crawl_logs"
MODEB_PLATFORM_TO_CRAWLER = {
    "weibo": "wb",
    "wb": "wb",
    "douyin": "dy",
    "dy": "dy",
    "kuaishou": "ks",
    "ks": "ks",
    "xhs": "xhs",
    "bili": "bili",
    "zhihu": "zhihu",
    "tieba": "tieba",
}
modeb_crawl_lock = threading.Lock()
modeb_crawl_state: Dict[str, Any] = {
    "status": "idle",
    "run_id": None,
    "pid": None,
    "started_at": None,
    "ended_at": None,
    "return_code": None,
    "command": [],
    "log_path": "",
    "mediacrawler_root": str(MODEB_CRAWLER_DEFAULT_ROOT),
    "platform_request": None,
    "platform_cli": None,
    "crawler_type": None,
    "keywords": None,
    "process": None,
    "log_handle": None,
}


# 数据模型
class AssessRequest(BaseModel):
    query: str
    with_propagation: bool = False


class BatchAssessRequest(BaseModel):
    queries: List[str]


class SamplingRequest(BaseModel):
    enterprise_id: Optional[str] = None


class PropagationRequest(BaseModel):
    node_id: str
    max_hops: int = 3


class SymptomAssessRequest(BaseModel):
    """症状驱动评估请求"""
    query: str
    product_type: Optional[str] = None  # 可选的产品类型过滤


class OpinionImportRequest(BaseModel):
    """ModeB 舆情导入请求"""
    media_root: Optional[str] = None
    enterprise_csv: Optional[str] = None
    platform: str = "weibo"
    days: int = 30


class OpinionCrawlStartRequest(BaseModel):
    """ModeB 舆情抓取请求"""
    mediacrawler_root: Optional[str] = None
    platform: str = "weibo"
    crawler_type: str = "search"
    login_type: str = "qrcode"
    keywords: str = "乳制品安全,奶粉腹泻,牛奶变质,牛奶变质投诉"
    headless: bool = True
    get_comment: bool = True
    get_sub_comment: bool = False
    start_page: int = 1
    max_comments_count_singlenotes: int = 20
    save_data_option: str = "json"


class QingmingQuickCrawlRequest(BaseModel):
    """清明节舆情一键抓取（简单版）"""
    mediacrawler_root: Optional[str] = None
    platform: str = "weibo"
    headless: bool = True
    get_comment: bool = True
    get_sub_comment: bool = False
    save_data_option: str = "json"
    login_type: str = "qrcode"


class ModeBMultimodalItemRequest(BaseModel):
    name: str = ""
    mime_type: str = ""
    data_url: Optional[str] = None
    note: Optional[str] = None


class ModeBMultimodalAssessRequest(BaseModel):
    """ModeB 四模态输入融合评估"""
    text: Optional[str] = None
    image_items: List[ModeBMultimodalItemRequest] = Field(default_factory=list)
    video_items: List[ModeBMultimodalItemRequest] = Field(default_factory=list)
    audio_items: List[ModeBMultimodalItemRequest] = Field(default_factory=list)
    product_type: Optional[str] = None
    use_qingming_context: bool = False
    qingming_days: int = 15
    qingming_platform: str = "all"


class LinkedWorkflowRequest(BaseModel):
    """Mode A/B 联动工作流请求"""
    symptom_description: str
    population: Optional[Dict[str, Any]] = None  # 人群特征


class PopulationInfo(BaseModel):
    """人群特征信息"""
    age_group: Optional[str] = None  # infant/child/adult/elderly
    case_count: Optional[int] = None
    region: Optional[str] = None


# 初始化Agent
@app.on_event("startup")
async def startup_event():
    global agent, symptom_router, orchestrator
    global opinion_feature_by_id, opinion_feature_by_name

    # 日志输出当前数据源
    data_dir = os.environ.get("DATA_DIR", "自动解析")
    print(f"=" * 60)
    print(f"启动信息:")
    print(f"  - DATA_DIR: {data_dir}")
    print(f"  - 版本: 1.2.0 (Mode A/B 联动版)")
    print(f"=" * 60)

    print("正在初始化 RiskAssessmentAgent...")
    agent = RiskAssessmentAgent(use_real_data=True)
    print(f"✓ Agent 初始化完成")
    print(f"  - 数据源: {agent.retriever.data_dir}")

    print("正在初始化症状驱动风险路由器...")
    symptom_router = get_symptom_router(agent.retriever)
    print("✓ 症状驱动路由器初始化完成")

    print("正在初始化 Mode A/B 联动编排器...")
    orchestrator = Orchestrator(data_dir=agent.retriever.data_dir)
    print("✓ 联动编排器初始化完成")

    if MODEB_OPINION_AVAILABLE:
        opinion_feature_by_id, opinion_feature_by_name = load_opinion_feature_map(OPINION_FEATURE_CSV)
        print(f"✓ ModeB 舆情特征已加载: {len(opinion_feature_by_id)} 家企业")


# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.1.0"}


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _normalize_crawler_platform(platform: str) -> str:
    p = str(platform or "").strip().lower()
    return MODEB_PLATFORM_TO_CRAWLER.get(p, p or "wb")


def _build_modeb_crawl_cmd(request: OpinionCrawlStartRequest, platform_cli: str) -> List[str]:
    cmd: List[str] = [
        "uv",
        "run",
        "main.py",
        "--platform",
        platform_cli,
        "--lt",
        request.login_type,
        "--type",
        request.crawler_type,
        "--headless",
        "true" if request.headless else "false",
        "--get_comment",
        "true" if request.get_comment else "false",
        "--get_sub_comment",
        "true" if request.get_sub_comment else "false",
        "--save_data_option",
        request.save_data_option,
        "--max_comments_count_singlenotes",
        str(max(1, int(request.max_comments_count_singlenotes))),
    ]

    if request.crawler_type == "search":
        kw = str(request.keywords or "").strip()
        if kw:
            cmd.extend(["--keywords", kw])
    if request.start_page and int(request.start_page) > 1:
        cmd.extend(["--start", str(int(request.start_page))])
    return cmd


def _read_log_tail(log_path: str, tail_lines: int = 80) -> List[str]:
    p = Path(log_path) if log_path else None
    if not p or not p.exists():
        return []
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    if tail_lines <= 0:
        return []
    return lines[-tail_lines:]


def _sync_modeb_crawl_state_locked() -> None:
    proc = modeb_crawl_state.get("process")
    if proc is None:
        return
    ret = proc.poll()
    if ret is None:
        return

    modeb_crawl_state["return_code"] = ret
    modeb_crawl_state["ended_at"] = modeb_crawl_state.get("ended_at") or _now_iso()
    if modeb_crawl_state.get("status") == "running":
        modeb_crawl_state["status"] = "success" if ret == 0 else "failed"
    modeb_crawl_state["process"] = None

    log_handle = modeb_crawl_state.get("log_handle")
    if log_handle is not None:
        try:
            log_handle.flush()
            log_handle.close()
        except Exception:
            pass
        modeb_crawl_state["log_handle"] = None


def _modeb_crawl_snapshot_locked(tail_lines: int = 80) -> Dict[str, Any]:
    _sync_modeb_crawl_state_locked()
    return {
        "status": modeb_crawl_state.get("status"),
        "run_id": modeb_crawl_state.get("run_id"),
        "pid": modeb_crawl_state.get("pid"),
        "started_at": modeb_crawl_state.get("started_at"),
        "ended_at": modeb_crawl_state.get("ended_at"),
        "return_code": modeb_crawl_state.get("return_code"),
        "command": modeb_crawl_state.get("command") or [],
        "log_path": modeb_crawl_state.get("log_path"),
        "mediacrawler_root": modeb_crawl_state.get("mediacrawler_root"),
        "platform_request": modeb_crawl_state.get("platform_request"),
        "platform_cli": modeb_crawl_state.get("platform_cli"),
        "crawler_type": modeb_crawl_state.get("crawler_type"),
        "keywords": modeb_crawl_state.get("keywords"),
        "log_tail": _read_log_tail(modeb_crawl_state.get("log_path") or "", tail_lines=tail_lines),
    }


def _enrich_linked_enterprises_with_opinion(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not items:
        return items
    if not MODEB_OPINION_AVAILABLE:
        return items

    enriched: List[Dict[str, Any]] = []
    for ent in items:
        e = dict(ent)
        eid = str(e.get("enterprise_id") or "")
        name = str(e.get("enterprise_name") or "")
        feat = opinion_feature_by_id.get(eid) or opinion_feature_by_name.get(name) or {}

        opinion_idx = _to_float(feat.get("opinion_risk_index"), 0.0)
        mention_cnt = int(_to_float(feat.get("mention_count_30d"), 0))
        neg_ratio = _to_float(feat.get("negative_ratio_30d"), 0.0)
        risk_hits = int(_to_float(feat.get("risk_keyword_hits_30d"), 0))

        # Mode B 基础分 + 舆情增强（上限控制）
        base_score = _to_float(e.get("risk_score"), 0.0)
        opinion_boost = min(5.0, opinion_idx * 5.0)
        combined_score = round(base_score + opinion_boost, 2)

        e["opinion_risk_index"] = round(opinion_idx, 6)
        e["opinion_mentions_30d"] = mention_cnt
        e["opinion_negative_ratio_30d"] = round(neg_ratio, 6)
        e["opinion_risk_keyword_hits_30d"] = risk_hits
        e["combined_risk_score"] = combined_score
        enriched.append(e)

    enriched.sort(key=lambda x: float(x.get("combined_risk_score", x.get("risk_score", 0.0))), reverse=True)
    return enriched


MODEB_MM_RISK_TERMS = [
    "腹泻",
    "呕吐",
    "发热",
    "异味",
    "变质",
    "过期",
    "污染",
    "细菌",
    "投诉",
    "召回",
    "不合格",
    "中毒",
]


def _modeb_decode_data_url(data_url: str, max_bytes: int = 2 * 1024 * 1024) -> bytes:
    if not data_url:
        return b""
    if not data_url.startswith("data:"):
        return b""
    try:
        head, body = data_url.split(",", 1)
    except ValueError:
        return b""
    if ";base64" not in head:
        raw = body.encode("utf-8", errors="ignore")
        return raw[:max_bytes]
    try:
        raw = base64.b64decode(body, validate=False)
    except Exception:
        return b""
    return raw[:max_bytes]


def _modeb_extract_textual_hints(
    item: ModeBMultimodalItemRequest,
    modality: str,
) -> Dict[str, Any]:
    name = str(item.name or "").strip()
    mime = str(item.mime_type or "").strip()
    note = str(item.note or "").strip()
    hints: List[str] = []
    if name:
        hints.append(name)
    if note:
        hints.append(note)

    raw = b""
    if item.data_url:
        raw = _modeb_decode_data_url(item.data_url)
    size_bytes = len(raw)

    # 仅对 text/* 尝试提取正文，其他模态只提取文件名/备注关键词
    decoded_text = ""
    if mime.startswith("text/") and raw:
        decoded_text = raw.decode("utf-8", errors="ignore")
        if decoded_text:
            hints.append(decoded_text[:1200])

    merged = " ".join(hints).lower()
    hit_terms = [w for w in MODEB_MM_RISK_TERMS if w in merged]
    # 尝试抽取中文片段，避免文件名完全无信息
    zh_tokens = re.findall(r"[\u4e00-\u9fff]{2,8}", merged)

    return {
        "modality": modality,
        "name": name,
        "mime_type": mime,
        "size_bytes": size_bytes,
        "risk_terms": hit_terms[:10],
        "zh_tokens": zh_tokens[:20],
        "text_hint": " ".join(hints)[:600],
    }


def _modeb_compose_multimodal_query(
    text: Optional[str],
    image_items: List[ModeBMultimodalItemRequest],
    video_items: List[ModeBMultimodalItemRequest],
    audio_items: List[ModeBMultimodalItemRequest],
) -> Dict[str, Any]:
    text_part = str(text or "").strip()
    image_ev = [_modeb_extract_textual_hints(x, "image") for x in (image_items or [])[:5]]
    video_ev = [_modeb_extract_textual_hints(x, "video") for x in (video_items or [])[:5]]
    audio_ev = [_modeb_extract_textual_hints(x, "audio") for x in (audio_items or [])[:5]]

    parts: List[str] = []
    if text_part:
        parts.append(text_part)

    def join_hint(arr: List[Dict[str, Any]], title: str) -> None:
        if not arr:
            return
        cues: List[str] = []
        for e in arr:
            if e.get("text_hint"):
                cues.append(str(e["text_hint"]))
            if e.get("risk_terms"):
                cues.extend(str(x) for x in e["risk_terms"])
            if e.get("zh_tokens"):
                cues.extend(str(x) for x in e["zh_tokens"][:6])
        if cues:
            parts.append(f"[{title}] " + " ".join(cues[:80]))

    join_hint(image_ev, "图片线索")
    join_hint(video_ev, "视频线索")
    join_hint(audio_ev, "语音线索")

    fused_query = " ".join(p for p in parts if p).strip()
    if not fused_query:
        fused_query = "乳制品 风险 线索不足"

    return {
        "fused_query": fused_query[:3000],
        "evidence": {
            "text_length": len(text_part),
            "image_count": len(image_ev),
            "video_count": len(video_ev),
            "audio_count": len(audio_ev),
            "images": image_ev,
            "videos": video_ev,
            "audios": audio_ev,
        },
    }


# 风险研判
@app.post("/assess")
async def assess(request: AssessRequest):
    """执行风险研判"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent未初始化")

    try:
        if request.with_propagation:
            report = agent.assess_with_propagation(request.query)
        else:
            report = agent.assess(request.query)

        return {
            "success": True,
            "data": asdict(report)
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 批量研判
@app.post("/batch_assess")
async def batch_assess(request: BatchAssessRequest):
    """批量执行风险研判"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent未初始化")

    reports = []
    for query in request.queries:
        try:
            report = agent.assess(query)
            reports.append(asdict(report))
        except Exception as e:
            reports.append({
                "error": str(e),
                "query": query
            })

    return {
        "success": True,
        "data": reports
    }


# 加载案例库（优先读 data/merged，不存在则回退到 data/mock）
MERGED_PATH = Path(__file__).parent.parent / "data" / "merged" / "case_library.json"
MOCK_PATH = Path(__file__).parent.parent / "data" / "mock" / "case_library.json"
CASE_LIBRARY_PATH = MERGED_PATH if MERGED_PATH.exists() else MOCK_PATH
case_library = {"cases": []}

def load_case_library():
    """加载案例库"""
    global case_library
    try:
        if CASE_LIBRARY_PATH.exists():
            with open(CASE_LIBRARY_PATH, 'r', encoding='utf-8') as f:
                case_library = json.load(f)
            print(f"✓ 案例库加载完成: {len(case_library.get('cases', []))} 个案例")
        else:
            print(f"⚠ 案例库文件不存在: {CASE_LIBRARY_PATH}")
    except Exception as e:
        print(f"⚠ 加载案例库失败: {e}")

# 启动时加载案例库
@app.on_event("startup")
async def load_cases_on_startup():
    load_case_library()


# 启动时加载 LLM 就绪子图
@app.on_event("startup")
async def load_llm_graph_on_startup():
    global llm_graph
    if LLM_GRAPH_PATH.exists():
        try:
            llm_graph = json.loads(LLM_GRAPH_PATH.read_text(encoding="utf-8"))
            print(f"✓ LLM 子图已加载: {len(llm_graph['nodes'])} 节点, {len(llm_graph['edges'])} 边")
        except Exception as e:
            print(f"⚠ 加载 LLM 子图失败: {e}")
    else:
        print(f"⚠ LLM 子图文件不存在: {LLM_GRAPH_PATH}，请先运行 scripts/prepare_llm_hetero_graph.py")


def _ensure_modela_v2_graph(force_rebuild: bool = False) -> Dict[str, Any]:
    """加载（或构建）ModelA v2 图谱数据。"""
    global modela_v2_graph
    if not MODELA_V2_AVAILABLE:
        raise RuntimeError("ModelA v2 模块不可用")

    if modela_v2_graph is not None and not force_rebuild:
        return modela_v2_graph

    if force_rebuild or not MODELA_V2_GRAPH_PATH.exists():
        if not MODELA_V2_DEFAULT_INPUT.exists():
            raise FileNotFoundError(
                f"未找到 ModelA v2 输入数据: {MODELA_V2_DEFAULT_INPUT}"
            )
        print("⏳ 正在构建 ModelA v2 图谱数据...")
        modela_v2_graph = build_modela_v2_graph(
            input_path=MODELA_V2_DEFAULT_INPUT,
            output_dir=MODELA_V2_GRAPH_PATH.parent,
        )
        print(
            f"✓ ModelA v2 构建完成: {modela_v2_graph['meta']['node_count']} 节点, "
            f"{modela_v2_graph['meta']['edge_count']} 边"
        )
        return modela_v2_graph

    modela_v2_graph = json.loads(MODELA_V2_GRAPH_PATH.read_text(encoding="utf-8"))
    return modela_v2_graph


@app.on_event("startup")
async def load_modela_v2_on_startup():
    if not MODELA_V2_AVAILABLE:
        print("⚠ 跳过 ModelA v2 启动加载：模块不可用")
        return
    try:
        graph = _ensure_modela_v2_graph(force_rebuild=False)
        print(
            f"✓ ModelA v2 已加载: {graph['meta']['node_count']} 节点, "
            f"{graph['meta']['edge_count']} 边, "
            f"{len(graph['meta']['product_categories'])} 品类"
        )
    except Exception as e:
        print(f"⚠ 加载 ModelA v2 失败: {e}")

# 获取演示案例
@app.get("/demo_cases")
async def get_demo_cases():
    """获取预定义的演示案例列表（从真实案例库提取）"""
    cases_data = case_library.get("cases", [])

    # 如果案例库为空，尝试重新加载
    if not cases_data:
        load_case_library()
        cases_data = case_library.get("cases", [])

    # 转换为前端需要的格式
    cases = []
    for case in cases_data[:6]:  # 取前6个作为演示案例
        case_item = {
            "id": case["case_id"],
            "name": case["title"].split("事件")[0][4:],  # 去掉年份和"事件"后缀
            "description": case["summary"][:80] + "..." if len(case["summary"]) > 80 else case["summary"],
            "query": case["demo_query"],
            "risk_level": case["risk_level"],
            "risk_type": case["risk_type"],
            "year": case["year"],
            "product_type": case["product_type"]
        }
        # 添加target_hint用于精准定位
        if "target_hint" in case:
            case_item["target_hint"] = case["target_hint"]
        cases.append(case_item)

    return {
        "success": True,
        "data": cases
    }


# 获取完整案例库
@app.get("/case_library")
async def get_case_library(risk_type: Optional[str] = None, risk_level: Optional[str] = None):
    """获取完整案例库，支持按风险类型和等级筛选"""
    cases = case_library.get("cases", [])

    # 筛选
    if risk_type:
        cases = [c for c in cases if risk_type in c.get("risk_type", "")]
    if risk_level:
        cases = [c for c in cases if c.get("risk_level") == risk_level]

    return {
        "success": True,
        "data": {
            "cases": cases,
            "total": len(cases),
            "filters": {"risk_type": risk_type, "risk_level": risk_level}
        }
    }


# 获取单个案例详情
@app.get("/case_library/{case_id}")
async def get_case_detail(case_id: str):
    """获取单个案例详情"""
    cases = case_library.get("cases", [])
    case = next((c for c in cases if c["case_id"] == case_id), None)

    if not case:
        raise HTTPException(status_code=404, detail="案例不存在")

    return {
        "success": True,
        "data": case
    }


# 获取企业列表
@app.get("/enterprises")
async def get_enterprises():
    """获取企业列表"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent未初始化")

    enterprises = [
        {
            "enterprise_id": e["enterprise_id"],
            "enterprise_name": e["enterprise_name"],
            "enterprise_type": e["enterprise_type"],
            "node_type": e["node_type"],
            "credit_rating": e["credit_rating"],
            "historical_violation_count": e["historical_violation_count"]
        }
        for e in agent.retriever.enterprises[:20]
    ]

    return {
        "success": True,
        "data": enterprises
    }


# 获取企业详情
@app.get("/enterprises/{enterprise_identifier}")
async def get_enterprise(enterprise_identifier: str):
    """获取企业详情（支持ID或名称，精确匹配）"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent未初始化")

    identifier = enterprise_identifier.strip()

    # 先尝试按ID查找
    enterprise = agent.retriever.find_enterprise(enterprise_id=identifier)

    # 再尝试按精确名称查找（避免模糊匹配导致错误）
    if not enterprise and identifier in agent.retriever.enterprises_by_name:
        enterprise = agent.retriever.enterprises_by_name[identifier]

    if not enterprise:
        raise HTTPException(status_code=404, detail="企业不存在")

    return {
        "success": True,
        "data": enterprise
    }


# 获取批次列表
@app.get("/batches")
async def get_batches():
    """获取批次列表"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent未初始化")

    batches = [
        {
            "batch_id": b["batch_id"],
            "enterprise_id": b["enterprise_id"],
            "product_name": b["product_name"],
            "product_type": b["product_type"],
            "batch_no": b["batch_no"],
            "production_date": b["production_date"]
        }
        for b in agent.retriever.batches[:20]
    ]

    return {
        "success": True,
        "data": batches
    }


# 获取批次详情
@app.get("/batches/{batch_identifier}")
async def get_batch(batch_identifier: str):
    """获取批次详情（支持ID或批次号）"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent未初始化")

    # 先尝试按ID查找，再尝试按批次号查找
    batch = agent.retriever.find_batch(batch_id=batch_identifier)
    if not batch:
        batch = agent.retriever.find_batch(batch_no=batch_identifier)

    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")

    return {
        "success": True,
        "data": batch
    }


# 获取抽检建议
@app.post("/sampling/suggestions")
async def get_sampling_suggestions(request: SamplingRequest):
    """获取抽检建议"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent未初始化")

    # 简化的抽检建议逻辑
    suggestions = [
        {
            "priority": "high",
            "action": "优先抽检",
            "target": request.enterprise_id or "高风险企业",
            "reason": "基于风险评分排序",
            "sampling_items": ["菌落总数", "大肠菌群", "蛋白质"],
            "deadline": "3日内"
        }
    ]

    return {
        "success": True,
        "data": {"suggestions": suggestions}
    }


# 获取Top-N抽检清单
@app.get("/sampling/top_n")
async def get_top_n_list(n: int = 10):
    """获取Top-N抽检清单"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent未初始化")

    # 获取所有批次的风险分数
    batches_with_scores = []
    for batch in agent.retriever.batches[:30]:
        try:
            score = agent.scoring_engine.calculate_node_risk(batch_id=batch["batch_id"])
            batches_with_scores.append({
                "rank": 0,  # 稍后排序
                "target_id": batch["batch_id"],
                "target_name": batch["product_name"],
                "risk_score": score.total_score,
                "risk_level": score.risk_level,
                "priority": "immediate" if score.risk_level == "high" else "high" if score.risk_level == "medium" else "normal",
                "sampling_items": ["菌落总数", "大肠菌群", "蛋白质"]
            })
        except:
            continue

    # 排序
    batches_with_scores.sort(key=lambda x: x["risk_score"], reverse=True)

    # 添加排名
    for i, item in enumerate(batches_with_scores[:n], 1):
        item["rank"] = i

    return {
        "success": True,
        "data": {
            "total": len(batches_with_scores[:n]),
            "items": batches_with_scores[:n]
        }
    }


# 风险传播分析
@app.post("/propagation/analyze")
async def analyze_propagation(request: PropagationRequest):
    """执行风险传播分析"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent未初始化")

    result = agent._analyze_propagation(request.node_id, request.max_hops)

    return {
        "success": True,
        "data": result
    }


# ==================== Mode A/B 联动 API ====================

@app.post("/linked_workflow")
async def run_linked_workflow(request: LinkedWorkflowRequest):
    """
    Mode A/B 联动工作流

    流程: Mode B(症状分析) -> RiskHypothesis -> Mode A(定向核查) -> 联合报告

    输入: 症状描述、人群特征
    输出: 包含症状证据、企业证据、GB依据、行动建议的联合报告
    """
    if not orchestrator:
        raise HTTPException(status_code=503, detail="联动编排器未初始化")

    try:
        # 执行联动工作流
        report = orchestrator.run_linked_workflow(
            symptom_description=request.symptom_description,
            population=request.population
        )

        return {
            "success": True,
            "data": report.to_dict()
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"联动工作流执行失败: {str(e)}")


@app.post("/linked_workflow_stream")
async def run_linked_workflow_stream(request: LinkedWorkflowRequest):
    """
    Mode A/B 联动工作流（流式）

    通过 SSE 返回每个步骤的状态更新
    """
    if not orchestrator:
        raise HTTPException(status_code=503, detail="联动编排器未初始化")

    async def event_generator():
        try:
            stream = orchestrator.run_linked_workflow_streaming(
                symptom_description=request.symptom_description,
                population=request.population
            )

            for update in stream:
                yield f"data: {json.dumps(update, ensure_ascii=False)}\n\n"

            # 发送结束标记
            final_update = {
                "step": "stream_end",
                "status": "complete",
                "message": "流式传输完成"
            }
            yield f"data: {json.dumps(final_update, ensure_ascii=False)}\n\n"

        except Exception as e:
            error_update = {
                "step": "workflow_error",
                "status": "error",
                "error": str(e),
                "message": f"联动工作流出错: {e}"
            }
            yield f"data: {json.dumps(error_update, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/data_source")
async def get_data_source():
    """获取当前数据源信息"""
    data_source_info = {
        "data_dir": str(agent.retriever.data_dir) if agent else None,
        "enterprise_count": len(agent.retriever.enterprises) if agent else 0,
        "batch_count": len(agent.retriever.batches) if agent else 0,
        "inspection_count": len(agent.retriever.inspections) if agent else 0,
        "data_source": "merged" if agent and "merged" in str(agent.retriever.data_dir) else
                      "release_v1_1" if agent and "release_v1_1" in str(agent.retriever.data_dir) else
                      "real" if agent and "real" in str(agent.retriever.data_dir) else
                      "mock" if agent else "unknown"
    }

    return {
        "success": True,
        "data": data_source_info
    }


# ==================== ModeB 舆情输入 API ====================

@app.post("/modeb/opinion/crawl/start")
async def modeb_opinion_crawl_start(request: OpinionCrawlStartRequest):
    """
    启动 MediaCrawler 抓取任务（单任务模式）
    """
    media_root = Path(request.mediacrawler_root) if request.mediacrawler_root else MODEB_CRAWLER_DEFAULT_ROOT
    main_file = media_root / "main.py"
    if not media_root.exists():
        raise HTTPException(status_code=400, detail=f"MediaCrawler 根目录不存在: {media_root}")
    if not main_file.exists():
        raise HTTPException(status_code=400, detail=f"未找到 main.py: {main_file}")

    platform_cli = _normalize_crawler_platform(request.platform)
    if platform_cli not in {"xhs", "dy", "ks", "bili", "wb", "tieba", "zhihu"}:
        raise HTTPException(status_code=400, detail=f"不支持的平台: {request.platform}")
    if request.crawler_type not in {"search", "detail", "creator"}:
        raise HTTPException(status_code=400, detail=f"不支持的抓取类型: {request.crawler_type}")
    if request.login_type not in {"qrcode", "phone", "cookie"}:
        raise HTTPException(status_code=400, detail=f"不支持的登录类型: {request.login_type}")

    cmd = _build_modeb_crawl_cmd(request, platform_cli)
    MODEB_CRAWL_LOG_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = MODEB_CRAWL_LOG_DIR / f"mediacrawler_{run_id}.log"

    with modeb_crawl_lock:
        _sync_modeb_crawl_state_locked()
        if modeb_crawl_state.get("status") == "running":
            raise HTTPException(status_code=409, detail="已有进行中的抓取任务，请先停止或等待完成")

        old_log_handle = modeb_crawl_state.get("log_handle")
        if old_log_handle is not None:
            try:
                old_log_handle.close()
            except Exception:
                pass

        try:
            log_handle = log_path.open("a", encoding="utf-8")
            proc = subprocess.Popen(
                cmd,
                cwd=str(media_root),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"启动 MediaCrawler 失败: {e}")

        modeb_crawl_state.update(
            {
                "status": "running",
                "run_id": run_id,
                "pid": proc.pid,
                "started_at": _now_iso(),
                "ended_at": None,
                "return_code": None,
                "command": cmd,
                "log_path": str(log_path),
                "mediacrawler_root": str(media_root),
                "platform_request": request.platform,
                "platform_cli": platform_cli,
                "crawler_type": request.crawler_type,
                "keywords": request.keywords,
                "process": proc,
                "log_handle": log_handle,
            }
        )
        snapshot = _modeb_crawl_snapshot_locked(tail_lines=40)
    return {"success": True, "data": snapshot}


@app.get("/modeb/opinion/crawl/status")
async def modeb_opinion_crawl_status(tail_lines: int = Query(80, ge=0, le=500)):
    """
    获取抓取任务状态与日志尾部
    """
    with modeb_crawl_lock:
        snapshot = _modeb_crawl_snapshot_locked(tail_lines=tail_lines)
    return {"success": True, "data": snapshot}


@app.post("/modeb/opinion/crawl/stop")
async def modeb_opinion_crawl_stop():
    """
    停止当前抓取任务
    """
    with modeb_crawl_lock:
        _sync_modeb_crawl_state_locked()
        proc = modeb_crawl_state.get("process")
        if proc is None or modeb_crawl_state.get("status") != "running":
            snapshot = _modeb_crawl_snapshot_locked(tail_lines=80)
            return {"success": True, "data": snapshot, "message": "当前没有运行中的抓取任务"}

        try:
            proc.terminate()
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        except Exception:
            pass

        modeb_crawl_state["ended_at"] = _now_iso()
        modeb_crawl_state["return_code"] = proc.returncode
        modeb_crawl_state["status"] = "stopped"
        modeb_crawl_state["process"] = None
        log_handle = modeb_crawl_state.get("log_handle")
        if log_handle is not None:
            try:
                log_handle.flush()
                log_handle.close()
            except Exception:
                pass
            modeb_crawl_state["log_handle"] = None
        snapshot = _modeb_crawl_snapshot_locked(tail_lines=80)
    return {"success": True, "data": snapshot}


@app.post("/modeb/opinion/qingming/quick_start")
async def modeb_opinion_qingming_quick_start(request: QingmingQuickCrawlRequest):
    """
    清明节舆情一键抓取（简单版）。
    使用固定关键词模板，便于快速演示。
    """
    qingming_keywords = "清明节 乳制品,清明 假期 牛奶,清明 奶粉 投诉,清明 乳制品 变质"
    crawl_req = OpinionCrawlStartRequest(
        mediacrawler_root=request.mediacrawler_root,
        platform=request.platform,
        crawler_type="search",
        login_type=request.login_type,
        keywords=qingming_keywords,
        headless=request.headless,
        get_comment=request.get_comment,
        get_sub_comment=request.get_sub_comment,
        start_page=1,
        max_comments_count_singlenotes=20,
        save_data_option=request.save_data_option,
    )
    return await modeb_opinion_crawl_start(crawl_req)


@app.get("/modeb/opinion/qingming/brief")
async def modeb_opinion_qingming_brief(
    platform: str = Query("all", description="平台: all/weibo/douyin/xhs/..."),
    days: int = Query(15, ge=1, le=120),
    top_n: int = Query(20, ge=5, le=100),
    media_root: Optional[str] = Query(None),
):
    """
    清明节舆情快速简报（轻量统计，不依赖复杂模型）。
    """
    if not MODEB_OPINION_AVAILABLE:
        raise HTTPException(status_code=503, detail="ModeB 舆情模块不可用")
    root = Path(media_root) if media_root else DEFAULT_MEDIA_ROOT
    if not root.exists():
        raise HTTPException(status_code=400, detail=f"MediaCrawler 数据目录不存在: {root}")
    data = build_qingming_brief(
        media_root=root,
        platform=platform,
        days=days,
        top_n=top_n,
    )
    return {"success": True, "data": data}


@app.post("/modeb/opinion/import")
async def modeb_import_opinion(request: OpinionImportRequest):
    """
    导入 MediaCrawler 舆情数据并生成企业舆情特征
    """
    global opinion_feature_by_id, opinion_feature_by_name

    if not MODEB_OPINION_AVAILABLE:
        raise HTTPException(status_code=503, detail="ModeB 舆情模块不可用")

    media_root = Path(request.media_root) if request.media_root else DEFAULT_MEDIA_ROOT
    enterprise_csv = Path(request.enterprise_csv) if request.enterprise_csv else DEFAULT_ENTERPRISE_CSV
    if not media_root.exists():
        raise HTTPException(status_code=400, detail=f"MediaCrawler 数据目录不存在: {media_root}")
    if not enterprise_csv.exists():
        raise HTTPException(status_code=400, detail=f"企业主档不存在: {enterprise_csv}")

    try:
        summary = build_opinion_features(
            media_root=media_root,
            enterprise_csv=enterprise_csv,
            platform=request.platform,
            days=request.days,
        )
        opinion_feature_by_id, opinion_feature_by_name = load_opinion_feature_map(OPINION_FEATURE_CSV)
        return {"success": True, "data": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"舆情导入失败: {e}")


@app.get("/modeb/opinion/summary")
async def modeb_opinion_summary():
    """获取舆情导入摘要"""
    if not MODEB_OPINION_AVAILABLE:
        raise HTTPException(status_code=503, detail="ModeB 舆情模块不可用")
    if not OPINION_SUMMARY_JSON.exists():
        return {
            "success": True,
            "data": {
                "message": "尚未生成舆情特征，请先调用 /modeb/opinion/import",
                "opinion_feature_loaded_count": len(opinion_feature_by_id),
            },
        }
    data = json.loads(OPINION_SUMMARY_JSON.read_text(encoding="utf-8"))
    data["opinion_feature_loaded_count"] = len(opinion_feature_by_id)
    return {"success": True, "data": data}


@app.get("/modeb/opinion/top")
async def modeb_opinion_top(top_n: int = Query(20, ge=1, le=200)):
    """获取舆情风险 TopN 企业"""
    if not MODEB_OPINION_AVAILABLE:
        raise HTTPException(status_code=503, detail="ModeB 舆情模块不可用")
    if not OPINION_FEATURE_CSV.exists():
        return {
            "success": True,
            "data": [],
            "message": "尚未生成舆情特征，请先调用 /modeb/opinion/import",
        }
    rows: List[Dict[str, Any]] = []
    with OPINION_FEATURE_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    rows.sort(key=lambda x: float(x.get("opinion_risk_index", 0.0) or 0.0), reverse=True)
    return {"success": True, "data": rows[:top_n]}


# ==================== 症状驱动评估 API (Mode B) ====================

@app.post("/symptom/assess")
async def symptom_assess(request: SymptomAssessRequest):
    """
    症状驱动风险评估

    输入: 症状描述（如"腹泻、发热、腹痛"）
    输出: 风险因子、关联生产环节、相关企业、监管建议
    """
    if not symptom_router:
        raise HTTPException(status_code=503, detail="症状驱动路由器未初始化")

    try:
        result = symptom_router.assess(request.query, request.product_type)
        linked_enterprises = _enrich_linked_enterprises_with_opinion(result.linked_enterprises)

        # 转换为字典格式
        response_data = {
            "query": result.query,
            "symptoms_detected": result.symptoms_detected,
            "risk_factors": result.risk_factors,
            "stage_candidates": result.stage_candidates,
            "linked_enterprises": linked_enterprises,
            "evidence": result.evidence,
            "risk_level": result.risk_level,
            "confidence": result.confidence,
            "suggested_actions": result.suggested_actions,
            # LLM 增强字段
            "llm_extraction": result.llm_extraction,
            "processing_steps": result.processing_steps,
            "opinion_enabled": MODEB_OPINION_AVAILABLE,
            "opinion_feature_loaded_count": len(opinion_feature_by_id),
        }

        return {
            "success": True,
            "data": response_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"症状评估失败: {str(e)}")


@app.post("/modeb/multimodal/assess")
async def modeb_multimodal_assess(request: ModeBMultimodalAssessRequest):
    """
    ModeB 四模态融合评估：
    - 文本、图片、视频、语音线索融合为统一 query
    - 复用症状驱动风险路由与舆情增强链路
    """
    if not symptom_router:
        raise HTTPException(status_code=503, detail="症状驱动路由器未初始化")

    try:
        composed = _modeb_compose_multimodal_query(
            text=request.text,
            image_items=request.image_items,
            video_items=request.video_items,
            audio_items=request.audio_items,
        )
        fused_query = composed["fused_query"]
        evidence = composed["evidence"]

        qingming_ctx: Optional[Dict[str, Any]] = None
        if request.use_qingming_context and MODEB_OPINION_AVAILABLE:
            qingming_ctx = build_qingming_brief(
                media_root=DEFAULT_MEDIA_ROOT,
                platform=request.qingming_platform,
                days=int(request.qingming_days),
                top_n=10,
            )
            qingming_hint = (
                f" 清明舆情: 命中{qingming_ctx.get('qingming_hits', 0)}条, "
                f"乳制品相关{qingming_ctx.get('qingming_dairy_hits', 0)}条。"
            )
            fused_query = (fused_query + qingming_hint)[:3200]

        result = symptom_router.assess(fused_query, request.product_type)
        linked_enterprises = _enrich_linked_enterprises_with_opinion(result.linked_enterprises)

        payload = {
            "query": result.query,
            "fused_query": fused_query,
            "modalities": evidence,
            "risk_level": result.risk_level,
            "confidence": result.confidence,
            "symptoms_detected": result.symptoms_detected,
            "risk_factors": result.risk_factors,
            "stage_candidates": result.stage_candidates,
            "linked_enterprises": linked_enterprises,
            "suggested_actions": result.suggested_actions,
            "opinion_enabled": MODEB_OPINION_AVAILABLE,
            "opinion_feature_loaded_count": len(opinion_feature_by_id),
            "qingming_context": qingming_ctx,
        }
        return {"success": True, "data": payload}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"四模态评估失败: {e}")


@app.post("/symptom/assess_stream")
async def symptom_assess_stream(request: SymptomAssessRequest):
    """
    症状驱动风险评估 - 流式输出 (SSE)

    实时显示 Minimax M2.5 LLM 症状提取过程
    """
    if not symptom_router:
        raise HTTPException(status_code=503, detail="症状驱动路由器未初始化")

    async def event_generator():
        try:
            # Step 1: 开始处理
            yield f"data: {json.dumps({'step': 'start', 'status': 'started', 'message': '开始症状分析...', 'query': request.query}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)

            # Step 2: LLM 症状提取 (流式显示)
            llm_configured = False
            llm_symptoms = []
            llm_raw = []

            if LLM_EXTRACTOR_AVAILABLE:
                from agent.symptom_extractor import get_symptom_extractor
                extractor = get_symptom_extractor()
                llm_configured = extractor.is_configured()

                if llm_configured:
                    yield f"data: {json.dumps({'step': 'llm_extraction', 'status': 'started', 'message': 'Minimax M2.5 正在分析症状...'}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.1)

                    # 调用 LLM 提取
                    result = extractor.extract_symptoms(request.query)
                    llm_symptoms = result.standardized_symptoms
                    llm_raw = result.raw_symptoms

                    # 流式返回 LLM 结果
                    yield f"data: {json.dumps({
                        'step': 'llm_extraction',
                        'status': 'progress',
                        'message': f'识别到原始症状: {", ".join(llm_raw)}',
                        'raw_symptoms': llm_raw,
                        'latency_ms': result.latency_ms
                    }, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.1)

                    yield f"data: {json.dumps({
                        'step': 'llm_extraction',
                        'status': 'completed',
                        'message': f'标准化症状: {", ".join(llm_symptoms)}',
                        'standardized_symptoms': llm_symptoms,
                        'confidence': result.confidence,
                        'latency_ms': result.latency_ms
                    }, ensure_ascii=False)}\n\n"
                else:
                    yield f"data: {json.dumps({'step': 'llm_extraction', 'status': 'skipped', 'message': 'Minimax API 未配置，使用同义词映射'}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'step': 'llm_extraction', 'status': 'skipped', 'message': 'LLM 提取器不可用'}, ensure_ascii=False)}\n\n"

            await asyncio.sleep(0.1)

            # Step 3: 执行完整评估
            yield f"data: {json.dumps({'step': 'assessment', 'status': 'started', 'message': '正在进行风险评估...'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)

            result = symptom_router.assess(request.query, request.product_type)
            linked_enterprises = _enrich_linked_enterprises_with_opinion(result.linked_enterprises)

            # Step 4: 返回最终结果
            yield f"data: {json.dumps({
                'step': 'assessment',
                'status': 'completed',
                'message': f'评估完成，风险等级: {result.risk_level}',
                'data': {
                    'query': result.query,
                    'symptoms_detected': result.symptoms_detected,
                    'risk_factors': result.risk_factors,
                    'stage_candidates': result.stage_candidates,
                    'linked_enterprises': linked_enterprises[:5],  # 只返回前5个
                    'risk_level': result.risk_level,
                    'confidence': result.confidence,
                    'suggested_actions': result.suggested_actions,
                    'llm_extraction': result.llm_extraction,
                    'processing_steps': result.processing_steps,
                    'opinion_enabled': MODEB_OPINION_AVAILABLE,
                    'opinion_feature_loaded_count': len(opinion_feature_by_id),
                }
            }, ensure_ascii=False)}\n\n"

            # Step 5: 结束
            yield f"data: {json.dumps({'step': 'complete', 'status': 'completed', 'message': '分析完成'}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'step': 'error', 'status': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/symptom/risk_factors")
async def get_risk_factor_library():
    """获取风险因子库（用于前端下拉选择）"""
    if not symptom_router:
        raise HTTPException(status_code=503, detail="症状驱动路由器未初始化")

    # 返回可用的风险因子
    risk_factors = []
    if symptom_router.kb:
        try:
            for rf_id, rf_def in symptom_router.kb.risk_factor_defs.items():
                risk_factors.append({
                    "id": rf_id,
                    "name": rf_def.get("name", rf_id),
                    "category": rf_def.get("category", "未知"),
                    "description": rf_def.get("description", "")[:100]
                })
        except:
            pass

    # 如果知识库不可用，返回备用数据
    if not risk_factors:
        risk_factors = [
            {"id": "microbial_salmonella", "name": "沙门氏菌", "category": "微生物污染"},
            {"id": "microbial_listeria", "name": "李斯特菌", "category": "微生物污染"},
            {"id": "microbial_ecoli", "name": "致病性大肠杆菌", "category": "微生物污染"},
            {"id": "microbial_staph", "name": "金黄色葡萄球菌", "category": "微生物污染"},
            {"id": "chemical_melamine", "name": "三聚氰胺", "category": "化学污染"},
            {"id": "chemical_aflatoxin", "name": "黄曲霉毒素M1", "category": "化学污染"},
        ]

    return {
        "success": True,
        "data": risk_factors
    }


@app.get("/symptom/symptom_library")
async def get_symptom_library():
    """获取症状库（用于前端自动补全）"""
    symptoms = [
        {"id": "symptom_diarrhea", "name": "腹泻", "description": "水样便或稀便，排便次数增多"},
        {"id": "symptom_fever", "name": "发热", "description": "体温升高，可能伴有寒战"},
        {"id": "symptom_vomit", "name": "呕吐", "description": "胃内容物经口排出"},
        {"id": "symptom_abdominal_pain", "name": "腹痛", "description": "腹部疼痛或绞痛"},
        {"id": "symptom_nausea", "name": "恶心", "description": "想吐的感觉"},
        {"id": "symptom_dizziness", "name": "头晕", "description": "头部昏沉感"},
        {"id": "symptom_fatigue", "name": "乏力", "description": "全身无力"},
        {"id": "symptom_allergy", "name": "过敏反应", "description": "皮疹、瘙痒、呼吸困难"},
    ]

    return {
        "success": True,
        "data": symptoms
    }


# 流式风险研判 - Server-Sent Events
@app.post("/assess_stream")
async def assess_stream(request: AssessRequest):
    """
    流式执行风险研判，通过SSE返回每一步的处理状态

    返回事件流，每个事件包含:
    - step: 步骤名称
    - status: 状态 (started/progress/complete/error/skipped)
    - input/output: 输入输出数据
    - llm_prompt/llm_response: LLM相关数据
    - message: 人类可读的消息
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent未初始化")

    async def event_generator():
        try:
            # 使用生成器获取流式更新
            stream = agent.assess_streaming(
                request.query,
                with_propagation=request.with_propagation
            )

            # 遍历所有步骤更新
            for update in stream:
                # 将更新转换为SSE格式
                yield f"data: {json.dumps(update, ensure_ascii=False)}\n\n"

            # 发送最终报告
            try:
                # 获取最终的report（生成器的返回值）
                # 注意：Python生成器的return值需要通过不同的方式获取
                # 这里我们简化处理，在最后一个update中包含report_id
                final_update = {
                    "step": "stream_end",
                    "status": "complete",
                    "message": "流式传输完成"
                }
                yield f"data: {json.dumps(final_update, ensure_ascii=False)}\n\n"
            except Exception as e:
                print(f"获取最终报告出错: {e}")

        except Exception as e:
            error_update = {
                "step": "workflow_error",
                "status": "error",
                "error": str(e),
                "message": f"研判流程出错: {e}"
            }
            yield f"data: {json.dumps(error_update, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# 获取流式研判的完整结果（用于非流式客户端）
@app.post("/assess_with_steps")
async def assess_with_steps(request: AssessRequest):
    """
    执行风险研判并返回所有步骤详情

    返回包含所有中间步骤的完整结果
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent未初始化")

    try:
        steps = []
        report = None

        # 收集所有步骤
        stream = agent.assess_streaming(
            request.query,
            with_propagation=request.with_propagation
        )

        for update in stream:
            steps.append(update)

        # 获取最终报告（简化处理，实际应该通过其他方式获取）
        # 这里我们重新运行一次非流式版本获取报告
        if request.with_propagation:
            report = agent.assess_with_propagation(request.query)
        else:
            report = agent.assess(request.query)

        return {
            "success": True,
            "data": {
                "steps": steps,
                "report": asdict(report)
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 图数据预警API ====================

@app.get("/api/alerts")
async def get_alerts(
    limit: int = Query(50, ge=1, le=200),
    severity: Optional[str] = Query(None, description="严重级别过滤: high/medium/low")
):
    """
    获取预警数据
    
    返回供应链风险预警列表
    """
    try:
        from dairyrisk.api.graph_routes import load_graph_data
        
        data = load_graph_data()
        alerts = data.get('alerts', [])
        
        # 应用过滤
        if severity:
            alerts = [a for a in alerts if a['level'] == severity]
        
        return {
            "success": True,
            "data": {
                "total": len(alerts),
                "alerts": alerts[:limit]
            }
        }
    except Exception as e:
        # 如果图数据不可用，返回模拟预警
        return {
            "success": True,
            "data": {
                "total": 5,
                "alerts": [
                    {
                        "id": f"alert_{i}",
                        "level": "high" if i % 2 == 0 else "medium",
                        "title": f"预警 {i+1}",
                        "message": f"检测到风险信号 {i+1}",
                        "timestamp": "2024-01-01T00:00:00",
                        "intensity": 0.8,
                        "nodeId": f"node_{i}"
                    }
                    for i in range(min(limit, 20))
                ]
            }
        }


# ==================== 子图 & LLM 评估 API ====================

def _parse_ts_local(ts: str | None):
    """解析时间戳字符串为 datetime 对象"""
    if not ts:
        return None
    ts = ts.strip()
    if not ts:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _extract_subgraph_local(
    graph: Dict[str, Any],
    region: Optional[str],
    start_time: Optional[datetime],
    end_time: Optional[datetime],
    seed_node: Optional[str],
    k_hop: int,
    max_nodes: int = 300,
    max_edges: int = 600,
) -> Dict[str, Any]:
    """从完整图中提取满足条件的子图（与 scripts/run_llm_subgraph_assessment.py 逻辑一致）"""
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    node_by_id = {n["node_id"]: n for n in nodes}
    node_by_name = {n["name"]: n for n in nodes}

    # 1) 边级时间过滤
    edge_filtered = []
    for e in edges:
        ts = _parse_ts_local(e.get("timestamp"))
        if start_time and (ts is None or ts < start_time):
            continue
        if end_time and (ts is None or ts > end_time):
            continue
        edge_filtered.append(e)

    # 2) 节点级区域过滤
    base_node_ids = set()
    for n in nodes:
        if region and n.get("region") != region:
            continue
        base_node_ids.add(n["node_id"])

    if not region:
        for e in edge_filtered:
            base_node_ids.add(e["source"])
            base_node_ids.add(e["target"])

    # 3) k-hop 扩展（基于过滤后的边构建邻接表）
    adjacency: Dict[str, set] = defaultdict(set)
    for e in edge_filtered:
        s, t = e["source"], e["target"]
        adjacency[s].add(t)
        adjacency[t].add(s)

    if seed_node:
        seed_id = node_by_name.get(seed_node, {}).get("node_id") if seed_node in node_by_name else seed_node
        if seed_id not in node_by_id:
            raise ValueError(f"seed_node 不存在: {seed_node}")
        allowed = {seed_id}
        q: deque = deque([(seed_id, 0)])
        visited = {seed_id}
        while q:
            cur, depth = q.popleft()
            if depth >= k_hop:
                continue
            for nb in adjacency.get(cur, set()):
                if nb not in visited:
                    visited.add(nb)
                    allowed.add(nb)
                    q.append((nb, depth + 1))
        selected_nodes = allowed & base_node_ids if base_node_ids else allowed
    else:
        selected_nodes = set(base_node_ids)

    sub_edges = [e for e in edge_filtered if e["source"] in selected_nodes and e["target"] in selected_nodes]

    # 优先按边风险降序截断：保证返回的边尽量有意义且节点连通
    sub_edges.sort(key=lambda x: int(x.get("risk_positive_count", 0)), reverse=True)
    sub_edges = sub_edges[:max_edges]

    # 从保留的边中收集节点，再补充高风险独立节点至 max_nodes
    edge_node_ids: set = set()
    for e in sub_edges:
        edge_node_ids.add(e["source"])
        edge_node_ids.add(e["target"])

    # 补充：不在边中但风险高的节点（显示孤立高风险节点）
    all_candidate_nodes = [node_by_id[nid] for nid in selected_nodes if nid in node_by_id]
    all_candidate_nodes.sort(key=lambda x: float(x.get("risk_score", 0.0)), reverse=True)

    kept_ids = set(edge_node_ids)
    for n in all_candidate_nodes:
        if len(kept_ids) >= max_nodes:
            break
        kept_ids.add(n["node_id"])

    sub_nodes = [node_by_id[nid] for nid in kept_ids if nid in node_by_id]
    sub_nodes.sort(key=lambda x: float(x.get("risk_score", 0.0)), reverse=True)

    return {
        "meta": {
            "region": region,
            "start_time": start_time.isoformat() if start_time else None,
            "end_time": end_time.isoformat() if end_time else None,
            "seed_node": seed_node,
            "k_hop": k_hop,
            "node_count": len(sub_nodes),
            "edge_count": len(sub_edges),
            "capped": len(sub_nodes) >= max_nodes or len(sub_edges) >= max_edges,
        },
        "nodes": sub_nodes,
        "edges": sub_edges,
    }


def _compute_time_window(graph: Dict[str, Any], time_window_days: int):
    """计算时间窗口：取图中最大时间戳往前推 time_window_days 天"""
    max_ts = None
    for e in graph.get("edges", []):
        ts = _parse_ts_local(e.get("timestamp"))
        if ts and (max_ts is None or ts > max_ts):
            max_ts = ts
    if max_ts is None:
        max_ts = datetime.now()
    start_ts = max_ts - timedelta(days=time_window_days)
    return start_ts, max_ts


@app.get("/api/graph/search")
async def search_graph_nodes(
    q: str = Query(..., description="企业名称关键词"),
    limit: int = Query(10, ge=1, le=50),
):
    """按企业名模糊搜索异构图节点，返回 node_id + name + type + risk_score"""
    if llm_graph is None:
        raise HTTPException(status_code=503, detail="LLM 图尚未加载")
    q_lower = q.strip().lower()
    results = [
        {
            "node_id": n["node_id"],
            "name": n["name"],
            "node_type": n.get("node_type", "未知"),
            "risk_score": n.get("risk_score", 0.0),
            "risk_level": n.get("risk_level", "low"),
            "product_tag": n.get("product_tag", "dairy_general"),
        }
        for n in llm_graph["nodes"]
        if q_lower in n.get("name", "").lower()
    ]
    results.sort(key=lambda x: x["risk_score"], reverse=True)
    return {"success": True, "data": results[:limit], "total": len(results)}


@app.get("/api/graph/subgraph")
async def get_subgraph(
    region: Optional[str] = Query("上海", description="区域过滤，留空则不过滤"),
    time_window: int = Query(30, ge=1, le=365, description="时间窗口（天），基于图中最新时间戳往前推"),
    k_hop: int = Query(2, ge=1, le=5, description="k-hop 邻域深度"),
    seed_node: Optional[str] = Query(None, description="种子节点名称或 node_id（留空则不做 k-hop 扩展）"),
    max_nodes: int = Query(300, ge=10, le=1000, description="返回节点数上限"),
    max_edges: int = Query(600, ge=10, le=3000, description="返回边数上限"),
):
    """
    提取 LLM 异构图的子图

    - 先按 time_window 过滤边（从图内最大时间戳往前推 N 天）
    - 再按 region 过滤节点
    - 若指定 seed_node，对其做 k-hop BFS 扩展
    - 结果按风险分数降序，并截断到 max_nodes/max_edges
    """
    if llm_graph is None:
        raise HTTPException(
            status_code=503,
            detail="LLM 图尚未加载，请先运行 scripts/prepare_llm_hetero_graph.py 生成 data/llm_graph/graph_llm_ready.json"
        )

    try:
        start_ts, end_ts = _compute_time_window(llm_graph, time_window)
        subgraph = _extract_subgraph_local(
            graph=llm_graph,
            region=region if region else None,
            start_time=start_ts,
            end_time=end_ts,
            seed_node=seed_node,
            k_hop=k_hop,
            max_nodes=max_nodes,
            max_edges=max_edges,
        )
        return {"success": True, "data": subgraph}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"子图提取失败: {e}")


class LLMAssessRequest(BaseModel):
    region: Optional[str] = "上海"
    time_window: int = 30
    k_hop: int = 2
    seed_node: Optional[str] = None
    use_mock_llm: bool = False


@app.post("/api/modea/llm_assess")
async def llm_assess_subgraph(request: LLMAssessRequest):
    """
    对指定子图执行 LLM 风险评估（Mode A 子图版本）

    流程：
    1. 按参数提取子图
    2. 汇总子图风险指标（高/中/低节点分布、top nodes）
    3. 调用 LLM（或 mock）生成风险评估报告
    """
    if llm_graph is None:
        raise HTTPException(
            status_code=503,
            detail="LLM 图尚未加载，请先运行 scripts/prepare_llm_hetero_graph.py"
        )

    try:
        start_ts, end_ts = _compute_time_window(llm_graph, request.time_window)
        subgraph = _extract_subgraph_local(
            graph=llm_graph,
            region=request.region if request.region else None,
            start_time=start_ts,
            end_time=end_ts,
            seed_node=request.seed_node,
            k_hop=request.k_hop,
        )

        nodes = subgraph["nodes"]
        edges = subgraph["edges"]

        if not nodes:
            return {
                "success": True,
                "data": {
                    "subgraph_meta": subgraph["meta"],
                    "rule_summary": {"risk_level": "low", "risk_score": 0.0, "top_nodes": []},
                    "llm": {"success": False, "content": None, "error": "子图为空，无法评估"},
                }
            }

        # 汇总风险
        risk_scores = [float(n.get("risk_score", 0.0)) for n in nodes]
        avg_risk = sum(risk_scores) / max(len(risk_scores), 1)
        high_cnt = sum(1 for n in nodes if n.get("risk_level") == "high")
        med_cnt = sum(1 for n in nodes if n.get("risk_level") == "medium")

        if avg_risk >= 0.45 or high_cnt >= max(1, len(nodes) // 8):
            risk_level = "high"
        elif avg_risk >= 0.25 or med_cnt >= max(1, len(nodes) // 4):
            risk_level = "medium"
        else:
            risk_level = "low"

        risk_score_100 = round(avg_risk * 100, 2)
        top_nodes = sorted(nodes, key=lambda x: float(x.get("risk_score", 0.0)), reverse=True)[:5]

        triggered_rules = [
            {"factor": "subgraph_high_risk_node_ratio", "reason": f"high={high_cnt}/{len(nodes)}", "score": round(min(100, 30 + high_cnt * 8), 2)},
            {"factor": "subgraph_avg_node_risk", "reason": f"avg={avg_risk:.3f}", "score": risk_score_100},
            {"factor": "subgraph_structure_complexity", "reason": f"nodes={len(nodes)}, edges={len(edges)}", "score": round(min(100, len(edges) / max(len(nodes), 1) * 20), 2)},
        ]
        supply_chain_context = {
            "nodes": [{"id": n["node_id"], "name": n["name"], "risk": n.get("risk_level")} for n in top_nodes],
            "edges": edges[:20],
            "complexity_score": round(len(edges) / max(len(nodes), 1), 3),
        }

        # 调用 LLM
        from agent.llm_client import get_llm_client
        use_mock = request.use_mock_llm or not bool(os.environ.get("MINIMAX_API_KEY"))
        llm_client = get_llm_client(use_mock=use_mock)

        target_name = f"Subgraph[{request.region or 'all'}|t={request.time_window}d|k={request.k_hop}]"
        response = llm_client.generate_risk_report(
            target_name=target_name,
            target_type="enterprise",
            risk_level=risk_level,
            risk_score=risk_score_100,
            triggered_rules=triggered_rules,
            evidence={"inspections": [], "events": []},
            supply_chain_context=supply_chain_context,
            similar_cases=[],
        )

        return {
            "success": True,
            "data": {
                "query": {
                    "region": request.region,
                    "time_window": request.time_window,
                    "k_hop": request.k_hop,
                    "seed_node": request.seed_node,
                },
                "subgraph_meta": subgraph["meta"],
                "rule_summary": {
                    "risk_level": risk_level,
                    "risk_score": risk_score_100,
                    "high_count": high_cnt,
                    "medium_count": med_cnt,
                    "low_count": len(nodes) - high_cnt - med_cnt,
                    "top_nodes": [
                        {"node_id": n["node_id"], "name": n["name"], "risk_level": n.get("risk_level"), "risk_score": n.get("risk_score")}
                        for n in top_nodes
                    ],
                },
                "llm": {
                    "success": response.success,
                    "latency_ms": response.latency_ms,
                    "error": response.error,
                    "content": response.content,
                    "usage": response.usage,
                    "mock": use_mock,
                },
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"LLM 评估失败: {e}")


# ==================== ModelA v2 API ====================

def _modela_uncertainty(node: Dict[str, Any], product_type: Optional[str] = None) -> float:
    """基于风险分布熵 + 证据稀缺度估计不确定性（0~1，越高越不确定）。"""
    vec = node.get("risk_probabilities", []) or []
    if product_type:
        vec = node.get("category_risk_probabilities", {}).get(product_type, vec)
    if not vec:
        return 1.0
    probs = [max(1e-6, min(1.0, float(x))) for x in vec]
    total = sum(probs)
    norm = [p / total for p in probs] if total > 0 else [1.0 / len(probs)] * len(probs)
    # 归一化熵
    import math

    entropy = -sum(p * math.log(p) for p in norm) / max(math.log(len(norm)), 1e-6)
    profile = node.get("profile_features", {})
    inspection_cnt = float(profile.get("历史抽检次数", 0))
    evidence_conf = min(1.0, inspection_cnt / 60.0)
    return round(max(0.0, min(1.0, 0.65 * entropy + 0.35 * (1.0 - evidence_conf))), 6)


def _modela_category_score(node: Dict[str, Any], product_type: Optional[str]) -> float:
    if product_type:
        vec = node.get("category_risk_probabilities", {}).get(product_type)
        if vec:
            return float(max(vec))
    return float(node.get("risk_score", 0.0))


def _modela_priority(node: Dict[str, Any], product_type: Optional[str]) -> float:
    risk = _modela_category_score(node, product_type)
    unc = _modela_uncertainty(node, product_type)
    return round(min(1.0, risk * (1.0 + 0.45 * unc)), 6)


def _modela_ranking_nodes(
    graph: Dict[str, Any],
    product_type: Optional[str],
    node_type: Optional[str],
) -> List[Dict[str, Any]]:
    ranked = []
    for n in graph.get("nodes", []):
        if node_type and n.get("node_type") != node_type:
            continue
        risk = _modela_category_score(n, product_type)
        unc = _modela_uncertainty(n, product_type)
        pri = _modela_priority(n, product_type)
        ranked.append(
            {
                "node_id": n.get("node_id"),
                "name": n.get("name"),
                "node_type": n.get("node_type"),
                "enterprise_scale": n.get("enterprise_scale"),
                "risk_score": round(risk, 6),
                "uncertainty": unc,
                "priority_score": pri,
                "profile_features": n.get("profile_features", {}),
            }
        )
    ranked.sort(key=lambda x: x["priority_score"], reverse=True)
    return ranked


def _modela_risk_level(score: float) -> str:
    if score >= 0.66:
        return "high"
    if score >= 0.38:
        return "medium"
    return "low"


def _modela_quantile(values: List[float], q: float) -> float:
    if not values:
        return 1.0
    arr = sorted(float(v) for v in values)
    if len(arr) == 1:
        return arr[0]
    q = max(0.0, min(1.0, float(q)))
    idx = int(round((len(arr) - 1) * q))
    return arr[max(0, min(len(arr) - 1, idx))]


def _modela_thresholds(vectors: List[List[float]], top_ratio: float) -> List[float]:
    ratio = max(0.001, min(0.5, float(top_ratio)))
    q = 1.0 - ratio
    out = []
    for i in range(7):
        vals = [float(v[i]) for v in vectors if len(v) > i]
        out.append(round(_modela_quantile(vals, q), 6))
    return out


def _modela_node_vec(node: Dict[str, Any], product_type: Optional[str]) -> List[float]:
    if product_type:
        vec = node.get("category_risk_probabilities", {}).get(product_type)
        if vec:
            return [float(x) for x in vec]
    return [float(x) for x in (node.get("risk_probabilities", []) or [0.0] * 7)]


def _modela_extract_view(
    graph: Dict[str, Any],
    view_mode: str,
    product_type: Optional[str],
    seed_node: Optional[str],
    k_hop: int,
    max_nodes: int,
    max_edges: int,
    top_ratio: float = 0.05,
) -> Dict[str, Any]:
    edges_all = graph.get("edges", [])
    nodes_all = graph.get("nodes", [])
    node_by_id = {n.get("node_id"): n for n in nodes_all if n.get("node_id")}
    node_by_name = {n.get("name"): n for n in nodes_all if n.get("name")}

    if view_mode not in {"full", "product"}:
        raise ValueError("view_mode 仅支持 full 或 product")
    if view_mode == "product" and not product_type:
        raise ValueError("view_mode=product 时必须提供 product_type")

    if product_type:
        filtered_edges = [e for e in edges_all if e.get("dairy_product_type") == product_type]
    else:
        filtered_edges = list(edges_all)

    selected_edge_indices = set()
    selected_node_ids = set()
    if seed_node:
        seed_id = seed_node
        if seed_node in node_by_name:
            seed_id = node_by_name[seed_node]["node_id"]
        if seed_id not in node_by_id:
            raise ValueError(f"seed_node 不存在: {seed_node}")
        adjacency: Dict[str, set] = defaultdict(set)
        edge_bucket: Dict[tuple, List[int]] = defaultdict(list)
        for idx, edge in enumerate(filtered_edges):
            s, t = edge.get("source"), edge.get("target")
            if not s or not t:
                continue
            adjacency[s].add(t)
            adjacency[t].add(s)
            edge_bucket[(s, t)].append(idx)
            edge_bucket[(t, s)].append(idx)
        depth_limit = max(1, int(k_hop))
        queue = deque([(seed_id, 0)])
        visited = {seed_id}
        selected_node_ids.add(seed_id)
        while queue:
            cur, dep = queue.popleft()
            if dep >= depth_limit:
                continue
            for nxt in adjacency.get(cur, set()):
                if nxt not in visited:
                    visited.add(nxt)
                    selected_node_ids.add(nxt)
                    queue.append((nxt, dep + 1))
                for ei in edge_bucket.get((cur, nxt), []):
                    selected_edge_indices.add(ei)
    else:
        for idx, edge in enumerate(filtered_edges):
            selected_edge_indices.add(idx)
            selected_node_ids.add(edge.get("source"))
            selected_node_ids.add(edge.get("target"))

    chosen_edges = [filtered_edges[i] for i in sorted(selected_edge_indices)]
    chosen_edges.sort(key=lambda e: float(max(e.get("risk_probabilities", [0.0]))), reverse=True)
    capped_edges = len(chosen_edges) > max_edges
    chosen_edges = chosen_edges[:max_edges]

    connected_nodes = set()
    for edge in chosen_edges:
        connected_nodes.add(edge.get("source"))
        connected_nodes.add(edge.get("target"))
    for node_id in selected_node_ids:
        if len(connected_nodes) >= max_nodes:
            break
        connected_nodes.add(node_id)

    node_candidates = [node_by_id[nid] for nid in connected_nodes if nid in node_by_id]
    node_candidates.sort(
        key=lambda n: max(_modela_node_vec(n, product_type)),
        reverse=True,
    )
    capped_nodes = len(node_candidates) > max_nodes
    chosen_nodes = node_candidates[:max_nodes]
    keep_node_ids = {n["node_id"] for n in chosen_nodes}
    chosen_edges = [e for e in chosen_edges if e.get("source") in keep_node_ids and e.get("target") in keep_node_ids]

    node_view = []
    for n in chosen_nodes:
        vec = _modela_node_vec(n, product_type)
        score = max(vec) if vec else 0.0
        node_view.append(
            {
                **n,
                "view_scope": view_mode,
                "view_product_type": product_type,
                "view_risk_probabilities": vec,
                "view_risk_score": round(float(score), 6),
                "view_risk_level": _modela_risk_level(float(score)),
            }
        )

    edge_view = []
    for e in chosen_edges:
        vec = [float(x) for x in (e.get("risk_probabilities", []) or [0.0] * 7)]
        score = max(vec) if vec else 0.0
        edge_view.append(
            {
                **e,
                "view_scope": view_mode,
                "view_product_type": product_type,
                "view_risk_probabilities": vec,
                "view_risk_score": round(float(score), 6),
                "view_risk_level": _modela_risk_level(float(score)),
            }
        )

    risk_keys = graph.get("meta", {}).get("risk_dimensions", [])
    if len(risk_keys) != 7:
        risk_keys = [
            "non_food_additives",
            "pesticide_vet_residue",
            "food_additive_excess",
            "microbial_contamination",
            "heavy_metal",
            "biotoxin",
            "other_contaminants",
        ]
    node_thresholds = _modela_thresholds([n.get("view_risk_probabilities", [0.0] * 7) for n in node_view], top_ratio)
    edge_thresholds = _modela_thresholds([e.get("view_risk_probabilities", [0.0] * 7) for e in edge_view], top_ratio)

    for n in node_view:
        vec = n.get("view_risk_probabilities", [0.0] * 7)
        flags = {risk_keys[i]: bool(float(vec[i]) >= float(node_thresholds[i])) for i in range(7)}
        n["top5_flags"] = flags
        n["top5_count"] = int(sum(1 for v in flags.values() if v))
        n["is_top5_any"] = bool(n["top5_count"] > 0)

    for e in edge_view:
        vec = e.get("view_risk_probabilities", [0.0] * 7)
        flags = {risk_keys[i]: bool(float(vec[i]) >= float(edge_thresholds[i])) for i in range(7)}
        e["top5_flags"] = flags
        e["top5_count"] = int(sum(1 for v in flags.values() if v))
        e["is_top5_any"] = bool(e["top5_count"] > 0)

    return {
        "meta": {
            "view_mode": view_mode,
            "product_type": product_type,
            "seed_node": seed_node,
            "k_hop": k_hop,
            "node_count": len(node_view),
            "edge_count": len(edge_view),
            "risk_dimensions": risk_keys,
            "risk_dimensions_zh": graph.get("meta", {}).get("risk_dimensions_zh", []),
            "top5_thresholds": {
                "ratio": float(top_ratio),
                "node": dict(zip(risk_keys, node_thresholds)),
                "edge": dict(zip(risk_keys, edge_thresholds)),
            },
            "capped_nodes": capped_nodes,
            "capped_edges": capped_edges,
        },
        "nodes": node_view,
        "edges": edge_view,
    }


def _modela_stable_random_01(key: str) -> float:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], byteorder="big", signed=False)
    return value / float(2**64 - 1)


def _modela_month_index(month: str) -> int:
    """将 YYYY-MM / YYYYMM 转为整数索引，异常时返回 0。"""
    s = str(month or "").strip().replace("/", "-")
    if not s:
        return 0
    try:
        if "-" in s:
            y, m = s.split("-", 1)
            return int(y) * 12 + int(m)
        if len(s) == 6:
            return int(s[:4]) * 12 + int(s[4:6])
    except Exception:
        return 0
    return 0


def _modela_build_month_graph(
    base_graph: Dict[str, Any],
    month: str,
    product_type: Optional[str],
    seed: int,
) -> Dict[str, Any]:
    """
    根据月份对边进行确定性扰动，构造“同节点、异边关系”的月度图。
    说明：这是流程验证用的可复现实验图，不代表真实业务观测。
    """
    month_idx = _modela_month_index(month)
    edges_in = base_graph.get("edges", [])
    nodes_in = base_graph.get("nodes", [])

    if product_type:
        edges_src = [e for e in edges_in if e.get("dairy_product_type") == product_type]
    else:
        edges_src = list(edges_in)

    if not edges_src:
        edges_src = list(edges_in)

    selected_edges: List[Dict[str, Any]] = []
    node_sum: Dict[str, List[float]] = defaultdict(lambda: [0.0] * 7)
    node_cnt: Dict[str, int] = defaultdict(int)
    global_sum = [0.0] * 7
    global_cnt = 0

    for e in edges_src:
        eid = str(e.get("edge_id") or "")
        if not eid:
            continue
        prod = str(e.get("dairy_product_type") or "")
        src_t = str(e.get("source_type") or "")
        dst_t = str(e.get("target_type") or "")
        base_keep = 0.70 + 0.15 * math.sin(month_idx * 0.23 + len(prod) * 0.17)
        stage_bias = 0.06 if src_t == "原奶供应商" else 0.0
        stage_bias += 0.04 if dst_t == "零售终端" else 0.0
        keep_prob = max(0.30, min(0.96, base_keep + stage_bias))
        keep_draw = _modela_stable_random_01(f"keep|{seed}|{month}|{eid}")
        if keep_draw > keep_prob:
            continue

        vec = [float(x) for x in (e.get("risk_probabilities", []) or [0.0] * 7)]
        if len(vec) < 7:
            vec = vec + [0.0] * (7 - len(vec))
        out_vec: List[float] = []
        for i in range(7):
            season = 0.05 * math.sin((month_idx + i + 1) * 0.41)
            jitter = (_modela_stable_random_01(f"jit|{seed}|{month}|{eid}|{i}") - 0.5) * 0.22
            v = max(0.0, min(1.0, vec[i] * (1.0 + season + jitter)))
            out_vec.append(round(v, 6))
            global_sum[i] += v
        global_cnt += 1

        item = dict(e)
        item["risk_probabilities"] = out_vec
        item["risk_vector"] = out_vec
        selected_edges.append(item)

        s = item.get("source")
        t = item.get("target")
        if s:
            for i in range(7):
                node_sum[s][i] += out_vec[i]
            node_cnt[s] += 1
        if t:
            for i in range(7):
                node_sum[t][i] += out_vec[i]
            node_cnt[t] += 1

    if global_cnt <= 0:
        global_avg = [0.0] * 7
    else:
        global_avg = [global_sum[i] / global_cnt for i in range(7)]

    nodes_out: List[Dict[str, Any]] = []
    for n in nodes_in:
        nid = n.get("node_id")
        item = dict(n)
        old_vec = [float(x) for x in (item.get("risk_probabilities", []) or [0.0] * 7)]
        if len(old_vec) < 7:
            old_vec = old_vec + [0.0] * (7 - len(old_vec))
        local = node_sum.get(nid, global_avg)
        cnt = node_cnt.get(nid, 0)
        if cnt > 0:
            local = [v / cnt for v in local]
        new_vec: List[float] = []
        for i in range(7):
            exposure_delta = local[i] - global_avg[i]
            jitter = (_modela_stable_random_01(f"n-jit|{seed}|{month}|{nid}|{i}") - 0.5) * 0.08
            nv = max(0.0, min(1.0, old_vec[i] + 0.22 * exposure_delta + jitter))
            new_vec.append(round(nv, 6))
        item["risk_probabilities"] = new_vec
        item["risk_vector"] = new_vec
        item["risk_score"] = round(max(new_vec), 6)
        if product_type:
            cat = dict(item.get("category_risk_probabilities", {}) or {})
            cat[product_type] = new_vec
            item["category_risk_probabilities"] = cat
        nodes_out.append(item)

    out = {
        "meta": {
            **(base_graph.get("meta", {}) or {}),
            "temporal_mode": True,
            "month": month,
            "seed": int(seed),
            "source_node_count": len(nodes_in),
            "source_edge_count": len(edges_src),
            "node_count": len(nodes_out),
            "edge_count": len(selected_edges),
            "product_type": product_type,
        },
        "nodes": nodes_out,
        "edges": selected_edges,
    }
    return out


def _modela_precision_recall_at_k(
    ranked_ids: List[str],
    labels: Dict[str, int],
    top_k: int,
) -> Dict[str, float]:
    k = max(1, min(int(top_k), len(ranked_ids)))
    top_ids = ranked_ids[:k]
    top_pos = sum(1 for nid in top_ids if int(labels.get(nid, 0)) == 1)
    total_pos = sum(int(v) for v in labels.values())
    return {
        "top_k": k,
        "positive_total": int(total_pos),
        "positive_in_top_k": int(top_pos),
        "precision_at_k": round(top_pos / max(k, 1), 6),
        "recall_at_k": round(top_pos / max(total_pos, 1), 6),
    }


def _modela_risk_buckets(scores: List[float]) -> Dict[str, int]:
    high = sum(1 for s in scores if s >= 0.66)
    mid = sum(1 for s in scores if 0.38 <= s < 0.66)
    low = sum(1 for s in scores if s < 0.38)
    return {"high": int(high), "medium": int(mid), "low": int(low)}


class ModelAModeAReportRequest(BaseModel):
    view_mode: str = "product"
    product_type: Optional[str] = None
    seed_node: Optional[str] = None
    k_hop: int = 0
    max_nodes: int = 400
    max_edges: int = 1500
    top_ratio: float = 0.05
    use_mock_llm: bool = False


class ModelAResourcePlanRequest(BaseModel):
    product_type: Optional[str] = None
    node_type: Optional[str] = None
    budget: float = 100.0
    max_enterprises: int = 20
    max_nodes: int = 2000
    max_edges: int = 15000
    cost_large: float = 1.8
    cost_medium: float = 1.2
    cost_small: float = 1.0
    min_samples_per_type: int = 0


class ModelATemporalSimRequest(BaseModel):
    """
    月度训练/测试 + 抽检反馈模拟请求。
    用于在缺少真实月度标签时进行流程验证与演示。
    """

    train_month: str = "2025-01"
    test_month: str = "2025-02"
    product_type: Optional[str] = None
    node_type: Optional[str] = None
    max_nodes: int = 5000
    max_edges: int = 50000
    top_ratio: float = 0.05
    top_k: int = 50
    inspect_count: int = 120
    explore_weight: float = 0.35
    seed: int = 42

@app.get("/api/modela/v2/meta")
async def modela_v2_meta():
    """返回 ModelA v2 元信息与构建状态。"""
    try:
        graph = _ensure_modela_v2_graph(force_rebuild=False)
        return {"success": True, "data": graph.get("meta", {})}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载 ModelA v2 元信息失败: {e}")


@app.get("/api/modela/v2/categories")
async def modela_v2_categories():
    """返回乳制品品类列表。"""
    try:
        graph = _ensure_modela_v2_graph(force_rebuild=False)
        categories = graph.get("meta", {}).get("product_categories", [])
        return {"success": True, "data": categories, "total": len(categories)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载品类失败: {e}")


@app.get("/api/modela/v2/subgraph")
async def modela_v2_subgraph(
    product_type: str = Query(..., description="乳制品品类"),
    seed_node: Optional[str] = Query(None, description="种子节点名称或ID"),
    k_hop: int = Query(0, ge=0, le=5, description="子图k-hop范围，0表示不过滤"),
    max_nodes: int = Query(500, ge=10, le=5000),
    max_edges: int = Query(2000, ge=10, le=50000),
):
    """按品类提取子图，并返回节点/边7类风险概率。"""
    try:
        graph = _ensure_modela_v2_graph(force_rebuild=False)
        subgraph = extract_category_subgraph(
            graph=graph,
            product_type=product_type,
            k_hop=k_hop,
            seed_node=seed_node,
            max_nodes=max_nodes,
            max_edges=max_edges,
        )
        if MODELA_FORMULA_AVAILABLE:
            subgraph = compute_formula_scores(
                subgraph,
                query_context={
                    "view_mode": "product",
                    "product_type": product_type,
                    "seed_node": seed_node,
                    "k_hop": k_hop,
                },
            )
        return {"success": True, "data": subgraph}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ModelA v2 子图提取失败: {e}")


@app.get("/api/modela/v2/view")
async def modela_v2_view(
    view_mode: str = Query("product", description="full 或 product"),
    product_type: Optional[str] = Query(None, description="乳制品品类，view_mode=product 时必填"),
    seed_node: Optional[str] = Query(None, description="种子节点名称或ID"),
    k_hop: int = Query(0, ge=0, le=5),
    max_nodes: int = Query(600, ge=50, le=5000),
    max_edges: int = Query(4000, ge=100, le=50000),
    top_ratio: float = Query(0.05, gt=0.0, le=0.2),
):
    """统一图视图接口：支持全图/品类子图，返回节点与边的Top5%风险标签。"""
    try:
        graph = _ensure_modela_v2_graph(force_rebuild=False)
        data = _modela_extract_view(
            graph=graph,
            view_mode=view_mode,
            product_type=product_type,
            seed_node=seed_node,
            k_hop=k_hop,
            max_nodes=max_nodes,
            max_edges=max_edges,
            top_ratio=top_ratio,
        )
        if MODELA_FORMULA_AVAILABLE:
            data = compute_formula_scores(
                data,
                query_context={
                    "view_mode": view_mode,
                    "product_type": product_type,
                    "seed_node": seed_node,
                    "k_hop": k_hop,
                },
            )
        return {"success": True, "data": data}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ModelA v2 视图提取失败: {e}")


@app.post("/api/modela/v2/modea_report")
async def modela_v2_modea_report(request: ModelAModeAReportRequest):
    """
    Mode A 结论与策略报告（LLM驱动）：
    先按全图/品类图提取视图，再汇总规则指标，最后调用 LLM 生成报告。
    """
    try:
        graph = _ensure_modela_v2_graph(force_rebuild=False)
        view = _modela_extract_view(
            graph=graph,
            view_mode=request.view_mode,
            product_type=request.product_type,
            seed_node=request.seed_node,
            k_hop=request.k_hop,
            max_nodes=request.max_nodes,
            max_edges=request.max_edges,
            top_ratio=request.top_ratio,
        )
        if MODELA_FORMULA_AVAILABLE:
            view = compute_formula_scores(
                view,
                query_context={
                    "view_mode": request.view_mode,
                    "product_type": request.product_type,
                    "seed_node": request.seed_node,
                    "k_hop": request.k_hop,
                },
            )
        nodes = view.get("nodes", [])
        edges = view.get("edges", [])
        if not nodes:
            return {
                "success": True,
                "data": {
                    "query": request.dict(),
                    "view_meta": view.get("meta", {}),
                    "rule_summary": {"risk_level": "low", "risk_score": 0.0, "top_nodes": []},
                    "llm": {"success": False, "content": None, "error": "图为空，无法生成报告"},
                },
            }

        node_risk_scores = [float(n.get("risk_proxy", n.get("view_risk_score", 0.0))) for n in nodes]
        node_priority_scores = [float(n.get("priority_score", n.get("view_risk_score", 0.0))) for n in nodes]
        edge_scores = [float(e.get("edge_risk_proxy", e.get("view_risk_score", 0.0))) for e in edges] if edges else [0.0]
        avg_node_risk = sum(node_risk_scores) / max(len(node_risk_scores), 1)
        avg_priority = sum(node_priority_scores) / max(len(node_priority_scores), 1)
        avg_edge_risk = sum(edge_scores) / max(len(edge_scores), 1)
        high_node_cnt = sum(1 for n in nodes if float(n.get("priority_score", n.get("view_risk_score", 0.0))) >= 0.66)
        top5_node_cnt = sum(1 for n in nodes if bool(n.get("is_top5_any")))
        uncertainty_scores = [float(n.get("uncertainty_proxy", _modela_uncertainty(n, request.product_type))) for n in nodes]
        credibility_scores = [float(n.get("credibility_proxy", 0.0)) for n in nodes]
        avg_uncertainty = sum(uncertainty_scores) / max(len(uncertainty_scores), 1)
        avg_credibility = sum(credibility_scores) / max(len(credibility_scores), 1) if credibility_scores else 0.0

        weighted_score = 0.55 * avg_priority + 0.25 * avg_edge_risk + 0.20 * avg_uncertainty
        risk_score_100 = round(weighted_score * 100, 2)
        if weighted_score >= 0.58 or high_node_cnt >= max(1, len(nodes) // 10):
            risk_level = "high"
        elif weighted_score >= 0.34:
            risk_level = "medium"
        else:
            risk_level = "low"

        top_nodes = sorted(
            nodes,
            key=lambda x: float(x.get("priority_score", x.get("view_risk_score", 0.0))),
            reverse=True,
        )[:8]
        triggered_rules = [
            {
                "factor": "node_avg_priority",
                "reason": f"avg_priority={avg_priority:.4f}",
                "score": round(avg_priority * 100, 2),
            },
            {
                "factor": "edge_avg_risk",
                "reason": f"avg_edge_risk={avg_edge_risk:.4f}",
                "score": round(avg_edge_risk * 100, 2),
            },
            {
                "factor": "high_risk_node_ratio",
                "reason": f"high={high_node_cnt}/{len(nodes)}",
                "score": round(high_node_cnt / max(len(nodes), 1) * 100, 2),
            },
            {
                "factor": "top5_hotspot_ratio",
                "reason": f"top5_any={top5_node_cnt}/{len(nodes)}",
                "score": round(top5_node_cnt / max(len(nodes), 1) * 100, 2),
            },
            {
                "factor": "uncertainty_penalty",
                "reason": f"avg_uncertainty={avg_uncertainty:.4f}",
                "score": round(avg_uncertainty * 100, 2),
            },
            {
                "factor": "credibility_support",
                "reason": f"avg_credibility={avg_credibility:.4f}",
                "score": round(avg_credibility * 100, 2),
            },
        ]

        supply_chain_context = {
            "nodes": [
                {
                    "id": n.get("node_id"),
                    "name": n.get("name"),
                    "risk": _modela_risk_level(float(n.get("priority_score", n.get("view_risk_score", 0.0)))),
                    "score": n.get("priority_score", n.get("view_risk_score")),
                }
                for n in top_nodes
            ],
            "edges": edges[:30],
            "complexity_score": round(len(edges) / max(len(nodes), 1), 3),
            "view_mode": request.view_mode,
            "product_type": request.product_type,
        }

        from agent.llm_client import get_llm_client

        use_mock = request.use_mock_llm or not bool(os.environ.get("MINIMAX_API_KEY"))
        llm_client = get_llm_client(use_mock=use_mock)
        response = llm_client.generate_risk_report(
            target_name=f"ModelA-v2[{request.view_mode}|{request.product_type or 'ALL'}]",
            target_type="enterprise",
            risk_level=risk_level,
            risk_score=risk_score_100,
            triggered_rules=triggered_rules,
            evidence={"inspections": [], "events": []},
            supply_chain_context=supply_chain_context,
            similar_cases=[],
        )

        return {
            "success": True,
            "data": {
                "query": request.dict(),
                "view_meta": view.get("meta", {}),
                "rule_summary": {
                    "risk_level": risk_level,
                    "risk_score": risk_score_100,
                    "high_count": high_node_cnt,
                    "low_count": len(nodes) - high_node_cnt,
                    "avg_node_risk": round(avg_node_risk, 6),
                    "avg_priority": round(avg_priority, 6),
                    "avg_edge_risk": round(avg_edge_risk, 6),
                    "avg_uncertainty": round(avg_uncertainty, 6),
                    "avg_credibility": round(avg_credibility, 6),
                    "top_nodes": [
                        {
                            "node_id": n.get("node_id"),
                            "name": n.get("name"),
                            "risk_level": _modela_risk_level(float(n.get("priority_score", n.get("view_risk_score", 0.0)))),
                            "risk_score": n.get("priority_score", n.get("view_risk_score")),
                        }
                        for n in top_nodes
                    ],
                },
                "llm": {
                    "success": response.success,
                    "latency_ms": response.latency_ms,
                    "error": response.error,
                    "content": response.content,
                    "usage": response.usage,
                    "mock": use_mock,
                },
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"ModeA 报告生成失败: {e}")


@app.get("/api/modela/v2/screening")
async def modela_v2_screening(
    product_type: Optional[str] = Query(None, description="乳制品品类"),
    node_type: Optional[str] = Query(None, description="节点类型，如 原奶供应商"),
    top_n: int = Query(10, ge=1, le=500),
    max_nodes: int = Query(2000, ge=200, le=5000),
    max_edges: int = Query(15000, ge=1000, le=50000),
):
    """
    目标1+2：初始筛选 + 不确定性量化（优先级排序）
    """
    try:
        graph = _ensure_modela_v2_graph(force_rebuild=False)
        if MODELA_FORMULA_AVAILABLE:
            view = _modela_extract_view(
                graph=graph,
                view_mode="product" if product_type else "full",
                product_type=product_type,
                seed_node=None,
                k_hop=0,
                max_nodes=max_nodes,
                max_edges=max_edges,
                top_ratio=0.05,
            )
            scored = compute_formula_scores(
                view,
                query_context={
                    "view_mode": "product" if product_type else "full",
                    "product_type": product_type,
                    "seed_node": None,
                    "k_hop": 0,
                    "node_type": node_type,
                },
            )
            ranked_nodes = rank_nodes_by_priority(scored, node_type=node_type, top_n=max(5000, top_n))
            ranked = [
                {
                    "node_id": n.get("node_id"),
                    "name": n.get("name"),
                    "node_type": n.get("node_type"),
                    "enterprise_scale": n.get("enterprise_scale"),
                    "risk_score": round(float(n.get("risk_proxy", n.get("risk_score", 0.0))), 6),
                    "uncertainty": round(float(n.get("uncertainty_proxy", 0.0)), 6),
                    "priority_score": round(float(n.get("priority_score", 0.0)), 6),
                    "priority_base_score": round(float(n.get("priority_base_score", 0.0)), 6),
                    "priority_piecewise_score": round(float(n.get("priority_piecewise_score", 0.0)), 6),
                    "profile_features": n.get("profile_features", {}),
                    "source_mix": n.get("source_mix", {}),
                    "formula_contrib": n.get("formula_contrib", {}),
                    "kqv_overlay": n.get("kqv_overlay", {}),
                }
                for n in ranked_nodes
            ]
        else:
            ranked = _modela_ranking_nodes(graph, product_type=product_type, node_type=node_type)
        return {
            "success": True,
            "data": {
                "total_candidates": len(ranked),
                "top_n": top_n,
                "items": ranked[:top_n],
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"筛选失败: {e}")


@app.get("/api/modela/v2/ranking_eval")
async def modela_v2_ranking_eval(
    product_type: Optional[str] = Query(None),
    node_type: Optional[str] = Query(None),
    top_k: int = Query(10, ge=1, le=500),
    max_nodes: int = Query(2000, ge=200, le=5000),
    max_edges: int = Query(15000, ge=1000, le=50000),
):
    """
    目标2：排序效果评估（弱监督 Proxy，关注 Top-K 命中率）
    """
    try:
        graph = _ensure_modela_v2_graph(force_rebuild=False)
        if MODELA_FORMULA_AVAILABLE:
            view = _modela_extract_view(
                graph=graph,
                view_mode="product" if product_type else "full",
                product_type=product_type,
                seed_node=None,
                k_hop=0,
                max_nodes=max_nodes,
                max_edges=max_edges,
                top_ratio=0.05,
            )
            scored = compute_formula_scores(
                view,
                query_context={
                    "view_mode": "product" if product_type else "full",
                    "product_type": product_type,
                    "seed_node": None,
                    "k_hop": 0,
                    "node_type": node_type,
                },
            )
            ranked_nodes = rank_nodes_by_priority(scored, node_type=node_type, top_n=5000)
            ranked = [
                {
                    "priority_score": float(n.get("priority_score", 0.0)),
                    "profile_features": n.get("profile_features", {}),
                }
                for n in ranked_nodes
            ]
        else:
            ranked = _modela_ranking_nodes(graph, product_type=product_type, node_type=node_type)
        if not ranked:
            return {"success": True, "data": {"total": 0, "top_k": top_k, "precision_at_k": 0.0, "recall_at_k": 0.0}}

        # proxy标签：历史不合格次数 > 0 视为风险企业
        labels = [1 if float(item["profile_features"].get("历史不合格次数", 0)) > 0 else 0 for item in ranked]
        total_pos = sum(labels)
        k = min(top_k, len(ranked))
        topk_pos = sum(labels[:k])
        precision_at_k = topk_pos / max(k, 1)
        recall_at_k = topk_pos / max(total_pos, 1)
        return {
            "success": True,
            "data": {
                "total": len(ranked),
                "top_k": k,
                "positive_total_proxy": total_pos,
                "positive_in_top_k_proxy": topk_pos,
                "precision_at_k": round(precision_at_k, 6),
                "recall_at_k": round(recall_at_k, 6),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"排序评估失败: {e}")


@app.post("/api/modela/v2/resource_plan")
async def modela_v2_resource_plan(request: ModelAResourcePlanRequest):
    """
    目标3：预算约束下的检测资源分配（贪心近似）
    """
    try:
        graph = _ensure_modela_v2_graph(force_rebuild=False)
        if MODELA_FORMULA_AVAILABLE:
            view = _modela_extract_view(
                graph=graph,
                view_mode="product" if request.product_type else "full",
                product_type=request.product_type,
                seed_node=None,
                k_hop=0,
                max_nodes=int(request.max_nodes),
                max_edges=int(request.max_edges),
                top_ratio=0.05,
            )
            scored = compute_formula_scores(
                view,
                query_context={
                    "view_mode": "product" if request.product_type else "full",
                    "product_type": request.product_type,
                    "seed_node": None,
                    "k_hop": 0,
                    "node_type": request.node_type,
                },
            )
            plan = build_budget_plan(
                scored_view=scored,
                budget=float(request.budget),
                max_enterprises=int(request.max_enterprises),
                node_type=request.node_type,
                rho=0.20,
                tau=0.10,
            )
            return {"success": True, "data": plan}

        ranked = _modela_ranking_nodes(graph, product_type=request.product_type, node_type=request.node_type)

        def sample_cost(item: Dict[str, Any]) -> float:
            scale = str(item.get("enterprise_scale", "小型企业"))
            if "大" in scale:
                return request.cost_large
            if "中" in scale:
                return request.cost_medium
            return request.cost_small

        # 分组保证最小覆盖
        by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for item in ranked:
            by_type[item["node_type"]].append(item)

        selected: List[Dict[str, Any]] = []
        used_ids = set()
        budget_left = float(request.budget)

        if request.min_samples_per_type > 0:
            for t, items in by_type.items():
                count = 0
                for item in items:
                    c = sample_cost(item)
                    if item["node_id"] in used_ids:
                        continue
                    if c <= budget_left and len(selected) < request.max_enterprises and count < request.min_samples_per_type:
                        selected.append({**item, "sample_cost": round(c, 4)})
                        used_ids.add(item["node_id"])
                        budget_left -= c
                        count += 1

        # 剩余预算按收益/成本比贪心
        candidates = [item for item in ranked if item["node_id"] not in used_ids]
        candidates.sort(key=lambda x: (x["priority_score"] / max(sample_cost(x), 1e-6)), reverse=True)
        for item in candidates:
            if len(selected) >= request.max_enterprises:
                break
            c = sample_cost(item)
            if c <= budget_left:
                selected.append({**item, "sample_cost": round(c, 4)})
                budget_left -= c

        expected_risk_covered = round(sum(float(x["priority_score"]) for x in selected), 6)
        return {
            "success": True,
            "data": {
                "budget": request.budget,
                "budget_used": round(request.budget - budget_left, 6),
                "budget_left": round(budget_left, 6),
                "selected_count": len(selected),
                "expected_risk_covered": expected_risk_covered,
                "items": selected,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"资源分配失败: {e}")


@app.post("/api/modela/v2/temporal_simulate")
async def modela_v2_temporal_simulate(request: ModelATemporalSimRequest):
    """
    月度训练/测试 + 抽检反馈闭环模拟。
    适用于当前“弱标签/无标签”阶段的流程验证与演示。
    """
    try:
        if request.top_k <= 0:
            raise HTTPException(status_code=400, detail="top_k 必须大于0")
        if request.inspect_count <= 0:
            raise HTTPException(status_code=400, detail="inspect_count 必须大于0")

        graph = _ensure_modela_v2_graph(force_rebuild=False)

        train_graph = _modela_build_month_graph(
            base_graph=graph,
            month=request.train_month,
            product_type=request.product_type,
            seed=int(request.seed),
        )
        test_graph = _modela_build_month_graph(
            base_graph=graph,
            month=request.test_month,
            product_type=request.product_type,
            seed=int(request.seed) + 17,
        )

        view_mode = "product" if request.product_type else "full"

        train_view = _modela_extract_view(
            graph=train_graph,
            view_mode=view_mode,
            product_type=request.product_type,
            seed_node=None,
            k_hop=0,
            max_nodes=int(request.max_nodes),
            max_edges=int(request.max_edges),
            top_ratio=float(request.top_ratio),
        )
        test_view = _modela_extract_view(
            graph=test_graph,
            view_mode=view_mode,
            product_type=request.product_type,
            seed_node=None,
            k_hop=0,
            max_nodes=int(request.max_nodes),
            max_edges=int(request.max_edges),
            top_ratio=float(request.top_ratio),
        )

        if MODELA_FORMULA_AVAILABLE:
            train_scored = compute_formula_scores(
                train_view,
                query_context={
                    "view_mode": view_mode,
                    "product_type": request.product_type,
                    "month": request.train_month,
                    "node_type": request.node_type,
                },
            )
            test_scored = compute_formula_scores(
                test_view,
                query_context={
                    "view_mode": view_mode,
                    "product_type": request.product_type,
                    "month": request.test_month,
                    "node_type": request.node_type,
                },
            )
            train_ranked_nodes = rank_nodes_by_priority(train_scored, node_type=request.node_type, top_n=100000)
            test_ranked_nodes = rank_nodes_by_priority(test_scored, node_type=request.node_type, top_n=100000)
        else:
            train_scored = train_view
            test_scored = test_view
            train_ranked_nodes = sorted(
                [n for n in train_view.get("nodes", []) if (not request.node_type or n.get("node_type") == request.node_type)],
                key=lambda x: float(x.get("view_risk_score", x.get("risk_score", 0.0))),
                reverse=True,
            )
            test_ranked_nodes = sorted(
                [n for n in test_view.get("nodes", []) if (not request.node_type or n.get("node_type") == request.node_type)],
                key=lambda x: float(x.get("view_risk_score", x.get("risk_score", 0.0))),
                reverse=True,
            )

        if not test_ranked_nodes:
            return {
                "success": True,
                "data": {
                    "message": "无可评估节点（请调整 node_type/product_type）",
                    "config": request.dict(),
                    "train_snapshot": {"node_count": 0, "edge_count": 0},
                    "test_snapshot": {"node_count": 0, "edge_count": 0},
                },
            }

        # 构造训练月弱标签，并做分箱校准（可审计）
        train_labels: Dict[str, int] = {}
        train_raw_scores: Dict[str, float] = {}
        train_bins: Dict[int, List[int]] = defaultdict(list)
        for n in train_ranked_nodes:
            nid = str(n.get("node_id") or "")
            score = float(n.get("priority_score", n.get("view_risk_score", 0.0)))
            train_raw_scores[nid] = score
            unc = float(n.get("uncertainty_proxy", _modela_uncertainty(n, request.product_type)))
            p_true = max(
                0.01,
                min(
                    0.98,
                    0.03
                    + 0.60 * score
                    + 0.12 * unc
                    + (_modela_stable_random_01(f"truth-bias|{nid}|{request.train_month}|{request.seed}") - 0.5) * 0.20,
                ),
            )
            y = 1 if _modela_stable_random_01(f"truth-draw|{nid}|{request.train_month}|{request.seed}") < p_true else 0
            train_labels[nid] = y
            b = min(9, max(0, int(score * 10)))
            train_bins[b].append(y)

        bin_rate: Dict[int, float] = {}
        for b in range(10):
            arr = train_bins.get(b, [])
            if not arr:
                bin_rate[b] = (sum(train_labels.values()) + 1.0) / (len(train_labels) + 2.0)
            else:
                # beta 平滑，避免极端概率
                bin_rate[b] = (sum(arr) + 1.0) / (len(arr) + 2.0)

        test_labels: Dict[str, int] = {}
        raw_scores: Dict[str, float] = {}
        unc_scores: Dict[str, float] = {}
        calibrated_scores: Dict[str, float] = {}
        for n in test_ranked_nodes:
            nid = str(n.get("node_id") or "")
            score = float(n.get("priority_score", n.get("view_risk_score", 0.0)))
            unc = float(n.get("uncertainty_proxy", _modela_uncertainty(n, request.product_type)))
            raw_scores[nid] = score
            unc_scores[nid] = unc
            b = min(9, max(0, int(score * 10)))
            calibrated_scores[nid] = round(float(bin_rate[b]), 6)

            p_true = max(
                0.01,
                min(
                    0.98,
                    0.03
                    + 0.62 * score
                    + 0.14 * unc
                    + (_modela_stable_random_01(f"truth-bias|{nid}|{request.test_month}|{request.seed}") - 0.5) * 0.20,
                ),
            )
            y = 1 if _modela_stable_random_01(f"truth-draw|{nid}|{request.test_month}|{request.seed}") < p_true else 0
            test_labels[nid] = y

        ranked_before = sorted(raw_scores.keys(), key=lambda x: raw_scores[x], reverse=True)
        metrics_before = _modela_precision_recall_at_k(ranked_before, test_labels, request.top_k)

        # 抽检选择：exploitation + exploration
        inspect_rank = sorted(
            raw_scores.keys(),
            key=lambda nid: raw_scores[nid] * (1.0 + float(request.explore_weight) * unc_scores.get(nid, 0.0)),
            reverse=True,
        )
        inspect_ids = inspect_rank[: min(int(request.inspect_count), len(inspect_rank))]
        inspect_id_set = set(inspect_ids)

        post_scores: Dict[str, float] = {}
        inspection_items: List[Dict[str, Any]] = []
        for idx, nid in enumerate(inspect_ids):
            y = int(test_labels.get(nid, 0))
            post_scores[nid] = float(y)
            inspection_items.append(
                {
                    "rank": idx + 1,
                    "node_id": nid,
                    "predicted_score": round(raw_scores.get(nid, 0.0), 6),
                    "uncertainty": round(unc_scores.get(nid, 0.0), 6),
                    "inspection_label": y,
                    "feedback_score": float(y),
                }
            )
        for nid, score in calibrated_scores.items():
            if nid in inspect_id_set:
                continue
            post_scores[nid] = score

        ranked_after = sorted(post_scores.keys(), key=lambda x: post_scores[x], reverse=True)
        metrics_after = _modela_precision_recall_at_k(ranked_after, test_labels, request.top_k)

        pos_found = sum(int(test_labels.get(nid, 0)) for nid in inspect_ids)
        inspect_hit_rate = pos_found / max(len(inspect_ids), 1)

        bucket_before = _modela_risk_buckets([raw_scores[x] for x in ranked_before])
        bucket_after = _modela_risk_buckets([post_scores[x] for x in ranked_after])

        return {
            "success": True,
            "data": {
                "config": request.model_dump(),
                "train_snapshot": {
                    "month": request.train_month,
                    "node_count": int(train_scored.get("meta", {}).get("node_count", len(train_scored.get("nodes", [])))),
                    "edge_count": int(train_scored.get("meta", {}).get("edge_count", len(train_scored.get("edges", [])))),
                    "positive_rate_proxy": round(sum(train_labels.values()) / max(len(train_labels), 1), 6),
                    "score_mean": round(sum(train_raw_scores.values()) / max(len(train_raw_scores), 1), 6),
                },
                "test_snapshot": {
                    "month": request.test_month,
                    "node_count": int(test_scored.get("meta", {}).get("node_count", len(test_scored.get("nodes", [])))),
                    "edge_count": int(test_scored.get("meta", {}).get("edge_count", len(test_scored.get("edges", [])))),
                    "positive_rate_proxy": round(sum(test_labels.values()) / max(len(test_labels), 1), 6),
                },
                "metrics_before": metrics_before,
                "metrics_after_feedback": metrics_after,
                "inspection": {
                    "selected_count": len(inspect_ids),
                    "positive_found": int(pos_found),
                    "hit_rate": round(inspect_hit_rate, 6),
                    "items": inspection_items[: min(200, len(inspection_items))],
                },
                "risk_buckets_before": bucket_before,
                "risk_buckets_after_feedback": bucket_after,
                "recommendations": [
                    "优先对高 priority_score 且 uncertainty_proxy 高的企业执行抽检。",
                    "将抽检阳性样本回写为强标签，下一轮更新分箱校准参数。",
                    "按月重复该闭环，观察 Precision@K 与 Recall@K 变化趋势。",
                ],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"月度训练测试模拟失败: {e}")


@app.post("/api/modela/v2/rebuild")
async def modela_v2_rebuild():
    """强制重建 ModelA v2 数据产物。"""
    try:
        graph = _ensure_modela_v2_graph(force_rebuild=True)
        return {
            "success": True,
            "message": "ModelA v2 重建完成",
            "data": graph.get("meta", {}),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重建失败: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
