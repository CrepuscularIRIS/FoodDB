#!/usr/bin/env python3
"""CLI entrypoint for the standalone layered food risk knowledge base."""

from __future__ import annotations

import argparse
import json

from router import LayeredFoodRiskKB


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="User query or symptom/risk description")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = parser.parse_args()

    kb = LayeredFoodRiskKB()
    result = kb.query(args.query)

    if args.pretty:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
