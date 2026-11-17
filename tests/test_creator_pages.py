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
        (site / "data" / "creators.json").write_text(json.dumps(creators, ensure_ascii=False), encoding="utf-8")
    for name, feed in picks.items():
        (site / "data" / name).write_text(json.dumps(feed, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, "build.py"], cwd=site, capture_output=True, text=True,
                       env={**os.environ, "BOT_FEED_URL": "off", "CF_BEACON": "off"})
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    return r.stdout, site / "_site"


SAMPLE = {"topics": [{"slug": "nails", "name": "ציפורניים", "h1": "ציפורניים: מה שאנשי מקצוע קונים", "lead": "שורת פתיחה.", "people": "היוצרות"}],
          "creators": [
              {"slug": "dana", "topic": "nails", "name": "דנה לדוגמה", "about": "בונה ציפורניים בג'ל", "tracking": "nails_dana", "videos_ok": "2026-11-19",
               "instagram": "https://www.instagram.com/dana_example/",
               "products": [
                   {"slug": "uv-lamp", "id": "1005000000000001", "name": "מנורת UV לציפורניים", "video": "https://www.instagram.com/reel/DZE-pBygPIr/",
                    "quote": "המנורה שעל השולחן", "text": ["פסקה <b>ראשונה</b> של דנה.", "פסקה שנייה."], "text_ok": "2026-11-20"},
                   {"slug": "gel", "id": "1005000000000002", "name": "לק ג'ל", "video": "https://www.youtube.com/shorts/3g_UNj5KyS8"},
                   {"slug": "drill", "id": "1005000000000003", "name": "מקדחה לציפורניים"},
                   {"slug": "gone", "id": "1005000000000004", "name": "מוצר שירד"}]},
              {"slug": "noa", "topic": "nails", "name": "נועה לדוגמה", "about": "אקריל", "tracking": "nails_noa", "videos_ok": "2026-11-19",
               "products": [{"slug": "top-coat", "id": "1005000000000009", "name": "טופ קוט", "video": "https://www.tiktok.com/@noa/video/7301234567890123456"}]},
              {"slug": "empty", "topic": "nails", "name": "בלי מוצרים חיים", "tracking": "nails_empty", "videos_ok": "2026-11-19",
               "products": [{"slug": "x", "id": "1005000000000077", "name": "אין מחיר"}]}]}
PICKS = {"picks-nails-dana.json": {"tid": "nails_dana", "updated": "2026-11-18T09:00+02:00", "products": [
             pick("1005000000000001", "מנורת ייבוש UV"), pick("1005000000000002", "לק ג'ל"), pick("1005000000000003", "מקדחה"),
             dict(pick("1005000000000004", "קישור רגיל"), link="https://www.aliexpress.com/item/1005000000000004.html")]},
         "picks-nails-noa.json": {"tid": "nails_noa", "updated": "2026-11-18T09:00+02:00", "products": [pick("1005000000000009", "טופ קוט")]},
         "picks-nails-empty.json": {"tid": "someone_else", "updated": "2026-11-18T09:00+02:00", "products": [pick("1005000000000077", "x")]}}

with tempfile.TemporaryDirectory() as tmp:
    out, site = build(Path(tmp) / "a", SAMPLE, PICKS)
    read = lambda p: (site / p / "index.html").read_text(encoding="utf-8")
    hub, dana, lamp, gel, top = read("nails"), read("nails/dana"), read("nails/dana/uv-lamp"), read("nails/dana/gel"), read("nails/noa/top-coat")
    # which pages exist: a product with neither a video nor her words has no page of its own; nothing for a creator
    # whose kept prices carry another tracking id; nothing for a product that has only a plain link
    assert not (site / "nails/dana/drill").exists() and not (site / "nails/dana/gone").exists() and not (site / "nails/empty").exists()
    assert "בלי מוצרים חיים" not in hub and "מוצר שירד" not in dana
    # the topic: both creators, each one's products under her name, the people heading from the file
    assert "דנה לדוגמה" in hub and "נועה לדוגמה" in hub and "<h2>היוצרות</h2>" in hub and 'href="/nails/dana/"' in hub
    assert hub.count("הבחירה של דנה לדוגמה") == 3 and hub.count("הבחירה של נועה לדוגמה") == 1
    # a card opens the product's own page when there is one, AliExpress (as a sponsored link) when there is not
    assert 'href="/nails/dana/uv-lamp/"' in dana and 'href="/nails/dana/gel/"' in dana
    assert f'href="{LINK}0003" rel="sponsored nofollow noopener" target="_blank"' in dana
    assert 'href="https://www.instagram.com/dana_example/"' in dana and "המנורה שעל השולחן" in dana
    # the product page: the player waits for a press, her words are escaped, the price is dated, the link is hers
    assert 'data-src="https://www.instagram.com/reel/DZE-pBygPIr/embed/"' in lamp and "<iframe" not in lamp
    assert "פסקה &lt;b&gt;ראשונה&lt;/b&gt; של דנה." in lamp and "במילים של דנה לדוגמה" in lamp
    assert lamp.count(f'href="{LINK}0001" rel="sponsored nofollow noopener"') == 2 and "נכון ל-18/11" in lamp
    assert 'data-src="https://www.youtube-nocookie.com/embed/3g_UNj5KyS8?autoplay=1&amp;rel=0"' in gel and "במילים של" not in gel
    assert gel.count(f'href="{LINK}0002" rel="sponsored nofollow noopener"') == 1
    assert 'data-src="https://www.tiktok.com/player/v1/7301234567890123456?autoplay=1&amp;rel=0"' in top
    # the disclosure is on every page, and names who is paid
    for html_, who in ((hub, None), (dana, "דנה לדוגמה"), (lamp, "דנה לדוגמה"), (top, "נועה לדוגמה")):
        assert "<b>שיתוף פעולה.</b>" in html_ and "קישורי שותפים" in html_ and (who is None or f"עובר אל {who}" in html_)
    # frames only from the three players in use; the chip leads the strip on every page; pages are in the sitemap
    home = (site / "index.html").read_text(encoding="utf-8")
    assert "frame-src https://www.instagram.com https://www.tiktok.com https://www.youtube-nocookie.com" in home
    assert home.index('href="/nails/"') < home.index('href="/c/') and "ציפורניים · המלצות" in home
    sm = (site / "sitemap.xml").read_text(encoding="utf-8")
    assert all(u in sm for u in ("/nails/</loc>", "/nails/dana/</loc>", "/nails/dana/uv-lamp/</loc>", "/nails/noa/top-coat/</loc>"))
    assert "vembed" in (site / "assets/app.js").read_text(encoding="utf-8")
    privacy = read("privacy")
    assert "סרטונים של יוצרים" in privacy and "רק אחרי שלוחצים" in privacy and all(n in privacy for n in ("יוטיוב", "אינסטגרם", "טיקטוק"))

    # with no creators file: no pages, no chip, no frames allowed
    out, site = build(Path(tmp) / "b", None, {})
    home = (site / "index.html").read_text(encoding="utf-8")
    assert "סרטונים של יוצרים" not in (site / "privacy/index.html").read_text(encoding="utf-8")
    assert not (site / "nails").exists() and "frame-src" not in home and "המלצות</span>" not in home
print("OK")
