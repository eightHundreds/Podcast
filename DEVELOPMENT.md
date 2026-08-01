# 技术说明（维护者）

本仓库如何托管与发布播客。听众请看 [README.md](README.md)。

## 架构

| 内容 | 位置 | 说明 |
|------|------|------|
| 节目元数据 / 分集列表 | `podcast.yaml` | 日常主要改这个 |
| 介绍页 + RSS + 字幕 | `docs/` → GitHub Pages | 免费、可版本控制 |
| 音频文件 | Cloudflare R2 / S3 | 不进 Git；R2 无出站流量费 |
| 本地素材 | `shows/<节目名>/` | 源音频、转写稿等 |

RSS 形态：`https://<用户名>.github.io/<仓库名>/feed.xml`

## 目录

```text
podcast.yaml
requirements.txt
docs/                    # Pages 站点根（feed、封面、字幕）
scripts/
  generate_feed.py       # YAML → RSS
  transcribe.py          # 可选：本地转写 + 说话人分离
  upload_r2.example.sh
shows/<节目>/
  audio/                 # 源音频（gitignore）
  transcripts/
  shownotes/
.github/workflows/       # 生成 feed 并部署 Pages
```

## 本地环境

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/generate_feed.py --dry-run
python scripts/generate_feed.py   # 写出 docs/feed.xml
```

## 配置 `podcast.yaml`

1. `metadata`：标题、简介、作者、邮箱、封面（https 绝对 URL）
2. `link` / `rss_feed_url` / `image` 与真实 GitHub Pages 地址一致
3. `audio_base_url`：R2/S3 公开前缀
4. `episodes`：标题、简介、`publication_date`、`file`、`duration`、`length`（字节）

```bash
wc -c ep001.mp3
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 ep001.mp3
```

封面：JPEG/PNG，**1400×1400 ~ 3000×3000** 正方形。可放 R2 或 `docs/cover.png`。  
Apple 分类示例：`Technology`；语言：`zh-cn`。完整列表见 [Apple Podcasts categories](https://podcasters.apple.com/support/1691-apple-podcasts-categories)。

## 上传音频到 R2

1. 创建 R2 bucket，开启 Public access 或自定义域名
2. 创建 API Token，按 `.env.example` 写本地 `.env`
3. 上传：

```bash
chmod +x scripts/upload_r2.example.sh
set -a && source .env && set +a
./scripts/upload_r2.example.sh ./ep001.mp3 ep001.mp3
```

将公开 URL 与 `length` 写入 `podcast.yaml`。也可用控制台、`aws s3 cp`、`rclone`。

## 部署 GitHub Pages

1. push 到 GitHub
2. **Settings → Pages** → Source 选 **GitHub Actions**
3. 等待 Actions 中 `Generate Podcast Feed` 成功

改仓库名时，同步改 `podcast.yaml` 里的相关 URL。

## 发布一集

1. 导出音频，上传到 R2/S3  
2. 在 `podcast.yaml` 的 `episodes` 追加一集  
3. 需要字幕则跑转写，并把 VTT/SRT 放到 `docs/transcripts/`  
4. `python scripts/generate_feed.py --dry-run`  
5. `git commit && git push` → CI 更新 Feed  

提交平台前可用 [Podbase](https://podba.se/validate/) 校验 Feed。  
平台入口： [Apple](https://podcastsconnect.apple.com) · [Spotify](https://podcasters.spotify.com) · 小宇宙创作者后台。

## 字幕转写（可选）

使用 **mlx-audio + [MOSS-Transcribe-Diarize](https://huggingface.co/OpenMOSS-Team/MOSS-Transcribe-Diarize)**：端到端转写 + 说话人标签（`[S01]` / `[S02]`…）。

- 模型约 **1.7 GB**（首次从 Hugging Face 下载）
- 标签匿名，需人工对照主播/嘉宾

```bash
source .venv/bin/activate
python scripts/transcribe.py "shows/设计数据密集型应用/audio/ep01-云原生分布式还是单机极简.m4a"
python scripts/transcribe.py "shows/设计数据密集型应用/audio/"*.m4a
```

输出到该节目 `transcripts/`：

| 文件 | 说明 |
|------|------|
| `ep0N.vtt` / `.srt` | 带时间轴字幕（含 `[S01]`） |
| `ep0N.txt` | 逐段纯文本 |
| `ep0N.dialog.txt` | 按说话人合并的对话稿 |
| `ep0N.json` | 结构化结果 |
| `ep0N.raw.txt` | 模型原始输出 |

发布时同步到 `docs/transcripts/`，并在 `podcast.yaml` 中配置可公网访问的 transcript URL。

## 备选：音频放仓库

仅适合极少更新、单集很小的情况：放进 `docs/audio/`，`audio_base_url` 用 Pages 前缀，可考虑 [Git LFS](https://git-lfs.com/)。有播放量后不推荐。  
源音频扩展名已在 `.gitignore` 中忽略。
