"""Shared pure helpers for multi-show podcast generation and player logic."""

from .config import (
    load_config,
    load_shows_index,
    resolve_show_paths,
    validate_config,
)
from .feed import build_feed, resolve_audio_url, write_feed
from .player_logic import (
    clamp_seek,
    cue_at,
    cue_index_at,
    format_cue_line,
    format_full_transcript,
    format_time,
    parse_duration,
    parse_vtt,
    progress_key,
    set_playback_rate,
    split_speaker,
)
from .site_data import episodes_for_player, shows_catalog

__all__ = [
    "load_config",
    "load_shows_index",
    "resolve_show_paths",
    "validate_config",
    "build_feed",
    "resolve_audio_url",
    "write_feed",
    "clamp_seek",
    "cue_at",
    "cue_index_at",
    "format_cue_line",
    "format_full_transcript",
    "format_time",
    "parse_duration",
    "parse_vtt",
    "progress_key",
    "set_playback_rate",
    "split_speaker",
    "episodes_for_player",
    "shows_catalog",
]
