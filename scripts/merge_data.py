#!/usr/bin/env python3
"""
数据合并脚本

合并真实数据(real)和模拟数据(mock)，生成统一的merged数据集
- 保留data_source标记
- 处理ID冲突（真实数据优先）
- 去重
"""

import csv
import json
from pathlib import Path
from typing import List, Dict, Set
from collections import OrderedDict


class DataMerger:
    """数据合并器"""

    def __init__(self, mock_dir: Path = None, real_dir: Path = None, output_dir: Path = None):
        """初始化"""
        if mock_dir is None:
            mock_dir = Path(__file__).parent.parent / "data" / "mock"
        if real_dir is None:
            real_dir = Path(__file__).parent.parent / "data" / "real"
        if output_dir is None:
            output_dir = Path(__file__).parent.parent / "data" / "merged"

        self.mock_dir = Path(mock_dir)
        self.real_dir = Path(real_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        print(f"✓ 数据合并器初始化完成")
        print(f"  - 模拟数据: {self.mock_dir}")
        print(f"  - 真实数据: {self.real_dir}")
        print(f"  - 输出目录: {self.output_dir}")

    def load_csv(self, filepath: Path) -> List[Dict]:
        """加载CSV文件"""
        if not filepath.exists():
            return []

        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)

    def save_csv(self, records: List[Dict], filename: str):
        """保存CSV文件"""
        if not records:
            print(f"  ⚠️ 无数据可保存: {filename}")
            return

        filepath = self.output_dir / filename

        # 统一字段名（处理BOM和多余字段）
        # 清理BOM
        for r in records:
            for key in list(r.keys()):
                clean_key = key.replace('\ufeff', '')
                if clean_key != key:
                    r[clean_key] = r.pop(key)

        # 获取所有字段
        all_fields = set()
        for r in records:
            all_fields.update(r.keys())

        # 排序字段，标准字段在前
        standard_first = ['enterprise_id', 'batch_id', 'inspection_id', 'event_id', 'edge_id', 'rule_id',
                         'enterprise_name', 'product_name', 'batch_no', 'data_source']
        ordered_fields = []
        for f in standard_first:
            if f in all_fields:
                ordered_fields.append(f)
        for f in sorted(all_fields):
            if f not in ordered_fields:
                ordered_fields.append(f)

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=ordered_fields)
            writer.writeheader()
            writer.writerows(records)

        print(f"  ✓ 保存: {filename} ({len(records)} 条)")

    def merge_enterprise_data(self) -> List[Dict]:
        """合并企业数据"""
        print("\n" + "="*60)
        print("合并企业数据")
        print("="*60)

        mock_data = self.load_csv(self.mock_dir / "enterprise_master.csv")
        real_data = self.load_csv(self.real_dir / "enterprise_master_real.csv")

        # 添加data_source标记
        for r in mock_data:
            r["data_source"] = "mock"
        for r in real_data:
            r.setdefault("data_source", "real")

        # 合并（真实数据优先）
        merged = {}

        # 先加入模拟数据
        for r in mock_data:
            merged[r["enterprise_id"]] = r

        # 再加入真实数据（覆盖）
        for idx, r in enumerate(real_data):
            # 生成新ID避免冲突
            orig_id = r.get('enterprise_id', f'ENT-REAL-{idx:04d}')
            new_id = f"{orig_id}-R"
            r["enterprise_id"] = new_id
            merged[new_id] = r

        print(f"  模拟数据: {len(mock_data)} 条")
        print(f"  真实数据: {len(real_data)} 条")
        print(f"  合并后: {len(merged)} 条")

        return list(merged.values())

    def merge_batch_data(self) -> List[Dict]:
        """合并批次数据"""
        print("\n" + "="*60)
        print("合并批次数据")
        print("="*60)

        mock_data = self.load_csv(self.mock_dir / "batch_records.csv")
        real_data = self.load_csv(self.real_dir / "batch_records_real.csv")

        # 添加data_source标记
        for r in mock_data:
            r["data_source"] = "mock"
        for r in real_data:
            r.setdefault("data_source", "real")

        # 合并
        merged = {}

        for r in mock_data:
            merged[r["batch_id"]] = r

        for idx, r in enumerate(real_data):
            orig_id = r.get('batch_id', f'BATCH-REAL-{idx:04d}')
            new_id = f"{orig_id}-R"
            r["batch_id"] = new_id
            merged[new_id] = r

        print(f"  模拟数据: {len(mock_data)} 条")
        print(f"  真实数据: {len(real_data)} 条")
        print(f"  合并后: {len(merged)} 条")

        return list(merged.values())

    def merge_inspection_data(self) -> List[Dict]:
        """合并检验数据"""
        print("\n" + "="*60)
        print("合并检验数据")
        print("="*60)

        mock_data = self.load_csv(self.mock_dir / "inspection_records.csv")
        real_data = self.load_csv(self.real_dir / "inspection_records_real.csv")

        # 添加data_source标记
        for r in mock_data:
            r["data_source"] = "mock"
        for r in real_data:
            r.setdefault("data_source", "real")

        # 清理真实数据中的内部字段
        for r in real_data:
            r.pop("_raw_enterprise_name", None)
            r.pop("_raw_product_name", None)
            r.pop("_raw_batch_info", None)

        # 合并
        merged = {}

        for r in mock_data:
            merged[r["inspection_id"]] = r

        for idx, r in enumerate(real_data):
            orig_id = r.get('inspection_id', f'INS-REAL-{idx:04d}')
            new_id = f"{orig_id}-R"
            r["inspection_id"] = new_id
            merged[new_id] = r

        print(f"  模拟数据: {len(mock_data)} 条")
        print(f"  真实数据: {len(real_data)} 条")
        print(f"  合并后: {len(merged)} 条")

        return list(merged.values())

    def merge_regulatory_data(self) -> List[Dict]:
        """合并监管事件数据"""
        print("\n" + "="*60)
        print("合并监管事件数据")
        print("="*60)

        mock_data = self.load_csv(self.mock_dir / "regulatory_events.csv")
        real_data = self.load_csv(self.real_dir / "regulatory_events_real.csv")

        # 添加data_source标记
        for r in mock_data:
            r["data_source"] = "mock"
        for r in real_data:
            r.setdefault("data_source", "real")

        # 合并
        merged = {}

        for r in mock_data:
            merged[r["event_id"]] = r

        for idx, r in enumerate(real_data):
            orig_id = r.get('event_id', f'EVT-REAL-{idx:04d}')
            new_id = f"{orig_id}-R"
            r["event_id"] = new_id
            merged[new_id] = r

        print(f"  模拟数据: {len(mock_data)} 条")
        print(f"  真实数据: {len(real_data)} 条")
        print(f"  合并后: {len(merged)} 条")

        return list(merged.values())

    def merge_edge_data(self) -> List[Dict]:
        """合并供应链边数据"""
        print("\n" + "="*60)
        print("合并供应链边数据")
        print("="*60)

        mock_data = self.load_csv(self.mock_dir / "supply_edges.csv")
        real_data = self.load_csv(self.real_dir / "supply_edges_real.csv")

        # 添加data_source标记
        for r in mock_data:
            r["data_source"] = "mock"
        for r in real_data:
            r.setdefault("data_source", "real")

        # 合并
        merged = {}

        for r in mock_data:
            merged[r["edge_id"]] = r

        for idx, r in enumerate(real_data):
            orig_id = r.get('edge_id', f'EDGE-REAL-{idx:04d}')
            new_id = f"{orig_id}-R"
            r["edge_id"] = new_id
            merged[new_id] = r

        print(f"  模拟数据: {len(mock_data)} 条")
        print(f"  真实数据: {len(real_data)} 条")
        print(f"  合并后: {len(merged)} 条")

        return list(merged.values())

    def merge_gb_rules(self) -> List[Dict]:
        """合并GB规则（直接使用现有的）"""
        print("\n" + "="*60)
        print("合并GB规则")
        print("="*60)

        # GB规则直接使用mock中的
        mock_data = self.load_csv(self.mock_dir / "gb_rules.csv")

        for r in mock_data:
            r["data_source"] = "standard"

        print(f"  GB规则: {len(mock_data)} 条")

        return mock_data

    def generate_data_summary(self, all_data: Dict[str, List[Dict]]):
        """生成数据汇总报告"""
        print("\n" + "="*60)
        print("生成数据汇总")
        print("="*60)

        summary = {
            "generated_at": str(Path(__file__).stat().st_mtime),
            "tables": {}
        }

        for table_name, records in all_data.items():
            source_counts = {}
            for r in records:
                source = r.get("data_source", "unknown")
                source_counts[source] = source_counts.get(source, 0) + 1

            summary["tables"][table_name] = {
                "total": len(records),
                "by_source": source_counts
            }

        # 保存汇总
        summary_path = self.output_dir / "data_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"  ✓ 汇总保存: {summary_path}")

        # 打印摘要
        print("\n  数据汇总:")
        for table_name, info in summary["tables"].items():
            print(f"    {table_name}: {info['total']} 条")
            for source, count in info['by_source'].items():
                print(f"      - {source}: {count} 条")

    def run(self):
        """执行合并"""
        print("="*60)
        print("开始合并数据")
        print("="*60)

        # 合并各表
        enterprises = self.merge_enterprise_data()
        batches = self.merge_batch_data()
        inspections = self.merge_inspection_data()
        events = self.merge_regulatory_data()
        edges = self.merge_edge_data()
        gb_rules = self.merge_gb_rules()

        # 保存
        print("\n" + "="*60)
        print("保存合并后的数据")
        print("="*60)

        self.save_csv(enterprises, "enterprise_master.csv")
        self.save_csv(batches, "batch_records.csv")
        self.save_csv(inspections, "inspection_records.csv")
        self.save_csv(events, "regulatory_events.csv")
        self.save_csv(edges, "supply_edges.csv")
        self.save_csv(gb_rules, "gb_rules.csv")

        # 生成汇总
        all_data = {
            "enterprise_master": enterprises,
            "batch_records": batches,
            "inspection_records": inspections,
            "regulatory_events": events,
            "supply_edges": edges,
            "gb_rules": gb_rules
        }
        self.generate_data_summary(all_data)

        print("\n" + "="*60)
        print("合并完成")
        print("="*60)
        print(f"数据位置: {self.output_dir}")


def main():
    """主函数"""
    merger = DataMerger()
    merger.run()


if __name__ == "__main__":
    main()
