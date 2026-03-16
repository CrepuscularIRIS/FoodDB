"""
企业候选匹配层 v1.0

输入: risk_factors + suspected_stage + population + location_hint + time_window_days + top_k
↓
匹配规则:
  - 环节匹配 25分
  - 产品风险匹配 20分
  - 历史违规 20分
  - 抽检时效 10分
  - 供应链邻近 15分
  - 地理匹配 10分
  - 惩罚项: 缺关键字段 -5分/项
↓
输出: Top-K 候选企业列表（带匹配分数、信号、证据）
"""

from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path


@dataclass
class EnterpriseCandidate:
    """企业候选对象"""
    enterprise_id: str
    enterprise_name: str
    node_type: str
    score: float  # 0-100
    matched_signals: List[str]  # 匹配信号，如 ["stage:生产", "history:微生物2次"]
    evidence: Dict[str, Any]  # 证据字段
    raw_data: Dict[str, Any]  # 原始企业数据


class EnterpriseMatcher:
    """企业候选匹配器 v1.0"""

    # 环节到企业类型的硬过滤映射
    STAGE_TO_NODE_TYPE = {
        "原料": ["牧场"],
        "生产加工": ["乳企"],
        "生产": ["乳企"],
        "物流": ["物流"],
        "仓储": ["仓储"],
        "销售": ["零售", "经销"],
    }

    # 风险因子到产品类型的映射
    RISK_TO_PRODUCT = {
        "salmonella": ["巴氏杀菌乳", "生鲜乳", "奶酪"],
        "escherichia_coli": ["巴氏杀菌乳", "生鲜乳", "乳制品"],
        "listeria": ["巴氏杀菌乳", "即食食品", "软奶酪"],
        "staphylococcus": ["乳制品", "糕点"],
        "norovirus": ["即食食品", "贝类"],
        "aflatoxin": ["乳制品", "坚果"],
        "melamine": ["婴幼儿配方乳粉", "乳粉"],
        "allergen": ["乳制品", "坚果制品", "烘焙食品"],
        "microbial": ["巴氏杀菌乳", "生鲜乳", "发酵乳"],
        "chemical": ["乳粉", "乳制品"],
    }

    # 风险因子到检验项目的映射
    RISK_TO_INSPECTION = {
        "salmonella": ["沙门氏菌", "菌落总数", "大肠菌群"],
        "escherichia_coli": ["大肠杆菌", "大肠菌群", "STEC"],
        "listeria": ["李斯特菌"],
        "staphylococcus": ["金黄色葡萄球菌"],
        "aflatoxin": ["黄曲霉毒素M1"],
        "melamine": ["三聚氰胺"],
        "microbial": ["菌落总数", "大肠菌群", "致病菌"],
    }

    def __init__(self, retriever):
        self.retriever = retriever
        self._build_indices()

    def _build_indices(self):
        """构建企业索引"""
        # 企业产品类型
        self.ent_products = {}
        product_keywords = {
            "巴氏": "巴氏杀菌乳", "鲜牛": "巴氏杀菌乳",
            "纯牛": "灭菌乳", "常温": "灭菌乳",
            "酸奶": "发酵乳", "酸乳": "发酵乳",
            "奶酪": "再制干酪", "芝士": "再制干酪",
            "奶粉": "乳粉", "婴幼儿": "婴幼儿配方乳粉",
        }

        for batch in self.retriever.batches:
            ent_id = batch.get("enterprise_id")
            product_name = batch.get("product_name", "")
            if ent_id not in self.ent_products:
                self.ent_products[ent_id] = set()
            for kw, ptype in product_keywords.items():
                if kw in product_name:
                    self.ent_products[ent_id].add(ptype)

        # 企业历史违规（按时间）
        self.ent_violations = {}  # ent_id -> [{date, type, description}]
        for event in self.retriever.events:
            ent_id = event.get("enterprise_id")
            if ent_id not in self.ent_violations:
                self.ent_violations[ent_id] = []

            violation_types = []
            desc = event.get("description", "")
            if "微生物" in desc or "菌" in desc:
                violation_types.append("微生物")
            if "添加剂" in desc or "防腐" in desc:
                violation_types.append("添加剂")
            if "标签" in desc:
                violation_types.append("标签")
            if "三聚氰胺" in desc:
                violation_types.append("非法添加")

            self.ent_violations[ent_id].append({
                "date": event.get("event_date", ""),
                "types": violation_types,
                "description": desc,
                "severity": event.get("severity", "low")
            })

        # 企业近期检验记录
        self.ent_inspections = {}  # ent_id -> [{date, item, result}]
        for ins in self.retriever.inspections:
            ent_id = ins.get("enterprise_id")
            if ent_id not in self.ent_inspections:
                self.ent_inspections[ent_id] = []

            unqualified = ins.get("unqualified_items", "")
            self.ent_inspections[ent_id].append({
                "date": ins.get("inspection_date", ""),
                "item": unqualified,
                "result": ins.get("test_result", ""),
                "is_unqualified": unqualified and unqualified.strip() != ""
            })

        # 供应链图（用于计算邻近度）
        self._build_supply_chain_graph()

    def _build_supply_chain_graph(self):
        """构建供应链图用于邻近度计算"""
        self.graph_neighbors = {}  # node_id -> [neighbor_ids]

        for edge in self.retriever.edges:
            source = edge.get("source_id")
            target = edge.get("target_id")

            if source not in self.graph_neighbors:
                self.graph_neighbors[source] = []
            if target not in self.graph_neighbors:
                self.graph_neighbors[target] = []

            self.graph_neighbors[source].append(target)
            self.graph_neighbors[target].append(source)  # 无向图

    def _get_graph_distance(self, start_id: str, target_id: str, max_depth: int = 3) -> int:
        """计算两节点在供应链图中的距离（BFS）"""
        if start_id == target_id:
            return 0
        if start_id not in self.graph_neighbors:
            return -1

        visited = {start_id}
        queue = [(start_id, 0)]

        while queue:
            node, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            for neighbor in self.graph_neighbors.get(node, []):
                if neighbor == target_id:
                    return depth + 1
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))

        return -1

    def match(self,
              risk_factors: List[str],
              suspected_stage: str,
              population: Optional[str] = None,
              location_hint: Optional[str] = None,
              time_window_days: int = 30,
              top_k: int = 10) -> List[EnterpriseCandidate]:
        """
        匹配企业候选

        Returns:
            List[EnterpriseCandidate] 按分数降序排列
        """
        candidates = []

        # 确定目标企业类型（硬过滤）
        target_node_types = self._get_target_node_types(suspected_stage)

        # 确定目标产品类型
        target_products = self._get_target_products(risk_factors)

        # 确定目标检验项目
        target_inspections = self._get_target_inspections(risk_factors)

        # 获取近期风险企业（用于供应链邻近度计算）
        recent_risk_enterprises = self._get_recent_risk_enterprises(time_window_days)

        # 遍历所有企业
        for enterprise in self.retriever.enterprises:
            ent_id = enterprise.get("enterprise_id")
            node_type = enterprise.get("node_type", "")
            ent_name = enterprise.get("enterprise_name", "")
            address = enterprise.get("address", "")

            # 硬过滤：环节类型不匹配则跳过
            if target_node_types and node_type not in target_node_types:
                continue

            scores = {
                "stage_match": 0,
                "product_risk_match": 0,
                "history_violation": 0,
                "inspection_recency": 0,
                "supply_chain_proximity": 0,
                "geo_match": 0,
            }
            penalties = 0
            signals = []
            evidence = {
                "violation_records": [],
                "inspection_records": [],
                "supply_chain_paths": [],
            }

            # 1. stage_match (25分) - 已通过硬过滤，直接给分
            scores["stage_match"] = 25
            signals.append(f"stage:{suspected_stage}")

            # 2. product_risk_match (20分)
            ent_products = self.ent_products.get(ent_id, set())
            product_hits = ent_products & target_products
            if product_hits:
                if len(product_hits) >= len(target_products):
                    scores["product_risk_match"] = 20
                else:
                    scores["product_risk_match"] = 10
                signals.append(f"product:{','.join(list(product_hits)[:2])}")

            # 3. history_violation (20分) - 近12个月
            violations = self.ent_violations.get(ent_id, [])
            relevant_violations = []
            for v in violations:
                # 检查时间（近12个月）
                try:
                    v_date = datetime.strptime(v["date"], "%Y-%m-%d")
                    if (datetime.now() - v_date).days <= 365:
                        # 检查类型相关性
                        for vt in v["types"]:
                            if any(vt.lower() in rf.lower() or rf.lower() in vt.lower()
                                   for rf in risk_factors):
                                relevant_violations.append(v)
                                break
                except:
                    continue

            v_count = len(relevant_violations)
            if v_count >= 3:
                scores["history_violation"] = 20
            elif v_count >= 1:
                scores["history_violation"] = 12

            if v_count > 0:
                signals.append(f"history:{v_count}次违规")
                evidence["violation_records"] = [v["date"] for v in relevant_violations[:3]]

            # 4. inspection_recency (10分) - time_window_days内
            inspections = self.ent_inspections.get(ent_id, [])
            recent_relevant = []
            for ins in inspections:
                try:
                    ins_date = datetime.strptime(ins["date"], "%Y-%m-%d")
                    if (datetime.now() - ins_date).days <= time_window_days:
                        # 检查检验项目相关性
                        for ti in target_inspections:
                            if ti in ins["item"]:
                                recent_relevant.append(ins)
                                break
                except:
                    continue

            if recent_relevant:
                scores["inspection_recency"] = 10
                signals.append(f"recent_inspection:{len(recent_relevant)}次")
                evidence["inspection_records"] = [ins["date"] for ins in recent_relevant[:3]]

            # 5. supply_chain_proximity (15分)
            min_distance = float('inf')
            for risk_ent in recent_risk_enterprises:
                dist = self._get_graph_distance(ent_id, risk_ent, max_depth=3)
                if dist >= 0:
                    min_distance = min(min_distance, dist)

            if min_distance == 1:
                scores["supply_chain_proximity"] = 15
                signals.append("supply:1跳")
            elif min_distance == 2:
                scores["supply_chain_proximity"] = 8
                signals.append("supply:2跳")
            elif min_distance == 3:
                scores["supply_chain_proximity"] = 3

            # 6. geo_match (10分)
            if location_hint and address:
                if location_hint in address:
                    scores["geo_match"] = 10
                    signals.append(f"geo:{location_hint}")
                # 简化的邻近区判断（可扩展）
                elif any(district in address for district in ["浦东", "黄浦", "静安"]):
                    if any(district in location_hint for district in ["浦东", "黄浦", "静安"]):
                        scores["geo_match"] = 5
                        signals.append("geo:邻近区")

            # 惩罚项：缺关键字段
            if not node_type:
                penalties += 5
            if ent_id not in self.ent_inspections:
                penalties += 5
            if not address:
                penalties += 5

            # 总分（最低0分）
            total_score = sum(scores.values()) - min(penalties, 15)
            total_score = max(0, total_score)

            # 只保留有意义的候选
            if total_score >= 20:
                candidate = EnterpriseCandidate(
                    enterprise_id=ent_id,
                    enterprise_name=ent_name,
                    node_type=node_type,
                    score=total_score,
                    matched_signals=signals,
                    evidence=evidence,
                    raw_data=enterprise
                )
                candidates.append(candidate)

        # 按分数降序排列
        candidates.sort(key=lambda x: x.score, reverse=True)

        return candidates[:top_k]

    def _get_target_node_types(self, suspected_stage: str) -> List[str]:
        """获取目标企业类型"""
        stage = suspected_stage.strip()
        if stage in self.STAGE_TO_NODE_TYPE:
            return self.STAGE_TO_NODE_TYPE[stage]
        # 模糊匹配
        for key, types in self.STAGE_TO_NODE_TYPE.items():
            if key in stage or stage in key:
                return types
        return []  # 空列表表示不过滤

    def _get_target_products(self, risk_factors: List[str]) -> Set[str]:
        """获取目标产品类型"""
        products = set()
        for rf in risk_factors:
            rf_lower = rf.lower().replace(" ", "_").replace("/", "_")
            for key, prods in self.RISK_TO_PRODUCT.items():
                if key in rf_lower or rf_lower in key:
                    products.update(prods)
        return products

    def _get_target_inspections(self, risk_factors: List[str]) -> List[str]:
        """获取目标检验项目"""
        inspections = []
        for rf in risk_factors:
            rf_lower = rf.lower().replace(" ", "_").replace("/", "_")
            for key, items in self.RISK_TO_INSPECTION.items():
                if key in rf_lower or rf_lower in key:
                    inspections.extend(items)
        return inspections

    def _get_recent_risk_enterprises(self, days: int) -> List[str]:
        """获取近期有风险的企业ID列表"""
        risk_ents = []
        cutoff = datetime.now() - timedelta(days=days)

        # 从监管事件中找
        for ent_id, violations in self.ent_violations.items():
            for v in violations:
                try:
                    v_date = datetime.strptime(v["date"], "%Y-%m-%d")
                    if v_date >= cutoff and v["severity"] in ["high", "medium"]:
                        risk_ents.append(ent_id)
                        break
                except:
                    continue

        # 从不合格检验记录中找
        for ent_id, inspections in self.ent_inspections.items():
            for ins in inspections:
                if ins.get("is_unqualified"):
                    try:
                        ins_date = datetime.strptime(ins["date"], "%Y-%m-%d")
                        if ins_date >= cutoff:
                            risk_ents.append(ent_id)
                            break
                    except:
                        continue

        return list(set(risk_ents))


def get_matcher(retriever) -> EnterpriseMatcher:
    """工厂函数"""
    return EnterpriseMatcher(retriever)


# 测试
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agent.retriever import DataRetriever

    print("="*70)
    print("企业候选匹配层 v1.0 测试")
    print("="*70)

    retriever = DataRetriever()
    matcher = EnterpriseMatcher(retriever)

    test_cases = [
        {
            "name": "沙门氏菌 + 生产加工",
            "risk_factors": ["Salmonella", "微生物污染"],
            "stage": "生产加工",
            "location": None
        },
        {
            "name": "过敏原 + 销售环节",
            "risk_factors": ["allergen", "过敏反应"],
            "stage": "销售",
            "location": "上海"
        },
        {
            "name": "黄曲霉毒素 + 原料环节",
            "risk_factors": ["aflatoxin", "化学污染"],
            "stage": "原料",
            "location": None
        },
    ]

    for case in test_cases:
        print(f"\n【{case['name']}】")
        candidates = matcher.match(
            risk_factors=case["risk_factors"],
            suspected_stage=case["stage"],
            location_hint=case["location"],
            top_k=3
        )
        print(f"  匹配到 {len(candidates)} 家企业:")
        for c in candidates:
            print(f"    - {c.enterprise_name} ({c.node_type})")
            print(f"      分数: {c.score:.0f}/100")
            print(f"      信号: {' | '.join(c.matched_signals[:3])}")

    print("\n" + "="*70)
    print("测试完成")
    print("="*70)
