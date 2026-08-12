#!/usr/bin/env python3
"""
按章节拆分 EPUB 文件。

优先使用 toc.ncx（EPUB2）或 nav.xhtml（EPUB3）目录；
若无目录，则按 spine 中的每个 HTML 文档拆分。

用法:
  python scripts/split_epub_chapters.py "书名.epub"
  python scripts/split_epub_chapters.py "书名.epub" -o output_dir --format md
  python scripts/split_epub_chapters.py "书名.epub" --format txt --skip-toc
"""

from __future__ import annotations

import argparse
import re
import zipfile
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from xml.etree import ElementTree as ET

# EPUB 常见命名空间
NS = {
    "container": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "ncx": "http://www.daisy.org/z3986/2005/ncx/",
    "xhtml": "http://www.w3.org/1999/xhtml",
    "epub": "http://www.idpf.org/2007/ops",
}


@dataclass
class Chapter:
    index: int
    title: str
    href: str  # 相对于 OPF 的路径，可能带 #fragment
    html_path: str  # 去掉 fragment 后的路径


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def sanitize_filename(name: str, max_len: int = 80) -> str:
    name = name.strip()
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip(" ._")
    if not name:
        name = "untitled"
    return name[:max_len]


def resolve_path(base: str, href: str) -> str:
    """将相对 href 解析为相对 EPUB 根的路径（去掉 fragment）。"""
    path_only = href.split("#", 1)[0]
    if not path_only:
        return base
    base_dir = str(Path(base).parent).replace("\\", "/")
    if base_dir == ".":
        base_dir = ""
    # 用 pathlib 归一化 ../
    combined = f"{base_dir}/{path_only}" if base_dir else path_only
    parts: list[str] = []
    for part in combined.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def read_container_rootfile(zf: zipfile.ZipFile) -> str:
    data = zf.read("META-INF/container.xml")
    root = ET.fromstring(data)
    rootfile = root.find(".//container:rootfile", NS)
    if rootfile is None:
        # 无命名空间兜底
        for el in root.iter():
            if local_name(el.tag) == "rootfile" and el.get("full-path"):
                return el.get("full-path")  # type: ignore[return-value]
        raise ValueError("无法在 META-INF/container.xml 中找到 rootfile")
    return rootfile.get("full-path")  # type: ignore[return-value]


def parse_opf(zf: zipfile.ZipFile, opf_path: str) -> tuple[dict[str, str], list[str], str | None, str]:
    """
    返回:
      - manifest: id -> href
      - spine: 按阅读顺序的 href 列表
      - ncx_href: toc.ncx 相对 EPUB 根路径（若有）
      - title: 书名
    """
    data = zf.read(opf_path)
    root = ET.fromstring(data)
    opf_dir = str(Path(opf_path).parent).replace("\\", "/")
    if opf_dir == ".":
        opf_dir = ""

    def to_root(href: str) -> str:
        return resolve_path(opf_path, href)

    manifest: dict[str, str] = {}
    id_to_media: dict[str, str] = {}
    for item in root.iter():
        if local_name(item.tag) != "item":
            continue
        item_id = item.get("id")
        href = item.get("href")
        if item_id and href:
            manifest[item_id] = to_root(href)
            id_to_media[item_id] = item.get("media-type") or ""

    spine: list[str] = []
    ncx_id = None
    for el in root.iter():
        if local_name(el.tag) == "spine":
            ncx_id = el.get("toc")
            for itemref in el:
                if local_name(itemref.tag) != "itemref":
                    continue
                idref = itemref.get("idref")
                if idref and idref in manifest:
                    spine.append(manifest[idref])

    ncx_href = manifest.get(ncx_id) if ncx_id else None
    # 也尝试找 ncx media-type
    if not ncx_href:
        for mid, href in manifest.items():
            if id_to_media.get(mid) == "application/x-dtbncx+xml":
                ncx_href = href
                break

    title = "untitled"
    for el in root.iter():
        if local_name(el.tag) == "title" and (el.text or "").strip():
            title = el.text.strip()
            break

    return manifest, spine, ncx_href, title


def parse_ncx_chapters(zf: zipfile.ZipFile, ncx_path: str, opf_path: str) -> list[Chapter]:
    data = zf.read(ncx_path)
    root = ET.fromstring(data)
    chapters: list[Chapter] = []
    order = 0

    def walk(nav_point: ET.Element) -> None:
        nonlocal order
        label = ""
        href = ""
        for child in nav_point:
            ln = local_name(child.tag)
            if ln == "navLabel":
                for t in child.iter():
                    if local_name(t.tag) == "text" and (t.text or "").strip():
                        label = t.text.strip()
                        break
            elif ln == "content":
                href = child.get("src") or ""
        if href:
            html_path = resolve_path(opf_path if ncx_path == opf_path else ncx_path, href)
            # ncx 与 opf 通常同目录；上面 resolve 以 ncx 为 base 更稳妥
            html_path = resolve_path(ncx_path, href)
            chapters.append(
                Chapter(
                    index=order,
                    title=label or f"chapter_{order + 1:02d}",
                    href=href,
                    html_path=html_path,
                )
            )
            order += 1
        for child in nav_point:
            if local_name(child.tag) == "navPoint":
                walk(child)

    for el in root.iter():
        if local_name(el.tag) == "navMap":
            for child in el:
                if local_name(child.tag) == "navPoint":
                    walk(child)
            break

    return chapters


def parse_nav_xhtml_chapters(zf: zipfile.ZipFile, nav_path: str) -> list[Chapter]:
    """EPUB3 nav.xhtml 简易解析。"""
    data = zf.read(nav_path)
    root = ET.fromstring(data)
    chapters: list[Chapter] = []
    order = 0

    # 找 epub:type="toc" 的 nav，或第一个 ol/li/a
    anchors: list[tuple[str, str]] = []
    for a in root.iter():
        if local_name(a.tag) != "a":
            continue
        href = a.get("href") or ""
        if not href or href.startswith("#"):
            continue
        text = "".join(a.itertext()).strip()
        anchors.append((text or f"chapter_{order + 1:02d}", href))

    seen: set[str] = set()
    for title, href in anchors:
        html_path = resolve_path(nav_path, href)
        if html_path in seen:
            continue
        seen.add(html_path)
        chapters.append(
            Chapter(index=order, title=title, href=href, html_path=html_path)
        )
        order += 1
    return chapters


def find_nav_xhtml(zf: zipfile.ZipFile, manifest: dict[str, str], opf_path: str) -> str | None:
    # 常见路径
    for name in zf.namelist():
        lower = name.lower()
        if lower.endswith("nav.xhtml") or lower.endswith("nav.html"):
            return name
    return None


def spine_as_chapters(spine: list[str]) -> list[Chapter]:
    chapters: list[Chapter] = []
    for i, href in enumerate(spine):
        # 跳过封面类
        base = Path(href).name.lower()
        if base in {"titlepage.xhtml", "cover.xhtml", "cover.html"}:
            continue
        chapters.append(
            Chapter(
                index=i,
                title=Path(href).stem,
                href=href,
                html_path=href,
            )
        )
    return chapters


def html_to_text(html: str) -> str:
    """简易 HTML → 纯文本（无第三方依赖）。"""
    # 去掉 script/style
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", html)
    # 块级换行
    html = re.sub(
        r"(?i)</(p|div|h[1-6]|li|tr|blockquote|section|article|br|hr)[^>]*>",
        "\n",
        html,
    )
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)<hr\s*/?>", "\n---\n", html)
    # 标题标记
    def heading_repl(m: re.Match[str]) -> str:
        level = int(m.group(1))
        inner = re.sub(r"(?is)<[^>]+>", "", m.group(2))
        inner = unescape(inner).strip()
        if not inner:
            return "\n"
        return "\n" + "#" * level + " " + inner + "\n\n"

    html = re.sub(r"(?is)<h([1-6])[^>]*>(.*?)</h\1>", heading_repl, html)
    # 去其余标签
    text = re.sub(r"(?is)<[^>]+>", "", html)
    text = unescape(text)
    # 空白整理
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip() + "\n"


def html_to_markdownish(html: str) -> str:
    """比纯文本多保留一点标题结构，仍是轻量实现。"""
    return html_to_text(html)


def extract_title_from_html(html: str, fallback: str) -> str:
    m = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", html)
    if m:
        t = re.sub(r"(?is)<[^>]+>", "", m.group(1))
        t = unescape(t).strip()
        t = re.sub(r"\s+", " ", t)
        if t:
            return t
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    if m:
        t = unescape(m.group(1)).strip()
        if t:
            return t
    return fallback


def is_toc_chapter(title: str, html: str) -> bool:
    t = title.strip().replace(" ", "")
    if t in {"目录", "目次", "Contents", "TableofContents", "TOC"}:
        return True
    if re.search(r'(?is)epub:type\s*=\s*["\']toc["\']', html):
        return True
    if re.search(r'(?is)<nav[^>]+epub:type\s*=\s*["\']toc["\']', html):
        return True
    return False


def split_epub(
    epub_path: Path,
    output_dir: Path,
    fmt: str = "md",
    skip_toc: bool = True,
    use_spine: bool = False,
) -> list[Path]:
    if not epub_path.is_file():
        raise FileNotFoundError(f"找不到 EPUB: {epub_path}")

    written: list[Path] = []
    book_title = epub_path.stem
    with zipfile.ZipFile(epub_path, "r") as zf:
        opf_path = read_container_rootfile(zf)
        _manifest, spine, ncx_href, book_title = parse_opf(zf, opf_path)

        chapters: list[Chapter] = []
        if not use_spine:
            if ncx_href and ncx_href in zf.namelist():
                chapters = parse_ncx_chapters(zf, ncx_href, opf_path)
            else:
                nav = find_nav_xhtml(zf, _manifest, opf_path)
                if nav:
                    chapters = parse_nav_xhtml_chapters(zf, nav)

        if not chapters:
            chapters = spine_as_chapters(spine)

        # 同一 html 只导出一次（toc 中可能有多级锚点指向同文件）
        seen_files: set[str] = set()
        unique_chapters: list[Chapter] = []
        for ch in chapters:
            if ch.html_path in seen_files:
                continue
            if ch.html_path not in zf.namelist():
                # 有些路径大小写/编码差异，再试一次
                match = next(
                    (n for n in zf.namelist() if n.lower() == ch.html_path.lower()),
                    None,
                )
                if not match:
                    print(f"  [跳过] 找不到文件: {ch.html_path} ({ch.title})")
                    continue
                ch.html_path = match
            seen_files.add(ch.html_path)
            unique_chapters.append(ch)

        out_root = output_dir
        out_root.mkdir(parents=True, exist_ok=True)

        print(f"书名: {book_title}")
        print(f"章节数: {len(unique_chapters)}")
        print(f"输出目录: {out_root.resolve()}")

        for i, ch in enumerate(unique_chapters, start=1):
            raw = zf.read(ch.html_path).decode("utf-8", errors="replace")
            title = ch.title
            # toc 里若标题为空，从 HTML 补
            if not title or title.startswith("part") or title == Path(ch.html_path).stem:
                title = extract_title_from_html(raw, title)

            if skip_toc and is_toc_chapter(title, raw):
                print(f"  [跳过目录] {title}")
                continue

            if fmt == "html":
                body = raw
                ext = "html"
            elif fmt == "txt":
                body = html_to_text(raw)
                # txt 去掉 markdown 风格 #
                body = re.sub(r"(?m)^#{1,6}\s*", "", body)
                ext = "txt"
            else:
                body = html_to_markdownish(raw)
                ext = "md"

            fname = f"{i:02d}_{sanitize_filename(title)}.{ext}"
            out_path = out_root / fname
            if fmt == "md":
                # 保证顶部有标题
                if not body.lstrip().startswith("#"):
                    content = f"# {title}\n\n{body}"
                else:
                    content = body
            elif fmt == "txt":
                content = f"{title}\n{'=' * len(title)}\n\n{body}"
            else:
                content = body

            out_path.write_text(content, encoding="utf-8")
            written.append(out_path)
            print(f"  [{i:02d}] {title}  ->  {out_path.name}")

    # 写一份索引
    index_path = output_dir / "00_章节索引.md"
    lines = [f"# {book_title} — 章节索引", ""]
    for p in written:
        lines.append(f"- [{p.stem}]({p.name})")
    lines.append("")
    index_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n索引: {index_path}")
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="按章节拆分 EPUB")
    parser.add_argument("epub", type=Path, help="EPUB 文件路径")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="输出目录（默认: <epub名>_chapters）",
    )
    parser.add_argument(
        "--format",
        choices=["md", "txt", "html"],
        default="md",
        help="输出格式（默认 md）",
    )
    parser.add_argument(
        "--skip-toc",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="是否跳过「目录」页（默认跳过）",
    )
    parser.add_argument(
        "--spine",
        action="store_true",
        help="强制按 spine 文档顺序拆分，忽略 toc.ncx",
    )
    args = parser.parse_args()

    epub_path = args.epub.expanduser().resolve()
    output = args.output
    if output is None:
        output = epub_path.with_name(epub_path.stem + "_chapters")
    else:
        output = output.expanduser().resolve()

    split_epub(
        epub_path=epub_path,
        output_dir=output,
        fmt=args.format,
        skip_toc=args.skip_toc,
        use_spine=args.spine,
    )


if __name__ == "__main__":
    main()
