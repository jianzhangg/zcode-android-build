#!/usr/bin/env python3
"""生成 ZCode 安卓启动图标：纯黑底 + 白色 Z。

输入：icon/src/zcode-app-1024.png，直接取自
      /Applications/ZCode.app/Contents/Resources/icon.png（ZCode 官方应用图标）。
源图是 macOS squircle（四角透明、带一点自上而下的渐变），安卓要满幅方形，
所以这里把白 Z 抠出来重新铺到纯黑底上。

输出：icon/res/ 下按密度铺好的传统图标、圆形图标、adaptive-icon 前景与配色。
      CI 直接把 icon/res 覆盖进 app/src/main/res，并删掉上游那套 .webp 位图。

用法：python3 icon/generate.py
依赖：Pillow
"""

from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "src" / "zcode-app-1024.png"
OUT = HERE / "res"

BG = (10, 11, 12)  # 取自源图背景中位数，看起来就是纯黑
DENSITIES = {
    "mdpi": 1.0,
    "hdpi": 1.5,
    "xhdpi": 2.0,
    "xxhdpi": 3.0,
    "xxxhdpi": 4.0,
}


def extract_glyph():
    """把白 Z 抠成白色 RGBA，alpha 用亮度还原，边缘保留半透明过渡。"""
    image = Image.open(SOURCE).convert("RGBA")
    source = image.load()
    width, height = image.size

    xs, ys = [], []
    for y in range(height):
        for x in range(width):
            r, g, b, a = source[x, y]
            if a > 200 and r > 200 and g > 200 and b > 200:
                xs.append(x)
                ys.append(y)
    box = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)

    glyph = Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), (0, 0, 0, 0))
    target = glyph.load()
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            r, g, b, a = source[x, y]
            if a == 0:
                continue
            # 源图是白字压在近黑底上，亮度即覆盖率
            coverage = min(255, max(0, round((r - BG[0]) * 255 / (255 - BG[0]))))
            if coverage:
                target[x - box[0], y - box[1]] = (255, 255, 255, coverage)
    return glyph, box


def compose(glyph, size, glyph_ratio, background=BG, circle=False):
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if background is not None:
        ImageDraw.Draw(canvas).rectangle((0, 0, size, size), fill=background + (255,))

    target_w = max(1, round(size * glyph_ratio))
    scale = target_w / glyph.size[0]
    scaled = glyph.resize((target_w, max(1, round(glyph.size[1] * scale))), Image.LANCZOS)
    canvas.alpha_composite(scaled, ((size - scaled.size[0]) // 2, (size - scaled.size[1]) // 2))

    if circle:
        # 放大四倍再缩小，避免硬边锯齿
        mask = Image.new("L", (size * 4, size * 4), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
        canvas.putalpha(mask.resize((size, size), Image.LANCZOS))

    return canvas


def main():
    glyph, box = extract_glyph()
    src_edge = Image.open(SOURCE).size[0]

    # 源图里 Z 占整幅边长的比例，传统图标沿用这个比例
    legacy_ratio = (box[2] - box[0]) / src_edge
    # adaptive 前景单独定档：规范里的「可见区 72dp」只是下限，启动器实际把整幅画布铺到
    # 图标槽位。源图那 49.8% 在真机上偏大、按 72/108 缩到 33% 又偏小，实测 41% 最接近。
    fg_ratio = 0.41

    print(f"源图 Z 边界 {box}，占边长 {legacy_ratio:.1%}")

    for name, scale in DENSITIES.items():
        target = OUT / f"mipmap-{name}"
        target.mkdir(parents=True, exist_ok=True)

        legacy_px = round(48 * scale)
        compose(glyph, legacy_px, legacy_ratio).convert("RGB").save(target / "ic_launcher.png")
        compose(glyph, legacy_px, legacy_ratio, circle=True).save(target / "ic_launcher_round.png")

        # adaptive 前景：透明画布 108dp，只放白 Z，底色由 <background> 铺
        fg_px = round(108 * scale)
        compose(glyph, fg_px, fg_ratio, background=None).save(target / "ic_launcher_foreground.png")
        print(f"{name}: legacy {legacy_px}px, foreground {fg_px}px")

    # adaptive-icon 表述：底色走 <background>，白 Z 走 <foreground>，<monochrome> 给主题图标用
    anydpi = OUT / "mipmap-anydpi-v26"
    anydpi.mkdir(parents=True, exist_ok=True)
    for filename in ("ic_launcher.xml", "ic_launcher_round.xml"):
        (anydpi / filename).write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
            '    <background android:drawable="@color/zcode_icon_background" />\n'
            '    <foreground android:drawable="@mipmap/ic_launcher_foreground" />\n'
            '    <monochrome android:drawable="@mipmap/ic_launcher_foreground" />\n'
            "</adaptive-icon>\n"
        )

    values = OUT / "values"
    values.mkdir(parents=True, exist_ok=True)
    (values / "zcode_icon_colors.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<resources>\n"
        f'    <color name="zcode_icon_background">#{BG[0]:02X}{BG[1]:02X}{BG[2]:02X}</color>\n'
        "</resources>\n"
    )
    print("配色写入 res/values/zcode_icon_colors.xml")


if __name__ == "__main__":
    main()
