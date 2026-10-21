"""Share cards: the 1200x630 picture that WhatsApp, Telegram, Facebook and X show when a page is shared.

Drawn at build time by build.py (one per page, into _site/og/<page>.png), in the flyer's own world: a red masthead
strip with the mascot, a fluorescent yellow field, the page's headline in Rubik Black, and on the home page and the
category pages up to three of the page's own deals as paper tags with their real price.

Provenance: everything on a card comes from the page itself; product photos are the AliExpress product images the
bot's feed points to, downloaded during the build and never stored in the repo. If Pillow or python-bidi are missing,
or a download fails, build.py falls back to the logo; a card never fails a build.
"""
from __future__ import annotations

import io
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    from bidi import get_display                     # python-bidi >= 0.5
except ImportError:                                  # older python-bidi
    from bidi.algorithm import get_display

W, H = 1200, 630
YELLOW, RED, INK, INK_ON_FLYER = (255, 229, 0), (216, 0, 26), (29, 22, 6), (61, 51, 0)
WHITE, GREEN, RULE = (255, 255, 255), (15, 122, 61), (228, 220, 192)
COLORS = {"ink": INK, "red": RED}
MARGIN = 48

_fonts: dict[tuple[str, int], tuple] = {}
_images: dict[str, bytes | None] = {}


# ------------------------------------------------------------------ fonts: the site's own Rubik subsets
# The site ships Rubik as two subsets per weight (assets/fonts). A character goes to the Hebrew subset when it is in
# that subset's unicode-range (the same ranges as the @font-face rules in style.css), otherwise to the Latin one.
HEBREW_RANGES = ((0x0307, 0x0308), (0x0590, 0x05FF), (0x200C, 0x2010), (0x20AA, 0x20AA), (0x25CC, 0x25CC), (0xFB1D, 0xFB4F))


def _is_hebrew(ch: str) -> bool:
    cp = ord(ch)
    return any(a <= cp <= b for a, b in HEBREW_RANGES)


def _font_source(root: Path, script: str, weight: int):
    path = root / "assets" / "fonts" / f"rubik-{script}-{weight}-normal.woff2"
    try:
        ImageFont.truetype(str(path), 10, layout_engine=ImageFont.Layout.BASIC)
        return str(path)
    except OSError:                                  # FreeType without WOFF2 support: decompress with fontTools
        from fontTools.ttLib import TTFont
        f = TTFont(str(path))
        f.flavor = None
        buf = io.BytesIO()
        f.save(buf)
        return buf.getvalue()


def _font(root: Path, weight: int, size: int) -> tuple:
    """(hebrew, latin) Rubik at this weight and size."""
    key = (str(root), weight, size)
    if key not in _fonts:
        pair = []
        for script in ("hebrew", "latin"):
            src = _font_source(root, script, weight)
            src = io.BytesIO(src) if isinstance(src, bytes) else src
            pair.append(ImageFont.truetype(src, size, layout_engine=ImageFont.Layout.BASIC))
        _fonts[key] = tuple(pair)
    return _fonts[key]


def _runs(visual: str, fonts) -> list[tuple[str, object]]:
    """Split a visually ordered line into runs, each drawn with the subset that has its glyphs."""
    heb, lat = fonts
    runs: list[tuple[str, object]] = []
    for ch in visual:
        f = runs[-1][1] if ch == " " and runs else (heb if _is_hebrew(ch) else lat)
        if runs and runs[-1][1] is f:
            runs[-1] = (runs[-1][0] + ch, f)
        else:
            runs.append((ch, f))
    return runs


def _width(text: str, fonts) -> float:
    return sum(f.getlength(t) for t, f in _runs(get_display(text, base_dir="R"), fonts))


def _draw_rtl(d: ImageDraw.ImageDraw, right: float, baseline: float, text: str, fonts, fill) -> float:
    """Draw one logical (RTL) line ending at `right`; returns its width."""
    runs = _runs(get_display(text, base_dir="R"), fonts)
    width = sum(f.getlength(t) for t, f in runs)
    x = right - width
    for t, f in runs:
        d.text((x, baseline), t, font=f, fill=fill, anchor="ls")
        x += f.getlength(t)
    return width


def _wrap(text: str, fonts, max_w: float) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        cand = f"{cur} {word}".strip()
        if cur and _width(cand, fonts) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


# ------------------------------------------------------------------ product photos
def _load_image(src: str, out: Path) -> bytes | None:
    if src.startswith("/"):                          # a file inside the built site (local test data)
        f = out / src.lstrip("/")
        return f.read_bytes() if f.exists() else None
    req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0 (boten-site share cards)"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return r.read()


def prefetch(urls: list[str], out: Path) -> None:
    todo = [u for u in dict.fromkeys(urls) if u and u not in _images]

    def get(u):
        try:
            return u, _load_image(u, out)
        except Exception:
            return u, None
    with ThreadPoolExecutor(max_workers=12) as pool:
        for u, data in pool.map(get, todo):
            _images[u] = data


def _photo(src: str, out: Path, size: int) -> Image.Image | None:
    if src not in _images:
        prefetch([src], out)
    data = _images.get(src)
    if not data:
        return None
    try:
        im = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        return None
    im.thumbnail((size, size), Image.LANCZOS)
    box = Image.new("RGB", (size, size), WHITE)
    box.paste(im, ((size - im.width) // 2, (size - im.height) // 2))
    return box


# ------------------------------------------------------------------ pieces of the flyer
def _shadow(canvas: Image.Image, box: tuple[int, int, int, int], radius: int = 6) -> None:
    """The laid-on paper shadow: a contact line and a soft warm drop, like the site's --shadow."""
    x0, y0, x1, y1 = box
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle((x0 + 4, y0 + 14, x1 - 4, y1 + 14), radius, fill=(61, 51, 0, 80))
    layer = layer.filter(ImageFilter.GaussianBlur(14))
    ImageDraw.Draw(layer).rounded_rectangle((x0, y0 + 1, x1, y1 + 1), radius, fill=(61, 51, 0, 40))
    canvas.alpha_composite(layer)


def _price(d: ImageDraw.ImageDraw, root: Path, left: int, baseline: int, value: float, size: int) -> None:
    """₪145⁸⁸: small shekel, big whole, small raised underlined agorot, read left to right."""
    heb_big, big = _font(root, 900, size)
    heb_small, small = _font(root, 900, int(size * 0.42))
    whole, ag = f"{value:.2f}".split(".")
    top = baseline + big.getbbox("8", anchor="ls")[1]              # the top of the big numerals
    small_base = top - small.getbbox("8", anchor="ls")[1]          # small figures hang from that top
    x = left
    d.text((x, small_base), "₪", font=heb_small, fill=RED, anchor="ls")
    x += heb_small.getlength("₪") + 2
    d.text((x, baseline), whole, font=big, fill=RED, anchor="ls")
    x += big.getlength(whole) + 3
    if ag != "00":
        d.text((x, small_base), ag, font=small, fill=RED, anchor="ls")
        uy = small_base + max(3, size // 14)
        d.line((x, uy, x + small.getlength(ag), uy), fill=RED, width=max(2, size // 22))


def _tag(canvas: Image.Image, root: Path, out: Path, p: dict, x: int, y: int, w: int) -> None:
    pic = w - 20
    h = 30 + 10 + pic + 74
    _shadow(canvas, (x, y, x + w, y + h))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((x, y, x + w, y + h), 6, fill=WHITE)
    d.rounded_rectangle((x, y, x + w, y + 30), 6, fill=RED)
    d.rectangle((x, y + 20, x + w, y + 30), fill=RED)
    disc = p.get("discount")
    fonts = _font(root, 900, 19)
    if disc and float(disc) >= 5:                    # "-67%" reads left to right, like the burst on the site
        d.text((x + w - 12, y + 22), f"-{float(disc):.0f}%", font=fonts[1], fill=WHITE, anchor="rs")
    else:
        _draw_rtl(d, x + w - 12, y + 22, "מבצע", fonts, WHITE)
    photo = _photo(p.get("image", ""), out, pic)
    if photo:
        canvas.paste(photo, (x + 10, y + 40))
    else:
        d.rectangle((x + 10, y + 40, x + 10 + pic, y + 40 + pic), outline=RULE, width=2)
    _price(d, root, x + 12, y + 40 + pic + 58, float(p["price"]), 46)


def _stamp(canvas: Image.Image, root: Path, cx: int, cy: int) -> None:
    """The green "נבדק בקופה" rubber stamp, at the stamp's own -9deg."""
    layer = Image.new("RGBA", (320, 170), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((10, 10, 310, 160), 12, outline=GREEN, width=8, fill=(255, 255, 255, 215))
    _draw_rtl(d, 160 + _width("נבדק", _font(root, 900, 64)) / 2, 88, "נבדק", _font(root, 900, 64), GREEN)
    _draw_rtl(d, 160 + _width("בקופה", _font(root, 500, 36)) / 2, 138, "בקופה", _font(root, 500, 36), GREEN)
    layer = layer.rotate(9, resample=Image.BICUBIC, expand=True)
    canvas.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))


# ------------------------------------------------------------------ the card
def _layout_text(root: Path, card: dict, text_w: float):
    """The headline (as large as fits in three lines) and the subline, laid out for this width."""
    spec = card.get("lines") or []
    for size in (92, 84, 76, 68, 62, 56, 50, 46):
        fonts = _font(root, 900, size)
        lines = [(ln, color) for text, color in spec for ln in _wrap(text, fonts, text_w)]
        if len(lines) <= 3 and all(_width(ln, fonts) <= text_w for ln, _ in lines):
            break
    sub_fonts = _font(root, 500, 32)
    sub = _wrap(card.get("sub") or "", sub_fonts, text_w)[:2]
    height = len(lines) * int(size * 1.04) + (14 + len(sub) * 44 if sub else 0)
    return size, fonts, lines[:3], sub_fonts, sub, height


def render(target: Path, card: dict, root: Path, out: Path) -> bool:
    canvas = Image.new("RGBA", (W, H), YELLOW + (255,))
    d = ImageDraw.Draw(canvas)
    top, bottom = 96, H - 10                         # the yellow field between the masthead and the ink rule

    # masthead: the red flyer strip with the mascot and the name
    d.rectangle((0, 0, W, top), fill=RED)
    logo_size = 64
    name_right = W - MARGIN
    try:
        logo = Image.open(root / "assets" / "logo-192.png").convert("RGBA").resize((logo_size, logo_size), Image.LANCZOS)
        mask = Image.new("L", (logo_size, logo_size), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, logo_size - 1, logo_size - 1), 14, fill=255)
        lx, ly = W - MARGIN - logo_size, 16
        d.rounded_rectangle((lx - 3, ly - 3, lx + logo_size + 2, ly + logo_size + 2), 16, fill=WHITE)
        canvas.paste(logo, (lx, ly), mask)
        name_right = lx - 18
    except OSError:
        pass
    _draw_rtl(d, name_right, 66, "בוטן", _font(root, 900, 50), WHITE)
    d.text((MARGIN, 60), "@Boten_IL_bot", font=_font(root, 500, 26)[1], fill=WHITE, anchor="ls")

    # the deals (home page, categories): paper tags on the left; the coupons page gets the rubber stamp there
    prods = [p for p in (card.get("products") or []) if p.get("price")][:3]
    text_w = W - 2 * MARGIN
    if prods:
        tw, gap = 184, 18
        tag_h = 30 + 10 + (tw - 20) + 74
        ty = top + (bottom - top - tag_h) // 2
        for i, p in enumerate(prods):                  # right to left: the first deal sits next to the headline
            _tag(canvas, root, out, p, MARGIN + (len(prods) - 1 - i) * (tw + gap), ty, tw)
        text_w = W - MARGIN - (MARGIN + len(prods) * (tw + gap)) - 26
    elif card.get("stamp"):
        _stamp(canvas, root, 250, (top + bottom) // 2)
        text_w = W - MARGIN - 470
    d = ImageDraw.Draw(canvas)

    # headline and subline, centred in the yellow field
    size, fonts, lines, sub_fonts, sub, height = _layout_text(root, card, text_w)
    y = top + max(34, (bottom - top - height) // 2) + int(size * 0.8)
    for ln, color in lines:
        _draw_rtl(d, W - MARGIN, y, ln, fonts, COLORS.get(color, INK))
        y += int(size * 1.04)
    if sub:
        y += 14 - int(size * 1.04) + int(size * 0.2) + 32
        for ln in sub:
            _draw_rtl(d, W - MARGIN, y, ln, sub_fonts, INK_ON_FLYER)
            y += 44

    # the footer's heavy ink rule
    d.rectangle((0, bottom, W, H), fill=INK)

    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(target, "PNG", optimize=True)
    return True
