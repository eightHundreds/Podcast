#!/usr/bin/env python3
"""Generate GitHub Pages hub + per-show player pages from shows.yaml."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from podcast_core.config import load_config, load_shows_index, resolve_show_paths, validate_config
from podcast_core.site_data import episodes_for_player, shows_catalog

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"
ASSETS = DOCS / "assets"


def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _short_blurb(text: str, n: int = 140) -> str:
    t = " ".join(str(text).split())
    if len(t) <= n:
        return t
    return t[: n - 1].rstrip() + "…"


def _site_chrome(
    *,
    site_title: str,
    base: str,
    active: str | None = None,
    feed_href: str | None = None,
) -> str:
    """Shared masthead + footer fragments. base is '' for hub or '../' for show pages."""
    home = f"{base}." if base else "./"
    if base == "../":
        home = "../"
    home_href = home if home.endswith("/") or home in ("./", "../") else home + "/"
    # normalize
    if base == "../":
        home_href = "../"
        assets_prefix = "../"
    else:
        home_href = "./"
        assets_prefix = ""

    nav_home_cur = ' aria-current="page"' if active == "home" else ""
    nav_shows_cur = ' aria-current="page"' if active == "shows" else ""

    feed_nav = ""
    if feed_href:
        feed_nav = f'<a href="{_esc(feed_href)}" id="nav-feed">RSS</a>'

    header = f"""
  <header class="site-header">
    <div class="wrap">
      <a class="brand" href="{home_href}">
        <span class="brand-name">{_esc(site_title)}</span>
        <span class="brand-tag">按书分章节</span>
      </a>
      <nav class="site-nav" aria-label="主导航">
        <a href="{home_href}"{nav_home_cur}>首页</a>
        <a href="{home_href}#series"{nav_shows_cur}>节目</a>
        {feed_nav}
      </nav>
    </div>
  </header>"""

    footer = f"""
  <footer class="site-footer">
    <div class="wrap">
      <div class="footer-grid">
        <div class="footer-brand-col">
          <p class="footer-brand">{_esc(site_title)}</p>
          <p class="footer-copy">围绕一本书做系列讨论。在浏览器里直接听，也可以用 RSS 订阅到任意播客客户端。</p>
        </div>
        <div class="footer-col">
          <h4>浏览</h4>
          <ul>
            <li><a href="{home_href}">首页</a></li>
            <li><a href="{home_href}#series">全部节目</a></li>
            {"<li><a href='" + _esc(feed_href) + "'>本节目 RSS</a></li>" if feed_href else ""}
          </ul>
        </div>
        <div class="footer-col">
          <h4>收听</h4>
          <ul>
            <li>在线播放与字幕</li>
            <li>倍速 · 进度记忆</li>
            <li>复制全文转写</li>
          </ul>
        </div>
      </div>
      <div class="footer-bottom">
        <span>源码与配置见仓库 README</span>
        <span>GitHub Pages</span>
      </div>
    </div>
  </footer>"""
    return header, footer, assets_prefix


def write_hub(catalog: list[dict], site: dict) -> Path:
    total_eps = sum(int(s.get("episodeCount") or 0) for s in catalog)
    show_count = len(catalog)
    site_title = site.get("title") or "读书播客"
    lead = site.get("description") or "按书分章节的系列播客。浏览器直接听，也可 RSS 订阅。"
    header, footer, _ = _site_chrome(site_title=site_title, base="", active="home")

    cards = []
    for show in catalog:
        img = show.get("image") or ""
        cover = (
            f'<img class="series-cover" src="{_esc(img)}" alt="" width="280" height="280" />'
            if img
            else '<div class="series-cover" aria-hidden="true"></div>'
        )
        blurb = _short_blurb(show.get("blurb") or "", 200)
        cards.append(
            f"""
        <a class="series-card" href="{_esc(show['pagePath'])}">
          {cover}
          <div class="series-body">
            <p class="series-label">系列 · {int(show['episodeCount'])} 集</p>
            <h3>{_esc(show['title'])}</h3>
            <p class="blurb">{_esc(blurb)}</p>
            <div class="series-actions">
              <span class="btn btn-primary">阅读并收听</span>
              <span class="btn btn-secondary">进入节目</span>
            </div>
          </div>
        </a>"""
        )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_esc(site_title)}</title>
  <meta name="description" content="{_esc(lead)}" />
  <link rel="stylesheet" href="assets/site.css" />
</head>
<body class="hub">
{header}
  <main>
    <section class="hub-hero">
      <div class="wrap">
        <p class="hub-kicker">Audio journal</p>
        <h1>{_esc(site_title)}</h1>
        <p class="deck">{_esc(lead)}</p>
        <div class="hub-meta-row">
          <span><strong>{show_count}</strong> 个系列</span>
          <span><strong>{total_eps}</strong> 篇文章 / 分集</span>
          <span>在线播放 · RSS 订阅</span>
        </div>
      </div>
    </section>

    <section class="section" id="series" aria-label="节目">
      <div class="wrap">
        <div class="section-head">
          <h2>系列</h2>
          <p class="section-note">每本书一个栏目，按章节推进</p>
        </div>
        {''.join(cards)}
      </div>
    </section>

    <section class="section" id="about" aria-label="关于">
      <div class="wrap">
        <div class="section-head">
          <h2>如何使用</h2>
          <p class="section-note">像读博客一样听</p>
        </div>
        <div class="about-grid">
          <div class="about-card">
            <h3>在线阅读 + 播放</h3>
            <p>进入系列页，左侧是当前分集正文与播放器，右侧是分集列表。进度会记在本机浏览器。</p>
          </div>
          <div class="about-card">
            <h3>字幕与转写</h3>
            <p>可打开同步字幕跟随播放；也可一键复制全文转写，方便做笔记或二次引用。</p>
          </div>
          <div class="about-card">
            <h3>RSS 订阅</h3>
            <p>每个系列提供 Feed。可加入 Apple Podcasts、Spotify、小宇宙、AntennaPod 等客户端。</p>
          </div>
          <div class="about-card">
            <h3>按书分章节</h3>
            <p>不是杂谈合集，而是围绕一本书的连续讨论。适合边读书边听，或当作章节导读。</p>
          </div>
        </div>
      </div>
    </section>
  </main>
{footer}
</body>
</html>
"""
    out = DOCS / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


def write_show_page(show: dict, config: dict, episodes: list[dict]) -> Path:
    publish = REPO_ROOT / str(show["publish_dir"])
    publish.mkdir(parents=True, exist_ok=True)

    meta = config.get("metadata") or {}
    title = str(show.get("title") or meta.get("title") or show["id"])
    feed_href = "./feed.xml"
    image = str(meta.get("image") or "")
    desc = str(meta.get("description") or show.get("blurb") or "").strip()
    desc_ui = desc  # full prose on show page
    site_title = "读书播客"
    ep_count = len(episodes)

    header, footer, _ = _site_chrome(
        site_title=site_title,
        base="../",
        active="shows",
        feed_href=feed_href,
    )

    payload = {
        "show": {
            "id": show["id"],
            "slug": show["slug"],
            "title": title,
            "description": desc,
            "image": image,
            "feedUrl": meta.get("rss_feed_url") or "",
            "feedPath": feed_href,
            "author": str(meta.get("author") or ""),
        },
        "episodes": episodes,
    }
    (publish / "episodes.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    embedded = json.dumps(payload, ensure_ascii=False)

    cover_html = (
        f'<img class="show-cover" src="{_esc(image)}" alt="" width="168" height="168" />'
        if image
        else ""
    )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_esc(title)} · {_esc(site_title)}</title>
  <meta name="description" content="{_esc(_short_blurb(desc, 160))}" />
  <link rel="stylesheet" href="../assets/site.css" />
  <link rel="stylesheet" href="../assets/player.css" />
</head>
<body class="show-page" data-show-id="{_esc(show['id'])}">
{header}

  <section class="show-masthead">
    <div class="wrap">
      <p class="show-breadcrumb">
        <a href="../">首页</a>
        <span class="sep">/</span>
        <a href="../#series">节目</a>
        <span class="sep">/</span>
        <span>{_esc(title)}</span>
      </p>
      <div class="show-intro">
        {cover_html}
        <div class="show-intro-text">
          <h1>{_esc(title)}</h1>
          <p class="show-byline">{ep_count} 集 · 系列讨论 · 可在线听与订阅</p>
          <p class="lead">{_esc(desc_ui)}</p>
          <div class="show-toolbar">
            <button type="button" class="btn btn-primary" id="btn-listen-top">开始收听</button>
            <div class="feed-chip">
              <span class="label">RSS</span>
              <a class="feed-link" id="feed-link" href="{_esc(feed_href)}">{_esc(feed_href)}</a>
              <button type="button" class="btn btn-ghost" id="copy-feed" data-feed="{_esc(feed_href)}" style="padding:0.25rem 0.55rem;font-size:0.78rem">复制</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <main class="wrap show-layout">
    <div class="reading-col">
      <p class="col-label">正在阅读 / 收听</p>
      <article class="article-card" aria-label="当前分集">
        <div class="article-head">
          <img id="np-cover" class="article-cover" alt="" width="88" height="88" />
          <div>
            <p id="np-ep" class="article-kicker">选择一集开始</p>
            <h2 id="np-title" class="article-title">从右侧列表选择一集</h2>
            <p id="np-meta" class="article-meta"></p>
          </div>
        </div>

        <div class="article-body">
          <p id="np-desc" class="prose"></p>
        </div>

        <div class="player-dock" aria-label="播放器">
          <audio id="audio" preload="metadata"></audio>

          <div id="live-caption" class="live-caption" hidden aria-live="polite" aria-atomic="true">
            <span id="live-caption-speaker" class="live-caption-speaker" hidden></span>
            <span id="live-caption-text" class="live-caption-text">开启字幕后显示当前台词</span>
          </div>

          <div class="controls">
            <div class="player-bar">
              <div class="transport">
                <button type="button" class="btn icon" id="btn-back15" title="快退 15 秒" aria-label="快退 15 秒"><span class="skip-label">−15</span></button>
                <button type="button" class="btn play" id="btn-play" aria-label="播放" data-playing="false">
                  <span class="icon-stack" aria-hidden="true">
                    <span class="icon-layer icon-play is-visible">
                      <svg viewBox="0 0 24 24" fill="currentColor" width="22" height="22"><path d="M8 5.14v13.72a1 1 0 0 0 1.54.84l10.12-6.86a1 1 0 0 0 0-1.68L9.54 4.3A1 1 0 0 0 8 5.14z"/></svg>
                    </span>
                    <span class="icon-layer icon-pause is-hidden">
                      <svg viewBox="0 0 24 24" fill="currentColor" width="22" height="22"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>
                    </span>
                  </span>
                </button>
                <button type="button" class="btn icon" id="btn-fwd30" title="快进 30 秒" aria-label="快进 30 秒"><span class="skip-label">+30</span></button>
              </div>
              <div class="scrub">
                <span id="time-cur" class="time">0:00</span>
                <input type="range" id="seek" min="0" max="1000" value="0" step="1" aria-label="进度" />
                <span id="time-dur" class="time">0:00</span>
              </div>
              <div class="extras">
                <label class="rate-label">倍速
                  <select id="rate" aria-label="播放倍速">
                    <option value="0.75">0.75×</option>
                    <option value="1" selected>1×</option>
                    <option value="1.25">1.25×</option>
                    <option value="1.5">1.5×</option>
                    <option value="1.75">1.75×</option>
                    <option value="2">2×</option>
                  </select>
                </label>
                <button type="button" class="btn btn-ghost" id="btn-transcript" aria-pressed="false" title="字幕跟随播放">字幕</button>
              </div>
            </div>
          </div>
        </div>

        <div id="transcript-panel" class="transcript-panel" hidden>
          <div class="transcript-head">
            <p id="caption-status" class="caption-status" aria-live="polite">字幕</p>
            <button type="button" class="btn btn-ghost btn-copy-transcript" id="btn-copy-transcript" disabled title="复制本集全部字幕">复制</button>
          </div>
          <div class="transcript-scroll">
            <ol id="cue-list" class="cue-list"></ol>
          </div>
        </div>
      </article>
    </div>

    <aside class="archive-col" aria-label="分集列表">
      <p class="col-label">分集 · {ep_count}</p>
      <ol id="episode-list" class="archive-list episode-list"></ol>
    </aside>
  </main>

{footer}

  <script type="application/json" id="show-data">{embedded.replace("</", "<\\/")}</script>
  <script src="../assets/player-core.js"></script>
  <script src="../assets/player.js"></script>
  <script>
    (function () {{
      var a = document.getElementById("feed-link");
      var navFeed = document.getElementById("nav-feed");
      try {{
        var abs = new URL(a.getAttribute("href"), location.href).href;
        a.textContent = abs;
        a.href = abs;
        if (navFeed) navFeed.href = abs;
        var btn = document.getElementById("copy-feed");
        if (btn) btn.dataset.feed = abs;
      }} catch (e) {{}}
      document.getElementById("copy-feed").addEventListener("click", function () {{
        var url = this.dataset.feed || a.href;
        if (navigator.clipboard && navigator.clipboard.writeText) {{
          navigator.clipboard.writeText(url).then(function () {{
            btnFlash(this, "已复制");
          }}.bind(this));
        }} else {{
          prompt("复制 Feed URL", url);
        }}
      }});
      function btnFlash(el, t) {{
        var old = el.textContent;
        el.textContent = t;
        setTimeout(function () {{ el.textContent = old; }}, 1200);
      }}
      var topListen = document.getElementById("btn-listen-top");
      if (topListen) {{
        topListen.addEventListener("click", function () {{
          var play = document.getElementById("btn-play");
          if (play) play.click();
          var dock = document.querySelector(".player-dock");
          if (dock) dock.scrollIntoView({{ behavior: "smooth", block: "center" }});
        }});
      }}
      PodcastPlayer.mount(document.getElementById("show-data"));
    }})();
  </script>
</body>
</html>
"""
    out = publish / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


def generate(index_path: Path, *, dry_run: bool = False) -> None:
    index = load_shows_index(index_path)
    site = index.get("site") or {}
    show_configs: dict[str, dict] = {}
    for show in index["shows"]:
        paths = resolve_show_paths(REPO_ROOT, show)
        cfg = load_config(paths["config"])
        errors = validate_config(cfg)
        if errors:
            print(f"配置校验失败 ({show['id']}):", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            sys.exit(1)
        show_configs[str(show["id"])] = cfg

    catalog = shows_catalog(index, show_configs)
    if dry_run:
        print(f"dry-run: {len(catalog)} 个节目，未写页面")
        return

    ASSETS.mkdir(parents=True, exist_ok=True)
    hub = write_hub(catalog, site)
    print(f"✓ 枢纽页: {hub}")
    (DOCS / "shows.json").write_text(
        json.dumps({"site": site, "shows": catalog}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"✓ 目录数据: {DOCS / 'shows.json'}")

    for show in index["shows"]:
        cfg = show_configs[str(show["id"])]
        eps = episodes_for_player(cfg, str(show["id"]))
        page = write_show_page(show, cfg, eps)
        print(f"✓ 节目页: {page} ({len(eps)} 集)")


def main() -> None:
    parser = argparse.ArgumentParser(description="生成多节目 GitHub Pages 站点")
    parser.add_argument(
        "--index",
        type=Path,
        default=REPO_ROOT / "shows.yaml",
        help="多节目索引（默认 shows.yaml）",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    generate(args.index, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
