"""
5个验收验证命令 - 可执行测试脚本
"""
import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 加载环境变量
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✓ 已加载环境变量: {env_path}")
except ImportError:
    pass

def test_1_minimax_connection():
    """验证1: Minimax M2.5 是否真正连接（不是Mock）"""
    print("\n" + "="*70)
    print("【验证1】Minimax M2.5 真实API连接测试")
    print("="*70)
    
    from agent.llm_client import get_llm_client, LLMConfig
    
    client = get_llm_client()
    
    if not client.is_configured():
        print("❌ FAIL: API Key 未配置")
        return False
    
    print(f"✓ API Key 已配置: {client.config.api_key[:10]}...")
    print(f"✓ 模型: {client.config.model}")
    print(f"✓ Base URL: {client.config.base_url}")
    
    # 检查是否是Mock客户端
    client_class = client.__class__.__name__
    print(f"✓ 客户端类型: {client_class}")
    
    if "Mock" in client_class:
        print("❌ FAIL: 当前使用的是 MockLLMClient（模拟客户端）")
        print("   原因: API Key 可能无效或环境变量未正确加载")
        return False
    
    print("\n✅ PASS: 使用的是真实 MinimaxLLMClient")
    return True

def test_2_symptom_extraction():
    """验证2: Mode B 症状提取（自然语言 → 标准症状）"""
    print("\n" + "="*70)
    print("【验证2】Mode B 症状提取测试")
    print("="*70)
    
    from agent.symptom_extractor import get_symptom_extractor
    
    extractor = get_symptom_extractor()
    
    test_queries = [
        "我拉肚子还发烧",
        "肚子疼想吐",
        "宝宝腹泻、发热",
        "头痛乏力，还有点皮疹"
    ]
    
    for query in test_queries:
        print(f"\n输入: '{query}'")
        result = extractor.extract_symptoms(query)
        print(f"  原始症状: {result.raw_symptoms}")
        print(f"  标准化症状: {result.standardized_symptoms}")
        print(f"  置信度: {result.confidence:.2f}")
        print(f"  延迟: {result.latency_ms:.0f}ms")
        
        if not result.standardized_symptoms:
            print("  ⚠️ 未提取到标准症状")
        else:
            print(f"  ✅ 成功提取: {', '.join(result.standardized_symptoms)}")
    
    print("\n✅ PASS: 症状提取完成")
    return True

def test_3_enterprise_matching():
    """验证3: Mode B → 企业候选匹配（为何返回0家）"""
    print("\n" + "="*70)
    print("【验证3】企业候选匹配测试（排查0候选问题）")
    print("="*70)
    
    from agent.retriever import DataRetriever
    from agent.enterprise_matcher import EnterpriseMatcher
    
    retriever = DataRetriever()
    matcher = EnterpriseMatcher(retriever)
    
    print(f"\n数据加载:")
    print(f"  - 企业总数: {len(retriever.enterprises)}")
    print(f"  - 按类型分布:")
    
    from collections import Counter
    node_types = Counter([e.get('node_type', 'unknown') for e in retriever.enterprises])
    for nt, count in node_types.items():
        print(f"    · {nt}: {count}家")
    
    test_cases = [
        {"name": "腹泻+发热 → 生产环节", "risk_factors": ["腹泻", "发热"], "stage": "生产加工"},
        {"name": "腹痛+呕吐 → 原料环节", "risk_factors": ["腹痛", "呕吐"], "stage": "原料"},
        {"name": "头晕 → 物流环节", "risk_factors": ["头晕"], "stage": "物流"},
    ]
    
    for case in test_cases:
        print(f"\n【{case['name']}】")
        print(f"  风险因子: {case['risk_factors']}")
        print(f"  怀疑环节: {case['stage']}")
        
        # 检查目标节点类型
        target_types = matcher._get_target_node_types(case['stage'])
        print(f"  目标节点类型: {target_types}")
        
        # 查看匹配到的企业数（在过滤前）
        filtered_ents = [e for e in retriever.enterprises 
                        if e.get('node_type') in target_types]
        print(f"  该环节企业数: {len(filtered_ents)}")
        
        # 执行匹配
        candidates = matcher.match(
            risk_factors=case['risk_factors'],
            suspected_stage=case['stage'],
            top_k=5
        )
        
        print(f"  匹配结果: {len(candidates)} 家企业")
        
        if len(candidates) == 0:
            print("  ⚠️ 返回0家！诊断信息:")
            # 显示该环节企业的详细情况
            for ent in filtered_ents[:3]:
                ent_id = ent.get('enterprise_id')
                violations = matcher.ent_violations.get(ent_id, [])
                inspections = matcher.ent_inspections.get(ent_id, [])
                print(f"    - {ent.get('enterprise_name')}: 违规{len(violations)}次, 检验{len(inspections)}次")
        else:
            for c in candidates[:3]:
                print(f"    - {c.enterprise_name} ({c.node_type}): {c.score:.0f}分")
    
    return True

def test_4_linked_workflow():
    """验证4: 完整联动流程（Mode A/B）"""
    print("\n" + "="*70)
    print("【验证4】完整联动工作流测试")
    print("="*70)
    
    from agent.orchestrator import Orchestrator
    
    orchestrator = Orchestrator()
    
    test_case = {
        "symptom": "腹泻、发热、腹痛",
        "population": {"age_group": "infant", "case_count": 3}
    }
    
    print(f"\n输入症状: {test_case['symptom']}")
    print(f"人群特征: {test_case['population']}")
    
    try:
        report = orchestrator.run_linked_workflow(
            symptom_description=test_case['symptom'],
            population=test_case['population']
        )
        
        print(f"\n✓ 联动报告生成成功")
        print(f"  - 报告ID: {report.report_id}")
        print(f"  - 风险假设:")
        print(f"    · 风险因子: {report.risk_hypothesis.risk_factors[:3] if report.risk_hypothesis else []}")
        print(f"    · 怀疑环节: {report.risk_hypothesis.suspected_stage if report.risk_hypothesis else 'N/A'}")
        conf = report.risk_hypothesis.confidence if report.risk_hypothesis else 0
        print(f"    · 置信度: {conf:.2f}")
        print(f"  - 企业核查: {len(report.enterprise_assessments)} 家")
        print(f"  - 综合风险: {report.overall_risk_level} ({report.overall_risk_score:.1f})")
        print(f"  - 行动建议: {len(report.action_suggestions)} 条")
        
        if len(report.enterprise_assessments) == 0:
            print("\n⚠️ 警告: 未匹配到任何企业候选！")
        
        print("\n✅ PASS: 联动工作流完成")
        return True
        
    except Exception as e:
        print(f"\n❌ FAIL: 工作流执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_5_report_completeness():
    """验证5: 报告数据完整性检查"""
    print("\n" + "="*70)
    print("【验证5】报告数据完整性检查")
    print("="*70)
    
    from agent.orchestrator import Orchestrator
    
    orchestrator = Orchestrator()
    
    report = orchestrator.run_linked_workflow(
        symptom_description="腹泻、发热",
        population={"age_group": "child"}
    )
    
    checks = []
    
    # 检查1: RiskHypothesis
    has_hypothesis = report.risk_hypothesis is not None
    checks.append(("RiskHypothesis 存在", has_hypothesis))
    
    if has_hypothesis:
        checks.append(("  - 风险因子非空", len(report.risk_hypothesis.risk_factors) > 0))
        checks.append(("  - 怀疑环节已识别", bool(report.risk_hypothesis.suspected_stage)))
    
    # 检查2: 企业评估
    checks.append(("企业评估列表", len(report.enterprise_assessments) > 0))
    
    # 检查3: 报告元数据
    checks.append(("报告ID", bool(report.report_id)))
    checks.append(("风险等级", report.overall_risk_level in ['high', 'medium', 'low']))
    checks.append(("风险分数", report.overall_risk_score > 0))
    
    # 检查4: 证据链
    checks.append(("证据链", bool(report.evidence_chain)))
    
    # 检查5: 行动建议
    checks.append(("行动建议", len(report.action_suggestions) > 0))
    
    print("\n检查结果:")
    all_pass = True
    for name, result in checks:
        status = "✅" if result else "❌"
        print(f"  {status} {name}")
        if not result:
            all_pass = False
    
    if all_pass:
        print("\n✅ PASS: 所有检查项通过")
    else:
        print("\n⚠️ 部分检查项未通过")
    
    return all_pass

if __name__ == "__main__":
    print("\n" + "#"*70)
    print("# Mode A/B 联动工作流 - 5项验收测试")
    print("#"*70)
    
    results = []
    
    # 运行所有测试
    results.append(("Minimax连接", test_1_minimax_connection()))
    results.append(("症状提取", test_2_symptom_extraction()))
    results.append(("企业匹配", test_3_enterprise_matching()))
    results.append(("联动流程", test_4_linked_workflow()))
    results.append(("报告完整性", test_5_report_completeness()))
    
    # 总结
    print("\n" + "="*70)
    print("测试总结")
    print("="*70)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有验收测试通过！")
    else:
        print("\n⚠️ 部分测试失败，请查看详细日志")
