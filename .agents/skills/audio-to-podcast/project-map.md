# 本仓库地图

在本工作区启动 **pipeline** 时先读此文件。

## 索引

| 用途 | 路径 |
|------|------|
| 多节目索引 | `shows.yaml`（`id`、`slug`、`config`、`publish_dir`） |
| 单节目配置 | `shows/<节目名>/podcast.yaml` |
| 本地音频（gitignore） | `shows/<节目名>/audio/` |
| 转写源稿 | `shows/<节目名>/transcripts/` |
| Pages 根目录 | `docs/` |
| 单节目站点 + RSS | `docs/<slug>/`（`feed.xml`、`index.html`、`episodes.json`） |
| 共享封面/字幕（历史或共用） | `docs/covers/`、`docs/transcripts/` — **以该节目 yaml 里已有 URL 为准** |
| 一键生成 | `python scripts/generate_all.py` |
| 仅 feed | `python scripts/generate_feed.py`（见 `--help`：`--all` 等） |
| 仅站点 | `python scripts/generate_site.py` |
| 转写 | `python scripts/transcribe.py <音频…>`（需 venv + mlx-audio） |
| 封面排版 | `scripts/_layout_episode_covers.py` |
| R2 S3 示例（可选） | `scripts/upload_r2.example.sh` + `.env.example` |
| 维护说明 | `DEVELOPMENT.md` |

## 当前示例节目（ddia）

| 字段 | 值 |
|------|-----|
| slug | `ddia` |
| config | `shows/设计数据密集型应用/podcast.yaml` |
| publish_dir | `docs/ddia` |
| 公开 RSS | `https://eighthundreds.github.io/Podcast/ddia/feed.xml` |
| R2 bucket | `podcast-audio` |
| R2 key 前缀 | `ddia/` |
| `audio_base_url` | 见该节目 `podcast.yaml`（公开 r2.dev 前缀） |

新节目：在 `shows.yaml` 登记，建 `shows/<名>/podcast.yaml` 与素材，再跑 `generate_all.py`。

## 上传（优先 wrangler）

```bash
# 本机需已登录：wrangler whoami
wrangler r2 object put "podcast-audio/ddia/ep0N.m4a" \
  --file "shows/设计数据密集型应用/audio/ep0N.m4a" \
  --content-type "audio/mp4" \
  --remote
```

公开 URL = `audio_base_url` + `file`（非 ASCII 文件名需正确 URL 编码）。

## 生成清单

```bash
source .venv/bin/activate
python scripts/generate_feed.py --dry-run   # 若支持
python scripts/generate_all.py
```

CI 可能在 push 时重生 feed——保持 `publication_date` / `--include-future` **feed-safe**（见 gotchas）。
