# Pipeline 常见坑

## 线上 feed 缺后面几集

**现象：** 远端 `feed.xml` 的 item 数少于 `podcast.yaml`。

**原因：** 生成器默认跳过 `publication_date` 在未来的分集（除非 `--include-future`）。CI 重生时若无该参数，会盖掉你本地带 flag 生成的完整 feed。

**处理：** 应公开的集把时间改到已过去，且 **CI 与本地一致**（都加 `--include-future`，或只写过去时间）。再 push，复查线上 item 数。

## 错章 / 音频装错

**现象：** 标题或字幕里「第 N 章」与听到的内容不符；与另一集主题高度重叠。

**排查：**

1. 读字幕开头与口播自称章节。
2. 按书的 **实际版本目录** 对照正文（本仓库 DDIA 线用 **第二版**：[toc](https://ddia.vonng.com/toc/)——ch1 架构权衡、ch2 非功能、ch3 模型、ch4 存储… ch14「将事情做正确」）。勿用第一版章序硬套。
3. 若音频错了：换文件、重传 R2（同 key 或改 yaml `file`）、重转写、**typo-only** 校对、改标题；主题变了则更新封面文案/底图。

## 播放器里「看不到字幕」

许多客户端（如 AntennaPod）通过菜单/弹窗打开 `podcast:transcript`，不是始终内嵌跟读。先确认字幕 URL 200 且出现在 feed item 里，再论播放器 UI。

## R2 上传成功但打不开

上传成功 ≠ 公网 200。需开启 bucket 公共访问 / r2.dev（或自定义域）。中文对象名在客户端 URL 中要编码正确。

## 密钥

禁止把含真实 R2 密钥的 `.env` 提交进库。Wrangler OAuth 在机器上，不在仓库。yaml 里的公开 `audio_base_url` 可以提交。

## 线上检查（核验分支）

```bash
# 按 shows.yaml 的 base_url + slug 替换
curl -sL "https://eighthundreds.github.io/Podcast/ddia/feed.xml" -o /tmp/feed.xml
# 统计 <item>、打印标题/enclosure
# 对 enclosure 与 transcript URL 做 HEAD → 期望 200
```

**完成标准：** item 数与应公开集合一致；抽样 enclosure、字幕 URL 均为 200。
