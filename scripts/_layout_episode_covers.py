from __future__ import annotations

from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


SIZE = 1400
FONT = "/System/Library/Fonts/Hiragino Sans GB.ttc"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT, size=size, index=2 if bold else 0)


def fit_square(image: Image.Image) -> Image.Image:
    image = image.convert("RGB")
    scale = max(SIZE / image.width, SIZE / image.height)
    resized = image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - SIZE) // 2
    top = (resized.height - SIZE) // 2
    return resized.crop((left, top, left + SIZE, top + SIZE))


def gradient_overlay(image: Image.Image) -> Image.Image:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    pixels = overlay.load()
    for y in range(SIZE):
        top_alpha = int(max(0.0, 1.0 - y / 520) ** 1.5 * 155)
        bottom_alpha = int(max(0.0, (y - 870) / 530) ** 1.25 * 225)
        alpha = min(235, top_alpha + bottom_alpha)
        for x in range(SIZE):
            pixels[x, y] = (2, 6, 18, alpha)
    return Image.alpha_composite(image.convert("RGBA"), overlay)


def draw_spaced(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str,
                face: ImageFont.FreeTypeFont, fill: tuple[int, ...], spacing: int) -> None:
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=face, fill=fill)
        bbox = draw.textbbox((x, y), char, font=face)
        x += bbox[2] - bbox[0] + spacing


def make_cover(source: Path, output: Path, episode: str,
               title_lines: tuple[str, str], accent: tuple[int, int, int]) -> None:
    base = fit_square(Image.open(source))
    base = ImageEnhance.Contrast(base).enhance(1.05)
    canvas = gradient_overlay(base)

    # Subtle atmospheric glow ties the typography to each episode's accent.
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((-170, -210, 730, 570), fill=(*accent, 38))
    glow = glow.filter(ImageFilter.GaussianBlur(110))
    canvas = Image.alpha_composite(canvas, glow)

    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((44, 44, SIZE - 44, SIZE - 44), radius=28,
                           outline=(*accent, 145), width=3)

    series_font = font(36)
    draw_spaced(
        draw,
        (92, 82),
        "设计数据密集型应用  ·  DDIA 读书讨论",
        series_font,
        (218, 231, 248, 225),
        1,
    )
    draw.line((92, 145, 126, 145), fill=(*accent, 255), width=7)
    draw.line((142, 145, 318, 145), fill=(168, 190, 222, 135), width=2)

    # Large, unmistakable episode number.
    ep_font = font(176, bold=True)
    draw.text((86, 152), f"EP{episode}", font=ep_font, fill=(245, 249, 255, 245),
              stroke_width=2, stroke_fill=(*accent, 190))

    # Lower title plate preserves legibility at podcast-thumbnail size.
    title_plate = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    plate_draw = ImageDraw.Draw(title_plate)
    plate_draw.rounded_rectangle((72, 1002, SIZE - 72, 1327), radius=28,
                                 fill=(2, 7, 20, 206), outline=(*accent, 105), width=2)
    title_plate = title_plate.filter(ImageFilter.GaussianBlur(0.35))
    canvas = Image.alpha_composite(canvas, title_plate)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((91, 1041, 101, 1287), radius=5, fill=(*accent, 255))

    title_font = font(88, bold=True)
    draw.text((137, 1035), title_lines[0], font=title_font, fill=(249, 251, 255, 255))
    draw.text((137, 1148), title_lines[1], font=title_font, fill=(249, 251, 255, 255))
    draw.text((139, 1266), "SYSTEMS · ARCHITECTURE · DATA",
              font=font(25), fill=(*accent, 225))

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output, format="PNG", optimize=True)


def main() -> None:
    if len(sys.argv) != 7:
        raise SystemExit("usage: script SRC1 SRC2 SRC3 OUT1 OUT2 OUT3")
    sources = [Path(arg) for arg in sys.argv[1:4]]
    outputs = [Path(arg) for arg in sys.argv[4:7]]
    specs = [
        ("01", ("云原生分布式", "还是单机极简"), (0, 198, 255)),
        ("02", ("DDIA 架构设计", "核心权衡"), (190, 86, 255)),
        ("03", ("数据模型背后的", "架构取舍"), (64, 224, 179)),
    ]
    for source, output, (episode, title, accent) in zip(sources, outputs, specs):
        make_cover(source, output, episode, title, accent)


if __name__ == "__main__":
    main()
