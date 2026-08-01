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


def normalize_segments(raw_segments: list | None, full_text: str) -> list[dict]:
    """统一成 {start, end, text, speaker}。"""
    out: list[dict] = []
    if raw_segments:
        for seg in raw_segments:
            if not isinstance(seg, dict):
                continue
            text = (seg.get("text") or "").strip()
            if not text:
                continue
            speaker = seg.get("speaker_id") or seg.get("speaker")
            if not speaker:
                m = re.match(r"\[(S\d+)\]\s*(.*)", text, re.I)
                if m:
                    speaker = m.group(1).upper()
                    text = m.group(2).strip() or text
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
        body = m.group("text").strip()
        if not body:
            continue
        out.append(
            {
                "start": float(m.group("start")),
                "end": float(m.group("end")),
                "text": body,
                "speaker": m.group("speaker").upper(),
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
    args = parser.parse_args()

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
        segments = normalize_segments(getattr(result, "segments", None), full_text)

        write_vtt(segments, out_dir / f"{stem}.vtt")
        write_srt(segments, out_dir / f"{stem}.srt")
        write_txt(segments, out_dir / f"{stem}.txt")
        write_dialog(segments, out_dir / f"{stem}.dialog.txt")
        (out_dir / f"{stem}.raw.txt").write_text(
            full_text + ("\n" if full_text else ""), encoding="utf-8"
        )
        (out_dir / f"{stem}.json").write_text(
            json.dumps(
                {
                    "model": args.model,
                    "audio": str(audio),
                    "text": full_text,
                    "segments": segments,
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
            f"  ✓ {stem}: {len(segments)} 段, 说话人={speakers or ['(未解析到)']}",
            flush=True,
        )
        print(f"    → {out_dir / (stem + '.vtt')}", flush=True)


if __name__ == "__main__":
    main()
