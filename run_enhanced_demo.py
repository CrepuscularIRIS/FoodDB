#!/usr/bin/env python3
"""
Enhanced Demo Script for Dairy Supply Chain Risk Assessment

Demonstrates the Minimax M2.5 LLM integration, heterogeneous graph modeling,
and real-world case integration.
"""

import os
import sys
import argparse
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.llm_client import get_llm_client, MockLLMClient
from agent.heterogeneous_graph import (
    create_sample_heterogeneous_graph,
    RealDataGraphBuilder
)
from agent.case_mapper import get_repository, RiskCase
from agent.enhanced_reporter import (
    EnhancedReportGenerator,
    generate_demo_report
)


def print_header(title: str):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")


def demo_llm_client():
    """Demo: LLM Client functionality"""
    print_header("Demo 1: Minimax M2.5 LLM Client")

    # Try to get real client, fallback to mock
    client = get_llm_client(use_mock=True)

    print(f"Client type: {type(client).__name__}")
    print(f"Is configured: {client.is_configured()}")

    # Test risk report generation
    print("\nGenerating sample risk report...\n")

    response = client.generate_risk_report(
        target_name="光明乳业华东中心工厂-BATCH-2024-001",
        target_type="batch",
        risk_level="medium",
        risk_score=55,
        triggered_rules=[
            {"factor": "cold_chain", "reason": "冷链运输温度异常", "score": 60},
            {"factor": "inspection", "reason": "历史抽检发现菌落总数临界", "score": 45}
        ],
        evidence={
            "inspections": [
                {"inspection_id": "INS-001", "test_result": "qualified", "inspection_date": "2024-01-15"}
            ],
            "events": []
        }
    )

    if response.success:
        print("✅ LLM Report Generated Successfully!")
        print(f"Latency: {response.latency_ms:.2f}ms")
        if response.usage:
            print(f"Tokens: {response.usage}")
        print("\n--- Generated Content Preview ---\n")
        print(response.content[:1000] + "...")
    else:
        print(f"❌ Error: {response.error}")


def demo_heterogeneous_graph():
    """Demo: Heterogeneous Graph"""
    print_header("Demo 2: Heterogeneous Supply Chain Graph")

    # Try to build from real data
    processing_plants_file = "/home/yarizakurahime/data/agents/清洗后的上海市乳制品加工厂(1).xlsx"
    supply_chain_nodes_file = "/home/yarizakurahime/data/agents/上海市乳制品供应链节点_筛选后(1).csv"

    if os.path.exists(processing_plants_file) and os.path.exists(supply_chain_nodes_file):
        print("Building graph from real-world data...")
        try:
            builder = RealDataGraphBuilder()
            graph = builder.build_graph_from_real_data(
                processing_plants_file,
                supply_chain_nodes_file
            )
            print("✅ Graph built from real data!")
        except Exception as e:
            print(f"⚠️  Could not build from real data: {e}")
            print("Using sample graph instead...")
            graph = create_sample_heterogeneous_graph()
    else:
        print("Real data files not found, using sample graph...")
        graph = create_sample_heterogeneous_graph()

    # Display graph metrics
    metrics = graph.calculate_network_metrics()
    print("\n--- Graph Metrics ---")
    print(f"Total nodes: {metrics['total_nodes']}")
    print(f"Total edges: {metrics['total_edges']}")
    print(f"Average degree: {metrics['average_degree']}")
    print(f"Network density: {metrics['network_density']:.4f}")

    print("\n--- Node Type Distribution ---")
    for node_type, count in metrics['node_type_distribution'].items():
        print(f"  {node_type}: {count}")

    # Show sample nodes
    print("\n--- Sample Nodes ---")
    for node_type in ["牧场", "乳企", "物流", "仓储", "零售"]:
        from agent.heterogeneous_graph import NodeType
        nt = NodeType(node_type)
        nodes = graph.get_nodes_by_type(nt)[:2]
        for node in nodes:
            print(f"  [{node_type}] {node.name} (ID: {node.node_id})")

    # Show upstream/downstream for a processor
    processors = graph.get_nodes_by_type(NodeType("乳企"))
    if processors:
        proc = processors[0]
        print(f"\n--- Supply Chain for {proc.name} ---")

        upstream = graph.get_upstream_network(proc.node_id, depth=1)
        print(f"  Upstream suppliers: {len(upstream.get('nodes', []))}")
        for node_data in upstream.get('nodes', [])[:3]:
            print(f"    - {node_data['name']}")

        downstream = graph.get_downstream_network(proc.node_id, depth=1)
        print(f"  Downstream customers: {len(downstream.get('nodes', []))}")
        for node_data in downstream.get('nodes', [])[:3]:
            print(f"    - {node_data['name']}")


def demo_case_repository():
    """Demo: Case Repository"""
    print_header("Demo 3: Real-world Case Repository")

    repo = get_repository()

    print(f"Total cases loaded: {len(repo.get_all_cases())}")

    print("\n--- Case Overview ---")
    for case in repo.get_all_cases():
        print(f"  [{case.case_id}] {case.case_name}")
        print(f"      Company: {case.company}")
        print(f"      Risk Type: {case.risk_type} | Level: {case.risk_level}")

    # Get cases by risk type
    print("\n--- Cases by Risk Type: microbial ---")
    microbial_cases = repo.get_cases_by_risk_type("microbial")
    for case in microbial_cases:
        print(f"  - {case.case_name} ({case.year})")

    # Get GB standards for risk type
    print("\n--- GB Standards for 'cold_chain' risk ---")
    standards = repo.get_gb_standards_for_risk_type("cold_chain")
    for std in standards:
        print(f"  - {std}")

    # Get similar cases
    print("\n--- Similar Cases (high risk + microbial) ---")
    similar = repo.get_similar_cases("microbial", "high", limit=2)
    for case in similar:
        print(f"  - {case.case_name}")
        print(f"    Key testing: {', '.join(case.key_testing_items[:3])}")

    # Show LLM context for a case
    print("\n--- LLM Context for CASE-001 (Preview) ---")
    context = repo.get_llm_context_for_case("CASE-001")
    print(context[:800] + "...")


def demo_enhanced_report(case_id: str = "CASE-002", use_llm: bool = False):
    """Demo: Enhanced Report Generation"""
    print_header(f"Demo 4: Enhanced Report Generation ({case_id})")

    print(f"Generating report with LLM enhancement: {use_llm}")
    print("(Note: Set MINIMAX_API_KEY env var for real LLM, otherwise using mock)\n")

    report_md = generate_demo_report(case_id=case_id, use_llm=use_llm)

    if report_md:
        print("✅ Report generated successfully!\n")
        print("--- Report Preview ---\n")
        # Print first 2000 characters
        preview = report_md[:2000]
        print(preview)
        print("\n... [truncated] ...")

        # Save to file (consistent path with demo_all_cases)
        output_dir = "reports/enhanced"
        os.makedirs(output_dir, exist_ok=True)
        filename = f"{output_dir}/report_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report_md)
        print(f"\n💾 Full report saved to: {filename}")
    else:
        print("❌ Failed to generate report")


def demo_all_cases():
    """Generate reports for all demo cases"""
    print_header("Demo 5: Generate Reports for All Cases")

    case_ids = ["CASE-001", "CASE-002", "CASE-003", "CASE-004", "CASE-005", "CASE-006"]

    output_dir = "reports/enhanced"
    os.makedirs(output_dir, exist_ok=True)

    for case_id in case_ids:
        print(f"\nGenerating report for {case_id}...")
        report_md = generate_demo_report(case_id=case_id, use_llm=False)

        if report_md:
            filename = f"{output_dir}/report_{case_id}.md"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report_md)
            print(f"  ✅ Saved to {filename}")
        else:
            print(f"  ❌ Failed")

    print(f"\n📁 All reports saved to {output_dir}/")


def main():
    parser = argparse.ArgumentParser(
        description="Enhanced Demo for Dairy Supply Chain Risk Assessment"
    )
    parser.add_argument(
        "--demo",
        choices=["llm", "graph", "cases", "report", "all", "all-reports"],
        default="all",
        help="Which demo to run"
    )
    parser.add_argument(
        "--case-id",
        default="CASE-002",
        help="Case ID for report demo (CASE-001 to CASE-006)"
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use real LLM (requires MINIMAX_API_KEY)"
    )

    args = parser.parse_args()

    if args.demo == "llm":
        demo_llm_client()
    elif args.demo == "graph":
        demo_heterogeneous_graph()
    elif args.demo == "cases":
        demo_case_repository()
    elif args.demo == "report":
        demo_enhanced_report(args.case_id, args.use_llm)
    elif args.demo == "all-reports":
        demo_all_cases()
    else:  # all
        demo_llm_client()
        demo_heterogeneous_graph()
        demo_case_repository()
        demo_enhanced_report("CASE-002", use_llm=False)

        print("\n" + "=" * 60)
        print("  All demos completed!")
        print("=" * 60)
        print("\nTo run individual demos:")
        print("  python run_enhanced_demo.py --demo llm")
        print("  python run_enhanced_demo.py --demo graph")
        print("  python run_enhanced_demo.py --demo cases")
        print("  python run_enhanced_demo.py --demo report --case-id CASE-001")
        print("  python run_enhanced_demo.py --demo all-reports")


if __name__ == "__main__":
    main()
