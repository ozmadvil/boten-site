"""The creator pages, built from a sample data/creators.json and kept /picks answers, in a copy of the site:
which pages exist, what is on them, and that with no file nothing of this exists."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = "https://s.click.aliexpress.com/e/_"


def pick(pid, title, price=18.31):
    return {"id": pid, "title": title, "image": "https://ae-pic-a1.aliexpress-media.com/kf/x.jpg", "price": price, "original": 43.26,
            "discount": 57.0, "link": LINK + pid[-4:], "checked": "2026-11-18T09:00+02:00"}


def build(d: Path, creators: dict | None, picks: dict[str, dict]) -> tuple[str, Path]:
    site = d / "site"
    shutil.copytree(ROOT, site, ignore=shutil.ignore_patterns("_site", ".git", "__pycache__", "picks-*.json", "creators.json"))
    if creators is not None:
        (site / "data" / "creators.json").write_text("null" if creators == "null" else json.dumps(creators, ensure_ascii=False), encoding="utf-8")
    for name, feed in picks.items():
        (site / "data" / name).write_text(json.dumps(feed, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, "build.py"], cwd=site, capture_output=True, text=True,
                       env={**os.environ, "BOT_FEED_URL": "off", "CF_BEACON": "off"})
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    return r.stdout, site / "_site"


SAMPLE = {"topics": [{"slug": "nails", "name": "ציפורניים", "h1": "ציפורניים: הציוד שיוצרים בחרו", "lead": "שורת פתיחה.", "people": "היוצרות"}],
          "creators": [
              {"slug": "dana", "topic": "nails", "name": "דנה לדוגמה", "about": "בונה ציפורניים בג'ל", "about_ok": "2026-11-10", "tracking": "nails_dana", "videos_ok": "2026-11-10",
               "instagram": "https://www.instagram.com/dana_example/",
               "products": [
                   {"slug": "uv-lamp", "id": "1005000000000001", "name": "מנורת UV לציפורניים", "video": "https://www.instagram.com/reel/DZE-pBygPIr/",
                    "quote": "המנורה שעל השולחן", "text": ["פסקה <b>ראשונה</b> של דנה.", "פסקה שנייה."], "text_ok": "2026-11-11"},
                   {"slug": "gel", "id": "1005000000000002", "name": "לק ג'ל", "video": "https://www.youtube.com/shorts/3g_UNj5KyS8"},
                   {"slug": "drill", "id": "1005000000000003", "name": "מקדחה לציפורניים"},
                   {"slug": "gone", "id": "1005000000000004", "name": "מוצר שירד"}]},
              {"slug": "noa", "topic": "nails", "name": "נועה לדוגמה", "about": "לא אושר", "tracking": "nails_noa", "videos_ok": "2026-11-10",
               "products": [{"slug": "top-coat", "id": "1005000000000009", "name": "טופ קוט", "video": "https://www.tiktok.com/@noa/video/7301234567890123456"}]},
              {"slug": "empty", "topic": "nails", "name": "בלי מוצרים חיים", "tracking": "nails_empty", "videos_ok": "2026-11-10",
               "products": [{"slug": "x", "id": "1005000000000077", "name": "אין מחיר"}]}]}
PICKS = {"picks--nails--dana.json": {"tid": "nails_dana", "updated": "2026-11-18T09:00+02:00", "products": [
             pick("1005000000000001", "מנורת ייבוש UV"), pick("1005000000000002", "לק ג'ל"), pick("1005000000000003", "מקדחה"),
             dict(pick("1005000000000004", "קישור רגיל"), link="https://www.aliexpress.com/item/1005000000000004.html")]},
         "picks--nails--noa.json": {"tid": "nails_noa", "updated": "2026-11-18T09:00+02:00", "products": [pick("1005000000000009", "טופ קוט")]},
         "picks--nails--empty.json": {"tid": "someone_else", "updated": "2026-11-18T09:00+02:00", "products": [pick("1005000000000077", "x")]}}

import re
main = lambda h: h[h.index('<main'):h.index('</main>')]

with tempfile.TemporaryDirectory() as tmp:
    out, site = build(Path(tmp) / "a", SAMPLE, PICKS)
    read = lambda p: (site / p / "index.html").read_text(encoding="utf-8")
    hub, dana, lamp, gel, top = read("nails"), read("nails/dana"), read("nails/dana/uv-lamp"), read("nails/dana/gel"), read("nails/noa/top-coat")
    # which pages exist: a product with neither a video nor her words has no page of its own; nothing for a creator
    # whose kept prices carry another tracking id; nothing for a product that has only a plain link
    assert not (site / "nails/dana/drill").exists() and not (site / "nails/dana/gone").exists() and not (site / "nails/empty").exists()
    assert "בלי מוצרים חיים" not in hub and "מוצר שירד" not in dana
    # the topic: both creators, each one's products under their name, the people heading from the file
    assert "דנה לדוגמה" in hub and "נועה לדוגמה" in hub and "<h2>היוצרות</h2>" in hub and 'href="/nails/dana/"' in hub
    assert "המוצרים של דנה לדוגמה</h2>" in hub and "המוצרים של נועה לדוגמה</h2>" in hub
    # the line about a creator is shown only when the creator approved it
    assert "בונה ציפורניים בג&#x27;ל" in dana and "לא אושר" not in hub and "לא אושר" not in read("nails/noa")
    # a card opens the product's own page when there is one, AliExpress (as a sponsored link, and saying so) when not
    assert 'href="/nails/dana/uv-lamp/"' in dana and 'href="/nails/dana/gel/"' in dana and "למוצר באליאקספרס" in dana
    assert f'href="{LINK}0003" rel="sponsored nofollow noopener" target="_blank"' in dana
    assert 'href="https://www.instagram.com/dana_example/"' in dana and "המנורה שעל השולחן" in dana
    # the product page: the player waits for a press, her words are escaped in the page itself, the price is dated
    assert 'data-src="https://www.instagram.com/reel/DZE-pBygPIr/embed/"' in lamp and "<iframe" not in lamp
    assert "<p>פסקה &lt;b&gt;ראשונה&lt;/b&gt; של דנה.</p>" in main(lamp) and "<b>ראשונה</b>" not in lamp and "במילים של דנה לדוגמה" in lamp
    assert lamp.count(f'href="{LINK}0001" rel="sponsored nofollow noopener"') == 1 and "נכון ל-18/11" in lamp    # one button to AliExpress, under the price
    assert 'data-src="https://www.youtube-nocookie.com/embed/3g_UNj5KyS8?autoplay=1&amp;rel=0"' in gel and "במילים של" not in gel
    assert gel.count(f'href="{LINK}0002" rel="sponsored nofollow noopener"') == 1
    assert 'data-src="https://www.tiktok.com/player/v1/7301234567890123456?autoplay=1&amp;rel=0"' in top
    # the disclosure: on every page, above the first link to AliExpress, saying who pays whom
    for html_, who in ((hub, None), (dana, "דנה לדוגמה"), (lamp, "דנה לדוגמה"), (top, "נועה לדוגמה")):
        m = main(html_)
        assert "תוכן שיווקי · שיתוף פעולה" in m and "NiceBuy מקבל עמלה מאליאקספרס" in m and "המחיר שלכם לא משתנה" in m
        assert who is None or f"עובר אל {who}" in m
        assert m.index("collab-note") < m.index("s.click.aliexpress.com"), "a link to AliExpress above the disclosure"
    # descriptions: no gendered verb, no claim of a video where there is none, cut on a whole word
    desc = lambda h: re.search(r'<meta name="description" content="([^"]*)"', h).group(1)
    assert desc(dana).startswith("הבחירות של דנה לדוגמה: מוצרי ציפורניים מאליאקספרס, עם סרטונים") and "בחרה" not in desc(dana)
    assert "דנה לדוגמה ונועה לדוגמה" in desc(hub) and "אנשי מקצוע" not in hub and len(desc(lamp)) <= 156 and not desc(lamp).endswith(" ")
    # frames only from the three players in use; the chip leads the strip on every page
    home = (site / "index.html").read_text(encoding="utf-8")
    assert "frame-src https://www.instagram.com https://www.tiktok.com https://www.youtube-nocookie.com" in home
    assert home.index('href="/nails/"') < home.index('href="/c/') and "ציפורניים · המלצות" in home
    # the sitemap: the topic, the creators, and a product page only when it has her words (a video alone is thin)
    sm = (site / "sitemap.xml").read_text(encoding="utf-8")
    assert all(u in sm for u in ("/nails/</loc>", "/nails/dana/</loc>", "/nails/dana/uv-lamp/</loc>"))
    assert "/nails/dana/gel/" not in sm and "/nails/noa/top-coat/" not in sm and "noindex" not in lamp
    assert "vembed" in (site / "assets/app.js").read_text(encoding="utf-8")
    privacy = read("privacy")
    assert "סרטונים של יוצרים" in privacy and "רק אחרי שלוחצים" in privacy and "מיוטיוב, מאינסטגרם או מטיקטוק" in privacy

    # a made-up creator, alone in its topic: marked as an example, hidden from search engines, linked from nowhere,
    # and nobody is said to be paid
    demo = {"topics": SAMPLE["topics"], "creators": [{"slug": "demo", "topic": "nails", "demo": True, "name": "יוצרת לדוגמה", "about": "משפט לדוגמה",
            "tracking": "nicebuy", "products": [{"slug": "uv-lamp", "id": "1005000000000001", "name": "מנורת UV", "video": "https://youtu.be/_KbrQ0PTjlg",
                                                 "text": ["טקסט ממלא מקום."]}]}]}
    out, site = build(Path(tmp) / "c", demo, {"picks--nails--demo.json": dict(PICKS["picks--nails--dana.json"], tid="nicebuy")})
    for pth in ("nails", "nails/demo", "nails/demo/uv-lamp"):
        h = (site / pth / "index.html").read_text(encoding="utf-8")
        assert '<meta name="robots" content="noindex, nofollow">' in h and "דף לדוגמה" in main(h), pth
        assert "בדף אמיתי תופיע כאן שורת הגילוי הנאות" in main(h) and "<b>שיתוף פעולה.</b>" not in main(h), pth
    home, sm = (site / "index.html").read_text(encoding="utf-8"), (site / "sitemap.xml").read_text(encoding="utf-8")
    assert "/nails/" not in sm and 'href="/nails/"' not in home
    # beside a real creator the example is not on the topic page, and its trail does not lead there
    mixed = {"topics": SAMPLE["topics"], "creators": [SAMPLE["creators"][0], demo["creators"][0]]}
    out, site = build(Path(tmp) / "d", mixed, {"picks--nails--dana.json": PICKS["picks--nails--dana.json"],
                                               "picks--nails--demo.json": dict(PICKS["picks--nails--dana.json"], tid="nicebuy")})
    hub, d = (site / "nails/index.html").read_text(encoding="utf-8"), (site / "nails/demo/index.html").read_text(encoding="utf-8")
    assert "יוצרת לדוגמה" not in hub and "noindex" not in hub and "noindex" in d and 'href="/nails/"' not in main(d)

    # hostile values in every field that reaches a page: nothing gets out of its place
    X = '"><img src=x onerror=1>'
    evil = {"topics": [{"slug": "nails", "name": "ציפורניים" + X, "h1": "h" + X, "lead": "l" + X, "people": "p" + X, "chip": "c" + X}],
            "creators": [{"slug": "dana", "topic": "nails", "name": "דנה" + X, "about": "a" + X, "about_ok": "2026-11-10", "tracking": "nails_dana",
                          "videos_ok": "2026-11-10", "photo": '../x"onerror=1.jpg', "instagram": "https://www.instagram.com/x" + X,
                          "youtube": "https://evil.com\\@youtube.com/x",
                          "products": [{"slug": "uv-lamp", "id": "1005000000000001", "name": "n" + X, "quote": "q" + X, "text": ["t" + X],
                                        "text_ok": "2026-11-11", "video": "https://www.youtube.com/watch?v=_KbrQ0PTjlg" + X, "poster": 'x" onload="1.jpg'}]}]}
    bad_feed = {"tid": "nails_dana", "updated": "2026-11-18T09:00+02:00", "products": [
        dict(pick("1005000000000001", "title" + X), image="https://ae-pic-a1.aliexpress-media.com/kf/x.jpg" + X)]}
    out, site = build(Path(tmp) / "e", evil, {"picks--nails--dana.json": bad_feed})
    for f in site.rglob("*.html"):
        h = f.read_text(encoding="utf-8")
        assert "</script><img" not in h and "<\\/script" not in re.sub(r"<script.*?</script>", "", h, flags=re.S)
        h = re.sub(r"<script.*?</script>", "", h, flags=re.S)       # inside a script element the text is data, kept whole by json_script()
        assert "<img src=x" not in h and "onerror=1>" not in h and 'onload="1' not in h and "evil.com" not in h, f

    # answers that must not be believed: a price that is not a number, no tracking id in a kept copy, an empty answer
    for name, feed in (("price", dict(PICKS["picks--nails--dana.json"], products=[dict(pick("1005000000000001", "x"), price="18.31₪")])),
                       ("no tid", {k: v for k, v in PICKS["picks--nails--dana.json"].items() if k != "tid"}),
                       ("empty", dict(PICKS["picks--nails--dana.json"], products=[]))):
        out, site = build(Path(tmp) / f"f-{name.replace(' ', '')}", {"topics": SAMPLE["topics"], "creators": [SAMPLE["creators"][0]]},
                          {"picks--nails--dana.json": feed})
        assert not (site / "nails").exists(), name
    # a wrongly shaped file does not stop the site from being built
    for i, shape in enumerate(([], None, {"topics": ["nails"], "creators": ["x"]}, {"topics": SAMPLE["topics"], "creators": [dict(SAMPLE["creators"][0], products={"a": 1})]})):
        out, site = build(Path(tmp) / f"g{i}", shape if shape is not None else "null", {})
        assert (site / "index.html").exists() and not (site / "nails").exists(), shape

    # with no creators file: no pages, no chip, no frames allowed
    out, site = build(Path(tmp) / "b", None, {})
    home = (site / "index.html").read_text(encoding="utf-8")
    assert "סרטונים של יוצרים" not in (site / "privacy/index.html").read_text(encoding="utf-8")
    assert not (site / "nails").exists() and "frame-src" not in home and "המלצות</span>" not in home
print("OK")
