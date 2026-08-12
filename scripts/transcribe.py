#!/usr/bin/env python3
"""
用 mlx-audio + MOSS-Transcribe-Diarize 做「转写 + 说话人分离」。

输出每段带 [S01]/[S02]… 标签（匿名说话人，不会自动知道谁是谁）。
模型约 1.7GB，首次运行会从 Hugging Face 下载。

用法:
  source .venv/bin/activate
  python scripts/transcribe.py shows/设计数据密集型应用/audio/ep01-*.m4a
  python scripts/transcribe.py   # 默认转写 shows/*/audio/*
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_MODEL = "OpenMOSS-Team/MOSS-Transcribe-Diarize"

# 双人技术播客：强调说话人标签与时间戳
DEFAULT_PROMPT = (
    "Transcribe the audio into text. Start each segment with the start "
    "timestamp and speaker label ([S01], [S02], [S03], ...), write the "
    "corresponding spoken content, and end each segment with the ending "
    "timestamp to clearly mark the segment range. "
    "This is a Chinese technical podcast discussion about distributed systems "
    "and data-intensive applications (DDIA). Prefer Simplified Chinese. "
    "Keep technical terms accurate (e.g. 一致性, 复制, 分区, Kafka, Raft)."
)


def ts_vtt(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def ts_srt(seconds: float) -> str:
    return ts_vtt(seconds).replace(".", ",")


def stem_from_audio(path: Path) -> str:
    m = re.match(r"(ep\d+)", path.stem, re.I)
    return m.group(1).lower() if m else path.stem


_SPEAKER_PREFIX_RE = re.compile(r"^\[(S\d+)\]\s*", re.I)
# 合并后可能残留的句中说话人标签（正文里不应再出现）
_INLINE_SPEAKER_RE = re.compile(r"\s*\[(S\d+)\]\s*", re.I)


def _strip_speaker_labels(text: str, speaker: str | None = None) -> tuple[str, str | None]:
    """去掉正文里的 [S01] 标签；若尚未知道 speaker 则从首个标签推断。"""
    body = (text or "").strip()
    if not body:
        return "", speaker
    m = _SPEAKER_PREFIX_RE.match(body)
    if m:
        if not speaker:
            speaker = m.group(1).upper()
        body = body[m.end() :].strip()
    # 去掉误嵌在正文中的其它 [Sxx]
    body = _INLINE_SPEAKER_RE.sub("", body).strip()
    return body, speaker


def normalize_segments(raw_segments: list | None, full_text: str) -> list[dict]:
    """统一成 {start, end, text, speaker}；text 不含 [Sxx] 前缀。"""
    out: list[dict] = []
    if raw_segments:
        for seg in raw_segments:
            if not isinstance(seg, dict):
                continue
            text = (seg.get("text") or "").strip()
            if not text:
                continue
            speaker = seg.get("speaker_id") or seg.get("speaker")
            if isinstance(speaker, str):
                speaker = speaker.upper()
            text, speaker = _strip_speaker_labels(text, speaker)
            if not text:
                continue
            out.append(
                {
                    "start": float(seg.get("start") or 0),
                    "end": float(seg.get("end") or 0),
                    "text": text,
                    "speaker": speaker,
                }
            )
        if out:
            return out

    # 回退：解析模型原始文本 [12.3][S01]…[15.0]
    pattern = re.compile(
        r"\[(?P<start>\d+(?:\.\d+)?)\]\[(?P<speaker>S\d+)\]"
        r"(?P<text>.*?)\[(?P<end>\d+(?:\.\d+)?)\]",
        re.DOTALL | re.IGNORECASE,
    )
    for m in pattern.finditer(full_text or ""):
        body, speaker = _strip_speaker_labels(
            m.group("text"), m.group("speaker").upper()
        )
        if not body:
            continue
        out.append(
            {
                "start": float(m.group("start")),
                "end": float(m.group("end")),
                "text": body,
                "speaker": speaker,
            }
        )
    return out


def cue_text(seg: dict) -> str:
    sp = seg.get("speaker")
    body = seg.get("text") or ""
    if sp:
        # 避免重复 [S01]
        if body.startswith(f"[{sp}]"):
            return body
        return f"[{sp}] {body}"
    return body


def _join_cue_text(left: str, right: str) -> str:
    """拼接两段字幕正文：中文直接连；两端都是拉丁词时补空格。"""
    if not left:
        return right
    if not right:
        return left
    if re.search(r"[A-Za-z0-9]$", left) and re.search(r"^[A-Za-z0-9]", right):
        return f"{left} {right}"
    return left + right


def merge_same_speaker_segments(
    segments: list[dict],
    *,
    max_gap: float = 1.0,
) -> list[dict]:
    """把同一说话人、间隔很小的连续片段合并成一条字幕。

    ASR 常把一句完整话切成很多短 cue；播放时同人连说应显示为一条。
    max_gap：上一段 end 到下一段 start 的最大允许间隔（秒）。
    """
    if not segments:
        return []

    merged: list[dict] = []
    cur = {
        "start": float(segments[0].get("start") or 0),
        "end": float(segments[0].get("end") or 0),
        "text": (segments[0].get("text") or "").strip(),
        "speaker": segments[0].get("speaker"),
    }

    for seg in segments[1:]:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        start = float(seg.get("start") or 0)
        end = float(seg.get("end") or 0)
        speaker = seg.get("speaker")
        gap = start - float(cur["end"])
        same = (
            speaker is not None
            and cur.get("speaker") is not None
            and speaker == cur.get("speaker")
        )
        if same and gap <= max_gap and cur.get("text"):
            cur["end"] = max(float(cur["end"]), end)
            cur["text"] = _join_cue_text(cur["text"], text)
            continue
        if cur.get("text"):
            merged.append(cur)
        cur = {
            "start": start,
            "end": end,
            "text": text,
            "speaker": speaker,
        }

    if cur.get("text"):
        merged.append(cur)
    return merged


def write_caption_outputs(segments: list[dict], out_dir: Path, stem: str) -> None:
    """写出发布用 vtt/srt/txt 与源稿 dialog。"""
    write_vtt(segments, out_dir / f"{stem}.vtt")
    write_srt(segments, out_dir / f"{stem}.srt")
    write_txt(segments, out_dir / f"{stem}.txt")
    write_dialog(segments, out_dir / f"{stem}.dialog.txt")


def write_vtt(segments: list[dict], path: Path) -> None:
    lines = ["WEBVTT", ""]
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{ts_vtt(seg['start'])} --> {ts_vtt(seg['end'])}")
        lines.append(cue_text(seg))
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_srt(segments: list[dict], path: Path) -> None:
    lines: list[str] = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{ts_srt(seg['start'])} --> {ts_srt(seg['end'])}")
        lines.append(cue_text(seg))
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_txt(segments: list[dict], path: Path) -> None:
    lines = [cue_text(s) for s in segments]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def write_dialog(segments: list[dict], path: Path) -> None:
    """按说话人合并连续句，方便做 shownotes。"""
    blocks: list[str] = []
    cur_sp = None
    buf: list[str] = []
    for seg in segments:
        sp = seg.get("speaker") or "S??"
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        if sp != cur_sp:
            if buf and cur_sp is not None:
                blocks.append(f"[{cur_sp}] " + "".join(buf))
            cur_sp = sp
            buf = [text]
        else:
            buf.append(text)
    if buf and cur_sp is not None:
        blocks.append(f"[{cur_sp}] " + "".join(buf))
    path.write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")


def remerge_from_json(
    json_path: Path,
    *,
    max_gap: float = 1.0,
    out_dir: Path | None = None,
) -> list[dict]:
    """从已有转写 json 重新合并同说话人片段，并重写 vtt/srt/txt/dialog。

    json 内保留 raw_segments（未合并）与 segments（合并后，用于字幕）。
    """
    data = json.loads(json_path.read_text(encoding="utf-8"))
    # 优先用未合并源；兼容旧文件（只有已切碎的 segments）
    raw = data.get("raw_segments") or data.get("segments") or []
    raw = normalize_segments(raw, data.get("text") or "")
    merged = merge_same_speaker_segments(raw, max_gap=max_gap)

    stem = json_path.stem
    dest = out_dir or json_path.parent
    dest.mkdir(parents=True, exist_ok=True)
    write_caption_outputs(merged, dest, stem)

    data["raw_segments"] = raw
    data["segments"] = merged
    data["merge_max_gap"] = max_gap
    json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(
        description="mlx-audio + MOSS-Transcribe-Diarize 转写（带说话人）"
    )
    parser.add_argument("inputs", nargs="*", type=Path, help="音频文件")
    parser.add_argument(
        "-o",
        "--out-dir",
        type=Path,
        default=None,
        help="输出目录（默认：音频同级 ../transcripts）",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"模型 id（默认 {DEFAULT_MODEL}，约 1.7GB）",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=16384,
        help="生成上限；长播客请调大（默认 16384）",
    )
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="自定义转写 prompt")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="打印推理详情",
    )
    parser.add_argument(
        "--max-gap",
        type=float,
        default=1.0,
        help="同说话人连续片段合并的最大间隔秒数（默认 1.0）",
    )
    parser.add_argument(
        "--remerge",
        nargs="*",
        type=Path,
        default=None,
        help="不跑模型：从已有 json 合并同说话人并重写字幕。"
        "可传 json 文件或目录；省略参数时处理 shows/*/transcripts/*.json",
    )
    args = parser.parse_args()

    # 仅重合并模式（不加载模型）
    if args.remerge is not None:
        paths: list[Path] = []
        if not args.remerge:
            root = Path("shows")
            paths = sorted(root.glob("*/transcripts/ep*.json")) if root.is_dir() else []
        else:
            for p in args.remerge:
                if p.is_dir():
                    paths.extend(sorted(p.glob("ep*.json")))
                    paths.extend(sorted(p.glob("*.json")))
                elif p.is_file():
                    paths.append(p)
            # 去重并保持顺序
            seen: set[Path] = set()
            uniq: list[Path] = []
            for p in paths:
                rp = p.resolve()
                if rp not in seen:
                    seen.add(rp)
                    uniq.append(p)
            paths = uniq

        if not paths:
            print("未找到可 remerge 的 json。", file=sys.stderr)
            sys.exit(1)

        for jp in paths:
            data0 = json.loads(jp.read_text(encoding="utf-8"))
            before = len(data0.get("raw_segments") or data0.get("segments") or [])
            merged = remerge_from_json(jp, max_gap=args.max_gap, out_dir=args.out_dir)
            print(
                f"  ✓ {jp}: {before} → {len(merged)} 段 (max_gap={args.max_gap})",
                flush=True,
            )
        return

    inputs = list(args.inputs)
    if not inputs:
        root = Path("shows")
        if root.is_dir():
            inputs = sorted(root.glob("*/audio/*.*"))
        if not inputs:
            print("未找到音频。请传入文件路径。", file=sys.stderr)
            sys.exit(1)

    try:
        from mlx_audio.stt.utils import load_model
    except ImportError:
        print(
            "缺少 mlx-audio。请先:\n"
            "  source .venv/bin/activate && pip install mlx-audio",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"加载模型: {args.model}", flush=True)
    print("（首次会从 Hugging Face 下载，约 1.7GB，请耐心等待）", flush=True)
    model = load_model(args.model)

    for audio in inputs:
        if not audio.is_file():
            print(f"跳过（不存在）: {audio}", file=sys.stderr)
            continue

        out_dir = args.out_dir
        if out_dir is None:
            if audio.parent.name == "audio":
                out_dir = audio.parent.parent / "transcripts"
            else:
                out_dir = audio.parent / "transcripts"
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = stem_from_audio(audio)

        print(f"→ 转写 {audio.name}", flush=True)
        result = model.generate(
            str(audio),
            max_tokens=args.max_tokens,
            prompt=args.prompt,
            verbose=args.verbose,
        )

        full_text = getattr(result, "text", "") or ""
        raw_segments = normalize_segments(getattr(result, "segments", None), full_text)
        segments = merge_same_speaker_segments(raw_segments, max_gap=args.max_gap)

        write_caption_outputs(segments, out_dir, stem)
        (out_dir / f"{stem}.raw.txt").write_text(
            full_text + ("\n" if full_text else ""), encoding="utf-8"
        )
        (out_dir / f"{stem}.json").write_text(
            json.dumps(
                {
                    "model": args.model,
                    "audio": str(audio),
                    "text": full_text,
                    "raw_segments": raw_segments,
                    "segments": segments,
                    "merge_max_gap": args.max_gap,
                    "prompt_tokens": getattr(result, "prompt_tokens", None),
                    "generation_tokens": getattr(result, "generation_tokens", None),
                    "total_time": getattr(result, "total_time", None),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        speakers = sorted({s["speaker"] for s in segments if s.get("speaker")})
        print(
            f"  ✓ {stem}: {len(raw_segments)} 原始段 → {len(segments)} 合并段, "
            f"说话人={speakers or ['(未解析到)']}",
            flush=True,
        )
        print(f"    → {out_dir / (stem + '.vtt')}", flush=True)


if __name__ == "__main__":
    main()
