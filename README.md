# 设计数据密集型应用

围绕《Designing Data-Intensive Applications》（DDIA）的系列播客。

从「云原生分布式 vs 单机极简」谈起，梳理架构权衡、数据模型、复制分片、事务与共识，以及批处理 / 流处理与数据伦理，把书里的原则接到真实系统设计决策上。

## 收听

- **节目页：** [eighthundreds.github.io/Podcast](https://eighthundreds.github.io/Podcast/)
- **RSS：** [feed.xml](https://eighthundreds.github.io/Podcast/feed.xml)（可提交到 Apple Podcasts、Spotify、小宇宙、AntennaPod 等）

## 分集

| 集 | 标题 | 时长 | 简介 |
|----|------|------|------|
| 1 | [云原生分布式还是单机极简](docs/transcripts/ep01.txt) | 21:20 | 面对数据密集型系统，何时该上云原生与分布式，何时单机极简反而更稳、更省、更好维护。 |
| 2 | [DDIA 架构设计核心权衡](docs/transcripts/ep02.txt) | 23:57 | 可靠性、可扩展性、可维护性如何互相牵制；做系统设计时如何显式列出取舍。 |
| 3 | [数据模型背后的架构取舍](docs/transcripts/ep03.txt) | 24:25 | 关系 / 文档 / 图模型不只是「怎么存」，更是查询方式、演进成本与一致性边界的选择。 |
| 4 | [软件逻辑战胜物理混乱](docs/transcripts/ep04.txt) | 25:24 | 闰秒拖垮半个互联网：软件如何用数据模型与架构，在硬件故障、网络延迟与时间错乱中撑起丝滑体验。 |
| 5 | [编码与演化](docs/transcripts/ep05.txt) | 20:22 | 序列化陷阱、向前/向后兼容，以及跨语言数据交换的底层取舍。 |
| 6 | [复制：让数据分身保持一致](docs/transcripts/ep06.txt) | 23:28 | 单主复制、多副本同步，以及数据分身如何避免「撕裂时空」。 |
| 7 | [分片：切开数据世界的魔法水晶](docs/transcripts/ep07.txt) | 16:07 | 分片如何支撑千万级并发，以及切分后如何查询与再平衡。 |
| 8 | [事务：断电也要钱货两清](docs/transcripts/ep08.txt) | 26:22 | 用「挖掘机铲断电源」的场景拆穿 ACID 营销滤镜，看数据库如何伪装一致性。 |
| 9 | [分布式系统的麻烦](docs/transcripts/ep09.txt) | 15:14 | 机房物理破坏、宇宙射线与网络谎言：分布式世界充满故障与延迟。 |
| 10 | [一致性与共识](docs/transcripts/ep10.txt) | 21:53 | 机票扣款成功却提示售罄：多机如何对「现实」达成一致。 |
| 11 | [批处理：派生数据与时间旅行](docs/transcripts/ep11.txt) | 28:00 | 不可变输入、派生输出，以及批处理赋予系统的可重放能力。 |
| 12 | [流处理：奔流不息的数据之河](docs/transcripts/ep12.txt) | 24:49 | 消息传递、背压与流处理如何在流动中捕捉并塑造实时世界。 |
| 13 | [系统必须出海：综合架构权衡](docs/transcripts/ep13.txt) | 27:41 | 没有完美系统，只有风险与取舍；把前面章节串成可落地的架构判断。 |
| 14 | [算法决策与数据伦理](docs/transcripts/ep14.txt) | 21:20 | 房贷秒拒、预测犯罪……当数据系统决定人生，终章追问系统把世界变成什么样。 |

字幕（VTT / SRT / 纯文本）见 [docs/transcripts/](docs/transcripts/)。  
节目封面见 [docs/cover.png](docs/cover.png)；单集封面见 [docs/covers/](docs/covers/)（目前 ep01–ep03）。

## 关于

本节目是 DDIA 读书讨论系列，适合在读这本书、或日常做架构选型与系统设计的人。内容以讨论与取舍为主，不是逐章朗读。

维护者说明（生成 Feed、上传 R2、转写字幕等）见 [DEVELOPMENT.md](DEVELOPMENT.md)。

---

© 2026 设计数据密集型应用
