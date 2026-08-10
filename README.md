# 读书播客

多节目播客平台：每个节目基于一本书、按章节做系列讨论。  
站点托管在 GitHub Pages，**可在浏览器内直接播放**；也提供 RSS 供客户端订阅。

## 在线收听

- **节目枢纽：** [eighthundreds.github.io/Podcast](https://eighthundreds.github.io/Podcast/)
- **DDIA 节目页（可播放）：** […/ddia/](https://eighthundreds.github.io/Podcast/ddia/)
- **DDIA RSS（兼容旧地址）：** [feed.xml](https://eighthundreds.github.io/Podcast/feed.xml)

播放器支持：播放/暂停、拖拽进度、倍速、±15/30 秒、分集切换、进度记忆、字幕点击跳转。

## 节目

| 节目 | 书目 | 集数 | 在线听 | RSS |
|------|------|------|--------|-----|
| [设计数据密集型应用](shows/设计数据密集型应用/) | *Designing Data-Intensive Applications* | 14 | [播放页](https://eighthundreds.github.io/Podcast/ddia/) | [feed.xml](https://eighthundreds.github.io/Podcast/feed.xml) |

### 设计数据密集型应用 · 分集

| 集 | 标题 | 时长 |
|----|------|------|
| 1 | 云原生分布式还是单机极简 | 21:20 |
| 2 | DDIA 架构设计核心权衡 | 23:57 |
| 3 | 数据模型背后的架构取舍 | 24:25 |
| 4 | 存储与检索：B 树、LSM 与索引 | 24:11 |
| 5 | 编码与演化 | 20:22 |
| 6 | 复制：让数据分身保持一致 | 23:28 |
| 7 | 分片：切开数据世界的魔法水晶 | 16:07 |
| 8 | 事务：断电也要钱货两清 | 26:22 |
| 9 | 分布式系统的麻烦 | 15:14 |
| 10 | 一致性与共识 | 21:53 |
| 11 | 批处理：派生数据与时间旅行 | 28:00 |
| 12 | 流处理：奔流不息的数据之河 | 24:49 |
| 13 | 系统必须出海：综合架构权衡 | 27:41 |
| 14 | 算法决策与数据伦理 | 21:20 |

字幕与封面见 `docs/transcripts/`、`docs/covers/`（发布用）；源素材在 `shows/设计数据密集型应用/`。

## 添加新节目

1. 在 `shows/<节目名>/` 下创建 `podcast.yaml`、`audio/`、`transcripts/` 等  
2. 在根目录 `shows.yaml` 登记 `id` / `slug` / `config` / `publish_dir`  
3. 运行 `python scripts/generate_all.py --include-future`  
4. 将发布用字幕/封面放到 `docs/` 对应路径（或节目 `publish_dir`），音频上传到 R2  

详见 [DEVELOPMENT.md](DEVELOPMENT.md)。

## 仓库结构（摘要）

```text
shows.yaml                 # 多节目索引
shows/<节目>/
  podcast.yaml             # 该节目元数据 + 分集
  audio/  transcripts/ …
docs/                      # GitHub Pages 根
  index.html               # 枢纽页
  feed.xml                 # DDIA 兼容 RSS
  ddia/                    # 节目页 + episodes.json + feed
  assets/                  # 播放器 JS/CSS
scripts/
  generate_all.py          # 一键生成 feed + 站点
  podcast_core/            # 可单测纯逻辑
tests/
```

---

© 2026 读书播客
