"""Drive the shipped docs/assets/player-core.js via Node (real path)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE_JS = ROOT / "docs" / "assets" / "player-core.js"


@pytest.fixture(scope="module")
def node_bin():
    bin_path = shutil.which("node")
    if not bin_path:
        pytest.skip("node not available")
    return bin_path


def run_core(node_bin: str, expr: str) -> str:
    """Evaluate expr after loading player-core; print JSON result."""
    script = f"""
const core = require({json.dumps(str(CORE_JS))});
const result = ({expr});
process.stdout.write(JSON.stringify(result));
"""
    proc = subprocess.run(
        [node_bin, "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(f"node failed: {proc.stderr}\n{proc.stdout}")
    return proc.stdout


def test_js_format_time_and_clamp(node_bin):
    out = run_core(
        node_bin,
        "{ t: core.formatTime(65), c1: core.clampSeek(-5, 100), c2: core.clampSeek(200, 100), r: core.setPlaybackRate(1.6) }",
    )
    data = json.loads(out)
    assert data["t"] == "1:05"
    assert data["c1"] == 0
    assert data["c2"] == 100
    assert data["r"] == 1.5


def test_js_vtt_cue_seek(node_bin):
    vtt = """WEBVTT

00:00:01.000 --> 00:00:03.000
hello

00:00:05.000 --> 00:00:07.000
[S02] world
"""
    out = run_core(
        node_bin,
        f"""
(() => {{
  const cues = core.parseVtt({json.dumps(vtt)});
  const active = core.cueAt(cues, 6);
  const idx = core.cueIndexAt(cues, 6);
  return {{
    n: cues.length,
    text: active && active.text,
    speaker: active && active.speaker,
    idx: idx,
    line: core.formatCueLine(active),
    seek: core.cueSeekTarget(cues[0]),
    key: core.progressKey('ddia', '1'),
  }};
}})()
""",
    )
    data = json.loads(out)
    assert data["n"] == 2
    assert data["text"] == "world"
    assert data["speaker"] == "S02"
    assert data["idx"] == 1
    assert data["line"].startswith("S02:")
    assert data["seek"] == 1
    assert data["key"] == "podcast:progress:ddia:1"


def test_js_format_full_transcript(node_bin):
    vtt = """WEBVTT

00:00:01.000 --> 00:00:03.000
[S01] hello

00:00:05.000 --> 00:00:07.000
[S02] world
"""
    out = run_core(
        node_bin,
        f"""
(() => {{
  const cues = core.parseVtt({json.dumps(vtt)});
  return core.formatFullTranscript(cues, {{ title: 'Ep 1', includeTimestamps: true, includeSpeakers: true }});
}})()
""",
    )
    data = json.loads(out)
    assert data.startswith("Ep 1")
    assert "[0:01]" in data
    assert "S01: hello" in data
    assert "S02: world" in data


def test_js_audio_cache_ttl(node_bin):
    out = run_core(
        node_bin,
        """
(() => {
  const now = 1e9;
  const ttl = core.AUDIO_CACHE_TTL_MS;
  const headers = { get: (k) => (k === core.AUDIO_CACHE_META_HEADER ? String(now) : null) };
  return {
    ttl,
    name: core.AUDIO_CACHE_NAME,
    fresh: core.isAudioCacheFresh(now, now),
    edge: core.isAudioCacheFresh(now, now + ttl),
    expired: core.isAudioCacheFresh(now, now + ttl + 1),
    miss: core.audioCacheDecision(null, now),
    decision: core.audioCacheDecision(now, now + ttl + 1),
    cachedAt: core.cachedAtFromHeaders(headers),
    evict: core.expiredAudioCacheUrls([
      { url: 'a', cachedAt: now },
      { url: 'b', cachedAt: now - ttl - 1 },
    ], now),
  };
})()
""",
    )
    data = json.loads(out)
    assert data["ttl"] == 7 * 24 * 60 * 60 * 1000
    assert data["name"] == "podcast-audio-v1"
    assert data["fresh"] is True
    assert data["edge"] is True
    assert data["expired"] is False
    assert data["miss"] == "miss"
    assert data["decision"] == "expired"
    assert data["cachedAt"] == 1e9
    assert data["evict"] == ["b"]


def test_player_core_file_exists():
    assert CORE_JS.is_file()
    text = CORE_JS.read_text(encoding="utf-8")
    assert "clampSeek" in text
    assert "parseVtt" in text
    assert "setPlaybackRate" in text
    assert "isAudioCacheFresh" in text
