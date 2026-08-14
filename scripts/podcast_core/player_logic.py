"""Pure player helpers — shared semantics with docs/assets/player-core.js."""

from __future__ import annotations

import re
import time
from typing import Any


def parse_duration(value: str | float | int | None) -> float:
    """Parse duration string HH:MM:SS / MM:SS / seconds into seconds."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    s = str(value).strip()
    if not s:
        return 0.0
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return max(0.0, float(s))
    parts = s.split(":")
    if not all(re.fullmatch(r"\d+(\.\d+)?", p) for p in parts):
        raise ValueError(f"invalid duration: {value!r}")
    nums = [float(p) for p in parts]
    if len(nums) == 3:
        h, m, sec = nums
        return h * 3600 + m * 60 + sec
    if len(nums) == 2:
        m, sec = nums
        return m * 60 + sec
    if len(nums) == 1:
        return nums[0]
    raise ValueError(f"invalid duration: {value!r}")


def format_time(seconds: float | int | None) -> str:
    """Format seconds as M:SS or H:MM:SS (non-negative)."""
    if seconds is None or seconds != seconds:  # NaN
        seconds = 0.0
    total = int(max(0, float(seconds)))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def clamp_seek(position: float, duration: float) -> float:
    """Clamp seek position into [0, duration]. Duration <= 0 → 0."""
    if duration is None or duration != duration or duration <= 0:
        return 0.0
    if position is None or position != position:
        return 0.0
    if position < 0:
        return 0.0
    if position > duration:
        return float(duration)
    return float(position)


ALLOWED_RATES = (0.75, 1.0, 1.25, 1.5, 1.75, 2.0)


def set_playback_rate(rate: float, allowed: tuple[float, ...] = ALLOWED_RATES) -> float:
    """Snap to nearest allowed playback rate."""
    if rate is None or rate != rate:
        return 1.0
    return min(allowed, key=lambda r: abs(r - float(rate)))


def progress_key(show_id: str, episode_id: str) -> str:
    """localStorage key for resume position."""
    return f"podcast:progress:{show_id}:{episode_id}"


AUDIO_CACHE_TTL_MS = 7 * 24 * 60 * 60 * 1000
AUDIO_CACHE_NAME = "podcast-audio-v1"
AUDIO_CACHE_META_HEADER = "X-Podcast-Cached-At"


def is_audio_cache_fresh(
    cached_at: float | int | str | None,
    now: float | int | None = None,
    ttl_ms: float | int | None = None,
) -> bool:
    """True when cached_at is within ttl_ms of now (default 7 days)."""
    if cached_at is None or cached_at == "":
        return False
    try:
        t = float(cached_at)
        n = time.time() * 1000 if now is None else float(now)
        ttl = float(AUDIO_CACHE_TTL_MS if ttl_ms is None else ttl_ms)
    except (TypeError, ValueError):
        return False
    if t != t or n != n or ttl != ttl or ttl < 0:
        return False
    age = n - t
    return 0 <= age <= ttl


def cached_at_from_headers(headers: Any) -> float | None:
    """Read X-Podcast-Cached-At from a mapping or header-like object."""
    if headers is None:
        return None
    raw = None
    if hasattr(headers, "get"):
        raw = headers.get(AUDIO_CACHE_META_HEADER)
        if raw is None and hasattr(headers, "keys"):
            raw = headers.get(AUDIO_CACHE_META_HEADER.lower())
    if raw is None or raw == "":
        return None
    try:
        n = float(raw)
    except (TypeError, ValueError):
        return None
    if n != n:
        return None
    return n


def audio_cache_decision(
    cached_at: float | int | str | None,
    now: float | int | None = None,
    ttl_ms: float | int | None = None,
) -> str:
    """Return miss / fresh / expired for a cache timestamp."""
    if cached_at is None or cached_at == "":
        return "miss"
    return "fresh" if is_audio_cache_fresh(cached_at, now, ttl_ms) else "expired"


def expired_audio_cache_urls(
    entries: list[dict[str, Any]] | None,
    now: float | int | None = None,
    ttl_ms: float | int | None = None,
) -> list[str]:
    """URLs whose cache timestamp is missing or past TTL."""
    if not entries:
        return []
    out: list[str] = []
    for entry in entries:
        if not entry or not entry.get("url"):
            continue
        if audio_cache_decision(entry.get("cachedAt"), now, ttl_ms) != "fresh":
            out.append(str(entry["url"]))
    return out


_TS_RE = re.compile(
    r"(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})(?:\.(?P<ms>\d{1,3}))?"
)


def _parse_ts(ts: str) -> float:
    m = _TS_RE.fullmatch(ts.strip())
    if not m:
        # also allow M:SS.mmm
        m2 = re.fullmatch(
            r"(?P<m>\d{1,2}):(?P<s>\d{2})(?:\.(?P<ms>\d{1,3}))?", ts.strip()
        )
        if not m2:
            raise ValueError(f"bad VTT timestamp: {ts!r}")
        ms = (m2.group("ms") or "0").ljust(3, "0")[:3]
        return int(m2.group("m")) * 60 + int(m2.group("s")) + int(ms) / 1000.0
    ms = (m.group("ms") or "0").ljust(3, "0")[:3]
    return (
        int(m.group("h")) * 3600
        + int(m.group("m")) * 60
        + int(m.group("s"))
        + int(ms) / 1000.0
    )


def parse_vtt(text: str) -> list[dict[str, Any]]:
    """Parse WebVTT into list of {start, end, text} cues (seconds)."""
    if not text or not str(text).strip():
        return []
    # Normalize newlines; strip BOM
    raw = str(text).lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\n+", raw.strip())
    cues: list[dict[str, Any]] = []
    arrow = re.compile(
        r"^(?:(\d+)\n)?"  # optional cue id
        r"([0-9:.]+)\s*-->\s*([0-9:.]+)(?:\s+.*)?\n"
        r"([\s\S]*)$"
    )
    for block in blocks:
        block = block.strip()
        if not block or block.upper().startswith("WEBVTT"):
            continue
        # STYLE / NOTE regions
        if block.upper().startswith("NOTE") or block.upper().startswith("STYLE"):
            continue
        m = arrow.match(block)
        if not m:
            # try without leading id line already handled
            lines = block.split("\n")
            if len(lines) >= 2 and "-->" in lines[0]:
                head, *body = lines
            elif len(lines) >= 3 and "-->" in lines[1]:
                head, *body = lines[1:]
            else:
                continue
            parts = re.split(r"\s*-->\s*", head, maxsplit=1)
            if len(parts) != 2:
                continue
            start_s, rest = parts
            end_s = rest.split()[0]
            try:
                start = _parse_ts(start_s)
                end = _parse_ts(end_s)
            except ValueError:
                continue
            cue_text = "\n".join(body).strip()
            if cue_text:
                cues.append(_normalize_cue(start, end, cue_text))
            continue
        try:
            start = _parse_ts(m.group(2))
            end = _parse_ts(m.group(3))
        except ValueError:
            continue
        cue_text = m.group(4).strip()
        if cue_text:
            cues.append(_normalize_cue(start, end, cue_text))
    cues.sort(key=lambda c: c["start"])
    return cues


def split_speaker(raw: str) -> dict[str, str]:
    """Parse leading [S01] / S01: speaker tags from diarization exports."""
    s = str(raw or "").strip()
    m = re.match(r"^\[([^\]]+)\]\s*(.*)$", s, re.DOTALL)
    if m:
        return {"speaker": m.group(1).strip(), "text": (m.group(2) or "").strip()}
    m = re.match(r"^(S\d+)\s*[:：]\s*(.*)$", s, re.DOTALL)
    if m:
        return {"speaker": m.group(1).strip(), "text": (m.group(2) or "").strip()}
    return {"speaker": "", "text": s}


def _normalize_cue(start: float, end: float, raw_text: str) -> dict[str, Any]:
    parsed = split_speaker(raw_text)
    return {
        "start": start,
        "end": end,
        "text": parsed["text"],
        "speaker": parsed["speaker"],
        "raw": raw_text,
    }


def cue_index_at(cues: list[dict[str, Any]], t: float) -> int:
    """Index of the cue active at time t, or -1."""
    if not cues:
        return -1
    t = float(t)
    lo, hi, ans = 0, len(cues) - 1, -1
    while lo <= hi:
        mid = (lo + hi) // 2
        if cues[mid]["start"] <= t:
            ans = mid
            lo = mid + 1
        else:
            hi = mid - 1
    if ans < 0:
        return -1
    c = cues[ans]
    if c["start"] <= t < c["end"]:
        return ans
    return -1


def cue_at(cues: list[dict[str, Any]], t: float) -> dict[str, Any] | None:
    """Return the cue active at time t, or None."""
    idx = cue_index_at(cues, t)
    return None if idx < 0 else cues[idx]


def cue_seek_target(cue: dict[str, Any]) -> float:
    """Seconds to seek when user clicks a cue row."""
    return float(cue["start"])


def format_cue_line(cue: dict[str, Any] | None) -> str:
    if not cue:
        return ""
    speaker = cue.get("speaker") or ""
    text = cue.get("text") or cue.get("raw") or ""
    if speaker:
        return f"{speaker}: {text}"
    return str(text)


def format_full_transcript(
    cues: list[dict[str, Any]] | None,
    *,
    include_timestamps: bool = True,
    include_speakers: bool = True,
    title: str | None = None,
) -> str:
    """Plain-text full transcript for copy/export."""
    lines: list[str] = []
    if title:
        lines.extend([str(title), ""])
    if not cues:
        return "\n".join(lines).strip()
    for c in cues:
        body = format_cue_line(c) if include_speakers else (c.get("text") or c.get("raw") or "")
        if include_timestamps:
            lines.append(f"[{format_time(c['start'])}] {body}")
        else:
            lines.append(str(body))
    return "\n".join(lines)
