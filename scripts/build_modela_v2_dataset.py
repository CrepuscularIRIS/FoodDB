#!/usr/bin/env python3
"""Build ModelA v2 artifacts from dataset_3_24."""

from __future__ import annotations

import argparse
from pathlib import Path

from modela_v2_pipeline import build_modela_v2_graph


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ModelA v2 graph and profile features")
    parser.add_argument(
        "--input",
        required=True,
        help="Path to dataset_3_24 directory or the handoff zip file",
    )
    parser.add_argument(
        "--output-dir",
        default="data/modela_v2",
        help="Output directory (default: data/modela_v2)",
    )
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    graph = build_modela_v2_graph(input_path=input_path, output_dir=output_dir)

    print("[OK] ModelA v2 artifacts generated")
    print(f"  output_dir: {output_dir}")
    print(f"  node_count: {graph['meta']['node_count']}")
    print(f"  edge_count: {graph['meta']['edge_count']}")
    print(f"  categories: {len(graph['meta']['product_categories'])}")


if __name__ == "__main__":
    main()
