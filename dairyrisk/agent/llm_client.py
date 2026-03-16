"""
Minimax M2.5 LLM Client for Risk Assessment Report Generation

This module provides integration with Minimax M2.5 API for intelligent
report generation based on risk assessment data.
"""

import os
import json
import logging
from typing import Optional
from dataclasses import dataclass
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """LLM configuration"""
    api_key: str
    group_id: str
    model: str = "MiniMax-M2.5"
    base_url: str = "https://api.minimax.chat/v1/chat/completions"
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 60


@dataclass
class LLMResponse:
    """Structured LLM response"""
    success: bool
    content: str
    usage: Optional[dict] = None
    error: Optional[str] = None
    latency_ms: Optional[float] = None


class MinimaxLLMClient:
    """
    Minimax M2.5 LLM Client

    Provides intelligent report generation capabilities for
    dairy supply chain risk assessment.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        """
        Initialize the LLM client

        Args:
            config: LLM configuration. If None, loads from environment variables.
        """
        if config is None:
            config = self._load_config_from_env()

        self.config = config
        self.session = requests.Session()

    def _load_config_from_env(self) -> LLMConfig:
        """Load configuration from environment variables"""
        api_key = os.environ.get("MINIMAX_API_KEY", "")
        # Group ID is optional - Minimax API only requires API key (Bearer token)
        group_id = os.environ.get("MINIMAX_GROUP_ID", "")

        if not api_key:
            logger.warning(
                "MINIMAX_API_KEY not set. LLM features will be disabled."
            )

        return LLMConfig(
            api_key=api_key,
            group_id=group_id,
            model=os.environ.get("MINIMAX_MODEL", "abab6.5s-chat"),
            temperature=float(os.environ.get("MINIMAX_TEMPERATURE", "0.3")),
            max_tokens=int(os.environ.get("MINIMAX_MAX_TOKENS", "4096"))
        )

    def is_configured(self) -> bool:
        """Check if the client is properly configured"""
        # Group ID is loaded but not required for API calls (Minimax uses Bearer token with API key only)
        return bool(self.config.api_key)

    def generate_risk_report(
        self,
        target_name: str,
        target_type: str,
        risk_level: str,
        risk_score: float,
        triggered_rules: list,
        evidence: dict,
        supply_chain_context: Optional[dict] = None,
        similar_cases: Optional[list] = None
    ) -> LLMResponse:
        """
        Generate an intelligent risk assessment report using LLM

        Args:
            target_name: Name of the target (batch or enterprise)
            target_type: Type of target ('batch' or 'enterprise')
            risk_level: Risk level ('high', 'medium', 'low')
            risk_score: Numerical risk score (0-100)
            triggered_rules: List of triggered risk rules
            evidence: Dictionary containing inspection records, events, etc.
            supply_chain_context: Optional supply chain graph context
            similar_cases: Optional list of similar historical cases

        Returns:
            LLMResponse with generated report content
        """
        if not self.is_configured():
            return LLMResponse(
                success=False,
                content="",
                error="LLM not configured. Set MINIMAX_API_KEY environment variable."
            )

        # Build the prompt
        prompt = self._build_risk_report_prompt(
            target_name=target_name,
            target_type=target_type,
            risk_level=risk_level,
            risk_score=risk_score,
            triggered_rules=triggered_rules,
            evidence=evidence,
            supply_chain_context=supply_chain_context,
            similar_cases=similar_cases
        )

        return self._call_api(prompt)

    def _build_risk_report_prompt(
        self,
        target_name: str,
        target_type: str,
        risk_level: str,
        risk_score: float,
        triggered_rules: list,
        evidence: dict,
        supply_chain_context: Optional[dict] = None,
        similar_cases: Optional[list] = None
    ) -> list[dict]:
        """Build the prompt for risk report generation with JSON output"""

        # System prompt - defines the expert role and JSON output requirement
        system_prompt = """你是一位资深的乳制品供应链风险评估专家，拥有丰富的食品安全监管经验。

【重要】你必须以JSON格式输出报告，不要输出任何其他文字。JSON格式如下：
{
  "executive_summary": "执行摘要（200字以内）",
  "deep_analysis": "深度风险分析（300-400字）",
  "root_cause": "根因分析（200-300字）",
  "regulatory_basis": ["GB标准引用1", "GB标准引用2"],
  "regulatory_basis_details": [
    {"gb_no": "GB XXXXX", "clause": "条款", "requirement": "要求说明"}
  ],
  "immediate_actions": ["立即行动项1", "立即行动项2"],
  "short_term_actions": ["短期行动项1", "短期行动项2"],
  "long_term_recommendations": ["长期建议1", "长期建议2"],
  "key_risk_factors": ["关键风险因子1", "关键风险因子2"],
  "confidence_assessment": "风险判定置信度说明"
}

报告要求：
1. 只输出JSON，不要markdown代码块标记
2. 使用正式的监管语言和专业术语
3. 引用具体的GB国家标准条款
4. 提供可操作的监管建议
5. 内容要具体、有洞察力"""

        # Build user prompt with structured data
        risk_level_cn = {
            "high": "高风险（红色预警）",
            "medium": "中风险（橙色预警）",
            "low": "低风险（绿色）"
        }.get(risk_level, risk_level)

        triggered_rules_text = "\n".join([
            f"- {rule.get('factor', '未知')}: {rule.get('reason', '')} (风险分: {rule.get('score', 0)})"
            for rule in triggered_rules[:5]
        ])

        inspections = evidence.get("inspections", [])
        inspections_text = "\n".join([
            f"- {ins.get('inspection_id')}: {ins.get('test_result')} ({ins.get('inspection_date')})"
            for ins in inspections[:3]
        ]) if inspections else "无检验记录"

        events = evidence.get("events", [])
        events_text = "\n".join([
            f"- {evt.get('event_id')}: {evt.get('event_type')} - {evt.get('severity')} ({evt.get('event_date')})"
            for evt in events[:3]
        ]) if events else "无监管事件"

        similar_cases_text = ""
        if similar_cases:
            similar_cases_text = "\n\n## 相似历史案例\n\n" + "\n".join([
                f"- {case.get('case_name')}: {case.get('key_lesson')}"
                for case in similar_cases[:3]
            ])

        supply_chain_text = ""
        if supply_chain_context:
            nodes = supply_chain_context.get("nodes", [])
            edges = supply_chain_context.get("edges", [])
            supply_chain_text = f"""\n\n## 供应链网络信息

- 节点数量: {len(nodes)}
- 连接关系: {len(edges)}
- 网络复杂度: {supply_chain_context.get('complexity_score', 'N/A')}"""

        user_prompt = f"""请基于以下风险评估数据生成一份专业的风险研判报告，以JSON格式输出：

## 评估对象信息

- 对象名称: {target_name}
- 对象类型: {"生产批次" if target_type == "batch" else "企业"}
- 风险等级: {risk_level_cn}
- 风险评分: {risk_score}/100

## 触发的风险规则

{triggered_rules_text}

## 相关检验记录

{inspections_text}

## 相关监管事件

{events_text}{supply_chain_text}{similar_cases_text}

## 输出要求

【重要】只输出JSON，不要包含任何解释文字或markdown标记。JSON必须包含以下字段：
- executive_summary: 执行摘要
- deep_analysis: 深度风险分析
- root_cause: 根因分析
- regulatory_basis: GB标准列表（数组）
- regulatory_basis_details: 标准详情（数组对象）
- immediate_actions: 立即行动项（数组）
- short_term_actions: 短期行动项（数组）
- long_term_recommendations: 长期建议（数组）
- key_risk_factors: 关键风险因子（数组）
- confidence_assessment: 置信度评估"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    def _call_api(self, messages: list[dict]) -> LLMResponse:
        """Call Minimax API"""
        start_time = datetime.now()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}"
        }

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens
        }

        try:
            response = self.session.post(
                self.config.base_url,
                headers=headers,
                json=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()

            data = response.json()
            latency = (datetime.now() - start_time).total_seconds() * 1000

            if data.get("choices") and len(data["choices"]) > 0:
                content = data["choices"][0].get("message", {}).get("content", "")
                usage = data.get("usage", {})

                return LLMResponse(
                    success=True,
                    content=content,
                    usage=usage,
                    latency_ms=latency
                )
            else:
                return LLMResponse(
                    success=False,
                    content="",
                    error=f"No content in response: {data}",
                    latency_ms=latency
                )

        except requests.exceptions.Timeout:
            return LLMResponse(
                success=False,
                content="",
                error="API call timed out",
                latency_ms=self.config.timeout * 1000
            )
        except requests.exceptions.RequestException as e:
            return LLMResponse(
                success=False,
                content="",
                error=f"API request failed: {str(e)}",
                latency_ms=(datetime.now() - start_time).total_seconds() * 1000
            )
        except Exception as e:
            return LLMResponse(
                success=False,
                content="",
                error=f"Unexpected error: {str(e)}",
                latency_ms=(datetime.now() - start_time).total_seconds() * 1000
            )

    def generate_risk_report_stream(
        self,
        target_name: str,
        target_type: str,
        risk_level: str,
        risk_score: float,
        triggered_rules: list,
        evidence: dict,
        supply_chain_context: Optional[dict] = None,
        similar_cases: Optional[list] = None
    ):
        """
        Generate an intelligent risk assessment report using LLM with streaming

        Yields:
            dict: Stream chunks with 'type' ('chunk'|'complete'|'error') and 'content'
        """
        if not self.is_configured():
            yield {'type': 'error', 'content': 'LLM not configured. Set MINIMAX_API_KEY environment variable.'}
            return

        # Build the prompt (reuse existing method)
        messages = self._build_risk_report_prompt(
            target_name=target_name,
            target_type=target_type,
            risk_level=risk_level,
            risk_score=risk_score,
            triggered_rules=triggered_rules,
            evidence=evidence,
            supply_chain_context=supply_chain_context,
            similar_cases=similar_cases
        )

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}"
        }

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": True  # Enable streaming
        }

        try:
            response = self.session.post(
                self.config.base_url,
                headers=headers,
                json=payload,
                timeout=self.config.timeout,
                stream=True
            )
            response.raise_for_status()

            full_content = ""

            # Process SSE stream
            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')

                    # Skip empty lines and comments
                    if line_text.startswith('data: '):
                        data_str = line_text[6:]

                        if data_str == '[DONE]':
                            break

                        try:
                            chunk_data = json.loads(data_str)

                            # Extract content from delta
                            choices = chunk_data.get('choices', [])
                            if choices and len(choices) > 0:
                                delta = choices[0].get('delta', {})
                                content_chunk = delta.get('content', '')

                                if content_chunk:
                                    full_content += content_chunk
                                    yield {'type': 'chunk', 'content': content_chunk}

                        except json.JSONDecodeError:
                            continue

            # Yield final complete response
            yield {'type': 'complete', 'content': full_content}

        except requests.exceptions.Timeout:
            yield {'type': 'error', 'content': 'API call timed out'}
        except requests.exceptions.RequestException as e:
            yield {'type': 'error', 'content': f'API request failed: {str(e)}'}
        except Exception as e:
            yield {'type': 'error', 'content': f'Unexpected error: {str(e)}'}


class MockLLMClient:
    """
    Mock LLM client for testing without API credentials
    Returns structured placeholder responses
    """

    def __init__(self):
        self.config = LLMConfig(api_key="mock", group_id="mock")

    def is_configured(self) -> bool:
        return True

    def generate_risk_report(self, **kwargs) -> LLMResponse:
        """Generate mock report for testing - Returns JSON format matching real LLM"""
        import json
        import random

        target_name = kwargs.get("target_name", "Unknown")
        risk_level = kwargs.get("risk_level", "medium")
        triggered_rules = kwargs.get("triggered_rules", [])

        risk_level_cn = {
            "high": "高风险（红色预警）",
            "medium": "中风险（橙色预警）",
            "low": "低风险（绿色）"
        }.get(risk_level, risk_level)

        # Extract rule factors for dynamic content
        rule_factors = [r.get("factor", "") for r in triggered_rules[:3]] if triggered_rules else ["暂无特定风险因子"]
        rule_factors_str = "、".join(rule_factors)

        # Build JSON response matching the real LLM format
        mock_analysis = {
            "executive_summary": f"经综合研判，**{target_name}**的风险等级为**{risk_level_cn}**。主要风险因素包括：{rule_factors_str}。建议立即启动专项抽检程序，重点关注相关风险点。",
            "deep_analysis": f"基于规则引擎的评估结果，该对象在以下维度表现出风险特征：{rule_factors_str}。通过分析历史检验记录和供应链信息，发现该对象存在潜在的质量控制风险。建议监管部门结合企业历史违规记录和供应链网络特征进行进一步深入分析。",
            "root_cause": "风险产生的根本原因可能涉及：生产工艺控制不严格、供应商资质审核机制不完善、质量检验频次不足、冷链运输监控存在盲区等多个环节的系统性问题。建议从管理体系层面进行整改。",
            "regulatory_basis": [
                "GB 19645-2010《巴氏杀菌乳》",
                "GB 25190-2010《灭菌乳》",
                "GB 2760-2014《食品添加剂使用标准》",
                "GB 4789.2《食品安全国家标准 食品微生物学检验》"
            ],
            "regulatory_basis_details": [
                {
                    "gb_no": "GB 19645-2010",
                    "clause": "4.1 感官要求",
                    "requirement": "巴氏杀菌乳应具有乳固有的香味，无异味，呈均匀一致的乳白色或微黄色。"
                },
                {
                    "gb_no": "GB 4789.2",
                    "clause": "菌落总数测定",
                    "requirement": "巴氏杀菌乳菌落总数不得超过10000 CFU/mL。"
                },
                {
                    "gb_no": "GB 2760-2014",
                    "clause": "附录A",
                    "requirement": "食品添加剂的使用应符合标准规定的范围和限量。"
                }
            ],
            "immediate_actions": [
                "启动专项抽检，重点关注微生物指标",
                "核查近3个月检验记录和不合格品处置记录",
                "约谈企业负责人，要求提交情况说明"
            ],
            "short_term_actions": [
                "完成全供应链排查，追溯上游原料来源",
                "提交详细整改报告和质量改进计划",
                "增加自检频次，由每月1次增至每周1次"
            ],
            "long_term_recommendations": [
                "完善质量管理体系，建立HACCP体系",
                "加强供应商审核，建立分级管理机制",
                "引入信息化追溯系统，实现批次全程可追溯",
                "定期开展员工食品安全培训"
            ],
            "key_risk_factors": rule_factors if rule_factors else ["暂无特定风险因子"],
            "confidence_assessment": f"基于现有数据的综合分析，本风险研判的置信度为{random.randint(75, 95)}%。建议结合现场检查结果进一步验证。"
        }

        return LLMResponse(
            success=True,
            content=json.dumps(mock_analysis, ensure_ascii=False),
            usage={"prompt_tokens": 500, "completion_tokens": 800, "total_tokens": 1300},
            latency_ms=random.randint(800, 2000)  # Simulate realistic API latency
        )


def get_llm_client(use_mock: bool = False) -> MinimaxLLMClient | MockLLMClient:
    """
    Factory function to get the appropriate LLM client

    Args:
        use_mock: If True, return mock client regardless of configuration

    Returns:
        Configured LLM client
    """
    if use_mock:
        return MockLLMClient()

    client = MinimaxLLMClient()
    if not client.is_configured():
        logger.warning("Minimax not configured, falling back to mock client")
        return MockLLMClient()

    return client
