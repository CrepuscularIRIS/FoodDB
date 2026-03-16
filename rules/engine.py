"""
风险评分引擎 - 核心评分逻辑
"""

import csv
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class RiskScore:
    """风险评分结果"""
    total_score: float  # 总分 (0-100)
    risk_level: str  # high/medium/low

    # 分项得分
    product_risk: float = 0.0  # 产品类别敏感度
    supply_chain_risk: float = 0.0  # 供应链复杂度
    supplier_risk: float = 0.0  # 供应商历史风险
    traceability_risk: float = 0.0  # 追溯完整性
    label_risk: float = 0.0  # 标签一致性
    inspection_risk: float = 0.0  # 历史抽检异常
    regulatory_risk: float = 0.0  # 监管处罚
    cold_chain_risk: float = 0.0  # 冷链敏感度
    diffusion_risk: float = 0.0  # 扩散度

    # 触发规则
    triggered_rules: list[dict] = field(default_factory=list)

    # 证据
    evidence: dict = field(default_factory=dict)


class RiskScoringEngine:
    """风险评分引擎"""

    # 风险等级阈值
    RISK_THRESHOLDS = {
        "high": 70,
        "medium": 40,
        "low": 0
    }

    # 默认权重配置
    DEFAULT_WEIGHTS = {
        "product_risk": 0.10,
        "supply_chain_risk": 0.10,
        "supplier_risk": 0.15,
        "traceability_risk": 0.10,
        "label_risk": 0.05,
        "inspection_risk": 0.20,
        "regulatory_risk": 0.15,
        "cold_chain_risk": 0.10,
        "diffusion_risk": 0.05
    }

    def __init__(self, data_dir: Optional[Path] = None):
        """初始化评分引擎"""
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "data" / "mock"

        self.data_dir = data_dir
        self.weights = self.DEFAULT_WEIGHTS.copy()

        # 加载数据
        self.enterprises = self._load_csv("enterprise_master.csv")
        self.batches = self._load_csv("batch_records.csv")
        self.inspections = self._load_csv("inspection_records.csv")
        self.events = self._load_csv("regulatory_events.csv")
        self.edges = self._load_csv("supply_edges.csv")
        self.gb_rules = self._load_csv("gb_rules.csv")

        # 构建索引
        self._build_indices()

    def _load_csv(self, filename: str) -> list[dict]:
        """加载CSV文件"""
        filepath = self.data_dir / filename
        if not filepath.exists():
            return []

        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)

    def _build_indices(self):
        """构建数据索引"""
        # 企业索引
        self.enterprise_by_id = {e["enterprise_id"]: e for e in self.enterprises}

        # 批次索引
        self.batch_by_id = {b["batch_id"]: b for b in self.batches}
        self.batches_by_enterprise = {}
        for b in self.batches:
            eid = b["enterprise_id"]
            if eid not in self.batches_by_enterprise:
                self.batches_by_enterprise[eid] = []
            self.batches_by_enterprise[eid].append(b)

        # 检验记录索引
        self.inspections_by_batch = {}
        self.inspections_by_enterprise = {}
        for ins in self.inspections:
            bid = ins.get("batch_id")
            if bid:
                if bid not in self.inspections_by_batch:
                    self.inspections_by_batch[bid] = []
                self.inspections_by_batch[bid].append(ins)

            eid = ins["enterprise_id"]
            if eid not in self.inspections_by_enterprise:
                self.inspections_by_enterprise[eid] = []
            self.inspections_by_enterprise[eid].append(ins)

        # 监管事件索引
        self.events_by_enterprise = {}
        for evt in self.events:
            eid = evt["enterprise_id"]
            if eid not in self.events_by_enterprise:
                self.events_by_enterprise[eid] = []
            self.events_by_enterprise[eid].append(evt)

        # 供应链边索引
        self.edges_from = {}
        self.edges_to = {}
        for edge in self.edges:
            sid = edge["source_id"]
            tid = edge["target_id"]
            if sid not in self.edges_from:
                self.edges_from[sid] = []
            self.edges_from[sid].append(edge)
            if tid not in self.edges_to:
                self.edges_to[tid] = []
            self.edges_to[tid].append(edge)

    def calculate_node_risk(self, batch_id: Optional[str] = None,
                           enterprise_id: Optional[str] = None) -> RiskScore:
        """
        计算节点风险评分

        Args:
            batch_id: 批次ID（可选）
            enterprise_id: 企业ID（可选，如不提供则使用批次关联企业）

        Returns:
            RiskScore: 风险评分结果
        """
        # 确定目标批次和企业
        batch = None
        if batch_id and batch_id in self.batch_by_id:
            batch = self.batch_by_id[batch_id]
            enterprise_id = batch["enterprise_id"]

        if not enterprise_id or enterprise_id not in self.enterprise_by_id:
            raise ValueError(f"无效的企业ID: {enterprise_id}")

        enterprise = self.enterprise_by_id[enterprise_id]

        # 初始化评分
        score = RiskScore(total_score=0, risk_level="low")
        evidence = {
            "batch": batch,
            "enterprise": enterprise,
            "inspections": [],
            "events": [],
            "edges": []
        }
        triggered_rules = []

        # 1. 产品类别敏感度因子
        score.product_risk = self._calc_product_risk(batch, enterprise)
        if score.product_risk > 0:
            triggered_rules.append({
                "factor": "product_type",
                "score": score.product_risk,
                "reason": f"产品类型风险: {batch.get('product_type', '未知') if batch else '企业综合'}"
            })

        # 2. 供应链复杂度因子
        score.supply_chain_risk = self._calc_supply_chain_risk(enterprise)
        if score.supply_chain_risk > 0:
            triggered_rules.append({
                "factor": "supply_chain_complexity",
                "score": score.supply_chain_risk,
                "reason": f"供应链复杂度: {len(self.edges_from.get(enterprise_id, [])) + len(self.edges_to.get(enterprise_id, []))} 条关联"
            })

        # 3. 供应商历史风险因子
        score.supplier_risk = self._calc_supplier_risk(enterprise)
        if score.supplier_risk > 0:
            triggered_rules.append({
                "factor": "supplier_risk",
                "score": score.supplier_risk,
                "reason": "上游供应商存在历史违规记录"
            })

        # 4. 批次追溯完整性因子
        score.traceability_risk = self._calc_traceability_risk(batch)
        if score.traceability_risk > 0:
            triggered_rules.append({
                "factor": "traceability",
                "score": score.traceability_risk,
                "reason": "批次追溯信息不完整"
            })

        # 5. 标签与标准一致性因子
        score.label_risk = self._calc_label_risk(batch, enterprise)

        # 6. 历史抽检异常因子
        score.inspection_risk, insp_evidence = self._calc_inspection_risk(
            batch, enterprise
        )
        evidence["inspections"] = insp_evidence
        if score.inspection_risk > 0:
            triggered_rules.append({
                "factor": "inspection_history",
                "score": score.inspection_risk,
                "reason": f"历史抽检异常: {len([i for i in insp_evidence if i.get('test_result') == 'unqualified'])} 次不合格"
            })

        # 7. 行政处罚次数因子
        score.regulatory_risk, event_evidence = self._calc_regulatory_risk(enterprise)
        evidence["events"] = event_evidence
        if score.regulatory_risk > 0:
            triggered_rules.append({
                "factor": "regulatory_history",
                "score": score.regulatory_risk,
                "reason": f"监管处罚记录: {len(event_evidence)} 次事件"
            })

        # 8. 冷链要求敏感度因子
        score.cold_chain_risk = self._calc_cold_chain_risk(batch)
        if score.cold_chain_risk > 0:
            triggered_rules.append({
                "factor": "cold_chain",
                "score": score.cold_chain_risk,
                "reason": "冷链储存/运输条件异常"
            })

        # 9. 销售区域扩散度因子
        score.diffusion_risk = self._calc_diffusion_risk(enterprise)

        # 计算总分
        total = (
            score.product_risk * self.weights["product_risk"] +
            score.supply_chain_risk * self.weights["supply_chain_risk"] +
            score.supplier_risk * self.weights["supplier_risk"] +
            score.traceability_risk * self.weights["traceability_risk"] +
            score.label_risk * self.weights["label_risk"] +
            score.inspection_risk * self.weights["inspection_risk"] +
            score.regulatory_risk * self.weights["regulatory_risk"] +
            score.cold_chain_risk * self.weights["cold_chain_risk"] +
            score.diffusion_risk * self.weights["diffusion_risk"]
        )

        score.total_score = round(min(total, 100), 2)
        score.risk_level = self._determine_risk_level(score.total_score)
        score.triggered_rules = triggered_rules
        score.evidence = evidence

        return score

    def _calc_product_risk(self, batch: Optional[dict], enterprise: dict) -> float:
        """计算产品类别敏感度风险"""
        product_type = batch.get("product_type") if batch else None

        if not product_type:
            # 根据企业主要产品
            if "鲜牛奶" in enterprise.get("main_products", "") or "pasteurized" in enterprise.get("main_products", ""):
                return 80  # 巴氏乳高风险
            elif "酸奶" in enterprise.get("main_products", "") or "yogurt" in enterprise.get("main_products", ""):
                return 75  # 酸奶次高风险
            else:
                return 50

        # 产品类型风险权重
        risk_map = {
            "pasteurized": 80,  # 巴氏杀菌乳：保质期短，冷链依赖高
            "yogurt": 75,       # 酸奶：需冷藏，微生物敏感
            "raw_milk": 70,     # 生乳：原料风险
            "UHT": 40,          # 灭菌乳：相对稳定
            "powder": 30        # 奶粉：最稳定
        }

        return risk_map.get(product_type, 50)

    def _calc_supply_chain_risk(self, enterprise: dict) -> float:
        """计算供应链复杂度风险"""
        eid = enterprise["enterprise_id"]

        # 计算关联边数
        out_edges = len(self.edges_from.get(eid, []))
        in_edges = len(self.edges_to.get(eid, []))
        total_edges = out_edges + in_edges

        # 边数越多，复杂度越高
        if total_edges >= 10:
            return 80
        elif total_edges >= 5:
            return 60
        elif total_edges >= 3:
            return 40
        elif total_edges >= 1:
            return 20
        else:
            return 10  # 孤立节点也有风险

    def _calc_supplier_risk(self, enterprise: dict) -> float:
        """计算供应商历史风险"""
        eid = enterprise["enterprise_id"]

        # 查找上游供应商
        upstream_edges = self.edges_to.get(eid, [])
        if not upstream_edges:
            return 30  # 无明确供应商记录

        max_risk = 0
        for edge in upstream_edges:
            supplier_id = edge["source_id"]
            supplier = self.enterprise_by_id.get(supplier_id)
            if supplier:
                # 检查供应商违规记录
                violation_count = int(supplier.get("historical_violation_count", 0))
                if violation_count >= 3:
                    max_risk = max(max_risk, 90)
                elif violation_count >= 1:
                    max_risk = max(max_risk, 60)

                # 检查供应商信用等级
                credit = supplier.get("credit_rating", "B")
                if credit == "D":
                    max_risk = max(max_risk, 80)
                elif credit == "C":
                    max_risk = max(max_risk, 50)

        return max_risk if max_risk > 0 else 20

    def _calc_traceability_risk(self, batch: Optional[dict]) -> float:
        """计算批次追溯完整性风险"""
        if not batch:
            return 50  # 无批次信息

        # 检查关键字段
        required_fields = ["raw_material_batch", "production_line"]
        missing = sum(1 for f in required_fields if not batch.get(f))

        if missing >= 2:
            return 70
        elif missing >= 1:
            return 40

        # 检查原料供应商
        if not batch.get("raw_material_supplier_id"):
            return 30

        return 10

    def _calc_label_risk(self, batch: Optional[dict], enterprise: dict) -> float:
        """计算标签与标准一致性风险"""
        # 简化为基于企业历史
        violation_count = int(enterprise.get("historical_violation_count", 0))

        if violation_count >= 3:
            return 60
        elif violation_count >= 1:
            return 30

        return 10

    def _calc_inspection_risk(self, batch: Optional[dict],
                               enterprise: dict) -> tuple[float, list]:
        """计算历史抽检异常风险"""
        eid = enterprise["enterprise_id"]
        evidence = []

        # 获取相关检验记录
        inspections = []
        if batch:
            inspections = self.inspections_by_batch.get(batch["batch_id"], [])
        if not inspections:
            inspections = self.inspections_by_enterprise.get(eid, [])

        if not inspections:
            return 30, []  # 无检验记录

        unqualified_count = 0
        high_risk_count = 0

        for ins in inspections:
            evidence.append(ins)
            if ins.get("test_result") == "unqualified":
                unqualified_count += 1
                # 检查是否涉及高风险项目
                unq_items = ins.get("unqualified_items", "")
                if any(item in unq_items for item in ["菌落总数", "大肠菌群", "黄曲霉毒素"]):
                    high_risk_count += 1

        # 计算风险分数
        total = len(inspections)
        if total == 0:
            return 30, evidence

        unq_rate = unqualified_count / total

        if high_risk_count > 0:
            return 90, evidence
        elif unq_rate >= 0.5:
            return 70, evidence
        elif unq_rate >= 0.2:
            return 50, evidence
        elif unqualified_count > 0:
            return 30, evidence
        else:
            return 10, evidence

    def _calc_regulatory_risk(self, enterprise: dict) -> tuple[float, list]:
        """计算监管处罚风险"""
        eid = enterprise["enterprise_id"]
        events = self.events_by_enterprise.get(eid, [])

        if not events:
            return 10, []

        high_severity = sum(1 for e in events if e.get("severity") == "high")
        medium_severity = sum(1 for e in events if e.get("severity") == "medium")

        if high_severity >= 2:
            return 90, events
        elif high_severity >= 1:
            return 70, events
        elif medium_severity >= 2:
            return 50, events
        elif medium_severity >= 1:
            return 30, events
        else:
            return 20, events

    def _calc_cold_chain_risk(self, batch: Optional[dict]) -> float:
        """计算冷链敏感度风险"""
        if not batch:
            return 30

        product_type = batch.get("product_type", "")

        # 检查产品类型
        if product_type in ["pasteurized", "yogurt", "raw_milk"]:
            base_risk = 70
        elif product_type == "UHT":
            base_risk = 30
        else:
            base_risk = 40

        # 检查冷链温度
        storage_temp = batch.get("storage_temp_avg")
        transport_temp = batch.get("transport_temp_avg")

        if product_type in ["pasteurized", "yogurt"]:
            # 巴氏乳和酸奶应在2-6°C
            if storage_temp and float(storage_temp) > 8:
                base_risk = max(base_risk, 90)
            elif transport_temp and float(transport_temp) > 10:
                base_risk = max(base_risk, 80)

        # 检查运输时长
        transport_hours = batch.get("transport_duration_hours")
        if transport_hours and product_type == "pasteurized":
            hours = float(transport_hours)
            if hours > 24:
                base_risk = max(base_risk, 85)
            elif hours > 12:
                base_risk = max(base_risk, 60)

        return base_risk

    def _calc_diffusion_risk(self, enterprise: dict) -> float:
        """计算销售区域扩散度风险"""
        eid = enterprise["enterprise_id"]

        # 根据下游销售节点数量
        downstream_edges = self.edges_from.get(eid, [])

        if len(downstream_edges) >= 5:
            return 60
        elif len(downstream_edges) >= 3:
            return 40
        elif len(downstream_edges) >= 1:
            return 20
        else:
            return 10

    def _determine_risk_level(self, total_score: float) -> str:
        """确定风险等级"""
        if total_score >= self.RISK_THRESHOLDS["high"]:
            return "high"
        elif total_score >= self.RISK_THRESHOLDS["medium"]:
            return "medium"
        else:
            return "low"

    def check_gb_compliance(self, inspection: dict) -> list[dict]:
        """
        检查GB标准合规性

        Args:
            inspection: 检验记录

        Returns:
            list[dict]: 违规规则列表
        """
        violations = []

        # 获取产品类型
        batch_id = inspection.get("batch_id")
        batch = self.batch_by_id.get(batch_id) if batch_id else None
        product_type = batch.get("product_type", "all") if batch else "all"

        # 遍历相关规则
        for rule in self.gb_rules:
            if rule["product_type"] not in [product_type, "all"]:
                continue

            check_item = rule["check_item"]
            threshold = float(rule["threshold"])
            operator = rule["operator"]

            # 获取检验值
            value = self._get_inspection_value(inspection, check_item)
            if value is None:
                continue

            # 判断是否违规
            violated = False
            if operator == "<=" and value > threshold:
                violated = True
            elif operator == ">=" and value < threshold:
                violated = True
            elif operator == "<" and value >= threshold:
                violated = True
            elif operator == ">" and value <= threshold:
                violated = True
            elif operator == "=" and value != threshold:
                violated = True

            if violated:
                violations.append({
                    "rule_id": rule["rule_id"],
                    "gb_no": rule["gb_no"],
                    "check_item": check_item,
                    "threshold": threshold,
                    "actual_value": value,
                    "severity": rule["severity"],
                    "action_suggestion": rule["action_suggestion"]
                })

        return violations

    def _get_inspection_value(self, inspection: dict, check_item: str) -> Optional[float]:
        """从检验记录中获取检测值"""
        mapping = {
            "蛋白质": "protein_g_100g",
            "脂肪": "fat_g_100g",
            "菌落总数": "aerobic_count_cfu_ml",
            "大肠菌群": "coliforms_mpn_100ml",
            "黄曲霉毒素M1": "aflatoxin_m1_ug_kg",
            "铅": "lead_mg_kg",
            "细菌总数": "total_bacteria_count",
            "酸度": "acid_degree",
            "三聚氰胺": "melamine_mg_kg",
            "体细胞数": "somatic_cell_count"
        }

        field = mapping.get(check_item)
        if field and field in inspection:
            try:
                return float(inspection[field])
            except (ValueError, TypeError):
                return None

        return None
