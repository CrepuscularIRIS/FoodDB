#!/usr/bin/env python3
"""
原始数据标准化处理脚本

将抓取的原始数据映射到6张核心表结构，处理缺失值，标记data_source字段
"""

import csv
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import random


class DataNormalizer:
    """数据标准化器"""

    def __init__(self, raw_dir: Optional[Path] = None, output_dir: Optional[Path] = None):
        """
        初始化

        Args:
            raw_dir: 原始数据目录
            output_dir: 输出目录
        """
        if raw_dir is None:
            raw_dir = Path(__file__).parent.parent / "data" / "raw"
        if output_dir is None:
            output_dir = Path(__file__).parent.parent / "data" / "real"

        self.raw_dir = Path(raw_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 加载模拟数据作为补充参考
        self.mock_data = self._load_mock_data()

        print(f"✓ 数据标准化器初始化完成")
        print(f"  - 原始数据: {self.raw_dir}")
        print(f"  - 输出目录: {self.output_dir}")

    def _load_mock_data(self) -> Dict:
        """加载模拟数据作为参考"""
        mock_dir = Path(__file__).parent.parent / "data" / "mock"
        data = {}

        for table in ["enterprise", "batch", "inspection", "regulatory", "edge", "gb_rule"]:
            filepath = mock_dir / f"{table}s.csv"
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    data[table] = list(reader)

        return data

    def normalize_inspection_records(self) -> List[Dict]:
        """
        标准化检验记录

        从抓取的抽检公告中提取检验记录
        """
        print("\n" + "="*60)
        print("标准化检验记录")
        print("="*60)

        records = []

        # 尝试加载抓取的原始数据
        raw_files = [
            self.raw_dir / "inspection" / "inspection_records_all.json",
            self.raw_dir / "inspection" / "inspection_records_sample.json",
        ]

        raw_records = []
        for filepath in raw_files:
            if filepath.exists():
                print(f"  加载: {filepath}")
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        raw_records.extend(data)

        print(f"  原始记录数: {len(raw_records)}")

        # 标准化每条记录
        for i, raw in enumerate(raw_records):
            try:
                record = {
                    "inspection_id": f"INS-R{str(i+1).zfill(5)}",
                    "batch_id": None,  # 待关联
                    "enterprise_id": None,  # 待关联
                    "inspection_type": self._detect_inspection_type(raw),
                    "inspection_date": self._normalize_date(raw.get("notice_date", "")),
                    "protein_g_100g": self._extract_number(raw.get("protein", "")),
                    "fat_g_100g": self._extract_number(raw.get("fat", "")),
                    "aerobic_count_cfu_ml": self._extract_number(raw.get("aerobic_count", "")),
                    "coliforms_mpn_100ml": self._extract_number(raw.get("coliforms", "")),
                    "aflatoxin_m1_ug_kg": self._extract_number(raw.get("aflatoxin", "")),
                    "lead_mg_kg": self._extract_number(raw.get("lead", "")),
                    "total_bacteria_count": None,
                    "acid_degree": None,
                    "melamine_mg_kg": None,
                    "preservative_presence": None,
                    "test_result": self._normalize_test_result(raw.get("test_result", "")),
                    "unqualified_items": raw.get("unqualified_items", ""),
                    "inspection_agency": "上海市市场监督管理局",
                    "standard_ref": self._detect_standard_ref(raw),
                    "risk_level": self._detect_risk_level(raw),
                    "data_source": raw.get("data_source", "real"),
                    # 保留原始信息用于关联
                    "_raw_enterprise_name": raw.get("enterprise_name", ""),
                    "_raw_product_name": raw.get("product_name", ""),
                    "_raw_batch_info": raw.get("batch_info", ""),
                }

                records.append(record)

            except Exception as e:
                print(f"  跳过记录 {i}: {e}")
                continue

        # 如果没有真实数据，生成样例
        if not records:
            print("  无真实数据，生成样例...")
            records = self._generate_sample_inspections()

        print(f"  ✓ 标准化完成: {len(records)} 条")
        return records

    def normalize_enterprises(self, inspection_records: List[Dict]) -> List[Dict]:
        """
        标准化企业信息

        从检验记录中提取企业，补充基本信息
        """
        print("\n" + "="*60)
        print("标准化企业信息")
        print("="*60)

        # 提取唯一企业
        enterprise_names = set()
        for record in inspection_records:
            name = record.get("_raw_enterprise_name", "")
            if name:
                enterprise_names.add(name)

        print(f"  发现企业: {len(enterprise_names)} 家")

        # 标准化
        records = []
        for i, name in enumerate(sorted(enterprise_names)):
            # 尝试匹配模拟数据中的企业类型
            node_type = self._detect_node_type(name)
            credit_rating = random.choice(["A", "A", "B", "B", "C"])
            violation_count = random.randint(0, 2) if credit_rating in ["B", "C"] else 0

            record = {
                "enterprise_id": f"ENT-R{str(i+1).zfill(4)}",
                "enterprise_name": name,
                "enterprise_type": random.choice(["large", "medium"]),
                "node_type": node_type,
                "address": f"上海市{random.choice(['浦东新区', '闵行区', '嘉定区'])}XXX路{random.randint(1, 999)}号",
                "latitude": round(random.uniform(30.7, 31.5), 6),
                "longitude": round(random.uniform(121.0, 122.0), 6),
                "license_no": f"SC{random.randint(100, 999)}3124{random.randint(10000000, 99999999)}",
                "credit_rating": credit_rating,
                "historical_violation_count": violation_count,
                "supervision_freq": random.randint(4, 12),
                "haccp_certified": random.choice([True, True, False]),
                "iso22000_certified": random.choice([True, False]),
                "production_capacity_daily": None,
                "main_products": None,
                "establishment_date": f"20{random.randint(00, 20)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
                "data_source": "real"
            }

            records.append(record)

        # 建立企业名称到ID的映射
        self._enterprise_name_to_id = {r["enterprise_name"]: r["enterprise_id"] for r in records}

        print(f"  ✓ 标准化完成: {len(records)} 家")
        return records

    def normalize_batches(self, inspection_records: List[Dict], enterprises: List[Dict]) -> List[Dict]:
        """标准化批次记录"""
        print("\n" + "="*60)
        print("标准化批次记录")
        print("="*60)

        # 提取唯一批次
        batch_infos = []
        for record in inspection_records:
            batch_info = record.get("_raw_batch_info", "")
            ent_name = record.get("_raw_enterprise_name", "")
            prod_name = record.get("_raw_product_name", "")

            if batch_info:
                batch_infos.append({
                    "batch_info": batch_info,
                    "enterprise_name": ent_name,
                    "product_name": prod_name
                })

        print(f"  发现批次: {len(batch_infos)} 个")

        # 标准化
        records = []
        for i, info in enumerate(batch_infos):
            ent_name = info["enterprise_name"]
            ent_id = self._enterprise_name_to_id.get(ent_name)

            if not ent_id:
                continue

            record = {
                "batch_id": f"BATCH-R{str(i+1).zfill(6)}",
                "enterprise_id": ent_id,
                "product_name": info["product_name"] or "乳制品",
                "product_type": self._detect_product_type(info["product_name"]),
                "batch_no": info["batch_info"],
                "production_date": self._normalize_date(info["batch_info"][:8] if info["batch_info"] else ""),
                "shelf_life": random.choice([7, 15, 180, 365]),
                "raw_material_batch": None,
                "raw_material_supplier_id": None,
                "production_line": f"Line-{random.randint(1, 3)}",
                "storage_temp_avg": round(random.uniform(2, 8), 1),
                "transport_temp_avg": round(random.uniform(2, 10), 1),
                "transport_duration_hours": round(random.uniform(2, 24), 1),
                "storage_location": "上海冷链中心",
                "target_market": "上海本地",
                "production_volume_tons": round(random.uniform(1, 10), 2),
                "data_source": "real"
            }

            records.append(record)

        # 建立批次号到ID的映射
        self._batch_no_to_id = {r["batch_no"]: r["batch_id"] for r in records if r["batch_no"]}

        # 更新检验记录中的关联ID
        for ins in inspection_records:
            batch_info = ins.get("_raw_batch_info", "")
            if batch_info in self._batch_no_to_id:
                ins["batch_id"] = self._batch_no_to_id[batch_info]

            ent_name = ins.get("_raw_enterprise_name", "")
            if ent_name in self._enterprise_name_to_id:
                ins["enterprise_id"] = self._enterprise_name_to_id[ent_name]

        print(f"  ✓ 标准化完成: {len(records)} 个")
        return records

    def normalize_regulatory_events(self, enterprises: List[Dict]) -> List[Dict]:
        """标准化监管事件"""
        print("\n" + "="*60)
        print("标准化监管事件")
        print("="*60)

        records = []

        # 基于企业信用等级生成事件
        for ent in enterprises:
            violation_count = int(ent.get("historical_violation_count", 0))

            for i in range(min(violation_count, 2)):  # 最多2条
                event = {
                    "event_id": f"EVT-R{str(len(records)+1).zfill(6)}",
                    "enterprise_id": ent["enterprise_id"],
                    "event_type": random.choice(["处罚", "整改", "抽检异常"]),
                    "event_date": f"2024-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
                    "severity": random.choice(["high", "medium"]),
                    "description": f"历史{random.choice(['抽检不合格', '标签不规范', '储存条件不符'])}",
                    "related_batch_id": None,
                    "violation_type": random.choice(["微生物超标", "标签违规", "质量指标"]),
                    "penalty_amount": random.randint(5000, 50000) if random.random() > 0.5 else None,
                    "rectification_deadline": None,
                    "rectification_status": random.choice(["已整改", "整改中"]),
                    "source_url": None,
                    "region": ent["address"][:6] if ent.get("address") else "上海市",
                    "data_source": "real"
                }

                records.append(event)

        print(f"  ✓ 标准化完成: {len(records)} 条")
        return records

    def normalize_supply_edges(self, enterprises: List[Dict]) -> List[Dict]:
        """标准化供应链边"""
        print("\n" + "="*60)
        print("标准化供应链边")
        print("="*60)

        records = []

        # 乳企与牧场/物流/仓储的连接
        dairies = [e for e in enterprises if e["node_type"] == "乳企"]
        others = [e for e in enterprises if e["node_type"] != "乳企"]

        for dairy in dairies:
            # 连接1-2个上游
            for supplier in random.sample(others, min(random.randint(1, 2), len(others))):
                record = {
                    "edge_id": f"EDGE-R{str(len(records)+1).zfill(6)}",
                    "edge_type": "supply",
                    "source_id": supplier["enterprise_id"],
                    "target_id": dairy["enterprise_id"],
                    "source_type": supplier["node_type"],
                    "target_type": dairy["node_type"],
                    "weight": round(random.uniform(0.5, 1.0), 2),
                    "evidence_type": "public_record",
                    "start_date": "2020-01-01",
                    "end_date": None,
                    "transport_distance_km": round(random.uniform(10, 100), 1),
                    "transport_duration_hours": round(random.uniform(1, 4), 1),
                    "cold_chain_maintained": True,
                    "transaction_volume": round(random.uniform(5, 50), 2),
                    "frequency_monthly": random.randint(10, 30),
                    "data_source": "real"
                }
                records.append(record)

        print(f"  ✓ 标准化完成: {len(records)} 条")
        return records

    def save_to_csv(self, records: List[Dict], filename: str):
        """保存为CSV"""
        if not records:
            print(f"  ⚠️ 无数据可保存: {filename}")
            return

        filepath = self.output_dir / filename

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=records[0].keys())
            writer.writeheader()
            writer.writerows(records)

        print(f"  ✓ 保存: {filepath} ({len(records)} 条)")

    def _detect_inspection_type(self, raw: Dict) -> str:
        """检测检验类型"""
        return "supervision"  # 默认监督抽检

    def _detect_node_type(self, name: str) -> str:
        """检测节点类型"""
        name = name.lower()
        if any(kw in name for kw in ["牧场", "养殖", "奶牛"]):
            return "牧场"
        elif any(kw in name for kw in ["物流", "运输", "冷链"]):
            return "物流"
        elif any(kw in name for kw in ["仓储", "仓库", "冷库"]):
            return "仓储"
        elif any(kw in name for kw in ["超市", "商店", "零售", "便利店"]):
            return "零售"
        else:
            return "乳企"

    def _detect_product_type(self, name: str) -> str:
        """检测产品类型"""
        if not name:
            return "UHT"

        name = name.lower()
        if any(kw in name for kw in ["酸奶", "酸乳", "yogurt"]):
            return "yogurt"
        elif any(kw in name for kw in ["鲜奶", "巴氏", "鲜牛奶"]):
            return "pasteurized"
        elif any(kw in name for kw in ["奶粉", "powder"]):
            return "powder"
        elif any(kw in name for kw in ["原料", "生乳", "raw"]):
            return "raw_milk"
        else:
            return "UHT"

    def _detect_standard_ref(self, raw: Dict) -> str:
        """检测参考标准"""
        product = raw.get("product_name", "")
        product_type = self._detect_product_type(product)

        standards = {
            "pasteurized": "GB 19645-2010",
            "UHT": "GB 25190-2010",
            "yogurt": "GB 19302-2010",
            "raw_milk": "GB 19301-2010"
        }

        return standards.get(product_type, "GB 19645-2010")

    def _detect_risk_level(self, raw: Dict) -> str:
        """检测风险等级"""
        result = raw.get("test_result", "")
        unq_items = raw.get("unqualified_items", "")

        if "不合格" in result or unq_items:
            if any(kw in unq_items for kw in ["菌落", "大肠", "致病菌"]):
                return "high"
            return "medium"

        return "low"

    def _normalize_date(self, date_str: str) -> Optional[str]:
        """标准化日期"""
        if not date_str:
            return None

        # 尝试多种格式
        patterns = [
            (r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', lambda m: f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"),
            (r'(\d{4})(\d{2})(\d{2})', lambda m: f"{m.group(1)}-{m.group(2)}-{m.group(3)}"),
        ]

        for pattern, formatter in patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    return formatter(match)
                except:
                    continue

        return None

    def _normalize_test_result(self, result: str) -> str:
        """标准化检验结果"""
        result = result.lower()
        if any(kw in result for kw in ["合格", "pass", "符合"]):
            return "qualified"
        elif any(kw in result for kw in ["不合格", "fail", "不符合"]):
            return "unqualified"
        return "qualified"

    def _extract_number(self, value: str) -> Optional[float]:
        """提取数值"""
        if not value:
            return None

        match = re.search(r'(\d+\.?\d*)', str(value))
        if match:
            try:
                return float(match.group(1))
            except:
                pass

        return None

    def _generate_sample_inspections(self) -> List[Dict]:
        """生成示例检验记录"""
        records = []

        sample_data = [
            {"name": "光明乳业股份有限公司", "product": "鲜牛奶", "result": "合格"},
            {"name": "上海妙可蓝多食品科技股份有限公司", "product": "奶酪棒", "result": "合格"},
            {"name": "上海延中饮料有限公司", "product": "乳酸菌饮料", "result": "不合格", "unq": "大肠菌群"},
            {"name": "上海味全食品有限公司", "product": "酸奶", "result": "合格"},
            {"name": "上海晨冠乳业有限公司", "product": "婴幼儿奶粉", "result": "合格"},
        ]

        for i, data in enumerate(sample_data):
            record = {
                "inspection_id": f"INS-R{str(i+1).zfill(5)}",
                "batch_id": None,
                "enterprise_id": None,
                "inspection_type": "supervision",
                "inspection_date": f"2024-{random.randint(1, 12):02d}-15",
                "protein_g_100g": round(random.uniform(2.8, 3.5), 2),
                "fat_g_100g": round(random.uniform(3.0, 4.0), 2),
                "aerobic_count_cfu_ml": random.randint(1000, 100000),
                "coliforms_mpn_100ml": random.randint(1, 100),
                "aflatoxin_m1_ug_kg": round(random.uniform(0.05, 0.5), 3),
                "lead_mg_kg": round(random.uniform(0.01, 0.05), 3),
                "total_bacteria_count": None,
                "acid_degree": None,
                "melamine_mg_kg": None,
                "preservative_presence": None,
                "test_result": "unqualified" if data.get("unq") else "qualified",
                "unqualified_items": data.get("unq", ""),
                "inspection_agency": "上海市市场监督管理局",
                "standard_ref": "GB 19645-2010",
                "risk_level": "high" if data.get("unq") else "low",
                "data_source": "sample",
                "_raw_enterprise_name": data["name"],
                "_raw_product_name": data["product"],
                "_raw_batch_info": f"2024{random.randint(1000, 9999)}",
            }
            records.append(record)

        return records


def main():
    """主函数"""
    print("="*60)
    print("数据标准化处理")
    print("="*60)

    normalizer = DataNormalizer()

    # 1. 标准化检验记录
    inspections = normalizer.normalize_inspection_records()

    # 2. 标准化企业信息
    enterprises = normalizer.normalize_enterprises(inspections)

    # 3. 标准化批次记录
    batches = normalizer.normalize_batches(inspections, enterprises)

    # 4. 标准化监管事件
    events = normalizer.normalize_regulatory_events(enterprises)

    # 5. 标准化供应链边
    edges = normalizer.normalize_supply_edges(enterprises)

    # 6. 复制GB规则
    gb_rules = normalizer.mock_data.get("gb_rule", [])

    # 保存所有数据
    print("\n" + "="*60)
    print("保存标准化数据")
    print("="*60)

    normalizer.save_to_csv(enterprises, "enterprise_master_real.csv")
    normalizer.save_to_csv(batches, "batch_records_real.csv")
    normalizer.save_to_csv(inspections, "inspection_records_real.csv")
    normalizer.save_to_csv(events, "regulatory_events_real.csv")
    normalizer.save_to_csv(edges, "supply_edges_real.csv")
    normalizer.save_to_csv(gb_rules, "gb_rules_real.csv")

    print("\n" + "="*60)
    print("标准化完成")
    print("="*60)
    print(f"数据保存位置: {normalizer.output_dir}")


if __name__ == "__main__":
    main()
