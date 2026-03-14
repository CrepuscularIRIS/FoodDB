#!/usr/bin/env python3
"""
症状驱动风险评估模块 (LLM增强版)
整合 standalone_food_risk_kb 的完整知识库能力
实现: 自然语言症状 → LLM提取 → 风险因子 → 供应链环节 → GB依据 → 关联企业
"""

import json
import sys
import re
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict

# 添加 standalone_food_risk_kb 路径
STANDALONE_KB_PATH = Path("/home/yarizakurahime/data/standalone_food_risk_kb")
sys.path.insert(0, str(STANDALONE_KB_PATH))

# 尝试导入知识库路由
try:
    import yaml
    KB_AVAILABLE = True
except ImportError:
    KB_AVAILABLE = False
    print("⚠ yaml 模块不可用")

# 导入 LLM 症状提取器
try:
    from .symptom_extractor import LLMSymptomExtractor, get_symptom_extractor
    LLM_EXTRACTOR_AVAILABLE = True
except ImportError:
    LLM_EXTRACTOR_AVAILABLE = False
    print("⚠ LLM 症状提取器不可用")


@dataclass
class SymptomRiskResult:
    """症状驱动风险评估结果 (LLM增强版)"""
    query: str
    symptoms_detected: list[dict] = field(default_factory=list)
    risk_factors: list[dict] = field(default_factory=list)
    stage_candidates: list[dict] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)
    linked_enterprises: list[dict] = field(default_factory=list)
    gb_references: list[dict] = field(default_factory=list)  # GB标准依据
    risk_level: str = "low"
    confidence: float = 0.0
    suggested_actions: list[str] = field(default_factory=list)
    # LLM 增强字段
    llm_extraction: Optional[dict] = None  # LLM 症状提取结果
    processing_steps: list[dict] = field(default_factory=list)  # 处理步骤日志


class StandaloneKBWrapper:
    """
    包装 standalone_food_risk_kb 的知识库
    直接读取 YAML 配置文件，适配新格式
    """

    def __init__(self):
        self.kb_path = Path("/home/yarizakurahime/data/standalone_food_risk_kb")
        self.config_dir = self.kb_path / "knowledge" / "configs"
        self.corpus_dir = self.kb_path / "knowledge" / "corpora"

        # 加载配置文件
        self.risk_taxonomy = self._load_yaml(self.config_dir / "risk_taxonomy.yaml")
        self.stage_rules = self._load_yaml(self.config_dir / "stage_rules.yaml")
        self.gb_dairy_rules = self._load_yaml(self.config_dir / "gb_dairy_rules.yaml")
        self.gb2762_rules = self._load_yaml(self.config_dir / "gb2762_contaminant_limits.yaml")

        # 加载语料库
        self.standard_corpus = self._load_jsonl(self.corpus_dir / "rag_corpus_standard_txt.jsonl")
        self.management_corpus = self._load_jsonl(self.corpus_dir / "rag_corpus_management_v2.jsonl")

        # 构建索引
        self._build_indices()

        print(f"✓ 知识库加载完成:")
        print(f"  - 风险因子: {len(self.risk_factor_defs)} 个")
        print(f"  - 症状映射: {len(self.symptom_to_risk)} 个症状")
        print(f"  - 生产环节: {len(self.stages_by_id)} 个")
        print(f"  - GB语料: {len(self.standard_corpus)} 条")

    def _load_yaml(self, path: Path) -> Any:
        """加载 YAML 文件"""
        if not path.exists():
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"加载 {path} 失败: {e}")
            return {}

    def _load_jsonl(self, path: Path) -> list[dict]:
        """加载 JSONL 文件"""
        if not path.exists():
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return [json.loads(line) for line in f if line.strip()]
        except Exception as e:
            print(f"加载 {path} 失败: {e}")
            return []

    def _build_indices(self):
        """构建索引"""
        # 风险因子定义
        self.risk_factor_defs = {}
        for rf in self.risk_taxonomy.get("risk_factors", []):
            if rf and "id" in rf:
                self.risk_factor_defs[rf["id"]] = rf

        # 从 risk_factors 构建症状映射
        self.symptom_to_risk = {}
        for rf_id, rf_def in self.risk_factor_defs.items():
            for symptom in rf_def.get("typical_symptoms", []):
                if symptom not in self.symptom_to_risk:
                    self.symptom_to_risk[symptom] = []
                self.symptom_to_risk[symptom].append({
                    "risk_factor": rf_id,
                    "weight": 0.5
                })

        # 生产环节定义
        self.stages_by_id = {}
        for stage in self.stage_rules.get("stages", []):
            if stage and "id" in stage:
                self.stages_by_id[stage["id"]] = stage

        # 风险因子到环节的映射
        self.stage_rules_by_risk = {}
        for rule in self.stage_rules.get("stage_rules", []):
            if rule and "risk_factor" in rule:
                self.stage_rules_by_risk[rule["risk_factor"]] = rule

        # 默认规则
        self.default_stage_rule = self.stage_rules.get("default_rule", {})

    def analyze_query(self, query: str, use_llm: bool = True) -> dict[str, Any]:
        """
        分析查询中的症状关键词 (LLM增强版)

        Args:
            query: 用户输入的症状描述
            use_llm: 是否使用 LLM 进行症状提取

        Returns:
            包含症状、检测项、产品和 LLM 提取结果的字典
        """
        query_lower = query.lower()
        processing_steps = []

        # Step 1: LLM 症状提取 (如果可用且启用)
        llm_symptoms = []
        llm_extraction_result = None

        if use_llm and LLM_EXTRACTOR_AVAILABLE:
            try:
                extractor = get_symptom_extractor()
                if extractor.is_configured():
                    print(f"  [LLM] 正在提取症状: '{query}'")
                    llm_result = extractor.extract_symptoms(query)
                    llm_extraction_result = {
                        "original_query": llm_result.original_query,
                        "standardized_symptoms": llm_result.standardized_symptoms,
                        "raw_symptoms": llm_result.raw_symptoms,
                        "confidence": llm_result.confidence,
                        "explanation": llm_result.explanation,
                        "latency_ms": round(llm_result.latency_ms, 2)
                    }
                    llm_symptoms = llm_result.standardized_symptoms
                    processing_steps.append({
                        "step": "llm_extraction",
                        "status": "completed",
                        "latency_ms": round(llm_result.latency_ms, 2),
                        "extracted": llm_result.standardized_symptoms
                    })
                    print(f"  [LLM] ✓ 提取完成: {llm_symptoms} ({llm_result.latency_ms:.0f}ms)")
                else:
                    processing_steps.append({
                        "step": "llm_extraction",
                        "status": "skipped",
                        "reason": "API not configured"
                    })
            except Exception as e:
                print(f"  [LLM] ✗ 提取失败: {e}")
                processing_steps.append({
                    "step": "llm_extraction",
                    "status": "failed",
                    "error": str(e)
                })

        # Step 2: 同义词映射匹配 (LLM不可用时作为智能后备)
        synonym_symptoms = []
        if LLM_EXTRACTOR_AVAILABLE:
            from .symptom_extractor import LLMSymptomExtractor
            for colloquial, standard in LLMSymptomExtractor.SYMPTOM_SYNONYMS.items():
                if colloquial in query_lower:
                    # 查找标准症状对应的风险因子
                    risk_mappings = self.symptom_to_risk.get(standard, [])
                    if risk_mappings and standard not in {s["term"] for s in synonym_symptoms}:
                        synonym_symptoms.append({
                            "term": standard,
                            "symptom_id": f"symptom_{standard}",
                            "risk_factors": [m["risk_factor"] for m in risk_mappings],
                            "source": "synonym_match",
                            "matched_colloquial": colloquial
                        })
                        print(f"    [同义词] '{colloquial}' → '{standard}'")

        # Step 3: 传统关键词匹配
        keyword_symptoms = []
        for symptom, mappings in self.symptom_to_risk.items():
            if symptom.lower() in query_lower:
                keyword_symptoms.append({
                    "term": symptom,
                    "symptom_id": f"symptom_{symptom}",
                    "risk_factors": [m["risk_factor"] for m in mappings],
                    "source": "keyword_match"
                })

        # Step 4: 合并所有匹配结果 (LLM + 同义词 + 关键词)
        symptom_hits = keyword_symptoms.copy()
        seen_symptoms = {s["term"] for s in symptom_hits}

        # 添加同义词匹配结果
        for s in synonym_symptoms:
            if s["term"] not in seen_symptoms:
                symptom_hits.append(s)
                seen_symptoms.add(s["term"])

        # 添加 LLM 匹配结果
        for symptom in llm_symptoms:
            if symptom not in seen_symptoms:
                risk_mappings = self.symptom_to_risk.get(symptom, [])
                if risk_mappings:  # 只添加知识库中存在的症状
                    symptom_hits.append({
                        "term": symptom,
                        "symptom_id": f"symptom_{symptom}",
                        "risk_factors": [m["risk_factor"] for m in risk_mappings],
                        "source": "llm_extraction"
                    })
                    seen_symptoms.add(symptom)

        processing_steps.append({
            "step": "symptom_merge",
            "status": "completed",
            "keyword_matches": len(keyword_symptoms),
            "synonym_matches": len(synonym_symptoms),
            "llm_matches": len([s for s in symptom_hits if s.get("source") == "llm_extraction"]),
            "total": len(symptom_hits)
        })

        return {
            "symptoms": symptom_hits,
            "test_items": [],
            "products": [],
            "llm_extraction": llm_extraction_result,
            "processing_steps": processing_steps
        }

    def infer_risk_factors(self, query: str, query_signals: dict, top_k: int = 6) -> list[dict]:
        """推断风险因子"""
        scores = defaultdict(float)
        reasons = defaultdict(list)

        # 基于症状推断
        for item in query_signals.get("symptoms", []):
            symptom_id = item.get("symptom_id", "")
            for mapping in self.symptom_to_risk.get(item.get("term", ""), []):
                risk_id = mapping["risk_factor"]
                weight = mapping.get("weight", 0.5)
                scores[risk_id] += weight
                reasons[risk_id].append(f"symptom:{item['term']} weight={weight}")

        # 基于名称直接匹配
        query_lower = query.lower()
        for risk_id, risk_def in self.risk_factor_defs.items():
            name = risk_def.get("name", "")
            if name and name.lower() in query_lower:
                scores[risk_id] += 1.0
                reasons[risk_id].append(f"direct_match:{name}")

            # 检查适用产品
            for product in risk_def.get("applicable_products", []):
                if product and product.lower() in query_lower:
                    scores[risk_id] += 0.3
                    reasons[risk_id].append(f"product:{product}")

        # 排序并返回
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        for risk_id, score in ranked:
            risk_def = self.risk_factor_defs.get(risk_id, {})
            results.append({
                "risk_factor_id": risk_id,
                "score": round(score, 4),
                "name": risk_def.get("name", risk_id),
                "category": risk_def.get("category", "未知"),
                "description": risk_def.get("description", ""),
                "applicable_products": risk_def.get("applicable_products", []),
                "typical_symptoms": risk_def.get("typical_symptoms", []),
                "vulnerable_groups": risk_def.get("vulnerable_groups", []),
                "evidence_strength": risk_def.get("evidence_strength", "medium"),
                "reasons": reasons[risk_id]
            })

        return results

    def infer_stages(self, risk_candidates: list[dict], top_k: int = 5) -> list[dict]:
        """推断相关生产环节"""
        stage_scores = defaultdict(float)
        stage_reasons = defaultdict(list)

        for risk in risk_candidates:
            risk_id = risk.get("risk_factor_id", "")
            base_score = float(risk.get("score", 0))

            # 查找该风险因子的环节规则
            rule = self.stage_rules_by_risk.get(risk_id)
            if rule:
                for cand in rule.get("stage_candidates", []):
                    stage_id = cand.get("stage")
                    probability = float(cand.get("probability", 0.5))
                    if stage_id:
                        stage_scores[stage_id] += base_score * probability
                        stage_reasons[stage_id].append(
                            f"{risk_id} * {probability:.2f}"
                        )
            else:
                # 使用默认规则
                for cand in self.default_stage_rule.get("stage_candidates", []):
                    stage_id = cand.get("stage")
                    probability = float(cand.get("probability", 0.3))
                    if stage_id:
                        stage_scores[stage_id] += base_score * probability
                        stage_reasons[stage_id].append(f"default:{risk_id}")

        # 排序并返回
        ranked = sorted(stage_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        for stage_id, score in ranked:
            stage_meta = self.stages_by_id.get(stage_id, {})
            results.append({
                "stage_id": stage_id,
                "stage": stage_meta.get("name", stage_id),
                "score": round(score, 4),
                "description": stage_meta.get("description", ""),
                "evidence_types": stage_meta.get("evidence_types", []),
                "reasons": stage_reasons[stage_id]
            })

        return results

    def retrieve_evidence(self, query: str, query_signals: dict,
                         risk_candidates: list[dict], stage_candidates: list[dict]) -> dict:
        """检索证据 - 简化版"""
        # 构建关键词
        keywords = [query]
        for item in query_signals.get("symptoms", []):
            keywords.append(item.get("term", ""))
        for risk in risk_candidates:
            keywords.append(risk.get("name", ""))
            keywords.append(risk.get("risk_factor_id", ""))
        for stage in stage_candidates:
            keywords.append(stage.get("stage", ""))

        keywords = [k.lower() for k in keywords if k]

        # 搜索标准语料
        standard_hits = []
        for row in self.standard_corpus:
            text = row.get("chunk_text", "") or row.get("content", "")
            text_lower = text.lower()
            score = sum(2 if kw in text_lower else 0 for kw in keywords)
            if score > 0:
                standard_hits.append({
                    "text": text[:500],
                    "score": score,
                    "metadata": row.get("metadata", {})
                })

        standard_hits.sort(key=lambda x: x["score"], reverse=True)

        return {
            "standards": standard_hits[:5],
            "management": [],
            "methods": []
        }


class SymptomRiskRouter:
    """症状驱动风险路由器 - 集成 standalone_food_risk_kb 完整知识库"""

    def __init__(self, data_retriever=None):
        """
        初始化症状风险路由器

        Args:
            data_retriever: 数据检索器实例，用于关联供应链企业
        """
        self.kb = None
        self.data_retriever = data_retriever

        # 尝试初始化完整知识库
        if KB_AVAILABLE:
            try:
                self.kb = StandaloneKBWrapper()
                print("✓ 完整知识库包装器初始化成功")
            except Exception as e:
                print(f"⚠ 知识库初始化失败: {e}")
                self._load_fallback_knowledge()
        else:
            print("⚠ yaml 模块不可用，使用备用实现")
            self._load_fallback_knowledge()

    def _load_fallback_knowledge(self):
        """加载备用风险知识"""
        self.symptom_to_risk = {
            "腹泻": [{"risk_factor": "microbial_salmonella", "weight": 0.8},
                    {"risk_factor": "microbial_ecoli", "weight": 0.7}],
            "发热": [{"risk_factor": "microbial_salmonella", "weight": 0.8},
                    {"risk_factor": "microbial_listeria", "weight": 0.7}],
            "呕吐": [{"risk_factor": "microbial_staph", "weight": 0.9},
                    {"risk_factor": "microbial_b_cereus", "weight": 0.6}],
            "腹痛": [{"risk_factor": "microbial_salmonella", "weight": 0.8},
                    {"risk_factor": "microbial_ecoli", "weight": 0.7}],
            "恶心": [{"risk_factor": "microbial_staph", "weight": 0.6}],
            "头晕": [{"risk_factor": "chemical_melamine", "weight": 0.5}],
            "乏力": [{"risk_factor": "microbial_listeria", "weight": 0.5}],
        }

        self.risk_factor_defs = {
            "microbial_salmonella": {
                "name": "沙门氏菌",
                "category": "microbial",
                "description": "革兰氏阴性杆菌，可引起胃肠炎、败血症",
                "applicable_products": ["生鲜乳", "奶酪", "肉类"],
                "typical_symptoms": ["腹泻", "发热", "腹痛"],
                "linked_stages": ["挤奶", "运输", "加工"]
            },
            "microbial_listeria": {
                "name": "李斯特菌",
                "category": "microbial",
                "description": "嗜冷菌，可在低温下生长",
                "applicable_products": ["奶酪", "冷链食品"],
                "typical_symptoms": ["发热", "乏力"],
                "linked_stages": ["加工", "冷链存储"]
            },
            "microbial_ecoli": {
                "name": "致病性大肠杆菌",
                "category": "microbial",
                "description": "可引起严重腹泻",
                "applicable_products": ["生鲜乳", "肉类"],
                "typical_symptoms": ["腹泻", "腹痛"],
                "linked_stages": ["挤奶", "初加工"]
            },
            "microbial_staph": {
                "name": "金黄色葡萄球菌",
                "category": "microbial",
                "description": "产生肠毒素",
                "applicable_products": ["乳制品", "肉类"],
                "typical_symptoms": ["呕吐", "恶心"],
                "linked_stages": ["加工", "包装"]
            },
            "chemical_melamine": {
                "name": "三聚氰胺",
                "category": "chemical",
                "description": "非法添加物",
                "applicable_products": ["奶粉"],
                "typical_symptoms": ["头晕"],
                "linked_stages": ["配料"]
            },
        }

        self.stages_by_id = {
            "milking": {"name": "挤奶", "description": "原料乳采集"},
            "transport": {"name": "运输", "description": "原料运输"},
            "processing": {"name": "加工", "description": "生产加工"},
            "storage": {"name": "冷链存储", "description": "冷藏存储"},
            "distribution": {"name": "配送", "description": "产品配送"},
            "retail": {"name": "零售", "description": "终端销售"}
        }

        print("✓ 备用知识加载完成")

    def analyze_symptoms(self, query: str) -> list[dict]:
        """分析症状关键词"""
        if self.kb:
            try:
                signals = self.kb.analyze_query(query)
                return signals.get("symptoms", [])
            except Exception as e:
                print(f"知识库症状分析失败: {e}")

        # 备用实现
        detected = []
        for symptom, mappings in self.symptom_to_risk.items():
            if symptom in query:
                detected.append({
                    "term": symptom,
                    "symptom_id": f"symptom_{symptom}",
                    "risk_factors": [m["risk_factor"] for m in mappings]
                })
        return detected

    def infer_risk_factors(self, query: str, symptoms: list[dict]) -> list[dict]:
        """推断风险因子"""
        if self.kb:
            try:
                query_signals = {"symptoms": symptoms, "test_items": [], "products": []}
                return self.kb.infer_risk_factors(query, query_signals, top_k=6)
            except Exception as e:
                print(f"知识库风险推断失败: {e}")

        # 备用实现
        scores = defaultdict(float)
        for symptom in symptoms:
            for mapping in self.symptom_to_risk.get(symptom.get("term", ""), []):
                risk_id = mapping["risk_factor"]
                scores[risk_id] += mapping.get("weight", 0.5)

        results = []
        for risk_id, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            risk_def = self.risk_factor_defs.get(risk_id, {})
            results.append({
                "risk_factor_id": risk_id,
                "name": risk_def.get("name", risk_id),
                "category": risk_def.get("category", "未知"),
                "description": risk_def.get("description", ""),
                "score": score,
                "applicable_products": risk_def.get("applicable_products", []),
                "typical_symptoms": risk_def.get("typical_symptoms", []),
                "reasons": ["symptom_match"]
            })
        return results

    def infer_stages(self, risk_factors: list[dict]) -> list[dict]:
        """推断生产环节"""
        if self.kb:
            try:
                kb_risks = [{"risk_factor_id": r["risk_factor_id"], "score": r["score"]}
                           for r in risk_factors]
                return self.kb.infer_stages(kb_risks, top_k=5)
            except Exception as e:
                print(f"知识库环节推断失败: {e}")

        # 备用实现
        stage_scores = defaultdict(float)
        stage_risks = defaultdict(list)

        for risk in risk_factors:
            risk_id = risk.get("risk_factor_id", "")
            risk_def = self.risk_factor_defs.get(risk_id, {})
            for stage in risk_def.get("linked_stages", []):
                stage_scores[stage] += risk.get("score", 0)
                stage_risks[stage].append(risk.get("name"))

        results = []
        for stage, score in sorted(stage_scores.items(), key=lambda x: x[1], reverse=True):
            results.append({
                "stage_id": stage,
                "stage": stage,
                "score": score,
                "related_risks": list(set(stage_risks[stage])),
                "reasons": ["fallback"]
            })
        return results

    def retrieve_gb_evidence(self, query: str, risk_factors: list[dict],
                            stages: list[dict]) -> list[dict]:
        """检索GB标准依据"""
        if not self.kb:
            return []

        try:
            query_signals = {"symptoms": [], "test_items": [], "products": []}
            kb_risks = [{"risk_factor_id": r["risk_factor_id"], "score": r["score"]}
                       for r in risk_factors]
            kb_stages = [{"stage_id": s.get("stage_id", s["stage"]), "score": s["score"]}
                        for s in stages]

            evidence = self.kb.retrieve_evidence(query, query_signals, kb_risks, kb_stages)

            gb_refs = []
            for item in evidence.get("standards", []):
                metadata = item.get("metadata", {})
                gb_no = metadata.get("gb_no") or metadata.get("standard_id")
                if gb_no:
                    gb_refs.append({
                        "gb_no": gb_no,
                        "title": metadata.get("title", ""),
                        "text": item.get("text", "")[:200],
                        "score": item.get("score", 0)
                    })
            return gb_refs
        except Exception as e:
            print(f"GB证据检索失败: {e}")
            return []

    # Stage ID mapping from KB (English) to Chinese keywords
    STAGE_ID_MAPPING = {
        "farm_and_raw_milk": ["挤奶", "牧场", "milking", "farm"],
        "raw_material_and_ingredients": ["原料", "辅料", "供应商", "material"],
        "production_and_processing": ["加工", "生产", "processing", "production"],
        "packaging_and_filling": ["包装", "灌装", "packaging", "filling"],
        "cold_chain_and_logistics": ["冷链", "物流", "运输", "cold", "logistics", "transport"],
        "retail_and_terminal_storage": ["零售", "终端", "销售", "retail", "storage"],
    }

    def _get_stage_keywords(self, stage: dict) -> list[str]:
        """Extract keywords for stage matching from stage dict"""
        stage_name = stage.get("stage", "")
        stage_id = stage.get("stage_id", "")

        keywords = []

        # Add direct name/keywords
        if stage_name:
            keywords.append(stage_name)
        if stage_id:
            keywords.append(stage_id)

        # Add mapped keywords from stage_id
        if stage_id in self.STAGE_ID_MAPPING:
            keywords.extend(self.STAGE_ID_MAPPING[stage_id])

        return keywords

    def link_to_enterprises(self, risk_factors: list[dict], stages: list[dict],
                           product_type: Optional[str] = None) -> list[dict]:
        """关联供应链企业"""
        if not self.data_retriever:
            return []

        linked = []
        enterprises = self.data_retriever.enterprises

        applicable_products = set()
        for r in risk_factors:
            applicable_products.update(r.get("applicable_products", []))

        for ent in enterprises:
            score = 0.0
            reasons = []
            node_type = ent.get("node_type", "")
            ent_id = ent.get("enterprise_id", "")
            ent_products = ent.get("licence_scope", "")

            for stage in stages:
                stage_score = stage.get("score", 0)
                stage_keywords = self._get_stage_keywords(stage)

                # Check for牧场匹配
                if any(kw in sk for sk in stage_keywords for kw in ["挤奶", "牧场", "milking", "farm"]):
                    if node_type == "牧场":
                        score += stage_score * 1.0
                        reasons.append(f"牧场环节: {stage.get('name', stage.get('stage_id', ''))}")
                # Check for加工/生产匹配
                elif any(kw in sk for sk in stage_keywords for kw in ["加工", "生产", "processing", "production"]):
                    if node_type == "乳企":
                        score += stage_score * 1.0
                        reasons.append(f"加工环节: {stage.get('name', stage.get('stage_id', ''))}")
                # Check for物流/运输匹配
                elif any(kw in sk for sk in stage_keywords for kw in ["物流", "运输", "logistics", "transport"]):
                    if node_type == "物流":
                        score += stage_score * 0.8
                        reasons.append(f"物流环节: {stage.get('name', stage.get('stage_id', ''))}")
                # Check for仓储/冷链匹配
                elif any(kw in sk for sk in stage_keywords for kw in ["仓储", "冷链", "storage", "cold"]):
                    if node_type == "仓储":
                        score += stage_score * 0.8
                        reasons.append(f"仓储环节: {stage.get('name', stage.get('stage_id', ''))}")

            if product_type and product_type in ent_products:
                score += 2.0
                reasons.append(f"生产{product_type}")

            for prod in applicable_products:
                if prod in ent_products:
                    score += 1.0
                    reasons.append(f"涉及: {prod}")

            violation_count = int(ent.get("historical_violation_count", 0) or 0)
            if violation_count > 0:
                score += violation_count * 5
                reasons.append(f"历史违规{violation_count}次")

            credit = ent.get("credit_rating", "A")
            if credit == "C":
                score += 3
                reasons.append("信用等级C")
            elif credit == "D":
                score += 5
                reasons.append("信用等级D")

            if score > 0:
                linked.append({
                    "enterprise_id": ent_id,
                    "enterprise_name": ent.get("enterprise_name"),
                    "node_type": node_type,
                    "risk_score": round(score, 2),
                    "risk_level": "high" if score >= 10 else "medium" if score >= 5 else "low",
                    "reasons": reasons,
                    "credit_rating": credit,
                    "historical_violations": violation_count
                })

        linked.sort(key=lambda x: x["risk_score"], reverse=True)
        return linked[:10]

    def assess(self, query: str, product_type: Optional[str] = None) -> SymptomRiskResult:
        """执行症状驱动风险评估 (LLM增强版)"""
        print(f"\n[症状评估] 输入: '{query}'")

        # 1. 使用 LLM 增强的症状分析
        all_processing_steps = []
        llm_extraction_data = None

        if self.kb:
            try:
                # 使用新的 analyze_query 方法 (支持 LLM)
                analysis_result = self.kb.analyze_query(query, use_llm=True)
                symptoms = analysis_result.get("symptoms", [])
                llm_extraction_data = analysis_result.get("llm_extraction")
                all_processing_steps.extend(analysis_result.get("processing_steps", []))
                print(f"  [症状识别] 发现 {len(symptoms)} 个症状")
                for s in symptoms:
                    source = s.get('source', 'keyword')
                    print(f"    - {s['term']} (来源: {source})")
            except Exception as e:
                print(f"  LLM 症状分析失败，回退到关键词匹配: {e}")
                symptoms = self.analyze_symptoms(query)
                all_processing_steps.append({
                    "step": "llm_extraction",
                    "status": "failed",
                    "error": str(e),
                    "fallback": "keyword_matching"
                })
        else:
            symptoms = self.analyze_symptoms(query)

        # 2. 推断风险因子
        print(f"  [风险推断] 基于症状推断风险因子...")
        risk_factors = self.infer_risk_factors(query, symptoms)
        print(f"    发现 {len(risk_factors)} 个风险因子")
        all_processing_steps.append({
            "step": "risk_inference",
            "status": "completed",
            "risk_factors_count": len(risk_factors)
        })

        # 3. 推断生产环节
        stages = self.infer_stages(risk_factors)
        all_processing_steps.append({
            "step": "stage_inference",
            "status": "completed",
            "stages_count": len(stages)
        })

        # 4. 检索GB标准依据
        gb_refs = self.retrieve_gb_evidence(query, risk_factors, stages)
        all_processing_steps.append({
            "step": "gb_retrieval",
            "status": "completed",
            "gb_refs_count": len(gb_refs)
        })

        # 5. 关联企业
        linked_enterprises = self.link_to_enterprises(risk_factors, stages, product_type)
        all_processing_steps.append({
            "step": "enterprise_linking",
            "status": "completed",
            "enterprises_count": len(linked_enterprises)
        })

        # 6. 获取证据
        evidence = {}
        if self.kb:
            try:
                query_signals = {"symptoms": symptoms, "test_items": [], "products": []}
                kb_risks = [{"risk_factor_id": r["risk_factor_id"], "score": r["score"]} for r in risk_factors]
                kb_stages = [{"stage_id": s.get("stage_id", s["stage"]), "score": s["score"]} for s in stages]
                evidence = self.kb.retrieve_evidence(query, query_signals, kb_risks, kb_stages)
            except Exception as e:
                print(f"证据检索失败: {e}")

        # 7. 确定风险等级
        max_risk_score = max([r.get("score", 0) for r in risk_factors] + [0])
        risk_level = "low"
        if max_risk_score >= 3:
            risk_level = "high"
        elif max_risk_score >= 1.5:
            risk_level = "medium"

        # 8. 生成建议
        suggested_actions = self._generate_suggestions(risk_factors, stages, linked_enterprises, gb_refs)

        print(f"  [评估完成] 风险等级: {risk_level}, 置信度: {min(0.9, 0.3 + len(symptoms) * 0.2 + len(risk_factors) * 0.1):.2f}")

        return SymptomRiskResult(
            query=query,
            symptoms_detected=symptoms,
            risk_factors=risk_factors,
            stage_candidates=stages,
            evidence=evidence,
            linked_enterprises=linked_enterprises,
            gb_references=gb_refs,
            risk_level=risk_level,
            confidence=min(0.9, 0.3 + len(symptoms) * 0.2 + len(risk_factors) * 0.1),
            suggested_actions=suggested_actions,
            llm_extraction=llm_extraction_data,
            processing_steps=all_processing_steps
        )

    def _generate_suggestions(self, risk_factors: list[dict], stages: list[dict],
                              enterprises: list[dict], gb_refs: list[dict]) -> list[str]:
        """生成监管建议"""
        suggestions = []

        risk_categories = set(r.get("category", "") for r in risk_factors)
        if "microbial" in risk_categories:
            suggestions.append("重点关注微生物指标：菌落总数、大肠菌群、沙门氏菌、金黄色葡萄球菌")
            suggestions.append("检查企业卫生管理制度执行情况")

        if "chemical" in risk_categories:
            suggestions.append("加强农兽药残留、重金属检测")

        stage_names = [s.get("stage", "") for s in stages]
        if any("farm" in s or "牧场" in s for s in stage_names):
            suggestions.append("加强牧场原料乳抽检")
        if any("processing" in s or "加工" in s for s in stage_names):
            suggestions.append("重点检查HACCP控制点")

        if gb_refs:
            gb_nos = list(set(ref["gb_no"] for ref in gb_refs if ref.get("gb_no")))[:3]
            if gb_nos:
                suggestions.append(f"依据标准: {', '.join(gb_nos)}")

        high_risk = [e for e in enterprises if e.get("risk_level") == "high"][:3]
        if high_risk:
            names = [e.get("enterprise_name") for e in high_risk]
            suggestions.append(f"优先检查: {', '.join(names)}")

        return suggestions


# 单例
_symptom_router: Optional[SymptomRiskRouter] = None


def get_symptom_router(data_retriever=None) -> SymptomRiskRouter:
    """获取症状路由器单例"""
    global _symptom_router
    if _symptom_router is None:
        if data_retriever is None:
            from .retriever import DataRetriever
            data_retriever = DataRetriever(use_real_data=True)
        _symptom_router = SymptomRiskRouter(data_retriever)
    return _symptom_router
