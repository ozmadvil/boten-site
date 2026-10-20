"""Builds the Boten static site into _site/ from the CSV files in data/.

Run:  python build.py            (SITE_URL env sets the public address, for canonical links and the sitemap)
GitHub Actions rebuilds it on every push and once a day, so expired codes drop off by themselves.
Design system: see DESIGN.md (the weekly sale flyer).
"""
import csv
import html
import json
import os
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "_site"
SITE_URL = os.environ.get("SITE_URL", "https://ozmadvil.github.io/boten-site").rstrip("/")
BASE = "/" + SITE_URL.split("://", 1)[1].split("/", 1)[1] if SITE_URL.count("/") > 2 else ""   # path prefix
BOT = "https://t.me/Boten_IL_bot"
CHANNEL = "https://t.me/Boten_deals"
IL = timezone(timedelta(hours=3))
NOW = datetime.now(IL)
TODAY = NOW.strftime("%d/%m/%Y")
HEB_MONTHS = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"]
MONTH_YEAR = f"{HEB_MONTHS[NOW.month - 1]} {NOW.year}"
NAME = "בוטן"
e = html.escape


# ------------------------------------------------------------------ data
def read_csv(name: str) -> list[dict]:
    path = ROOT / "data" / name
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(l for l in f if l.strip() and not l.lstrip().startswith("#")))


def parse_dt(s: str, end: bool = True) -> datetime | None:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            d = datetime.strptime(s, fmt)
            if fmt == "%Y-%m-%d" and end:
                d = d.replace(hour=23, minute=59)
            return d.replace(tzinfo=IL)
        except ValueError:
            pass
    return None


def fmt_d(d: datetime | None, with_time: bool = False) -> str:
    if not d:
        return ""
    return d.strftime("%d/%m %H:%M" if with_time else "%d/%m/%Y")


def num(s) -> float | None:
    try:
        return float(str(s).strip())
    except (TypeError, ValueError):
        return None


seller = []
for r in read_csv("seller_codes.csv"):
    r["_end"] = parse_dt(r.get("ends", ""))
    if r["_end"] and r["_end"] >= NOW:
        seller.append(r)
seller.sort(key=lambda r: -float(r["off_ils"] or 0))
SELLER_CODES = {r["code"] for r in read_csv("seller_codes.csv")}   # never printed on the site

platform_all = read_csv("platform_codes.csv")
for r in platform_all:
    r["_start"], r["_end"] = parse_dt(r.get("start", ""), end=False), parse_dt(r.get("end", ""))
platform_active = [r for r in platform_all
                   if r["_start"] and r["_end"] and r["_start"] <= NOW <= r["_end"] and r.get("status") != "removed"]
platform_active.sort(key=lambda r: float(r["min_usd"]))
checks = sorted(read_csv("checks.csv"), key=lambda r: r["date"], reverse=True)

# Channel deals for the product tiles. The bot snapshots every product it posts to @Boten_deals and serves the
# list at BOT_FEED_URL; data/products.json is the fallback (and the last good copy when building locally).
BOT_FEED_URL = os.environ.get("BOT_FEED_URL", "https://worker-production-b0bb.up.railway.app/products.json")


def load_products() -> list[dict]:
    import urllib.request
    cache = ROOT / "data" / "products.json"
    data = None
    if BOT_FEED_URL and os.environ.get("BOT_FEED_URL", "x") != "off":
        try:
            with urllib.request.urlopen(BOT_FEED_URL, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
            cache.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as ex:
            print(f"products feed unavailable ({ex}); using {cache.name}")
    if data is None and cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
    out = []
    for p in (data or {}).get("products", []):
        if p.get("title") and p.get("image") and p.get("link", "").startswith("https://") and p.get("price"):
            out.append(p)
    return out[:12]


products = load_products()

# Product categories (the "קטגוריות" menu). Names and order come from the bot (site_categories.txt there);
# data/categories_menu.json keeps the menu alive when the feed is unreachable.
BOT_CATS_URL = os.environ.get("BOT_CATS_URL") or BOT_FEED_URL.replace("/products.json", "/categories.json")


def load_categories() -> list[dict]:
    import urllib.request
    cache, menu = ROOT / "data" / "categories.json", ROOT / "data" / "categories_menu.json"
    data = None
    if os.environ.get("BOT_FEED_URL", "x") != "off":
        try:
            with urllib.request.urlopen(BOT_CATS_URL, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
            cache.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as ex:
            print(f"categories feed unavailable ({ex})")
    if data is None and cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
    if data is None and menu.exists():
        data = json.loads(menu.read_text(encoding="utf-8"))
    cats = []
    for c in (data or {}).get("categories", []):
        if not re.fullmatch(r"[a-z0-9-]+", c.get("slug", "")) or not c.get("name"):
            continue
        prods = [p for p in c.get("products", []) if p.get("title") and p.get("image")
                 and str(p.get("link", "")).startswith("https://") and p.get("price")]
        cats.append({"slug": c["slug"], "name": c["name"], "products": prods})
    return cats


categories = load_categories()


def bot_link(product_id: str | None = None, src: str = "site") -> str:
    return f"{BOT}?start=" + (f"p_{product_id}-{src}" if product_id else src)


# ------------------------------------------------------------------ small parts
ICON_TG = ('<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" '
           'stroke-linecap="round" stroke-linejoin="round"><path d="M21 4 3 11l6 2.4M21 4l-3.5 16L9 13.4M21 4 9 13.4v5.3l3-3"/></svg>')
ICON_ARROW = ('<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.4" '
              'stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5m6-6-6 6 6 6"/></svg>')
ICON_CHECK = ('<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="3" '
              'stroke-linecap="round" stroke-linejoin="round"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>')
ICON_X = ('<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="3" '
          'stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>')
ICON_SCISSORS = ('<svg class="scissors" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" '
                 'stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/>'
                 '<path d="M8.6 7.6 20 18M8.6 16.4 20 6"/></svg>')


def price(v: float, cls: str = "") -> str:
    """₪145⁸⁸ — the flyer's price: big shekels, raised agorot."""
    whole, ag = f"{v:.2f}".split(".")
    ag_html = f'<span class="ag">{ag}</span>' if ag != "00" else ""
    return (f'<span class="price {cls}" aria-label="{v:.2f} שקלים"><span class="cur" aria-hidden="true">₪</span>'
            f'<span aria-hidden="true">{whole}</span>{ag_html.replace("<span", "<span aria-hidden=\"true\"", 1)}</span>')


def checker(src: str, field_id: str = "link") -> str:
    """The price checker: paste a product link, land in the bot on that product. Works without JS (opens the bot)."""
    return f"""<form class="checker" action="{BOT}" method="get" data-bot="{BOT}" data-src="{src}" novalidate>
<label for="{field_id}">בודק מחירים: הדביקו לינק של מוצר מאליאקספרס</label>
<input type="hidden" name="start" value="{src}">
<div class="row">
<input id="{field_id}" type="url" inputmode="url" autocomplete="off" spellcheck="false" placeholder="https://aliexpress.com/item/…" aria-describedby="{field_id}-msg">
<button class="btn" type="submit">{ICON_TG}<span>בדקו בבוטן</span></button>
</div>
<p class="msg" id="{field_id}-msg" role="status" aria-live="polite">בוטן מחזיר מחיר בשקלים, הנחה וקוד קופון אם יש. בחינם.</p>
<p class="tip">💡 בתשובה של בוטן לחצו על <b class="btn-name">🔍 מצא מוכר זול יותר</b>, והוא יחפש את אותו מוצר אצל מוכרים אחרים.</p>
<p class="also">📢 דילים חדשים כל יום: <a href="{CHANNEL}">הצטרפו לערוץ הדילים של בוטן בטלגרם</a></p>
</form>"""


CHECKER_JS = r"""<script>
document.querySelectorAll('form.checker').forEach(function (f) {
  var input = f.querySelector('input[type=url]'), btn = f.querySelector('button'), msg = f.querySelector('.msg');
  var idle = msg.textContent, label = btn.querySelector('span').textContent;
  var bot = f.dataset.bot, src = f.dataset.src;
  function say(t, err) { msg.textContent = t; msg.classList.toggle('err', !!err); }
  input.addEventListener('input', function () { if (msg.classList.contains('err')) say(idle); });
  f.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var v = input.value.trim();
    if (!v) { say('הדביקו קודם לינק של מוצר מאליאקספרס.', true); input.focus(); return; }
    if (!/aliexpress|aliexpi|s\.click\.ali|\d{13,}/i.test(v)) {
      say('זה לא נראה כמו לינק מאליאקספרס. באפליקציה: שיתוף ← העתק קישור.', true); input.focus(); return;
    }
    var m = v.match(/(?:\/item\/|productIds?=|[?&]id=|\/i\/)(\d{10,20})/) || v.match(/(\d{13,20})/);
    btn.setAttribute('aria-busy', 'true'); btn.querySelector('span').textContent = 'בודק…';
    var tag = document.querySelector('.proof .tag'), ts = tag && tag.querySelector('.strip span');
    if (tag && ts) { tag.classList.remove('checking'); void tag.offsetWidth; tag.classList.add('checking'); ts.textContent = 'בודק את הלינק שלכם…'; }
    function go(url) { window.location.href = url; setTimeout(function () { btn.removeAttribute('aria-busy'); btn.querySelector('span').textContent = label; if (tag && ts) { tag.classList.remove('checking'); ts.textContent = ts.dataset.idle; } }, 2500); }
    if (m) { say('פותח את בוטן על המוצר הזה…'); go(bot + '?start=p_' + m[1] + '-' + src); return; }
    var done = function () { say('הלינק הועתק. בטלגרם הדביקו אותו לבוטן ושלחו.'); setTimeout(function () { go(bot + '?start=' + src); }, 900); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(v).then(done, done); else done();
  });
});
</script>"""


# ------------------------------------------------------------------ layout
NAV = [("/", "ראשי"), ("/coupons/", "קודי קופון"), ("/guides/", "מדריכים"), ("/guides/11-11/", "11.11"), ("/guides/black-friday/", "בלאק פריידי"),
       ("/guides/code-not-working/", "קוד לא עובד?"), ("/about/", "אודות")]

ORG = {"@type": "Organization", "@id": f"{SITE_URL}/#org", "name": NAME, "alternateName": "Boten",
       "url": f"{SITE_URL}/", "logo": f"{SITE_URL}/assets/logo-192.png", "sameAs": [BOT, CHANNEL]}

SITEMAP: list[str] = []


def page(path: str, title: str, description: str, body: str, crumbs: list[tuple[str, str]] | None = None,
         schema: list[dict] | None = None, full: bool = False, js: bool = False) -> None:
    """full=True: body brings its own full-bleed sections. Otherwise it is a reading page, wrapped and closed with the bot invite."""
    url = SITE_URL + path
    graph = [ORG, {"@type": "WebSite", "@id": f"{SITE_URL}/#site", "url": f"{SITE_URL}/", "name": NAME,
                   "inLanguage": "he-IL", "publisher": {"@id": f"{SITE_URL}/#org"}}]
    if crumbs:
        items = [("/", "ראשי")] + crumbs
        graph.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i, "name": n, "item": SITE_URL + p} for i, (p, n) in enumerate(items, 1)]})
    graph += schema or []
    nav = "".join(f'<a href="{BASE}{p}"{" aria-current=\"page\"" if p == path else ""}>{n}</a>' for p, n in NAV)
    strip = ""
    if categories:                             # the category chips under the menu, on every page
        chips = "".join(
            f'<a class="chip" href="{BASE}/c/{c["slug"]}/"'
            f'{" aria-current=\"page\"" if path == "/c/" + c["slug"] + "/" else ""}>{e(c["name"])}</a>'
            for c in categories)
        strip = f'<nav class="cats-strip" aria-label="קטגוריות"><div class="wrap">{chips}</div></nav>'
    menubar = f'<nav class="menubar" aria-label="ראשי"><div class="wrap">{nav}</div></nav>' + strip
    if full and "<!--MENUBAR-->" in body:          # home: the menu sits right under the yellow band
        body, menubar_top = body.replace("<!--MENUBAR-->", menubar), ""
    else:                                      # every other page gets the same yellow band on top
        menubar_top = hero("page", False) + menubar
        js = True
    crumb_html = ""
    if crumbs:
        parts = [f'<a href="{BASE}/">ראשי</a>'] + [
            f'<a href="{BASE}{p}">{e(n)}</a>' if i < len(crumbs) - 1 else f'<span aria-current="page">{e(n)}</span>'
            for i, (p, n) in enumerate(crumbs)]
        crumb_html = f'<nav class="crumbs" aria-label="פירורי לחם">{" › ".join(parts)}</nav>'
    if not full:
        body = f"""<div class="wrap">
{crumb_html}
{body}
<aside class="cta-inline"><p>יש לכם מוצר מאליאקספרס? שלחו את הלינק לבוטן וקבלו מחיר, הנחה וקוד קופון אם יש.</p>
<a class="btn" href="{bot_link(src='guide')}">{ICON_TG}פתחו את בוטן</a><a class="btn secondary" href="{CHANNEL}">📢 לערוץ הדילים</a></aside>
</div>"""
    doc = f"""<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:locale" content="he_IL">
<meta property="og:site_name" content="{NAME}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE_URL}/assets/logo.png">
<meta name="theme-color" content="#d8001a">
<link rel="icon" href="{BASE}/assets/favicon.png">
<link rel="preload" href="{BASE}/assets/fonts/rubik-hebrew-900-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{BASE}/assets/fonts/rubik-hebrew-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{BASE}/assets/style.css">
<script type="application/ld+json">{json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)}</script>
</head>
<body>
<a class="skip" href="#main">דלגו לתוכן</a>
<header class="site"><div class="wrap">
<a class="logo" href="{BASE}/"><img src="{BASE}/assets/logo-192.png" alt="" width="40" height="40">{NAME}</a>
<a class="tg" href="{bot_link(src='nav')}">{ICON_TG}פתחו את בוטן</a>
<a class="tg ch" href="{CHANNEL}" aria-label="ערוץ הדילים בטלגרם">📢 <span class="long">ערוץ הדילים</span><span class="short">ערוץ</span></a>
</div></header>
{menubar_top}
<main id="main">
{body}
</main>
<footer class="site"><div class="wrap">
<div class="links">{"".join(f'<a href="{BASE}{p}">{n}</a>' for p, n in NAV)}<a href="{BOT}">בוטן בטלגרם</a><a href="{CHANNEL}">ערוץ הדילים</a></div>
<p>* גילוי נאות: חלק מהקישורים באתר ובבוט הם קישורי שותפים של אליאקספרס. על רכישה דרכם בוטן מקבל עמלה קטנה, והמחיר שלכם לא משתנה.</p>
<p>* בוטן אינו קשור לאליאקספרס ואינו מייצג אותה. AliExpress הוא סימן מסחר של בעליו. המחירים וההנחות נכונים ליום הבדיקה בלבד.</p>
<p>עודכן לאחרונה: {TODAY}</p>
</div></footer>
{CHECKER_JS if js else ""}
</body>
</html>
"""
    target = OUT / path.strip("/") / "index.html" if path != "/404.html" else OUT / "404.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(doc, encoding="utf-8")
    if path != "/404.html":
        SITEMAP.append(url)


def faq_block(items: list[tuple[str, str]]) -> tuple[str, dict]:
    html_ = "".join(f'<details class="faq"><summary>{e(q)}</summary><p>{a}</p></details>' for q, a in items)
    schema = {"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": re.sub("<[^>]+>", "", a)}}
        for q, a in items]}
    return html_, schema


# ------------------------------------------------------------------ pieces
def hero_tag() -> str:
    """The shelf tag in the hero: the latest real checkout check that has full numbers."""
    for r in checks:
        cart, auto, code = num(r.get("cart_ils")), num(r.get("auto_off_ils")), num(r.get("code_off_ils"))
        if r.get("result") == "עובד" and cart and code is not None:
            auto = auto or 0
            final = cart - auto - code
            d = datetime.strptime(r["date"], "%Y-%m-%d")
            units = r.get("units") or ""
            name = e(r.get("product") or "")
            unit_txt = f" · {units} יח׳" if units and units != "1" else ""
            return f"""<div class="tag" role="figure" aria-label="דוגמה לבדיקה בקופה">
<div class="strip"><span data-idle="מבצע אמיתי">מבצע אמיתי</span><span>נבדק {d.strftime('%d/%m')}</span></div>
<div class="body">
<p class="name"><bdi>{name}</bdi><span class="nowrap">{unit_txt}</span></p>
<ul class="lines">
<li><span>סל לפני הנחות</span><span class="num was">₪{cart:.2f}</span></li>
<li><span>הנחות אוטומטיות</span><span class="num minus">‎-₪{auto:.2f}</span></li>
<li><span>קוד מוכר מבוטן</span><span class="num minus">‎-₪{code:.2f}</span></li>
</ul>
{price(final, "now")}
<p class="fine">המחיר בקופה אחרי הקוד, בלי משלוח. נבדק {d.strftime('%d/%m/%Y')}.</p>
</div>
<div class="stamp" aria-hidden="true">נבדק<small>בקופה</small></div>
</div>"""
    return f'<img src="{BASE}/assets/logo.png" alt="הלוגו של בוטן" width="300" height="300">'


def coupons(rows: list[dict], src: str) -> str:
    if not rows:
        return ('<div class="empty"><p><b>כרגע אין קודי מוכר מאומתים בתוקף.</b> בוטן בודק כל מוצר שתשלחו ומחזיר קוד אם יש.</p>'
                f'<a class="btn" href="{bot_link(src=src)}">{ICON_TG}בדקו מוצר בבוטן</a> '
                f'<a class="btn secondary" href="{CHANNEL}">📢 לערוץ הדילים</a></div>')
    out = []
    for r in rows:
        badge = (f'<span class="sticker ok">{ICON_CHECK}נבדק בקופה</span>' if r["verified"] == "checkout"
                 else '<span class="sticker info">מפורטל השותפים הרשמי</span>')
        note = f'<p class="fine">{e(r["note"])}</p>' if r.get("note") else ""
        out.append(f"""<article class="coupon">
<div class="strip">הנחה עם קוד מוכר</div>
<div class="inner">
{price(float(r['off_ils']), "off")}
<h3>{e(r['product'])}</h3>
<p class="fine">בקנייה מעל <b>₪{float(r['min_ils']):.2f}</b> (אחרי הנחות) · בתוקף עד {fmt_d(r['_end'], True)}</p>
<p>{badge}</p>
{note}
<a class="go" href="{bot_link(r['product_id'], src)}">קבלו את הקוד והמחיר בבוטן {ICON_ARROW}</a>
</div>
<span class="cut" aria-hidden="true">{ICON_SCISSORS}גזור ושמור</span>
</article>""")
    return f'<div class="deals">{"".join(out)}</div>'


def checks_log() -> str:
    """Dated shelf tags of real checkout checks. Codes are never printed, working or not."""
    if not checks:
        return ""
    items = []
    for r in checks:
        ok = r["result"] == "עובד"
        c, details = r["code"], r["details"]
        if c in SELLER_CODES:
            what = "קוד מוכר (נשלח בבוטן)"
        elif "בלוג" in details:
            what = "קוד שפורסם בבלוג קופונים"
        elif c.upper().startswith("IL"):
            what = "קוד פלטפורמה לישראל"
        else:
            what = "קוד קופון"
        details = details.replace(c, "הקוד")
        if what == "קוד שפורסם בבלוג קופונים":   # the label already says where it came from
            details = details.replace("קוד שפורסם בבלוג קופונים ", "")
        parts = re.split(r'("[^"]+")', details)   # English error messages stay intact inside Hebrew text
        details_html = "".join(f'<bdi lang="en">{e(x)}</bdi>' if x.startswith('"') else e(x) for x in parts)
        d = datetime.strptime(r["date"], "%Y-%m-%d")
        icon = ICON_CHECK if ok else ICON_X
        items.append(f'<li><div class="strip {"ok" if ok else "bad"}"><span>{icon} {"עובד" if ok else "לא עובד"}</span>'
                     f'<time datetime="{r["date"]}">{d.strftime("%d/%m/%Y")}</time></div>'
                     f'<p class="what">{e(what)}</p><p>{details_html}</p></li>')
    return f'<ul class="log">{"".join(items)}</ul>'


def product_tiles(rows: list[dict]) -> str:
    """Channel deals as flyer tiles. A tile is one link straight to AliExpress (affiliate)."""
    tiles = []
    for p in rows:
        price_v, orig, disc = float(p["price"]), p.get("original"), p.get("discount")
        was = f'<span class="was">₪{float(orig):.2f}</span>' if orig and float(orig) > price_v + 0.5 else ""
        burst = f'<span class="burst" aria-label="הנחה {disc:.0f}%">-{disc:.0f}%</span>' if disc and disc >= 5 else ""
        cat = f'<span class="cat">{e(p["category"])}</span>' if p.get("category") else ""
        if p.get("pick"):
            cat = '<span class="cat pick">בחירה של בוטן</span>'
        tiles.append(f"""<li><a class="tile" href="{e(p['link'])}" rel="sponsored nofollow noopener" target="_blank">
<span class="pic"><img src="{e(p['image'])}" alt="" width="300" height="300" loading="lazy" decoding="async" referrerpolicy="no-referrer"></span>
{burst}
<span class="tprice">{price(price_v)}{was}</span>
<span class="ttl">{e(p['title'])}</span>
{cat}
</a></li>""")
    return f'<ul class="tiles">{"".join(tiles)}</ul>'


# ------------------------------------------------------------------ pages
def hero(src: str, main_heading: bool) -> str:
    """The yellow band with the price checker. On the home page its title is the page's h1; elsewhere the page
    keeps its own h1, so the band's title is a styled paragraph (one h1 per page)."""
    tag = "h1" if main_heading else "p"
    return f"""<section class="hero" aria-labelledby="hero-title"><div class="wrap">
<div>
<{tag} id="hero-title" class="hero-title">דילים מאליאקספרס <em>שבאמת שווים</em></{tag}>
<p class="lead">כל מוצר כאן עבר סינון של בוטן: דירוג גבוה, הרבה מכירות, מחיר בשקלים. ויש לכם מוצר משלכם? הדביקו אותו כאן.</p>
</div>
{checker(src)}
</div></section>"""


def build_home():
    body = f"""{hero('home', True)}
<!--MENUBAR-->

<div class="wrap">
{f'''<section aria-labelledby="hot-title">
<div class="sec-head"><h2 id="hot-title">הדילים של השבוע</h2><a href="{CHANNEL}">כל הדילים בערוץ {ICON_ARROW}</a></div>
{product_tiles(products)}
<p class="tiles-note">המחירים נכונים לשעת הפרסום בערוץ ועשויים להשתנות. לחיצה על מוצר פותחת אותו באליאקספרס (קישור שותפים: המחיר שלכם לא משתנה).</p>
</section>''' if products else ""}


<section aria-labelledby="deals-title">
<h2 id="deals-title">קודי מוכר שנבדקו</h2>
<p class="lead">קודי מוכר שנבדקו, עם תאריך. את הקוד עצמו מקבלים בבוטן, יחד עם המחיר המעודכן.</p>
{coupons(seller[:4], 'home')}
</section>

<section aria-labelledby="how-title">
<h2 id="how-title">איך בוטן עובד</h2>
<ol class="how">
<li><span class="n" aria-hidden="true">1</span><b>מעתיקים לינק</b><p>באפליקציה של אליאקספרס: שיתוף ← העתק קישור.</p></li>
<li><span class="n" aria-hidden="true">2</span><b>שולחים לבוטן</b><p>מדביקים בצ'אט עם בוטן בטלגרם, או בבודק המחירים למעלה.</p></li>
<li><span class="n" aria-hidden="true">3</span><b>מקבלים מחיר וקוד</b><p>ואם אין קופון, בוטן מציע לחפש חלופה זולה יותר.</p></li>
</ol>
</section>

<section aria-labelledby="guides-title">
<div class="sec-head"><h2 id="guides-title">לפני שקונים</h2><a href="{BASE}/guides/">כל המדריכים {ICON_ARROW}</a></div>
<ul class="guide-list">
<li><a class="guide-card" href="{BASE}/guides/11-11/"><b>יום הרווקים 11.11: תאריכים וקופונים</b><span>מתי זה מתחיל בשעון ישראל ואיך משלבים קודים.</span></a></li>
<li><a class="guide-card" href="{BASE}/guides/customs-tax/"><b>מכס ומע"מ: הפטור הוא 75 דולר</b><span>מה משלמים, מתי, ומה זה כלל 72 השעות.</span></a></li>
<li><a class="guide-card" href="{BASE}/guides/shipping-israel/"><b>משלוח לישראל: חינם מ-139 ש"ח</b><span>כמה זמן לוקח ומה עושים כשהמעקב נתקע.</span></a></li>
</ul>
</section>

<section aria-labelledby="log-title" class="proof">
<div class="proof-text">
<h2 id="log-title">יומן הבדיקות</h2>
<p class="lead">רוב אתרי הקופונים מעתיקים רשימות בלי לבדוק. אנחנו בודקים בקופה, ומתעדים גם מה שלא עבד.</p>
</div>
<div class="tag-slot">{hero_tag()}</div>
{checks_log()}
</section>
</div>

<section class="closer" aria-labelledby="closer-title"><div class="wrap">
<div><h2 id="closer-title">יש לכם לינק? בוטן בודק.</h2>
<p>חינם, בטלגרם, בלי הרשמה. והדילים הכי טובים של השבוע מחכים בערוץ.</p></div>
<div class="actions"><a class="btn" href="{bot_link(src='closer')}">{ICON_TG}פתחו את בוטן</a>
<a class="btn secondary" href="{CHANNEL}">לערוץ הדילים</a></div>
</div></section>"""
    page("/", f"{NAME}: קודי קופון לאליאקספרס שנבדקו + בוט שבודק כל מוצר",
         "קודי קופון לאליאקספרס בישראל שנבדקו בקופה, עם תאריך. ובוט טלגרם חינמי שמחזיר לכל מוצר מחיר בשקלים, הנחה וקוד מוכר.",
         body, full=True, js=True)


# ------------------------------------------------------------------ the coupon codes page (/coupons/)
def _links() -> dict:
    """Affiliate links made by the bot (data/site_links.json): {"home": url, "products": {product_id: url}}."""
    try:
        return json.loads((ROOT / "data" / "site_links.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def build_coupons_page():
    links = _links()
    home_link = links.get("home")
    prod_links = links.get("products", {})
    buy = (f'<a class="btn" href="{e(home_link)}" rel="sponsored nofollow noopener" target="_blank">🛒 לקנייה באליאקספרס</a>'
           if home_link else "")
    bot_btn = f'<a class="btn secondary" href="{bot_link(src="coupons")}">{ICON_TG}בדקו מוצר בבוטן</a>'

    # --- verified seller codes (codes printed, with a buy link to that product)
    rows = ""
    for r in seller:
        status = ("✅ עובד (נבדק בקופה " + datetime.strptime(r["checked"], "%Y-%m-%d").strftime("%d/%m") + ")"
                  if r["verified"] == "checkout" else "מפורטל השותפים הרשמי של אליאקספרס")
        link = prod_links.get(r["product_id"])
        go = (f'<a href="{e(link)}" rel="sponsored nofollow noopener" target="_blank">למוצר ←</a>' if link
              else f'<a href="{bot_link(r["product_id"], "coupons")}">למוצר בבוטן ←</a>')
        rows += (f"<tr><td data-l=\"קוד\"><code class=\"code\">{e(r['code'])}</code></td><td data-l=\"מוצר\">{e(r['product'])}</td>"
                 f"<td data-l=\"הנחה\">₪{float(r['off_ils']):.2f}</td><td data-l=\"מינימום\">מעל ₪{float(r['min_ils']):.2f}</td>"
                 f"<td data-l=\"בתוקף עד\">{fmt_d(r['_end'], True)}</td><td data-l=\"סטטוס\">{status}</td><td>{go}</td></tr>")
    seller_html = (f"""<div class="table-wrap"><table class="codes cards"><thead><tr><th>קוד</th><th>מוצר</th><th>הנחה</th>
<th>מינימום לסל (אחרי הנחות)</th><th>בתוקף עד</th><th>סטטוס</th><th></th></tr></thead><tbody>{rows}</tbody></table></div>"""
                   if rows else '<p>כרגע אין קודי מוכר מאומתים בתוקף. בוטן בודק כל מוצר שתשלחו ומחזיר קוד אם יש.</p>')

    # --- Israel platform codes (ILAFF): active set, or the last one
    if platform_active:
        end = min(r["_end"] for r in platform_active)
        prow = "".join(f"<tr><td><code class=\"code\">{e(r['code'])}</code></td><td>${float(r['off_usd']):g}</td>"
                       f"<td>מעל ${float(r['min_usd']):g}</td></tr>" for r in platform_active)
        platform_html = (f"<p><b>סט קודי ישראל פעיל עד {fmt_d(end, True)}.</b> מזינים קוד אחד, לפי הסכום בסל אחרי הנחות.</p>"
                         f'<div class="table-wrap"><table class="codes"><thead><tr><th>קוד</th><th>הנחה</th><th>מינימום לסל</th>'
                         f"</tr></thead><tbody>{prow}</tbody></table></div>")
        answer_now = f"יש סט פעיל של קודי ישראל (ILAFF) עד {fmt_d(end, True)}, ראו בטבלה."
    else:
        last = sorted([r for r in platform_all if r["_end"] and r["_end"] < NOW], key=lambda r: float(r["min_usd"]))
        prow = "".join(f"<tr><td><code class=\"code bad\">{e(r['code'])}</code></td><td>${float(r['off_usd']):g}</td>"
                       f"<td>מעל ${float(r['min_usd']):g}</td><td>❌ פג תוקף</td></tr>" for r in last)
        when = (f"מ-{fmt_d(last[0]['_start'], True)} עד {fmt_d(last[0]['_end'], True)}" if last else "")
        platform_html = ("<p>אליאקספרס מוציאה סט קודים לישראל (ILAFF…) לקראת אירועי מבצע, לחלון של כשבוע. "
                         "אנחנו מפרסמים סט רק כשיש לו חלון תוקף רשמי, ומעדכנים כאן ביום שהוא יוצא.</p>"
                         + (f"<p>הסט האחרון היה בתוקף {when}:</p>"
                            f'<div class="table-wrap"><table class="codes"><thead><tr><th>קוד</th><th>הנחה</th><th>מינימום לסל</th>'
                            f"<th>סטטוס</th></tr></thead><tbody>{prow}</tbody></table></div>" if prow else ""))
        answer_now = "אין כרגע סט רשמי פעיל של קודי ישראל (ILAFF). הסט הבא צפוי לקראת 11.11."

    # --- codes that circulate on coupon sites, with what we actually know about each (sorted by cart size)
    circ = sorted(read_csv("circulating_codes.csv"), key=lambda r: float(r["min_usd"] or 0))
    crow = ""
    for r in circ:
        if r["status"] == "failed":
            d = datetime.strptime(r["checked"], "%Y-%m-%d").strftime("%d/%m")
            parts = re.split(r'("[^"]+")', r["details"])
            det = "".join(f'<bdi lang="en">{e(x)}</bdi>' if x.startswith('"') else e(x) for x in parts)
            st, cls = f"❌ נכשל בבדיקה שלנו ({d}): {det}", "code bad"
        else:
            st, cls = "⚠️ לא נבדק: נסו בקופה, ייתכן שהמכסה נגמרה", "code"
        crow += (f"<tr><td data-l=\"מינימום לסל\">מעל ${float(r['min_usd']):g}</td><td data-l=\"הנחה\">${float(r['off_usd']):g}</td>"
                 f"<td data-l=\"קוד\"><code class=\"{cls}\">{e(r['code'])}</code></td>"
                 f"<td data-l=\"מה ידוע\">{e(r['claimed'])}. {st}</td></tr>")
    bad_html = (f"""<h2 id="not-working">הקודים שמסתובבים באתרי קופונים ({MONTH_YEAR}), ומה המצב שלהם</h2>
<p>אלה הקודים שאתרי קופונים ישראליים (וגם ChatGPT, שמצטט אותם) מציגים החודש. לא מצאנו לסט ILAFFOCT מקור רשמי של אליאקספרס או חלון תוקף רשמי.
מה שבדקנו בקופה אמיתית עם משלוח לישראל מסומן, וכך גם מה שלא הספקנו לבדוק. בוחרים את המדרגה הגבוהה ביותר שהסל עובר אחרי ההנחות.</p>
<div class="table-wrap"><table class="codes cards"><thead><tr><th>מינימום לסל</th><th>הנחה</th><th>קוד</th><th>מה ידוע</th></tr></thead>
<tbody>{crow}</tbody></table></div>""" if crow else "")

    seller_now = (", ".join(f"{r['code']} (₪{float(r['off_ils']):.2f} הנחה מעל ₪{float(r['min_ils']):.2f})" for r in seller)
                  if seller else "")
    faq_html, faq_schema = faq_block([
        ("יש עכשיו קוד קופון לאליאקספרס שעובד בישראל?",
         f"{answer_now} "
         + f"לכל מוצר אחר אפשר לשלוח את הלינק <a href=\"{bot_link(src='faq')}\">לבוטן</a>, והוא מחזיר קוד מוכר אם יש."),
        ("הקודים ILAFFOCT01–ILAFFOCT010 עובדים?",
         "ILAFFOCT01 (‏$3 מעל $29) נכשל בבדיקה שלנו בקופה ב-18/10: \"used up by other shoppers\", כלומר המכסה נגמרה. "
         "את שאר המדרגות לא בדקנו, כי הן דורשות סל גדול (מעל $59). לא מצאנו לסט הזה מקור רשמי של אליאקספרס. אפשר לנסות, "
         "ואם הקוד נדחה, כנראה שגם המכסה שלו נגמרה."),
        ("יש הטבה למשתמש חדש באליאקספרס?",
         "בדרך כלל כן: לחשבון חדש אליאקספרס מציעה הטבות פתיחה באפליקציה, שמופיעות אוטומטית בחשבון אחרי ההרשמה. "
         "הן משתנות ותלויות בחשבון, ולכן אין להן קוד קבוע שאפשר לפרסם."),
        ("האם הקודים בדף הזה נבדקו?",
         "קודי המוכר מסומנים לפי המקור: נבדק בקופה, או מופיע בפורטל השותפים הרשמי של אליאקספרס. בטבלת הקודים שמסתובבים ברשת "
         "כתוב ליד כל קוד אם בדקנו אותו ומה קרה. אנחנו לא מסמנים קוד כ\"עובד\" בלי בדיקה."),
        ("למה הקוד לא עובד לי בקופה?",
         "שלוש סיבות כמעט תמיד: הסל מתחת למינימום, המכסה של הקוד נגמרה, או שהקוד פג תוקף. "
         f'<a href="{BASE}/guides/code-not-working/">הודעות השגיאה המדויקות ומה עושים ←</a>'),
        ("המינימום נבדק לפני או אחרי ההנחות?",
         "אחרי. בדקנו: סוללה ב-₪93.50 ירדה בסל ל-₪77.68 אחרי ההנחות האוטומטיות, ולכן קוד עם מינימום ₪126.55 נדחה. "
         "עם שתי יחידות הסל עבר את המינימום והקוד נכנס."),
        ("כמה קודים אפשר להזין בהזמנה אחת?",
         "בשדה Promo code נכנס קוד אחד. קופוני חנות שאוספים בדף המוצר, קופוני Select ומטבעות מצטרפים אליו. "
         "אם אפשר לשלב קוד מוכר עם קוד ישראל (ILAFF) באותה הזמנה עוד לא אימתנו בעצמנו."),
        ("מה ההבדל בין קוד מוכר לקוד ישראל (ILAFF)?",
         "קוד מוכר עובד רק על המוצרים של אותו מוכר. קוד ישראל הוא קוד של אליאקספרס שעובד על כל הסל, במדרגות לפי הסכום, "
         "ורק במשלוח לישראל."),
        ("למה באתרים אחרים יש הרבה יותר קודים?",
         "כי הם מעתיקים רשימות בלי לבדוק. חלק מהקודים שמופיעים שם בדקנו בקופה, והם נגמרו או לא תקפים "
         "(ראו את הטבלה \"קודים שלא עובדים\"). אנחנו מפרסמים רק מה שנבדק או שמופיע בפורטל הרשמי של אליאקספרס."),
        ("מתי יוצאים קודים חדשים?",
         f'סביב אירועי מבצע: 11.11, בלאק פריידי (27/11), 12.12 והמבצע של סוף השנה. <a href="{BASE}/guides/11-11/">מה צפוי ב-11.11 ←</a> · <a href="{BASE}/guides/black-friday/">בלאק פריידי ←</a>'),
        ("איך מקבלים קוד למוצר מסוים?",
         f'שולחים את הלינק של המוצר <a href="{bot_link(src="faq")}">לבוטן בטלגרם</a>. הוא בודק את המוצר ומחזיר מחיר בשקלים, '
         "הנחה וקוד מוכר אם יש, ואם אין, מחפש מוכר זול יותר."),
    ])
    body = f"""<header class="page-head"><h1>קודי קופון לאליאקספרס בישראל ({MONTH_YEAR}): רק קודים שנבדקו בקופה</h1>
<span class="updated">עודכן: {TODAY} · ליד כל קוד מופיע מתי נבדק</span></header>
<div class="answer"><p><b>בקצרה, נכון ל-{TODAY}:</b> {answer_now}
הסט ILAFFOCT שמופיע באתרי קופונים עם תוקף "עד 31/10": הקוד הראשון (ILAFFOCT01) נגמר בבדיקה שלנו, ואת השאר לא הצלחנו לאמת, <a href="#not-working">פירוט בטבלה</a>.</p></div>
<p class="actions">{buy}{bot_btn}</p>
<h2>קודי ישראל של אליאקספרס (ILAFF)</h2>
{platform_html}
{bad_html}
<h2>איך בוחרים קוד ומזינים אותו</h2>
<p>מוסיפים לסל, נכנסים לתשלום, ובשדה Promo code מדביקים את הקוד ולוחצים Apply. מזינים קוד אחד. אם יש כמה מדרגות,
בוחרים את הגבוהה ביותר שהסל עובר אחרי ההנחות. מחיר המשלוח לא נספר למינימום. ההנחה מופיעה רק אחרי Apply.</p>
<p>לפני שמזינים קוד, כדאי לאסוף בדף המוצר את קופוני החנות ("קבלו קופונים"). הם מצטרפים לקוד ולא תופסים את מקומו.</p>
<h2>שאלות נפוצות</h2>
{faq_html}
<p class="fine">* הקישורים בדף הם קישורי שותפים של אליאקספרס. הקודים והתוקף נכונים ליום הבדיקה בלבד, וקודים עלולים להיגמר במכסה לפני התאריך.</p>"""
    page("/coupons/", f"קודי קופון לאליאקספרס ({MONTH_YEAR}): רק קודים שנבדקו בקופה | {NAME}",
         f"קודי קופון לאליאקספרס בישראל, {MONTH_YEAR}: קודי מוכר שנבדקו בקופה, קודי ישראל (ILAFF) עם תוקף, "
         "ורשימת קודים שמסתובבים ברשת ולא עובדים. מתעדכן כל יום.",
         body, crumbs=[("/coupons/", "קודי קופון")], schema=[faq_schema])


def build_coupon_types():
    body = f"""<header class="page-head"><h1>סוגי הקופונים באליאקספרס ואיך משלבים אותם</h1>
<span class="updated">עודכן: {TODAY}</span></header>
<div class="answer"><p><b>בקצרה:</b> באליאקספרס יש ארבעה סוגי הנחות: קוד קופון שמקלידים בקופה, קופון חנות, קופוני Select ומטבעות.
קוד אחד בלבד נכנס לשדה Promo code, ושאר ההנחות נאספות בלחיצה ומצטרפות אליו.</p></div>
<div class="prose">
<h2>1. קוד קופון (Promo code)</h2>
<p>קוד שמקלידים בקופה, בשדה Promo code. יש שני סוגים:</p>
<ul>
<li><b>קוד מוכר</b>: עובד רק על המוצרים של מוכר מסוים. לדוגמה: ₪12.65 הנחה בקנייה מעל ₪126.55 על סוללה של Essager. את הקוד למוצר מסוים מקבלים בבוטן.</li>
<li><b>קוד פלטפורמה לישראל</b> (ILAFF…): עובד על כל הסל, במדרגות לפי סכום, ורק במשלוח לישראל. יוצא לחלון של כשבוע סביב אירועי מבצעים, ולכל קוד יש מכסה.</li>
</ul>
<h2>2. קופון חנות</h2>
<p>הנחה שהמוכר נותן, ומופיעה בדף המוצר (בדרך כלל בכתום, "קבלו קופונים"). לא מקלידים אותה: לוחצים לאסוף, והיא מוחלת בקופה.</p>
<h2>3. קופוני Select</h2>
<p>קופונים של אליאקספרס לאירועי מבצע, שעובדים על מוצרים מסומנים. אוספים אותם בדפי המבצע, והם בתוקף רק עד סוף המבצע.</p>
<h2>4. מטבעות (Coins)</h2>
<p>נאספים באפליקציה (צ'ק-אין יומי, משחקים) ומורידים אחוז קטן מהמחיר במוצרים שמשתתפים.</p>
<h2>מה אפשר לשלב באותה הזמנה?</h2>
</div>
<div class="table-wrap"><table><thead><tr><th>שילוב</th><th>מצב</th></tr></thead><tbody>
<tr><td>קוד קופון + קופון חנות + מטבעות</td><td><span class="sticker ok">{ICON_CHECK}אפשר</span></td></tr>
<tr><td>שני קודי ישראל (ILAFF) באותה הזמנה</td><td><span class="sticker bad">{ICON_X}לא: קוד פלטפורמה אחד להזמנה</span></td></tr>
<tr><td>קוד מוכר + קוד ישראל</td><td><span class="sticker info">עוד לא אימתנו בקופה</span></td></tr>
</tbody></table></div>
<div class="prose">
<h2>טיפ: המינימום נבדק אחרי ההנחות</h2>
<p>בבדיקה שלנו סוללה ב-₪93.50 ירדה בסל ל-₪77.68 אחרי הנחות אוטומטיות, ולכן קוד עם מינימום ₪126.55 נדחה. עם שתי יחידות הסל עבר את המינימום והקוד נכנס.</p>
</div>"""
    page("/guides/coupon-types/", f"סוגי קופונים באליאקספרס ואיך משלבים אותם | {NAME}",
         "קוד קופון, קופון חנות, קופוני Select ומטבעות: מה ההבדל, מה אפשר לשלב באותה הזמנה, ולמה המינימום נבדק אחרי ההנחות.",
         body, crumbs=[("/guides/", "מדריכים"), ("/guides/coupon-types/", "סוגי קופונים")],
         schema=[{"@type": "Article", "headline": "סוגי הקופונים באליאקספרס ואיך משלבים אותם", "inLanguage": "he-IL",
                  "dateModified": NOW.date().isoformat(), "author": {"@id": f"{SITE_URL}/#org"},
                  "publisher": {"@id": f"{SITE_URL}/#org"}}])


def build_not_working():
    items = [
        ("The eligible items total after discounts (excluding shipping) is below the minimum for this coupon.",
         "הסל מתחת למינימום של הקוד.",
         "המינימום נבדק על הסל אחרי כל ההנחות, בלי משלוח. מוסיפים עוד מוצר או יחידה, או בוחרים קוד עם מינימום נמוך יותר."),
        ("Sorry, the coupon code you entered is based on a first come first served basis and has been used up by other shoppers.",
         "המכסה של הקוד נגמרה.",
         "לקודים יש מספר שימושים מוגבל, והמדרגות הנמוכות נגמרות ראשונות. אין מה לעשות מלבד קוד אחר."),
        ("Sorry, this code can't be applied. It may be incorrect, inactive, or already used.",
         "הקוד שגוי, לא פעיל או שכבר השתמשתם בו.",
         "בדרך כלל זה קוד שפג תוקפו או קוד שהועתק מבלוג בלי תאריכים. בודקים שהקוד הועתק בדיוק (אותיות גדולות, בלי רווחים)."),
    ]
    rows = "".join(f'<h3>{e(he)}</h3><p class="error-msg" lang="en">{e(en)}</p><p>{e(fix)}</p>'
                   for en, he, fix in items)
    body = f"""<header class="page-head"><h1>למה קוד הקופון לא עובד באליאקספרס?</h1>
<span class="updated">עודכן: {TODAY} · עם הודעות השגיאה האמיתיות מהקופה</span></header>
<div class="answer"><p><b>שלוש הסיבות הנפוצות:</b> הסל מתחת למינימום (שנבדק אחרי ההנחות), המכסה של הקוד נגמרה, או שהקוד לא בתוקף.
את ההודעות הבאות קיבלנו בעצמנו בקופה, ב-18/10/2026.</p></div>
<div class="prose">
<h2>שלוש הודעות השגיאה ומה עושים</h2>
{rows}
<h2>עוד דברים לבדוק</h2>
<ul>
<li><b>כתובת משלוח בישראל:</b> קודי ישראל (ILAFF) עובדים רק במשלוח לישראל.</li>
<li><b>קוד אחד בשדה:</b> מזינים קוד אחד ב-Promo code. אם יש כמה מדרגות, בוחרים לפי הסכום בסל.</li>
<li><b>קוד מוכר:</b> עובד רק על מוצרים של אותו מוכר.</li>
</ul>
</div>"""
    page("/guides/code-not-working/", f"קוד קופון לא עובד באליאקספרס? 3 סיבות והפתרון | {NAME}",
         "הודעות השגיאה האמיתיות מהקופה של אליאקספרס, מה כל אחת אומרת ומה עושים: מינימום אחרי הנחות, מכסה שנגמרה, קוד לא תקף.",
         body, crumbs=[("/guides/", "מדריכים"), ("/guides/code-not-working/", "קוד קופון לא עובד")],
         schema=[{"@type": "Article", "headline": "למה קוד הקופון לא עובד באליאקספרס", "inLanguage": "he-IL",
                  "dateModified": NOW.date().isoformat(), "author": {"@id": f"{SITE_URL}/#org"},
                  "publisher": {"@id": f"{SITE_URL}/#org"}}])


def build_guides():
    """Guide pages from guides_content.py, plus the guides hub."""
    from guides_content import GUIDES
    for g in GUIDES:
        url = f"/guides/{g['slug']}/"
        body_html = g["body"].replace("{BASE}", BASE).replace("{BOT}", BOT)
        faq_html, faq_schema = faq_block(g.get("faq") or [])
        upd = datetime.strptime(g["updated"], "%Y-%m-%d")
        tiles = ""
        if g.get("products") and products:
            keys = g["products"]
            rows = products if keys == ["*"] else [p for p in products if any(k in p["title"] for k in keys)]
            if rows:
                tiles = (f'<h2>דילים מהערוץ</h2>{product_tiles(rows[:8])}'
                         '<p class="tiles-note">המחירים נכונים לשעת הפרסום בערוץ. קישורי שותפים: המחיר שלכם לא משתנה.</p>')
        srcs = ""
        if g.get("sources"):
            srcs = ('<h2>מקורות</h2><ul class="sources">' + "".join(
                f'<li><a href="{e(u)}" rel="noopener">{e(t)}</a></li>' for t, u in g["sources"]) + "</ul>")
        faq_section = f"<h2>שאלות נפוצות</h2>{faq_html}" if faq_html else ""
        body = f"""<header class="page-head"><h1>{e(g['h1'])}</h1>
<span class="updated">עודכן: {upd.strftime('%d/%m/%Y')}</span></header>
<div class="answer"><p>{g['answer']}</p></div>
<div class="prose">
{body_html}
{tiles}
{faq_section}
{srcs}
</div>"""
        schema = [{"@type": "Article", "headline": g["h1"], "inLanguage": "he-IL", "description": g["desc"],
                   "dateModified": g["updated"], "author": {"@id": f"{SITE_URL}/#org"},
                   "publisher": {"@id": f"{SITE_URL}/#org"}, "mainEntityOfPage": SITE_URL + url}]
        if faq_html:
            schema.append(faq_schema)
        page(url, g["title"], g["desc"], body, crumbs=[("/guides/", "מדריכים"), (url, g["nav"])], schema=schema)

    # hub
    groups = [
        ("מבצעים", ["11-11", "sales-calendar"]),
        ("מיסים, משלוח ואישורים", ["customs-tax", "shipping-israel", "wireless-approval", "dispute-refund"]),
        ("קופונים", ["coupon-types", "code-not-working"]),
        ("מוצרים", ["popular-products", "jump-starter"]),
    ]
    by_slug = {g["slug"]: (g["h1"], g["desc"]) for g in GUIDES}
    by_slug["coupon-types"] = ("סוגי הקופונים באליאקספרס ואיך משלבים אותם",
                               "קוד קופון, קופון חנות, Select ומטבעות: מה ההבדל ומה מצטרף למה.")
    by_slug["code-not-working"] = ("למה קוד הקופון לא עובד?", "הודעות השגיאה האמיתיות מהקופה ומה עושים בכל אחת.")
    sections = ""
    for name, slugs in groups:
        cards = "".join(f'<li><a class="guide-card" href="{BASE}/guides/{sl}/"><b>{e(by_slug[sl][0])}</b>'
                        f'<span>{e(by_slug[sl][1])}</span></a></li>' for sl in slugs if sl in by_slug)
        sections += f'<h2>{name}</h2><ul class="guide-list">{cards}</ul>'
    body = f"""<header class="page-head"><h1>מדריכים לקנייה חכמה באליאקספרס</h1>
<span class="updated">עודכן: {TODAY} · כל מה שצריך לדעת לפני שקונים מחו"ל</span></header>
{sections}"""
    page("/guides/", f"מדריכים לקנייה באליאקספרס: מבצעים, מכס, משלוח וקופונים | {NAME}",
         "מדריכים בעברית לקונים באליאקספרס: מתי המבצעים, כמה מס משלמים, כמה זמן לוקח משלוח, אישור משרד התקשורת, החזרים וקופונים.",
         body, crumbs=[("/guides/", "מדריכים")])


def build_categories():
    """A page per product category: Boten's picks first, then the automatic best deals."""
    for c in categories:
        url = f"/c/{c['slug']}/"
        others = "".join(f'<a class="chip" href="{BASE}/c/{o["slug"]}/">{e(o["name"])}</a>'
                         for o in categories if o["slug"] != c["slug"])
        if c["products"]:
            grid = (product_tiles(c["products"][:24]) +
                    '<p class="tiles-note">בוטן בוחר לכל קטגוריה את הדילים הכי שווים לפי מחיר, הנחה, דירוג ומכירות, '
                    'ומעדכן אותם כמה פעמים ביום. המחירים עשויים להשתנות. לחיצה פותחת את המוצר באליאקספרס '
                    '(קישור שותפים: המחיר שלכם לא משתנה).</p>')
        else:
            grid = ('<div class="empty"><p><b>בוטן עוד מחפש את הדילים לקטגוריה הזו.</b> בינתיים אפשר לשלוח לו לינק '
                    'של כל מוצר ולקבל מחיר, הנחה וקוד אם יש.</p>'
                    f'<a class="btn" href="{bot_link(src="cat")}">{ICON_TG}בדקו מוצר בבוטן</a> '
                    f'<a class="btn secondary" href="{CHANNEL}">📢 לערוץ הדילים</a></div>')
        body = f"""<header class="page-head"><h1>{e(c['name'])} מאליאקספרס: הדילים של השבוע</h1>
<span class="updated">עודכן: {TODAY} · מחיר בשקלים, עם הנחה ודירוג</span></header>
{grid}"""
        items = [{"@type": "ListItem", "position": i, "url": p["link"], "name": p["title"]}
                 for i, p in enumerate(c["products"][:24], 1)]
        schema = [{"@type": "CollectionPage", "name": f"{c['name']} מאליאקספרס", "inLanguage": "he-IL",
                   "mainEntity": {"@type": "ItemList", "itemListElement": items}}] if items else []
        page(url, f"{c['name']} מאליאקספרס: דילים והנחות בשקלים | {NAME}",
             f"הדילים הכי שווים ב{c['name']} מאליאקספרס, שבוטן בחר לפי מחיר, הנחה, דירוג ומכירות. מחיר בשקלים, מתעדכן כמה פעמים ביום.",
             body, crumbs=[(url, c["name"])], schema=schema)
        if not c["products"] and SITE_URL + url in SITEMAP:   # no thin pages in the sitemap
            SITEMAP.remove(SITE_URL + url)


def build_about():
    body = f"""<header class="page-head"><h1>אודות בוטן</h1></header>
<div class="prose">
<p class="lead">בוטן הוא בוט טלגרם חינמי ואתר שעוזרים לקנות באליאקספרס בפחות.</p>
<p>הבוט בודק כל מוצר שמדביקים לו ומחזיר מחיר בשקלים, הנחה וקוד מוכר אם יש, ומציע חלופות זולות יותר. באתר אנחנו מפרסמים רק מה שנבדק, עם תאריך, ומתעדים גם קודים שלא עבדו.</p>
<h2>גילוי נאות</h2>
<p>הקישורים לאליאקספרס בבוט ובאתר הם קישורי שותפים. על רכישה דרכם בוטן מקבל עמלה קטנה מאליאקספרס, והמחיר שלכם לא משתנה. בוטן אינו קשור לאליאקספרס ואינו מייצג אותה.</p>
<h2>פרטיות</h2>
<p>הבוט לא שומר מידע אישי ולא שולח הודעות שלא ביקשתם. האתר לא משתמש בעוגיות מעקב.</p>
<h2>יצירת קשר</h2>
<p>דרך <a href="{BOT}">הבוט בטלגרם</a>. דילים חדשים מתפרסמים ב<a href="{CHANNEL}">ערוץ הדילים</a>.</p>
</div>"""
    page("/about/", f"אודות {NAME} וגילוי נאות", "מי אנחנו, איך בוטן עובד, גילוי נאות על קישורי שותפים ופרטיות.",
         body, crumbs=[("/about/", "אודות")])


def build_404():
    body = f"""<div class="notfound">
<span class="price now" aria-hidden="true">404</span>
<h1>המבצע הזה כבר נגמר</h1>
<p class="lead">הדף שחיפשתם לא קיים, או שהוסר. אבל בוטן עדיין בודק כל מוצר.</p>
<p><a class="btn" href="{BASE}/">לדף הראשי</a></p>
</div>"""
    page("/404.html", f"הדף לא נמצא | {NAME}", "הדף לא נמצא", body)


def build_meta_files():
    (OUT / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\n"
        "# AI search engines are welcome (citations in ChatGPT, Perplexity, Claude, Copilot)\n"
        "User-agent: OAI-SearchBot\nAllow: /\n\nUser-agent: ChatGPT-User\nAllow: /\n\n"
        "User-agent: PerplexityBot\nAllow: /\n\nUser-agent: Claude-SearchBot\nAllow: /\n\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    today = NOW.date().isoformat()
    urls = "".join(f"<url><loc>{u}</loc><lastmod>{today}</lastmod></url>" for u in SITEMAP)
    (OUT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
        encoding="utf-8")
    (OUT / "llms.txt").write_text(
        f"# {NAME} (Boten)\n\n> קודי קופון לאליאקספרס בישראל שנבדקו בקופה, ובוט טלגרם חינמי (@Boten_IL_bot) שבודק כל מוצר.\n\n"
        f"- [סוגי קופונים ושילובים]({SITE_URL}/guides/coupon-types/)\n"
        f"- [קוד קופון לא עובד]({SITE_URL}/guides/code-not-working/): הודעות השגיאה האמיתיות ופתרונות\n"
        + "".join(f"- [{g['h1']}]({SITE_URL}/guides/{g['slug']}/)\n" for g in __import__("guides_content").GUIDES),
        encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    cname = os.environ.get("CNAME")
    if cname:
        (OUT / "CNAME").write_text(cname, encoding="utf-8")


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / "assets", OUT / "assets")
    for f in ROOT.glob("google*.html"):           # Google Search Console verification file
        shutil.copy(f, OUT / f.name)
    build_home(); build_coupons_page(); build_coupon_types(); build_not_working(); build_guides(); build_categories(); build_about(); build_404()
    build_meta_files()
    print(f"built {len(SITEMAP)} pages into {OUT} (base={BASE or '/'}), {len(seller)} seller codes, "
          f"{len(platform_active)} platform codes active")


if __name__ == "__main__":
    main()
