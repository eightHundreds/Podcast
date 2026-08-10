#!/usr/bin/env python3
"""Generate all feeds + site pages from shows.yaml."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from generate_feed import generate_all as gen_feeds
from generate_site import generate as gen_site

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="生成全部 feed 与站点页面")
    parser.add_argument(
        "--index",
        type=Path,
        default=REPO_ROOT / "shows.yaml",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--include-future", action="store_true")
    args = parser.parse_args()

    gen_feeds(args.index, dry_run=args.dry_run, include_future=args.include_future)
    gen_site(args.index, dry_run=args.dry_run)
    print("✓ 全部完成")


if __name__ == "__main__":
    main()
