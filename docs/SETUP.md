# 部署与运维指南

本文是 [README](../README.md) 的补充：R2 上传、Pages 配置、平台提交与进阶选项。

## 架构说明

| 内容 | 放哪 | 原因 |
|------|------|------|
| `feed.xml` / 介绍页 | GitHub Pages | 免费、可版本控制、迁移容易 |
| MP3 / M4A | R2（推荐）或 S3 | 可扩展；R2 无出站流量费 |
| 节目元数据 | 本仓库 `podcast.yaml` | 用 PR / git 管理更新 |

参考思路：[planetoftheweb/podcast-generator](https://github.com/planetoftheweb/podcast-generator)、[vpetersson/podcast-rss-generator](https://github.com/vpetersson/podcast-rss-generator)。本仓库用轻量自维护脚本，避免强依赖外部 Action 镜像。

RSS 地址形态：

```text
https://<GitHub用户名>.github.io/<仓库名>/feed.xml
```

---

## 上传音频到 R2（推荐）

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

---

## 推送到 GitHub 并开启 Pages

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

---

## 提交到播客平台

| 平台 | 入口 |
|------|------|
| Apple Podcasts | [Podcasts Connect](https://podcastsconnect.apple.com) |
| Spotify | [Spotify for Podcasters](https://podcasters.spotify.com) |
| 小宇宙 | 创作者后台 → 添加节目 → 填 RSS |

建议先用 [Podbase Validator](https://podba.se/validate/) 或 [Cast Feed Validator](https://www.castfeedvalidator.com/) 检查 `feed.xml`。

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

## 备选：音频也放仓库

仅适合更新极少、单集很小的情况。把 MP3 放进 `docs/audio/`，`audio_base_url` 写成 Pages 前缀，并考虑 [Git LFS](https://git-lfs.com/)。有一定播放量后带宽与仓库体积都会吃紧，不推荐作为长期方案。

本地 `audio/` 与常见音视频扩展名已在 `.gitignore` 中忽略，请勿把大体积源文件提交进 Git。
