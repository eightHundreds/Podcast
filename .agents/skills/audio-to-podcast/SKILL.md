---
name: audio-to-podcast
description: >
  执行「音频→字幕→播客」流水线（本地音频转字幕并发布到可订阅的 RSS）。
  在用户要发布/更新一集播客、把 m4a/mp3 转成字幕、用 wrangler 上传 R2、
  改 podcast.yaml 并重生 feed/站点、补单集封面、核验线上 feed，
  或在本仓库自托管多节目 GitHub Pages 播客时使用。
---

# 音频 → 字幕 → 播客

工作单位是一集 **episode**。按 **pipeline** 顺序做完再进入下一步，禁止为赶后续步骤提前收工。

**本仓库路径：** 首次改文件前先读 [`project-map.md`](project-map.md)。

**排错**（未来发布时间被 CI 裁掉、错章音频、播放器里「没有字幕」）：见 [`gotchas.md`](gotchas.md)。

## 默认：完整上线一集

按顺序执行。仅当用户明确只要某一分支时，才走下方「部分分支」。

### 1. 落盘音频

- 放到该节目 `audio/`（默认 gitignore）。优先稳定文件名：`ep0N.m4a` 或 `ep0N-<标题>.m4a`。
- 记下 **duration**（`HH:MM:SS`）与 **length**（字节）：`ffprobe` / `wc -c`。

**完成标准：** 本地路径存在，且 duration、length 已确定。

### 2. 上传音频（R2）

- 优先 **wrangler**（本机 OAuth 登录）。禁止把真实 Access Key 写进仓库。
- 对象 key 必须与该节目 `podcast.yaml` 中 `audio_base_url` + 分集 `file` 一致。
- 示例：`wrangler r2 object put "podcast-audio/<前缀>/<file>" --file <本地路径> --content-type "audio/mp4" --remote`

**完成标准：** 公开 URL HEAD（或 Range GET）返回 HTTP 200。

### 3. 字幕

- 转写：`python scripts/transcribe.py <音频>`（mlx-audio + MOSS-Transcribe-Diarize；说话人 `[S01]`…）。
- 校对只做 **typo-only**：改 ASR 错别字/乱码，不改写语义、不「润色成文」。
- 发布用 VTT/SRT/TXT 放到该节目 **publish** 的字幕路径（见 project-map）；json/dialog 等源稿留在节目 `transcripts/`。

**完成标准：** 已发布 vtt+srt；抽样复读，无明显残留 ASR 硬伤。

### 4. 标题与 yaml

- 标题/简介以 **字幕内容**（及适用时的书章节）为准，不要只信文件名。
- 在该节目 `podcast.yaml` 增改分集：`title`、`description`、`publication_date`、`file`、`type`、`duration`、`length`、`episode`，可选 `image`、`transcripts` URL。
- `publication_date` 必须 **feed-safe**：已过发布时间，或生成时带 `--include-future`，且 **CI 与本地一致**。

**完成标准：** yaml 校验通过（`generate_feed` dry-run 或正式生成成功）。

### 5. 封面（缺图或标题主题变了时）

- 单集图 1400×1400，系列风格统一。标题/EP 号用排版脚本叠字（若项目有）。
- 节目总封面：`metadata.image`；单集：`episodes[].image` → `itunes:image`。

**完成标准：** PNG 落在 Pages 对应路径，yaml 中 URL 与文件名一致。

### 6. 生成并发布

- 优先 `python scripts/generate_all.py`（feed + 站点）。否则按 project-map 分步生成。
- **仅当用户要求 commit/push 时才提交。** 禁止 force-push。

**完成标准：** 本地 feed 含该集；push 后线上 feed 条目数正确，enclosure/字幕 URL 抽样 200（若用户暂缓 push 则本地完成即可）。

## 部分分支

| 用户意图 | 只跑 |
|----------|------|
| 字幕 / 转写 / 校对 | §3（远端无音频时再补 §1–2） |
| 仅上传 / R2 | §1–2 |
| 仅 feed / RSS / 站点 | §4（yaml 有改时）+ §6 |
| 仅封面 | §5 + yaml image + 需要时 §6 |
| 核验线上 RSS | [`gotchas.md`](gotchas.md) 线上检查 |

## 硬性规则

1. **密钥不进 git。** R2 密钥只用 wrangler 登录或被 ignore 的 `.env`。
2. **yaml 是真相源**：标题、文件、length、字幕/封面 URL 只改 yaml；feed 由脚本生成，不手改当主配置。
3. 字幕 **typo-only**。章节认定：字幕口播自称 + 正文优先于文件名；音频内容与标题不符则换音频或改标题（见 gotchas）。
4. **AntennaPod 类客户端** 的 `podcast:transcript` 多在菜单/弹窗，不是始终内嵌卡拉 OK；勿在 feed 里「修播放器 UI」。
