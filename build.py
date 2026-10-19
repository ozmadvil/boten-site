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
NAV = [("/", "ראשי"), ("/guides/coupon-types/", "סוגי קופונים"),
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
<a class="btn" href="{bot_link(src='guide')}">{ICON_TG}פתחו את בוטן</a></aside>
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
<nav class="main" aria-label="ראשי">{nav}<a class="tg" href="{bot_link(src='nav')}">{ICON_TG}לבוט</a></nav>
</div></header>
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
                f'<a class="btn" href="{bot_link(src=src)}">{ICON_TG}בדקו מוצר בבוטן</a></div>')
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
        tiles.append(f"""<li><a class="tile" href="{e(p['link'])}" rel="sponsored nofollow noopener" target="_blank">
<span class="pic"><img src="{e(p['image'])}" alt="" width="300" height="300" loading="lazy" decoding="async" referrerpolicy="no-referrer"></span>
{burst}
<span class="tprice">{price(price_v)}{was}</span>
<span class="ttl">{e(p['title'])}</span>
{cat}
</a></li>""")
    return f'<ul class="tiles">{"".join(tiles)}</ul>'


# ------------------------------------------------------------------ pages
def build_home():
    body = f"""<section class="hero" aria-labelledby="hero-title"><div class="wrap">
<div>
<h1 id="hero-title">דילים מאליאקספרס <em>שבאמת שווים</em></h1>
<p class="lead">כל מוצר כאן עבר סינון של בוטן: דירוג גבוה, הרבה מכירות, מחיר בשקלים. ויש לכם מוצר משלכם? הדביקו אותו כאן.</p>
</div>
{checker('home')}
</div></section>

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
         body, crumbs=[("/guides/coupon-types/", "סוגי קופונים")],
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
         body, crumbs=[("/guides/code-not-working/", "קוד קופון לא עובד")],
         schema=[{"@type": "Article", "headline": "למה קוד הקופון לא עובד באליאקספרס", "inLanguage": "he-IL",
                  "dateModified": NOW.date().isoformat(), "author": {"@id": f"{SITE_URL}/#org"},
                  "publisher": {"@id": f"{SITE_URL}/#org"}}])


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
        f"- [קוד קופון לא עובד]({SITE_URL}/guides/code-not-working/): הודעות השגיאה האמיתיות ופתרונות\n",
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
    build_home(); build_coupon_types(); build_not_working(); build_about(); build_404()
    build_meta_files()
    print(f"built {len(SITEMAP)} pages into {OUT} (base={BASE or '/'}), {len(seller)} seller codes, "
          f"{len(platform_active)} platform codes active")


if __name__ == "__main__":
    main()
