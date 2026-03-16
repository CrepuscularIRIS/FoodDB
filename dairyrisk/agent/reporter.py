"""
报告生成模块 - 生成结构化风险研判报告
"""

from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class RiskAssessmentReport:
    """风险研判报告"""
    # 元信息
    report_id: str
    generated_at: str
    target_type: str  # batch / enterprise
    target_id: str
    target_name: str

    # 结论
    risk_level: str  # high / medium / low
    risk_score: float
    conclusion: str

    # 证据
    evidence_summary: str
    related_inspections: list[dict] = field(default_factory=list)
    related_events: list[dict] = field(default_factory=list)
    supply_chain_path: list[dict] = field(default_factory=list)

    # 依据
    gb_references: list[dict] = field(default_factory=list)
    triggered_rules: list[dict] = field(default_factory=list)

    # 建议
    sampling_suggestions: list[dict] = field(default_factory=list)
    traceability_suggestions: list[dict] = field(default_factory=list)
    risk_mitigation_suggestions: list[dict] = field(default_factory=list)

    # 传播分析（可选）
    propagation_analysis: Optional[dict] = None

    # 数据来源与证据类型（可解释性增强）
    data_sources: dict = field(default_factory=dict)
    evidence_types: list[dict] = field(default_factory=list)

    # LLM分析结果
    llm_analysis: Optional[str] = None
    llm_usage: Optional[dict] = None
    llm_latency_ms: Optional[float] = None

    # 案例类比与图分析指标
    case_analogies: list[dict] = field(default_factory=list)
    graph_metrics: Optional[dict] = None


class ReportGenerator:
    """报告生成器"""

    RISK_LEVEL_LABELS = {
        "high": "高风险（红色预警）",
        "medium": "中风险（橙色预警）",
        "low": "低风险（绿色）"
    }

    def generate(self, target_type: str, target_id: str, target_name: str,
                 score_result: object, retriever: object,
                 trace_result: Optional[dict] = None,
                 propagation_result: Optional[dict] = None) -> RiskAssessmentReport:
        """
        生成风险研判报告

        Args:
            target_type: 目标类型 (batch/enterprise)
            target_id: 目标ID
            target_name: 目标名称
            score_result: 评分结果
            retriever: 数据检索器
            trace_result: 追溯结果
            propagation_result: 传播分析结果

        Returns:
            RiskAssessmentReport
        """
        report_id = f"RPT-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{target_id}"

        # 生成结论
        conclusion = self._generate_conclusion(
            target_type, target_name, score_result
        )

        # 生成证据摘要
        evidence_summary = self._generate_evidence_summary(score_result)

        # 生成建议
        sampling_suggestions = self._generate_sampling_suggestions(
            target_type, target_id, score_result, retriever
        )
        traceability_suggestions = self._generate_traceability_suggestions(
            target_type, target_id, score_result, trace_result
        )
        mitigation_suggestions = self._generate_mitigation_suggestions(score_result)

        # 构建数据来源信息
        data_sources = {
            "enterprise_source": "release_v1_1/enterprise_master.csv",
            "inspection_source": "release_v1_1/inspection_records.csv",
            "event_source": "release_v1_1/regulatory_events.csv",
            "data_version": "v1.1",
            "frozen_at": "2026-03-13",
            "source_type": "mock_based_on_real_enterprises",
            "real_data_ratio": "0%",
            "note": "基于上海市市场监管局公开企业名单的模拟数据"
        }

        # 构建证据类型分布
        evidence_types = self._build_evidence_types(score_result)

        return RiskAssessmentReport(
            report_id=report_id,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            risk_level=score_result.risk_level,
            risk_score=score_result.total_score,
            conclusion=conclusion,
            evidence_summary=evidence_summary,
            related_inspections=score_result.evidence.get("inspections", []),
            related_events=score_result.evidence.get("events", []),
            supply_chain_path=self._format_supply_chain(trace_result),
            gb_references=self._extract_gb_references(score_result),
            triggered_rules=score_result.triggered_rules,
            sampling_suggestions=sampling_suggestions,
            traceability_suggestions=traceability_suggestions,
            risk_mitigation_suggestions=mitigation_suggestions,
            propagation_analysis=propagation_result,
            data_sources=data_sources,
            evidence_types=evidence_types
        )

    def _generate_conclusion(self, target_type: str, target_name: str,
                            score_result: object) -> str:
        """生成结论段落"""
        risk_label = self.RISK_LEVEL_LABELS.get(score_result.risk_level, "未知")

        if target_type == "batch":
            base = f"经综合研判，批次'{target_name}'的风险等级为{risk_label}，总分{score_result.total_score}分。"
        else:
            base = f"经综合研判，企业'{target_name}'的风险等级为{risk_label}，总分{score_result.total_score}分。"

        # 添加主要原因
        if score_result.triggered_rules:
            top_reasons = [r["reason"] for r in score_result.triggered_rules[:3]]
            base += f"主要风险因素：{'；'.join(top_reasons)}。"

        return base

    def _generate_evidence_summary(self, score_result: object) -> str:
        """生成证据摘要"""
        parts = []

        # 检验记录
        inspections = score_result.evidence.get("inspections", [])
        if inspections:
            unq_count = sum(1 for i in inspections if i.get("test_result") == "unqualified")
            parts.append(f"检验记录{len(inspections)}条，其中不合格{unq_count}条")

        # 监管事件
        events = score_result.evidence.get("events", [])
        if events:
            high_count = sum(1 for e in events if e.get("severity") == "high")
            parts.append(f"监管事件{len(events)}起，其中高风险{high_count}起")

        # 触发规则
        if score_result.triggered_rules:
            parts.append(f"触发风险规则{len(score_result.triggered_rules)}条")

        return "；".join(parts) if parts else "无特殊风险证据"

    def _generate_sampling_suggestions(self, target_type: str, target_id: str,
                                      score_result: object, retriever: object) -> list[dict]:
        """生成抽检建议"""
        suggestions = []

        if score_result.risk_level == "high":
            suggestions.append({
                "priority": "immediate",
                "action": "立即抽检",
                "target": target_id if target_type == "batch" else f"企业{target_id}所有在产批次",
                "reason": f"风险评分{score_result.total_score}分，达到高风险阈值",
                "sampling_items": ["菌落总数", "大肠菌群", "蛋白质"],
                "deadline": "24小时内"
            })
        elif score_result.risk_level == "medium":
            suggestions.append({
                "priority": "high",
                "action": "优先抽检",
                "target": target_id if target_type == "batch" else f"企业{target_id}近期生产批次",
                "reason": f"风险评分{score_result.total_score}分，存在潜在风险",
                "sampling_items": ["菌落总数", "大肠菌群"],
                "deadline": "3日内"
            })
        else:
            suggestions.append({
                "priority": "normal",
                "action": "常规抽检",
                "target": target_id if target_type == "batch" else f"企业{target_id}随机批次",
                "reason": "风险评分较低，按常规计划抽检",
                "sampling_items": ["常规指标"],
                "deadline": "按计划执行"
            })

        # 根据触发规则添加专项建议
        for rule in score_result.triggered_rules:
            if rule.get("factor") == "cold_chain":
                suggestions.append({
                    "priority": "immediate",
                    "action": "冷链专项检查",
                    "target": "仓储温度和运输记录",
                    "reason": "冷链条件异常",
                    "sampling_items": ["温度记录", "温控设备校验"],
                    "deadline": "立即"
                })

        return suggestions

    def _generate_traceability_suggestions(self, target_type: str, target_id: str,
                                          score_result: object,
                                          trace_result: Optional[dict]) -> list[dict]:
        """生成溯源建议"""
        suggestions = []

        if not trace_result:
            return suggestions

        # 原料溯源
        upstream = trace_result.get("upstream", [])
        if upstream:
            for u in upstream[:2]:
                ent = u.get("enterprise", {})
                suggestions.append({
                    "direction": "upstream",
                    "target": ent.get("enterprise_name", "未知供应商"),
                    "action": "核查原料批次和供应商资质",
                    "evidence_needed": ["原料检验报告", "供应商许可证", "进货查验记录"]
                })

        # 下游追溯
        downstream = trace_result.get("downstream", [])
        if downstream:
            for d in downstream[:2]:
                ent = d.get("enterprise", {})
                suggestions.append({
                    "direction": "downstream",
                    "target": ent.get("enterprise_name", "未知销售方"),
                    "action": "追踪产品流向",
                    "evidence_needed": ["销售记录", "物流单据", "库存记录"]
                })

        # 根据追溯完整性添加建议
        if score_result.traceability_risk > 50:
            suggestions.append({
                "direction": "internal",
                "target": "企业内部记录",
                "action": "补充完善追溯信息",
                "evidence_needed": ["原料批次记录", "生产记录", "检验记录"]
            })

        return suggestions

    def _generate_mitigation_suggestions(self, score_result: object) -> list[dict]:
        """生成风险缓解建议"""
        suggestions = []

        # 根据风险类型生成建议
        if score_result.inspection_risk > 50:
            suggestions.append({
                "category": "质量控制",
                "action": "加强出厂检验",
                "details": "增加检验频次，完善检验项目"
            })

        if score_result.cold_chain_risk > 50:
            suggestions.append({
                "category": "储运管理",
                "action": "整改冷链设施",
                "details": "检查冷藏设备和温控系统，确保温度记录完整"
            })

        if score_result.regulatory_risk > 50:
            suggestions.append({
                "category": "合规管理",
                "action": "整改违规行为",
                "details": "针对历史处罚事项进行整改，完善合规体系"
            })

        if score_result.supplier_risk > 50:
            suggestions.append({
                "category": "供应商管理",
                "action": "评估和更换高风险供应商",
                "details": "对上游供应商进行审核，优先选择合规供应商"
            })

        if not suggestions:
            suggestions.append({
                "category": "常规管理",
                "action": "保持现有管理措施",
                "details": "继续执行现有质量管理体系"
            })

        return suggestions

    def _format_supply_chain(self, trace_result: Optional[dict]) -> list[dict]:
        """格式化供应链路径"""
        if not trace_result:
            return []

        path = []

        # 上游
        for u in trace_result.get("upstream", []):
            ent = u.get("enterprise", {})
            path.append({
                "direction": "upstream",
                "node_type": ent.get("node_type", "未知"),
                "name": ent.get("enterprise_name", "未知"),
                "relation": u.get("type", "供应关系")
            })

        # 当前节点
        production = trace_result.get("production_enterprise")
        if production:
            path.append({
                "direction": "current",
                "node_type": production.get("node_type", "乳企"),
                "name": production.get("enterprise_name", "未知"),
                "relation": "生产加工"
            })

        # 下游
        for d in trace_result.get("downstream", []):
            ent = d.get("enterprise", {})
            path.append({
                "direction": "downstream",
                "node_type": ent.get("node_type", "未知"),
                "name": ent.get("enterprise_name", "未知"),
                "relation": d.get("type", "销售关系")
            })

        return path

    def _extract_gb_references(self, score_result: object) -> list[dict]:
        """提取相关GB标准"""
        refs = []

        # 从触发规则中提取
        for rule in score_result.triggered_rules:
            # 这里简化处理，实际需要更复杂的映射
            if "cold_chain" in rule.get("factor", ""):
                refs.append({
                    "gb_no": "GB 19645-2010",
                    "clause": "冷链储运要求",
                    "requirement": "巴氏杀菌乳应在2-6°C条件下储存和运输"
                })

        return refs

    def _build_evidence_types(self, score_result: object) -> list[dict]:
        """构建证据类型分布"""
        evidence_types = []

        # 检验记录证据
        inspections = score_result.evidence.get("inspections", [])
        if inspections:
            evidence_types.append({
                "type": "检验记录",
                "count": len(inspections),
                "evidence_level": "一级证据（原始数据）",
                "data_source": "政府抽检公告",
                "reliability": "高"
            })

        # 监管事件证据
        events = score_result.evidence.get("events", [])
        if events:
            evidence_types.append({
                "type": "监管事件",
                "count": len(events),
                "evidence_level": "一级证据（官方处罚）",
                "data_source": "行政处罚公示",
                "reliability": "高"
            })

        # 规则触发证据
        if score_result.triggered_rules:
            evidence_types.append({
                "type": "规则匹配",
                "count": len(score_result.triggered_rules),
                "evidence_level": "二级证据（规则推导）",
                "data_source": "GB标准规则库",
                "reliability": "中"
            })

        return evidence_types

    def format_report_to_markdown(self, report: RiskAssessmentReport) -> str:
        """将报告格式化为Markdown"""
        lines = [
            f"# 乳制品供应链风险研判报告",
            f"",
            f"**报告编号**: {report.report_id}",
            f"**生成时间**: {report.generated_at}",
            f"**研判对象**: {report.target_name} ({report.target_type})",
            f"",
            f"---",
            f"",
            f"## 一、结论",
            f"",
            f"**风险等级**: {self.RISK_LEVEL_LABELS.get(report.risk_level, report.risk_level)}",
            f"",
            f"**风险评分**: {report.risk_score}/100",
            f"",
            f"{report.conclusion}",
            f"",
            f"## 二、证据",
            f"",
            f"{report.evidence_summary}",
            f"",
        ]

        # 检验记录
        if report.related_inspections:
            lines.extend([
                f"### 相关检验记录",
                f"",
            ])
            for ins in report.related_inspections[:5]:
                result = "✓ 合格" if ins.get("test_result") == "qualified" else "✗ 不合格"
                lines.append(f"- {ins.get('inspection_id')}: {result} ({ins.get('inspection_date', '未知日期')})")
                if ins.get("unqualified_items"):
                    lines.append(f"  - 不合格项: {ins['unqualified_items']}")
            lines.append("")

        # 监管事件
        if report.related_events:
            lines.extend([
                f"### 相关监管事件",
                f"",
            ])
            for evt in report.related_events[:5]:
                severity = {"high": "🔴 高", "medium": "🟠 中", "low": "🟢 低"}.get(
                    evt.get("severity"), "⚪ 未知"
                )
                lines.append(f"- {evt.get('event_id')}: {severity} - {evt.get('event_type')} ({evt.get('event_date', '未知日期')})")
            lines.append("")

        # 供应链路径
        if report.supply_chain_path:
            lines.extend([
                f"### 供应链路径",
                f"",
            ])
            for node in report.supply_chain_path:
                direction = {"upstream": "⬆️", "current": "⏺️", "downstream": "⬇️"}.get(
                    node.get("direction"), "➡️"
                )
                lines.append(f"{direction} {node.get('name')} ({node.get('node_type')}) - {node.get('relation')}")
            lines.append("")

        # 依据
        lines.extend([
            f"## 三、依据",
            f"",
        ])

        if report.gb_references:
            lines.append(f"### GB标准条款")
            lines.append("")
            for ref in report.gb_references:
                lines.append(f"- **{ref['gb_no']}** {ref['clause']}")
                lines.append(f"  - 要求: {ref['requirement']}")
            lines.append("")

        if report.triggered_rules:
            lines.append(f"### 触发规则")
            lines.append("")
            for rule in report.triggered_rules:
                lines.append(f"- {rule.get('factor')}: {rule.get('reason')} (风险分: {rule.get('score')})")
            lines.append("")

        # 建议
        lines.extend([
            f"## 四、建议",
            f"",
        ])

        if report.sampling_suggestions:
            lines.append(f"### 抽检建议")
            lines.append("")
            for sug in report.sampling_suggestions:
                priority = {"immediate": "🚨 紧急", "high": "⚠️ 优先", "normal": "📋 常规"}.get(
                    sug.get("priority"), "📋"
                )
                lines.append(f"{priority} **{sug['action']}**")
                lines.append(f"- 目标: {sug['target']}")
                lines.append(f"- 原因: {sug['reason']}")
                lines.append(f"- 检验项: {', '.join(sug['sampling_items'])}")
                lines.append(f"- 时限: {sug['deadline']}")
                lines.append("")

        if report.traceability_suggestions:
            lines.append(f"### 溯源建议")
            lines.append("")
            for sug in report.traceability_suggestions:
                direction = {"upstream": "⬆️ 向上游", "downstream": "⬇️ 向下游", "internal": "🏭 内部"}.get(
                    sug.get("direction"), "➡️"
                )
                lines.append(f"{direction} **{sug['target']}**")
                lines.append(f"- 行动: {sug['action']}")
                lines.append(f"- 需核查: {', '.join(sug['evidence_needed'])}")
                lines.append("")

        if report.risk_mitigation_suggestions:
            lines.append(f"### 风险缓解建议")
            lines.append("")
            for sug in report.risk_mitigation_suggestions:
                lines.append(f"**{sug['category']}**: {sug['action']}")
                lines.append(f"- {sug['details']}")
                lines.append("")

        # LLM 深度分析（如果有）
        chapter_num = 5
        if report.llm_analysis:
            lines.extend([
                f"## 六、AI深度分析",
                f"",
                f"{report.llm_analysis}",
                f"",
            ])
            chapter_num = 6

        # 传播分析（如果有）
        if report.propagation_analysis:
            lines.extend([
                f"## {'七' if report.llm_analysis else '六'}、供应链网络分析",
                f"",
                f"**影响范围**: {report.propagation_analysis.get('affected_nodes', 0)} 个节点",
                f"",
                f"**传播半径**: {report.propagation_analysis.get('propagation_radius', 0)} 跳",
                f"",
            ])

        lines.extend([
            f"---",
            f"",
            f"*本报告由乳制品供应链风险研判智能体自动生成*",
            f"",
            f"*报告仅供参考，具体执法决策请以现场检查为准*",
        ])

        return "\n".join(lines)

    DEFAULT_REPORT_DIR = "reports/enhanced"

    def save_report(self, report: RiskAssessmentReport, output_dir: str = None) -> str:
        """
        保存报告到文件

        Args:
            report: 报告对象
            output_dir: 输出目录，默认为 reports/enhanced

        Returns:
            文件路径
        """
        import os
        if output_dir is None:
            output_dir = self.DEFAULT_REPORT_DIR

        os.makedirs(output_dir, exist_ok=True)

        filename = f"{report.report_id}.md"
        filepath = f"{output_dir}/{filename}"

        content = self.format_report_to_markdown(report)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        return filepath
