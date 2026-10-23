"""Builds the Boten static site into _site/ from the CSV files in data/.

Run:  python build.py            (SITE_URL env sets the public address, for canonical links and the sitemap)
GitHub Actions rebuilds it on every push and every hour, so expired codes and past sale events drop off by themselves.
Design system: see DESIGN.md (the weekly sale flyer).

Dates are honest: every page carries the date its content last changed (footer, sitemap lastmod, dateModified),
never just the build time. Every link into the bot carries the page and the place it came from (see src_for).
"""
import csv
import html
import json
import os
import re
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "_site"
SITE_URL = os.environ.get("SITE_URL", "https://ozmadvil.github.io/boten-site").rstrip("/")
BASE = "/" + SITE_URL.split("://", 1)[1].split("/", 1)[1] if SITE_URL.count("/") > 2 else ""   # path prefix
BOT = "https://t.me/Boten_IL_bot"
CHANNEL = "https://t.me/Boten_deals"
try:                                      # Israel time with daylight saving (winter time from the last Sunday of October)
    from zoneinfo import ZoneInfo
    IL = ZoneInfo("Asia/Jerusalem")
except Exception:                         # no tz database: fixed summer offset, as before
    IL = timezone(timedelta(hours=3))
NOW = datetime.now(IL)
if os.environ.get("BUILD_NOW"):          # preview the site as it will look on a date: BUILD_NOW="2026-11-20 10:00"
    NOW = datetime.fromisoformat(os.environ["BUILD_NOW"]).replace(tzinfo=IL)
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
    """A date for the page. With the time it is isolated left to right, so Hebrew text around it doesn't flip it
    into "09:59 29/10"."""
    if not d:
        return ""
    if with_time:
        return f'<bdi dir="ltr">{d.strftime("%d/%m %H:%M")}</bdi>'
    return d.strftime("%d/%m/%Y")


def iso_dt(s) -> datetime | None:
    """A timestamp from the bot's feeds ("2026-10-21T10:00+03:00"), in Israel time."""
    try:
        d = datetime.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None
    return (d if d.tzinfo else d.replace(tzinfo=IL)).astimezone(IL)


def latest(*values) -> date | None:
    """The newest date among datetimes, dates and date strings, ignoring blanks and anything in the future."""
    out = None
    for v in values:
        if isinstance(v, str):
            v = iso_dt(v) or parse_dt(v, end=False)
        if isinstance(v, datetime):
            if v > NOW:
                continue
            v = v.astimezone(IL).date()
        if isinstance(v, date) and v <= NOW.date() and (out is None or v > out):
            out = v
    return out


# Every link into the bot says where it came from: a place letter + the page, letters and digits only, at most
# 20 characters (the bot's /start parser: _START_RE in boten-bot/bot.py). Example: "hgcustomstax" = the price
# checker on the customs guide. The bot counts them as start_<src> in insights.
PLACES = {"hero": "h", "nav": "n", "inline": "i", "empty": "e", "faq": "f", "closer": "c", "deal": "d", "code": "k",
          "footer": "b", "actions": "a"}


def page_key(path: str) -> str:
    parts = [p for p in path.strip("/").split("/") if p]
    if not parts:
        return "home"
    if parts[0] == "guides" and len(parts) > 1:
        return "g" + re.sub(r"[^a-z0-9]", "", parts[1])
    if parts[0] == "c" and len(parts) > 1:
        return "c" + re.sub(r"[^a-z0-9]", "", parts[1])
    return re.sub(r"[^a-z0-9]", "", parts[0].replace(".html", "")) or "home"


def src_for(place: str, path: str) -> str:
    return (PLACES[place] + page_key(path))[:20]


def short_title(t: str, limit: int = 56) -> str:
    """AliExpress's own titles run long ("UGREEN תג חכם Bluetooth Tracker, מוצא מפתחות…"): keep the part before
    the first separator, or cut at a word."""
    t = re.sub(r"\s+", " ", str(t or "")).strip()
    if len(t) <= limit:
        return t
    for sep in (",", "،", "|", " - ", " – ", "(", "/"):
        i = t.find(sep)
        if 12 <= i <= limit:
            return t[:i].strip()
    cut = t.rfind(" ", 0, limit)
    return (t[:cut] if cut > 20 else t[:limit]).rstrip(" ,-–") + "…"


def clean_cat(s: str) -> str:
    """The channel's collection name without its emoji ("🎒 לטיולים" → "לטיולים")."""
    return re.sub(r"^[^\w₪]+", "", str(s or "")).strip()


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

for r in checks:
    r["_date"] = parse_dt(r.get("date", ""), end=False)


def _show_until(r: dict) -> datetime | None:
    """A circulating code stays on the page until the validity the coupon sites claim, or 45 days after our check."""
    until = parse_dt(r.get("show_until", ""))
    if until:
        return until
    checked = parse_dt(r.get("checked", ""))
    return checked + timedelta(days=45) if checked else None


circulating_all = read_csv("circulating_codes.csv")
circulating = sorted([r for r in circulating_all if not _show_until(r) or _show_until(r) >= NOW],
                     key=lambda r: float(r["min_usd"] or 0))

# Sale events (data/events.csv): the menu items, the first "before you buy" card and "the next event" are built from
# them, so 11.11 leaves the menu on its own once it is over.
events = []
for r in read_csv("events.csv"):
    r["_from"], r["_start"], r["_end"] = (parse_dt(r.get("show_from", ""), end=False),
                                          parse_dt(r.get("start", ""), end=False), parse_dt(r.get("end", "")))
    if r["_start"] and r["_end"]:
        events.append(r)
events.sort(key=lambda r: r["_start"])
events_live = [r for r in events if r["_end"] >= NOW]                       # running or still to come
events_menu = [r for r in events_live if r.get("guide") and r.get("nav") and r["_from"] and r["_from"] <= NOW][:2]

# The bot's feeds: channel deals (product tiles) and the product categories. Order of trust: the bot itself →
# the copy this site published on its last build (so a bot restart during the hourly build doesn't empty the
# site) → the local cache. A published copy older than FEED_MAX_AGE is not used: no tiles beat stale tiles.
BOT_FEED_URL = os.environ.get("BOT_FEED_URL", "https://worker-production-b0bb.up.railway.app/products.json")
BOT_CATS_URL = os.environ.get("BOT_CATS_URL") or BOT_FEED_URL.replace("/products.json", "/categories.json")
SEARCH_URL = os.environ.get("SEARCH_URL") or BOT_FEED_URL.replace("/products.json", "/search")   # live product search
FEED_MAX_AGE = timedelta(hours=72)
FEEDS: dict[str, dict] = {}                 # what this build used, republished under /feed/


def load_feed(name: str, bot_url: str, key: str) -> dict | None:
    import urllib.request
    cache = ROOT / "data" / name
    if os.environ.get("BOT_FEED_URL", "x") != "off":
        for label, url in (("bot", bot_url), ("last build", f"{SITE_URL}/feed/{name}")):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "boten-site-build"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = json.loads(r.read().decode("utf-8"))
                if not isinstance(data, dict) or not isinstance(data.get(key), list):
                    raise ValueError(f"no '{key}' list")
                served = iso_dt(data.get("updated"))
                if label != "bot" and (not served or NOW - served > FEED_MAX_AGE):
                    raise ValueError(f"copy too old ({data.get('updated')})")
                cache.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"{name}: from the {label}")
                FEEDS[name] = data
                return data
            except Exception as ex:
                print(f"{name}: {label} unavailable ({ex})")
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
        print(f"{name}: from the local cache")
        FEEDS[name] = data
        return data
    return None


def _usable(p: dict) -> bool:
    return bool(p.get("title") and p.get("image") and str(p.get("link", "")).startswith("https://") and p.get("price"))


products = [p for p in (load_feed("products.json", BOT_FEED_URL, "products") or {}).get("products", []) if _usable(p)][:12]


def load_categories() -> list[dict]:
    """The "קטגוריות" chips. Names and order come from the bot (site_categories.txt there);
    data/categories_menu.json keeps the menu alive when no feed is reachable."""
    data = load_feed("categories.json", BOT_CATS_URL, "categories")
    menu = ROOT / "data" / "categories_menu.json"
    if data is None and menu.exists():
        data = json.loads(menu.read_text(encoding="utf-8"))
    cats = []
    for c in (data or {}).get("categories", []):
        if not re.fullmatch(r"[a-z0-9-]+", c.get("slug", "")) or not c.get("name"):
            continue
        cats.append({"slug": c["slug"], "name": c["name"], "updated": c.get("updated"),
                     "products": [p for p in c.get("products", []) if _usable(p)]})
    return cats


categories = load_categories()
try:
    INTROS = json.loads((ROOT / "data" / "category_intros.json").read_text(encoding="utf-8"))
except (OSError, ValueError):
    INTROS = {}


def bot_link(product_id: str | None = None, src: str = "site") -> str:
    return f"{BOT}?start=" + (f"p_{product_id}-{src}" if product_id else src)


# ------------------------------------------------------------------ small parts
ICON_TG = ('<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" '
           'stroke-linecap="round" stroke-linejoin="round"><path d="M21 4 3 11l6 2.4M21 4l-3.5 16L9 13.4M21 4 9 13.4v5.3l3-3"/></svg>')
# Telegram's own round logo (blue circle, white plane), so it's clear at a glance that the buttons open Telegram
ICON_TG_LOGO = ('<svg class="icon tglogo" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="12" fill="#229ED9"/>'
                '<path fill="#fff" d="M5.4 11.8 16.9 7.4c.5-.2 1 .1.8.9l-2 9.3c-.1.6-.5.8-1 .5l-2.9-2.1-1.4 1.4c-.2.2-.3.3-.6.3l.2-3 '
                '5.4-4.9c.2-.2 0-.3-.3-.1l-6.7 4.2-2.9-.9c-.6-.2-.6-.6.1-.9Z"/></svg>')
ICON_ARROW = ('<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.4" '
              'stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5m6-6-6 6 6 6"/></svg>')
ICON_CHECK = ('<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="3" '
              'stroke-linecap="round" stroke-linejoin="round"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>')
ICON_X = ('<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="3" '
          'stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>')
ICON_SCISSORS = ('<svg class="scissors" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" '
                 'stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/>'
                 '<path d="M8.6 7.6 20 18M8.6 16.4 20 6"/></svg>')
ICON_MEGAPHONE = ('<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" '
                  'stroke-linecap="round" stroke-linejoin="round"><path d="M4 10v4h3l7 4V6l-7 4H4Zm14-1.5a4.5 4.5 0 0 1 0 7"/></svg>')
ICON_CART = ('<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" '
             'stroke-linecap="round" stroke-linejoin="round"><path d="M3 4h2.5l2.2 10.5h10.6L20.5 8H7"/>'
             '<circle cx="9.5" cy="19" r="1.4"/><circle cx="17" cy="19" r="1.4"/></svg>')


def price(v: float, cls: str = "") -> str:
    """₪145⁸⁸ — the flyer's price: big shekels, raised agorot. The decimal point is there but hidden, so search
    engines, AI answers and screen readers read ₪145.88 and not ₪14588."""
    whole, ag = f"{v:.2f}".split(".")
    ag_html = f'<span class="sr-only">.</span><span class="ag">{ag}</span>' if ag != "00" else ""
    return f'<span class="price {cls}"><span class="cur">₪</span><span>{whole}</span>{ag_html}</span>'


def checker(src: str, field_id: str = "link", compact: bool = False) -> str:
    """The price checker: paste a product link, land in the bot on that product. Works without JS (opens the bot).
    One status line under it; in the slim band of inner pages the band's title is the visible label."""
    label_cls = ' class="sr-only"'                 # the label is for screen readers only (the field's hint says it)
    return f"""<form class="checker" action="{BOT}" method="get" data-bot="{BOT}" data-src="{src}" data-search="{SEARCH_URL}" novalidate>
<label for="{field_id}"{label_cls}>הדביקו לינק מאליאקספרס או כתבו מה אתם מחפשים</label>
<input type="hidden" name="start" value="{src}">
<div class="row">
<input id="{field_id}" class="q" type="search" enterkeyhint="search" autocomplete="off" spellcheck="false" placeholder="לינק או שם מוצר, למשל: סוללה ניידת" aria-describedby="{field_id}-msg">
<button class="btn" type="submit">{ICON_TG}<span>חפש</span></button>
</div>
<p class="msg" id="{field_id}-msg" role="status" aria-live="polite">חפשו מוצרים או <span class="ring">הדביקו קישור מאליאקספרס להשוואה</span></p>
</form>"""


CHECKER_JS = r"""<script>
function esc(t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
function priceHtml(v) { var p = Number(v).toFixed(2).split('.'); return '<span class="price"><span class="cur">₪</span><span>' + p[0] + '</span>' + (p[1] !== '00' ? '<span class="sr-only">.</span><span class="ag">' + p[1] + '</span>' : '') + '</span>'; }
function codeLabel(p) {
  var c = p.code; if (!c || typeof c !== 'object') return null;
  if (c.ends && new Date(c.ends.replace(' ', 'T')) < new Date()) return null;
  if (c.min && c.min > p.price + 0.01) return 'יש קוד הנחה בבוטן';
  if (c.off) return 'קוד ₪' + (Math.abs(c.off - Math.round(c.off)) < 0.005 ? Math.round(c.off) : c.off.toFixed(2)) + ' בבוטן';
  if (c.pct) return 'קוד ' + Math.round(c.pct) + '% בבוטן';
  return 'יש קוד הנחה בבוטן';
}
document.querySelectorAll('form.checker').forEach(function (f) {
  var input = f.querySelector('input.q'), btn = f.querySelector('button'), msg = f.querySelector('.msg');
  var idle = msg.innerHTML, label = btn.querySelector('span').textContent;
  var bot = f.dataset.bot, src = f.dataset.src;
  function say(t, err) { msg.textContent = t; msg.classList.toggle('err', !!err); }
  input.addEventListener('input', function () { if (msg.classList.contains('err')) { msg.innerHTML = idle; msg.classList.remove('err'); } });
  f.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var v = input.value.trim();
    if (!v) { say('הדביקו קודם לינק של מוצר מאליאקספרס.', true); input.focus(); return; }
    var isLink = /aliexpress|aliexpi|s\.click\.ali|\d{13,}/i.test(v);
    if (!isLink) {
      if (/https?:|www\./i.test(v)) { say('זה לא לינק מאליאקספרס. באפליקציה: שיתוף ← העתק קישור.', true); input.focus(); return; }
      if (v.length < 2) { say('כתבו שם של מוצר, למשל: סוללה ניידת', true); input.focus(); return; }
      siteSearch(v); return;
    }
    var m = v.match(/(?:\/item\/|productIds?=|[?&]id=|\/i\/)(\d{10,20})/) || v.match(/(\d{13,20})/);
    btn.setAttribute('aria-busy', 'true'); btn.querySelector('span').textContent = 'בודק…';
    var tag = document.querySelector('.proof .tag'), ts = tag && tag.querySelector('.strip span');
    if (tag && ts) { tag.classList.remove('checking'); void tag.offsetWidth; tag.classList.add('checking'); ts.textContent = 'בודק את הלינק שלכם…'; }
    function reset() { btn.removeAttribute('aria-busy'); btn.querySelector('span').textContent = label; if (tag && ts) { tag.classList.remove('checking'); ts.textContent = ts.dataset.idle; } }
    // On phones open the Telegram app directly (tg://), so the start parameter isn't lost on the way through
    // the t.me web page; if the app doesn't open within a moment, fall back to t.me.
    var mobile = /android|iphone|ipad|ipod/i.test(navigator.userAgent);
    function go(url) {
      var start = (url.split('?start=')[1] || '');
      if (mobile && start) {
        var user = bot.replace(/^https?:\/\/t\.me\//, '');
        var t = setTimeout(function () { if (!document.hidden) window.location.href = url; }, 1500);
        document.addEventListener('visibilitychange', function () { if (document.hidden) clearTimeout(t); }, { once: true });
        window.location.href = 'tg://resolve?domain=' + user + '&start=' + start;
      } else { window.location.href = url; }
      setTimeout(reset, 2500);
    }
    function siteSearch(q) {
      var band = f.closest('section') || f, box = document.getElementById('sresults');
      if (!box) { box = document.createElement('section'); box.id = 'sresults'; box.className = 'sresults'; box.setAttribute('aria-live', 'polite'); band.insertAdjacentElement('afterend', box); }
      btn.setAttribute('aria-busy', 'true'); btn.querySelector('span').textContent = 'מחפש…'; say('בוטן מחפש את הדילים הכי שווים…');
      var done = function () { btn.removeAttribute('aria-busy'); btn.querySelector('span').textContent = label; };
      fetch(f.dataset.search + '?q=' + encodeURIComponent(q) + '&v=2').then(function (r) {
        if (r.status === 429) throw new Error('slow'); if (!r.ok) throw new Error('bad'); return r.json();
      }).then(function (d) {
        done();
        var items = (d.products || []);
        if (!items.length) { say('לא מצאתי תוצאות טובות ל"' + q + '". נסו מילה אחרת, או באנגלית (למשל power bank).', true); box.innerHTML = ''; return; }
        say('נמצאו ' + items.length + ' דילים ל"' + q + '"' + (items.some(function (p) { return p.coupon; }) ? ', כולל עם קוד קופון' : '') + ' 👇');
        var codeSrc = 'k' + src.slice(1);
        var tile = function (p) {
          var was = p.original && p.original > p.price + 0.5 ? '<span class="was">₪' + p.original.toFixed(2) + '</span>' : '';
          var burst = p.discount && p.discount >= 5 ? '<span class="burst"><span class="sr-only">הנחה של </span>-' + Math.round(p.discount) + '%</span>' : '';
          var meta = (p.rating ? '⭐ ' + esc(p.rating) : '') + (p.sold ? (p.rating ? ' · ' : '') + esc(p.sold) + ' נמכרו' : '');
          var lab = codeLabel(p), code = lab ? '<a class="tcode" href="' + bot + '?start=p_' + p.id + '-' + codeSrc + '">' + esc(lab) + '</a>' : '';
          return '<li><a class="tile" href="' + esc(p.link) + '" rel="sponsored nofollow noopener" target="_blank"><span class="pic"><img src="' + esc(p.image) + '_350x350.jpg" onerror="this.onerror=null;this.src=\'' + esc(p.image) + '\'" alt="" width="300" height="300" loading="lazy" referrerpolicy="no-referrer"></span>' + burst +
            '<span class="tprice">' + priceHtml(p.price) + was + '</span><span class="ttl">' + esc(p.title) + '</span><span class="tfoot"><span class="cat">' + meta + '</span></span></a>' + code + '</li>';
        };
        var coded = items.filter(function (p) { return p.coupon; }), rest = items.filter(function (p) { return !p.coupon; });
        var group = function (title, list) { return list.length ? '<div class="sec-head"><h2>' + title + '</h2></div><ul class="tiles">' + list.map(tile).join('') + '</ul>' : ''; };
        box.innerHTML = '<div class="wrap">' + (coded.length
            ? group('🎟️ עם קוד קופון: "' + esc(q) + '"', coded) + group('עוד דילים מומלצים', rest)
            : group('הכי שווים ל"' + esc(q) + '"', rest)) + '<p class="tiles-note">תוצאות חיות מאליאקספרס, נבחרו לפי קופון, הנחה, דירוג ומכירות. לחיצה על מוצר פותחת אותו באליאקספרס (קישור שותפים: המחיר שלכם לא משתנה). רוצים גם מוכר זול יותר למוצר מסוים? הדביקו את הלינק שלו למעלה.</p></div>';
        box.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }).catch(function (e) {
        done(); say(e.message === 'slow' ? 'רגע, יותר מדי חיפושים. נסו שוב בעוד דקה.' : 'החיפוש לא זמין כרגע. נסו שוב בעוד רגע, או חפשו ישר בבוט.', true);
      });
    }
    if (!isLink) return;
    try { navigator.clipboard.writeText(v); } catch (e) {}   // backup: the link is on the clipboard too
    if (m) { say('פותח את בוטן על המוצר…'); go(bot + '?start=p_' + m[1] + '-' + src); return; }
    var sh = v.match(/a\.aliexpress\.[a-z.]+\/_([A-Za-z0-9]{3,40})/i);
    if (sh) { say('פותח את בוטן על המוצר…'); go(bot + '?start=s_' + sh[1] + '-' + src); return; }
    var done = function () { say('הלינק הועתק. בטלגרם הדביקו אותו לבוטן ושלחו.'); setTimeout(function () { go(bot + '?start=' + src); }, 900); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(v).then(done, done); else done();
  });
});
</script>"""


# ------------------------------------------------------------------ layout
def _nav() -> list[tuple[str, str]]:
    """The menu. The sale events slot comes from data/events.csv: up to two running or upcoming events with a guide
    of their own; with none, the sales calendar."""
    sale = [(f"/guides/{r['guide']}/", r["nav"]) for r in events_menu] or [("/guides/sales-calendar/", "לוח המבצעים")]
    return ([("/", "ראשי"), ("/coupons/", "קודי קופון"), ("/guides/", "מדריכים")] + sale +
            [("/guides/code-not-working/", "קוד לא עובד?"), ("/about/", "אודות")])


NAV = _nav()

ORG = {"@type": "Organization", "@id": f"{SITE_URL}/#org", "name": NAME, "alternateName": "Boten",
       "url": f"{SITE_URL}/", "logo": f"{SITE_URL}/assets/logo-192.png", "sameAs": [BOT, CHANNEL]}

SITEMAP: list[tuple[str, date | None]] = []
LOGO_OG = (f"{SITE_URL}/assets/logo.png", 512, 512)


_cards_off: list[str] = []


def share_image(path: str, card: dict | None) -> tuple[str, int, int]:
    """The page's share card (1200x630, see share_cards.py), or the logo when cards can't be drawn here."""
    if not card or _cards_off:
        return LOGO_OG
    try:
        import share_cards
    except ImportError as ex:                      # Pillow / python-bidi not installed: the logo, said once
        _cards_off.append(str(ex))
        print(f"share cards off ({ex}): pages use the logo")
        return LOGO_OG
    try:
        name = page_key(path) + ".png"
        if share_cards.render(OUT / "og" / name, card, ROOT, OUT):
            return f"{SITE_URL}/og/{name}", 1200, 630
    except Exception as ex:                        # never fail the build over a picture
        print(f"share card {path}: {ex}")
    return LOGO_OG


def page(path: str, title: str, description: str, body: str, crumbs: list[tuple[str, str]] | None = None,
         schema: list[dict] | None = None, full: bool = False, js: bool = False,
         updated: date | None = None, card: dict | None = None) -> None:
    """full=True: body brings its own full-bleed sections. Otherwise it is a reading page, wrapped and closed with the bot invite.
    updated: the date this page's content last changed (footer, sitemap). card: what goes on the share image."""
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
    else:                                      # every other page: the slim yellow band, so the page's answer stays in view
        menubar_top = hero(src_for("hero", path), False, compact=True) + menubar
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
<a class="btn" href="{bot_link(src=src_for('inline', path))}">{ICON_TG}פתחו את בוטן בטלגרם</a><a class="btn secondary" href="{CHANNEL}">{ICON_MEGAPHONE}לערוץ הדילים בטלגרם</a></aside>
</div>"""
    og_url, og_w, og_h = share_image(path, card)
    footer_date = f"<p>עודכן לאחרונה: {updated.strftime('%d/%m/%Y')}</p>" if updated else ""
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
<meta property="og:image" content="{og_url}">
<meta property="og:image:width" content="{og_w}">
<meta property="og:image:height" content="{og_h}">
<meta property="og:image:alt" content="{e(title)}">
<meta name="twitter:card" content="{'summary_large_image' if og_w > og_h else 'summary'}">
<meta name="theme-color" content="#d03b37">
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
<a class="tg" href="{bot_link(src=src_for('nav', path))}" aria-label="בוטן בטלגרם">{ICON_TG_LOGO}בוטן בטלגרם</a>
<a class="tg ch" href="{CHANNEL}" aria-label="ערוץ הדילים בטלגרם">{ICON_TG_LOGO}<span class="long">ערוץ הדילים</span><span class="short">ערוץ</span></a>
</div></header>
{menubar_top}
<main id="main">
{body}
</main>
<footer class="site"><div class="wrap">
<div class="links">{"".join(f'<a href="{BASE}{p}">{n}</a>' for p, n in NAV)}<a href="{bot_link(src=src_for('footer', path))}">בוטן בטלגרם</a><a href="{CHANNEL}">ערוץ הדילים</a></div>
<p>* גילוי נאות: חלק מהקישורים באתר ובבוט הם קישורי שותפים של אליאקספרס. על רכישה דרכם בוטן מקבל עמלה קטנה, והמחיר שלכם לא משתנה.</p>
<p>* בוטן אינו קשור לאליאקספרס ואינו מייצג אותה. AliExpress הוא סימן מסחר של בעליו. המחירים וההנחות נכונים ליום הבדיקה בלבד.</p>
{footer_date}
</div></footer>
{CHECKER_JS if js else ""}
</body>
</html>
"""
    target = OUT / path.strip("/") / "index.html" if path != "/404.html" else OUT / "404.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(doc, encoding="utf-8")
    if path != "/404.html":
        SITEMAP.append((url, updated))


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
                f'<a class="btn secondary" href="{CHANNEL}">{ICON_MEGAPHONE}לערוץ הדילים בטלגרם</a></div>')
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


def ils(v: float) -> str:
    """A shekel amount inside running text: ₪12.65, ₪10."""
    return f"₪{v:.0f}" if abs(v - round(v)) < 0.005 else f"₪{v:.2f}"


def code_label(p: dict) -> str | None:
    """What a tile may say about the product's code. The code itself is never printed: it waits in the bot."""
    c = p.get("code")
    if not isinstance(c, dict):
        return None
    ends = parse_dt(c.get("ends") or "")
    if ends and ends < NOW:
        return None
    off, pct, minimum = num(c.get("off")), num(c.get("pct")), num(c.get("min"))
    if minimum and minimum > float(p["price"]) + 0.01:     # needs a bigger cart than one unit: the bot explains
        return "יש קוד הנחה בבוטן"
    if off:
        return f"קוד {ils(off)} בבוטן"
    if pct:
        return f"קוד {pct:.0f}% בבוטן"
    return "יש קוד הנחה בבוטן"


def product_tiles(rows: list[dict], path: str) -> str:
    """Channel deals as flyer tiles. A tile is one link straight to AliExpress (affiliate), dated like every price
    on the site. When the product has a seller code, a sticker beside the link opens the bot on that product."""
    tiles = []
    for p in rows:
        price_v, orig, disc = float(p["price"]), p.get("original"), p.get("discount")
        was = f'<span class="was">₪{float(orig):.2f}</span>' if orig and float(orig) > price_v + 0.5 else ""
        burst = (f'<span class="burst"><span class="sr-only">הנחה של </span>-{disc:.0f}%</span>'
                 if disc and disc >= 5 else "")
        cat = f'<span class="cat">{e(clean_cat(p["category"]))}</span>' if clean_cat(p.get("category")) else ""
        if p.get("pick"):
            cat = '<span class="cat pick">בחירה של בוטן</span>'
        when = iso_dt(p.get("checked") or p.get("posted"))
        asof = f'<span class="asof">נכון ל-{when.strftime("%d/%m")}</span>' if when else ""
        label = code_label(p)
        code = (f'<a class="tcode" href="{bot_link(p.get("id"), src_for("code", path))}">{ICON_TG}<span>{e(label)}</span></a>'
                if label and p.get("id") else "")
        tiles.append(f"""<li><a class="tile" href="{e(p['link'])}" rel="sponsored nofollow noopener" target="_blank">
<span class="pic"><img src="{e(p['image'])}" alt="" width="300" height="300" loading="lazy" decoding="async" referrerpolicy="no-referrer"></span>
{burst}
<span class="tprice">{price(price_v)}{was}</span>
<span class="ttl">{e(short_title(p['title']))}</span>
<span class="tfoot">{cat}{asof}</span>
</a>{code}</li>""")
    return f'<ul class="tiles">{"".join(tiles)}</ul>'


# ------------------------------------------------------------------ pages
def hero(src: str, main_heading: bool, compact: bool = False) -> str:
    """The yellow band with the price checker. On the home page its title is the page's h1; elsewhere the page
    keeps its own h1, so the band's title is a styled paragraph (one h1 per page). Inner pages get the slim band:
    a line and the checker, so the page's own answer is on the first phone screen."""
    if compact:
        return f"""<section class="hero compact" aria-labelledby="hero-title"><div class="wrap">
<p id="hero-title" class="hero-title">יש לכם לינק? <em>בוטן בודק.</em></p>
{checker(src, compact=True)}
</div></section>"""
    tag = "h1" if main_heading else "p"
    return f"""<section class="hero" aria-labelledby="hero-title"><div class="wrap">
<div>
<{tag} id="hero-title" class="hero-title">קנייה חכמה,<br><span class="sub">בדקו אם קיבלתם את <em class="nowrap">הדיל המשתלם ביותר</em> עבורכם</span></{tag}>
</div>
{checker(src)}
</div></section>"""


# The date someone last changed each page's own text here in build.py (data-driven parts date themselves).
EDITED = {"/": "2026-10-23", "/coupons/": "2026-10-21", "/guides/": "2026-10-21", "/guides/coupon-types/": "2026-10-20",
          "/guides/code-not-working/": "2026-10-20", "/about/": "2026-10-20"}


def event_card() -> tuple[str, str, str]:
    """The first "before you buy" card: the next sale event with a guide of its own, else the sales calendar."""
    for r in events_menu:
        if r.get("card_title"):
            return f"/guides/{r['guide']}/", r["card_title"], r.get("card_text", "")
    return "/guides/sales-calendar/", "לוח המבצעים: מתי הכי משתלם לקנות", "כל אירועי המבצעים של השנה, ומה כדאי לקנות בכל אחד."


def event_marks() -> list[datetime]:
    """Moments when the sale-event content changed on its own (an event entered the menu or ended)."""
    return [d for r in events for d in (r["_from"], r["_end"]) if d and d <= NOW]


def build_home():
    path = "/"
    ev_url, ev_title, ev_text = event_card()
    tiles = ""
    if products:
        tiles = f"""<section aria-labelledby="hot-title">
<div class="sec-head"><h2 id="hot-title">הדילים של השבוע</h2><a href="{CHANNEL}">כל הדילים בערוץ {ICON_ARROW}</a></div>
{product_tiles(products, path)}
<p class="tiles-note">המחירים נכונים לתאריך שמופיע על כל מוצר, ועשויים להשתנות. לחיצה על מוצר פותחת אותו באליאקספרס (קישור שותפים: המחיר שלכם לא משתנה).</p>
</section>"""
    deals = ""
    if seller:                 # no verified seller code in force = no section: an empty box here says nothing useful
        deals = f"""<section aria-labelledby="deals-title">
<h2 id="deals-title">קודי מוכר שנבדקו</h2>
<p class="lead">קודי מוכר שנבדקו, עם תאריך. את הקוד עצמו מקבלים בבוטן, יחד עם המחיר המעודכן.</p>
{coupons(seller[:4], src_for("deal", path))}
</section>"""
    body = f"""{hero(src_for('hero', path), True)}
<!--MENUBAR-->

<div class="wrap">
{tiles}

{deals}

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
<li><a class="guide-card" href="{BASE}{ev_url}"><b>{e(ev_title)}</b><span>{e(ev_text)}</span></a></li>
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
<div class="actions"><a class="btn" href="{bot_link(src=src_for('closer', path))}">{ICON_TG}פתחו את בוטן בטלגרם</a>
<a class="btn secondary" href="{CHANNEL}">{ICON_MEGAPHONE}לערוץ הדילים בטלגרם</a></div>
</div></section>"""
    updated = latest(EDITED[path], *[p.get("checked") or p.get("posted") for p in products],
                     *[r["_date"] for r in checks], *[r.get("checked") for r in seller],
                     *[r["_end"] for r in read_csv_ends("seller_codes.csv")], *event_marks())
    page(path, f"{NAME}: קודי קופון לאליאקספרס שנבדקו + בוט שבודק כל מוצר",
         "קודי קופון לאליאקספרס בישראל שנבדקו בקופה, עם תאריך. ובוט טלגרם חינמי שמחזיר לכל מוצר מחיר בשקלים, הנחה וקוד מוכר.",
         body, full=True, js=True, updated=updated,
         card={"lines": [("קנייה חכמה,", "ink"), ("בדקו אם קיבלתם", "ink"), ("את הדיל המשתלם ביותר", "red")],
               "sub": "מחיר בשקלים, הנחה וקוד אם יש. בבוט טלגרם חינמי.", "products": products[:3]})


def read_csv_ends(name: str) -> list[dict]:
    """Rows of a codes file whose end has passed: their disappearance changed the page that day."""
    return [{"_end": d} for r in read_csv(name) if (d := parse_dt(r.get("ends") or r.get("end") or "")) and d <= NOW]


# ------------------------------------------------------------------ the coupon codes page (/coupons/)
def _links() -> dict:
    """Affiliate links made by the bot (data/site_links.json): {"home": url, "products": {product_id: url}}."""
    try:
        return json.loads((ROOT / "data" / "site_links.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _code_sets(rows: list[dict]) -> list[tuple[str, list[dict]]]:
    """Circulating codes grouped by set (the code without its running number: ILAFFOCT01..10 → ILAFFOCT).
    Sets of three codes or more get their own line in the answer box and their own FAQ; single codes stay in the table."""
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(re.sub(r"\d+$", "", r["code"]), []).append(r)
    return [(name, rs) for name, rs in groups.items() if len(rs) >= 3]


def build_coupons_page():
    path = "/coupons/"
    links = _links()
    home_link = links.get("home")
    buy = (f'<a class="btn" href="{e(home_link)}" rel="sponsored nofollow noopener" target="_blank">{ICON_CART}לקנייה באליאקספרס</a>'
           if home_link else "")
    bot_btn = f'<a class="btn secondary" href="{bot_link(src=src_for("actions", path))}">{ICON_TG}בדקו מוצר בבוטן</a>'
    nxt = events_live[0] if events_live else None

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
                       f"<td>מעל ${float(r['min_usd']):g}</td><td><span class=\"sticker bad\">{ICON_X}פג תוקף</span></td></tr>" for r in last)
        when = (f"מ-{fmt_d(last[0]['_start'], True)} עד {fmt_d(last[0]['_end'], True)}" if last else "")
        platform_html = ("<p>אליאקספרס מוציאה סט קודים לישראל (ILAFF…) לקראת אירועי מבצע, לחלון של כשבוע. "
                         "אנחנו מפרסמים סט רק כשיש לו חלון תוקף רשמי, ומעדכנים כאן ביום שהוא יוצא.</p>"
                         + (f"<p>הסט האחרון היה בתוקף {when}:</p>"
                            f'<div class="table-wrap"><table class="codes"><thead><tr><th>קוד</th><th>הנחה</th><th>מינימום לסל</th>'
                            f"<th>סטטוס</th></tr></thead><tbody>{prow}</tbody></table></div>" if prow else ""))
        answer_now = "אין כרגע סט רשמי פעיל של קודי ישראל (ILAFF)."
        if nxt:                                    # from data/events.csv, so it never names an event that is over
            which = "שרץ עכשיו" if nxt["_start"] <= NOW else "הבא"
            answer_now += (f" סטים לישראל יוצאים בדרך כלל לקראת אירועי מבצע, והאירוע {which} הוא "
                           f"{e(nxt['name'])} ({e(nxt['date_label'])}).")

    # --- codes that circulate on coupon sites, with what we actually know about each (sorted by cart size).
    # Rows leave on their own after the validity the coupon sites claim (show_until in the CSV).
    crow = ""
    for r in circulating:
        if r["status"] == "failed":
            d = datetime.strptime(r["checked"], "%Y-%m-%d").strftime("%d/%m")
            parts = re.split(r'("[^"]+")', r["details"])
            det = "".join(f'<bdi lang="en">{e(x)}</bdi>' if x.startswith('"') else e(x) for x in parts)
            st, cls = f'<span class="sticker bad">{ICON_X}נכשל בבדיקה שלנו ({d})</span> {det}', "code bad"
        else:
            st, cls = '<span class="sticker info">לא נבדק</span> נסו בקופה, ייתכן שהמכסה נגמרה', "code"
        crow += (f"<tr><td data-l=\"מינימום לסל\">מעל ${float(r['min_usd']):g}</td><td data-l=\"הנחה\">${float(r['off_usd']):g}</td>"
                 f"<td data-l=\"קוד\"><code class=\"{cls}\">{e(r['code'])}</code></td>"
                 f"<td data-l=\"מה ידוע\">{e(r['claimed'])}. {st}</td></tr>")
    bad_html = (f"""<h2 id="not-working">הקודים שמסתובבים באתרי קופונים ({MONTH_YEAR}), ומה המצב שלהם</h2>
<p>אלה הקודים שאתרי קופונים ישראליים (וגם ChatGPT, שמצטט אותם) מציגים החודש. לאף אחד מהם לא מצאנו מקור רשמי של אליאקספרס או חלון תוקף רשמי.
מה שבדקנו בקופה אמיתית עם משלוח לישראל מסומן, וכך גם מה שלא הספקנו לבדוק. בוחרים את המדרגה הגבוהה ביותר שהסל עובר אחרי ההנחות.</p>
<div class="table-wrap"><table class="codes cards"><thead><tr><th>מינימום לסל</th><th>הנחה</th><th>קוד</th><th>מה ידוע</th></tr></thead>
<tbody>{crow}</tbody></table></div>""" if crow else "")

    # One line in the answer box and one FAQ per circulating set, written from the data (they leave with the set).
    set_lines, set_faq = [], []
    for name, rows in _code_sets(circulating):
        claimed = rows[0]["claimed"].split(":", 1)[-1].strip()
        failed = [r for r in rows if r["status"] == "failed"]
        rest = [r for r in rows if r["status"] != "failed"]
        if failed:
            what = (f"הקוד {failed[0]['code']} נכשל בבדיקה שלנו" if len(failed) == 1
                    else f"{len(failed)} קודים ממנו נכשלו בבדיקה שלנו")
            what += ", ואת השאר לא הצלחנו לאמת" if rest else ""
        else:
            what = "את הקודים לא הצלחנו לאמת"
        set_lines.append(f"הסט {e(name)} שמופיע באתרי קופונים ({e(claimed)}): {what}, "
                         f'<a href="#not-working">פירוט בטבלה</a>.')
        answer = "".join(f"{r['code']} (‏${float(r['off_usd']):g} מעל ${float(r['min_usd']):g}) נכשל בבדיקה שלנו בקופה ב-"
                         f"{datetime.strptime(r['checked'], '%Y-%m-%d').strftime('%d/%m')}: {e(r['details'].strip(), quote=False)}. "
                         for r in failed)
        if rest:
            answer += (f"את {'שאר המדרגות' if failed else 'המדרגות'} לא בדקנו "
                       f"(הן מתחילות בסל של ${min(float(r['min_usd']) for r in rest):g}). ")
        answer += "לא מצאנו לסט הזה מקור רשמי של אליאקספרס. אפשר לנסות, ואם הקוד נדחה, כנראה שגם המכסה שלו נגמרה."
        set_faq.append((f"הקודים {rows[0]['code']}–{rows[-1]['code']} עובדים?", answer))

    upcoming = events_live[:3]
    when_new = "סביב אירועי מבצע, לחלון של כשבוע."
    if upcoming:
        when_new += " הקרובים: " + ", ".join(f"{e(r['name'])} ({e(r['date_label'])})" for r in upcoming) + "."
    guide_links = [f'<a href="{BASE}/guides/{r["guide"]}/">{e(r["nav"] or r["name"])} ←</a>' for r in upcoming if r.get("guide")]
    when_new += " " + " · ".join([f'<a href="{BASE}/guides/sales-calendar/">לוח המבצעים ←</a>'] + guide_links)

    faq_html, faq_schema = faq_block([
        ("יש עכשיו קוד קופון לאליאקספרס שעובד בישראל?",
         f"{answer_now} "
         + f"לכל מוצר אחר אפשר לשלוח את הלינק <a href=\"{bot_link(src=src_for('faq', path))}\">לבוטן</a>, והוא מחזיר קוד מוכר אם יש."),
        *set_faq,
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
        ("מתי יוצאים קודים חדשים?", when_new),
        ("איך מקבלים קוד למוצר מסוים?",
         f'שולחים את הלינק של המוצר <a href="{bot_link(src=src_for("faq", path))}">לבוטן בטלגרם</a>. הוא בודק את המוצר ומחזיר מחיר בשקלים, '
         "הנחה וקוד מוכר אם יש, ואם אין, מחפש מוכר זול יותר."),
    ])
    updated = latest(EDITED[path], *[r["_start"] for r in platform_all], *[r["_end"] for r in platform_all],
                     *[r.get("checked") for r in circulating_all], *[_show_until(r) for r in circulating_all],
                     *[r["_date"] for r in checks], *event_marks())
    upd = updated.strftime("%d/%m/%Y") if updated else TODAY
    body = f"""<header class="page-head"><h1>קודי קופון לאליאקספרס בישראל ({MONTH_YEAR}): רק קודים שנבדקו בקופה</h1>
<span class="updated">עודכן: {upd} · ליד כל קוד מופיע מתי נבדק</span></header>
<div class="answer"><p><b>בקצרה, נכון ל-{TODAY}:</b> {answer_now}
{" ".join(set_lines)}</p></div>
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
    page(path, f"קודי קופון לאליאקספרס ({MONTH_YEAR}): רק קודים שנבדקו בקופה | {NAME}",
         f"קודי קופון לאליאקספרס בישראל, {MONTH_YEAR}: קודי מוכר שנבדקו בקופה, קודי ישראל (ILAFF) עם תוקף, "
         "ורשימת קודים שמסתובבים ברשת ולא עובדים. מתעדכן כל יום.",
         body, crumbs=[(path, "קודי קופון")], schema=[faq_schema], updated=updated,
         card={"lines": [("קודי קופון", "ink"), ("לאליאקספרס בישראל", "ink")],
               "sub": f"רק קודים שנבדקו בקופה · {MONTH_YEAR}", "stamp": True})


def build_coupon_types():
    path = "/guides/coupon-types/"
    updated = latest(EDITED[path]) or NOW.date()
    body = f"""<header class="page-head"><h1>סוגי הקופונים באליאקספרס ואיך משלבים אותם</h1>
<span class="updated">עודכן: {updated.strftime('%d/%m/%Y')}</span></header>
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
    page(path, f"סוגי קופונים באליאקספרס ואיך משלבים אותם | {NAME}",
         "קוד קופון, קופון חנות, קופוני Select ומטבעות: מה ההבדל, מה אפשר לשלב באותה הזמנה, ולמה המינימום נבדק אחרי ההנחות.",
         body, crumbs=[("/guides/", "מדריכים"), (path, "סוגי קופונים")], updated=updated,
         schema=[{"@type": "Article", "headline": "סוגי הקופונים באליאקספרס ואיך משלבים אותם", "inLanguage": "he-IL",
                  "dateModified": updated.isoformat(), "author": {"@id": f"{SITE_URL}/#org"},
                  "publisher": {"@id": f"{SITE_URL}/#org"}}],
         card={"lines": [("סוגי הקופונים", "ink"), ("באליאקספרס", "ink")], "sub": "קוד, קופון חנות, Select ומטבעות: מה מצטרף למה"})


def build_not_working():
    path = "/guides/code-not-working/"
    updated = latest(EDITED[path]) or NOW.date()
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
<span class="updated">עודכן: {updated.strftime('%d/%m/%Y')} · עם הודעות השגיאה האמיתיות מהקופה</span></header>
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
    page(path, f"קוד קופון לא עובד באליאקספרס? 3 סיבות והפתרון | {NAME}",
         "הודעות השגיאה האמיתיות מהקופה של אליאקספרס, מה כל אחת אומרת ומה עושים: מינימום אחרי הנחות, מכסה שנגמרה, קוד לא תקף.",
         body, crumbs=[("/guides/", "מדריכים"), (path, "קוד קופון לא עובד")], updated=updated,
         schema=[{"@type": "Article", "headline": "למה קוד הקופון לא עובד באליאקספרס", "inLanguage": "he-IL",
                  "dateModified": updated.isoformat(), "author": {"@id": f"{SITE_URL}/#org"},
                  "publisher": {"@id": f"{SITE_URL}/#org"}}],
         card={"lines": [("קוד הקופון", "ink"), ("לא עובד?", "red")], "sub": "3 הודעות השגיאה האמיתיות מהקופה, ומה עושים"})


def _split_h1(h1: str) -> tuple[str, str]:
    """A guide's h1 as a share-card headline and subline: "X: Y" → ("X", "Y")."""
    head, _, sub = h1.partition(":")
    return head.strip(), sub.strip()


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
                tiles = (f'<h2>דילים מהערוץ</h2>{product_tiles(rows[:8], url)}'
                         '<p class="tiles-note">המחירים נכונים לתאריך שמופיע על כל מוצר. קישורי שותפים: המחיר שלכם לא משתנה.</p>')
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
        head, sub = _split_h1(g["h1"])
        page(url, g["title"], g["desc"], body, crumbs=[("/guides/", "מדריכים"), (url, g["nav"])], schema=schema,
             updated=upd.date(), card={"lines": [(head, "ink")], "sub": sub or g["nav"], "kicker": "מדריך"})

    # hub
    groups = [
        ("מבצעים", ["11-11", "black-friday", "sales-calendar"]),
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
    path = "/guides/"
    updated = latest(EDITED[path], EDITED["/guides/coupon-types/"], EDITED["/guides/code-not-working/"],
                     *[g["updated"] for g in GUIDES]) or NOW.date()
    body = f"""<header class="page-head"><h1>מדריכים לקנייה חכמה באליאקספרס</h1>
<span class="updated">עודכן: {updated.strftime('%d/%m/%Y')} · כל מה שצריך לדעת לפני שקונים מחו"ל</span></header>
{sections}"""
    page(path, f"מדריכים לקנייה באליאקספרס: מבצעים, מכס, משלוח וקופונים | {NAME}",
         "מדריכים בעברית לקונים באליאקספרס: מתי המבצעים, כמה מס משלמים, כמה זמן לוקח משלוח, אישור משרד התקשורת, החזרים וקופונים.",
         body, crumbs=[(path, "מדריכים")], updated=updated,
         card={"lines": [("מדריכים לקנייה", "ink"), ("חכמה באליאקספרס", "ink")], "sub": "מבצעים, מכס, משלוח וקופונים"})


def category_intro(slug: str) -> str:
    """The category's short intro (data/category_intros.json), with a link to the guide it draws on."""
    c = (INTROS.get("categories") or {}).get(slug)
    if not c or not c.get("text"):
        return ""
    link = ""
    g = c.get("guide")
    if g:
        label = (INTROS.get("guides") or {}).get(g, "המדריך")
        link = f' <a href="{BASE}/guides/{e(g)}/">{e(label)} {ICON_ARROW}</a>'
    return f'<p class="cat-intro">{e(c["text"])}{link}</p>'


def build_categories():
    """A page per product category: a short buying note, then Boten's picks, then the automatic best deals."""
    for c in categories:
        url = f"/c/{c['slug']}/"
        if c["products"]:
            grid = (product_tiles(c["products"][:24], url) +
                    '<p class="tiles-note">בוטן בוחר לכל קטגוריה את הדילים הכי שווים לפי מחיר, הנחה, דירוג ומכירות, '
                    'ומעדכן אותם כמה פעמים ביום. המחירים עשויים להשתנות. לחיצה פותחת את המוצר באליאקספרס '
                    '(קישור שותפים: המחיר שלכם לא משתנה).</p>')
        else:
            grid = ('<div class="empty"><p><b>בוטן עוד מחפש את הדילים לקטגוריה הזו.</b> בינתיים אפשר לשלוח לו לינק '
                    'של כל מוצר ולקבל מחיר, הנחה וקוד אם יש.</p>'
                    f'<a class="btn" href="{bot_link(src=src_for("empty", url))}">{ICON_TG}בדקו מוצר בבוטן</a> '
                    f'<a class="btn secondary" href="{CHANNEL}">{ICON_MEGAPHONE}לערוץ הדילים בטלגרם</a></div>')
        stamp = iso_dt(c.get("updated"))                 # when the bot last refreshed this category
        updated = latest(stamp, *[p.get("checked") or p.get("posted") for p in c["products"]]) if c["products"] else None
        upd_txt = f"עודכן: {fmt_d(stamp, True) if stamp else updated.strftime('%d/%m/%Y')} · " if updated else ""
        body = f"""<header class="page-head"><h1>{e(c['name'])} מאליאקספרס: הדילים של השבוע</h1>
<span class="updated">{upd_txt}מחיר בשקלים, עם הנחה ודירוג</span></header>
{category_intro(c['slug'])}
{grid}"""
        items = [{"@type": "ListItem", "position": i, "url": p["link"], "name": short_title(p["title"])}
                 for i, p in enumerate(c["products"][:24], 1)]
        schema = [{"@type": "CollectionPage", "name": f"{c['name']} מאליאקספרס", "inLanguage": "he-IL",
                   "mainEntity": {"@type": "ItemList", "itemListElement": items}}] if items else []
        page(url, f"{c['name']} מאליאקספרס: דילים והנחות בשקלים | {NAME}",
             f"הדילים הכי שווים ב{c['name']} מאליאקספרס, שבוטן בחר לפי מחיר, הנחה, דירוג ומכירות. מחיר בשקלים, מתעדכן כמה פעמים ביום.",
             body, crumbs=[(url, c["name"])], schema=schema, updated=updated,
             card={"lines": [(c["name"], "ink")], "sub": "הדילים של השבוע מאליאקספרס, מחיר בשקלים",
                   "products": c["products"][:3]})
        if not c["products"]:                             # no thin pages in the sitemap
            SITEMAP[:] = [(u, d) for u, d in SITEMAP if u != SITE_URL + url]


def build_about():
    path = "/about/"
    updated = latest(EDITED[path]) or NOW.date()
    body = f"""<header class="page-head"><h1>אודות בוטן</h1></header>
<div class="prose">
<p class="lead">בוטן הוא בוט טלגרם חינמי ואתר שעוזרים לקנות באליאקספרס בפחות.</p>
<p>הבוט בודק כל מוצר שמדביקים לו ומחזיר מחיר בשקלים, הנחה וקוד מוכר אם יש, ומציע חלופות זולות יותר. באתר אנחנו מפרסמים רק מה שנבדק, עם תאריך, ומתעדים גם קודים שלא עבדו.</p>
<h2>גילוי נאות</h2>
<p>הקישורים לאליאקספרס בבוט ובאתר הם קישורי שותפים. על רכישה דרכם בוטן מקבל עמלה קטנה מאליאקספרס, והמחיר שלכם לא משתנה. בוטן אינו קשור לאליאקספרס ואינו מייצג אותה.</p>
<h2>פרטיות</h2>
<p>הבוט לא שומר מידע אישי ולא שולח הודעות שלא ביקשתם. האתר לא משתמש בעוגיות מעקב.</p>
<h2>יצירת קשר</h2>
<p>דרך <a href="{bot_link(src=src_for('inline', path))}">הבוט בטלגרם</a>. דילים חדשים מתפרסמים ב<a href="{CHANNEL}">ערוץ הדילים</a>.</p>
</div>"""
    page(path, f"אודות {NAME} וגילוי נאות", "מי אנחנו, איך בוטן עובד, גילוי נאות על קישורי שותפים ופרטיות.",
         body, crumbs=[(path, "אודות")], updated=updated,
         card={"lines": [("אודות בוטן", "ink")], "sub": "בוט טלגרם חינמי שבודק מחירים וקודים באליאקספרס"})


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
        f"User-agent: *\nAllow: /\nDisallow: {BASE}/feed/\n\n"
        "# AI search engines are welcome (citations in ChatGPT, Perplexity, Claude, Copilot)\n"
        "User-agent: OAI-SearchBot\nAllow: /\n\nUser-agent: ChatGPT-User\nAllow: /\n\n"
        "User-agent: PerplexityBot\nAllow: /\n\nUser-agent: Claude-SearchBot\nAllow: /\n\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    urls = "".join(f"<url><loc>{u}</loc>" + (f"<lastmod>{d.isoformat()}</lastmod>" if d else "") + "</url>"
                   for u, d in SITEMAP)
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
    # The feeds this build used, so the next build has a copy when the bot doesn't answer (see load_feed).
    (OUT / "feed").mkdir(exist_ok=True)
    for name, data in FEEDS.items():
        (OUT / "feed" / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
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
    try:                                          # product photos for the share cards, fetched in parallel
        import share_cards
        share_cards.prefetch([p["image"] for p in products[:3]] +
                             [p["image"] for c in categories for p in c["products"][:3]], OUT)
    except Exception as ex:
        print(f"share cards: no prefetch ({ex})")
    build_home(); build_coupons_page(); build_coupon_types(); build_not_working(); build_guides(); build_categories(); build_about(); build_404()
    build_meta_files()
    print(f"built {len(SITEMAP)} pages into {OUT} (base={BASE or '/'}), {len(seller)} seller codes, "
          f"{len(platform_active)} platform codes active, {len(events_live)} sale events ahead")


if __name__ == "__main__":
    main()
