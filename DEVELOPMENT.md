# 技术说明（维护者）

本仓库如何托管与发布**多节目**播客。听众请看 [README.md](README.md)。

## 架构

| 内容 | 位置 | 说明 |
|------|------|------|
| 节目索引 | `shows.yaml` | 登记所有节目 slug / 配置路径 |
| 单节目元数据 / 分集 | `shows/<节目>/podcast.yaml` | 日常主要改这个 |
| 介绍页 + 播放器 + RSS + 字幕 | `docs/` → GitHub Pages | 免费、可版本控制 |
| 音频文件 | Cloudflare R2 / S3 | 不进 Git；R2 无出站流量费 |
| 本地素材 | `shows/<节目名>/` | 源音频、转写稿等 |

- **在线收听：** `docs/index.html`（枢纽）→ `docs/<slug>/`（播放器）  
- **RSS：** 每节目 `docs/<slug>/feed.xml`；DDIA 额外兼容 `docs/feed.xml`  
- 对外 RSS 形态示例：`https://<用户名>.github.io/<仓库名>/feed.xml`

## 目录

```text
shows.yaml
requirements.txt
docs/                         # Pages 站点根
  index.html                  # 枢纽：列出全部节目
  shows.json                  # 枢纽数据
  feed.xml                    # DDIA 兼容 RSS（旧订阅地址）
  cover.png / covers / transcripts/   # DDIA 发布资源（URL 已在配置中）
  ddia/
    index.html                # 节目播放页
    episodes.json
    feed.xml
  assets/
    player-core.js            # 纯逻辑（可 Node require 测）
    player.js / player.css / site.css
scripts/
  generate_all.py             # feed + 站点一键生成
  generate_feed.py            # YAML → RSS（支持 --all）
  generate_site.py            # 枢纽 + 节目页
  podcast_core/               # 校验 / feed / VTT / 进度键 等纯函数
  transcribe.py
  _layout_episode_covers.py
  upload_r2.example.sh
shows/<节目>/
  podcast.yaml
  audio/                      # 源音频（gitignore）
  transcripts/                # 转写源稿
  shownotes/
tests/                        # pytest：配置、feed、播放器逻辑
.github/workflows/            # 生成并部署 Pages
```

## 本地环境

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/generate_all.py --dry-run --include-future
python scripts/generate_all.py --include-future
python -m pytest tests/ -q
```

单节目 feed（兼容旧用法）：

```bash
python scripts/generate_feed.py \
  -i shows/设计数据密集型应用/podcast.yaml \
  -o docs/feed.xml --include-future
```

本地预览 Pages：

```bash
python -m http.server 8765 --directory docs
# 打开 http://127.0.0.1:8765/ 与 http://127.0.0.1:8765/ddia/
```

> 播放器脚本使用普通 `<script src>`（非 bare ESM），`file://` 也可打开页面；字幕 fetch 在 `file://` 下可能受浏览器限制，请用本地静态服务验证字幕。

## 配置

### `shows.yaml`

- `site.base_url`：GitHub Pages 根 URL  
- `shows[]`：`id`、`slug`、`config`、`publish_dir`  
- `legacy_root_feed: true`：额外写出 `docs/feed.xml`（保持旧订阅）

### `shows/<节目>/podcast.yaml`

1. `metadata`：标题、简介、作者、邮箱、封面（https 绝对 URL）  
2. `link` / `rss_feed_url` / `image` 与真实 Pages 地址一致  
3. `audio_base_url`：R2/S3 公开前缀  
4. `episodes`：标题、简介、`publication_date`、`file`、`duration`、`length`（字节）、`transcripts`

```bash
wc -c ep001.mp3
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 ep001.mp3
```

封面：JPEG/PNG，**1400×1400 ~ 3000×3000** 正方形。  
Apple 分类示例：`Technology`；语言：`zh-cn`。

## 上传音频到 R2

当前 DDIA 使用 bucket **`podcast-audio`**，对象前缀 **`ddia/`**，公开基址见该节目 `podcast.yaml` 的 `audio_base_url`。

### 方式 A：Wrangler（推荐）

```bash
wrangler r2 object put "podcast-audio/ddia/ep04.m4a" \
  --file "shows/设计数据密集型应用/audio/ep04-软件逻辑战胜物理混乱.m4a" \
  --content-type "audio/mp4" --remote
```

### 方式 B：S3 兼容 API

1. 创建 R2 bucket，开启 r2.dev 公开访问或自定义域名  
2. 创建 API Token，按 `.env.example` 写本地 `.env`  
3. 参考 `scripts/upload_r2.example.sh`

## 转写字幕

```bash
# 详见 scripts/transcribe.py 帮助
python scripts/transcribe.py --help
```

发布时把 VTT/SRT/TXT 拷到 `docs/transcripts/`（或节目配置中的绝对 URL 路径），再 `generate_all`。

## CI

Push 到 `main` 且触及 `shows.yaml` / `shows/**` / `scripts/**` / `docs/**` 时：

1. `generate_all.py --include-future`  
2. `pytest tests/`  
3. 上传 `docs/` 为 GitHub Pages artifact 并部署  

## 播放器行为（验收相关）

| 能力 | 实现 |
|------|------|
| play/pause、seek、时间显示 | `docs/assets/player.js` + `<audio>` |
| 倍速 0.75–2× | `setPlaybackRate`（core） |
| ±15s / +30s | 按钮 + `clampSeek` |
| 切集 | 列表点击 / 播完自动下一集 |
| 进度记忆 | `localStorage` 键 `podcast:progress:<showId>:<epId>` |
| 字幕 | 拉取 VTT → `parseVtt`；点击 cue → seek 到 `start` |
