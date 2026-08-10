"""RSS feed building (pure + write helpers)."""

from __future__ import annotations

import html
import re
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
CONTENT = "http://purl.org/rss/1.0/modules/content/"
PODCAST = "https://podcastindex.org/namespace/1.0"
ATOM = "http://www.w3.org/2005/Atom"

ET.register_namespace("itunes", ITUNES)
ET.register_namespace("content", CONTENT)
ET.register_namespace("podcast", PODCAST)
ET.register_namespace("atom", ATOM)


def die(msg: str, code: int = 1) -> None:
    print(f"错误: {msg}", file=sys.stderr)
    sys.exit(code)


def parse_pub_date(value: str) -> datetime:
    """Parse ISO 8601 (with Z or offset) into aware datetime."""
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        s = s + "T00:00:00+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def to_rfc2822(dt: datetime) -> str:
    return format_datetime(dt.astimezone(timezone.utc))


def resolve_audio_url(file_value: str, base: str | None) -> str:
    file_value = file_value.strip()
    if file_value.startswith(("http://", "https://")):
        return file_value
    if not base:
        die(
            f"音频路径 {file_value!r} 是相对路径，请设置 audio_base_url "
            "或写成完整 https URL"
        )
    base = base if base.endswith("/") else base + "/"
    return urljoin(base, file_value.lstrip("/"))


def sub(parent: ET.Element, tag: str, text: str | None = None, **attrs: str) -> ET.Element:
    el = ET.SubElement(parent, tag, {k: v for k, v in attrs.items() if v is not None})
    if text is not None:
        el.text = text
    return el


def itunes(parent: ET.Element, tag: str, text: str | None = None, **attrs: str) -> ET.Element:
    return sub(parent, f"{{{ITUNES}}}{tag}", text, **attrs)


def podcast_ns(parent: ET.Element, tag: str, text: str | None = None, **attrs: str) -> ET.Element:
    return sub(parent, f"{{{PODCAST}}}{tag}", text, **attrs)


def content_encoded(parent: ET.Element, text: str) -> ET.Element:
    el = sub(parent, f"{{{CONTENT}}}encoded")
    el.text = text
    return el


def build_feed(config: dict[str, Any], *, include_future: bool = False) -> ET.ElementTree:
    meta = config["metadata"]
    audio_base = config.get("audio_base_url")
    now = datetime.now(timezone.utc)

    rss = ET.Element("rss", {"version": "2.0"})
    channel = sub(rss, "channel")

    sub(channel, "title", str(meta["title"]))
    sub(channel, "description", str(meta["description"]).strip())
    sub(channel, "link", str(meta["link"]))
    sub(channel, "language", str(meta["language"]))
    sub(channel, "generator", "Podcast generate_feed.py")
    sub(channel, "lastBuildDate", to_rfc2822(now))
    if meta.get("copyright"):
        sub(channel, "copyright", str(meta["copyright"]))

    sub(
        channel,
        f"{{{ATOM}}}link",
        href=str(meta["rss_feed_url"]),
        rel="self",
        type="application/rss+xml",
    )

    itunes(channel, "author", str(meta["author"]))
    itunes(channel, "summary", str(meta["description"]).strip())
    itunes(channel, "explicit", "true" if meta.get("explicit") else "false")
    if meta.get("image"):
        itunes(channel, "image", href=str(meta["image"]))
        image = sub(channel, "image")
        sub(image, "url", str(meta["image"]))
        sub(image, "title", str(meta["title"]))
        sub(image, "link", str(meta["link"]))
    if meta.get("category"):
        itunes(channel, "category", text=str(meta["category"]))

    owner = itunes(channel, "owner")
    itunes(owner, "name", str(meta["author"]))
    itunes(owner, "email", str(meta["email"]))

    if meta.get("podcast_guid"):
        podcast_ns(channel, "guid", str(meta["podcast_guid"]))
    locked = str(meta.get("podcast_locked", "no")).lower()
    podcast_ns(
        channel,
        "locked",
        locked if locked in ("yes", "no") else "no",
        owner=str(meta["email"]),
    )

    episodes = list(config.get("episodes") or [])

    def sort_key(ep: dict[str, Any]) -> datetime:
        return parse_pub_date(str(ep["publication_date"]))

    episodes_sorted = sorted(episodes, key=sort_key, reverse=True)

    skipped_future = 0
    for ep in episodes_sorted:
        pub = parse_pub_date(str(ep["publication_date"]))
        if not include_future and pub > now:
            skipped_future += 1
            continue

        item = sub(channel, "item")
        sub(item, "title", str(ep["title"]))
        desc = str(ep["description"]).strip()
        sub(item, "description", desc)
        content_encoded(item, html.escape(desc).replace("\n", "<br/>\n"))
        sub(item, "pubDate", to_rfc2822(pub))
        sub(item, "link", str(ep.get("link") or meta["link"]))

        audio_url = resolve_audio_url(str(ep["file"]), str(audio_base) if audio_base else None)
        guid_text = str(ep.get("guid") or audio_url)
        guid_el = sub(item, "guid", guid_text)
        guid_el.set("isPermaLink", "true" if guid_text.startswith("http") else "false")

        length = str(int(ep.get("length") or 0))
        mime = str(ep.get("type") or "audio/mpeg")
        sub(item, "enclosure", url=audio_url, length=length, type=mime)

        itunes(item, "author", str(ep.get("author") or meta["author"]))
        itunes(item, "summary", desc)
        itunes(item, "explicit", "true" if ep.get("explicit", meta.get("explicit")) else "false")
        if ep.get("duration"):
            itunes(item, "duration", str(ep["duration"]))
        if ep.get("episode") is not None:
            itunes(item, "episode", str(int(ep["episode"])))
        if ep.get("season") is not None:
            itunes(item, "season", str(int(ep["season"])))
        et = str(ep.get("episode_type") or "full")
        itunes(item, "episodeType", et)
        img = ep.get("image") or meta.get("image")
        if img:
            itunes(item, "image", href=str(img))

        for tr in ep.get("transcripts") or []:
            if not isinstance(tr, dict) or not tr.get("url") or not tr.get("type"):
                continue
            attrs = {"url": str(tr["url"]), "type": str(tr["type"])}
            if tr.get("language"):
                attrs["language"] = str(tr["language"])
            if tr.get("rel"):
                attrs["rel"] = str(tr["rel"])
            podcast_ns(item, "transcript", **attrs)

    if skipped_future:
        print(f"提示: 跳过 {skipped_future} 个未到发布时间的单集", file=sys.stderr)

    return ET.ElementTree(rss)


def indent(elem: ET.Element, level: int = 0) -> None:
    if hasattr(ET, "indent"):
        ET.indent(elem, space="  ")
        return
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for child in elem:
            indent(child, level + 1)
        if not child.tail or not child.tail.strip():  # type: ignore[name-defined]
            child.tail = i  # type: ignore[name-defined]
    elif level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i


def write_feed(tree: ET.ElementTree, output: Path) -> None:
    indent(tree.getroot())
    output.parent.mkdir(parents=True, exist_ok=True)
    tree.write(
        output,
        encoding="utf-8",
        xml_declaration=True,
        default_namespace=None,
        method="xml",
    )
    text = output.read_text(encoding="utf-8")
    if not text.startswith("<?xml"):
        text = '<?xml version="1.0" encoding="UTF-8"?>\n' + text
    output.write_text(text, encoding="utf-8")
