"""
数据检索模块 - 从数据层获取相关信息
"""

import csv
import os
from pathlib import Path
from typing import Optional


class DataRetriever:
    """数据检索器"""

    # 默认数据目录优先级（从高到低）
    DEFAULT_DATA_PRIORITY = ["merged", "release_v1_1", "real", "mock"]

    def __init__(self, data_dir: Optional[Path] = None, use_real_data: bool = True):
        """
        初始化检索器

        Args:
            data_dir: 数据目录路径，None则使用自动解析
            use_real_data: 是否优先使用真实/合并数据（已废弃，保留兼容性）
        """
        if data_dir is None:
            data_dir = self._resolve_data_dir()

        self.data_dir = data_dir
        self._initialize()
        print(f"✓ 数据检索器初始化完成: {self.data_dir}")

    def _resolve_data_dir(self) -> Path:
        """
        解析数据目录优先级：
        1. DATA_DIR 环境变量
        2. 默认优先级: merged > release_v1_1 > real > mock
        3. 兜底创建 mock
        """
        base_dir = Path(__file__).parent.parent / "data"

        # 1. 检查环境变量
        env_data_dir = os.environ.get("DATA_DIR")
        if env_data_dir:
            path = Path(env_data_dir)
            if path.exists() and (path / "enterprise_master.csv").exists():
                print(f"✓ 使用环境变量 DATA_DIR: {path}")
                return path
            else:
                print(f"⚠ 环境变量 DATA_DIR 无效: {path}，尝试默认路径")

        # 2. 按优先级尝试默认路径
        for name in self.DEFAULT_DATA_PRIORITY:
            path = base_dir / name
            if path.exists() and (path / "enterprise_master.csv").exists():
                print(f"✓ 使用默认数据源: {name} ({path})")
                return path

        # 3. 兜底：创建并返回 mock 目录
        mock_dir = base_dir / "mock"
        mock_dir.mkdir(parents=True, exist_ok=True)
        print(f"⚠ 警告：未找到有效数据，使用兜底数据源: mock ({mock_dir})")
        print(f"  建议：运行数据生成脚本或设置 DATA_DIR 环境变量")
        return mock_dir

    def _initialize(self):
        """初始化数据加载"""
        self._load_all_data()
        self._build_indices()
        print(f"  - 加载企业: {len(self.enterprises)} 家")
        print(f"  - 加载批次: {len(self.batches)} 个")
        print(f"  - 加载检验记录: {len(self.inspections)} 条")
        print(f"  - 加载监管事件: {len(self.events)} 条")
        print(f"  - 加载供应链边: {len(self.edges)} 条")
        print(f"  - 加载GB规则: {len(self.gb_rules)} 条")

    def _load_all_data(self):
        """加载所有数据"""
        self.enterprises = self._load_csv("enterprise_master.csv")
        self.batches = self._load_csv("batch_records.csv")
        self.inspections = self._load_csv("inspection_records.csv")
        self.events = self._load_csv("regulatory_events.csv")
        self.edges = self._load_csv("supply_edges.csv")
        self.gb_rules = self._load_csv("gb_rules.csv")

    def _load_csv(self, filename: str) -> list[dict]:
        """加载CSV文件"""
        filepath = self.data_dir / filename
        if not filepath.exists():
            return []

        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)

    def _build_indices(self):
        """构建索引"""
        # 企业索引
        self.enterprise_by_id = {e["enterprise_id"]: e for e in self.enterprises}
        self.enterprises_by_name = {e["enterprise_name"]: e for e in self.enterprises}

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

    def find_enterprise(self, enterprise_id: Optional[str] = None,
                       enterprise_name: Optional[str] = None) -> Optional[dict]:
        """
        查找企业信息

        Args:
            enterprise_id: 企业ID
            enterprise_name: 企业名称

        Returns:
            企业信息字典或None
        """
        if enterprise_id and enterprise_id in self.enterprise_by_id:
            return self.enterprise_by_id[enterprise_id]

        if enterprise_name and enterprise_name in self.enterprises_by_name:
            return self.enterprises_by_name[enterprise_name]

        # 尝试模糊匹配
        if enterprise_name:
            for name, ent in self.enterprises_by_name.items():
                if enterprise_name in name or name in enterprise_name:
                    return ent

        return None

    def find_batch(self, batch_id: Optional[str] = None,
                  batch_no: Optional[str] = None) -> Optional[dict]:
        """
        查找批次信息

        Args:
            batch_id: 批次ID
            batch_no: 批次号

        Returns:
            批次信息字典或None
        """
        if batch_id and batch_id in self.batch_by_id:
            return self.batch_by_id[batch_id]

        if batch_no:
            for b in self.batches:
                if b.get("batch_no") == batch_no:
                    return b

        return None

    def get_related_batches(self, enterprise_id: str) -> list[dict]:
        """获取企业相关的所有批次"""
        return self.batches_by_enterprise.get(enterprise_id, [])

    def get_inspections(self, batch_id: Optional[str] = None,
                       enterprise_id: Optional[str] = None) -> list[dict]:
        """获取检验记录"""
        if batch_id:
            return self.inspections_by_batch.get(batch_id, [])
        if enterprise_id:
            return self.inspections_by_enterprise.get(enterprise_id, [])
        return []

    def get_regulatory_events(self, enterprise_id: str) -> list[dict]:
        """获取监管事件"""
        return self.events_by_enterprise.get(enterprise_id, [])

    def get_supply_chain(self, enterprise_id: str) -> dict:
        """
        获取供应链关系

        Returns:
            {"upstream": [...], "downstream": [...]}
        """
        return {
            "upstream": self.edges_to.get(enterprise_id, []),
            "downstream": self.edges_from.get(enterprise_id, [])
        }

    def get_gb_rules(self, product_type: Optional[str] = None) -> list[dict]:
        """获取GB标准规则"""
        if product_type:
            return [r for r in self.gb_rules
                   if r.get("product_type") in [product_type, "all"]]
        return self.gb_rules

    def search_enterprise_candidates(self, query: str, top_k: int = 3) -> list[dict]:
        """
        使用分词关键词搜索企业候选

        Args:
            query: 查询字符串
            top_k: 返回的最大候选数

        Returns:
            按匹配分数排序的企业候选列表
        """
        import re

        # 提取查询中的关键词（2字以上的词）
        keywords = set()
        for match in re.findall(r'[\u4e00-\u9fa5]{2,}|[a-zA-Z]{2,}|\d+', query):
            if len(match) >= 2:
                keywords.add(match.lower() if match.isascii() else match)

        if not keywords:
            return []

        candidates = []
        for ent in self.enterprises:
            score = 0
            name = ent.get("enterprise_name", "")
            name_lower = name.lower() if name else ""

            # 计算关键词匹配分数
            for kw in keywords:
                if kw in name_lower or kw in name:
                    score += 10  # 企业名完全匹配
                # 部分匹配（如"光明"匹配"光明乳业"）
                elif len(kw) >= 2 and (kw in name or any(kw in part for part in name.split())):
                    score += 5

            if score > 0:
                candidates.append({
                    "enterprise": ent,
                    "score": score,
                    "matched_keywords": [k for k in keywords if k in name or k in name_lower]
                })

        # 按分数排序
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:top_k]

    def search_batch_candidates(self, query: str, top_k: int = 3) -> list[dict]:
        """
        使用分词关键词搜索批次候选

        Args:
            query: 查询字符串
            top_k: 返回的最大候选数

        Returns:
            按匹配分数排序的批次候选列表
        """
        import re

        # 提取查询中的关键词
        keywords = set()
        for match in re.findall(r'[\u4e00-\u9fa5]{2,}|[a-zA-Z]{2,}|\d+', query):
            if len(match) >= 2:
                keywords.add(match.lower() if match.isascii() else match)

        if not keywords:
            return []

        candidates = []
        for batch in self.batches:
            score = 0
            product_name = batch.get("product_name", "")
            batch_id = batch.get("batch_id", "")
            batch_no = batch.get("batch_no", "")

            product_lower = product_name.lower() if product_name else ""

            # 产品名匹配
            for kw in keywords:
                if kw in product_lower or kw in product_name:
                    score += 10
                elif len(kw) >= 2 and (kw in product_name or any(kw in part for part in product_name.split())):
                    score += 5

            # 批次ID/号精确匹配（如果查询包含ID模式）
            if query.upper() in batch_id or query in batch_no:
                score += 20

            if score > 0:
                # 获取企业信息
                ent = self.enterprise_by_id.get(batch.get("enterprise_id", ""), {})
                candidates.append({
                    "batch": batch,
                    "enterprise": ent,
                    "score": score,
                    "matched_keywords": [k for k in keywords if k in product_name or k in product_lower]
                })

        # 按分数排序
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:top_k]

    def trace_supply_chain(self, batch_id: str, direction: str = "both") -> dict:
        """
        追溯供应链路径

        Args:
            batch_id: 批次ID
            direction: 追溯方向 (upstream/downstream/both)

        Returns:
            追溯路径信息
        """
        batch = self.batch_by_id.get(batch_id)
        if not batch:
            return {}

        enterprise_id = batch["enterprise_id"]
        result = {
            "batch": batch,
            "production_enterprise": self.enterprise_by_id.get(enterprise_id),
            "upstream": [],
            "downstream": []
        }

        # 原料供应商
        raw_supplier_id = batch.get("raw_material_supplier_id")
        if raw_supplier_id:
            supplier = self.enterprise_by_id.get(raw_supplier_id)
            if supplier:
                result["upstream"].append({
                    "type": "raw_material_supplier",
                    "enterprise": supplier,
                    "batch": batch.get("raw_material_batch")
                })

        # 供应链边
        if direction in ["upstream", "both"]:
            edges = self.edges_to.get(enterprise_id, [])
            for edge in edges:
                supplier = self.enterprise_by_id.get(edge["source_id"])
                if supplier:
                    result["upstream"].append({
                        "type": edge.get("edge_type"),
                        "enterprise": supplier,
                        "edge": edge
                    })

        if direction in ["downstream", "both"]:
            edges = self.edges_from.get(enterprise_id, [])
            for edge in edges:
                customer = self.enterprise_by_id.get(edge["target_id"])
                if customer:
                    result["downstream"].append({
                        "type": edge.get("edge_type"),
                        "enterprise": customer,
                        "edge": edge
                    })

        return result
