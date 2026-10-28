#!/usr/bin/env python3
"""从 ZCode PWA 的 icon-512.png 生成 Android 壳的整套启动图标。

输入：icon/src/icon-512.png（ZCode PWA 的图标，即 ../zcode-pwa/icons/icon-512.png，深底 + 薄荷绿终端图形）
输出：icon/res/ 下按密度铺好的 PNG 与 adaptive-icon 表述文件，CI 直接把 icon/res 覆盖进
      app/src/main/res，并删掉上游那套 .webp 位图。

用法：python3 icon/generate.py
依赖：Pillow
"""

from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "src" / "icon-512.png"
OUT = HERE / "res"

# 传统图标边长（dp 1:1 像素）
LEGACY_SIZES = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}

# adaptive-icon 前景画布 108dp；可见区约 72dp，图形取画布的 36%，
# 换算到可见区正好是 52%，和源图里终端图形占 512 的比例一致
ADAPTIVE_DP = 108
FOREGROUND_RATIO = 0.36


def rgb_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def key_out_background(image: Image.Image, bg: tuple[int, int, int], fg: tuple[int, int, int]) -> Image.Image:
    """把纯色底扣成透明，边缘按到底色的距离做线性 alpha，保留抗锯齿。"""
    span = rgb_distance(bg, fg)
    out = Image.new("RGBA", image.size)
    pixels = []
    for r, g, b in image.convert("RGB").getdata():
        alpha = round(min(1.0, rgb_distance((r, g, b), bg) / span) * 255)
        pixels.append((r, g, b, alpha))
    out.putdata(pixels)
    return out


def main() -> None:
    source = Image.open(SOURCE).convert("RGB")
    bg = source.getpixel((0, 0))
    glyph = (141, 240, 187)  # 采样自源图，见 README

    glyph_layer = key_out_background(source, bg, glyph)
    bbox = glyph_layer.getbbox()
    if bbox is None:
        raise SystemExit("源图标里没有可提取的图形")
    glyph_layer = glyph_layer.crop(bbox)
    print(f"底色 #{bg[0]:02X}{bg[1]:02X}{bg[2]:02X}，图形框 {bbox}")

    for density, size in LEGACY_SIZES.items():
        target = OUT / f"mipmap-{density}"
        target.mkdir(parents=True, exist_ok=True)

        source.resize((size, size), Image.LANCZOS).save(target / "ic_launcher.png")

        # round 版：同样内容的圆形裁切，四角留透明
        round_icon = source.resize((size, size), Image.LANCZOS).convert("RGBA")
        mask = Image.new("L", (size * 4, size * 4), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
        round_icon.putalpha(mask.resize((size, size), Image.LANCZOS))
        round_icon.save(target / "ic_launcher_round.png")

        canvas = round(size * ADAPTIVE_DP / 48)
        scale = canvas * FOREGROUND_RATIO / max(glyph_layer.size)
        scaled = glyph_layer.resize(
            (round(glyph_layer.width * scale), round(glyph_layer.height * scale)),
            Image.LANCZOS,
        )
        foreground = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
        foreground.paste(
            scaled,
            ((canvas - scaled.width) // 2, (canvas - scaled.height) // 2),
            scaled,
        )
        foreground.save(target / "ic_launcher_foreground.png")
        print(f"{density}: legacy {size}px, adaptive {canvas}px")

    anydpi = OUT / "mipmap-anydpi-v26"
    anydpi.mkdir(parents=True, exist_ok=True)
    for name in ("ic_launcher.xml", "ic_launcher_round.xml"):
        (anydpi / name).write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
            '    <background android:drawable="@color/zcode_icon_background" />\n'
            '    <foreground android:drawable="@mipmap/ic_launcher_foreground" />\n'
            '    <monochrome android:drawable="@mipmap/ic_launcher_foreground" />\n'
            "</adaptive-icon>\n",
            encoding="utf-8",
        )

    values = OUT / "values"
    values.mkdir(parents=True, exist_ok=True)
    (values / "zcode_icon_colors.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<resources>\n"
        f'    <color name="zcode_icon_background">#{bg[0]:02X}{bg[1]:02X}{bg[2]:02X}</color>\n'
        "</resources>\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
