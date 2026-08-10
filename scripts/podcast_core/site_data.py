"""Build player-facing episode / show catalog data from configs."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from .feed import resolve_audio_url
from .player_logic import parse_duration


def _pick_transcript_url(ep: dict[str, Any], prefer: str = "text/vtt") -> str | None:
    for tr in ep.get("transcripts") or []:
        if isinstance(tr, dict) and tr.get("type") == prefer and tr.get("url"):
            return str(tr["url"])
    for tr in ep.get("transcripts") or []:
        if isinstance(tr, dict) and tr.get("url"):
            return str(tr["url"])
    return None


def episodes_for_player(config: dict[str, Any], show_id: str) -> list[dict[str, Any]]:
    """
    Serialize episodes for the web player (oldest-first listening order).
    """
    audio_base = config.get("audio_base_url")
    out: list[dict[str, Any]] = []
    for ep in config.get("episodes") or []:
        if not isinstance(ep, dict):
            continue
        ep_num = ep.get("episode")
        ep_id = str(ep_num if ep_num is not None else ep.get("guid") or ep["title"])
        audio = resolve_audio_url(str(ep["file"]), str(audio_base) if audio_base else None)
        duration_raw = ep.get("duration")
        try:
            duration_sec = parse_duration(duration_raw)
        except ValueError:
            duration_sec = 0.0
        out.append(
            {
                "id": ep_id,
                "showId": show_id,
                "episode": ep_num,
                "title": str(ep["title"]),
                "description": str(ep.get("description") or "").strip(),
                "audioUrl": audio,
                "mimeType": str(ep.get("type") or "audio/mpeg"),
                "duration": str(duration_raw) if duration_raw is not None else "",
                "durationSec": duration_sec,
                "image": str(ep.get("image") or (config.get("metadata") or {}).get("image") or ""),
                "transcriptUrl": _pick_transcript_url(ep),
                "publicationDate": str(ep.get("publication_date") or ""),
            }
        )
    # Listening order: episode number asc, else publication
    def sort_key(e: dict[str, Any]) -> tuple:
        n = e.get("episode")
        if isinstance(n, int):
            return (0, n)
        return (1, e.get("publicationDate") or "")

    out.sort(key=sort_key)
    return out


def shows_catalog(
    index: dict[str, Any],
    show_configs: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Hub-page list of shows with cover, counts, paths."""
    site = index.get("site") or {}
    base = str(site.get("base_url") or "").rstrip("/") + "/"
    catalog: list[dict[str, Any]] = []
    for show in index.get("shows") or []:
        sid = str(show["id"])
        slug = str(show["slug"])
        cfg = show_configs.get(sid) or {}
        meta = cfg.get("metadata") or {}
        eps = cfg.get("episodes") or []
        page_path = f"{slug}/"
        feed_path = "feed.xml" if show.get("legacy_root_feed") else f"{slug}/feed.xml"
        catalog.append(
            {
                "id": sid,
                "slug": slug,
                "title": str(show.get("title") or meta.get("title") or sid),
                "blurb": str(show.get("blurb") or meta.get("description") or "").strip(),
                "image": str(meta.get("image") or ""),
                "episodeCount": len(eps) if isinstance(eps, list) else 0,
                "pageUrl": urljoin(base, page_path),
                "pagePath": page_path,
                "feedUrl": urljoin(base, feed_path),
                "feedPath": feed_path,
                "link": str(meta.get("link") or urljoin(base, page_path)),
            }
        )
    return catalog
