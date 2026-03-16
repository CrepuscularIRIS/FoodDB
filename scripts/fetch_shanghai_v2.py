#!/usr/bin/env python3
"""
上海市乳制品数据抓取脚本 v2.1
支持Excel附件下载和解析
"""

import os
import sys
import json
import time
import csv
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin
from typing import Optional, List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
    from bs4 import BeautifulSoup
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("⚠️ pandas未安装，将跳过Excel解析")
    print("   pip install pandas openpyxl")


class ShanghaiDataFetcherV2:
    """上海市数据抓取器 v2"""

    BASE_URL = "https://scjgj.sh.gov.cn"
    NOTICE_URL = "https://scjgj.sh.gov.cn/922/20250612/2c984a72974479dd019762b31c7e6831.html"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path(__file__).parent.parent / "data" / "raw"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.attachments_dir = self.output_dir / "attachments"
        self.attachments_dir.mkdir(exist_ok=True)

        self.session = requests.Session() if REQUESTS_AVAILABLE else None
        if self.session:
            self.session.headers.update(self.HEADERS)

        self.records = []
        print("="*60)
        print("上海市乳制品数据抓取器 v2.1")
        print("="*60)

    def fetch_page(self, url: str) -> Optional[str]:
        """抓取页面"""
        try:
            time.sleep(1)
            response = self.session.get(url, timeout=30)
            response.encoding = 'utf-8'
            return response.text if response.status_code == 200 else None
        except Exception as e:
            print(f"  请求失败: {e}")
            return None

    def extract_excel_links(self, html: str) -> List[Dict]:
        """从HTML中提取Excel附件链接"""
        soup = BeautifulSoup(html, 'html.parser')
        links = []

        for a in soup.find_all('a', href=True):
            href = a['href']
            if '.xls' in href.lower():
                full_url = urljoin(self.BASE_URL, href)
                filename = href.split('/')[-1]
                # 尝试从文本获取描述
                description = a.get_text(strip=True)
                links.append({
                    'url': full_url,
                    'filename': filename[:50],
                    'description': description,
                    'source_path': href
                })

        return links

    def download_file(self, url: str, filename: str) -> Optional[Path]:
        """下载文件"""
        try:
            time.sleep(0.5)
            response = self.session.get(url, timeout=60)

            if response.status_code == 200:
                filepath = self.attachments_dir / filename
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                return filepath
            else:
                print(f"  下载失败 HTTP {response.status_code}: {url}")
                return None
        except Exception as e:
            print(f"  下载失败: {e}")
            return None

    def parse_excel(self, filepath: Path) -> List[Dict]:
        """解析Excel文件"""
        if not PANDAS_AVAILABLE:
            return []

        records = []
        try:
            # 读取Excel
            df = pd.read_excel(filepath, engine='xlrd')

            # 转换为字典列表
            for _, row in df.iterrows():
                record = {
                    'source_file': filepath.name,
                    'evidence_type': 'public_record'
                }

                # 遍历所有列
                for col in df.columns:
                    value = row[col]
                    # 处理NaN
                    if pd.isna(value):
                        value = ''
                    else:
                        value = str(value).strip()
                    record[str(col)] = value

                # 只保留有产品名称或企业名称的记录
                if any(keyword in str(record.values()).lower() for keyword in ['乳', '奶']):
                    records.append(record)

        except Exception as e:
            print(f"  解析失败 {filepath.name}: {e}")

        return records

    def normalize_record(self, raw_record: Dict) -> Dict:
        """标准化记录格式"""
        # 列名映射（根据实际Excel表头调整）
        col_mapping = {
            # 可能的列名 -> 标准列名
            '食品名称': 'product_name',
            '产品名称': 'product_name',
            '样品名称': 'product_name',
            '标称生产企业名称': 'enterprise_name',
            '生产企业': 'enterprise_name',
            '生产厂家': 'enterprise_name',
            '规格型号': 'specification',
            '生产日期/批号': 'batch_info',
            '生产日期': 'production_date',
            '批号': 'batch_no',
            '被抽样单位': 'sampled_unit',
            '检验结果': 'test_result',
            '检验结论': 'test_result',
            '不合格项目': 'unqualified_items',
            '食品大类': 'food_category',
        }

        normalized = {
            'evidence_type': raw_record.get('evidence_type', 'public_record'),
            'source_file': raw_record.get('source_file', ''),
        }

        # 应用映射
        for original_col, std_col in col_mapping.items():
            if original_col in raw_record:
                normalized[std_col] = raw_record[original_col]

        # 保留原始字段
        for key, value in raw_record.items():
            if key not in normalized and key not in ['evidence_type', 'source_file']:
                normalized[f'raw_{key}'] = value

        return normalized

    def is_dairy_product(self, record: Dict) -> bool:
        """判断是否为乳制品"""
        dairy_keywords = ['乳', '奶', '酸奶', '牛奶', '羊奶', '奶粉', '液态奶', '巴氏', '灭菌乳']

        text_to_check = ''
        for key in ['product_name', 'enterprise_name', 'food_category', 'raw_食品大类']:
            if key in record:
                text_to_check += ' ' + str(record[key])

        return any(kw in text_to_check for kw in dairy_keywords)

    def run(self):
        """主流程"""
        print(f"\n📄 抓取公告页面...")
        html = self.fetch_page(self.NOTICE_URL)

        if not html:
            print("❌ 抓取失败")
            return

        # 保存HTML
        html_path = self.output_dir / "notice_2025_18.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"  ✓ HTML保存: {html_path}")

        # 提取Excel链接
        print(f"\n🔗 提取Excel附件...")
        excel_links = self.extract_excel_links(html)
        print(f"  找到 {len(excel_links)} 个Excel附件")

        # 下载并解析
        all_records = []
        dairy_records = []

        for i, link in enumerate(excel_links, 1):  # 下载所有附件
            print(f"\n[{i}/5] {link['description'][:30]}...")
            print(f"   下载: {link['filename']}")

            filepath = self.download_file(link['url'], f"{i:02d}_{link['filename']}")

            if filepath and PANDAS_AVAILABLE:
                print(f"   解析中...")
                records = self.parse_excel(filepath)
                print(f"   ✓ 解析到 {len(records)} 条乳制品相关记录")

                for record in records:
                    normalized = self.normalize_record(record)
                    all_records.append(normalized)

                    if self.is_dairy_product(normalized):
                        dairy_records.append(normalized)

        # 保存结果
        print(f"\n💾 保存结果...")

        if all_records:
            # JSON格式
            json_path = self.output_dir / "shanghai_dairy_records.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(all_records, f, ensure_ascii=False, indent=2)
            print(f"  ✓ JSON: {json_path} ({len(all_records)} 条)")

            # CSV格式 - 只保留标准字段
            if all_records:
                # 获取所有可能的字段
                all_fields = set()
                for record in all_records:
                    all_fields.update(record.keys())

                # 排序字段，标准字段在前
                standard_fields = ['product_name', 'enterprise_name', 'specification',
                                 'batch_info', 'test_result', 'unqualified_items',
                                 'sampled_unit', 'food_category', 'evidence_type', 'source_file']
                other_fields = sorted([f for f in all_fields if f not in standard_fields])
                fieldnames = standard_fields + other_fields

                csv_path = self.output_dir / "shanghai_dairy_records.csv"
                with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(all_records)
                print(f"  ✓ CSV: {csv_path}")

        # 生成报告
        report = {
            "fetch_time": datetime.now().isoformat(),
            "source_url": self.NOTICE_URL,
            "total_excel_files": len(excel_links),
            "downloaded_files": min(5, len(excel_links)),
            "total_records": len(all_records),
            "dairy_records": len(dairy_records),
            "excel_links": excel_links
        }

        report_path = self.output_dir / "fetch_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"  ✓ 报告: {report_path}")

        print(f"\n" + "="*60)
        print("统计")
        print("="*60)
        print(f"Excel附件总数: {len(excel_links)}")
        print(f"下载解析: {min(5, len(excel_links))} 个")
        print(f"总记录数: {len(all_records)}")
        print(f"乳制品相关: {len(dairy_records)}")
        print(f"\n附件保存: {self.attachments_dir}")
        print(f"数据保存: {self.output_dir}")

        return all_records


def main():
    fetcher = ShanghaiDataFetcherV2()
    fetcher.run()

    print("\n下一步:")
    print("1. 检查 data/raw/ 目录下的CSV文件")
    print("2. 运行 normalize_real_data.py 标准化")
    print("3. 运行 merge_data.py 合并到答辩数据集")


if __name__ == "__main__":
    main()
