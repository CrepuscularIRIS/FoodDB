#!/usr/bin/env python3
"""
FastAPI 后端服务
为前端提供 RESTful API 接口
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import asdict

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 加载环境变量
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✓ 已加载环境变量: {env_path}")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.workflow import RiskAssessmentAgent
from agent.symptom_router import get_symptom_router, SymptomRiskResult
from agent.risk_predictor import RiskPredictor, get_risk_predictor

# 检查 LLM 提取器是否可用
try:
    from agent.symptom_extractor import LLMSymptomExtractor, get_symptom_extractor
    LLM_EXTRACTOR_AVAILABLE = True
except ImportError:
    LLM_EXTRACTOR_AVAILABLE = False
from agent.orchestrator import Orchestrator

# 创建FastAPI应用
app = FastAPI(
    title="乳制品供应链风险研判智能体 API",
    description="基于知识驱动与规则增强的乳制品供应链风险研判系统（Mode A/B 联动版）",
    version="1.2.0"
)

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
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局Agent实例
agent: Optional[RiskAssessmentAgent] = None
symptom_router = None
orchestrator: Optional[Orchestrator] = None


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


# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.1.0"}


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


# 加载案例库
CASE_LIBRARY_PATH = Path(__file__).parent.parent / "data" / "mock" / "case_library.json"
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

        # 转换为字典格式
        response_data = {
            "query": result.query,
            "symptoms_detected": result.symptoms_detected,
            "risk_factors": result.risk_factors,
            "stage_candidates": result.stage_candidates,
            "linked_enterprises": result.linked_enterprises,
            "evidence": result.evidence,
            "risk_level": result.risk_level,
            "confidence": result.confidence,
            "suggested_actions": result.suggested_actions,
            # LLM 增强字段
            "llm_extraction": result.llm_extraction,
            "processing_steps": result.processing_steps
        }

        return {
            "success": True,
            "data": response_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"症状评估失败: {str(e)}")


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
                    'linked_enterprises': result.linked_enterprises[:5],  # 只返回前5个
                    'risk_level': result.risk_level,
                    'confidence': result.confidence,
                    'suggested_actions': result.suggested_actions,
                    'llm_extraction': result.llm_extraction,
                    'processing_steps': result.processing_steps
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


# ==================== V2 图特征 API ====================

import os
from pathlib import Path

# V2 数据路径
V2_DATA_DIR = Path(__file__).parent.parent / "data" / "v2"

# 缓存图特征数据
_graph_features_cache = None
_graph_stats_cache = None


def _load_graph_features():
    """加载图特征数据"""
    global _graph_features_cache
    if _graph_features_cache is None:
        features_path = V2_DATA_DIR / "node_features_64d.json"
        if features_path.exists():
            with open(features_path, 'r', encoding='utf-8') as f:
                _graph_features_cache = json.load(f)
        else:
            _graph_features_cache = {"features": {}}
    return _graph_features_cache


def _load_graph_stats():
    """加载图统计数据"""
    global _graph_stats_cache
    if _graph_stats_cache is None:
        stats_path = V2_DATA_DIR / "graph_statistics.json"
        if stats_path.exists():
            with open(stats_path, 'r', encoding='utf-8') as f:
                _graph_stats_cache = json.load(f)
        else:
            _graph_stats_cache = {
                "node_count": 0,
                "edge_count": 0,
                "density": 0,
                "avg_clustering": 0,
                "avg_path_length": 0
            }
    return _graph_stats_cache


@app.get("/api/graph/features")
async def get_graph_features(node_id: Optional[str] = None):
    """
    获取图节点特征
    
    - 无参数: 返回所有节点特征
    - node_id: 返回指定节点的特征
    """
    features_data = _load_graph_features()
    
    if node_id:
        # 返回指定节点
        features = features_data.get("features", {})
        if node_id in features:
            return {
                "success": True,
                "data": {
                    "node_id": node_id,
                    "feature_dim": features_data.get("feature_dim", 64),
                    **features[node_id]
                }
            }
        else:
            raise HTTPException(status_code=404, detail=f"节点 {node_id} 不存在")
    
    # 返回所有节点
    return {
        "success": True,
        "data": {
            "feature_dim": features_data.get("feature_dim", 64),
            "node_count": features_data.get("node_count", 0),
            "features": features_data.get("features", {})
        }
    }


@app.get("/api/graph/stats")
async def get_graph_stats():
    """获取图统计信息"""
    stats = _load_graph_stats()
    
    return {
        "success": True,
        "data": stats
    }


@app.post("/api/graph/features/generate")
async def regenerate_features():
    """重新生成图特征"""
    import subprocess
    import sys
    
    try:
        # 运行特征生成脚本
        script_path = Path(__file__).parent.parent / "scripts" / "generate_features.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            # 清除缓存
            global _graph_features_cache
            _graph_features_cache = None
            
            features_data = _load_graph_features()
            return {
                "success": True,
                "message": "特征生成完成",
                "data": {
                    "feature_dim": features_data.get("feature_dim", 64),
                    "node_count": features_data.get("node_count", 0)
                }
            }
        else:
            raise HTTPException(status_code=500, detail=f"特征生成失败: {result.stderr}")
    
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="特征生成超时")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"特征生成错误: {str(e)}")


@app.post("/api/graph/compute")
async def compute_graph_features():
    """重新计算图特征"""
    import subprocess
    import sys
    
    try:
        # 运行图特征计算脚本
        script_path = Path(__file__).parent.parent / "scripts" / "compute_graph_features.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=180
        )
        
        if result.returncode == 0:
            # 清除缓存
            global _graph_stats_cache
            _graph_stats_cache = None
            
            stats = _load_graph_stats()
            return {
                "success": True,
                "message": "图特征计算完成",
                "data": stats
            }
        else:
            raise HTTPException(status_code=500, detail=f"图特征计算失败: {result.stderr}")
    
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="图特征计算超时")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图特征计算错误: {str(e)}")


# ==================== 风险预测 API ====================

@app.post("/api/risk/predict")
async def predict_risk(node_id: str):
    """
    预测单个节点的风险
    
    - node_id: 节点ID
    """
    try:
        predictor = get_risk_predictor()
        result = predictor.predict(node_id)
        
        if result is None:
            raise HTTPException(status_code=404, detail=f"节点 {node_id} 不存在")
        
        return {
            "success": True,
            "data": {
                "node_id": result.node_id,
                "enterprise_name": result.enterprise_name,
                "node_type": result.node_type,
                "scale": result.scale,
                "region": result.region,
                "risk_probability": result.risk_probability,
                "risk_level": result.risk_level,
                "confidence": result.confidence,
                "risk_factors": result.risk_factors
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"风险预测失败: {str(e)}")


@app.get("/api/risk/stats")
async def get_risk_stats():
    """
    获取风险统计信息
    """
    try:
        predictor = get_risk_predictor()
        stats = predictor.get_statistics()
        
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
