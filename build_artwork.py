"""
PolyXRD GetCIF 品牌资产生成器
=============================
参照 PolyXRD / PolyXRD-CifCalc 的家族视觉，程序化生成一整套主题一致的美术资产。
（与家族 build_artwork.py 同源思路：Pillow 纯代码绘制，可复现、颜色精确。）

设计血统（与家族严格一致）
--------------------------
- 品牌深色 #0F172A (slate-950)  →  品牌蓝 #0284C7 (sky-600)  对角线渐变
- 家族符号 = 「白色正六边形 + 青色晶体晶格球棍」
- 子工具强调色 = 青色 #22D3EE（浅底词标用 #0891B2 提高对比）
- 词标字符沿用 PolyXRD-CifCalc logo 的排版：Segoe UI Bold「Poly(深) XRD(蓝) │ 工具名(青)」
  + 字距展开的 Segoe UI Semibold 副标。

产出（写入 ../resources/，即工程根 resources/）
------------------------------------------------
- app-icon.png        256×256  运行时窗口图标（PNG 优先，避开 .ico 插件崩溃问题）
- app-icon@2x.png     512×512  高分屏备份
- app-icon.ico        多分辨率  给 exe 资源 / 安装器使用
- crystal-mark.png    256×256  透明底深色 mark（浅色背景用，如 About/文档）
- logo-horizontal.png 512×160  横向 logo：mark + 「PolyXRD │ GetCIF」
- splash-screen.png   480×270  启动图（与家族同尺寸，便于复用加载逻辑）
- hero-banner.jpg     1600×900 About/官网用横幅

使用：
    python build_artwork.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# --------------------------------------------------------------------------- #
# 品牌常量
# --------------------------------------------------------------------------- #
BRAND_DARK = (15, 23, 42)        # #0F172A  slate-950  "Poly"
BRAND_BLUE = (2, 132, 199)       # #0284C7  sky-600    "XRD"
WHITE = (255, 255, 255)
SOFT = (226, 232, 240)           # #E2E8F0  slate-200
SLATE = (100, 116, 139)          # #64748B  slate-500
CYAN = (34, 211, 238)            # #22D3EE  子工具强调色
CYAN_LIGHT = (125, 211, 252)     # #7DD3FC
CYAN_DEEP = (14, 116, 144)       # #0E7490
CYAN_DARK = (8, 145, 178)        # #0891B2  浅色背景上的青色词标（更高对比）

# 启动图 / 横幅的深空背景（与家族 splash 的墨青基调一致）
BG_INNER = (12, 48, 70)
BG_OUTER = (5, 12, 24)

FONT_BOLD = r"C:/Windows/Fonts/segoeuib.ttf"
FONT_SEMI = r"C:/Windows/Fonts/seguisb.ttf"

RES_DIR = Path(__file__).resolve().parent / "resources"
ICON_SIZES = [16, 24, 32, 48, 64, 128, 256]
ISO_COS = math.cos(math.radians(30.0))  # 0.8660

# 工具标识（GetCIF 专属文案）
TOOL_WORD = "GetCIF"                 # 词标中的工具名（青色）
LOGO_SUB = "S E A R C H   &   F E T C H"
SPLASH_SUB = "CIF Search & Structure Retrieval"
HERO_SUB = "CIF Search · Fetch · Structure Retrieval"


# --------------------------------------------------------------------------- #
# 基础几何 / 绘制工具
# --------------------------------------------------------------------------- #
def hex_points(cx: float, cy: float, r: float) -> list[tuple[float, float]]:
    """尖顶正六边形顶点（顶点在正上/正下）。图像坐标 y 向下，故顶角取 -90°。"""
    return [
        (cx + r * math.cos(math.radians(-90 + 60 * k)),
         cy + r * math.sin(math.radians(-90 + 60 * k)))
        for k in range(6)
    ]


def _iso(x: float, y: float, z: float) -> tuple[float, float]:
    """等轴测投影：立方晶胞 -> 2D。"""
    return ((x - z) * ISO_COS, (x + z) * 0.5 - y)


def draw_lattice(draw: ImageDraw.ImageDraw, cx: float, cy: float, s: float,
                 node_color, bond_color, node_r: float, bond_w: int) -> None:
    """画一个球棍式晶胞（立方 8 顶点 + 12 条键），代表晶体结构。"""
    corners: dict[tuple[int, int, int], tuple[float, float]] = {}
    for xs in (-1, 1):
        for ys in (-1, 1):
            for zs in (-1, 1):
                px, py = _iso(xs * s, ys * s, zs * s)
                corners[(xs, ys, zs)] = (cx + px, cy + py)
    # 键：每条只画一次
    for cell, p in corners.items():
        for axis in range(3):
            c = list(cell)
            c[axis] = -c[axis]
            other = tuple(c)
            if cell < other:
                q = corners[other]
                draw.line([p, q], fill=bond_color, width=bond_w)
    # 原子节点
    for p in corners.values():
        draw.ellipse([p[0] - node_r, p[1] - node_r,
                      p[0] + node_r, p[1] + node_r], fill=node_color)


def make_mark(size: int, hex_color, node_color, bond_color,
              hex_w_ratio: float = 0.070,
              motif_scale: float = 0.150,
              node_ratio: float = 0.034,
              bond_ratio: float = 0.017,
              glow: bool = False) -> Image.Image:
    """生成「六边形 + 晶格球棍」家族符号（透明底 RGBA）。"""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cx = cy = size / 2.0
    r = size * 0.44
    hex_w = max(2, int(round(size * hex_w_ratio)))
    pts = hex_points(cx, cy, r)

    if glow:
        gl = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        gd = ImageDraw.Draw(gl)
        gd.line(pts + [pts[0]], fill=hex_color, width=hex_w, joint="curve")
        draw_lattice(gd, cx, cy, size * motif_scale, node_color, bond_color,
                     size * node_ratio, max(2, int(size * bond_ratio)))
        gl = gl.filter(ImageFilter.GaussianBlur(max(2, size * 0.02)))
        im.alpha_composite(gl)

    d = ImageDraw.Draw(im)
    d.line(pts + [pts[0]], fill=hex_color, width=hex_w, joint="curve")
    draw_lattice(d, cx, cy, size * motif_scale, node_color, bond_color,
                 size * node_ratio, max(2, int(size * bond_ratio)))
    return im


def diagonal_gradient(size: int, c1, c2) -> Image.Image:
    """左上 -> 右下 对角线渐变（低分辨率生成再放大，保证平滑）。"""
    small = Image.new("RGB", (96, 96))
    px = small.load()
    for y in range(96):
        for x in range(96):
            t = (x + y) / (2 * 95.0)
            px[x, y] = (round(c1[0] + (c2[0] - c1[0]) * t),
                        round(c1[1] + (c2[1] - c1[1]) * t),
                        round(c1[2] + (c2[2] - c1[2]) * t))
    return small.resize((size, size), Image.BICUBIC)


def radial_gradient(w: int, h: int, inner, outer) -> Image.Image:
    """径向渐变背景（中心亮 -> 四周暗）。"""
    small = Image.new("RGB", (120, 68))
    px = small.load()
    cx, cy = 59.5, 33.0
    maxd = math.hypot(cx, cy)
    for y in range(68):
        for x in range(120):
            d = min(1.0, math.hypot(x - cx, y - cy) / maxd)
            d = d ** 0.85
            px[x, y] = (round(inner[0] + (outer[0] - inner[0]) * d),
                        round(inner[1] + (outer[1] - inner[1]) * d),
                        round(inner[2] + (outer[2] - inner[2]) * d))
    return small.resize((w, h), Image.BICUBIC)


def rounded_mask(size: int, ratio: float = 0.22) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size - 1, size - 1),
                                        radius=int(size * ratio), fill=255)
    return m


def draw_wordmark(draw: ImageDraw.ImageDraw, x: float, y_top: float,
                  segments: list[tuple[str, tuple[int, int, int]]],
                  font: ImageFont.FreeTypeFont) -> float:
    """按 segment 着色绘制词标，返回结束 x。"""
    for text, color in segments:
        draw.text((x, y_top), text, font=font, fill=color)
        x += draw.textlength(text, font=font)
    return x


# --------------------------------------------------------------------------- #
# 各类资产构建
# --------------------------------------------------------------------------- #
def build_icon() -> None:
    size = 512
    base = diagonal_gradient(size, BRAND_DARK, BRAND_BLUE).convert("RGBA")
    mark = make_mark(size, WHITE, CYAN, CYAN,
                     hex_w_ratio=0.075, motif_scale=0.150,
                     node_ratio=0.035, bond_ratio=0.018)
    base.alpha_composite(mark, (0, 0))
    base.putalpha(rounded_mask(size, 0.22))

    RES_DIR.mkdir(parents=True, exist_ok=True)
    base.resize((512, 512), Image.LANCZOS).save(RES_DIR / "app-icon@2x.png",
                                                 format="PNG", optimize=True)
    base.resize((256, 256), Image.LANCZOS).save(RES_DIR / "app-icon.png",
                                                 format="PNG", optimize=True)
    base.save(RES_DIR / "app-icon.ico", format="ICO",
              sizes=[(s, s) for s in ICON_SIZES])
    print(f"[icon] app-icon.png / @2x / .ico  ->  {RES_DIR}")


def build_crystal_mark() -> None:
    """透明底、深色线条版家族符号（浅色背景 About / 文档用）。"""
    size = 256
    mark = make_mark(size, BRAND_DARK, BRAND_BLUE, BRAND_DARK,
                     hex_w_ratio=0.055, motif_scale=0.150,
                     node_ratio=0.032, bond_ratio=0.016)
    mark.save(RES_DIR / "crystal-mark.png", format="PNG", optimize=True)
    print("[mark] crystal-mark.png")


def build_logo_horizontal() -> None:
    """横向 logo：mark + 「PolyXRD │ GetCIF」。"""
    SS = 4
    H = 160
    mH = H * SS

    mark_size = int(mH * 0.78)
    pad_x = int(mH * 0.10)
    x0 = pad_x + mark_size + int(mH * 0.10)

    font_big = ImageFont.truetype(FONT_BOLD, int(mH * 0.42))
    font_sub = ImageFont.truetype(FONT_SEMI, int(mH * 0.150))
    sub = LOGO_SUB

    tmp = Image.new("RGBA", (8, 8))
    td = ImageDraw.Draw(tmp)
    seg_w = td.textlength("Poly", font=font_big) + td.textlength("XRD", font=font_big)
    gap = int(mH * 0.05)
    div_w = max(2, int(mH * 0.015))
    tool_w = td.textlength(TOOL_WORD, font=font_big)
    big_w = seg_w + gap + div_w + gap + tool_w
    sub_w = td.textlength(sub, font=font_sub)
    mW = int(x0 + max(big_w, sub_w) + int(mH * 0.18))

    im = Image.new("RGBA", (mW, mH), (0, 0, 0, 0))
    mark = make_mark(mark_size, BRAND_DARK, BRAND_BLUE, BRAND_DARK,
                     hex_w_ratio=0.055, motif_scale=0.150,
                     node_ratio=0.032, bond_ratio=0.016)
    im.alpha_composite(mark, (pad_x, (mH - mark_size) // 2))

    d = ImageDraw.Draw(im)
    y_big = int(mH * 0.17)
    x = draw_wordmark(d, x0, y_big,
                      [("Poly", BRAND_DARK), ("XRD", BRAND_BLUE)], font_big)
    dv_x = x + gap
    d.line([(dv_x, y_big + int(mH * 0.03)), (dv_x, y_big + int(mH * 0.40))],
           fill=(203, 213, 225), width=div_w)
    d.text((dv_x + gap, y_big), TOOL_WORD, font=font_big, fill=CYAN_DARK)
    d.text((x0 + int(mH * 0.012), y_big + int(mH * 0.46)), sub,
           font=font_sub, fill=SLATE)

    im.resize((mW // SS, mH // SS), Image.LANCZOS).save(
        RES_DIR / "logo-horizontal.png", format="PNG", optimize=True)
    print("[logo] logo-horizontal.png")


def _draw_wave(d: ImageDraw.ImageDraw, x0: float, y0: float, length: float,
               amp: float, color, width: int, peak: bool = True) -> None:
    """画一段 XRD 式衍射波（带中心尖峰）。"""
    pts = []
    n = 220
    for i in range(n + 1):
        t = i / n
        x = x0 + t * length
        env = math.sin(math.pi * t) ** 1.2
        y = y0 - amp * env * math.sin(t * math.pi * (6 if peak else 8))
        if peak:
            y -= amp * 0.9 * env * math.exp(-((t - 0.5) ** 2) / 0.006)
        pts.append((x, y))
    d.line(pts, fill=color, width=width, joint="curve")


def build_splash() -> None:
    """启动图 480×270（先 2× 渲染再下采样）。"""
    W, H = 480, 270
    SS = 2
    w, h = W * SS, H * SS
    bg = radial_gradient(w, h, BG_INNER, BG_OUTER).convert("RGBA")

    # 中心发光晶格
    lat = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lat)
    draw_lattice(ld, w / 2, h * 0.44, h * 0.115, CYAN_LIGHT, CYAN_LIGHT,
                 h * 0.026, max(2, int(h * 0.013)))
    glow = lat.filter(ImageFilter.GaussianBlur(h * 0.035))
    bg.alpha_composite(glow)
    bg.alpha_composite(glow)
    bg.alpha_composite(lat)

    # 两侧衍射波
    waves = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    wd = ImageDraw.Draw(waves)
    _draw_wave(wd, w * 0.04, h * 0.44, w * 0.27, h * 0.095, (34, 211, 238, 130), 2)
    _draw_wave(wd, w * 0.69, h * 0.44, w * 0.27, h * 0.095, (34, 211, 238, 130), 2)
    bg.alpha_composite(waves.filter(ImageFilter.GaussianBlur(1.2)))

    d = ImageDraw.Draw(bg)
    # 标题
    font_t = ImageFont.truetype(FONT_BOLD, int(h * 0.100))
    tw = d.textlength("PolyXRD", font=font_t) + d.textlength(" " + TOOL_WORD, font=font_t)
    tx = (w - tw) / 2
    ty = h * 0.70
    draw_wordmark(d, tx, ty,
                  [("PolyXRD", (226, 232, 240)), (" " + TOOL_WORD, CYAN_LIGHT)], font_t)
    # 副标
    font_s = ImageFont.truetype(FONT_SEMI, int(h * 0.050))
    sub = SPLASH_SUB
    sw = d.textlength(sub, font=font_s)
    d.text(((w - sw) / 2, h * 0.845), sub, font=font_s, fill=(130, 176, 205))

    bg.convert("RGB").resize((W, H), Image.LANCZOS).save(
        RES_DIR / "splash-screen.png", format="PNG", optimize=True)
    print("[splash] splash-screen.png")


def build_hero() -> None:
    """About / 官网横幅 1600×900。"""
    W, H = 1600, 900
    bg = radial_gradient(W, H, BG_INNER, BG_OUTER).convert("RGBA")

    lat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lat)
    draw_lattice(ld, W / 2, H * 0.42, H * 0.115, CYAN_LIGHT, CYAN_LIGHT,
                 H * 0.026, max(2, int(H * 0.012)))
    glow = lat.filter(ImageFilter.GaussianBlur(H * 0.03))
    bg.alpha_composite(glow)
    bg.alpha_composite(glow)
    bg.alpha_composite(lat)

    waves = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wd = ImageDraw.Draw(waves)
    _draw_wave(wd, W * 0.03, H * 0.42, W * 0.24, H * 0.07, CYAN_DEEP, 3)
    _draw_wave(wd, W * 0.73, H * 0.42, W * 0.24, H * 0.07, CYAN_DEEP, 3)
    bg.alpha_composite(waves.filter(ImageFilter.GaussianBlur(3)))

    d = ImageDraw.Draw(bg)
    font_t = ImageFont.truetype(FONT_BOLD, int(H * 0.090))
    title = "PolyXRD " + TOOL_WORD
    tw = d.textlength(title, font=font_t)
    draw_wordmark(d, (W - tw) / 2, H * 0.70,
                  [("PolyXRD", (226, 232, 240)), (" " + TOOL_WORD, CYAN_LIGHT)], font_t)
    font_s = ImageFont.truetype(FONT_SEMI, int(H * 0.038))
    sub = HERO_SUB
    sw = d.textlength(sub, font=font_s)
    d.text(((W - sw) / 2, H * 0.83), sub, font=font_s, fill=(130, 176, 205))

    bg.convert("RGB").save(RES_DIR / "hero-banner.jpg", format="JPEG", quality=90)
    print("[hero] hero-banner.jpg")


def build_all() -> None:
    RES_DIR.mkdir(parents=True, exist_ok=True)
    build_icon()
    build_crystal_mark()
    build_logo_horizontal()
    build_splash()
    build_hero()
    print(f"\n[done] 全部资产已写入: {RES_DIR}")


if __name__ == "__main__":
    build_all()
