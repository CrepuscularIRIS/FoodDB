#!/usr/bin/env python3
"""Download selected Hugging Face datasets for risk-taxonomy support."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "knowledge" / "derived" / "risk_taxonomy_raw_huggingface"
DATASETS = [
    "bigbio/bc5cdr",
    "bigbio/biored",
]


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dumps(data) + "\n", encoding="utf-8")


def _read_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip("'").strip('"')
    return env


class HuggingFaceDatasetFetcher:
    def __init__(self, output_dir: Path = DEFAULT_OUTPUT_DIR) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        env = _read_env(ROOT / ".env")
        self.token = (
            os.environ.get("HUGGINGFACE_TOKEN")
            or os.environ.get("Huggingface-Token")
            or env.get("HUGGINGFACE_TOKEN")
            or env.get("Huggingface-Token")
        )

    def fetch_all(self) -> dict[str, Any]:
        if not self.token:
            raise RuntimeError("Missing Hugging Face token")

        downloads: list[dict[str, Any]] = []
        for repo_id in DATASETS:
            local_dir = self.output_dir / repo_id.replace("/", "__")
            cmd = [
                "huggingface-cli",
                "download",
                "--repo-type",
                "dataset",
                "--token",
                self.token,
                "--local-dir",
                str(local_dir),
                repo_id,
            ]
            subprocess.run(cmd, check=True)
            file_count = sum(1 for path in local_dir.rglob("*") if path.is_file())
            downloads.append(
                {
                    "repo_id": repo_id,
                    "local_dir": str(local_dir),
                    "file_count": file_count,
                }
            )

        manifest = {
            "generated_at": datetime.now(UTC).isoformat(),
            "output_dir": str(self.output_dir),
            "datasets": downloads,
        }
        _write_json(self.output_dir / "huggingface_manifest.json", manifest)
        return manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download selected Hugging Face datasets.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for downloaded datasets.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    manifest = HuggingFaceDatasetFetcher(output_dir=Path(args.output_dir)).fetch_all()
    print(_json_dumps(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
