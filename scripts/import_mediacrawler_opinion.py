#!/usr/bin/env python3
"""
从本机 MediaCrawler 导入舆情数据并生成企业舆情特征。

示例:
python scripts/import_mediacrawler_opinion.py \
  --media-root /home/yarizakurahime/Agents/winteragent/MediaCrawler/data \
  --platform weibo \
  --days 30
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.opinion_module import (
    DEFAULT_ENTERPRISE_CSV,
    DEFAULT_MEDIA_ROOT,
    build_opinion_features,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="导入 MediaCrawler 舆情语料")
    parser.add_argument("--media-root", default=str(DEFAULT_MEDIA_ROOT), help="MediaCrawler 的 data 根目录")
    parser.add_argument("--enterprise-csv", default=str(DEFAULT_ENTERPRISE_CSV), help="企业主档 CSV 路径")
    parser.add_argument("--platform", default="weibo", help="平台标识，如 weibo/douyin/xhs")
    parser.add_argument("--days", type=int, default=30, help="统计窗口天数")
    args = parser.parse_args()

    summary = build_opinion_features(
        media_root=Path(args.media_root),
        enterprise_csv=Path(args.enterprise_csv),
        platform=args.platform,
        days=args.days,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

