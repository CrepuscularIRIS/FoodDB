"""
Enhanced Report Generator with LLM Integration

Integrates Minimax M2.5 LLM, heterogeneous graph analysis, and real-world
case analogies for intelligent risk assessment report generation.
"""

import os
import logging
from datetime import datetime
from typing import Optional

from agent.llm_client import get_llm_client, LLMResponse
from agent.heterogeneous_graph import (
    HeterogeneousSupplyChainGraph,
    RealDataGraphBuilder,
    create_sample_heterogeneous_graph
)
from agent.case_mapper import get_repository, RiskCase
from agent.reporter import (
    RiskAssessmentReport,
    ReportGenerator as BaseReportGenerator
)

logger = logging.getLogger(__name__)


class EnhancedReportGenerator:
    """
    Enhanced report generator with LLM and heterogeneous graph capabilities
    """

    def __init__(
        self,
        use_llm: bool = True,
        use_mock_llm: bool = False,
        graph: Optional[HeterogeneousSupplyChainGraph] = None
    ):
        """
        Initialize the enhanced report generator

        Args:
            use_llm: Whether to use LLM for report enhancement
            use_mock_llm: Whether to use mock LLM (for testing without API key)
            graph: Pre-built heterogeneous graph (will create sample if None)
        """
        self.base_generator = BaseReportGenerator()
        self.case_repository = get_repository()

        # Initialize LLM client
        self.use_llm = use_llm
        if use_llm:
            self.llm_client = get_llm_client(use_mock=use_mock_llm)
        else:
            self.llm_client = None

        # Initialize or create graph
        if graph is None:
            self.graph = self._build_graph_from_real_data()
        else:
            self.graph = graph

    def _build_graph_from_real_data(self) -> HeterogeneousSupplyChainGraph:
        """Build heterogeneous graph from real-world data"""
        processing_plants_file = "/home/yarizakurahime/data/agents/清洗后的上海市乳制品加工厂(1).xlsx"
        supply_chain_nodes_file = "/home/yarizakurahime/data/agents/上海市乳制品供应链节点_筛选后(1).csv"

        # Check if files exist
        if os.path.exists(processing_plants_file) and os.path.exists(supply_chain_nodes_file):
            try:
                builder = RealDataGraphBuilder()
                graph = builder.build_graph_from_real_data(
                    processing_plants_file,
                    supply_chain_nodes_file
                )
                logger.info(f"Built graph from real data: {len(graph.nodes)} nodes")
                return graph
            except Exception as e:
                logger.error(f"Failed to build graph from real data: {e}")
                logger.info("Falling back to sample graph")

        # Fallback to sample graph
        return create_sample_heterogeneous_graph()

    def generate_enhanced_report(
        self,
        target_type: str,
        target_id: str,
        target_name: str,
        score_result: object,
        retriever: object,
        trace_result: Optional[dict] = None,
        propagation_result: Optional[dict] = None
    ) -> RiskAssessmentReport:
        """
        Generate an enhanced risk assessment report

        Combines rule-based scoring with LLM-enhanced analysis and
        heterogeneous graph insights.
        """
        # First generate the base report
        base_report = self.base_generator.generate(
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            score_result=score_result,
            retriever=retriever,
            trace_result=trace_result,
            propagation_result=propagation_result
        )

        # Get heterogeneous graph context
        graph_context = self._get_graph_context(target_id, target_name)

        # Get similar real-world cases
        similar_cases = self._get_similar_cases(score_result)

        # Generate LLM-enhanced content if enabled
        if self.use_llm and self.llm_client:
            llm_response = self.llm_client.generate_risk_report(
                target_name=target_name,
                target_type=target_type,
                risk_level=score_result.risk_level,
                risk_score=score_result.total_score,
                triggered_rules=score_result.triggered_rules,
                evidence=score_result.evidence,
                supply_chain_context=graph_context,
                similar_cases=[c.to_dict() for c in similar_cases]
            )

            if llm_response.success:
                # Append LLM analysis to report
                base_report.llm_analysis = llm_response.content
                base_report.llm_usage = llm_response.usage
                base_report.llm_latency_ms = llm_response.latency_ms

                # Update conclusion with LLM insights
                base_report.conclusion += f"\n\n【AI深度分析】\n{self._extract_summary(llm_response.content)}"

        # Add case analogies
        base_report.case_analogies = [
            {
                "case_id": c.case_id,
                "case_name": c.case_name,
                "similarity": self._calculate_similarity(c, score_result),
                "key_lesson": c.root_cause[:100] + "..."
            }
            for c in similar_cases[:3]
        ]

        # Add graph metrics
        base_report.graph_metrics = self.graph.calculate_network_metrics()

        return base_report

    def _get_graph_context(self, target_id: str, target_name: str) -> Optional[dict]:
        """Get supply chain graph context for the target"""
        try:
            # Try to find node by name
            node_id = None
            for nid, node in self.graph.nodes.items():
                if target_name in node.name or node.name in target_name:
                    node_id = nid
                    break

            if node_id is None:
                return None

            # Get upstream and downstream networks
            upstream = self.graph.get_upstream_network(node_id, depth=2)
            downstream = self.graph.get_downstream_network(node_id, depth=2)

            return {
                "target_node_id": node_id,
                "upstream_nodes": len(upstream.get("nodes", [])),
                "downstream_nodes": len(downstream.get("nodes", [])),
                "complexity_score": self._calculate_complexity(node_id)
            }

        except Exception as e:
            logger.error(f"Error getting graph context: {e}")
            return None

    def _calculate_complexity(self, node_id: str) -> float:
        """Calculate supply chain complexity score for a node"""
        if node_id not in self.graph.nodes:
            return 0.0

        upstream = self.graph.get_upstream_network(node_id, depth=2)
        downstream = self.graph.get_downstream_network(node_id, depth=2)

        # Complexity based on number of connections
        up_count = len(upstream.get("nodes", []))
        down_count = len(downstream.get("nodes", []))

        # Normalize to 0-100 scale
        complexity = min(100, (up_count + down_count) * 10)
        return round(complexity, 2)

    def _get_similar_cases(self, score_result: object) -> list[RiskCase]:
        """Get similar real-world cases based on risk factors"""
        # Determine primary risk type from triggered rules
        risk_type = None
        risk_level = score_result.risk_level

        for rule in score_result.triggered_rules:
            factor = rule.get("factor", "")
            if "cold_chain" in factor:
                risk_type = "cold_chain"
                break
            elif "inspection" in factor:
                risk_type = "microbial"
                break
            elif "supplier" in factor:
                risk_type = "veterinary_drug"
                break

        # Get similar cases
        if risk_type:
            return self.case_repository.get_similar_cases(risk_type, risk_level, limit=3)
        else:
            # Return diverse set of cases
            return [
                self.case_repository.get_case("CASE-001"),
                self.case_repository.get_case("CASE-002"),
                self.case_repository.get_case("CASE-003")
            ]

    def _calculate_similarity(self, case: RiskCase, score_result: object) -> str:
        """Calculate similarity between case and current assessment"""
        similarities = []

        # Check risk level match
        if case.risk_level == score_result.risk_level:
            similarities.append("风险等级相同")

        # Check triggered rules against case risk type
        for rule in score_result.triggered_rules:
            factor = rule.get("factor", "")
            if case.risk_type == "cold_chain" and "cold_chain" in factor:
                similarities.append("冷链风险相似")
            elif case.risk_type == "microbial" and "inspection" in factor:
                similarities.append("微生物风险相似")

        return "、".join(similarities) if similarities else "风险类型相关"

    def _num_to_cn(self, num: int) -> str:
        """Convert number to Chinese numeral (1-9)"""
        cn_nums = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九']
        if 1 <= num <= 9:
            return cn_nums[num]
        return str(num)

    def _extract_summary(self, llm_content: str) -> str:
        """Extract summary from LLM content"""
        # Extract first section (Executive Summary)
        lines = llm_content.split('\n')
        summary_lines = []
        in_summary = False

        for line in lines:
            if '执行摘要' in line or '1.' in line:
                in_summary = True
            elif in_summary and (line.startswith('2.') or line.startswith('##')):
                break
            elif in_summary and line.strip():
                summary_lines.append(line.strip())

        return '\n'.join(summary_lines[:5]) if summary_lines else llm_content[:300]

    def format_enhanced_report_to_markdown(self, report: RiskAssessmentReport) -> str:
        """Format enhanced report to Markdown with LLM analysis"""
        # Get base markdown
        base_md = self.base_generator.format_report_to_markdown(report)

        # Track section number dynamically
        section_num = 5  # Start after base sections (一~四)
        enhanced_sections = []

        # Add case analogies
        has_cases = hasattr(report, 'case_analogies') and report.case_analogies
        if has_cases:
            enhanced_sections.append(f"\n## {self._num_to_cn(section_num)}、历史案例类比\n")
            section_num += 1
            for analogy in report.case_analogies:
                enhanced_sections.append(
                    f"\n### {analogy['case_name']}\n"
                    f"- 相似度: {analogy['similarity']}\n"
                    f"- 关键教训: {analogy['key_lesson']}\n"
                )

        # Add LLM analysis
        has_llm = hasattr(report, 'llm_analysis') and report.llm_analysis
        if has_llm:
            enhanced_sections.append(f"\n## {self._num_to_cn(section_num)}、AI深度分析报告\n")
            section_num += 1
            enhanced_sections.append(report.llm_analysis)

            # Add LLM usage stats
            if hasattr(report, 'llm_usage') and report.llm_usage:
                usage = report.llm_usage
                enhanced_sections.append(
                    f"\n\n*（本分析由Minimax M2.5生成，"
                    f"耗时{getattr(report, 'llm_latency_ms', 0):.0f}ms，"
                    f"使用{usage.get('total_tokens', 'N/A')} tokens）*"
                )

        # Add graph metrics
        if hasattr(report, 'graph_metrics') and report.graph_metrics:
            metrics = report.graph_metrics
            enhanced_sections.append(f"\n## {self._num_to_cn(section_num)}、供应链网络分析\n")
            enhanced_sections.append(
                f"\n- 网络节点总数: {metrics.get('total_nodes', 'N/A')}\n"
                f"- 连接关系数: {metrics.get('total_edges', 'N/A')}\n"
                f"- 网络密度: {metrics.get('network_density', 'N/A'):.4f}\n"
            )

            # Node type distribution
            type_dist = metrics.get('node_type_distribution', {})
            if type_dist:
                enhanced_sections.append("\n### 节点类型分布\n")
                for node_type, count in type_dist.items():
                    enhanced_sections.append(f"- {node_type}: {count}个\n")

        # Combine everything
        # Insert enhanced sections before the footer
        footer_marker = "*本报告由乳制品供应链风险研判智能体自动生成*"
        if footer_marker in base_md:
            base_md = base_md.replace(
                footer_marker,
                ''.join(enhanced_sections) + '\n\n---\n\n' + footer_marker
            )
        else:
            base_md += '\n'.join(enhanced_sections)

        return base_md

    def generate_report_with_demo_case(
        self,
        case_id: str,
        target_name: str = None
    ) -> Optional[RiskAssessmentReport]:
        """
        Generate a report based on a demo case

        Args:
            case_id: ID of the demo case (e.g., "CASE-001")
            target_name: Optional override for target name

        Returns:
            RiskAssessmentReport or None
        """
        case = self.case_repository.get_case(case_id)
        if not case:
            logger.error(f"Case {case_id} not found")
            return None

        # Create mock score result based on case
        class MockScoreResult:
            def __init__(self, case):
                self.risk_level = case.risk_level
                self.total_score = 75 if case.risk_level == "high" else (55 if case.risk_level == "medium" else 30)
                self.triggered_rules = [
                    {"factor": case.risk_type, "reason": case.direct_cause[:100], "score": 60}
                ]
                self.evidence = {
                    "inspections": [],
                    "events": []
                }
                # Add all risk factor scores
                self.product_risk = 40
                self.supply_chain_risk = 50
                self.supplier_risk = 60 if case.risk_type in ["veterinary_drug", "microbial"] else 30
                self.traceability_risk = 35
                self.label_risk = 70 if case.risk_type == "additive" else 20
                self.inspection_risk = 65 if case.risk_type in ["microbial", "cross_contamination"] else 30
                self.regulatory_risk = 50
                self.cold_chain_risk = 75 if case.risk_type == "cold_chain" else 25
                self.diffusion_risk = 45

        score_result = MockScoreResult(case)

        # Generate report
        report = self.generate_enhanced_report(
            target_type="batch" if "批次" in case.product else "enterprise",
            target_id=case.case_id,
            target_name=target_name or f"{case.company}-{case.product}",
            score_result=score_result,
            retriever=None,
            trace_result=None,
            propagation_result=None
        )

        # Add case-specific context
        report.case_id = case.case_id
        report.case_name = case.case_name

        return report


# Convenience function
def generate_demo_report(case_id: str = "CASE-001", use_llm: bool = True) -> Optional[str]:
    """
    Generate a demo report for a specific case

    Args:
        case_id: Case ID (CASE-001 to CASE-006)
        use_llm: Whether to use LLM enhancement

    Returns:
        Markdown formatted report string
    """
    generator = EnhancedReportGenerator(use_llm=use_llm, use_mock_llm=not use_llm)
    report = generator.generate_report_with_demo_case(case_id)

    if report:
        return generator.format_enhanced_report_to_markdown(report)
    return None
