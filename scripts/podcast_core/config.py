"""Load and validate multi-show + per-show YAML configs."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    print(
        "缺少 PyYAML。请先: python3 -m venv .venv && "
        ".venv/bin/pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)

REQUIRED_META = (
    "title",
    "description",
    "link",
    "rss_feed_url",
    "language",
    "author",
    "email",
)


def die(msg: str, code: int = 1) -> None:
    print(f"错误: {msg}", file=sys.stderr)
    sys.exit(code)


def load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        die(f"找不到配置文件: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        die(f"{path} 顶层必须是映射 (mapping)")
    return data


def load_shows_index(path: Path) -> dict[str, Any]:
    """Load root shows.yaml index."""
    data = load_config(path)
    if "shows" not in data or not isinstance(data["shows"], list):
        die(f"{path}: 缺少 shows 列表")
    site = data.get("site")
    if not isinstance(site, dict) or not site.get("base_url"):
        die(f"{path}: site.base_url 为必填")
    for i, show in enumerate(data["shows"], start=1):
        if not isinstance(show, dict):
            die(f"{path}: shows[{i}] 必须是映射")
        for key in ("id", "slug", "config", "publish_dir"):
            if not show.get(key):
                die(f"{path}: shows[{i}].{key} 为必填")
    return data


def resolve_show_paths(repo_root: Path, show: dict[str, Any]) -> dict[str, Path]:
    """Resolve absolute paths for a show entry from shows.yaml."""
    return {
        "config": (repo_root / str(show["config"])).resolve(),
        "publish_dir": (repo_root / str(show["publish_dir"])).resolve(),
        "legacy_feed": (repo_root / "docs" / "feed.xml").resolve(),
    }


def validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    meta = config.get("metadata")
    if not isinstance(meta, dict):
        return ["缺少 metadata 段"]

    for key in REQUIRED_META:
        if not meta.get(key):
            errors.append(f"metadata.{key} 为必填")

    email = str(meta.get("email") or "")
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        errors.append(f"metadata.email 格式无效: {email!r}")

    for url_key in ("link", "rss_feed_url", "image"):
        val = meta.get(url_key)
        if val and not str(val).startswith(("http://", "https://")):
            errors.append(f"metadata.{url_key} 必须是 http(s) URL")

    episodes = config.get("episodes")
    if episodes is None:
        errors.append("缺少 episodes 列表（可以为空列表 []）")
        return errors
    if not isinstance(episodes, list):
        errors.append("episodes 必须是列表")
        return errors

    for i, ep in enumerate(episodes, start=1):
        if not isinstance(ep, dict):
            errors.append(f"Episode {i}: 必须是映射")
            continue
        for key in ("title", "description", "publication_date", "file"):
            if not ep.get(key):
                errors.append(f"Episode {i}: 缺少 {key}")
        if ep.get("publication_date"):
            try:
                from .feed import parse_pub_date

                parse_pub_date(str(ep["publication_date"]))
            except ValueError as e:
                errors.append(f"Episode {i}: publication_date 无效 — {e}")
        et = ep.get("episode_type", "full")
        if et not in ("full", "trailer", "bonus"):
            errors.append(f"Episode {i}: episode_type 必须是 full/trailer/bonus")
        for int_key in ("episode", "season", "length"):
            if int_key in ep and ep[int_key] is not None:
                try:
                    int(ep[int_key])
                except (TypeError, ValueError):
                    errors.append(f"Episode {i}: {int_key} 必须是整数")
    return errors
