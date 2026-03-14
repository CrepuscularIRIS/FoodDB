"""
Mode A/B 联动编排层 - 统一协调症状驱动与供应链研判

核心概念:
- RiskHypothesis: 统一中间对象，连接 Mode B 输出与 Mode A 输入
- Orchestrator: 编排器，管理双模式联动流程

联动流程:
Mode B(症状) -> RiskHypothesis -> Mode A(定向核查) -> 联合报告

运行方式:
    python -m agent.orchestrator
"""

import os
import sys
import time
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Generator

# 处理相对导入，支持模块方式和直接运行
try:
    from .retriever import DataRetriever
    from .symptom_router import SymptomRiskRouter, SymptomRiskResult
    from .workflow import RiskAssessmentAgent
    from .reporter import ReportGenerator
    from .enterprise_matcher import EnterpriseMatcher, get_matcher
except ImportError:
    # 直接运行时添加项目路径
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agent.retriever import DataRetriever
    from agent.symptom_router import SymptomRiskRouter, SymptomRiskResult
    from agent.workflow import RiskAssessmentAgent
    from agent.reporter import ReportGenerator
    from agent.enterprise_matcher import EnterpriseMatcher, get_matcher


@dataclass
class RiskHypothesis:
    """
    风险假设 - Mode A/B 联动的统一数据契约

    承载 Mode B 的输出，作为 Mode A 的输入触发条件
    """
    # 风险因子列表（从症状推断）
    risk_factors: List[str] = field(default_factory=list)

    # 怀疑的问题环节: 原料/生产/物流/销售
    suspected_stage: str = ""

    # 置信度 (0-1)
    confidence: float = 0.0

    # 目标候选（企业/批次）- Mode B 初步关联的企业
    target_candidates: List[Dict[str, Any]] = field(default_factory=list)

    # 建议检验项（基于 GB 标准）
    suggested_checks: List[str] = field(default_factory=list)

    # 症状证据（原始输入）
    symptom_evidence: Dict[str, Any] = field(default_factory=dict)

    # 关联的 GB 条款
    related_gb_rules: List[Dict[str, Any]] = field(default_factory=list)

    # 生成时间戳
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 关联的症状描述
    symptom_description: str = ""

    # 影响人群特征
    affected_population: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_symptom_result(cls, result, symptom_input: str) -> "RiskHypothesis":
        """
        从 Mode B 症状分析结果创建 RiskHypothesis

        Args:
            result: SymptomRiskRouter.assess() 的输出 (SymptomRiskResult 对象)
            symptom_input: 原始症状描述

        Returns:
            RiskHypothesis 实例
        """
        # 处理 SymptomRiskResult 对象
        # 提取风险因子
        risk_factors = result.risk_factors if hasattr(result, 'risk_factors') else []
        risk_factor_names = [rf.get("name", rf.get("risk_factor_id", "")) for rf in risk_factors]

        # 推断怀疑环节（取最高置信度的环节）
        stage_candidates = result.stage_candidates if hasattr(result, 'stage_candidates') else []
        suspected_stage = ""
        if stage_candidates:
            # 找到最高分环节
            top_stage = max(stage_candidates, key=lambda x: x.get("score", 0))
            suspected_stage = top_stage.get("stage", top_stage.get("stage_id", ""))

        # 映射环节英文名到中文
        stage_mapping = {
            "raw_material": "原料",
            "production": "生产",
            "logistics": "物流",
            "storage": "仓储",
            "sales": "销售",
            "raw_materials": "原料",
            "processing": "生产",
            "transport": "物流",
            "retail": "销售"
        }
        suspected_stage_cn = stage_mapping.get(suspected_stage, suspected_stage)

        # 计算整体置信度
        confidence = result.confidence if hasattr(result, 'confidence') else 0.5

        # 提取目标候选企业
        target_candidates = result.linked_enterprises if hasattr(result, 'linked_enterprises') else []

        # 提取建议检验项 (从风险因子推断)
        suggested_checks = []
        if risk_factors:
            for rf in risk_factors:
                test_items = rf.get("test_items", [])
                suggested_checks.extend(test_items)
            suggested_checks = list(set(suggested_checks))  # 去重

        # 提取 GB 规则
        related_gb_rules = result.gb_references if hasattr(result, 'gb_references') else []

        # 提取人群特征 (从证据中)
        affected_population = {}
        evidence = result.evidence if hasattr(result, 'evidence') else {}
        if evidence and isinstance(evidence, dict):
            affected_population = evidence.get("population_at_risk", {})

        return cls(
            risk_factors=risk_factor_names,
            suspected_stage=suspected_stage_cn,
            confidence=confidence,
            target_candidates=target_candidates,
            suggested_checks=suggested_checks,
            symptom_evidence=result,
            related_gb_rules=related_gb_rules,
            symptom_description=symptom_input,
            affected_population=affected_population
        )


@dataclass
class CombinedReport:
    """
    联合报告 - Mode A + Mode B 的综合输出

    包含症状证据、企业证据、GB 依据、行动建议
    """
    # 报告元数据
    report_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Mode B 输出
    risk_hypothesis: Optional[RiskHypothesis] = None

    # Mode A 输出（多个企业的研判结果）
    enterprise_assessments: List[Dict[str, Any]] = field(default_factory=list)

    # 综合风险结论
    overall_risk_level: str = ""  # high/medium/low
    overall_risk_score: float = 0.0

    # 证据链
    evidence_chain: Dict[str, Any] = field(default_factory=dict)

    # GB 标准依据
    gb_basis: List[Dict[str, Any]] = field(default_factory=list)

    # 行动建议（监管决策支持）
    action_suggestions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "report_id": self.report_id,
            "created_at": self.created_at,
            "risk_hypothesis": self.risk_hypothesis.to_dict() if self.risk_hypothesis else {},
            "enterprise_assessments": self.enterprise_assessments,
            "overall_risk_level": self.overall_risk_level,
            "overall_risk_score": self.overall_risk_score,
            "evidence_chain": self.evidence_chain,
            "gb_basis": self.gb_basis,
            "action_suggestions": self.action_suggestions
        }
        return result

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class Orchestrator:
    """
    Mode A/B 联动编排器

    职责:
    1. 接收 Mode B 症状分析请求
    2. 生成 RiskHypothesis
    3. 触发 Mode A 定向核查
    4. 整合输出联合报告
    """

    def __init__(self, data_dir: Optional[Path] = None, use_real_data: bool = True):
        """
        初始化编排器

        Args:
            data_dir: 数据目录路径
            use_real_data: 是否使用真实数据
        """
        # 确定数据目录
        if data_dir is None:
            data_dir = self._resolve_data_dir(use_real_data)

        self.data_dir = data_dir
        print(f"✓ Orchestrator 初始化")
        print(f"  - 数据目录: {data_dir}")

        # 初始化各模块
        self.retriever = DataRetriever(data_dir)
        self.symptom_router = SymptomRiskRouter()
        self.enterprise_matcher = get_matcher(self.retriever)

        # Mode A Agent（延迟初始化，按需使用）
        self._mode_a_agent: Optional[RiskAssessmentAgent] = None

    def _resolve_data_dir(self, use_real_data: bool) -> Path:
        """解析数据目录优先级：环境变量 > 默认路径"""
        # 1. 检查环境变量
        env_data_dir = os.environ.get("DATA_DIR")
        if env_data_dir:
            path = Path(env_data_dir)
            if path.exists():
                print(f"✓ 使用环境变量 DATA_DIR: {path}")
                return path
            else:
                print(f"⚠ 环境变量 DATA_DIR 指向的路径不存在: {path}")

        # 2. 使用默认优先级: merged > release_v1_1 > real > mock
        base_dir = Path(__file__).parent.parent / "data"

        candidates = [
            ("merged", base_dir / "merged"),
            ("release_v1_1", base_dir / "release_v1_1"),
            ("real", base_dir / "real"),
            ("mock", base_dir / "mock"),
        ]

        for name, path in candidates:
            if path.exists() and (path / "enterprise_master.csv").exists():
                print(f"✓ 使用默认数据源: {name} ({path})")
                return path

        # 3. 兜底：创建 mock 目录
        mock_dir = base_dir / "mock"
        mock_dir.mkdir(parents=True, exist_ok=True)
        print(f"⚠ 使用兜底数据源: mock ({mock_dir})")
        return mock_dir

    @property
    def mode_a_agent(self) -> RiskAssessmentAgent:
        """懒加载 Mode A Agent"""
        if self._mode_a_agent is None:
            self._mode_a_agent = RiskAssessmentAgent(self.data_dir, use_real_data=True)
        return self._mode_a_agent

    def analyze_symptom(self, symptom_description: str,
                       population: Optional[Dict[str, Any]] = None) -> RiskHypothesis:
        """
        Mode B: 症状驱动风险分析

        Args:
            symptom_description: 症状描述（如"腹泻、发热、腹痛"）
            population: 人群特征（年龄、数量等）

        Returns:
            RiskHypothesis 风险假设对象
        """
        print(f"\n{'='*60}")
        print(f"Mode B: 症状风险分析")
        print(f"症状: {symptom_description}")
        print(f"{'='*60}")

        # 调用症状路由器 (使用 assess 方法，返回 SymptomRiskResult 对象)
        result = self.symptom_router.assess(symptom_description, product_type=None)

        # 转换为 RiskHypothesis
        hypothesis = RiskHypothesis.from_symptom_result(result, symptom_description)

        print(f"\n✓ 风险假设生成完成")
        print(f"  - 风险因子: {hypothesis.risk_factors}")
        print(f"  - 怀疑环节: {hypothesis.suspected_stage}")
        print(f"  - 置信度: {hypothesis.confidence:.2f}")
        print(f"  - 候选企业: {len(hypothesis.target_candidates)} 家")

        return hypothesis

    def targeted_verification(self, hypothesis: RiskHypothesis) -> List[Dict[str, Any]]:
        """
        Mode A: 基于 RiskHypothesis 的定向核查
        使用 EnterpriseMatcher 进行智能企业匹配

        Args:
            hypothesis: 风险假设对象

        Returns:
            企业研判结果列表
        """
        print(f"\n{'='*60}")
        print(f"Mode A: 定向核查 (使用企业匹配层 v1.0)")
        print(f"怀疑环节: {hypothesis.suspected_stage}")
        print(f"风险因子: {hypothesis.risk_factors}")
        print(f"{'='*60}")

        assessments = []

        # 1. 使用企业匹配器获取候选企业
        print("  - 使用企业匹配器搜索相关企业...")
        matched_candidates = self.enterprise_matcher.match(
            risk_factors=hypothesis.risk_factors,
            suspected_stage=hypothesis.suspected_stage,
            top_k=5,
            time_window_days=30
        )

        if not matched_candidates:
            print("  ⚠ 未匹配到相关企业")
            return assessments

        print(f"  ✓ 匹配到 {len(matched_candidates)} 家企业:")
        for c in matched_candidates:
            print(f"    - {c.enterprise_name} (分数: {c.score:.0f}/100)")
            print(f"      信号: {' | '.join(c.matched_signals[:3])}")

        # 2. 对每个候选企业执行 Mode A 研判
        for candidate in matched_candidates:
            ent_id = candidate.enterprise_id
            ent_name = candidate.enterprise_name

            print(f"\n  核查企业: {ent_name} ({candidate.node_type})")
            print(f"    匹配分数: {candidate.score:.0f}/100")
            print(f"    匹配信号: {', '.join(candidate.matched_signals)}")

            try:
                # 执行 Mode A 研判（使用非流式版本获取完整报告）
                report = self.mode_a_agent.assess(
                    query=ent_id,
                    query_type="enterprise"
                )

                # 将完整报告转换为字典
                final_report_data = {
                    "report_id": report.report_id,
                    "generated_at": report.generated_at,
                    "target_type": report.target_type,
                    "target_id": report.target_id,
                    "target_name": report.target_name,
                    "risk_level": report.risk_level,
                    "risk_score": report.risk_score,
                    "conclusion": report.conclusion,
                    "evidence_summary": report.evidence_summary,
                    "related_inspections": report.related_inspections,
                    "related_events": report.related_events,
                    "supply_chain_path": report.supply_chain_path,
                    "gb_references": report.gb_references,
                    "triggered_rules": report.triggered_rules,
                    "sampling_suggestions": report.sampling_suggestions,
                    "traceability_suggestions": report.traceability_suggestions,
                    "risk_mitigation_suggestions": report.risk_mitigation_suggestions,
                    "propagation_analysis": report.propagation_analysis,
                    "data_sources": report.data_sources,
                    "evidence_types": report.evidence_types,
                    "llm_analysis": report.llm_analysis,
                    "llm_usage": report.llm_usage,
                    "llm_latency_ms": report.llm_latency_ms,
                    "case_analogies": report.case_analogies,
                    "graph_metrics": report.graph_metrics,
                }

                # 添加到评估列表
                if final_report_data.get("report_id"):
                    assessments.append({
                        "enterprise_id": ent_id,
                        "enterprise_name": ent_name,
                        "match_score": candidate.score,
                        "matched_signals": candidate.matched_signals,
                        "match_evidence": candidate.evidence,
                        "risk_assessment": final_report_data,
                        "source": "enterprise_matcher"
                    })
                    print(f"    ✓ Mode A 风险分: {final_report_data.get('risk_score', 0):.1f}")
                else:
                    print(f"    ⚠ 未获取到有效报告")

            except Exception as e:
                print(f"    ✗ 核查失败: {e}")
                import traceback
                traceback.print_exc()
                assessments.append({
                    "enterprise_id": ent_id,
                    "enterprise_name": ent_name,
                    "match_score": candidate.score,
                    "matched_signals": candidate.matched_signals,
                    "error": str(e),
                    "source": "enterprise_matcher"
                })

        print(f"\n✓ 定向核查完成: {len(assessments)} 家企业")
        return assessments

    def _search_by_stage(self, stage: str) -> List[Dict[str, Any]]:
        """基于环节类型搜索相关企业"""
        stage_to_node_type = {
            "原料": "牧场",
            "生产": "乳企",
            "物流": "物流",
            "仓储": "仓储",
            "销售": "零售"
        }

        node_type = stage_to_node_type.get(stage, "")
        if not node_type:
            return []

        # 搜索该类型的企业
        candidates = []
        for ent in self.retriever.enterprises:
            if ent.get("node_type") == node_type:
                candidates.append({
                    "enterprise_id": ent.get("enterprise_id"),
                    "enterprise_name": ent.get("enterprise_name"),
                    "node_type": node_type
                })

        # 限制数量
        return candidates[:5]

    def generate_combined_report(self,
                                  hypothesis: RiskHypothesis,
                                  assessments: List[Dict[str, Any]]) -> CombinedReport:
        """
        生成联合报告

        Args:
            hypothesis: 风险假设
            assessments: Mode A 研判结果

        Returns:
            CombinedReport 联合报告
        """
        print(f"\n{'='*60}")
        print(f"生成联合报告")
        print(f"{'='*60}")

        # 生成报告 ID
        report_id = f"RPT-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{id(hypothesis) % 10000:04d}"

        # 计算综合风险等级
        overall_score = 0.0
        risk_levels = []

        for assessment in assessments:
            if "risk_assessment" in assessment:
                score = assessment["risk_assessment"].get("risk_score", 0)
                overall_score = max(overall_score, score)
                risk_levels.append(assessment["risk_assessment"].get("risk_level", "low"))

        # 考虑 Mode B 置信度
        if hypothesis.confidence > 0.7 and overall_score < 50:
            overall_score = min(overall_score + 20, 100)

        # 确定风险等级
        if overall_score >= 70:
            overall_level = "high"
        elif overall_score >= 40:
            overall_level = "medium"
        else:
            overall_level = "low"

        # 如果 Mode B 是高置信度且 Mode A 有中高风险，提升等级
        if hypothesis.confidence > 0.8 and overall_level == "medium":
            overall_level = "high"

        # 构建证据链
        evidence_chain = {
            "symptom_input": hypothesis.symptom_description,
            "risk_factors": hypothesis.risk_factors,
            "suspected_stage": hypothesis.suspected_stage,
            "affected_population": hypothesis.affected_population,
            "linked_enterprises": [
                {
                    "enterprise_id": a.get("enterprise_id"),
                    "enterprise_name": a.get("enterprise_name"),
                    "risk_score": a.get("risk_assessment", {}).get("risk_score", 0),
                    "risk_level": a.get("risk_assessment", {}).get("risk_level", "unknown")
                }
                for a in assessments if "risk_assessment" in a
            ]
        }

        # 生成行动建议
        action_suggestions = self._generate_action_suggestions(hypothesis, assessments, overall_level)

        report = CombinedReport(
            report_id=report_id,
            risk_hypothesis=hypothesis,
            enterprise_assessments=assessments,
            overall_risk_level=overall_level,
            overall_risk_score=overall_score,
            evidence_chain=evidence_chain,
            gb_basis=hypothesis.related_gb_rules,
            action_suggestions=action_suggestions
        )

        print(f"✓ 联合报告生成完成")
        print(f"  - 报告 ID: {report_id}")
        print(f"  - 综合风险: {overall_level} ({overall_score:.1f})")
        print(f"  - 行动建议: {len(action_suggestions)} 条")

        return report

    def _generate_action_suggestions(self,
                                      hypothesis: RiskHypothesis,
                                      assessments: List[Dict[str, Any]],
                                      overall_level: str) -> List[Dict[str, Any]]:
        """生成行动建议"""
        suggestions = []

        # 1. 紧急抽检建议
        if overall_level in ["high", "medium"]:
            high_risk_ents = [
                a for a in assessments
                if a.get("risk_assessment", {}).get("risk_level") == "high"
            ]

            if high_risk_ents:
                suggestions.append({
                    "priority": "high",
                    "action_type": "紧急抽检",
                    "target": [a.get("enterprise_name") for a in high_risk_ents],
                    "test_items": hypothesis.suggested_checks,
                    "reason": f"症状分析识别出风险因子: {', '.join(hypothesis.risk_factors[:3])}"
                })

        # 2. 溯源建议
        if hypothesis.suspected_stage:
            suggestions.append({
                "priority": "medium",
                "action_type": "环节溯源",
                "target": hypothesis.suspected_stage,
                "reason": f"症状模式指向 {hypothesis.suspected_stage} 环节异常"
            })

        # 3. 预警建议
        if hypothesis.confidence > 0.7:
            suggestions.append({
                "priority": "high",
                "action_type": "风险预警",
                "target": "同批次/同时段产品",
                "reason": f"高置信度 ({hypothesis.confidence:.0%}) 风险假设"
            })

        # 4. 扩大监测建议
        if overall_level == "high":
            suggestions.append({
                "priority": "medium",
                "action_type": "扩大监测",
                "target": "同区域同类企业",
                "reason": "综合风险评估为高风险"
            })

        return suggestions

    def run_linked_workflow(self,
                            symptom_description: str,
                            population: Optional[Dict[str, Any]] = None) -> CombinedReport:
        """
        执行完整的 Mode A/B 联动流程

        Args:
            symptom_description: 症状描述
            population: 人群特征

        Returns:
            CombinedReport 联合报告
        """
        print(f"\n{'#'*60}")
        print(f"# 启动 Mode A/B 联动工作流")
        print(f"{'#'*60}")

        # Step 1: Mode B - 症状分析
        hypothesis = self.analyze_symptom(symptom_description, population)

        # Step 2: Mode A - 定向核查
        assessments = self.targeted_verification(hypothesis)

        # Step 3: 生成联合报告
        report = self.generate_combined_report(hypothesis, assessments)

        print(f"\n{'#'*60}")
        print(f"# 联动工作流完成")
        print(f"{'#'*60}")

        return report

    def run_linked_workflow_streaming(self,
                                      symptom_description: str,
                                      population: Optional[Dict[str, Any]] = None) -> Generator[Dict[str, Any], None, CombinedReport]:
        """
        流式执行 Mode A/B 联动流程

        Yields:
            步骤状态更新

        Returns:
            CombinedReport 联合报告
        """
        print(f"\n{'#'*60}")
        print(f"# 启动 Mode A/B 联动工作流 (流式)")
        print(f"{'#'*60}")

        # Step 0: 启动工作流
        yield {
            "step": "workflow_start",
            "status": "started",
            "message": "启动 Mode A/B 联动工作流",
            "input": {"symptom": symptom_description}
        }

        yield {
            "step": "workflow_start",
            "status": "complete",
            "message": "工作流初始化完成",
        }

        # Step 1: Mode B - 症状分析
        yield {
            "step": "mode_b_analysis",
            "status": "started",
            "message": "Mode B: 症状驱动风险分析"
        }

        hypothesis = self.analyze_symptom(symptom_description, population)

        yield {
            "step": "mode_b_analysis",
            "status": "complete",
            "message": f"Mode B 完成: 识别 {len(hypothesis.risk_factors)} 个风险因子",
            "output": {
                "risk_factors": hypothesis.risk_factors,
                "suspected_stage": hypothesis.suspected_stage,
                "confidence": hypothesis.confidence
            }
        }

        # Step 2: 生成风险假设
        yield {
            "step": "hypothesis_generation",
            "status": "started",
            "message": "生成风险假设"
        }

        # 企业匹配在 targeted_verification 中完成
        matched_candidates = self.enterprise_matcher.match(
            risk_factors=hypothesis.risk_factors,
            suspected_stage=hypothesis.suspected_stage,
            top_k=5,
            time_window_days=30
        )

        yield {
            "step": "hypothesis_generation",
            "status": "complete",
            "message": f"匹配到 {len(matched_candidates)} 家候选企业",
            "output": {
                "risk_factors": hypothesis.risk_factors,
                "suspected_stage": hypothesis.suspected_stage,
                "confidence": hypothesis.confidence,
                "target_candidates": hypothesis.target_candidates,
                "matched_enterprises": [
                    {
                        "enterprise_id": c.enterprise_id,
                        "enterprise_name": c.enterprise_name,
                        "node_type": c.node_type,
                        "score": c.score,
                        "matched_signals": c.matched_signals
                    } for c in matched_candidates
                ]
            }
        }

        # Step 3: Mode A - 定向核查
        yield {
            "step": "mode_a_verification",
            "status": "started",
            "message": f"Mode A: 定向核查 {len(hypothesis.target_candidates)} 家候选企业"
        }

        assessments = self.targeted_verification(hypothesis)

        yield {
            "step": "mode_a_verification",
            "status": "complete",
            "message": f"Mode A 完成: 核查 {len(assessments)} 家企业",
            "output": {
                "assessment_count": len(assessments),
                "high_risk_count": sum(1 for a in assessments
                                        if a.get("risk_assessment", {}).get("risk_level") == "high")
            }
        }

        # Step 3: 生成联合报告
        yield {
            "step": "report_generation",
            "status": "started",
            "message": "生成联合报告"
        }

        report = self.generate_combined_report(hypothesis, assessments)

        yield {
            "step": "report_generation",
            "status": "complete",
            "message": "联合报告生成完成",
            "output": {
                "report_id": report.report_id,
                "overall_risk_level": report.overall_risk_level,
                "overall_risk_score": report.overall_risk_score
            }
        }

        yield {
            "step": "workflow_complete",
            "status": "complete",
            "message": "Mode A/B 联动工作流完成",
            "output": report.to_dict()
        }

        return report


def demo_linked_workflow():
    """演示 Mode A/B 联动工作流"""
    print("\n" + "="*80)
    print("Mode A/B 联动工作流演示 - 3个端到端案例")
    print("="*80)

    # 初始化编排器
    orchestrator = Orchestrator()

    # 保存报告目录
    output_dir = Path(__file__).parent.parent / "reports" / "enhanced"
    output_dir.mkdir(parents=True, exist_ok=True)

    reports = []

    # 演示案例 1: 婴幼儿腹泻 + 发热 (高风险场景)
    print("\n" + "="*60)
    print("【案例 1】婴幼儿群体腹泻 + 发热 - 高风险场景")
    print("="*60)
    print("场景: 某幼儿园5名婴幼儿同时出现症状")
    print("症状: 腹泻、发热、腹痛")
    print("人群: 婴幼儿 (高风险人群)")
    report1 = orchestrator.run_linked_workflow(
        symptom_description="腹泻、发热、腹痛",
        population={"age_group": "infant", "case_count": 5, "scenario": "kindergarten"}
    )
    reports.append(report1)
    print_summary(report1)
    save_report(report1, output_dir, "CASE-001")

    # 演示案例 2: 成人呕吐 + 腹痛 (中风险场景 - 物流环节)
    print("\n" + "="*60)
    print("【案例 2】成人群体呕吐 + 腹痛 - 物流/仓储环节场景")
    print("="*60)
    print("场景: 办公楼工作人员午餐后出现症状")
    print("症状: 呕吐、腹痛、头晕、恶心")
    print("人群: 成年人 (办公人群)")
    report2 = orchestrator.run_linked_workflow(
        symptom_description="呕吐、腹痛、头晕、恶心",
        population={"age_group": "adult", "case_count": 12, "scenario": "office_lunch"}
    )
    reports.append(report2)
    print_summary(report2)
    save_report(report2, output_dir, "CASE-002")

    # 演示案例 3: 复杂症状群 + 过敏原 (复杂场景 - 生产环节)
    print("\n" + "="*60)
    print("【案例 3】多症状群 + 过敏反应 - 生产/加工环节场景")
    print("="*60)
    print("场景: 某批次产品多地区消费者反馈")
    print("症状: 皮疹、瘙痒、腹泻、头痛、乏力")
    print("人群: 混合人群 (各年龄段)")
    report3 = orchestrator.run_linked_workflow(
        symptom_description="皮疹、瘙痒、腹泻、头痛、乏力",
        population={"age_group": "mixed", "case_count": 8, "scenario": "multi_region"}
    )
    reports.append(report3)
    print_summary(report3)
    save_report(report3, output_dir, "CASE-003")

    # 最终总结
    print("\n" + "="*80)
    print("演示完成 - 案例总结")
    print("="*80)
    print(f"\n共生成 {len(reports)} 个联动报告:")
    for i, r in enumerate(reports, 1):
        print(f"\n案例 {i}: {r.report_id}")
        print(f"  - 症状: {r.risk_hypothesis.symptom_description[:30]}...")
        print(f"  - 风险因子: {len(r.risk_hypothesis.risk_factors)} 个")
        print(f"  - 怀疑环节: {r.risk_hypothesis.suspected_stage}")
        print(f"  - 综合风险: {r.overall_risk_level} ({r.overall_risk_score:.1f})")
        print(f"  - 核查企业: {len(r.enterprise_assessments)} 家")
    print(f"\n所有报告已保存至: {output_dir}/")
    print("="*80)


def print_summary(report: CombinedReport):
    """打印报告摘要"""
    print(f"\n📋 报告摘要")
    print(f"  报告 ID: {report.report_id}")
    print(f"  风险假设:")
    print(f"    - 风险因子: {', '.join(report.risk_hypothesis.risk_factors[:3])}")
    print(f"    - 怀疑环节: {report.risk_hypothesis.suspected_stage}")
    print(f"    - 置信度: {report.risk_hypothesis.confidence:.0%}")
    print(f"  综合评估:")
    print(f"    - 风险等级: {report.overall_risk_level}")
    print(f"    - 风险评分: {report.overall_risk_score:.1f}")
    print(f"    - 核查企业: {len(report.enterprise_assessments)} 家")
    print(f"    - 行动建议: {len(report.action_suggestions)} 条")


def save_report(report: CombinedReport, output_dir: Path, case_id: str):
    """保存报告到文件"""
    # 使用 COMBINED- 前缀 + 案例ID
    filename = f"COMBINED-{case_id}-{report.report_id}.json"
    report_file = output_dir / filename
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report.to_json())
    print(f"\n💾 报告已保存: {report_file}")


if __name__ == "__main__":
    demo_linked_workflow()
