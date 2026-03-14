#!/usr/bin/env python3
"""
LLM 增强症状提取器
使用 Minimax M2.5 将自然语言症状描述转换为标准症状词
"""

import os
import json
import logging
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
import requests

logger = logging.getLogger(__name__)


@dataclass
class SymptomExtractionResult:
    """症状提取结果"""
    original_query: str
    standardized_symptoms: list[str]
    raw_symptoms: list[str]  # LLM 识别的原始症状
    confidence: float
    explanation: str
    latency_ms: float


class LLMSymptomExtractor:
    """
    基于 Minimax M2.5 的症状提取器
    将自然语言（如"拉肚子"）转换为标准症状词（如"腹泻"）
    """

    # 标准症状词表（从 risk_taxonomy.yaml 提取）
    # 症状同义词映射 (口语化 -> 标准医学术语)
    SYMPTOM_SYNONYMS = {
        # 消化系统
        "拉肚子": "腹泻",
        "拉稀": "腹泻",
        "泻肚子": "腹泻",
        "水样便": "腹泻",
        "稀便": "腹泻",
        "跑肚": "腹泻",
        "闹肚子": "腹泻",
        "肚子疼": "腹痛",
        "胃疼": "腹痛",
        "肚子痛": "腹痛",
        "胃绞痛": "腹痛",
        "想吐": "恶心",
        "反胃": "恶心",
        "作呕": "恶心",
        "吐": "呕吐",
        "呕": "呕吐",
        "反酸": "呕吐",
        "不消化": "消化不良",
        "胃胀": "腹胀",
        "胀气": "腹胀",
        "打嗝": "嗳气",
        "便秘": "排便困难",
        "拉血": "便血",
        "血便": "便血",
        "黑便": "消化道出血",
        "拉血": "消化道出血",

        # 发热相关
        "发烧": "发热",
        "高烧": "发热",
        "低烧": "发热",
        "烧": "发热",
        "发烫": "发热",
        "体温高": "发热",
        "寒战": "发热",
        "打摆子": "发热",
        "发冷": "发热",

        # 神经系统
        "头疼": "头痛",
        "头昏": "头晕",
        "眩晕": "头晕",
        "晕": "头晕",
        "迷糊": "头晕",
        "昏沉": "头晕",
        "没劲": "乏力",
        "无力": "乏力",
        "没力气": "乏力",
        "疲倦": "乏力",
        "累": "乏力",
        "犯困": "乏力",
        "嗜睡": "乏力",
        "没精神": "乏力",
        "浑身疼": "肌肉酸痛",
        "酸痛": "肌肉酸痛",
        "抽筋": "肌肉痉挛",

        # 皮肤反应
        "起疹子": "皮疹",
        "红疹": "皮疹",
        "疙瘩": "皮疹",
        "风团": "皮疹",
        "荨麻疹": "皮疹",
        "痒": "瘙痒",
        "发红": "皮肤潮红",
        "红肿": "局部红肿",
        "肿胀": "水肿",

        # 呼吸系统
        "喘不过气": "呼吸困难",
        "气短": "呼吸困难",
        "喘": "呼吸困难",
        "呼吸急促": "呼吸困难",
        "咳嗽": "咳嗽",
        "咳": "咳嗽",
        "嗓子疼": "咽痛",
        "喉咙痛": "咽痛",
        "嗓子干": "口干",

        # 全身症状
        "出虚汗": "盗汗",
        "冷汗": "盗汗",
        "冒汗": "出汗",
        "心慌": "心悸",
        "心跳快": "心悸",
        "胸闷": "胸痛",
        "憋气": "呼吸困难",
        "发紫": "发绀",
        "青紫": "发绀",
        "嘴紫": "发绀",

        # 脱水相关
        "口渴": "口干",
        "嘴干": "口干",
        "尿少": "尿量减少",
        "没尿": "无尿",
        "眼窝凹": "脱水",
        "皮肤干": "皮肤干燥",

        # 严重症状
        "抽风": "抽搐",
        "惊厥": "抽搐",
        "昏迷": "意识障碍",
        "不省人事": "意识障碍",
        "休克": "循环衰竭",
        "血压低": "血压下降",
        "手脚冰凉": "四肢冰冷",

        # 婴幼儿特定
        "哭闹": "烦躁",
        "不吃奶": "拒食",
        "不喝": "拒食",
        "不睡觉": "睡眠障碍",
        "体重不长": "发育迟缓",
        "不长个": "发育迟缓",
    }

    STANDARD_SYMPTOMS = [
        "中毒", "人畜共患感染", "伤口感染", "先天畸形", "免疫抑制", "免疫毒性",
        "免疫调节", "全身性感染", "关节痛", "内伤", "内分泌干扰", "内分泌紊乱",
        "再生障碍性贫血", "出血", "出血性结肠炎", "动物健康受损", "动物疾病",
        "十二指肠炎", "发热", "发绀", "发育异常", "发育毒性", "发育迟缓",
        "口腔撕裂", "呕吐", "呕吐综合征", "呼吸困难", "呼吸衰竭", "唇腭裂",
        "器官损伤", "坏死性小肠结肠炎", "头晕", "头痛", "失聪", "婴儿肉毒中毒",
        "宫内发育迟缓", "寄生虫感染", "寒战", "小肠结肠炎", "尿道炎", "局部感染",
        "尿布疹", "恶心", "感染", "感染扩大", "感染性休克", "感染性疾病",
        "慢性中毒", "急性中毒", "急性出血性胃肠炎", "急性胃肠炎", "急性感染",
        "感冒样症状", "成神经细胞瘤", "慢性感染", "抑郁", "颤抖", "操纵基因",
        "染色体畸变", "流产", "淋巴细胞减少", "消化不良", "消化道出血",
        "消化道症状", "淋巴结肿大", "淋巴结病", "淋巴结炎", "溃疡", "溃疡性结肠炎",
        "溶血", "溶血性贫血", "溶血性尿毒综合征", "疼痛", "痢疾", "病毒性胃肠炎",
        "瘙痒", "瘫痪", "皮疹", "白血病", "眼痛", "眼部刺激", "眼部感染",
        "眼炎症", "睾丸萎缩", "神经症状", "神经系统症状", "神经毒性", "神经管缺陷",
        "神经病变", "穿孔", "红细胞溶解", "细胞毒性", "细菌感染", "脱发",
        "肝肾损伤", "肝毒性", "肝脏损伤", "肝炎", "肝脾肿大", "肠炎", "肠道损伤",
        "肠穿孔", "肾功能损伤", "肾功能衰竭", "肾小管损伤", "肾结石", "肾毒性",
        "肾脏损伤", "肾脏疾病", "胸痛", "脑膜炎", "脱水", "腹泻", "腹腔积液",
        "腹膜炎", "腹痛", "腹胀", "膀胱炎", "便血", "萎缩", "虚弱", "血小板减少",
        "血症", "血栓形成", "表皮剥脱", "视力模糊", "视力损伤", "视力障碍",
        "视野缺损", "角膜炎", "角膜溃疡", "败血症", "贫血", "过敏", "过敏反应",
        "过敏性休克", "身体乏力", "身体不适", "身体不适感", "免疫力下降",
        "胃肠道症状", "胃肠炎", "胃痉挛", "胃炎", "胃黏膜损伤", "胃黏膜炎症",
        "胃黏膜糜烂", "胃黏膜病变", "胆道疾病", "胎儿宫内发育迟缓", "胎儿畸形",
        "胎停", "胎死腹中", "胸痛", "脐炎", "脑炎", "脑积水", "脑梗死",
        "脑脓肿", "脑膜炎", "脓毒症", "脓肿", "菌血症", "萎缩", "虚弱",
        "血小板减少性紫癜", "血小板减少", "血便", "血压下降", "血糖异常",
        "血红蛋白尿", "血尿", "血红蛋白减少", "血液系统异常", "血钙降低",
        "行为改变", "认知障碍", "记忆障碍", "言语困难", "乏力", "体重减轻",
        "体重下降", "体重增加", "体重异常", "体重波动", "体重控制困难"
    ]

    def __init__(self, api_key: Optional[str] = None, model: str = "MiniMax-M2.5"):
        """
        初始化提取器

        Args:
            api_key: Minimax API Key，如果为None则从环境变量读取
            model: 模型名称，默认 MiniMax-M2.5
        """
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.model = "MiniMax-M2.5"
        self.base_url = "https://api.minimax.chat/v1/chat/completions"

    def is_configured(self) -> bool:
        """检查是否配置了 API Key"""
        return bool(self.api_key)

    def extract_symptoms(self, query: str, timeout: int = 30) -> SymptomExtractionResult:
        """
        从自然语言描述中提取标准症状词

        Args:
            query: 用户的症状描述（如"我拉肚子还发烧"）
            timeout: API 调用超时时间（秒）

        Returns:
            SymptomExtractionResult: 提取结果
        """
        if not self.is_configured():
            logger.warning("Minimax API not configured, falling back to keyword matching")
            return SymptomExtractionResult(
                original_query=query,
                standardized_symptoms=[],
                raw_symptoms=[],
                confidence=0.0,
                explanation="API not configured",
                latency_ms=0.0
            )

        start_time = datetime.now()

        # 构建提示词
        prompt = self._build_extraction_prompt(query)

        # 调用 API
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是一个专业的医学症状提取助手。你的任务是将用户的自然语言症状描述转换为标准化的医学症状术语。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 500,
            "response_format": {"type": "json_object"}
        }

        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()

            data = response.json()
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000

            # 解析响应
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # 清理响应内容（去除 think 标签和 markdown 代码块）
            cleaned_content = self._clean_llm_response(content)

            # 尝试解析 JSON
            try:
                result_json = json.loads(cleaned_content)
            except json.JSONDecodeError:
                # 如果不是 JSON，尝试提取症状词
                result_json = self._parse_non_json_response(cleaned_content)

            standardized = result_json.get("standardized_symptoms", [])
            raw = result_json.get("raw_symptoms", [])
            confidence = result_json.get("confidence", 0.8)
            explanation = result_json.get("explanation", "")

            # 验证症状词是否在标准列表中
            validated_symptoms = [
                s for s in standardized
                if s in self.STANDARD_SYMPTOMS
            ]

            # 如果有未匹配的词，记录日志
            unmatched = [s for s in standardized if s not in self.STANDARD_SYMPTOMS]
            if unmatched:
                logger.info(f"Unmatched symptoms (will use fuzzy matching): {unmatched}")
                # 对于未匹配的词，保留它们（可能是新的有效症状）
                validated_symptoms.extend(unmatched)

            return SymptomExtractionResult(
                original_query=query,
                standardized_symptoms=validated_symptoms,
                raw_symptoms=raw,
                confidence=confidence,
                explanation=explanation,
                latency_ms=latency_ms
            )

        except requests.exceptions.Timeout:
            logger.error("Symptom extraction API timeout")
            return SymptomExtractionResult(
                original_query=query,
                standardized_symptoms=[],
                raw_symptoms=[],
                confidence=0.0,
                explanation="API timeout",
                latency_ms=timeout * 1000
            )
        except Exception as e:
            logger.error(f"Symptom extraction failed: {e}")
            return SymptomExtractionResult(
                original_query=query,
                standardized_symptoms=[],
                raw_symptoms=[],
                confidence=0.0,
                explanation=f"Error: {str(e)}",
                latency_ms=0.0
            )

    def _build_extraction_prompt(self, query: str) -> str:
        """构建症状提取提示词"""
        symptoms_list = "、".join(self.STANDARD_SYMPTOMS[:50])  # 只显示前50个作为示例

        # 构建同义词示例
        synonym_examples = []
        for colloquial, standard in list(self.SYMPTOM_SYNONYMS.items())[:15]:
            synonym_examples.append(f'  "{colloquial}" → "{standard}"')

        prompt = f"""你是一个专业的医学症状标准化助手。请将用户的口语化症状描述转换为标准医学症状词。

【用户描述】
"{query}"

【标准症状词表】（共170个，部分示例）
{symptoms_list}
...

【同义词映射示例】
{chr(10).join(synonym_examples)}
...

【任务要求】
1. 从用户描述中提取所有症状
2. **必须将口语化症状映射为标准症状词**（如"拉肚子"必须映射为"腹泻"）
3. standardized_symptoms 字段必须包含标准症状词（从标准词表中选择）
4. raw_symptoms 字段保留原始识别的症状
5. 只返回在标准词表中存在的症状词
6. 如果没有匹配的症状，返回空数组

【重要】
- "拉肚子" 必须输出 "腹泻"
- "发烧" 必须输出 "发热"
- "肚子疼" 必须输出 "腹痛"
- "想吐" 必须输出 "恶心"
- "没劲" 必须输出 "乏力"

输出格式：
{{
    "raw_symptoms": ["用户原始描述中的症状"],
    "standardized_symptoms": ["标准症状词1", "标准症状词2"],
    "confidence": 0.95,
    "explanation": "映射说明"
}}

只输出 JSON，不要其他内容。"""

        return prompt

    def _clean_llm_response(self, content: str) -> str:
        """清理 LLM 响应，去除 think 标签和 markdown 代码块"""
        import re

        # 去除 <think>...</think> 标签
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)

        # 去除 markdown 代码块标记
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*', '', content)

        # 去除多余空白
        content = content.strip()

        return content

    def _parse_non_json_response(self, content: str) -> dict:
        """解析非 JSON 格式的响应"""
        # 尝试从文本中提取症状词
        import re

        # 查找方括号中的内容
        bracket_match = re.search(r'\[(.*?)\]', content)
        if bracket_match:
            items_text = bracket_match.group(1)
            # 分割并清理
            items = [item.strip().strip('"').strip("'") for item in items_text.split(",")]
            return {
                "standardized_symptoms": items,
                "raw_symptoms": items,
                "confidence": 0.7,
                "explanation": "Parsed from text"
            }

        return {
            "standardized_symptoms": [],
            "raw_symptoms": [],
            "confidence": 0.0,
            "explanation": "Failed to parse"
        }


# 单例模式
_extractor_instance: Optional[LLMSymptomExtractor] = None


def get_symptom_extractor() -> LLMSymptomExtractor:
    """获取症状提取器实例（单例）"""
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = LLMSymptomExtractor()
    return _extractor_instance
