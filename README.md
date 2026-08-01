# Podcast

自托管播客脚手架：**GitHub Pages 托管 RSS + 封面页，音频放对象存储（Cloudflare R2 / AWS S3）**。

```
podcast.yaml          # 节目信息 + 每一集（你主要改这个）
scripts/generate_feed.py
docs/                 # GitHub Pages 站点根目录
  index.html
  feed.xml            # 由脚本/CI 生成
.github/workflows/    # push 后自动生成 feed 并部署 Pages
```

RSS 地址形态：

```text
https://<GitHub用户名>.github.io/<仓库名>/feed.xml
```

把该地址提交给 Apple Podcasts、Spotify、小宇宙等即可。

---

## 为什么这样拆

| 内容 | 放哪 | 原因 |
|------|------|------|
| `feed.xml` / 介绍页 | GitHub Pages | 免费、可版本控制、迁移容易 |
| MP3 / M4A | R2（推荐）或 S3 | 无限扩展、R2 无出站流量费 |
| 节目元数据 | 本仓库 `podcast.yaml` | 用 PR/git 管理更新 |

参考实现思路：[planetoftheweb/podcast-generator](https://github.com/planetoftheweb/podcast-generator)、[vpetersson/podcast-rss-generator](https://github.com/vpetersson/podcast-rss-generator)。本仓库用轻量自维护脚本，避免强依赖外部 Action 镜像。

---

## 快速开始

### 1. 本地环境

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 校验配置
python scripts/generate_feed.py --dry-run

# 生成 docs/feed.xml
python scripts/generate_feed.py
```

### 2. 改成你的节目

编辑 `podcast.yaml`：

1. `metadata`：标题、简介、作者、邮箱、封面 URL
2. 把 `YOUR_GITHUB_USER` / `Podcast` 换成真实 GitHub 用户名与仓库名
3. `audio_base_url`：R2/S3 公开访问前缀
4. `episodes`：每集的标题、简介、发布时间、`file`、时长、文件字节数

获取文件大小与时长示例：

```bash
wc -c ep001.mp3
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 ep001.mp3
# duration 可写成 00:12:34
```

### 3. 上传音频到 R2（推荐）

1. Cloudflare → R2 → 创建 bucket（如 `podcast-audio`）
2. 开启 **Public access** 或绑定自定义域名（如 `audio.example.com`）
3. 创建 R2 API Token，写入 `.env`（参考 `.env.example`）
4. 上传：

```bash
chmod +x scripts/upload_r2.example.sh
set -a && source .env && set +a
./scripts/upload_r2.example.sh ./ep001.mp3 ep001.mp3
```

把打印出的公开 URL / `length` 写进 `podcast.yaml`。

也可用控制台网页上传，或任意兼容 S3 的工具（`aws s3 cp`、`rclone`）。

### 4. 推送到 GitHub 并开启 Pages

```bash
git add .
git commit -m "chore: init podcast scaffold"
git branch -M main
git remote add origin git@github.com:<你的用户名>/<仓库名>.git
git push -u origin main
```

仓库 **Settings → Pages**：

- Source 选 **GitHub Actions**（不要选 “Deploy from a branch”）
- 首次 push 后打开 **Actions**，等 `Generate Podcast Feed` 成功
- 站点：`https://<用户名>.github.io/<仓库名>/`
- Feed：`https://<用户名>.github.io/<仓库名>/feed.xml`

若仓库名不是 `Podcast`，记得同步改 `podcast.yaml` 里的 `link` / `rss_feed_url` / `image`。

### 5. 提交到播客平台

| 平台 | 入口 |
|------|------|
| Apple Podcasts | [Podcasts Connect](https://podcastsconnect.apple.com) |
| Spotify | [Spotify for Podcasters](https://podcasters.spotify.com) |
| 小宇宙 | 创作者后台 → 添加节目 → 填 RSS |

建议先用 [Podbase Validator](https://podba.se/validate/) 或 [Cast Feed Validator](https://www.castfeedvalidator.com/) 检查 `feed.xml`。

---

## 日常更新一集

1. 导出 MP3（建议 64–128 kbps mono/stereo AAC/MP3，按内容定）
2. 上传到 R2：`ep00N.mp3`
3. 在 `podcast.yaml` 的 `episodes` **最上方或任意位置**追加一集（脚本会按时间倒序输出）
4. `python scripts/generate_feed.py --dry-run` 本地校验
5. `git commit && git push` → Actions 自动更新 Feed

---

## 封面图

- 格式：JPEG 或 PNG  
- 尺寸：**1400×1400 ~ 3000×3000**（正方形）  
- 可放 R2，或放 `docs/cover.png`（随 Pages 发布）  
- `metadata.image` 必须是 **https 绝对 URL**

---

## Apple 分类（`metadata.category`）

常用：`Technology`、`News`、`Business`、`Arts`、`Comedy`、`Education`、`Health & Fitness`、`History`、`Music`、`Science`、`Society & Culture`、`Sports`、`True Crime` 等。  
完整列表：[Apple Podcasts categories](https://podcasters.apple.com/support/1691-apple-podcasts-categories)

语言代码示例：`zh-cn`、`zh-tw`、`en-us`。

---

## 目录说明

```text
.
├── podcast.yaml                 # 唯一需要经常改的配置
├── requirements.txt
├── docs/                        # Pages 内容
│   ├── index.html
│   ├── feed.xml                 # 生成物（可提交，CI 会覆盖部署）
│   └── cover.png                # 可选封面
├── scripts/
│   ├── generate_feed.py         # YAML → RSS
│   └── upload_r2.example.sh     # R2 上传示例
├── .env.example
└── .github/workflows/generate-feed.yml
```

本地 `audio/` 目录已在 `.gitignore` 中忽略，请勿把大体积音频提交进 Git。

---

## 备选：音频也放仓库

仅适合更新极少、单集很小的情况。把 MP3 放进 `docs/audio/`，`audio_base_url` 写成 Pages 前缀，并考虑 [Git LFS](https://git-lfs.com/)。有一定播放量后带宽与仓库体积都会吃紧，不推荐作为长期方案。

---

## 许可

脚手架代码可自由用于你的节目；节目内容版权归你所有。
