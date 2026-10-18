"""Builds the Boten static site into _site/ from the CSV files in data/.

Run:  python build.py            (SITE_URL env sets the public address, for canonical links and the sitemap)
GitHub Actions rebuilds it on every push and once a day, so expired codes drop off by themselves.
"""
import csv
import html
import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "_site"
SITE_URL = os.environ.get("SITE_URL", "https://ozmadvil.github.io/boten-site").rstrip("/")
BASE = "/" + SITE_URL.split("://", 1)[1].split("/", 1)[1] if SITE_URL.count("/") > 2 else ""   # path prefix
BOT = "https://t.me/Boten_IL_bot"
IL = timezone(timedelta(hours=3))
NOW = datetime.now(IL)
TODAY = NOW.strftime("%d/%m/%Y")
NAME = "בוטן"

HEB_MONTHS = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"]
MONTH_YEAR = f"{HEB_MONTHS[NOW.month - 1]} {NOW.year}"
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


seller = []
for r in read_csv("seller_codes.csv"):
    r["_end"] = parse_dt(r.get("ends", ""))
    if r["_end"] and r["_end"] >= NOW:
        seller.append(r)
seller.sort(key=lambda r: -float(r["off_ils"] or 0))

platform_all = read_csv("platform_codes.csv")
for r in platform_all:
    r["_start"], r["_end"] = parse_dt(r.get("start", ""), end=False), parse_dt(r.get("end", ""))
platform_active = [r for r in platform_all
                   if r["_start"] and r["_end"] and r["_start"] <= NOW <= r["_end"] and r.get("status") != "removed"]
platform_active.sort(key=lambda r: float(r["min_usd"]))
platform_last = sorted([r for r in platform_all if r["_end"] and r["_end"] < NOW], key=lambda r: float(r["min_usd"]))
checks = sorted(read_csv("checks.csv"), key=lambda r: r["date"], reverse=True)


def bot_link(product_id: str | None = None, src: str = "site") -> str:
    return f"{BOT}?start=" + (f"p_{product_id}-{src}" if product_id else src)


# ------------------------------------------------------------------ layout
NAV = [("/", "ראשי"), ("/guides/coupon-types/", "סוגי קופונים"),
       ("/guides/code-not-working/", "קוד לא עובד?"), ("/about/", "אודות")]

ORG = {"@type": "Organization", "@id": f"{SITE_URL}/#org", "name": NAME, "alternateName": "Boten",
       "url": f"{SITE_URL}/", "logo": f"{SITE_URL}/assets/logo-192.png", "sameAs": [BOT]}


def page(path: str, title: str, description: str, body: str, crumbs: list[tuple[str, str]] | None = None,
         schema: list[dict] | None = None) -> None:
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
            f'<a href="{BASE}{p}">{e(n)}</a>' if i < len(crumbs) - 1 else e(n) for i, (p, n) in enumerate(crumbs)]
        crumb_html = f'<nav class="crumbs" aria-label="פירורי לחם">{" › ".join(parts)}</nav>'
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
<meta name="theme-color" content="#b8722c">
<link rel="icon" href="{BASE}/assets/favicon.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{BASE}/assets/style.css">
<script type="application/ld+json">{json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)}</script>
</head>
<body>
<header class="site"><div class="wrap">
<a class="logo" href="{BASE}/"><img src="{BASE}/assets/logo-192.png" alt="" width="38" height="38">{NAME}</a>
<nav class="main" aria-label="ראשי">{nav}</nav>
</div></header>
<main class="wrap">
{crumb_html}
{body}
<section class="cta-band">
<p>🥜 יש לכם מוצר מאליאקספרס? שלחו את הלינק לבוטן וקבלו מחיר, הנחה וקוד קופון אם יש.</p>
<a class="btn" href="{bot_link()}">פתחו את בוטן בטלגרם</a>
</section>
</main>
<footer class="site"><div class="wrap">
<div class="links">{"".join(f'<a href="{BASE}{p}">{n}</a>' for p, n in NAV)}<a href="{BOT}">בוטן בטלגרם</a></div>
<p>גילוי נאות: חלק מהקישורים באתר ובבוט הם קישורי שותפים של אליאקספרס. על רכישה דרכם בוטן מקבל עמלה קטנה, והמחיר שלכם לא משתנה. בוטן אינו קשור לאליאקספרס ואינו מייצג אותה. AliExpress הוא סימן מסחר של בעליו.</p>
<p>עודכן לאחרונה: {TODAY}</p>
</div></footer>
</body>
</html>
"""
    target = OUT / path.strip("/") / "index.html" if path != "/404.html" else OUT / "404.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(doc, encoding="utf-8")
    if path != "/404.html":
        SITEMAP.append(url)


SITEMAP: list[str] = []


def faq_block(items: list[tuple[str, str]]) -> tuple[str, dict]:
    html_ = "".join(f'<details class="faq"><summary>{e(q)}</summary><p>{a}</p></details>' for q, a in items)
    import re
    schema = {"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": re.sub("<[^>]+>", "", a)}}
        for q, a in items]}
    return html_, schema


# ------------------------------------------------------------------ pieces
def seller_cards(rows: list[dict], src: str) -> str:
    if not rows:
        return '<p class="lead">כרגע אין קודי מוכר מאומתים בתוקף. בוטן בודק כל מוצר שתשלחו ומחזיר קוד אם יש.</p>'
    out = []
    for r in rows:
        badge = ('<span class="pill ok">נבדק בקופה</span>' if r["verified"] == "checkout"
                 else '<span class="pill info">מפורטל השותפים הרשמי</span>')
        out.append(f"""<div class="card">
<h3>{e(r['product'])}</h3>
<p><b>₪{float(r['off_ils']):.2f} הנחה עם קוד מוכר</b> בקנייה מעל ₪{float(r['min_ils']):.2f} (אחרי הנחות)</p>
<p class="meta">{badge} · בתוקף עד {fmt_d(r['_end'], True)}</p>
{f'<p class="meta">{e(r["note"])}</p>' if r.get("note") else ''}
<p><a class="btn" href="{bot_link(r['product_id'], src)}">🥜 קבלו את הקוד והמחיר בבוטן</a></p>
</div>""")
    return f'<div class="cards">{"".join(out)}</div>'


def platform_section() -> str:
    if platform_active:
        end = min(r["_end"] for r in platform_active)
        rows = "".join(f"<tr><td><code>{e(r['code'])}</code></td><td>${float(r['off_usd']):g}</td>"
                       f"<td>מעל ${float(r['min_usd']):g}</td></tr>" for r in platform_active)
        return f"""<div class="answer"><p><b>סט קודי ישראל פעיל עד {fmt_d(end, True)}.</b> מזינים קוד אחד בלבד, לפי הסכום בסל אחרי הנחות.</p></div>
<div class="table-wrap"><table><thead><tr><th>קוד</th><th>הנחה</th><th>מינימום לסל</th></tr></thead><tbody>{rows}</tbody></table></div>"""
    last = ""
    if platform_last:
        s, t = platform_last[0]["_start"], platform_last[0]["_end"]
        rows = "".join(f"<tr><td><code>{e(r['code'])}</code></td><td>${float(r['off_usd']):g}</td>"
                       f"<td>מעל ${float(r['min_usd']):g}</td></tr>" for r in platform_last)
        last = (f"<h3>הסט האחרון (לא בתוקף)</h3><p>היה בתוקף מ-{fmt_d(s, True)} עד {fmt_d(t, True)}.</p>"
                f'<div class="table-wrap"><table><thead><tr><th>קוד</th><th>הנחה</th><th>מינימום לסל</th></tr></thead>'
                f"<tbody>{rows}</tbody></table></div>")
    return f"""<div class="answer"><p><b>נכון ל-{TODAY} אין סט רשמי פעיל של קודי פלטפורמה לישראל.</b>
אליאקספרס מוציאה סטים כאלה (ILAFF…) לקראת אירועי מבצעים, לחלון של כשבוע. אנחנו מפרסמים סט רק כשיש לו תאריכי תוקף רשמיים.</p></div>
{last}"""


def checks_table() -> str:
    if not checks:
        return ""
    items = "".join(
        f'<div class="card check"><p class="meta">{datetime.strptime(r["date"], "%Y-%m-%d").strftime("%d/%m/%Y")} · '
        f'<code>{e(r["code"])}</code> · <span class="pill {"ok" if r["result"] == "עובד" else "bad"}">{e(r["result"])}</span></p>'
        f'<p>{e(r["details"])}</p></div>'
        for r in checks)
    return f'<div class="checks">{items}</div>'


# ------------------------------------------------------------------ pages
def build_home():
    body = f"""<section class="hero">
<div>
<h1>קודי קופון לאליאקספרס שבאמת עובדים, ובוט שבודק כל מוצר בשבילכם</h1>
<p class="lead">בוטן הוא בוט טלגרם חינמי: שולחים לו לינק של מוצר מאליאקספרס ומקבלים את המחיר בשקלים, ההנחה וקוד הקופון של המוכר, אם יש.</p>
<div class="actions"><a class="btn" href="{bot_link(src='home')}">🥜 בדקו מוצר עם בוטן</a>
<a class="btn ghost" href="{BASE}/guides/coupon-types/">איך משלבים קופונים</a></div>
</div>
<img src="{BASE}/assets/logo.png" alt="הלוגו של בוטן" width="150" height="150">
</section>
<h2>דילים עם קוד הנחה השבוע</h2>
{seller_cards(seller[:4], 'home')}
<h2>איך בוטן עובד</h2>
<ol class="steps">
<li><b>פותחים מוצר באליאקספרס</b> ולוחצים "שיתוף" ← "העתק קישור".</li>
<li><b>מדביקים את הלינק לבוטן</b> בטלגרם ושולחים.</li>
<li><b>מקבלים מחיר, הנחה וקוד</b> אם יש, ואם אין קופון, בוטן מציע לחפש חלופה זולה יותר.</li>
</ol>
<h2>למה לסמוך על הקודים כאן</h2>
<p>רוב אתרי הקופונים מעתיקים רשימות קודים בלי לבדוק אותן. בוטן מושך את הקודים ישירות מאליאקספרס לכל מוצר שתשלחו, ואנחנו בודקים אותם בקופה אמיתית.</p>
"""
    page("/", f"{NAME}: קודי קופון לאליאקספרס שנבדקו + בוט שבודק כל מוצר",
         "קודי קופון לאליאקספרס בישראל שנבדקו בקופה, עם תאריך. ובוט טלגרם חינמי שמחזיר לכל מוצר מחיר בשקלים, הנחה וקוד מוכר.",
         body)


def build_coupon_types():
    body = f"""<h1>סוגי הקופונים באליאקספרס ואיך משלבים אותם</h1>
<p><span class="updated">עודכן: {TODAY}</span></p>
<div class="answer"><p><b>בקצרה:</b> באליאקספרס יש ארבעה סוגי הנחות: קוד קופון שמקלידים בקופה, קופון חנות, קופוני Select ומטבעות.
קוד אחד בלבד נכנס לשדה Promo code, ושאר ההנחות נאספות בלחיצה ומצטרפות אליו.</p></div>
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
<div class="table-wrap"><table><thead><tr><th>שילוב</th><th>מצב</th></tr></thead><tbody>
<tr><td>קוד קופון + קופון חנות + מטבעות</td><td><span class="pill ok">אפשר</span></td></tr>
<tr><td>שני קודי ישראל (ILAFF) באותה הזמנה</td><td><span class="pill bad">לא: קוד פלטפורמה אחד להזמנה</span></td></tr>
<tr><td>קוד מוכר + קוד ישראל</td><td><span class="pill info">עוד לא אימתנו בקופה</span></td></tr>
</tbody></table></div>
<h2>טיפ: המינימום נבדק אחרי ההנחות</h2>
<p>בבדיקה שלנו סוללה ב-₪93.50 ירדה בסל ל-₪77.68 אחרי הנחות אוטומטיות, ולכן קוד עם מינימום ₪126.55 נדחה. עם שתי יחידות הסל עבר את המינימום והקוד נכנס.</p>
"""
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
    rows = "".join(f'<h3>{e(he)}</h3><p dir="ltr" style="text-align:left"><code>{e(en)}</code></p><p>{e(fix)}</p>'
                   for en, he, fix in items)
    body = f"""<h1>למה קוד הקופון לא עובד באליאקספרס? (עם הודעות השגיאה האמיתיות)</h1>
<p><span class="updated">עודכן: {TODAY}</span></p>
<div class="answer"><p><b>שלוש הסיבות הנפוצות:</b> הסל מתחת למינימום (שנבדק אחרי ההנחות), המכסה של הקוד נגמרה, או שהקוד לא בתוקף.
את ההודעות הבאות קיבלנו בעצמנו בקופה, ב-18/10/2026.</p></div>
{rows}
<h2>עוד דברים לבדוק</h2>
<ul>
<li><b>כתובת משלוח בישראל:</b> קודי ישראל (ILAFF) עובדים רק במשלוח לישראל.</li>
<li><b>קוד אחד בשדה:</b> מזינים קוד אחד ב-Promo code. אם יש כמה מדרגות, בוחרים לפי הסכום בסל.</li>
<li><b>קוד מוכר:</b> עובד רק על מוצרים של אותו מוכר.</li>
</ul>
"""
    page("/guides/code-not-working/", f"קוד קופון לא עובד באליאקספרס? 3 סיבות והפתרון | {NAME}",
         "הודעות השגיאה האמיתיות מהקופה של אליאקספרס, מה כל אחת אומרת ומה עושים: מינימום אחרי הנחות, מכסה שנגמרה, קוד לא תקף.",
         body, crumbs=[("/guides/code-not-working/", "קוד קופון לא עובד")],
         schema=[{"@type": "Article", "headline": "למה קוד הקופון לא עובד באליאקספרס", "inLanguage": "he-IL",
                  "dateModified": NOW.date().isoformat(), "author": {"@id": f"{SITE_URL}/#org"},
                  "publisher": {"@id": f"{SITE_URL}/#org"}}])


def build_about():
    body = f"""<h1>אודות בוטן</h1>
<p>בוטן הוא בוט טלגרם חינמי ואתר שעוזרים לקנות באליאקספרס בפחות: הבוט בודק כל מוצר שמדביקים לו ומחזיר מחיר בשקלים, הנחה וקוד מוכר אם יש, ומציע חלופות זולות יותר. באתר אנחנו מפרסמים רק קודים שנבדקו, עם תאריך, ומתעדים גם קודים שלא עבדו.</p>
<h2>גילוי נאות</h2>
<p>הקישורים לאליאקספרס בבוט ובאתר הם קישורי שותפים. על רכישה דרכם בוטן מקבל עמלה קטנה מאליאקספרס, והמחיר שלכם לא משתנה. בוטן אינו קשור לאליאקספרס ואינו מייצג אותה.</p>
<h2>פרטיות</h2>
<p>הבוט לא שומר מידע אישי ולא שולח הודעות שלא ביקשתם. האתר לא משתמש בעוגיות מעקב.</p>
<h2>יצירת קשר</h2>
<p>דרך <a href="{BOT}">הבוט בטלגרם</a>.</p>
"""
    page("/about/", f"אודות {NAME} וגילוי נאות", "מי אנחנו, איך בוטן עובד, גילוי נאות על קישורי שותפים ופרטיות.",
         body, crumbs=[("/about/", "אודות")])


def build_404():
    page("/404.html", f"הדף לא נמצא | {NAME}", "הדף לא נמצא",
         f'<h1>הדף לא נמצא 🥜</h1><p><a href="{BASE}/">לדף הראשי</a></p>')


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
