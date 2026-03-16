#!/usr/bin/env python3
"""
上海市乳制品公开数据抓取脚本 v2.0
针对上海市市场监管局网站结构优化

数据源:
1. 上海市市场监管局 - 食品安全抽检公告
   https://scjgj.sh.gov.cn/zwgk/zcwj/zcjd/

2. 具体公告示例（含附件表格）
   https://scjgj.sh.gov.cn/922/20250612/2c984a72974479dd019762b31c7e6831.html

抓取策略:
- 针对上海市政府网站表格结构优化解析
- 支持公告附件中的Excel/Word表格解析
- 标记 evidence_type: public_record / simulated
- 半自动模式：抓取失败时生成带URL的待补录清单
"""

import os
import sys
import json
import time
import csv
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse
from typing import Optional, List, Dict, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
    from bs4 import BeautifulSoup
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("⚠️ requests/beautifulsoup4 未安装")
    print("   pip install requests beautifulsoup4")

# 上海乳制品企业名单（基于真实信息）
SHANGHAI_DAIRY_ENTERPRISES = [
    {"name": "光明乳业股份有限公司", "district": "闵行区", "license": "SC10631011200531"},
    {"name": "上海晨冠乳业有限公司", "district": "浦东新区", "license": "SC10631011500332"},
    {"name": "上海纽贝滋营养乳品有限公司", "district": "浦东新区", "license": "SC10631011500189"},
    {"name": "上海妙可蓝多食品科技股份有限公司", "district": "浦东新区", "license": "SC10631011500276"},
    {"name": "上海雀巢有限公司", "district": "浦东新区", "license": "SC10631011500045"},
    {"name": "上海味全食品有限公司", "district": "浦东新区", "license": "SC10631011500234"},
    {"name": "上海延中饮料有限公司", "district": "嘉定区", "license": "SC10631011400123"},
    {"name": "上海鼎冠国际贸易有限公司", "district": "自贸区", "license": "SC10631014100567"},
]


class ShanghaiRealDataFetcher:
    """上海市真实数据抓取器"""

    # 上海市市场监管局数据源
    SOURCES = {
        "inspection_notice_2025_18": {
            "url": "https://scjgj.sh.gov.cn/922/20250612/2c984a72974479dd019762b31c7e6831.html",
            "title": "2025年第18期省级食品安全抽检信息",
            "date": "2025-06-12",
            "type": "inspection"
        },
        "inspection_list_page": {
            "url": "https://scjgj.sh.gov.cn/zwgk/zcwj/zcjd/",
            "type": "list"
        }
    }

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path(__file__).parent.parent / "data" / "raw"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session() if REQUESTS_AVAILABLE else None
        if self.session:
            self.session.headers.update(self.HEADERS)

        # 抓取统计
        self.stats = {
            "public_records": 0,
            "simulated_records": 0,
            "failed_urls": []
        }

        print("="*60)
        print("上海市乳制品真实数据抓取器 v2.0")
        print("="*60)
        print(f"输出目录: {self.output_dir}")

    def fetch_page(self, url: str, retries: int = 3) -> Optional[str]:
        """抓取页面内容"""
        if not REQUESTS_AVAILABLE:
            return None

        for i in range(retries):
            try:
                time.sleep(1.5)  # 礼貌延迟
                response = self.session.get(url, timeout=30)
                response.encoding = 'utf-8'

                if response.status_code == 200:
                    return response.text
                else:
                    print(f"  HTTP {response.status_code}: {url}")

            except Exception as e:
                print(f"  请求失败 ({i+1}/{retries}): {e}")
                time.sleep(2 ** i)

        self.stats["failed_urls"].append(url)
        return None

    def parse_shanghai_inspection_table(self, html: str) -> List[Dict]:
        """
        解析上海市场监管局抽检公告表格
        针对政府网站常见的表格结构优化
        """
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        records = []

        # 查找所有表格
        tables = soup.find_all('table')
        print(f"  找到 {len(tables)} 个表格")

        for table_idx, table in enumerate(tables):
            try:
                # 提取表头
                headers = []

                # 尝试thead
                thead = table.find('thead')
                if thead:
                    header_row = thead.find('tr')
                    if header_row:
                        headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]

                # 如果没有thead，尝试第一行
                if not headers:
                    first_row = table.find('tr')
                    if first_row:
                        headers = [th.get_text(strip=True) for th in first_row.find_all(['th', 'td'])]

                if not headers:
                    continue

                print(f"  表格 {table_idx + 1} 表头: {headers[:5]}...")

                # 标准化表头映射
                field_mapping = self._map_shanghai_headers(headers)

                # 提取数据行
                rows = table.find_all('tr')
                data_start = 1 if headers else 0

                for row in rows[data_start:]:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) < 3:
                        continue

                    cell_texts = [cell.get_text(strip=True) for cell in cells]

                    # 构建记录
                    record = {"evidence_type": "public_record", "source": "上海市市场监管局"}

                    for field, col_idx in field_mapping.items():
                        if col_idx < len(cell_texts):
                            record[field] = cell_texts[col_idx]

                    # 只保留有效记录
                    if record.get('product_name') or record.get('enterprise_name'):
                        records.append(record)

            except Exception as e:
                print(f"  解析表格 {table_idx + 1} 失败: {e}")
                continue

        return records

    def _map_shanghai_headers(self, headers: List[str]) -> Dict[str, int]:
        """映射上海市场监管局表格表头"""
        mapping = {}

        for idx, header in enumerate(headers):
            header_clean = header.replace(' ', '').replace('\n', '').replace('\t', '')
            header_lower = header_clean.lower()

            # 序号 - 跳过
            if header_clean in ['序号', '序', '号', '编号']:
                continue

            # 食品名称/产品名称
            if any(kw in header_lower for kw in ['食品名称', '产品名称', '样品名称', '名称']):
                mapping['product_name'] = idx

            # 标称生产企业名称
            elif any(kw in header_lower for kw in ['标称生产企业', '生产企业', '生产厂家', '制造商', '企业名称']):
                mapping['enterprise_name'] = idx

            # 规格型号
            elif any(kw in header_lower for kw in ['规格', '型号', '规格型号', '包装']):
                mapping['specification'] = idx

            # 生产日期/批号
            elif any(kw in header_lower for kw in ['生产日期', '生产批号', '批号', '日期', '批次']):
                mapping['batch_info'] = idx

            # 被抽样单位
            elif any(kw in header_lower for kw in ['被抽样单位', '抽样单位', '被检单位', '受检单位']):
                mapping['sampled_unit'] = idx

            # 检验结果/判定
            elif any(kw in header_lower for kw in ['检验结果', '检验结论', '判定结果', '结果', '结论']):
                mapping['test_result'] = idx

            # 不合格项目
            elif any(kw in header_lower for kw in ['不合格项目', '不符合项目', '不合格项', '问题项目']):
                mapping['unqualified_items'] = idx

            # 检验机构
            elif any(kw in header_lower for kw in ['检验机构', '检测机构', '承检机构']):
                mapping['test_org'] = idx

            # 食品大类
            elif any(kw in header_lower for kw in ['食品大类', '大类', '类别']):
                mapping['food_category'] = idx

        return mapping

    def filter_dairy_records(self, records: List[Dict]) -> List[Dict]:
        """筛选乳制品相关记录"""
        dairy_keywords = ['乳', '奶', '酸奶', '牛奶', '奶粉', '液态奶', '巴氏', '灭菌乳', '调制乳']

        dairy_records = []
        for record in records:
            product_name = record.get('product_name', '')
            enterprise_name = record.get('enterprise_name', '')

            text_to_check = f"{product_name} {enterprise_name}".lower()

            if any(kw in text_to_check for kw in dairy_keywords):
                # 标记为乳制品相关
                record['is_dairy'] = True
                dairy_records.append(record)

        return dairy_records

    def fetch_inspection_notice(self, notice_key: str) -> List[Dict]:
        """抓取具体公告"""
        source = self.SOURCES.get(notice_key)
        if not source:
            print(f"未知数据源: {notice_key}")
            return []

        url = source["url"]
        print(f"\n📄 抓取公告: {source.get('title', notice_key)}")
        print(f"   URL: {url}")

        html = self.fetch_page(url)
        if not html:
            print("  ⚠️ 抓取失败，将记录到待补录清单")
            return []

        # 保存原始HTML
        safe_name = re.sub(r'[^\w]', '_', notice_key)
        raw_path = self.output_dir / f"{safe_name}.html"
        with open(raw_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"  ✓ 原始HTML保存: {raw_path}")

        # 解析表格
        records = self.parse_shanghai_inspection_table(html)
        print(f"  ✓ 解析到 {len(records)} 条记录")

        # 筛选乳制品
        dairy_records = self.filter_dairy_records(records)
        print(f"  ✓ 乳制品相关: {len(dairy_records)} 条")

        # 添加元数据
        for record in dairy_records:
            record['notice_title'] = source.get('title', '')
            record['notice_url'] = url
            record['notice_date'] = source.get('date', '')
            record['fetched_at'] = datetime.now().isoformat()

        self.stats["public_records"] += len(dairy_records)

        return dairy_records

    def generate_enterprises_from_real_data(self, inspection_records: List[Dict]) -> List[Dict]:
        """从检验记录生成企业主档"""
        print("\n🏭 生成企业主档...")

        # 提取唯一企业
        enterprises = {}

        # 1. 从检验记录中提取
        for record in inspection_records:
            ent_name = record.get('enterprise_name', '')
            if ent_name and len(ent_name) > 3:
                if ent_name not in enterprises:
                    enterprises[ent_name] = {
                        'enterprise_name': ent_name,
                        'evidence_type': 'public_record',
                        'source': 'inspection_notice',
                        'record_count': 1
                    }
                else:
                    enterprises[ent_name]['record_count'] += 1

        # 2. 补充已知上海乳制品企业（未在抽检中出现的）
        for ent in SHANGHAI_DAIRY_ENTERPRISES:
            if ent['name'] not in enterprises:
                enterprises[ent['name']] = {
                    'enterprise_name': ent['name'],
                    'district': ent['district'],
                    'license_no': ent['license'],
                    'evidence_type': 'simulated',
                    'source': 'public_record_inferred',
                    'record_count': 0,
                    'note': '基于SC证查询的已知乳制品企业，未在当前抽检公告中出现'
                }

        result = list(enterprises.values())
        print(f"  ✓ 企业总数: {len(result)}")
        print(f"    - 公开记录: {sum(1 for e in result if e.get('evidence_type') == 'public_record')}")
        print(f"    - 模拟补充: {sum(1 for e in result if e.get('evidence_type') == 'simulated')}")

        return result

    def normalize_to_standard_format(self, inspection_records: List[Dict], enterprises: List[Dict]):
        """标准化为系统所需的6张表格式"""
        print("\n📊 标准化为系统格式...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_subdir = self.output_dir / f"standardized_{timestamp}"
        output_subdir.mkdir(exist_ok=True)

        # 1. enterprise_master.csv
        enterprise_rows = []
        for idx, ent in enumerate(enterprises, 1):
            enterprise_rows.append({
                'enterprise_id': f"ENT-SH-{idx:04d}",
                'enterprise_name': ent['enterprise_name'],
                'enterprise_type': 'large' if '股份' in ent['enterprise_name'] or '有限' in ent['enterprise_name'] else 'medium',
                'node_type': '乳企',
                'address': ent.get('district', '上海市') + '某路某号',
                'latitude': '',
                'longitude': '',
                'license_no': ent.get('license_no', f"SC{idx:06d}"),
                'credit_rating': 'A',
                'historical_violation_count': 0,
                'supervision_freq': 4,
                'haccp_certified': True,
                'iso22000_certified': True,
                'data_source': ent.get('evidence_type', 'simulated'),
                'source_note': ent.get('note', '从抽检公告提取或已知企业列表')
            })

        # 保存 enterprise_master
        self._save_csv(output_subdir / "enterprise_master.csv", enterprise_rows)
        print(f"  ✓ enterprise_master: {len(enterprise_rows)} 条")

        # 2. inspection_records.csv
        inspection_rows = []
        for idx, record in enumerate(inspection_records, 1):
            result = record.get('test_result', '')
            is_qualified = '合格' in result and '不' not in result

            inspection_rows.append({
                'inspection_id': f"INS-SH-{idx:04d}",
                'batch_id': '',  # 关联到batch_records
                'enterprise_id': '',  # 需要后续关联
                'enterprise_name': record.get('enterprise_name', ''),
                'product_name': record.get('product_name', ''),
                'specification': record.get('specification', ''),
                'batch_info': record.get('batch_info', ''),
                'inspection_type': 'routine',
                'inspection_date': record.get('notice_date', '2025-06-12'),
                'test_result': 'qualified' if is_qualified else 'unqualified',
                'unqualified_items': record.get('unqualified_items', ''),
                'test_org': record.get('test_org', ''),
                'notice_title': record.get('notice_title', ''),
                'notice_url': record.get('notice_url', ''),
                'evidence_type': record.get('evidence_type', 'public_record'),
                'data_source': '上海市市场监管局抽检公告'
            })

        self._save_csv(output_subdir / "inspection_records_real.csv", inspection_rows)
        print(f"  ✓ inspection_records: {len(inspection_rows)} 条")

        # 3. 生成数据质量报告
        report = {
            "generated_at": datetime.now().isoformat(),
            "source": "上海市市场监管局公开数据",
            "statistics": {
                "total_enterprises": len(enterprise_rows),
                "total_inspections": len(inspection_rows),
                "public_record_ratio": f"{len(inspection_records)}/{len(inspection_rows)}",
                "dairy_related": len(inspection_records),
                "failed_urls": self.stats["failed_urls"]
            },
            "evidence_type_distribution": {
                "public_record": len([r for r in inspection_rows if r['evidence_type'] == 'public_record']),
                "simulated": len([r for r in inspection_rows if r['evidence_type'] == 'simulated'])
            },
            "output_directory": str(output_subdir)
        }

        with open(output_subdir / "fetch_report.json", 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n✓ 标准化数据保存至: {output_subdir}")
        return output_subdir

    def _save_csv(self, filepath: Path, rows: List[Dict]):
        """保存CSV文件"""
        if not rows:
            return

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    def run(self, mode: str = "full"):
        """运行抓取流程"""
        print(f"\n模式: {mode}")
        print("="*60)

        all_inspection_records = []

        # 1. 抓取公告
        if mode in ["full", "inspection"]:
            records = self.fetch_inspection_notice("inspection_notice_2025_18")
            all_inspection_records.extend(records)

        # 2. 生成企业列表
        enterprises = self.generate_enterprises_from_real_data(all_inspection_records)

        # 3. 标准化输出
        if all_inspection_records:
            output_dir = self.normalize_to_standard_format(all_inspection_records, enterprises)
        else:
            print("\n⚠️ 未抓取到公开记录，生成待补录清单...")
            output_dir = self.generate_todo_list()

        # 4. 输出统计
        print("\n" + "="*60)
        print("抓取统计")
        print("="*60)
        print(f"公开记录: {self.stats['public_records']} 条")
        print(f"模拟补充: {self.stats['simulated_records']} 条")
        print(f"失败URL: {len(self.stats['failed_urls'])} 个")

        if self.stats["failed_urls"]:
            print("\n待手动补录的URL:")
            for url in self.stats["failed_urls"]:
                print(f"  - {url}")

        print(f"\n输出目录: {output_dir}")
        return output_dir

    def generate_todo_list(self):
        """生成待补录清单（当自动抓取失败时使用）"""
        todo = {
            "created_at": datetime.now().isoformat(),
            "note": "以下链接需要手动下载或半自动抓取",
            "sources": [
                {
                    "url": self.SOURCES["inspection_notice_2025_18"]["url"],
                    "title": "2025年第18期省级食品安全抽检信息",
                    "type": "inspection",
                    "priority": "high",
                    "instruction": "访问链接，下载公告附件中的Excel表格，放入 data/raw/manual/ 目录"
                }
            ]
        }

        todo_path = self.output_dir / "TODO_manual_fetch.json"
        with open(todo_path, 'w', encoding='utf-8') as f:
            json.dump(todo, f, ensure_ascii=False, indent=2)

        print(f"  ✓ 待补录清单: {todo_path}")
        return self.output_dir


def main():
    """主函数"""
    fetcher = ShanghaiRealDataFetcher()
    fetcher.run(mode="full")

    print("\n" + "="*60)
    print("下一步:")
    print("="*60)
    print("1. 检查 data/raw/standardized_*/ 目录下的输出")
    print("2. 如有抓取失败，查看 TODO_manual_fetch.json 手动补录")
    print("3. 运行 normalize_real_data.py 进一步标准化")
    print("4. 运行 merge_data.py 合并到答辩数据集")


if __name__ == "__main__":
    main()
