#!/usr/bin/env python3
"""
上海市乳制品相关公开数据抓取脚本

数据源:
1. 上海市市场监管局 - 食品安全抽检信息
   https://scjgj.sh.gov.cn/zwgk/zcwj/zcjd/202307/t20230705_1789017.html

2. 国家企业信用信息公示系统 - 企业基本信息
   https://www.gsxt.gov.cn/

3. 上海市食品生产许可证查询
   https://zwdt.sh.gov.cn/

抓取策略:
- 优先使用 requests + BeautifulSoup
- 反爬严重时使用 Playwright
- 数据保存为原始HTML/JSON，后续统一处理
"""

import os
import sys
import json
import time
import csv
import re
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
from typing import Optional, List, Dict

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 尝试导入playwright
try:
    from playwright.sync_api import sync_playwright, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️ Playwright 未安装，将使用 requests 模式")

# 尝试导入requests
try:
    import requests
    from bs4 import BeautifulSoup
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class ShanghaiMarketDataFetcher:
    """上海市市场监管局数据抓取器"""

    # 数据源URL
    URLs = {
        "inspection_list": "https://scjgj.sh.gov.cn/zwgk/zcwj/zcjd/202307/t20230705_1789017.html",
        "inspection_base": "https://scjgj.sh.gov.cn",
        "food_safety_notice": "https://scjgj.sh.gov.cn/zwgk/zcwj/zcjd/",
    }

    # 请求头
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    def __init__(self, output_dir: Optional[Path] = None, use_playwright: bool = True):
        """
        初始化抓取器

        Args:
            output_dir: 输出目录
            use_playwright: 是否使用Playwright
        """
        if output_dir is None:
            output_dir = Path(__file__).parent.parent / "data" / "raw"

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.use_playwright = use_playwright and PLAYWRIGHT_AVAILABLE
        self.session = requests.Session() if REQUESTS_AVAILABLE else None

        if self.session:
            self.session.headers.update(self.HEADERS)

        print(f"✓ 抓取器初始化完成")
        print(f"  - 输出目录: {self.output_dir}")
        print(f"  - 使用Playwright: {self.use_playwright}")
        print(f"  - 使用Requests: {REQUESTS_AVAILABLE}")

    def fetch_with_requests(self, url: str, retries: int = 3) -> Optional[str]:
        """使用requests抓取页面"""
        if not REQUESTS_AVAILABLE:
            return None

        for i in range(retries):
            try:
                time.sleep(1)  # 礼貌性延迟
                response = self.session.get(url, timeout=30)
                response.encoding = 'utf-8'

                if response.status_code == 200:
                    return response.text
                else:
                    print(f"  HTTP {response.status_code}: {url}")

            except Exception as e:
                print(f"  请求失败 ({i+1}/{retries}): {e}")
                time.sleep(2 ** i)  # 指数退避

        return None

    def fetch_with_playwright(self, url: str, wait_for: Optional[str] = None) -> Optional[str]:
        """使用Playwright抓取页面"""
        if not PLAYWRIGHT_AVAILABLE:
            return None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                page.goto(url, wait_until="networkidle", timeout=60000)

                if wait_for:
                    page.wait_for_selector(wait_for, timeout=10000)

                # 等待页面加载完成
                time.sleep(2)

                content = page.content()
                browser.close()

                return content

        except Exception as e:
            print(f"  Playwright抓取失败: {e}")
            return None

    def fetch_page(self, url: str, use_browser: bool = False, wait_for: Optional[str] = None) -> Optional[str]:
        """
        智能抓取页面

        Args:
            url: 目标URL
            use_browser: 是否强制使用浏览器
            wait_for: Playwright等待的选择器

        Returns:
            HTML内容或None
        """
        print(f"\n📄 抓取: {url}")

        # 优先使用requests，失败或需要时切换playwright
        if not use_browser and REQUESTS_AVAILABLE:
            content = self.fetch_with_requests(url)
            if content:
                return content
            print("  Requests失败，尝试Playwright...")

        if self.use_playwright:
            return self.fetch_with_playwright(url, wait_for)

        return None

    def save_raw_data(self, filename: str, data: str, subdir: str = ""):
        """保存原始数据"""
        save_dir = self.output_dir / subdir
        save_dir.mkdir(parents=True, exist_ok=True)

        filepath = save_dir / filename

        if isinstance(data, str):
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(data)
        else:
            with open(filepath, 'wb') as f:
                f.write(data)

        print(f"  ✓ 保存: {filepath}")
        return filepath

    def parse_inspection_list(self, html: str) -> List[Dict]:
        """解析抽检公告列表"""
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        notices = []

        # 尝试多种选择器
        selectors = [
            '.news-list li',
            '.list-con li',
            '.news-list-item',
            'ul.news li',
            '.main-content li',
        ]

        for selector in selectors:
            items = soup.select(selector)
            if items:
                print(f"  使用选择器: {selector}, 找到 {len(items)} 条")
                break

        for item in items[:20]:  # 限制数量
            try:
                # 提取标题和链接
                link_elem = item.find('a')
                if not link_elem:
                    continue

                title = link_elem.get_text(strip=True)
                href = link_elem.get('href', '')

                # 跳过非乳制品相关内容
                if not self._is_dairy_related(title):
                    continue

                # 提取日期
                date_elem = item.find(class_=re.compile('date|time'))
                date = date_elem.get_text(strip=True) if date_elem else ""

                # 补全URL
                if href and not href.startswith('http'):
                    href = urljoin(self.URLs["inspection_base"], href)

                notices.append({
                    'title': title,
                    'url': href,
                    'date': date,
                    'fetched_at': datetime.now().isoformat()
                })

            except Exception as e:
                print(f"  解析条目失败: {e}")
                continue

        return notices

    def _is_dairy_related(self, text: str) -> bool:
        """判断是否与乳制品相关"""
        dairy_keywords = [
            '乳', '奶', '酸奶', '牛奶', '羊奶', '奶粉',
            'dairy', 'milk', 'yogurt', 'yoghurt',
            '乳制品', '液态奶', '巴氏', '灭菌乳'
        ]

        text_lower = text.lower()
        return any(kw in text for kw in dairy_keywords)

    def parse_inspection_detail(self, html: str) -> List[Dict]:
        """解析抽检公告详情中的表格数据"""
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        records = []

        # 查找表格
        tables = soup.find_all('table')
        print(f"  找到 {len(tables)} 个表格")

        for table in tables:
            try:
                # 提取表头
                headers = []
                header_row = table.find('thead')
                if header_row:
                    headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]

                if not headers:
                    # 尝试第一行作为表头
                    first_row = table.find('tr')
                    if first_row:
                        headers = [th.get_text(strip=True) for th in first_row.find_all(['th', 'td'])]

                # 标准化表头
                header_mapping = self._standardize_headers(headers)

                # 提取数据行
                rows = table.find_all('tr')[1:] if headers else table.find_all('tr')

                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) < 3:  # 跳过无效行
                        continue

                    cell_data = [cell.get_text(strip=True) for cell in cells]

                    # 映射到标准字段
                    record = {}
                    for std_field, idx in header_mapping.items():
                        if idx < len(cell_data):
                            record[std_field] = cell_data[idx]

                    if record:
                        records.append(record)

            except Exception as e:
                print(f"  解析表格失败: {e}")
                continue

        return records

    def _standardize_headers(self, headers: List[str]) -> Dict[str, int]:
        """标准化表头字段"""
        mapping = {}

        for idx, header in enumerate(headers):
            header_lower = header.lower()

            # 企业名称
            if any(kw in header_lower for kw in ['企业', '生产', '厂家', '制造商']):
                mapping['enterprise_name'] = idx

            # 产品名称
            elif any(kw in header_lower for kw in ['产品', '样品', '名称']):
                mapping['product_name'] = idx

            # 规格型号
            elif any(kw in header_lower for kw in ['规格', '型号', '包装']):
                mapping['specification'] = idx

            # 生产日期/批号
            elif any(kw in header_lower for kw in ['日期', '批号', '批次']):
                mapping['batch_info'] = idx

            # 检验结果
            elif any(kw in header_lower for kw in ['结果', '判定', '结论']):
                mapping['test_result'] = idx

            # 不合格项目
            elif any(kw in header_lower for kw in ['不合格', '项目', '不符合']):
                mapping['unqualified_items'] = idx

            # 被抽样单位
            elif any(kw in header_lower for kw in ['抽样', '被检']):
                mapping['sampled_unit'] = idx

        return mapping

    def fetch_inspection_notices(self, max_pages: int = 3) -> List[Dict]:
        """
        抓取抽检公告列表

        Args:
            max_pages: 最大抓取页数

        Returns:
            公告列表
        """
        print("\n" + "="*60)
        print("开始抓取抽检公告列表")
        print("="*60)

        all_notices = []

        # 抓取主要公告页面
        for page_num in range(1, max_pages + 1):
            print(f"\n📄 抓取第 {page_num} 页...")

            # 构造分页URL（如果有）
            if page_num == 1:
                url = self.URLs["inspection_list"]
            else:
                # 假设分页格式，实际需根据网站调整
                url = f"{self.URLs['inspection_list']}?page={page_num}"

            html = self.fetch_page(url)

            if html:
                # 保存原始HTML
                self.save_raw_data(f"inspection_list_page_{page_num}.html", html, "inspection")

                # 解析列表
                notices = self.parse_inspection_list(html)
                print(f"  ✓ 解析到 {len(notices)} 条乳制品相关公告")

                all_notices.extend(notices)

        # 保存汇总
        if all_notices:
            self.save_raw_data(
                "inspection_notices_summary.json",
                json.dumps(all_notices, ensure_ascii=False, indent=2),
                "inspection"
            )

        print(f"\n✓ 公告列表抓取完成: 共 {len(all_notices)} 条")
        return all_notices

    def fetch_inspection_details(self, notices: List[Dict], max_items: int = 10) -> List[Dict]:
        """
        抓取公告详情

        Args:
            notices: 公告列表
            max_items: 最大抓取数量

        Returns:
            详细记录列表
        """
        print("\n" + "="*60)
        print("开始抓取公告详情")
        print("="*60)

        all_records = []

        for i, notice in enumerate(notices[:max_items]):
            url = notice.get('url')
            if not url:
                continue

            print(f"\n[{i+1}/{min(len(notices), max_items)}] {notice.get('title', '无标题')[:50]}...")

            html = self.fetch_page(url, use_browser=True)

            if html:
                # 保存原始HTML
                safe_title = re.sub(r'[^\w]', '_', notice.get('title', 'unknown')[:30])
                self.save_raw_data(f"detail_{i+1}_{safe_title}.html", html, "inspection/details")

                # 解析表格数据
                records = self.parse_inspection_detail(html)
                print(f"  ✓ 解析到 {len(records)} 条记录")

                # 添加来源信息
                for record in records:
                    record['source_notice'] = notice.get('title')
                    record['source_url'] = url
                    record['notice_date'] = notice.get('date')

                all_records.extend(records)

            time.sleep(2)  # 避免请求过快

        # 保存汇总
        if all_records:
            self.save_raw_data(
                "inspection_records_all.json",
                json.dumps(all_records, ensure_ascii=False, indent=2),
                "inspection"
            )

            # 同时保存为CSV
            if all_records:
                csv_path = self.output_dir / "inspection" / "inspection_records_all.csv"
                csv_path.parent.mkdir(parents=True, exist_ok=True)

                with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=all_records[0].keys())
                    writer.writeheader()
                    writer.writerows(all_records)

                print(f"  ✓ CSV保存: {csv_path}")

        print(f"\n✓ 详情抓取完成: 共 {len(all_records)} 条记录")
        return all_records

    def generate_sample_data(self):
        """
        生成示例数据（当抓取失败时使用）

        基于真实的上海市乳制品企业信息生成模拟数据
        """
        print("\n" + "="*60)
        print("生成示例数据（基于真实企业信息）")
        print("="*60)

        # 上海真实乳制品企业
        real_enterprises = [
            {"name": "光明乳业股份有限公司", "district": "闵行区"},
            {"name": "上海妙可蓝多食品科技股份有限公司", "district": "浦东新区"},
            {"name": "上海延中饮料有限公司", "district": "嘉定区"},
            {"name": "上海味全食品有限公司", "district": "浦东新区"},
            {"name": "上海晨冠乳业有限公司", "district": "浦东新区"},
            {"name": "上海纽贝滋营养乳品有限公司", "district": "浦东新区"},
            {"name": "上海乳品四厂有限公司", "district": "徐汇区"},
        ]

        # 生成检验记录示例
        sample_records = []

        products = ["鲜牛奶", "纯牛奶", "酸奶", "高钙奶", "儿童成长牛奶"]
        results = ["合格", "合格", "合格", "不合格", "合格"]
        unqualified_items = ["", "", "", "大肠菌群", ""]

        for i in range(20):
            ent = real_enterprises[i % len(real_enterprises)]
            record = {
                "enterprise_name": ent["name"],
                "product_name": products[i % len(products)],
                "specification": f"{250 * (i % 3 + 1)}ml",
                "batch_info": f"2024{str(i+1).zfill(2)}{str(i*3).zfill(2)}",
                "test_result": results[i % len(results)],
                "unqualified_items": unqualified_items[i % len(unqualified_items)],
                "sampled_unit": f"上海市{ent['district']}某超市",
                "source_notice": "上海市市场监督管理局食品安全抽检信息公告",
                "source_url": "https://scjgj.sh.gov.cn/",
                "notice_date": f"2024-{str(i % 12 + 1).zfill(2)}-15",
                "data_source": "sample"
            }
            sample_records.append(record)

        # 保存
        self.save_raw_data(
            "inspection_records_sample.json",
            json.dumps(sample_records, ensure_ascii=False, indent=2),
            "inspection"
        )

        # CSV
        csv_path = self.output_dir / "inspection" / "inspection_records_sample.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=sample_records[0].keys())
            writer.writeheader()
            writer.writerows(sample_records)

        print(f"  ✓ 生成示例记录: {len(sample_records)} 条")
        print(f"  ✓ 保存: {csv_path}")

        return sample_records


def main():
    """主函数"""
    print("="*60)
    print("上海市乳制品公开数据抓取工具")
    print("="*60)

    # 初始化
    fetcher = ShanghaiMarketDataFetcher(use_playwright=PLAYWRIGHT_AVAILABLE)

    # 抓取公告列表
    notices = fetcher.fetch_inspection_notices(max_pages=2)

    # 抓取详情
    if notices:
        records = fetcher.fetch_inspection_details(notices, max_items=5)
    else:
        print("\n⚠️ 未抓取到公告列表，使用示例数据")
        records = fetcher.generate_sample_data()

    print("\n" + "="*60)
    print("抓取任务完成")
    print("="*60)
    print(f"数据保存位置: {fetcher.output_dir}")
    print(f"原始数据可用于后续标准化处理")


if __name__ == "__main__":
    main()
