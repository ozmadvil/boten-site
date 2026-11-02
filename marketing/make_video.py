"""Short vertical marketing video (1080x1920, ~12s) for one price comparison: the same product at two prices.

Usage: python marketing/make_video.py marketing/demo.json out.mp4
The JSON holds the product name, the two prices, the date and the photo (or video) URLs. Text is drawn with Pillow
(Rubik, real RTL), motion and assembly by ffmpeg. Media are downloaded at run time and never stored in the repo.
"""
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import share_cards as sc  # noqa: E402  (Rubik fonts + RTL line drawing)

W, H, FPS = 1080, 1920, 30
INDIGO, INDIGO_D, SOFT = (79, 70, 229), (55, 48, 163), (238, 242, 255)
LIME, LIME_INK, INK, GREY, RED, GREEN = (163, 230, 53), (26, 46, 5), (17, 24, 39), (107, 114, 128), (220, 38, 38), (21, 128, 61)
WHITE = (255, 255, 255)


def fetch(url: str, path: Path) -> Path:
    if url.startswith(("http://", "https://")):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        path.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    else:
        path.write_bytes(Path(url).read_bytes())
    return path


def text(d, right, base, s, weight, size, fill):
    return sc._draw_rtl(d, right, base, s, sc._font(ROOT, weight, size), fill)


def centred(d, base, s, weight, size, fill, cx=W // 2):
    fonts = sc._font(ROOT, weight, size)
    w = sc._width(s, fonts)
    sc._draw_rtl(d, cx + w / 2, base, s, fonts, fill)


def pill(d, cx, cy, s, weight, size, bg, fg, pad=(34, 18)):
    fonts = sc._font(ROOT, weight, size)
    w = sc._width(s, fonts)
    box = (cx - w / 2 - pad[0], cy - size / 2 - pad[1], cx + w / 2 + pad[0], cy + size / 2 + pad[1])
    d.rounded_rectangle(box, radius=(box[3] - box[1]) / 2, fill=bg)
    sc._draw_rtl(d, cx + w / 2, cy + size * 0.36, s, fonts, fg)


def price_text(v: float) -> str:
    return f"₪{v:.2f}"


def fit_photo(src: Path, size: int) -> Image.Image:
    im = Image.open(src).convert("RGBA")
    im.thumbnail((size, size), Image.LANCZOS)
    tile = Image.new("RGBA", (size, size), WHITE + (255,))
    tile.alpha_composite(im, ((size - im.width) // 2, (size - im.height) // 2))
    return tile


def rounded(im: Image.Image, r: int) -> Image.Image:
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), r, fill=255)
    out = im.copy()
    out.putalpha(mask)
    return out


def scene_hook(spec, photo: Path, out: Path):
    """Scene 1 background (the photo, big, on a soft wash) + the hook line on top. ffmpeg zooms it slowly."""
    bg = Image.new("RGB", (W, H), SOFT)
    d = ImageDraw.Draw(bg)
    tile = rounded(fit_photo(photo, 900), 48)
    bg.paste(tile, ((W - 900) // 2, 560), tile)
    centred(d, 250, spec["hook1"], 900, 104, INK)
    centred(d, 390, spec["hook2"], 900, 104, INDIGO)
    pill(d, W // 2, 1600, spec["name"], 700, 46, WHITE, INK)
    bg.save(out)


def scene_prices(spec, photo_a: Path, photo_b: Path, out_a: Path, out_b: Path):
    """Scene 2: seller A (dear) then seller B (cheaper) appears; two frames, ffmpeg switches between them."""
    def base():
        im = Image.new("RGB", (W, H), WHITE)
        d = ImageDraw.Draw(im)
        centred(d, 200, spec["name"], 900, 64, INK)
        centred(d, 270, "אותו דגם · שני מוכרים", 500, 40, GREY)
        return im, d

    def card(im, d, y, photo, label, price, tone, strike):
        d.rounded_rectangle((60, y, W - 60, y + 560), 40, fill=SOFT if tone == "a" else (220, 252, 231))
        tile = rounded(fit_photo(photo, 400), 30)
        im.paste(tile, (100, y + 80), tile)
        right = W - 110
        text(d, right, y + 150, label, 700, 46, GREY)
        col = GREY if strike else GREEN
        fonts = sc._font(ROOT, 900, 100)
        w = sc._width(price_text(price), fonts)
        sc._draw_rtl(d, right, y + 320, price_text(price), fonts, col)
        if strike:
            d.line((right - w - 6, y + 285, right + 6, y + 285), fill=RED, width=10)

    im, d = base()
    card(im, d, 360, photo_a, "מוכר א׳", spec["price_a"], "a", False)
    im.save(out_a)
    im, d = base()
    card(im, d, 360, photo_a, "מוכר א׳", spec["price_a"], "a", True)
    card(im, d, 980, photo_b, "מוכר ב׳", spec["price_b"], "b", False)
    save = spec["price_a"] - spec["price_b"]
    pill(d, W // 2, 1660, f"חוסכים {price_text(save)}", 900, 64, LIME, LIME_INK, pad=(48, 26))
    centred(d, 1820, f"מחירים נכון ל-{spec['date']}, לפני משלוח", 400, 34, GREY)
    im.save(out_b)


def scene_end(spec, out: Path):
    im = Image.new("RGB", (W, H), INDIGO)
    glow = Image.new("RGB", (W, H), INDIGO)
    ImageDraw.Draw(glow).ellipse((-200, 300, W + 200, 1500), fill=(99, 102, 241))
    im = Image.blend(im, glow.filter(ImageFilter.GaussianBlur(160)), 0.8)
    d = ImageDraw.Draw(im)
    lat = sc._font(ROOT, 900, 150)[1]
    nice, buy = "Nice", "Buy"
    total = lat.getlength(nice) + lat.getlength(buy)
    x = (W - total) / 2
    d.text((x, 900), nice, font=lat, fill=WHITE, anchor="ls")
    d.text((x + lat.getlength(nice), 900), buy, font=lat, fill=LIME, anchor="ls")
    centred(d, 1080, "מדביקים לינק מאליאקספרס", 700, 62, WHITE)
    centred(d, 1170, "ומגלים אם יש זול יותר", 700, 62, WHITE)
    pill(d, W // 2, 1400, "nicebuy.co.il", 900, 64, WHITE, INDIGO_D, pad=(56, 30))
    im.save(out)


def build(spec_path: str, out_path: str):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    work = Path(out_path).with_suffix("")
    work.mkdir(parents=True, exist_ok=True)
    pa = fetch(spec["photo_a"], work / "a.img")
    pb = fetch(spec["photo_b"], work / "b.img")
    scene_hook(spec, pa, work / "s1.png")
    scene_prices(spec, pa, pb, work / "s2a.png", work / "s2b.png")
    scene_end(spec, work / "s3.png")
    T1, T2a, T2b, T3 = 3.5, 1.5, 4.0, 3.0
    zoom = f"zoompan=z='min(zoom+0.0009,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={int(T1 * FPS)}:s={W}x{H}:fps={FPS}"
    still = f"scale={W}:{H},fps={FPS},format=yuv420p"
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-loop", "1", "-t", str(T1), "-i", str(work / "s1.png"),
           "-loop", "1", "-t", str(T2a), "-i", str(work / "s2a.png"),
           "-loop", "1", "-t", str(T2b), "-i", str(work / "s2b.png"),
           "-loop", "1", "-t", str(T3), "-i", str(work / "s3.png"),
           "-filter_complex",
           f"[0:v]{zoom},format=yuv420p,trim=duration={T1}[v0];"
           f"[1:v]{still}[v1];[2:v]{still}[v2];[3:v]{still}[v3];"
           f"[v0][v1]xfade=transition=slideleft:duration=0.4:offset={T1 - 0.4}[x1];"
           f"[x1][v2]xfade=transition=fade:duration=0.2:offset={T1 + T2a - 0.6}[x2];"
           f"[x2][v3]xfade=transition=slideleft:duration=0.4:offset={T1 + T2a + T2b - 1.0}[v]",
           "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True)
    for name in ("s1", "s2b", "s3"):                    # stills too, for a quick look
        Image.open(work / f"{name}.png").convert("RGB").save(Path(out_path).parent / f"{Path(out_path).stem}-{name}.jpg", quality=88)


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
