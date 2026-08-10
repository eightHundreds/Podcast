#!/usr/bin/env python3
"""Generate Podcast RSS feed(s) from show config(s).

Single show (legacy-compatible):
  python scripts/generate_feed.py -i shows/…/podcast.yaml -o docs/feed.xml

All shows from shows.yaml:
  python scripts/generate_feed.py --all
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# Allow `python scripts/generate_feed.py` without installing package
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from podcast_core.config import load_config, load_shows_index, resolve_show_paths, validate_config
from podcast_core.feed import build_feed, write_feed

REPO_ROOT = Path(__file__).resolve().parents[1]


def generate_one(
    config_path: Path,
    output: Path,
    *,
    dry_run: bool = False,
    include_future: bool = False,
) -> None:
    config = load_config(config_path)
    errors = validate_config(config)
    if errors:
        print("配置校验失败:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    print(f"✓ 配置有效: {config_path}")
    if dry_run:
        print("dry-run：未生成 feed")
        return

    tree = build_feed(config, include_future=include_future)
    write_feed(tree, output)
    print(f"✓ 已生成: {output}")


def generate_all(
    index_path: Path,
    *,
    dry_run: bool = False,
    include_future: bool = False,
) -> None:
    index = load_shows_index(index_path)
    for show in index["shows"]:
        paths = resolve_show_paths(REPO_ROOT, show)
        config_path = paths["config"]
        publish = paths["publish_dir"]
        show_feed = publish / "feed.xml"
        generate_one(
            config_path,
            show_feed,
            dry_run=dry_run,
            include_future=include_future,
        )
        if dry_run:
            continue
        if show.get("legacy_root_feed"):
            legacy = paths["legacy_feed"]
            legacy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(show_feed, legacy)
            print(f"✓ 兼容副本: {legacy}")


def main() -> None:
    parser = argparse.ArgumentParser(description="从节目 YAML 生成 Podcast RSS feed")
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        help="单个节目 YAML（与 --all 互斥）",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="输出 XML（单节目模式；默认 docs/feed.xml）",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="按 shows.yaml 为每个节目生成 feed（含 legacy 兼容路径）",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=REPO_ROOT / "shows.yaml",
        help="多节目索引（默认仓库根 shows.yaml）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只校验配置，不写文件",
    )
    parser.add_argument(
        "--include-future",
        action="store_true",
        help="包含发布时间在未来的单集（默认跳过）",
    )
    args = parser.parse_args()

    if args.all:
        generate_all(args.index, dry_run=args.dry_run, include_future=args.include_future)
        return

    # Single-show mode (backward compatible defaults)
    input_path = args.input
    if input_path is None:
        # Prefer new location, fall back to root podcast.yaml
        candidates = [
            REPO_ROOT / "shows" / "设计数据密集型应用" / "podcast.yaml",
            REPO_ROOT / "podcast.yaml",
        ]
        for c in candidates:
            if c.is_file():
                input_path = c
                break
        if input_path is None:
            print("错误: 找不到节目配置，请指定 -i 或使用 --all", file=sys.stderr)
            sys.exit(1)

    output = args.output or (REPO_ROOT / "docs" / "feed.xml")
    generate_one(
        Path(input_path),
        Path(output),
        dry_run=args.dry_run,
        include_future=args.include_future,
    )


if __name__ == "__main__":
    main()
