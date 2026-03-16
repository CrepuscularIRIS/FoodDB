#!/usr/bin/env python3
"""
乳制品供应链风险研判智能体 - 一键运行入口

使用方法:
    python run_demo.py --case case1          # 运行案例1
    python run_demo.py --case case2          # 运行案例2
    python run_demo.py --case case3          # 运行案例3
    python run_demo.py --all                 # 运行全部案例
    python run_demo.py --query "BATCH-000001" # 自定义查询
"""

import argparse
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from agent.workflow import RiskAssessmentAgent


# 预定义演示案例
DEMO_CASES = {
    "case1": {
        "name": "低温奶冷链异常案例",
        "query": "BATCH-000001",
        "description": "巴氏杀菌乳冷链温度异常，存在微生物超标风险"
    },
    "case2": {
        "name": "常温奶批次添加剂案例",
        "query": "BATCH-000050",
        "description": "灭菌乳批次检验数据异常"
    },
    "case3": {
        "name": "供应商联动风险案例",
        "query": "ENT-0005",
        "description": "上游供应商资质过期，存在联动风险"
    }
}


def run_case(case_id: str, agent: RiskAssessmentAgent, with_propagation: bool = False):
    """运行单个案例"""
    case = DEMO_CASES.get(case_id)
    if not case:
        print(f"错误: 未知案例 '{case_id}'")
        print(f"可用案例: {', '.join(DEMO_CASES.keys())}")
        return None

    print("\n" + "=" * 70)
    print(f"案例: {case['name']}")
    print(f"描述: {case['description']}")
    print(f"查询: {case['query']}")
    print("=" * 70)

    try:
        if with_propagation:
            report = agent.assess_with_propagation(case['query'])
        else:
            report = agent.assess(case['query'])

        # 打印报告摘要
        print("\n" + "-" * 70)
        print("报告摘要")
        print("-" * 70)
        print(f"报告编号: {report.report_id}")
        print(f"风险等级: {report.risk_level}")
        print(f"风险评分: {report.risk_score}/100")
        print(f"结论: {report.conclusion[:100]}...")

        # 保存报告
        filepath = agent.save_report(report, output_dir=f"reports/{case_id}")
        print(f"\n✓ 报告已保存: {filepath}")

        return report

    except Exception as e:
        print(f"\n✗ 研判失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_all_cases(agent: RiskAssessmentAgent):
    """运行全部案例"""
    print("\n" + "=" * 70)
    print("运行全部演示案例")
    print("=" * 70)

    reports = {}
    for case_id in DEMO_CASES.keys():
        report = run_case(case_id, agent)
        if report:
            reports[case_id] = report

    # 汇总
    print("\n" + "=" * 70)
    print("案例运行汇总")
    print("=" * 70)
    for case_id, case in DEMO_CASES.items():
        if case_id in reports:
            r = reports[case_id]
            print(f"{case_id}: {case['name']} - {r.risk_level} ({r.risk_score}分)")
        else:
            print(f"{case_id}: {case['name']} - 运行失败")

    return reports


def run_custom_query(agent: RiskAssessmentAgent, query: str, with_propagation: bool = False):
    """运行自定义查询"""
    print(f"\n自定义查询: {query}")

    try:
        if with_propagation:
            report = agent.assess_with_propagation(query)
        else:
            report = agent.assess(query)

        # 打印完整报告
        print("\n" + "=" * 70)
        print("完整报告")
        print("=" * 70)
        print(agent.generate_report(report, output_format="markdown"))

        # 保存报告
        filepath = agent.save_report(report, output_dir="reports/custom")
        print(f"\n✓ 报告已保存: {filepath}")

        return report

    except Exception as e:
        print(f"\n✗ 研判失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser(
        description="乳制品供应链风险研判智能体",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_demo.py --case case1              # 运行案例1
  python run_demo.py --case case2 --propagation # 运行案例2（带传播分析）
  python run_demo.py --all                     # 运行全部案例
  python run_demo.py --query "BATCH-000001"    # 自定义批次查询
  python run_demo.py --query "光明乳业"         # 自定义企业查询
        """
    )

    parser.add_argument(
        "--case",
        choices=["case1", "case2", "case3"],
        help="运行指定案例"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="运行全部案例"
    )
    parser.add_argument(
        "--query",
        type=str,
        help="自定义查询（企业ID/名称 或 批次ID/号）"
    )
    parser.add_argument(
        "--propagation",
        action="store_true",
        help="启用风险传播分析"
    )
    parser.add_argument(
        "--list-cases",
        action="store_true",
        help="列出所有可用案例"
    )

    args = parser.parse_args()

    # 列出案例
    if args.list_cases:
        print("\n可用案例:")
        for case_id, case in DEMO_CASES.items():
            print(f"  {case_id}: {case['name']}")
            print(f"         {case['description']}")
            print(f"         查询: {case['query']}")
        return

    # 初始化Agent
    print("\n" + "=" * 70)
    print("乳制品供应链风险研判智能体")
    print("=" * 70)

    agent = RiskAssessmentAgent()

    # 执行命令
    if args.all:
        run_all_cases(agent)
    elif args.case:
        run_case(args.case, agent, with_propagation=args.propagation)
    elif args.query:
        run_custom_query(agent, args.query, with_propagation=args.propagation)
    else:
        # 默认运行全部
        print("\n未指定案例，默认运行全部案例...")
        run_all_cases(agent)

    print("\n" + "=" * 70)
    print("完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()
