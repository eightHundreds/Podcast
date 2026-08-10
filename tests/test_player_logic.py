"""Unit tests for shipped pure player / feed helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from podcast_core.config import load_config, load_shows_index, validate_config
from podcast_core.feed import build_feed, resolve_audio_url
from podcast_core.player_logic import (
    clamp_seek,
    cue_at,
    cue_index_at,
    cue_seek_target,
    format_cue_line,
    format_full_transcript,
    format_time,
    parse_duration,
    parse_vtt,
    progress_key,
    set_playback_rate,
    split_speaker,
)
from podcast_core.site_data import episodes_for_player, shows_catalog


class TestTimeAndSeek:
    def test_format_time(self):
        assert format_time(0) == "0:00"
        assert format_time(65) == "1:05"
        assert format_time(3661) == "1:01:01"
        assert format_time(-3) == "0:00"
        assert format_time(None) == "0:00"

    def test_parse_duration(self):
        assert parse_duration("00:21:20") == 1280.0
        assert parse_duration("1:05") == 65.0
        assert parse_duration(90) == 90.0

    def test_clamp_seek_bounds(self):
        assert clamp_seek(-10, 100) == 0.0
        assert clamp_seek(50, 100) == 50.0
        assert clamp_seek(150, 100) == 100.0
        assert clamp_seek(10, 0) == 0.0
        assert clamp_seek(float("nan"), 100) == 0.0

    def test_set_playback_rate(self):
        assert set_playback_rate(1.0) == 1.0
        assert set_playback_rate(1.4) == 1.5
        assert set_playback_rate(2.0) == 2.0
        assert set_playback_rate(0.1) == 0.75


class TestVtt:
    SAMPLE = """WEBVTT

1
00:00:01.000 --> 00:00:03.500
第一句字幕

2
00:00:04.000 --> 00:00:06.000
第二句

00:00:10.000 --> 00:00:12.000
第三句无序号
"""

    DIARIZED = """WEBVTT

1
00:00:00.060 --> 00:00:01.740
[S01] 欢迎来到The Debate

2
00:00:02.040 --> 00:00:05.000
[S02] 确实如此
"""

    def test_parse_and_cue_at(self):
        cues = parse_vtt(self.SAMPLE)
        assert len(cues) == 3
        assert cues[0]["text"] == "第一句字幕"
        assert cues[0]["start"] == pytest.approx(1.0)
        assert cues[0]["end"] == pytest.approx(3.5)

        assert cue_at(cues, 0.5) is None
        active = cue_at(cues, 2.0)
        assert active is not None
        assert active["text"] == "第一句字幕"
        assert cue_at(cues, 5.0)["text"] == "第二句"
        assert cue_at(cues, 11.0)["text"] == "第三句无序号"
        assert cue_index_at(cues, 5.0) == 1
        assert cue_index_at(cues, 0.2) == -1

    def test_speaker_tags_and_sync_line(self):
        cues = parse_vtt(self.DIARIZED)
        assert len(cues) == 2
        assert cues[0]["speaker"] == "S01"
        assert cues[0]["text"] == "欢迎来到The Debate"
        assert format_cue_line(cues[0]).startswith("S01:")
        # time-sync: at 3s second cue is active
        assert cue_index_at(cues, 3.0) == 1
        assert cue_at(cues, 3.0)["speaker"] == "S02"
        assert split_speaker("[S01] hi")["speaker"] == "S01"

    def test_format_full_transcript_for_copy(self):
        cues = parse_vtt(self.DIARIZED)
        text = format_full_transcript(cues, title="第 1 集")
        assert text.startswith("第 1 集")
        assert "[0:00]" in text
        assert "S01:" in text
        assert "欢迎来到The Debate" in text
        assert "S02:" in text
        plain = format_full_transcript(cues, include_timestamps=False, include_speakers=False)
        assert "[" not in plain
        assert "S01" not in plain
        assert "欢迎来到The Debate" in plain
    def test_cue_click_seek_target(self):
        cues = parse_vtt(self.SAMPLE)
        t = cue_seek_target(cues[1])
        assert t == pytest.approx(4.0)
        # seek target is clamped by player using clamp_seek
        assert clamp_seek(t, 100) == 4.0

    def test_empty_vtt(self):
        assert parse_vtt("") == []
        assert parse_vtt("WEBVTT\n") == []


class TestProgressKey:
    def test_key_shape(self):
        assert progress_key("ddia", "3") == "podcast:progress:ddia:3"


class TestMultiShowConfig:
    def test_shows_index_and_ddia_episodes(self):
        index = load_shows_index(ROOT / "shows.yaml")
        assert len(index["shows"]) >= 1
        ddia = next(s for s in index["shows"] if s["id"] == "ddia")
        cfg_path = ROOT / ddia["config"]
        assert cfg_path.is_file()
        cfg = load_config(cfg_path)
        errors = validate_config(cfg)
        assert errors == []
        eps = cfg["episodes"]
        assert len(eps) == 14
        titles = [e["title"] for e in eps]
        assert any("云原生" in t for t in titles)
        # audio / duration / transcripts present
        ep1 = eps[0]
        assert ep1["file"]
        assert ep1["duration"]
        assert ep1.get("transcripts")
        audio = resolve_audio_url(ep1["file"], cfg["audio_base_url"])
        assert audio.startswith("https://")
        assert "ep01" in audio

        player_eps = episodes_for_player(cfg, "ddia")
        assert len(player_eps) == 14
        assert player_eps[0]["audioUrl"]
        assert player_eps[0]["transcriptUrl"]

        catalog = shows_catalog(index, {"ddia": cfg})
        assert catalog[0]["episodeCount"] == 14
        assert "ddia" in catalog[0]["pagePath"]


class TestFeedBuild:
    def test_build_feed_from_real_config(self, tmp_path):
        cfg = load_config(ROOT / "shows/设计数据密集型应用/podcast.yaml")
        tree = build_feed(cfg, include_future=True)
        root = tree.getroot()
        assert root.tag == "rss"
        channel = root.find("channel")
        assert channel is not None
        assert channel.findtext("title") == "设计数据密集型应用"
        items = channel.findall("item")
        assert len(items) >= 1
        # find enclosure with non-empty url
        enc = items[0].find("enclosure")
        assert enc is not None
        assert enc.get("url")
        titles = [it.findtext("title") for it in items]
        assert any("云原生" in (t or "") for t in titles)
