#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.product_app.agent_runtime import resolve_agent_runtime  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve an Agent runtime profile without executing commands.")
    parser.add_argument("--stage", required=True, help="Agent pipeline stage id")
    parser.add_argument("--dry-run", action="store_true", help="Resolve as dry-run mode")
    parser.add_argument("--output", help="Optional JSON output path")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    profile = resolve_agent_runtime(args.stage, dry_run=args.dry_run)
    payload = profile.model_dump(mode="json")
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
