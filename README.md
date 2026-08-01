# Podcast

自托管播客脚手架：用 Git 管理节目元数据，GitHub Pages 托管 RSS 与介绍页，音频放对象存储（Cloudflare R2 / AWS S3）。

**站点：** [eighthundreds.github.io/Podcast](https://eighthundreds.github.io/Podcast/)  
**RSS：** [feed.xml](https://eighthundreds.github.io/Podcast/feed.xml)

把 RSS 提交给 Apple Podcasts、Spotify、小宇宙等平台即可分发。

## 特性

- **`podcast.yaml` 即配置** — 节目信息与分集列表一处维护
- **GitHub Actions 自动生成 Feed** — push 后更新 `docs/feed.xml` 并部署 Pages
- **音频与仓库分离** — MP3/M4A 走 R2/S3，仓库保持轻量
- **字幕 / 转写脚本** — 可选本地转写（mlx-audio + 说话人分离）
- **多节目目录** — `shows/` 下按节目组织素材与文稿

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 校验配置
python scripts/generate_feed.py --dry-run

# 生成 docs/feed.xml
python scripts/generate_feed.py
```

编辑 `podcast.yaml`：

1. `metadata` — 标题、简介、作者、封面 URL
2. 将链接中的用户名 / 仓库名改成你的
3. `audio_base_url` — 音频公开访问前缀（R2/S3）
4. `episodes` — 每集标题、简介、发布时间、`file`、时长、`length`（字节）

获取文件大小与时长：

```bash
wc -c ep001.mp3
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 ep001.mp3
```

### 部署到 GitHub Pages

1. 推送到 GitHub
2. 仓库 **Settings → Pages** → Source 选 **GitHub Actions**
3. 等待 Actions 中 `Generate Podcast Feed` 成功
4. 用 [Podbase](https://podba.se/validate/) 等校验 Feed，再提交各平台

详细步骤（R2 上传、环境变量、平台入口）见 [docs/SETUP.md](docs/SETUP.md)。

## 发布一集

1. 导出音频，上传到 R2/S3
2. 在 `podcast.yaml` 的 `episodes` 中追加一集
3. `python scripts/generate_feed.py --dry-run` 本地校验
4. `git commit && git push` — CI 自动更新 Feed

## 项目结构

```text
podcast.yaml          # 节目配置（日常主要改这个）
docs/                 # GitHub Pages 根目录
  index.html          # 介绍页
  feed.xml            # 由脚本 / CI 生成
  covers/ transcripts/
scripts/
  generate_feed.py    # YAML → RSS
  transcribe.py       # 可选：本地转写
  upload_r2.example.sh
shows/                # 各节目素材（音频默认不进 Git）
```

## 当前节目

| 节目 | 说明 |
|------|------|
| [设计数据密集型应用](shows/设计数据密集型应用/) | 围绕 DDIA 的架构讨论系列 |

## 许可

脚手架代码可自由用于你的节目；节目内容版权归作者所有。
