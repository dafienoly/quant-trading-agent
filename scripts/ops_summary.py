#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.product_app.ops_summary import build_ops_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a read-only operations summary JSON.")
    parser.add_argument("--repo-root", default=".", help="Repository root to scan")
    parser.add_argument("--output", help="Optional JSON output path")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = build_ops_summary(args.repo_root)
    text = json.dumps(summary.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
