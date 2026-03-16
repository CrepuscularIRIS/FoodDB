# Mode A/B 联动工作流 - 5个可执行验收命令

## 命令1: 验证 Minimax M2.5 真实连接（非Mock）
```bash
python -c "
from dotenv import load_dotenv
load_dotenv('.env')
from agent.llm_client import get_llm_client
client = get_llm_client()
print(f'Client: {client.__class__.__name__}')
print(f'Model: {client.config.model}')
print(f'Configured: {client.is_configured()}')
print('✅ REAL' if 'MinimaxLLMClient' in str(type(client)) else '❌ MOCK')
"
```

## 命令2: 验证 Mode B 自然语言症状提取
```bash
cd /home/yarizakurahime/data/dairy_supply_chain_risk && python -c "
from dotenv import load_dotenv
load_dotenv('.env')
from agent.symptom_extractor import get_symptom_extractor
extractor = get_symptom_extractor()
result = extractor.extract_symptoms('我拉肚子还发烧')
print(f'Input: 我拉肚子还发烧')
print(f'Raw: {result.raw_symptoms}')
print(f'Standardized: {result.standardized_symptoms}')
print(f'Latency: {result.latency_ms:.0f}ms')
print('✅ PASS' if result.latency_ms > 1000 else '❌ MOCK MODE')
"
```

## 命令3: 验证 Mode B → 企业候选匹配（非0家）
```bash
cd /home/yarizakurahime/data/dairy_supply_chain_risk && python -c "
from agent.retriever import DataRetriever
from agent.enterprise_matcher import EnterpriseMatcher
retriever = DataRetriever()
matcher = EnterpriseMatcher(retriever)
candidates = matcher.match(
    risk_factors=['腹泻', '发热'],
    suspected_stage='生产加工',
    top_k=5
)
print(f'Matched: {len(candidates)} enterprises')
for c in candidates[:3]:
    print(f'  - {c.enterprise_name}: {c.score:.0f}/100')
print('✅ PASS' if len(candidates) > 0 else '❌ ZERO CANDIDATES')
"
```

## 命令4: 验证完整联动工作流（症状 → 报告）
```bash
cd /home/yarizakurahime/data/dairy_supply_chain_risk && python -c "
from dotenv import load_dotenv
load_dotenv('.env')
from agent.orchestrator import Orchestrator
orch = Orchestrator()
report = orch.run_linked_workflow(
    symptom_description='腹泻、发热、腹痛',
    population={'age_group': 'infant', 'case_count': 3}
)
print(f'Report ID: {report.report_id}')
print(f'Risk Factors: {len(report.risk_hypothesis.risk_factors) if report.risk_hypothesis else 0}')
print(f'Enterprises: {len(report.enterprise_assessments)}')
print(f'Overall Risk: {report.overall_risk_level} ({report.overall_risk_score:.1f})')
print('✅ PASS' if len(report.enterprise_assessments) > 0 else '❌ NO ENTERPRISES')
"
```

## 命令5: 验证报告数据完整性（6个Tab）
```bash
cd /home/yarizakurahime/data/dairy_supply_chain_risk && python -c "
from dotenv import load_dotenv
load_dotenv('.env')
from agent.orchestrator import Orchestrator
orch = Orchestrator()
report = orch.run_linked_workflow('腹泻、发热')
checks = [
    ('Report ID', bool(report.report_id)),
    ('Risk Hypothesis', report.risk_hypothesis is not None),
    ('Risk Factors', len(report.risk_hypothesis.risk_factors) > 0 if report.risk_hypothesis else False),
    ('Enterprises', len(report.enterprise_assessments) > 0),
    ('Evidence Chain', bool(report.evidence_chain)),
    ('Action Suggestions', len(report.action_suggestions) > 0),
]
for name, ok in checks:
    print(f'{\"✅\" if ok else \"❌\"} {name}')
print(f'\nAll Passed: {all(c[1] for c in checks)}')
"
```
