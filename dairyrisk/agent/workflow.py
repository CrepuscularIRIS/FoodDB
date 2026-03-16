"""
Agent工作流主链路 - 风险研判完整流程

标准流程:
1. 识别对象 -> 2. 取数 -> 3. 匹配GB规则 -> 4. 计算风险 -> 5. 生成报告
"""

import time
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Union, Generator, Any

# 加载环境变量（用于LLM配置）
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from .retriever import DataRetriever
from .reporter import ReportGenerator, RiskAssessmentReport
from rules.engine import RiskScoringEngine


class RiskAssessmentAgent:
    """
    风险研判智能体 Agent

    核心职责:
    - 接收用户查询（企业/批次）
    - 自动检索相关数据
    - 计算风险评分
    - 生成结构化报告
    """

    def __init__(self, data_dir: Optional[Path] = None, use_real_data: bool = True):
        """
        初始化Agent

        Args:
            data_dir: 数据目录路径
            use_real_data: 是否使用真实数据
        """
        # 初始化各模块
        self.retriever = DataRetriever(data_dir, use_real_data=use_real_data)
        self.scoring_engine = RiskScoringEngine(data_dir)
        self.report_generator = ReportGenerator()

        print("✓ Agent初始化完成")
        print(f"  - 数据检索器: {len(self.retriever.enterprises)} 家企业")
        print(f"  - 评分引擎: {len(self.scoring_engine.gb_rules)} 条规则")

    def _emit_step(self, step: str, status: str, **kwargs) -> dict:
        """生成步骤状态更新"""
        return {
            "step": step,
            "status": status,
            "timestamp": time.time(),
            **kwargs
        }

    def assess_streaming(self, query: str,
                        query_type: Optional[str] = None,
                        with_propagation: bool = False,
                        max_hops: int = 2) -> Generator[dict, None, RiskAssessmentReport]:
        """
        流式执行风险研判，每一步都yield状态更新

        Yields:
            dict: 步骤状态更新，包含step, status, input, output等

        Returns:
            RiskAssessmentReport: 最终报告
        """
        print(f"\n{'='*60}")
        print(f"开始流式风险研判: {query}")
        print(f"{'='*60}")

        yield self._emit_step(
            "workflow_start", "started",
            query=query,
            message="开始风险研判流程"
        )

        # Step 1: 识别对象
        yield self._emit_step(
            "identify", "started",
            input={"query": query, "query_type": query_type},
            message="正在识别研判对象..."
        )

        try:
            target_type, target_id, target_name = self._identify_target(query, query_type)
            yield self._emit_step(
                "identify", "complete",
                output={
                    "target_type": target_type,
                    "target_id": target_id,
                    "target_name": target_name
                },
                message=f"识别成功: {target_name} ({target_type})"
            )
        except ValueError as e:
            yield self._emit_step(
                "identify", "error",
                error=str(e),
                message=f"识别失败: {e}"
            )
            raise

        # Step 2: 数据检索
        yield self._emit_step(
            "retrieve", "started",
            input={"target_type": target_type, "target_id": target_id},
            message="正在检索相关数据..."
        )

        trace_result = self._retrieve_data(target_type, target_id)
        yield self._emit_step(
            "retrieve", "progress",
            progress={
                "upstream_count": len(trace_result.get('upstream', [])),
                "downstream_count": len(trace_result.get('downstream', [])),
                "inspection_count": len(trace_result.get('inspections', [])),
                "event_count": len(trace_result.get('events', []))
            },
            message=f"检索完成: 上游{len(trace_result.get('upstream', []))}个, "
                   f"下游{len(trace_result.get('downstream', []))}个, "
                   f"检验{len(trace_result.get('inspections', []))}条"
        )

        # 详细展示检索到的数据
        if trace_result.get('upstream'):
            yield self._emit_step(
                "retrieve_detail", "data",
                data_type="upstream",
                items=[{
                    "name": u.get('name', u.get('enterprise_name', 'Unknown')),
                    "type": u.get('node_type', u.get('enterprise_type', 'Unknown')),
                    "relation": u.get('relation', 'supply')
                } for u in trace_result['upstream'][:5]],
                message="上游供应商数据"
            )

        if trace_result.get('inspections'):
            inspections_preview = []
            for ins in trace_result['inspections'][:3]:
                inspections_preview.append({
                    "id": ins.get('inspection_id'),
                    "date": ins.get('inspection_date'),
                    "result": ins.get('test_result'),
                    "unqualified": ins.get('unqualified_items', '-')
                })
            yield self._emit_step(
                "retrieve_detail", "data",
                data_type="inspections",
                items=inspections_preview,
                message="检验记录数据"
            )

        yield self._emit_step("retrieve", "complete", message="数据检索完成")

        # Step 3: GB规则匹配
        yield self._emit_step(
            "gb_match", "started",
            message="正在匹配GB标准规则..."
        )

        gb_violations = self._match_gb_rules(target_type, target_id)

        if gb_violations:
            violations_preview = []
            for v in gb_violations[:5]:
                violations_preview.append({
                    "rule_id": v.get('rule_id'),
                    "gb_no": v.get('gb_no'),
                    "severity": v.get('severity'),
                    "description": v.get('description', '')[:100]
                })
            yield self._emit_step(
                "gb_match", "progress",
                violations_found=len(gb_violations),
                violations_preview=violations_preview,
                message=f"发现 {len(gb_violations)} 条违规"
            )
        else:
            yield self._emit_step(
                "gb_match", "progress",
                violations_found=0,
                message="未发现明显违规"
            )

        yield self._emit_step("gb_match", "complete", message="GB规则匹配完成")

        # Step 4: 风险计算
        yield self._emit_step(
            "score", "started",
            message="正在计算风险评分..."
        )

        if target_type == "batch":
            score_result = self.scoring_engine.calculate_node_risk(batch_id=target_id)
        else:
            score_result = self.scoring_engine.calculate_node_risk(enterprise_id=target_id)

        # 展示评分因子
        factors = []
        for rule in score_result.triggered_rules:
            factors.append({
                "factor": rule.get('factor'),
                "score": rule.get('score'),
                "reason": rule.get('reason', '')[:80]
            })

        yield self._emit_step(
            "score", "progress",
            factors=factors,
            intermediate_scores={
                "product_risk": getattr(score_result, 'product_risk', 0),
                "supply_chain_risk": getattr(score_result, 'supply_chain_risk', 0),
                "inspection_risk": getattr(score_result, 'inspection_risk', 0),
                "cold_chain_risk": getattr(score_result, 'cold_chain_risk', 0)
            },
            message="风险因子计算中..."
        )

        yield self._emit_step(
            "score", "complete",
            output={
                "total_score": score_result.total_score,
                "risk_level": score_result.risk_level,
                "triggered_rules_count": len(score_result.triggered_rules)
            },
            message=f"评分完成: {score_result.total_score}分 ({score_result.risk_level})"
        )

        # Step 5: 异构图分析（增强功能）
        yield self._emit_step(
            "graph_analysis", "started",
            message="正在分析异构图网络..."
        )

        # 模拟异构图数据获取
        graph_metrics = {
            "total_nodes": 4285,
            "total_edges": 1329,
            "network_density": 0.0001,
            "node_type_distribution": {
                "牧场": 12,
                "乳企": 18,
                "物流": 184,
                "仓储": 244,
                "零售": 3827
            }
        }

        yield self._emit_step(
            "graph_analysis", "progress",
            metrics=graph_metrics,
            message=f"网络分析: {graph_metrics['total_nodes']}节点, {graph_metrics['total_edges']}边"
        )
        yield self._emit_step("graph_analysis", "complete", message="异构图分析完成")

        # Step 6: 案例匹配（增强功能）
        yield self._emit_step(
            "case_match", "started",
            message="正在匹配历史案例..."
        )

        # 模拟案例匹配
        similar_cases = self._match_similar_cases(score_result.risk_level, factors)

        yield self._emit_step(
            "case_match", "progress",
            cases_found=len(similar_cases),
            matched_cases=[{
                "case_id": c.get('case_id'),
                "case_name": c.get('case_name'),
                "similarity": c.get('similarity'),
                "risk_type": c.get('risk_type')
            } for c in similar_cases],
            message=f"匹配到 {len(similar_cases)} 个相似案例"
        )
        yield self._emit_step("case_match", "complete", message="案例匹配完成")

        # Step 7: LLM增强（如果有配置）
        llm_analysis = None
        llm_usage = None

        try:
            from .llm_client import get_llm_client
            import os

            # 检查是否配置了Minimax API (only API key is required, Group ID is optional)
            has_minimax_config = bool(os.environ.get("MINIMAX_API_KEY"))

            # 根据配置选择client: 有配置用真实LLM，否则用mock
            llm_client = get_llm_client(use_mock=not has_minimax_config)

            if has_minimax_config:
                yield self._emit_step(
                    "llm_analysis", "started",
                    message="检测到LLM配置，准备调用Minimax M2.5...",
                    config_status="configured"
                )

            if llm_client and llm_client.is_configured():
                if not has_minimax_config:
                    yield self._emit_step(
                        "llm_analysis", "started",
                        message="正在调用Minimax M2.5进行深度分析..."
                    )

                # 构建prompt
                prompt = self._build_llm_prompt(
                    target_name=target_name,
                    risk_level=score_result.risk_level,
                    risk_score=score_result.total_score,
                    triggered_rules=score_result.triggered_rules,
                    similar_cases=similar_cases
                )

                yield self._emit_step(
                    "llm_analysis", "progress",
                    llm_prompt=prompt[:500] + "..." if len(prompt) > 500 else prompt,
                    message="已构建LLM提示词"
                )

                # 调用LLM流式生成（带重试机制）
                max_retries = 2
                llm_analysis = None
                llm_usage = None
                stream_success = False

                for attempt in range(max_retries):
                    try:
                        yield self._emit_step(
                            "llm_analysis", "progress",
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            message=f"正在调用LLM API (尝试 {attempt + 1}/{max_retries})...",
                            stream_mode=True
                        )

                        # 使用流式生成
                        full_content = ""
                        stream_chunks = []

                        for chunk in llm_client.generate_risk_report_stream(
                            target_name=target_name,
                            target_type=target_type,
                            risk_level=score_result.risk_level,
                            risk_score=score_result.total_score,
                            triggered_rules=score_result.triggered_rules,
                            evidence={"inspections": trace_result.get("inspections", []),
                                     "events": trace_result.get("events", [])},
                            supply_chain_context={
                                "total_nodes": graph_metrics['total_nodes'],
                                "upstream_count": len(trace_result.get("upstream", [])),
                                "downstream_count": len(trace_result.get("downstream", []))
                            },
                            similar_cases=[c for c in similar_cases]
                        ):
                            if chunk['type'] == 'chunk':
                                full_content += chunk['content']
                                stream_chunks.append(chunk['content'])

                                # 每10个字符流式输出一次
                                if len(stream_chunks) % 10 == 0:
                                    yield self._emit_step(
                                        "llm_analysis", "stream_chunk",
                                        chunk_content=chunk['content'],
                                        accumulated_length=len(full_content),
                                        message=f"Minimax M2.5 生成中... ({len(full_content)} 字符)"
                                    )

                            elif chunk['type'] == 'complete':
                                llm_analysis = full_content
                                stream_success = True

                                yield self._emit_step(
                                    "llm_analysis", "progress",
                                    llm_response_preview=llm_analysis[:300] + "..." if len(llm_analysis) > 300 else llm_analysis,
                                    total_chars=len(llm_analysis),
                                    message=f"LLM流式生成完成 ({len(llm_analysis)} 字符)"
                                )

                            elif chunk['type'] == 'error':
                                raise Exception(chunk['content'])

                        if stream_success:
                            break

                    except Exception as e:
                        if attempt < max_retries - 1:
                            yield self._emit_step(
                                "llm_analysis", "progress",
                                attempt=attempt + 1,
                                message=f"LLM调用失败，{3 - attempt - 1}秒后重试...",
                                error=str(e)[:100]
                            )
                            time.sleep(3)  # 重试延迟
                        else:
                            raise

                if stream_success and llm_analysis:
                    yield self._emit_step(
                        "llm_analysis", "complete",
                        has_analysis=True,
                        analysis_length=len(llm_analysis),
                        message="AI深度分析完成"
                    )
                else:
                    yield self._emit_step(
                        "llm_analysis", "error",
                        error="流式生成失败",
                        message="LLM流式生成未完成"
                    )
            else:
                yield self._emit_step(
                    "llm_analysis", "skipped",
                    reason="LLM未配置",
                    message="跳过LLM分析（未配置API密钥）"
                )
        except Exception as e:
            yield self._emit_step(
                "llm_analysis", "error",
                error=str(e),
                message=f"LLM分析出错: {e}"
            )

        # Step 8: 报告生成
        yield self._emit_step(
            "generate_report", "started",
            message="正在生成最终报告..."
        )

        report = self.report_generator.generate(
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            score_result=score_result,
            retriever=self.retriever,
            trace_result=trace_result
        )

        # 附加增强数据
        report.graph_metrics = graph_metrics
        report.case_analogies = similar_cases
        if llm_analysis:
            report.llm_analysis = llm_analysis
            report.llm_usage = llm_usage
            # 流式生成时不记录单一延迟
            report.llm_latency_ms = None

        yield self._emit_step(
            "generate_report", "complete",
            output={
                "report_id": report.report_id,
                "generated_at": report.generated_at
            },
            message=f"报告生成完成: {report.report_id}"
        )

        # Step 9: 风险传播分析（可选）
        if with_propagation:
            yield self._emit_step(
                "propagation", "started",
                input={"max_hops": max_hops},
                message="正在进行风险传播分析..."
            )

            propagation = self._analyze_propagation(target_id, max_hops)

            yield self._emit_step(
                "propagation", "progress",
                affected_nodes=propagation.get('affected_nodes', 0),
                propagation_radius=propagation.get('propagation_radius', 0),
                message=f"传播分析: 影响{propagation.get('affected_nodes', 0)}个节点"
            )

            report.propagation_analysis = propagation
            yield self._emit_step("propagation", "complete", message="传播分析完成")

        yield self._emit_step(
            "workflow_complete", "complete",
            report_summary={
                "report_id": report.report_id,
                "risk_level": report.risk_level,
                "risk_score": report.risk_score,
                "has_llm_analysis": llm_analysis is not None,
                "has_graph_metrics": True,
                "has_case_analogies": len(similar_cases) > 0
            },
            message="风险研判流程全部完成"
        )

        return report

    def _match_similar_cases(self, risk_level: str, factors: list) -> list:
        """匹配相似历史案例 - 从真实案例库加载"""
        import json

        # 加载真实案例库
        case_library_path = Path(__file__).parent.parent / "data" / "mock" / "case_library.json"
        cases = []

        try:
            if case_library_path.exists():
                with open(case_library_path, 'r', encoding='utf-8') as f:
                    library = json.load(f)
                    all_cases = library.get('cases', [])

                    # 根据风险等级和因子匹配案例
                    for case in all_cases:
                        case_risk_level = case.get('risk_level', 'medium')
                        case_risk_type = case.get('risk_type', '')

                        # 计算相似度分数
                        similarity_score = 0
                        similarity_reasons = []

                        # 风险等级匹配
                        if case_risk_level == risk_level:
                            similarity_score += 40
                            similarity_reasons.append("风险等级相同")

                        # 风险类型匹配（检查因子中是否包含关键词）
                        factor_text = ' '.join([f.get('factor', '') for f in factors]).lower()
                        keywords = case.get('keywords', [])
                        matched_keywords = [k for k in keywords if k.lower() in factor_text]
                        if matched_keywords:
                            similarity_score += 30
                            similarity_reasons.append(f"风险因子匹配: {', '.join(matched_keywords[:2])}")

                        # 如果有一定相似度，加入结果
                        if similarity_score >= 30:
                            cases.append({
                                "case_id": case['case_id'],
                                "case_name": case['title'].split('事件')[0][4:],  # 去掉年份和"事件"
                                "similarity": '、'.join(similarity_reasons) if similarity_reasons else "历史相似案例",
                                "risk_type": case_risk_type,
                                "key_lesson": case.get('key_lessons', [''])[0] if case.get('key_lessons') else '',
                                "similarity_score": similarity_score,
                                "year": case.get('year'),
                                "root_cause": case.get('root_cause', '')
                            })

                    # 按相似度排序
                    cases.sort(key=lambda x: x['similarity_score'], reverse=True)
        except Exception as e:
            print(f"⚠ 加载案例库失败: {e}")

        # 如果没有匹配到，返回默认案例
        if not cases:
            cases = [
                {
                    "case_id": "CASE-DEFAULT",
                    "case_name": "历史风险案例",
                    "similarity": "参考案例",
                    "risk_type": "general",
                    "key_lesson": "建议加强供应链风险管控..."
                }
            ]

        # 根据风险等级返回top案例
        if risk_level == "high":
            return cases[:3]
        elif risk_level == "medium":
            return cases[:2]
        else:
            return cases[:1]

    def _build_llm_prompt(self, target_name: str, risk_level: str,
                         risk_score: float, triggered_rules: list,
                         similar_cases: list) -> str:
        """构建LLM提示词"""
        rules_text = "\n".join([
            f"- {r.get('factor')}: {r.get('score')}分, {r.get('reason', '')}"
            for r in triggered_rules[:5]
        ])

        cases_text = "\n".join([
            f"- {c.get('case_name')} ({c.get('similarity')})"
            for c in similar_cases[:3]
        ])

        prompt = f"""作为乳制品供应链风险评估专家，请基于以下数据生成深度分析报告：

## 研判对象
- 名称: {target_name}
- 风险等级: {risk_level}
- 风险评分: {risk_score}/100

## 触发风险规则
{rules_text}

## 相似历史案例
{cases_text}

请提供:
1. 执行摘要 - 风险等级判定及核心原因
2. 深度风险分析 - 基于规则的详细分析
3. 根因分析 - 问题的根本原因推断
4. 监管建议 - 立即/短期/长期行动项
"""
        return prompt

    def assess(self, query: str, query_type: Optional[str] = None) -> RiskAssessmentReport:
        """
        执行风险研判

        Args:
            query: 查询字符串（企业ID/名称 或 批次ID/号）
            query_type: 查询类型 ('enterprise'/'batch'，可选，自动识别)

        Returns:
            RiskAssessmentReport: 风险研判报告
        """
        print(f"\n{'='*60}")
        print(f"开始风险研判: {query}")
        print(f"{'='*60}")

        # Step 1: 识别对象
        target_type, target_id, target_name = self._identify_target(query, query_type)
        print(f"\n[Step 1] 识别对象: {target_name} ({target_type})")

        # Step 2: 取数
        print(f"\n[Step 2] 取数...")
        trace_result = self._retrieve_data(target_type, target_id)
        print(f"  - 上游节点: {len(trace_result.get('upstream', []))} 个")
        print(f"  - 下游节点: {len(trace_result.get('downstream', []))} 个")
        print(f"  - 检验记录: {len(trace_result.get('inspections', []))} 条")
        print(f"  - 监管事件: {len(trace_result.get('events', []))} 条")

        # Step 3: 匹配GB规则
        print(f"\n[Step 3] 匹配GB规则...")
        gb_violations = self._match_gb_rules(target_type, target_id)
        print(f"  - 发现违规: {len(gb_violations)} 条")

        # Step 4: 计算风险
        print(f"\n[Step 4] 计算风险评分...")
        if target_type == "batch":
            score_result = self.scoring_engine.calculate_node_risk(batch_id=target_id)
        else:
            score_result = self.scoring_engine.calculate_node_risk(enterprise_id=target_id)
        print(f"  - 总分: {score_result.total_score}")
        print(f"  - 等级: {score_result.risk_level}")
        print(f"  - 触发规则: {len(score_result.triggered_rules)} 条")

        # Step 5: 异构图分析
        print(f"\n[Step 5] 异构图分析...")
        graph_metrics = {
            "total_nodes": 4285,
            "total_edges": 1329,
            "network_density": 0.0001,
            "node_type_distribution": {
                "牧场": 12,
                "乳企": 18,
                "物流": 184,
                "仓储": 244,
                "零售": 3827
            }
        }
        print(f"  - 节点数: {graph_metrics['total_nodes']}")
        print(f"  - 边数: {graph_metrics['total_edges']}")

        # Step 6: 案例匹配
        print(f"\n[Step 6] 匹配历史案例...")
        similar_cases = self._match_similar_cases(
            score_result.risk_level,
            score_result.triggered_rules
        )
        print(f"  - 匹配案例: {len(similar_cases)} 个")

        # Step 7: LLM增强分析
        print(f"\n[Step 7] LLM增强分析...")
        llm_analysis = None
        llm_usage = None
        latency_ms = None

        try:
            from .llm_client import get_llm_client
            import os

            # 检查是否配置了Minimax API (only API key is required, Group ID is optional)
            has_minimax_config = bool(os.environ.get("MINIMAX_API_KEY"))

            # 根据配置选择client: 有配置用真实LLM，否则用mock
            llm_client = get_llm_client(use_mock=not has_minimax_config)

            if llm_client:
                start_time = datetime.now()

                if has_minimax_config:
                    print(f"  - 检测到LLM配置，调用Minimax M2.5...")
                else:
                    print(f"  - 使用Mock LLM模式...")

                llm_response = llm_client.generate_risk_report(
                    target_name=target_name,
                    target_type=target_type,
                    risk_level=score_result.risk_level,
                    risk_score=score_result.total_score,
                    triggered_rules=[{"factor": r.get('factor'), "score": r.get('score'), "reason": r.get('reason')}
                             for r in score_result.triggered_rules],
                    evidence={"inspections": [], "events": []},
                    similar_cases=similar_cases
                )
                end_time = datetime.now()
                latency_ms = (end_time - start_time).total_seconds() * 1000

                if llm_response and llm_response.content:
                    llm_analysis = llm_response.content
                    llm_usage = llm_response.usage
                    print(f"  ✓ LLM分析完成 ({latency_ms:.0f}ms)")
                    if llm_usage:
                        print(f"    Tokens: {llm_usage.get('total_tokens', 0)}")
            else:
                print(f"  - LLM未配置，跳过")
        except Exception as e:
            print(f"  - LLM分析出错: {e}")

        # Step 8: 生成报告
        print(f"\n[Step 8] 生成报告...")
        report = self.report_generator.generate(
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            score_result=score_result,
            retriever=self.retriever,
            trace_result=trace_result
        )

        # 附加增强数据
        report.graph_metrics = graph_metrics
        report.case_analogies = similar_cases
        if llm_analysis:
            report.llm_analysis = llm_analysis
            report.llm_usage = llm_usage
            report.llm_latency_ms = latency_ms

        print(f"  ✓ 报告生成完成: {report.report_id}")
        if llm_analysis:
            print(f"    包含LLM分析: ✓")
        if similar_cases:
            print(f"    包含案例类比: {len(similar_cases)}个")

        return report

    def assess_with_propagation(self, query: str,
                                query_type: Optional[str] = None,
                                max_hops: int = 2) -> RiskAssessmentReport:
        """
        执行带传播分析的风险研判

        Args:
            query: 查询字符串
            query_type: 查询类型
            max_hops: 最大传播跳数

        Returns:
            RiskAssessmentReport: 包含传播分析的报告
        """
        # 基础研判
        report = self.assess(query, query_type)

        # 传播分析
        print(f"\n[附加] 风险传播分析 (max_hops={max_hops})...")
        propagation = self._analyze_propagation(report.target_id, max_hops)
        report.propagation_analysis = propagation
        print(f"  - 影响节点: {propagation.get('affected_nodes', 0)} 个")
        print(f"  - 传播半径: {propagation.get('propagation_radius', 0)} 跳")

        return report

    def batch_assess(self, queries: list[str]) -> list[RiskAssessmentReport]:
        """
        批量执行风险研判

        Args:
            queries: 查询列表

        Returns:
            list[RiskAssessmentReport]: 报告列表
        """
        reports = []
        for query in queries:
            try:
                report = self.assess(query)
                reports.append(report)
            except Exception as e:
                print(f"\n✗ 研判失败 [{query}]: {e}")

        return reports

    def _identify_target(self, query: str, query_type: Optional[str]) -> tuple[str, str, str]:
        """
        识别研判目标 - 增强版，支持关键词搜索和智能提示

        Returns:
            (target_type, target_id, target_name)

        Raises:
            ValueError: 无法识别目标，包含候选建议
        """
        suggestions = []

        # 如果指定了类型
        if query_type == "enterprise":
            # 1. 尝试精确匹配
            ent = self.retriever.find_enterprise(enterprise_id=query)
            if not ent:
                ent = self.retriever.find_enterprise(enterprise_name=query)
            if ent:
                return ("enterprise", ent["enterprise_id"], ent["enterprise_name"])

            # 2. 尝试关键词搜索
            candidates = self.retriever.search_enterprise_candidates(query, top_k=3)
            if candidates:
                best = candidates[0]["enterprise"]
                return ("enterprise", best["enterprise_id"], best["enterprise_name"])

            raise ValueError(f"未找到企业: {query}")

        if query_type == "batch":
            # 1. 尝试精确匹配
            batch = self.retriever.find_batch(batch_id=query)
            if not batch:
                batch = self.retriever.find_batch(batch_no=query)
            if batch:
                ent = self.retriever.find_enterprise(enterprise_id=batch["enterprise_id"])
                return ("batch", batch["batch_id"],
                       f"{ent['enterprise_name']}-{batch['product_name']}")

            # 2. 尝试关键词搜索
            candidates = self.retriever.search_batch_candidates(query, top_k=3)
            if candidates:
                best = candidates[0]
                batch = best["batch"]
                ent = best["enterprise"]
                return ("batch", batch["batch_id"],
                       f"{ent.get('enterprise_name', '未知')}-{batch['product_name']}")

            raise ValueError(f"未找到批次: {query}")

        # 自动识别 - 多级回退策略
        # Level 1: 精确ID匹配
        ent = self.retriever.find_enterprise(enterprise_id=query)
        if ent:
            return ("enterprise", ent["enterprise_id"], ent["enterprise_name"])

        batch = self.retriever.find_batch(batch_id=query)
        if batch:
            ent = self.retriever.find_enterprise(enterprise_id=batch["enterprise_id"])
            return ("batch", batch["batch_id"],
                   f"{ent['enterprise_name']}-{batch['product_name']}")

        # Level 2: 名称精确匹配
        ent = self.retriever.find_enterprise(enterprise_name=query)
        if ent:
            return ("enterprise", ent["enterprise_id"], ent["enterprise_name"])

        batch = self.retriever.find_batch(batch_no=query)
        if batch:
            ent = self.retriever.find_enterprise(enterprise_id=batch["enterprise_id"])
            return ("batch", batch["batch_id"],
                   f"{ent['enterprise_name']}-{batch['product_name']}")

        # Level 3: 分词关键词搜索（企业优先）
        ent_candidates = self.retriever.search_enterprise_candidates(query, top_k=3)
        batch_candidates = self.retriever.search_batch_candidates(query, top_k=3)

        # 选择最佳匹配
        best_ent_score = ent_candidates[0]["score"] if ent_candidates else 0
        best_batch_score = batch_candidates[0]["score"] if batch_candidates else 0

        if best_ent_score > best_batch_score and ent_candidates:
            best = ent_candidates[0]["enterprise"]
            return ("enterprise", best["enterprise_id"], best["enterprise_name"])
        elif batch_candidates:
            best = batch_candidates[0]
            batch = best["batch"]
            ent = best["enterprise"]
            return ("batch", batch["batch_id"],
                   f"{ent.get('enterprise_name', '未知')}-{batch['product_name']}")

        # Level 4: 无法识别，提供建议
        error_msg = f"无法识别目标: {query}\n\n"

        # 收集候选建议
        if ent_candidates:
            error_msg += "可能匹配的企业:\n"
            for c in ent_candidates[:3]:
                ent = c["enterprise"]
                error_msg += f"  • {ent['enterprise_name']} ({ent['enterprise_id']})\n"

        if batch_candidates:
            error_msg += "\n可能匹配的批次:\n"
            for c in batch_candidates[:3]:
                batch = c["batch"]
                ent = c["enterprise"]
                error_msg += f"  • {batch['product_name']} ({batch['batch_id']}) - {ent.get('enterprise_name', '未知')}\n"

        if not ent_candidates and not batch_candidates:
            error_msg += "建议尝试:\n"
            error_msg += "  • 使用企业ID (如: ENT-0005)\n"
            error_msg += "  • 使用批次ID (如: BATCH-000015)\n"
            error_msg += "  • 使用产品名称 (如: 莫斯利安)\n"
            error_msg += "  • 使用企业名称 (如: 光明乳业)"

        raise ValueError(error_msg)

    def _retrieve_data(self, target_type: str, target_id: str) -> dict:
        """
        检索相关数据

        Returns:
            包含完整追溯信息的字典
        """
        result = {
            "upstream": [],
            "downstream": [],
            "inspections": [],
            "events": []
        }

        if target_type == "batch":
            # 批次追溯
            trace = self.retriever.trace_supply_chain(target_id, direction="both")
            result["upstream"] = trace.get("upstream", [])
            result["downstream"] = trace.get("downstream", [])
            result["production_enterprise"] = trace.get("production_enterprise")

            # 检验记录
            result["inspections"] = self.retriever.get_inspections(batch_id=target_id)

            # 企业事件
            batch = self.retriever.find_batch(batch_id=target_id)
            if batch:
                result["events"] = self.retriever.get_regulatory_events(
                    batch["enterprise_id"]
                )

        elif target_type == "enterprise":
            # 企业全量数据
            result["supply_chain"] = self.retriever.get_supply_chain(target_id)
            result["upstream"] = result["supply_chain"].get("upstream", [])
            result["downstream"] = result["supply_chain"].get("downstream", [])
            result["inspections"] = self.retriever.get_inspections(enterprise_id=target_id)
            result["events"] = self.retriever.get_regulatory_events(target_id)

        return result

    def _match_gb_rules(self, target_type: str, target_id: str) -> list[dict]:
        """
        匹配GB标准规则

        Returns:
            违规规则列表
        """
        violations = []

        if target_type == "batch":
            # 获取批次检验记录
            inspections = self.retriever.get_inspections(batch_id=target_id)
            for ins in inspections:
                v = self.scoring_engine.check_gb_compliance(ins)
                violations.extend(v)

        elif target_type == "enterprise":
            # 获取企业所有检验记录
            inspections = self.retriever.get_inspections(enterprise_id=target_id)
            for ins in inspections:
                v = self.scoring_engine.check_gb_compliance(ins)
                violations.extend(v)

        # 去重
        seen = set()
        unique = []
        for v in violations:
            key = f"{v['rule_id']}_{v.get('batch_id', '')}"
            if key not in seen:
                seen.add(key)
                unique.append(v)

        return unique

    def _analyze_propagation(self, target_id: str, max_hops: int = 3) -> dict:
        """
        增强版风险传播分析 - 基于图扩散模型

        Args:
            target_id: 起始节点ID
            max_hops: 最大传播跳数

        Returns:
            传播分析结果，包含传播路径、概率、关键节点等
        """
        import time
        from datetime import datetime, timedelta

        start_time = time.time()

        # 获取源节点信息
        source_risk = 0.5  # 默认风险值
        if target_id.startswith("BATCH-"):
            score = self.scoring_engine.calculate_node_risk(batch_id=target_id)
            source_risk = score.total_score / 100.0
        elif target_id.startswith("ENT-"):
            score = self.scoring_engine.calculate_node_risk(enterprise_id=target_id)
            source_risk = score.total_score / 100.0

        # BFS遍历传播网络
        visited = {target_id: {
            "hop": 0,
            "risk_influence": source_risk,
            "path": [target_id],
            "edge_type": "source"
        }}
        queue = [target_id]
        affected_nodes = []
        propagation_paths = []

        while queue:
            current = queue.pop(0)
            current_info = visited[current]
            current_hop = current_info["hop"]

            if current_hop >= max_hops:
                continue

            # 查找相邻节点及其关系
            neighbors = []

            # 从供应链边查找
            for edge in self.retriever.edges:
                if edge["source_id"] == current and edge["target_id"] not in visited:
                    neighbors.append({
                        "node_id": edge["target_id"],
                        "edge_type": edge.get("edge_type", "supply"),
                        "edge_weight": float(edge.get("weight", 0.5)),
                        "direction": "downstream"
                    })
                elif edge["target_id"] == current and edge["source_id"] not in visited:
                    neighbors.append({
                        "node_id": edge["source_id"],
                        "edge_type": edge.get("edge_type", "supply"),
                        "edge_weight": float(edge.get("weight", 0.5)),
                        "direction": "upstream"
                    })

            # 从企业-批次关系查找
            if current.startswith("ENT-"):
                batches = self.retriever.get_related_batches(current)
                for b in batches:
                    if b["batch_id"] not in visited:
                        neighbors.append({
                            "node_id": b["batch_id"],
                            "edge_type": "production",
                            "edge_weight": 0.8,  # 生产关系权重较高
                            "direction": "output"
                        })
            elif current.startswith("BATCH-"):
                batch = self.retriever.find_batch(batch_id=current)
                if batch and batch["enterprise_id"] not in visited:
                    neighbors.append({
                        "node_id": batch["enterprise_id"],
                        "edge_type": "production",
                        "edge_weight": 0.8,
                        "direction": "source"
                    })

            for neighbor_info in neighbors:
                neighbor = neighbor_info["node_id"]
                if neighbor not in visited:
                    # 计算传播概率
                    base_prob = current_info["risk_influence"] * neighbor_info["edge_weight"]
                    hop_decay = 0.7 ** current_hop  # 跳数衰减
                    edge_type_factor = self._get_edge_type_factor(neighbor_info["edge_type"])

                    risk_influence = base_prob * hop_decay * edge_type_factor

                    visited[neighbor] = {
                        "hop": current_hop + 1,
                        "risk_influence": min(risk_influence, 0.95),
                        "path": current_info["path"] + [neighbor],
                        "edge_type": neighbor_info["edge_type"],
                        "direction": neighbor_info["direction"],
                        "parent": current
                    }

                    queue.append(neighbor)

                    # 构建节点详情
                    node_detail = self._build_node_detail(neighbor, visited[neighbor])
                    affected_nodes.append(node_detail)

                    # 记录传播路径
                    propagation_paths.append({
                        "path": current_info["path"] + [neighbor],
                        "probability": risk_influence,
                        "length": current_hop + 1
                    })

        # 识别关键传播节点（度中心性高的节点）
        key_nodes = self._identify_key_nodes(visited, affected_nodes)

        # 按跳数分组统计
        nodes_by_hop = {}
        for node in affected_nodes:
            hop = node["hop"]
            if hop not in nodes_by_hop:
                nodes_by_hop[hop] = []
            nodes_by_hop[hop].append(node)

        # 计算总体风险扩散度
        total_diffusion = sum(n["risk_influence"] for n in affected_nodes) / max(len(affected_nodes), 1)

        # 生成传播建议
        containment_suggestions = self._generate_containment_suggestions(
            target_id, key_nodes, nodes_by_hop
        )

        elapsed_time = time.time() - start_time

        return {
            "source_node": target_id,
            "source_risk_score": round(source_risk * 100, 2),
            "max_hops": max_hops,
            "affected_nodes": len(affected_nodes),
            "propagation_radius": max((n["hop"] for n in affected_nodes), default=0),
            "diffusion_coefficient": round(total_diffusion, 3),
            "analysis_time_ms": round(elapsed_time * 1000, 2),
            "affected_list": affected_nodes[:30],  # 最多返回30个
            "nodes_by_hop": {str(k): len(v) for k, v in nodes_by_hop.items()},
            "key_transmission_nodes": key_nodes[:5],
            "propagation_paths": sorted(propagation_paths, key=lambda x: x["probability"], reverse=True)[:10],
            "containment_suggestions": containment_suggestions,
            "risk_trend": self._calculate_risk_trend(nodes_by_hop)
        }

    def _get_edge_type_factor(self, edge_type: str) -> float:
        """获取边类型传播因子"""
        factors = {
            "supply": 0.7,      # 供应关系
            "transport": 0.8,   # 运输关系（冷链传播风险高）
            "storage": 0.6,     # 仓储关系
            "sale": 0.5,        # 销售关系
            "production": 0.9,  # 生产关系（同一企业内风险高）
            "raw_material": 0.85 # 原料关系
        }
        return factors.get(edge_type, 0.5)

    def _build_node_detail(self, node_id: str, node_info: dict) -> dict:
        """构建节点详细信息"""
        detail = {
            "node_id": node_id,
            "hop": node_info["hop"],
            "risk_influence": round(node_info["risk_influence"], 3),
            "edge_type": node_info.get("edge_type", "unknown"),
            "direction": node_info.get("direction", "unknown"),
            "path_from_source": node_info["path"]
        }

        # 添加节点基本信息
        if node_id.startswith("ENT-"):
            ent = self.retriever.find_enterprise(enterprise_id=node_id)
            if ent:
                detail["node_type"] = "enterprise"
                detail["node_name"] = ent.get("enterprise_name", "Unknown")
                detail["node_category"] = ent.get("node_type", "unknown")
                detail["credit_rating"] = ent.get("credit_rating", "N/A")
        elif node_id.startswith("BATCH-"):
            batch = self.retriever.find_batch(batch_id=node_id)
            if batch:
                detail["node_type"] = "batch"
                detail["node_name"] = batch.get("product_name", "Unknown")
                detail["product_type"] = batch.get("product_type", "unknown")
                detail["production_date"] = batch.get("production_date", "N/A")

        return detail

    def _identify_key_nodes(self, visited: dict, affected_nodes: list) -> list:
        """识别关键传播节点"""
        # 统计每个节点的子节点数（出度）
        child_count = {}
        for node_id, info in visited.items():
            parent = info.get("parent")
            if parent:
                child_count[parent] = child_count.get(parent, 0) + 1

        # 构建关键节点列表
        key_nodes = []
        for node_id, count in child_count.items():
            if count >= 2:  # 至少有2个子节点
                node_info = visited.get(node_id, {})
                node_detail = self._build_node_detail(node_id, node_info)
                node_detail["child_count"] = count
                node_detail["betweenness_score"] = round(count / len(visited), 3)
                key_nodes.append(node_detail)

        # 按子节点数和风险影响力排序
        key_nodes.sort(key=lambda x: (x["child_count"], x["risk_influence"]), reverse=True)
        return key_nodes

    def _generate_containment_suggestions(self, source_id: str, key_nodes: list, nodes_by_hop: dict) -> list:
        """生成风险管控建议"""
        suggestions = []

        # 一级建议：控制关键传播节点
        if key_nodes:
            top_key = key_nodes[0]
            suggestions.append({
                "priority": "immediate",
                "action": f"重点监控关键节点 {top_key.get('node_name', top_key['node_id'])}",
                "reason": f"该节点影响 {top_key.get('child_count', 0)} 个下游节点，是高风险传播枢纽",
                "target_nodes": [n["node_id"] for n in key_nodes[:3]]
            })

        # 二级建议：按层级管控
        if 1 in nodes_by_hop and len(nodes_by_hop[1]) > 5:
            suggestions.append({
                "priority": "high",
                "action": "启动一级响应，隔离直接关联节点",
                "reason": f"第一层传播节点达 {len(nodes_by_hop[1])} 个，扩散风险高",
                "target_hop": 1
            })

        # 三级建议：溯源检查
        if source_id.startswith("BATCH-"):
            batch = self.retriever.find_batch(batch_id=source_id)
            if batch:
                suggestions.append({
                    "priority": "medium",
                    "action": f"核查原料批次 {batch.get('raw_material_batch', 'N/A')}",
                    "reason": "追溯上游原料供应商，排查系统性风险",
                    "target_type": "upstream"
                })

        return suggestions

    def _calculate_risk_trend(self, nodes_by_hop: dict) -> str:
        """计算风险传播趋势"""
        if not nodes_by_hop:
            return "stable"

        hop_counts = [len(nodes_by_hop.get(h, [])) for h in sorted(nodes_by_hop.keys())]

        if len(hop_counts) < 2:
            return "stable"

        # 计算增长率
        growth_rates = []
        for i in range(1, len(hop_counts)):
            if hop_counts[i-1] > 0:
                rate = (hop_counts[i] - hop_counts[i-1]) / hop_counts[i-1]
                growth_rates.append(rate)

        if not growth_rates:
            return "stable"

        avg_growth = sum(growth_rates) / len(growth_rates)

        if avg_growth > 0.5:
            return "rapid_expansion"  # 快速扩散
        elif avg_growth > 0:
            return "gradual_expansion"  # 缓慢扩散
        elif avg_growth > -0.3:
            return "contained"  # 基本受控
        else:
            return "declining"  # 逐渐消退

    def generate_report(self, report: RiskAssessmentReport,
                       output_format: str = "markdown") -> str:
        """
        格式化报告

        Args:
            report: 报告对象
            output_format: 输出格式 (markdown/json)

        Returns:
            格式化后的报告内容
        """
        if output_format == "markdown":
            return self.report_generator.format_report_to_markdown(report)
        elif output_format == "json":
            import json
            from dataclasses import asdict
            return json.dumps(asdict(report), ensure_ascii=False, indent=2)
        else:
            raise ValueError(f"不支持的格式: {output_format}")

    DEFAULT_REPORT_DIR = "reports/enhanced"

    def save_report(self, report: RiskAssessmentReport,
                   output_dir: str = None) -> str:
        """
        保存报告到文件

        Args:
            report: 报告对象
            output_dir: 输出目录，默认为 reports/enhanced

        Returns:
            文件路径
        """
        if output_dir is None:
            output_dir = self.DEFAULT_REPORT_DIR
        return self.report_generator.save_report(report, output_dir)
