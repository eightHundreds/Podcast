# 设计数据密集型应用

基于《Designing Data-Intensive Applications》(DDIA) 的系列播客第一季素材。

## 目录

```text
audio/           # 源音频（.m4a，默认不进 git）
transcripts/     # 字幕 VTT/SRT/TXT（由 scripts/transcribe.py 生成）
shownotes/       # 每集文字介绍（可手改）
```

## 分集

| 集 | 文件 | 时长 |
|----|------|------|
| 1 | `ep01-云原生分布式还是单机极简.m4a` | 21:20 |
| 2 | `ep02-DDIA架构设计核心权衡.m4a` | 23:57 |
| 3 | `ep03-数据模型背后的架构取舍.m4a` | 24:25 |

## 生成 / 更新字幕（说话人分离）

使用 **mlx-audio + [MOSS-Transcribe-Diarize](https://huggingface.co/OpenMOSS-Team/MOSS-Transcribe-Diarize)**：
端到端转写 + 说话人标签（`[S01]` / `[S02]`…），适合双人播客。

- 模型体积约 **1.7 GB**（首次从 Hugging Face 下载）
- 标签是匿名的，不会自动知道谁是主播/嘉宾，需人工对照一次

```bash
cd 仓库根目录
source .venv/bin/activate
pip install -r requirements.txt

# 单集试跑
python scripts/transcribe.py "shows/设计数据密集型应用/audio/ep01-云原生分布式还是单机极简.m4a"

# 三集全跑
python scripts/transcribe.py "shows/设计数据密集型应用/audio/"*.m4a
```

输出到 `transcripts/`：

| 文件 | 说明 |
|------|------|
| `ep0N.vtt` / `.srt` | 带时间轴字幕（cue 内含 `[S01]`） |
| `ep0N.txt` | 逐段纯文本 |
| `ep0N.dialog.txt` | 按说话人合并的对话稿 |
| `ep0N.json` | 结构化结果（含 speaker） |
| `ep0N.raw.txt` | 模型原始输出 |

发布时把 `transcripts` 同步到 Pages 的 `docs/transcripts/`，并保证 `podcast.yaml` 里 transcript URL 可公网访问。
