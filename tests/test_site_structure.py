"""Static structure checks for multi-show Pages site."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def test_hub_and_show_pages_exist():
    hub = DOCS / "index.html"
    assert hub.is_file()
    html = hub.read_text(encoding="utf-8")
    assert "设计数据密集型应用" in html or "ddia" in html.lower()
    assert "series-card" in html or "site-header" in html

    show = DOCS / "ddia" / "index.html"
    assert show.is_file()
    page = show.read_text(encoding="utf-8")
    assert "<audio" in page
    assert "episode-list" in page
    assert "player-core.js" in page
    assert "btn-play" in page
    assert "seek" in page
    # blog-like structure
    assert "site-header" in page
    assert "article-card" in page or "show-layout" in page
    assert "archive-list" in page or "archive-col" in page
    # synced captions UI + copy full transcript
    assert "live-caption" in page
    assert "btn-transcript" in page
    assert "cue-list" in page
    assert "btn-copy-transcript" in page
    assert "formatFullTranscript" in (DOCS / "assets" / "player-core.js").read_text(
        encoding="utf-8"
    )


def test_episodes_json_has_audio():
    data = json.loads((DOCS / "ddia" / "episodes.json").read_text(encoding="utf-8"))
    eps = data["episodes"]
    assert len(eps) == 14
    assert all(e.get("audioUrl") for e in eps)
    assert any(e.get("transcriptUrl") for e in eps)


def test_show_feed_present():
    feed = (DOCS / "ddia" / "feed.xml").read_text(encoding="utf-8")
    assert "<rss" in feed
    assert "<enclosure" in feed
    assert "设计数据密集型应用" in feed
    assert "ddia/feed.xml" in feed or "eighthundreds.github.io/Podcast/ddia" in feed
    # per-show feeds only — no root feed.xml
    assert not (DOCS / "feed.xml").exists()


def test_shows_yaml_and_config_paths():
    assert (ROOT / "shows.yaml").is_file()
    assert (ROOT / "shows" / "设计数据密集型应用" / "podcast.yaml").is_file()
