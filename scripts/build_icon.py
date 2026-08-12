"""生成 GoUsage 应用图标 (logo-final.svg 结构, 多尺寸 ICO).

外弧蓝 #1890FF r16 75% + 内弧青 #06B6D4 r9 70% + 中心 H (粗体).
运行: python scripts/build_icon.py -> 输出 assets/GoUsage.ico
"""
import os

from PIL import Image, ImageDraw, ImageFont

VIEW = 48
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "GoUsage.ico")


def draw_logo(size: int) -> Image.Image:
    s = size / VIEW
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def box(cx: float, r: float) -> tuple[float, float, float, float]:
        return ((cx - r) * s, (cx - r) * s, (cx + r) * s, (cx + r) * s)

    # 外弧: r16 蓝色 75% (270°), 从 12 点方向顺时针
    d.arc(box(24, 16), start=270, end=540, fill=(24, 144, 255, 255), width=max(1, round(6 * s)))
    # 内弧: r9 青色 70% (252°), 从 12 点顺时针偏转 30°
    d.arc(box(24, 9), start=300, end=552, fill=(6, 182, 212, 255), width=max(1, round(5 * s)))
    # 中心 H
    font_size = max(4, round(11 * s))
    try:
        font = ImageFont.truetype("arialbd.ttf", font_size)
    except OSError:
        try:
            font = ImageFont.truetype("segoeuib.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()
    d.text((size / 2, size * (27.8 / VIEW)), "H", font=font, fill=(24, 144, 255, 255), anchor="mm")
    return img


def main() -> None:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    base = draw_logo(256)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    base.save(OUT, format="ICO", sizes=sizes)
    print("written:", os.path.abspath(OUT))
    for s in sizes:
        im = draw_logo(s[0])
        im.save(OUT, format="ICO", append_images=[] if s == sizes[0] else None, sizes=[s]) if False else None
    # 校验
    chk = Image.open(OUT)
    print("ico sizes:", getattr(chk, "info", {}).get("sizes"), "| fmt:", chk.format)


if __name__ == "__main__":
    main()
