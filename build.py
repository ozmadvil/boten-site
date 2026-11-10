"""Builds the NiceBuy static site into _site/ from the CSV files in data/.

Run:  python build.py            (SITE_URL env sets the public address, for canonical links and the sitemap)
GitHub Actions rebuilds it on every push and every hour, so expired codes and past sale events drop off by themselves.
Design system: see DESIGN.md (the weekly sale flyer).

Dates are honest: every page carries the date its content last changed (footer, sitemap lastmod, dateModified),
never just the build time. Every link into the bot carries the page and the place it came from (see src_for).
"""
import csv
import hashlib
import html
import json
import os
import re
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "_site"
SITE_URL = os.environ.get("SITE_URL", "https://nicebuy.co.il").rstrip("/")
BASE = "/" + SITE_URL.split("://", 1)[1].split("/", 1)[1] if SITE_URL.count("/") > 2 else ""   # path prefix
BOT = "https://t.me/Boten_IL_bot"
CHANNEL = "https://t.me/Boten_deals"
YOUTUBE = "https://www.youtube.com/@nicebuycoil"
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
NAME = "NiceBuy"
EMAIL = "nicebuyisrael@gmail.com"
LEGAL = [("/accessibility/", "הצהרת נגישות"), ("/privacy/", "מדיניות פרטיות"), ("/terms/", "תנאי שימוש")]
e = html.escape


def json_script(obj) -> str:
    """JSON for inside a <script> element: '</' and '<!--' can't end or bend the element (product titles come
    from AliExpress sellers)."""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "\\u003c!--")


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
USD_ILS = float(os.environ.get("USD_ILS") or 3.7)       # only to pick a tier for a ₪ price; the coupons page keeps $
for r in platform_all:                       # a set published in ₪ (off_ils/min_ils) or in $ (off_usd/min_usd)
    r["_off"] = float(r.get("off_ils") or 0) or round(float(r.get("off_usd") or 0) * USD_ILS, 2)
    r["_min"] = float(r.get("min_ils") or 0) or round(float(r.get("min_usd") or 0) * USD_ILS, 2)
platform_active.sort(key=lambda r: r["_min"])


def platform_for(price: float) -> dict | None:
    """The Israel code that fits one unit of this product: the biggest tier whose minimum the price reaches.
    None when the price is under every minimum (owner's choice 02/11: no code on cards it doesn't fit)."""
    if not platform_active:
        return None
    fit = [r for r in platform_active if r["_min"] <= price + 0.01]
    return max(fit, key=lambda r: r["_off"]) if fit else None


def platform_what(r: dict) -> str:
    """The tier as published: in ₪ when the set is in ₪, else in $ (no converted amounts on the site)."""
    return f"{platform_amt(r, 'off')} הנחה מעל {platform_amt(r, 'min')}"


def platform_amt(r: dict, k: str) -> str:
    """'off' or 'min' as published: ₪ for a set in shekels, else $."""
    return ils(float(r[f"{k}_ils"])) if r.get(f"{k}_ils") else f"${float(r[f'{k}_usd']):g}"
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
PRODUCT_URL = os.environ.get("PRODUCT_URL") or BOT_FEED_URL.replace("/products.json", "/product")  # a pasted link, answered on the site


def _origin(u: str) -> str:
    from urllib.parse import urlsplit
    p = urlsplit(u)
    return f"{p.scheme}://{p.netloc}" if p.scheme in ("http", "https") and p.netloc else ""


# Content Security Policy (as a <meta>: GitHub Pages can't send headers). Scripts and styles only from the site;
# photos from AliExpress; live search and link checks from the bot; the search form may only go to Telegram.
# Cloudflare Web Analytics (no cookies, no personal data); the token is public. CF_BEACON=off removes it.
CF_BEACON = os.environ.get("CF_BEACON", "bc36a20e0c3348f189f2652e81091876")
CF_BEACON = "" if CF_BEACON == "off" else CF_BEACON
BEACON_HTML = ('<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
               "data-cf-beacon='{\"token\": \"" + CF_BEACON + "\"}'></script>") if CF_BEACON else ""
CSP = "; ".join([
    "default-src 'self'", "script-src 'self'" + (" https://static.cloudflareinsights.com" if CF_BEACON else ""), "style-src 'self'", "font-src 'self'", "object-src 'none'",
    "base-uri 'self'", "form-action https://t.me",
    "img-src 'self' data: https://*.aliexpress-media.com https://*.alicdn.com https://*.aliexpress.com",
    "connect-src 'self' " + " ".join(sorted({o for o in map(_origin, (SEARCH_URL, PRODUCT_URL)) if o}))
    + (" https://cloudflareinsights.com" if CF_BEACON else ""),
])
FEED_MAX_AGE = timedelta(hours=72)
FEEDS: dict[str, dict] = {}                 # what this build used, republished under /feed/


# a new style.css reaches visitors at once (browsers keep the old one otherwise)
import hashlib as _hashlib
CSS_VERSION = _hashlib.md5((ROOT / "assets" / "style.css").read_bytes()).hexdigest()[:8]


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


AFFILIATE = re.compile(r"^https://s\.click\.aliexpress\.com/")    # the owner's affiliate links, nothing else


def _usable(p: dict) -> bool:
    """A product is shown only with an affiliate link (never a plain AliExpress link that earns nothing)."""
    return bool(p.get("title") and p.get("image") and AFFILIATE.match(str(p.get("link", ""))) and p.get("price"))


products = [p for p in (load_feed("products.json", BOT_FEED_URL, "products") or {}).get("products", []) if _usable(p)][:36]   # home page "מוצרים נבחרים": 36 tiles, pinned first (the feed orders them)


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
# The owner's own videos (YouTube channel): data/videos.json. Shorts carry the product and its affiliate link.
VIDEOS = json.loads((ROOT / "data" / "videos.json").read_text(encoding="utf-8")) if (ROOT / "data" / "videos.json").exists() else []
VIDEO_BY_PID = {v["product_id"]: v for v in VIDEOS if v.get("product_id")}
BOT_STORES_URL = os.environ.get("BOT_STORES_URL") or BOT_FEED_URL.replace("/products.json", "/stores.json")
STORES_ENABLED = False                  # "חנויות במבצע" switched off 2026-10-24 (no real value to shoppers for now)
stores = []
for _s in ([] if not STORES_ENABLED else (load_feed("stores.json", BOT_STORES_URL, "stores") or {}).get("stores", [])):
    _end = parse_dt(_s.get("code", {}).get("ends") or "")
    _prods = [p for p in _s.get("products", []) if _usable(p)]
    if (not _end or _end >= NOW) and len(_prods) >= 2:
        stores.append(dict(_s, products=_prods, _end=_end))
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


ICON_SEARCH = ('<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.4" '
               'stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/></svg>')
_CAT_PATHS = {
    "phones": '<rect x="6" y="2.5" width="12" height="19" rx="2.5"/><path d="M11 18h2"/>',
    "audio": '<path d="M4 15v-3a8 8 0 0 1 16 0v3"/><path d="M4 15h3v5H5.5A1.5 1.5 0 0 1 4 18.5Zm16 0h-3v5h1.5a1.5 1.5 0 0 0 1.5-1.5Z"/>',
    "computers": '<rect x="4" y="5" width="16" height="11" rx="1.5"/><path d="M2 19.5h20"/>',
    "gaming": '<rect x="2.5" y="7" width="19" height="11" rx="5"/><path d="M7.5 11v3M6 12.5h3"/><path d="M15.5 12h.01M18 14h.01"/>',
    "smart-home": '<path d="M3.5 11 12 4l8.5 7v8.5a1 1 0 0 1-1 1h-15a1 1 0 0 1-1-1Z"/><path d="M9.5 15.2a3.5 3.5 0 0 1 5 0M12 18h.01"/>',
    "cleaning": '<path d="M18.5 3 13 10.5"/><path d="M8 11h8l1.5 10h-11Z"/><path d="M10 21v-4M14 21v-4"/>',
    "kitchen-appliances": '<path d="M13 2.5 5 13.5h6l-1 8 8-11h-6Z"/>',
    "kitchen": '<path d="M3 11h18"/><path d="M5 11v6.5A3.5 3.5 0 0 0 8.5 21h7a3.5 3.5 0 0 0 3.5-3.5V11"/><path d="M9 7.5c0-2.2 6-2.2 6 0"/>',
    "tools": '<path d="m14.5 4 5.5 5.5-3 3L11.5 7Z"/><path d="M12.8 10.2 4.5 18.5l1.9 1.9 8.3-8.3"/>',
    "car": '<path d="M5 16.5h14v-4.5l-2-5H7l-2 5Z"/><path d="M5 12h14"/><circle cx="8" cy="16.5" r="1.6"/><circle cx="16" cy="16.5" r="1.6"/>',
    "lighting": '<path d="M9 18h6M10 21.5h4"/><path d="M12 2.5a6.5 6.5 0 0 0-4 11.6V16h8v-1.9a6.5 6.5 0 0 0-4-11.6Z"/>',
    "camping": '<path d="M2.5 20.5 12 4l9.5 16.5Z"/><path d="m9 20.5 3-5.5 3 5.5"/>',
    "fitness": '<path d="M6.5 7v10M17.5 7v10M3.5 9.5v5M20.5 9.5v5M6.5 12h11"/>',
    "men": '<path d="M8.5 3.5 3.5 6.5l2 4 2-1V20.5h9V9.5l2 1 2-4-5-3a3.5 3.5 0 0 1-7 0Z"/>',
    "women": '<path d="M9.5 3h5l-1 5.5 5 12h-13l5-12Z"/><path d="M10 8.5h4"/>',
    "bags": '<rect x="5.5" y="7" width="13" height="13.5" rx="2"/><path d="M9 7V4h6v3M10 11v6M14 11v6"/>',
    "watches": '<circle cx="12" cy="12" r="5.5"/><path d="M12 9.5V12l1.8 1"/><path d="M9 6.8 9.6 3h4.8l.6 3.8M9 17.2l.6 3.8h4.8l.6-3.8"/>',
    "beauty": '<path d="M9 21h6v-8.5H9Z"/><path d="M10 12.5V7.5L14 4v8.5"/>',
    "kids": '<circle cx="12" cy="13.5" r="6.5"/><circle cx="6.5" cy="6.8" r="2"/><circle cx="17.5" cy="6.8" r="2"/><path d="M10 12.5h.01M14 12.5h.01M10.2 16s.7.8 1.8.8 1.8-.8 1.8-.8"/>',
    "pets": '<circle cx="8.5" cy="6.5" r="1.7"/><circle cx="15.5" cy="6.5" r="1.7"/><circle cx="5" cy="11.5" r="1.7"/><circle cx="19" cy="11.5" r="1.7"/><path d="M12 11.5c-3 0-5 3.2-5 5.3A2 2 0 0 0 9 19c1.1 0 1.9-.6 3-.6s1.9.6 3 .6a2 2 0 0 0 2-2.2c0-2.1-2-5.3-5-5.3Z"/>',
    "garden": '<path d="M12 21V11"/><path d="M12 11C12 6.5 8.5 4 4 4c0 4.8 3 7 8 7Zm0 2.5c0-4 3-6.5 8-6.5 0 4.3-3 6.5-8 6.5Z"/>',
    "under-50": '<path d="M3 11.5V4a1 1 0 0 1 1-1h7.5l9.5 9.5-8.5 8.5Z"/><circle cx="7.5" cy="7.5" r="1.4"/>',
}


def cat_icon(slug: str) -> str:
    """A small line icon for a category chip; a price tag for any slug the menu doesn't know yet."""
    return ('<svg class="icon cicon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round">{_CAT_PATHS.get(slug, _CAT_PATHS["under-50"])}</svg>')


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
    return f"""<form class="checker" action="{BOT}" method="get" data-bot="{BOT}" data-src="{src}" data-search="{SEARCH_URL}" data-product="{PRODUCT_URL}" novalidate>
<label for="{field_id}"{label_cls}>הדביקו לינק מאליאקספרס או כתבו מה אתם מחפשים</label>
<input type="hidden" name="start" value="{src}">
<div class="row">
<input id="{field_id}" class="q" type="search" enterkeyhint="search" autocomplete="off" spellcheck="false" placeholder="לינק או שם מוצר, למשל: סוללה ניידת" aria-describedby="{field_id}-msg">
<button class="btn" type="submit">{ICON_SEARCH}<span>חפש</span></button>
</div>
<p class="msg" id="{field_id}-msg" role="status" aria-live="polite">חפשו מוצרים או <span class="ring">הדביקו לינק מאליאקספרס להשוואה</span></p>
</form>"""


CHECKER_JS = r"""
var NB_PLATFORM = (function () { try { return JSON.parse(document.getElementById('nb-platform').textContent) || []; } catch (e) { return []; } })();
// only the owner's AliExpress links and AliExpress photos, whatever a response holds
function safeLink(u) { try { var x = new URL(u); return x.protocol === 'https:' && x.hostname === 's.click.aliexpress.com' ? x.href : ''; } catch (e) { return ''; } }  // affiliate links only
function safeImg(u) { try { var x = new URL(u); return x.protocol === 'https:' && /(^|\.)(aliexpress-media\.com|alicdn\.com|aliexpress\.com)$/i.test(x.hostname) ? x.href : ''; } catch (e) { return ''; } }
function imgTag(src, w) { var s = safeImg(src); return s ? '<img src="' + esc(s) + '_350x350.jpg" data-fallback="' + esc(s) + '" alt="" width="' + w + '" height="' + w + '" loading="lazy" referrerpolicy="no-referrer">' : ''; }
// a photo that fails in the small size falls back to the original (no inline handlers: the CSP forbids them)
document.addEventListener('error', function (ev) {
  var t = ev.target; if (t && t.tagName === 'IMG' && t.dataset.fallback) { var f = t.dataset.fallback; delete t.dataset.fallback; t.src = f; }
}, true);
function esc(t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
function priceHtml(v) { var p = Number(v).toFixed(2).split('.'); return '<span class="price"><span class="cur">₪</span><span>' + p[0] + '</span>' + (p[1] !== '00' ? '<span class="sr-only">.</span><span class="ag">' + p[1] + '</span>' : '') + '</span>'; }
function ils(v) { return '₪' + (Math.abs(v - Math.round(v)) < 0.005 ? Math.round(v) : Number(v).toFixed(2)); }
function maskCode(c) { var k = c.length > 5 ? 3 : 2; return c.slice(0, k) + '•'.repeat(Math.max(3, Math.min(5, c.length - k))); }
function couponBtn(code, kind, what, link) {
  return '<button class="tcoupon" type="button" data-code="' + esc(code) + '" data-href="' + esc(link) + '" aria-label="העתקת ' + kind + ' ופתיחת המוצר">' +
    '<span class="tc-what"><b>' + kind + '</b> ' + esc(what) + '</span><span class="tc-code"><span class="tc-txt">' + esc(maskCode(code)) + '</span><span class="tc-act">העתקה</span></span></button>';
}
function coupons(p) {
  var out = '', c = p.code;
  if (c && typeof c === 'object' && c.code && !(c.ends && new Date(c.ends.replace(' ', 'T')) < new Date())) {
    var what = c.off ? ils(c.off) + ' הנחה' : (c.pct ? Math.round(c.pct) + '% הנחה' : '');
    if (c.min && c.min > 1) what += ' מעל ' + ils(c.min);
    out += couponBtn(c.code, 'קוד מוכר', what, p.link);
  }
  var pl = NB_PLATFORM;
  if (pl.length) {
    var fit = pl.filter(function (r) { return r.min <= p.price + 0.01; });
    if (fit.length) { var r = fit.reduce(function (a, b) { return b.off > a.off ? b : a; });
      out += couponBtn(r.code, 'קוד ישראל', r.what, p.link); }
  }
  return out ? '<span class="tcoupons">' + out + '</span>' : '';
}
// a code inside a card: copy it and say so clearly, then (after a moment, so the shopper sees it) open the product
// in a new tab through the affiliate link. If the browser blocks the late open, the button becomes a plain link.
document.addEventListener('click', function (ev) {
  var b = ev.target.closest && ev.target.closest('.tcoupon'); if (!b) return;
  var href = safeLink(b.dataset.href);
  if (b.classList.contains('ready')) { if (href) window.open(href, '_blank', 'noopener'); return; }
  if (b.classList.contains('shown')) return;
  var code = b.dataset.code, txt = b.querySelector('.tc-txt'), act = b.querySelector('.tc-act'), what = b.querySelector('.tc-what');
  var done = function (ok) {
    txt.textContent = code; b.classList.add('shown');
    act.textContent = ok ? '✓ הועתק!' : 'העתיקו ידנית';
    what.innerHTML = ok ? '<b>הקוד הועתק</b> הדביקו אותו בקופה באליאקספרס' : '<b>העתיקו את הקוד</b> והדביקו אותו בקופה';
  };
  try { navigator.clipboard.writeText(code).then(function () { done(true); }, function () { done(false); }); } catch (e) { done(false); }
  if (!href) return;
  setTimeout(function () {
    var w = null;
    try { w = window.open(href, '_blank'); if (w) w.opener = null; } catch (e) {}   // (with 'noopener' it always returns null)
    if (!w) {                               // blocked: let the shopper open it with one more tap
      b.classList.add('ready'); act.textContent = 'לאליאקספרס ←';
    }
  }, 1500);
});
function codeLabel(p) {
  var c = p.code; if (!c || typeof c !== 'object') return null;
  if (c.ends && new Date(c.ends.replace(' ', 'T')) < new Date()) return null;
  if (c.min && c.min > p.price + 0.01) return 'יש קוד הנחה בבוט';
  if (c.off) return 'קוד ₪' + (Math.abs(c.off - Math.round(c.off)) < 0.005 ? Math.round(c.off) : c.off.toFixed(2)) + ' בבוט';
  if (c.pct) return 'קוד ' + Math.round(c.pct) + '% בבוט';
  return 'יש קוד הנחה בבוט';
}
document.querySelectorAll('form.checker').forEach(function (f) {
  var input = f.querySelector('input.q'), btn = f.querySelector('button'), msg = f.querySelector('.msg');
  var idle = msg.innerHTML, label = btn.querySelector('span').textContent;
  var bot = f.dataset.bot, src = f.dataset.src;
  function say(t, err) { msg.textContent = t; msg.classList.toggle('err', !!err); }
  function busy(on, t) { if (on) { btn.setAttribute('aria-busy', 'true'); btn.querySelector('span').textContent = t; } else { btn.removeAttribute('aria-busy'); btn.querySelector('span').textContent = label; } }
  input.addEventListener('input', function () { if (msg.classList.contains('err')) { msg.innerHTML = idle; msg.classList.remove('err'); } });
  // the answers appear as a chat right under the search, newest at the bottom
  function chatLog() {
    var box = document.getElementById('sresults');
    if (!box) {
      var band = f.closest('section') || f;
      box = document.createElement('section'); box.id = 'sresults'; box.className = 'sresults chat'; box.setAttribute('aria-live', 'polite');
      box.innerHTML = '<div class="wrap"><div class="chat-head"><b>התשובות שלכם</b><button type="button" class="chat-clear">ניקוי</button></div><div class="chat-log"></div></div>';
      band.insertAdjacentElement('afterend', box);
      box.querySelector('.chat-clear').addEventListener('click', function () { box.remove(); input.focus(); });
    }
    return box.querySelector('.chat-log');
  }
  function ask(text) {
    var log = chatLog();
    var me = document.createElement('div'); me.className = 'cmsg me'; me.innerHTML = '<p>' + esc(text) + '</p>'; log.appendChild(me);
    var ans = document.createElement('div'); ans.className = 'cmsg bot';
    ans.innerHTML = '<span class="cavatar" aria-hidden="true">N</span><div class="cbody"><p class="typing"><span></span><span></span><span></span></p></div>';
    log.appendChild(ans);
    me.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return ans.querySelector('.cbody');
  }
  function botLink(start) { return bot + '?start=' + start + '-' + src; }
  function tile(p) {
    p.link = safeLink(p.link); if (!p.link) return '';
    var was = p.original && p.original > p.price + 0.5 ? '<span class="was">₪' + p.original.toFixed(2) + '</span>' : '';
    var burst = p.discount && p.discount >= 5 ? '<span class="burst"><span class="sr-only">הנחה של </span>-' + Math.round(p.discount) + '%</span>' : '';
    var meta = (p.rating ? '⭐ ' + esc(p.rating) : '') + (p.sold ? (p.rating ? ' · ' : '') + esc(p.sold) + ' נמכרו' : '');
    var attrs = 'href="' + esc(p.link) + '" rel="sponsored nofollow noopener" target="_blank"';
    return '<li><div class="tile"><a class="tlink" ' + attrs + '><span class="pic">' + imgTag(p.image, 300) + '</span>' + burst +
      '<span class="tprice">' + priceHtml(p.price) + was + '</span><span class="ttl">' + esc(p.title) + '</span><span class="tfoot"><span class="cat">' + meta + '</span></span></a>' + coupons(p) +
      '<a class="cta" ' + attrs + ' tabindex="-1">לצפייה במוצר</a></div></li>';
  }
  // one product as a wide card in the answer (the pasted link, or an alternative)
  function wide(p, alt) {
    p.link = safeLink(p.link); if (!p.link) return '';
    var attrs = 'href="' + esc(p.link) + '" rel="sponsored nofollow noopener" target="_blank"';
    var was = p.original && p.original > p.price + 0.5 ? '<span class="was">₪' + p.original.toFixed(2) + '</span>' : '';
    var disc = p.discount && p.discount >= 5 ? '<span class="pill">-' + Math.round(p.discount) + '%</span>' : '';
    var meta = (p.rating ? '⭐ ' + esc(p.rating) : '') + (p.sold ? (p.rating ? ' · ' : '') + esc(p.sold) + ' נמכרו' : '');
    var save = alt && p.saving > 0.5 ? '<span class="save">חוסכים ' + ils(p.saving) + '</span>' : '';
    return '<div class="wcard' + (alt ? ' alt' : '') + '"><a class="wpic" ' + attrs + ' tabindex="-1" aria-hidden="true">' + imgTag(p.image, 160) + '</a>' +
      '<div class="wbody"><a class="wttl" ' + attrs + '>' + esc(p.title) + '</a>' +
      '<div class="wprice">' + priceHtml(p.price) + was + disc + save + '</div>' + (meta ? '<p class="wmeta">' + meta + '</p>' : '') +
      coupons(p) + '<a class="btn wbtn" ' + attrs + '>' + (alt ? 'לצפייה במוצר' : 'לקנייה באליאקספרס') + '</a></div></div>';
  }
  function fail(body, text) { body.innerHTML = '<p class="cerr">' + esc(text) + '</p><p class="cnote"><a href="' + botLink('') + '">אפשר לנסות גם בבוט בטלגרם</a></p>'; }
  function siteSearch(q) {
    var body = ask(q);
    busy(true, 'מחפש…'); say('מחפשים את הדילים הכי שווים…');
    fetch(f.dataset.search + '?q=' + encodeURIComponent(q) + '&v=2').then(function (r) {
      if (r.status === 429) throw new Error('slow'); if (!r.ok) throw new Error('bad'); return r.json();
    }).then(function (d) {
      busy(false); msg.innerHTML = idle; msg.classList.remove('err');
      var items = (d.products || []);
      if (!items.length) { body.innerHTML = '<p>לא מצאתי תוצאות טובות ל"' + esc(q) + '". נסו מילה אחרת, או באנגלית (למשל power bank).</p>'; return; }
      var coded = items.filter(function (p) { return p.coupon; }), rest = items.filter(function (p) { return !p.coupon; });
      var group = function (title, list) { return list.length ? '<h3 class="cgroup">' + title + '</h3><ul class="tiles">' + list.map(tile).join('') + '</ul>' : ''; };
      body.innerHTML = '<p>מצאתי ' + items.length + ' דילים ל"' + esc(q) + '"' + (coded.length ? ', ' + coded.length + ' מהם עם קוד קופון' : '') + ':</p>' +
        (coded.length ? group('עם קוד קופון', coded) + group('עוד דילים', rest) : '<ul class="tiles">' + rest.map(tile).join('') + '</ul>') +
        '<p class="cnote">תוצאות חיות מאליאקספרס. ייתכן שהמחיר התעדכן לנמוך יותר באליאקספרס. רוצים מוכר זול יותר למוצר מסוים? הדביקו את הלינק שלו בחיפוש. * קישורי שותפים של אליאקספרס.</p>';
      body.closest('.cmsg').classList.add('wide');
    }).catch(function (e) {
      busy(false); msg.innerHTML = idle;
      fail(body, e.message === 'slow' ? 'רגע, יותר מדי חיפושים. נסו שוב בעוד דקה.' : 'החיפוש לא זמין כרגע. נסו שוב בעוד רגע.');
    });
  }
  function linkCheck(v) {
    var body = ask(v.length > 70 ? v.slice(0, 70) + '…' : v);
    var m = v.match(/(?:\/item\/|productIds?=|[?&]id=|\/i\/)(\d{10,20})/) || v.match(/(\d{13,20})/);
    var sh = v.match(/a\.aliexpress\.[a-z.]+\/_([A-Za-z0-9]{3,40})/i);
    var start = m ? 'p_' + m[1] : (sh ? 's_' + sh[1] : '');
    body.innerHTML = '<p>בודק את המחיר והקופון, ומחפש אם מוכרים אחרים מוכרים את זה בזול יותר… (עד חצי דקה)</p><p class="typing"><span></span><span></span><span></span></p>';
    busy(true, 'בודק…'); say('בודק את הלינק שלכם…');
    fetch(f.dataset.product + '?url=' + encodeURIComponent(v)).then(function (r) {
      if (r.status === 429) throw new Error('slow'); if (!r.ok && r.status !== 400) throw new Error('bad'); return r.json();
    }).then(function (d) {
      busy(false); msg.innerHTML = idle; msg.classList.remove('err');
      if (!d.ok) { body.innerHTML = '<p class="cerr">' + esc(d.message || 'לא הצלחתי לבדוק את הלינק הזה.') + '</p>'; return; }
      var p = d.product, alts = d.alternatives || [];
      var html = '<p>זה המוצר שלכם' + (p.code && p.code.code ? ', ויש לו קוד הנחה של המוכר' : '') + ':</p>' + wide(p, false) + '<p class="cnote">ייתכן שהמחיר התעדכן לנמוך יותר באליאקספרס.</p>';
      if (alts.length) {
        html += '<p class="cgap">💡 מצאתי ' + (alts.length === 1 ? 'מוכר אחד שמוכר' : alts.length + ' מוכרים שמוכרים') + ' משהו דומה בזול יותר:</p>' + alts.map(function (a) { return wide(a, true); }).join('') +
          '<p class="cnote">שווה לוודא שזה אותו דגם ואותו מפרט לפני הקנייה.</p>';
      } else {
        html += '<p class="cgap">👌 בדקתי מוכרים אחרים ולא מצאתי את זה זול יותר עם דירוג טוב. נראה שזה כבר מחיר טוב.</p>';
      }
      html += '<p class="cnote">* קישורי שותפים של אליאקספרס.' + (start ? ' <a href="' + botLink(start) + '">להמשיך בבוט בטלגרם</a>' : '') + '</p>';
      body.innerHTML = html;
    }).catch(function (e) {
      busy(false); msg.innerHTML = idle;
      body.innerHTML = '<p class="cerr">' + (e.message === 'slow' ? 'רגע, יותר מדי בדיקות. נסו שוב בעוד דקה.' : 'לא הצלחתי לבדוק כרגע.') + '</p>' +
        (start ? '<p><a class="btn secondary" href="' + botLink(start) + '">לבדוק את המוצר בבוט בטלגרם</a></p>' : '');
    });
  }
  f.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var v = input.value.trim();
    if (!v) { say('הדביקו לינק של מוצר מאליאקספרס, או כתבו מה אתם מחפשים.', true); input.focus(); return; }
    if (btn.getAttribute('aria-busy')) return;
    var isLink = /aliexpress|aliexpi|s\.click\.ali|\d{13,}/i.test(v);
    if (!isLink) {
      if (/https?:|www\./i.test(v)) { say('זה לא לינק מאליאקספרס. באפליקציה: שיתוף ← העתק קישור.', true); input.focus(); return; }
      if (v.length < 2) { say('כתבו שם של מוצר, למשל: סוללה ניידת', true); input.focus(); return; }
      siteSearch(v); input.value = ''; return;
    }
    linkCheck(v); input.value = '';
  });
});
// count clicks out to AliExpress: only a number per day (no ids, no cookies), so the owner's dashboard can be
// compared with the clicks AliExpress reports. The bot counts them (POST /click, same origin as /product).
(function () {
  var f = document.querySelector('form.checker'), api = f && f.dataset.product;
  if (!api || !navigator.sendBeacon || /[?&]qa=1/.test(location.search)) return;
  var url = api.replace(/\/product$/, '/click');
  var OUT = 'a[href^="https://s.click.aliexpress.com/"], .tcoupon';
  function out(ev) {
    if (ev.type === 'auxclick' && ev.button !== 1) return;          // the middle button opens a tab; the right one doesn't
    var el = ev.target.closest && ev.target.closest(OUT); if (!el) return;
    var w = el.closest('.chat-log') ? 'chat' : el.classList.contains('tcoupon') ? 'code' : 'tile';
    try { navigator.sendBeacon(url + '?w=' + w); } catch (e) {}
  }
  document.addEventListener('click', out, true);
  document.addEventListener('auxclick', out, true);
})();
"""


# ------------------------------------------------------------------ layout
def _nav() -> list[tuple[str, str]]:
    """The menu. The sale events slot comes from data/events.csv: up to two running or upcoming events with a guide
    of their own; with none, the sales calendar."""
    sale = [(f"/guides/{r['guide']}/", r["nav"]) for r in events_menu] or [("/guides/sales-calendar/", "לוח המבצעים")]
    return ([("/", "ראשי"), ("/coupons/", "קודי קופון")] + ([("/videos/", "סרטונים")] if VIDEOS else []) + [("/guides/", "מדריכים")] + sale +
            [("/guides/code-not-working/", "קוד לא עובד?"), ("/about/", "אודות")])


NAV = _nav()

ORG = {"@type": "Organization", "@id": f"{SITE_URL}/#org", "name": NAME, "alternateName": ["נייס ביי", "בוטן", "Boten"],
       "url": f"{SITE_URL}/", "logo": f"{SITE_URL}/assets/logo-192.png", "sameAs": [BOT, CHANNEL, YOUTUBE]}

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
         updated: date | None = None, card: dict | None = None, tab: str | None = None) -> None:
    """full=True: body brings its own full-bleed sections. Otherwise it is a reading page, wrapped and closed with the bot invite.
    updated: the date this page's content last changed (footer, sitemap). card: what goes on the share image."""
    url = SITE_URL + path
    graph = [ORG, {"@type": "WebSite", "@id": f"{SITE_URL}/#site", "url": f"{SITE_URL}/", "name": NAME,
                   "alternateName": ["נייס ביי", "nicebuy.co.il"],
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
            f'{" aria-current=\"page\"" if path == "/c/" + c["slug"] + "/" else ""}>{cat_icon(c["slug"])}<span>{e(c["name"])}</span></a>'
            for c in categories)
        if stores:                             # stores on sale lead the strip while there are any
            chips = (f'<a class="chip hot" href="{BASE}/stores/"{" aria-current=\"page\"" if path == "/stores/" else ""}>'
                     f'🏷️ חנויות במבצע</a>') + chips
        strip = f'<nav class="cats-strip" aria-label="קטגוריות"><div class="wrap">{chips}</div></nav>'
    menubar = strip                            # the menu itself lives in the header now
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
<aside class="cta-inline"><p>יש לכם מוצר מאליאקספרס? שלחו את הלינק לבוט של NiceBuy וקבלו מחיר, הנחה וקוד קופון אם יש.</p>
<a class="btn" href="{bot_link(src=src_for('inline', path))}">{ICON_TG}פתחו את הבוט בטלגרם</a><a class="btn secondary" href="{CHANNEL}">{ICON_MEGAPHONE}לערוץ הדילים בטלגרם</a></aside>
</div>"""
    og_url, og_w, og_h = share_image(path, card)
    footer_date = f"<p>עודכן לאחרונה: {updated.strftime('%d/%m/%Y')}</p>" if updated else ""
    doc = f"""<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(tab or title)}</title>
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
<meta name="theme-color" content="#ffffff">
<link rel="preload" href="{BASE}/assets/fonts/rubik-hebrew-900-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{BASE}/assets/fonts/rubik-hebrew-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{BASE}/assets/style.css?v={CSS_VERSION}">
<script type="application/ld+json">{json_script({"@context": "https://schema.org", "@graph": graph})}</script>
</head>
<body>
<a class="skip" href="#main">דלגו לתוכן</a>
<header class="site"><div class="wrap">
<a class="logo" href="{BASE}/" aria-label="NiceBuy, לדף הבית"><span>Nice<b>Buy</b></span></a>
<nav class="menu" aria-label="ראשי">{nav}</nav>
<div class="tgs">
<a class="tg ch" href="{CHANNEL}" aria-label="ערוץ הדילים בטלגרם">{ICON_TG}<span class="long">ערוץ הדילים</span><span class="short">ערוץ</span></a>
<a class="tg" href="{bot_link(src=src_for('nav', path))}" aria-label="הבוט של NiceBuy בטלגרם">{ICON_TG}הבוט בטלגרם</a>
</div>
</div></header>
{menubar_top}
<main id="main">
{body}
</main>
<footer class="site"><div class="wrap">
<div class="links">{"".join(f'<a href="{BASE}{p}">{n}</a>' for p, n in NAV)}<a href="{bot_link(src=src_for('footer', path))}">הבוט בטלגרם</a><a href="{CHANNEL}">ערוץ הדילים</a><a href="{YOUTUBE}">יוטיוב</a></div>
<p>* גילוי נאות: חלק מהקישורים באתר ובבוט הם קישורי שותפים של אליאקספרס. על רכישה דרכם NiceBuy מקבל עמלה קטנה, והמחיר שלכם לא משתנה.</p>
<p>* NiceBuy אינו קשור לאליאקספרס ואינו מייצג אותה. AliExpress הוא סימן מסחר של בעליו. המחירים וההנחות נכונים ליום הבדיקה בלבד, אינם כוללים משלוח, ואחוזי ההנחה מחושבים לפי המחיר המקורי שמוצג באליאקספרס.</p>
<p class="legal">{"".join(f'<a href="{BASE}{p}">{n}</a>' for p, n in LEGAL)}<a href="mailto:{EMAIL}">{EMAIL}</a></p>
{footer_date}
</div></footer>
{platform_js() if js else ""}{'<script src="' + BASE + '/assets/app.js?v=' + hashlib.sha256(CHECKER_JS.encode('utf-8')).hexdigest()[:10] + '" defer></script>' if js else ""}{BEACON_HTML}
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
<li><span>קוד מוכר מהבוט</span><span class="num minus">‎-₪{code:.2f}</span></li>
</ul>
{price(final, "now")}
<p class="fine">המחיר בקופה אחרי הקוד, בלי משלוח. נבדק {d.strftime('%d/%m/%Y')}.</p>
</div>
<div class="stamp" aria-hidden="true">נבדק<small>בקופה</small></div>
</div>"""
    return f'<img src="{BASE}/assets/logo.png" alt="הלוגו של NiceBuy" width="300" height="300">'


def coupons(rows: list[dict], src: str) -> str:
    if not rows:
        return ('<div class="empty"><p><b>כרגע אין קודי מוכר מאומתים בתוקף.</b> הבוט של NiceBuy בודק כל מוצר שתשלחו ומחזיר קוד אם יש.</p>'
                f'<a class="btn" href="{bot_link(src=src)}">{ICON_TG}בדקו מוצר בבוט</a> '
                f'<a class="btn secondary" href="{CHANNEL}">{ICON_MEGAPHONE}לערוץ הדילים בטלגרם</a></div>')
    out = []
    for r in rows:
        badge = (f'<span class="sticker ok">{ICON_CHECK}נבדק בקופה</span>' if r["verified"] == "checkout"
                 else '<span class="sticker info">קוד רשמי של המוכר · לא נבדק בקופה</span>' if r["verified"] == "api"
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
<a class="go" href="{bot_link(r['product_id'], src)}">קבלו את הקוד והמחיר בבוט {ICON_ARROW}</a>
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
            what = "קוד מוכר (נשלח בבוט)"
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
        return "יש קוד הנחה בבוט"
    if off:
        return f"קוד {ils(off)} בבוט"
    if pct:
        return f"קוד {pct:.0f}% בבוט"
    return "יש קוד הנחה בבוט"


def mask_code(code: str) -> str:
    keep = 3 if len(code) > 5 else 2
    return code[:keep] + "•" * max(3, min(5, len(code) - keep))


def coupon_btn(code: str, kind: str, what: str, link: str) -> str:
    """A code inside the card: shown partly; a click copies it and opens the product (affiliate link) in a new tab."""
    return (f'<button class="tcoupon" type="button" data-code="{e(code)}" data-href="{e(link)}" '
            f'aria-label="העתקת {kind} ופתיחת המוצר">'
            f'<span class="tc-what"><b>{kind}</b> {what}</span>'
            f'<span class="tc-code"><span class="tc-txt">{e(mask_code(code))}</span><span class="tc-act">העתקה</span></span></button>')


def tile_coupons(p: dict) -> str:
    """Seller code (from the product) and the Israel platform code that fits it."""
    out, price_v, link = [], float(p["price"]), p["link"]
    c = p.get("code") if isinstance(p.get("code"), dict) else None
    ends = parse_dt((c or {}).get("ends") or "")
    if c and c.get("code") and not (ends and ends < NOW):
        off, pct, minimum = num(c.get("off")), num(c.get("pct")), num(c.get("min"))
        what = f"{ils(off)} הנחה" if off else (f"{pct:.0f}% הנחה" if pct else "")
        if minimum and minimum > 1:
            what += f" מעל {ils(minimum)}"
        out.append(coupon_btn(c["code"], "קוד קופון" if p.get("owner_code") else "קוד מוכר", what.strip(), link))
    if p.get("owner_code"):                    # a code the owner added in the bot (🎟️): show only that code
        return f'<span class="tcoupons">{"".join(out)}</span>' if out else ""
    # The owner can fix the Israel code for a product he added (feed field "il_code"); while that code is active it
    # replaces the automatic tier, otherwise the card falls back to the tier that fits the price.
    fixed = str(p.get("il_code") or "").strip().upper()
    r = next((x for x in platform_active if x["code"].upper() == fixed), None) if fixed else None
    r = r or platform_for(price_v)
    if r:
        out.append(coupon_btn(r["code"], "קוד ישראל", platform_what(r), link))
    return f'<span class="tcoupons">{"".join(out)}</span>' if out else ""


def platform_js() -> str:
    data = [{"code": r["code"], "off": r["_off"], "min": r["_min"], "what": platform_what(r)} for r in platform_active]
    return f'<script type="application/json" id="nb-platform">{json_script(data)}</script>'


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
            cat = '<span class="cat pick">בחירה של NiceBuy</span>'
        when = iso_dt(p.get("checked") or p.get("posted"))
        asof = f'<span class="asof">נכון ל-{when.strftime("%d/%m")}</span>' if when else ""
        coupons = tile_coupons(p)
        note = f'<span class="tnote">{e(str(p["owner_note"])[:60])}</span>' if p.get("owner_note") else ""
        temp = p.get("temp_price")            # the owner's temporary price, set in the bot (⏳ on the channel post)
        if temp:
            try:
                note += f'<span class="ttemp">מוצר ראשון ב-₪{float(temp):.2f}</span>'
            except (TypeError, ValueError):
                pass
        attrs = f'href="{e(p['link'])}" rel="sponsored nofollow noopener" target="_blank"'
        vid = VIDEO_BY_PID.get(str(p.get("id")))
        vtag = (f'<a class="vtag" href="{yt_url(vid)}" target="_blank" rel="noopener">▶ סרטון שלנו<span class="sr-only">: '
                f'{e(vid["title"])} (נפתח ביוטיוב)</span></a>') if vid else ""
        tiles.append(f"""<li><div class="tile">{vtag}
<a class="tlink" {attrs}>
<span class="pic"><img src="{e(p['image'])}" alt="" width="300" height="300" loading="lazy" decoding="async" referrerpolicy="no-referrer"></span>
{burst}
<span class="tprice">{price(price_v)}{was}</span>
{note}<span class="ttl">{e(short_title(p['title']))}</span>
<span class="tfoot">{cat}{asof}</span>
</a>
{coupons}
<a class="cta" {attrs} tabindex="-1">{ICON_CART}לצפייה במוצר</a>
</div></li>""")
    return f'<ul class="tiles">{"".join(tiles)}</ul>'


# ------------------------------------------------------------------ pages
HERO_ART = (f'<img class="art art-bag" src="{BASE}/assets/hero-bag.jpg" alt="" width="690" height="724" decoding="async">'
            '<svg class="art art-badge" viewBox="0 0 80 80" aria-hidden="true">'
            '<path d="M40 4l8 7 10-2 4 10 10 4-2 10 7 8-7 8 2 10-10 4-4 10-10-2-8 7-8-7-10 2-4-10-10-4 2-10-7-8 7-8-2-10 10-4 4-10 10 2Z" fill="#4F46E5"/>'
            '<path d="M30 52l20-24" stroke="#fff" stroke-width="5" stroke-linecap="round"/><circle cx="31" cy="31" r="5" fill="none" stroke="#fff" stroke-width="4"/>'
            '<circle cx="49" cy="49" r="5" fill="none" stroke="#fff" stroke-width="4"/></svg>')


def hero(src: str, main_heading: bool, compact: bool = False) -> str:
    """The yellow band with the price checker. On the home page its title is the page's h1; elsewhere the page
    keeps its own h1, so the band's title is a styled paragraph (one h1 per page). Inner pages get the slim band:
    a line and the checker, so the page's own answer is on the first phone screen."""
    if compact:
        return f"""<section class="hero compact" aria-labelledby="hero-title"><div class="wrap">
<p id="hero-title" class="hero-title">יש לכם לינק? <em>NiceBuy בודק.</em></p>
{checker(src, compact=True)}
</div></section>"""
    tag = "h1" if main_heading else "p"
    return f"""<section class="hero" aria-labelledby="hero-title"><div class="wrap">
<div class="hero-copy">
<{tag} id="hero-title" class="hero-title">המוצרים <em>הכי שווים</em> ברשת</{tag}>
<p class="lead">קופונים, מבצעים והנחות שיחסכו לכם כסף!</p>
</div>
{checker(src)}
{HERO_ART}
</div></section>"""


# The date someone last changed each page's own text here in build.py (data-driven parts date themselves).
EDITED = {"/": "2026-11-08", "/videos/": "2026-11-08", "/coupons/": "2026-10-21", "/guides/": "2026-10-21", "/guides/coupon-types/": "2026-10-20",
          "/guides/code-not-working/": "2026-10-20", "/about/": "2026-11-08",
          "/accessibility/": "2026-11-03", "/privacy/": "2026-11-06", "/terms/": "2026-11-03"}


def event_card() -> tuple[str, str, str]:
    """The first "before you buy" card: the next sale event with a guide of its own, else the sales calendar."""
    for r in events_menu:
        if r.get("card_title"):
            return f"/guides/{r['guide']}/", r["card_title"], r.get("card_text", "")
    return "/guides/sales-calendar/", "לוח המבצעים: מתי הכי משתלם לקנות", "כל אירועי המבצעים של השנה, ומה כדאי לקנות בכל אחד."


def event_marks() -> list[datetime]:
    """Moments when the sale-event content changed on its own (an event entered the menu or ended)."""
    return [d for r in events for d in (r["_from"], r["_end"]) if d and d <= NOW]


def yt_url(v: dict) -> str:
    return f"https://www.youtube.com/{'shorts/' + v['yt'] if v['kind'] == 'short' else 'watch?v=' + v['yt']}"


def _dur(iso: str) -> str:
    m = re.fullmatch(r"PT(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    return f"{int(m.group(1) or 0)}:{int(m.group(2) or 0):02d}" if m else ""


VIDEO_NOTE = "המחיר נקבע באליאקספרס ומשתנה. המחיר בסרטון הוא מה ששילמתי בזמן הקנייה."


def video_cards(rows: list[dict], wide: bool = False) -> str:
    """The owner's videos as cards: the picture opens the video on YouTube, the button opens the product (affiliate)."""
    out = []
    for v in rows:
        w, h = (640, 360) if v["kind"] != "short" else (360, 640)
        btn = (f'<a class="btn" href="{e(v["link"])}" rel="sponsored nofollow noopener" target="_blank">{ICON_CART}לצפייה במוצר</a>'
               f'<p class="vnote">{VIDEO_NOTE}</p>') if v.get("link") else \
              f'<a class="btn secondary" href="{yt_url(v)}" target="_blank" rel="noopener">לצפייה ביוטיוב</a>'
        out.append(f"""<li class="vcard{' wide' if v['kind'] != 'short' else ''}">
<a class="vthumb" href="{yt_url(v)}" target="_blank" rel="noopener"><img src="{BASE}/assets/videos/{e(v['yt'])}.jpg" alt="" width="{w}" height="{h}" loading="lazy" decoding="async"><span class="play" aria-hidden="true">▶</span><span class="dur">{_dur(v.get('duration', ''))}</span><span class="sr-only">צפייה ביוטיוב: {e(v['title'])}</span></a>
<div class="vbody"><h3>{e(v['title'])}</h3><p class="vtext">{e(v.get('text', ''))}</p>{btn}</div>
</li>""")
    return f'<ul class="{"vgrid" if wide else "vrow"}">{"".join(out)}</ul>'


def build_videos():
    path = "/videos/"
    if not VIDEOS:
        return
    shorts = [v for v in VIDEOS if v["kind"] == "short"]
    longs = [v for v in VIDEOS if v["kind"] != "short"]
    schema = [{"@type": "VideoObject", "name": v["title"], "description": v.get("text") or v["title"],
               "thumbnailUrl": f"{SITE_URL}/assets/videos/{v['yt']}.jpg", "uploadDate": v["date"],
               "duration": v.get("duration"), "contentUrl": yt_url(v),
               "embedUrl": f"https://www.youtube.com/embed/{v['yt']}"} for v in VIDEOS]
    body = f"""<header class="page-head"><h1>סרטונים: מוצרים שבדקנו בעצמנו</h1>
<p class="lead">קונים, מצלמים ומראים איך המוצר נראה באמת, לפני שאתם קונים. כל הסרטונים גם ב<a href="{YOUTUBE}">ערוץ היוטיוב שלנו</a>.</p></header>
{('<section aria-labelledby="ep-title"><h2 id="ep-title">פרקים</h2>' + video_cards(longs, wide=True) + '</section>') if longs else ''}
<section aria-labelledby="sh-title"><h2 id="sh-title">סרטונים קצרים</h2>
{video_cards(shorts, wide=True)}
</section>
<p class="tiles-note">{VIDEO_NOTE} הכפתור "לצפייה במוצר" הוא קישור שותפים: המחיר שלכם לא משתנה.</p>"""
    page(path, f"סרטונים: מוצרים מאליאקספרס שבדקנו בעצמנו | {NAME}",
         "סרטונים קצרים של מוצרים מאליאקספרס שקנינו ובדקנו בעצמנו, עם קישור ישיר למוצר.",
         body, crumbs=[(path, "סרטונים")], schema=schema, updated=latest(EDITED[path], *[v["date"] for v in VIDEOS]),
         card={"lines": [("סרטונים", "ink"), ("בדקנו בעצמנו", "red")], "sub": "מוצרים מאליאקספרס בשימוש אמיתי"})


def build_home():
    path = "/"
    ev_url, ev_title, ev_text = event_card()
    tiles = ""
    if products:
        tiles = f"""<section aria-labelledby="hot-title">
<div class="sec-head"><h2 id="hot-title">מוצרים נבחרים</h2><a href="{CHANNEL}">כל הדילים בערוץ {ICON_ARROW}</a></div>
{product_tiles(products, path)}
<p class="tiles-note">ייתכן שהמחיר התעדכן לנמוך יותר באליאקספרס. המחירים נכונים לתאריך שמופיע על כל מוצר, ועשויים להשתנות. לחיצה על מוצר פותחת אותו באליאקספרס (קישור שותפים: המחיר שלכם לא משתנה).</p>
</section>"""
    vids = ""
    if VIDEOS:
        recent = [v for v in VIDEOS if v["kind"] == "short"][:6]
        vids = f"""<section class="vids" aria-labelledby="vids-title">
<div class="sec-head"><h2 id="vids-title"><span class="pl" aria-hidden="true">▶</span>בדקנו בעצמנו</h2><a href="{BASE}/videos/">כל הסרטונים {ICON_ARROW}</a></div>
{video_cards(recent)}
</section>"""
    deals = ""
    if seller:                 # no verified seller code in force = no section: an empty box here says nothing useful
        deals = f"""<section aria-labelledby="deals-title">
<h2 id="deals-title">קודי מוכר שנבדקו</h2>
<p class="lead">קודי מוכר שנבדקו, עם תאריך. את הקוד עצמו מקבלים בבוט, יחד עם המחיר המעודכן.</p>
{coupons(seller[:4], src_for("deal", path))}
</section>"""
    body = f"""{hero(src_for('hero', path), True)}
<!--MENUBAR-->

<div class="wrap">
{vids}

{tiles}

{deals}

<section aria-labelledby="guides-title">
<div class="sec-head"><h2 id="guides-title">מדריכים מומלצים</h2><a href="{BASE}/guides/">כל המדריכים {ICON_ARROW}</a></div>
<ul class="guide-list">
<li><a class="guide-card" href="{BASE}{ev_url}"><b>{e(ev_title)}</b><span>{e(ev_text)}</span></a></li>
<li><a class="guide-card" href="{BASE}/guides/customs-tax/"><b>מכס ומע"מ: הפטור הוא 75 דולר</b><span>מה משלמים, מתי, ומה זה כלל 72 השעות.</span></a></li>
<li><a class="guide-card" href="{BASE}/guides/shipping-israel/"><b>משלוח לישראל: חינם מ-139 ש"ח</b><span>כמה זמן לוקח ומה עושים כשהמעקב נתקע.</span></a></li>
</ul>
</section>

</div>

<section class="closer" aria-labelledby="closer-title"><div class="wrap">
<div><h2 id="closer-title">יש לכם לינק? NiceBuy בודק.</h2>
<p>חינם, בטלגרם, בלי הרשמה. והדילים הכי טובים של השבוע מחכים בערוץ.</p></div>
<div class="actions"><a class="btn" href="{bot_link(src=src_for('closer', path))}">{ICON_TG}פתחו את הבוט בטלגרם</a>
<a class="btn secondary" href="{CHANNEL}">{ICON_MEGAPHONE}לערוץ הדילים בטלגרם</a></div>
</div></section>"""
    updated = latest(EDITED[path], *[p.get("checked") or p.get("posted") for p in products],
                     *[r["_date"] for r in checks], *[r.get("checked") for r in seller],
                     *[r["_end"] for r in read_csv_ends("seller_codes.csv")], *event_marks())
    page(path, f"אל תשלמו יקר באליאקספרס | {NAME}",
         "השוואת מחירים: מדביקים לינק של מוצר, ו-NiceBuy מוצא מוכרים אחרים שמוכרים אותו בפחות, עם קודי קופון שמורידים עוד מהמחיר.",
         body, full=True, js=True, updated=updated, tab=NAME,     # the browser tab shows the name only (owner)
         card={"lines": [("המוצרים", "ink"), ("הכי שווים", "red"), ("ברשת", "ink")],
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
    bot_btn = f'<a class="btn secondary" href="{bot_link(src=src_for("actions", path))}">{ICON_TG}בדקו מוצר בבוט</a>'
    nxt = events_live[0] if events_live else None

    # --- Israel platform codes (ILAFF): active set, or the last one
    if platform_active:
        end = min(r["_end"] for r in platform_active)
        prow = "".join(f"<tr><td><code class=\"code\">{e(r['code'])}</code></td><td>{platform_amt(r, 'off')}</td>"
                       f"<td>מעל {platform_amt(r, 'min')}</td></tr>" for r in platform_active)
        open_end = any(r.get("status") == "no-end-date" for r in platform_active)
        until = "פעיל כרגע (אליאקספרס לא פרסמה תאריך סיום)" if open_end else f"פעיל עד {fmt_d(end, True)}"
        platform_html = (f"<p><b>סט קודי ישראל {until}.</b> מזינים קוד אחד, לפי הסכום בסל אחרי הנחות.</p>"
                         f'<div class="table-wrap"><table class="codes"><thead><tr><th>קוד</th><th>הנחה</th><th>מינימום לסל</th>'
                         f"</tr></thead><tbody>{prow}</tbody></table></div>")
        answer_now = ("יש כרגע קודי ישראל פעילים, ראו בטבלה." if open_end
                      else f"יש סט פעיל של קודי ישראל עד {fmt_d(end, True)}, ראו בטבלה.")
    else:
        last = sorted([r for r in platform_all if r["_end"] and r["_end"] < NOW], key=lambda r: r["_min"])
        prow = "".join(f"<tr><td><code class=\"code bad\">{e(r['code'])}</code></td><td>{platform_amt(r, 'off')}</td>"
                       f"<td>מעל {platform_amt(r, 'min')}</td><td><span class=\"sticker bad\">{ICON_X}פג תוקף</span></td></tr>" for r in last)
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
         + f"לכל מוצר אחר אפשר לשלוח את הלינק <a href=\"{bot_link(src=src_for('faq', path))}\">לבוט</a>, והוא מחזיר קוד מוכר אם יש."),
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
         f'שולחים את הלינק של המוצר <a href="{bot_link(src=src_for("faq", path))}">לבוט בטלגרם</a>. הוא בודק את המוצר ומחזיר מחיר בשקלים, '
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
<li><b>קוד מוכר</b>: עובד רק על המוצרים של מוכר מסוים. לדוגמה: ₪12.65 הנחה בקנייה מעל ₪126.55 על סוללה של Essager. את הקוד למוצר מסוים מקבלים בבוט.</li>
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
                         '<p class="tiles-note">ייתכן שהמחיר התעדכן לנמוך יותר באליאקספרס. המחירים נכונים לתאריך שמופיע על כל מוצר. קישורי שותפים: המחיר שלכם לא משתנה.</p>')
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
                    '<p class="tiles-note">ייתכן שהמחיר התעדכן לנמוך יותר באליאקספרס. NiceBuy בוחר לכל קטגוריה את הדילים הכי שווים לפי מחיר, הנחה, דירוג ומכירות, '
                    'ומעדכן אותם כמה פעמים ביום. המחירים עשויים להשתנות. לחיצה פותחת את המוצר באליאקספרס '
                    '(קישור שותפים: המחיר שלכם לא משתנה).</p>')
        else:
            grid = ('<div class="empty"><p><b>NiceBuy עוד מחפש את הדילים לקטגוריה הזו.</b> בינתיים אפשר לשלוח לו לינק '
                    'של כל מוצר ולקבל מחיר, הנחה וקוד אם יש.</p>'
                    f'<a class="btn" href="{bot_link(src=src_for("empty", url))}">{ICON_TG}בדקו מוצר בבוט</a> '
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
             f"הדילים הכי שווים ב{c['name']} מאליאקספרס, ש-NiceBuy בחר לפי מחיר, הנחה, דירוג ומכירות. מחיר בשקלים, מתעדכן כמה פעמים ביום.",
             body, crumbs=[(url, c["name"])], schema=schema, updated=updated,
             card={"lines": [(c["name"], "ink")], "sub": "הדילים של השבוע מאליאקספרס, מחיר בשקלים",
                   "products": c["products"][:3]})
        if not c["products"]:                             # no thin pages in the sitemap
            SITEMAP[:] = [(u, d) for u, d in SITEMAP if u != SITE_URL + url]


def build_stores():
    """Stores with a worthwhile seller code this week, each with its best sellers (from the bot's weekly scan)."""
    url = "/stores/"
    if not stores:
        return
    blocks = []
    for s_ in stores:
        c = s_["code"]
        off = num(c.get("off")); pct = num(c.get("pct")); minimum = num(c.get("min"))
        amount = ils(off) if off else (f"{pct:.0f}%" if pct else "")
        cond = f" בקנייה מעל {ils(minimum)} מהחנות" if minimum and minimum > 1 else ""
        until = f" · בתוקף עד {s_['_end'].strftime('%d/%m')}" if s_.get("_end") else ""
        shop_btn = (f'<a class="btn secondary" href="{e(s_["link"])}" rel="sponsored nofollow noopener" target="_blank">'
                    f'{ICON_CART}לחנות באליאקספרס</a>' if s_.get("link") else "")
        code_btn = (f'<a class="btn" href="{bot_link(c.get("product"), src_for("deal", url))}">{ICON_TG}קבלו את הקוד בבוט</a>'
                    if c.get("product") else "")
        blocks.append(f"""<section class="store" aria-label="{e(s_['name'])}">
<div class="sec-head"><h2>{e(s_['name'])}</h2></div>
<p class="store-deal"><b>קוד מוכר: {amount} הנחה</b>{cond}{until}</p>
<div class="actions">{code_btn} {shop_btn}</div>
{product_tiles(s_['products'], url)}
</section>""")
    stamp = iso_dt((FEEDS.get("stores.json") or {}).get("updated"))
    body = f"""<header class="page-head"><h1>חנויות במבצע באליאקספרס</h1>
<span class="updated">{"עודכן: " + fmt_d(stamp, True) + " · " if stamp else ""}מתעדכן פעם בשבוע</span></header>
<p class="lead">חנויות שיש להן השבוע קוד הנחה של המוכר ששווה לפחות ₪20, עם המוצרים הנמכרים שלהן. בדרך כלל הקוד חל על כל החנות: אפשר לשלב כמה מוצרים מאותה חנות כדי להגיע למינימום. את הקוד עצמו מקבלים בבוט. קודים רשמיים של המוכרים, לא נבדקו בקופה.</p>
{"".join(blocks)}
<p class="tiles-note">ייתכן שהמחיר התעדכן לנמוך יותר באליאקספרס. המוצרים הם הנמכרים ביותר של כל חנות מתוך מה ש-NiceBuy סרק השבוע. המחירים נכונים לתאריך על כל מוצר. קישורי שותפים: המחיר שלכם לא משתנה.</p>"""
    page(url, f"חנויות במבצע באליאקספרס: קודי מוכר מעל ₪20 | {NAME}",
         "חנויות באליאקספרס עם קוד הנחה של המוכר ששווה לפחות ₪20 השבוע, והמוצרים הנמכרים שלהן. מתעדכן פעם בשבוע.",
         body, crumbs=[(url, "חנויות במבצע")], updated=stamp.date() if stamp else None,
         card={"lines": [("חנויות במבצע", "ink"), ("באליאקספרס", "red")], "sub": "קודי מוכר מעל ₪20 והמוצרים הנמכרים",
               "products": [p for s_ in stores for p in s_["products"][:1]][:3]})


def build_accessibility():
    path = "/accessibility/"
    updated = latest(EDITED[path]) or NOW.date()
    body = f"""<header class="page-head"><h1>הצהרת נגישות</h1></header>
<div class="prose">
<p class="lead">ב-NiceBuy רוצים שכל אחד ואחת יוכלו לחפש מוצרים, להשוות מחירים ולמצוא קודי קופון בקלות, כולל אנשים עם מוגבלות. השקענו בהנגשת האתר ונמשיך לשפר אותו.</p>
<h2>רמת הנגישות באתר</h2>
<p>האתר הותאם לדרישות תקנות שוויון זכויות לאנשים עם מוגבלות (התאמות נגישות לשירות), התשע"ג-2013, ולתקן הישראלי ת"י 5568, שמבוסס על הנחיות WCAG 2.0 ברמה AA.</p>
<h2>מה הונגש באתר</h2>
<ul>
<li>ניווט מלא במקלדת, עם סימון ברור של הרכיב שנמצא בפוקוס, וקישור "דלגו לתוכן" בתחילת כל עמוד.</li>
<li>מבנה עמוד תקני (כותרות, אזורי ניווט, רשימות) שמאפשר שימוש בקוראי מסך.</li>
<li>שפת העמוד וכיוון הקריאה מוגדרים לעברית מימין לשמאל, וטקסטים באנגלית מסומנים בשפתם.</li>
<li>לשדה החיפוש יש תווית, ותשובות החיפוש מוקראות לקורא המסך כשהן מופיעות.</li>
<li>ניגודיות צבעים מספקת בין הטקסט לרקע.</li>
<li>האתר מותאם לטלפון ולהגדלת תצוגה עד 400% בלי גלילה לרוחב.</li>
<li>תמונות שמשמשות לקישוט מוסתרות מקוראי מסך, ולכפתורים ולקישורים יש שם ברור.</li>
<li>האתר עובר בדיקה אוטומטית לפי WCAG 2.1 ברמה AA, ונבדק ידנית בניווט במקלדת.</li>
</ul>
<p>האתר לא משתמש ב"תוסף נגישות". ההתאמות בנויות בקוד האתר עצמו.</p>
<p>האתר נבדק בדפדפן Chrome במחשב ובתצוגת טלפון.</p>
<h2>חלקים שאינם בשליטתנו</h2>
<ul>
<li><b>אליאקספרס:</b> לחיצה על מוצר מעבירה לאתר אליאקספרס. הקנייה, התשלום והמשלוח נעשים שם, והנגישות של אתר אליאקספרס באחריותה.</li>
<li><b>תמונות ופרטי מוצרים:</b> התמונות ותיאורי המוצרים מגיעים מהמוכרים באליאקספרס. שמות המוצרים בעברית מתורגמים אוטומטית, ולכן ייתכן שלא כל תיאור יהיה מדויק.</li>
<li><b>טלגרם:</b> הבוט וערוץ הדילים פועלים בתוך אפליקציית טלגרם, והנגישות של הממשק עצמו תלויה בטלגרם.</li>
</ul>
<h2>נתקלתם בבעיה? דברו איתנו</h2>
<p>אם משהו באתר לא נגיש לכם, או שאתם צריכים מידע בדרך אחרת, נשמח לעזור ולתקן. כדי שנוכל לטפל מהר, כתבו לנו מה ניסיתם לעשות, באיזה עמוד, ובאיזה דפדפן או טכנולוגיה מסייעת השתמשתם.</p>
<ul>
<li>איש קשר לנגישות: צוות NiceBuy</li>
<li>מייל: <a href="mailto:{EMAIL}">{EMAIL}</a></li>
<li>או דרך <a href="{bot_link(src=src_for('inline', path))}">הבוט בטלגרם</a></li>
</ul>
<p>הצהרת הנגישות עודכנה לאחרונה ב-{updated.strftime("%d/%m/%Y")}.</p>
</div>"""
    page(path, f"הצהרת נגישות | {NAME}", "רמת הנגישות של אתר NiceBuy, ההתאמות שבוצעו, והדרך לפנות אלינו בנושא נגישות.",
         body, crumbs=[(path, "הצהרת נגישות")], updated=updated,
         card={"lines": [("הצהרת נגישות", "ink")], "sub": "NiceBuy"})


def build_privacy():
    path = "/privacy/"
    updated = latest(EDITED[path]) or NOW.date()
    body = f"""<header class="page-head"><h1>מדיניות פרטיות</h1></header>
<div class="prose">
<p class="lead">NiceBuy לא צריך לדעת מי אתם כדי לעזור לכם לקנות בזול. כאן מוסבר בדיוק איזה מידע עובר דרכנו, למה, ומה אנחנו עושים איתו.</p>
<h2>מה אנחנו לא עושים</h2>
<ul>
<li>לא מבקשים שם, טלפון, מייל או פרטי תשלום, ואין באתר הרשמה.</li>
<li>לא משתמשים בעוגיות (cookies) למעקב או לפרסום.</li>
<li>לא מוכרים מידע ולא מעבירים אותו למפרסמים.</li>
</ul>
<h2>איזה מידע עובר דרכנו</h2>
<ul>
<li><b>מה שאתם מקלידים בחיפוש:</b> שם מוצר או לינק מאליאקספרס נשלחים לשרת שלנו כדי למצוא תוצאות. כדי להבין את החיפוש ולבחור מוצרים מתאימים, טקסט החיפוש ושמות המוצרים נשלחים גם לשירות בינה מלאכותית (Anthropic). אנחנו שומרים סטטיסטיקה מצטברת של מילות חיפוש, למשל כמה פעמים חיפשו "מטען נייד", כדי לשפר את התוצאות. הסטטיסטיקה לא מקושרת לאדם מסוים.</li>
<li><b>מידע טכני:</b> כמו בכל אתר, ספקי התשתית שלנו רושמים ביומני השרת את כתובת ה-IP, סוג הדפדפן ושעת הגישה. בכתובת ה-IP אנחנו משתמשים גם כדי להגביל עומס, למשל מספר חיפושים בדקה, והיא נשמרת לשם כך בזיכרון זמני בלבד.</li>
<li><b>הבוט בטלגרם:</b> הבוט מקבל מטלגרם את מזהה המשתמש ואת ההודעות שאתם שולחים לו, ומשתמש בהם כדי לענות לכם ולהגביל עומס. אנחנו לא שומרים מאגר של משתמשים, והבוט שולח הודעות רק בתגובה לפנייה שלכם.</li>
<li><b>סטטיסטיקת ביקורים:</b> אנחנו משתמשים ב-Cloudflare Web Analytics כדי לדעת כמה ביקורים יש באתר, באילו דפים ומאיזה סוג מקור (למשל גוגל או טלגרם). הכלי לא משתמש בעוגיות, לא שומר מזהה של מבקר ולא עוקב אחריכם בין אתרים.</li>
<li><b>פנייה במייל:</b> אם תכתבו לנו, נשתמש בכתובת ובתוכן הפנייה רק כדי לענות לכם.</li>
</ul>
<h2>מי מעבד את המידע בשבילנו</h2>
<p>אנחנו נעזרים בספקים שמעבדים את המידע רק לצורך הפעלת השירות: GitHub (אחסון האתר), Cloudflare (שרתי שמות, אבטחה וסטטיסטיקת ביקורים), Railway (השרת של הבוט והחיפוש), Anthropic (בינה מלאכותית לחיפוש) וטלגרם (הבוט והערוץ). חלק מהספקים פועלים מחוץ לישראל. יומני השרת נשמרים לתקופה מוגבלת, לפי מדיניות כל ספק.</p>
<h2>מעבר לאליאקספרס</h2>
<p>לחיצה על מוצר מעבירה אתכם לאליאקספרס דרך קישור שותפים. מרגע המעבר חלה עליכם מדיניות הפרטיות של אליאקספרס, שעשויה להשתמש בעוגיות, למשל כדי לשייך את הרכישה לקישור. לרכישות ולפרטים שאתם מוסרים באליאקספרס אין לנו גישה.</p>
<h2>הזכויות שלכם</h2>
<p>אתם יכולים לבקש לעיין במידע עליכם, לתקן אותו או למחוק אותו, במייל <a href="mailto:{EMAIL}">{EMAIL}</a>. מכיוון שאנחנו לא שומרים מידע מזהה, ברוב המקרים לא יהיה מידע כזה.</p>
<h2>עדכונים</h2>
<p>אם נשנה את המדיניות, נעדכן את העמוד הזה ואת התאריך שבסופו. עודכן לאחרונה ב-{updated.strftime("%d/%m/%Y")}.</p>
</div>"""
    page(path, f"מדיניות פרטיות | {NAME}", "איזה מידע עובר דרך NiceBuy, למה, ומה הזכויות שלכם.",
         body, crumbs=[(path, "מדיניות פרטיות")], updated=updated,
         card={"lines": [("מדיניות פרטיות", "ink")], "sub": "NiceBuy"})


def build_terms():
    path = "/terms/"
    updated = latest(EDITED[path]) or NOW.date()
    body = f"""<header class="page-head"><h1>תנאי שימוש</h1></header>
<div class="prose">
<p class="lead">השימוש באתר NiceBuy ובבוט "בוטן" בטלגרם (להלן "השירות") כפוף לתנאים האלה. השימוש בשירות מהווה הסכמה להם. התנאים מנוסחים בלשון רבים ומתייחסים לכל המגדרים.</p>
<h2>מה השירות עושה</h2>
<p>NiceBuy הוא שירות מידע חינמי שמציג מוצרים, מחירים וקודי קופון מאליאקספרס ומשווה בין מוכרים. NiceBuy אינו מוכר מוצרים, אינו צד לעסקה, ואינו קשור לאליאקספרס ואינו מייצג אותה.</p>
<h2>קנייה באליאקספרס</h2>
<p>הקנייה, התשלום, המשלוח, האחריות, הביטולים וההחזרות נעשים מול אליאקספרס והמוכר, לפי התנאים שלהם ולפי הדין. בכל בעיה בהזמנה יש לפנות לאליאקספרס או למוכר.</p>
<h2>מחירים וקודי קופון</h2>
<ul>
<li>המחירים, ההנחות וקודי הקופון נלקחים מאליאקספרס ונכונים לתאריך שמופיע לידם. אליאקספרס והמוכרים יכולים לשנות אותם בכל רגע, והמחיר הקובע הוא המחיר שמוצג בקופה.</li>
<li>המחירים אינם כוללים משלוח, ובמקרים מסוימים גם מיסים שחלים ביבוא.</li>
<li>אחוזי ההנחה מחושבים לפי המחיר המקורי שאליאקספרס מציגה.</li>
<li>קודי קופון מוגבלים בכמות ובתנאים של אליאקספרס, ולכן גם קוד שנבדק עלול להפסיק לעבוד.</li>
<li>שמות המוצרים בעברית ותוצאות החיפוש וההשוואה נוצרים בחלקם באופן אוטומטי. כדאי לוודא בעמוד המוצר שזה אותו דגם ואותו מפרט לפני הקנייה.</li>
</ul>
<h2>קישורי שותפים</h2>
<p>הקישורים לאליאקספרס הם קישורי שותפים. על רכישה דרכם NiceBuy מקבל עמלה מאליאקספרס, והמחיר שלכם לא משתנה.</p>
<h2>אחריות</h2>
<p>השירות ניתן כמות שהוא (AS IS). אנחנו משתדלים שהמידע יהיה מדויק ועדכני, אבל לא מתחייבים לכך, ולא נישא באחריות לנזק שנגרם מהסתמכות על המידע, מרכישה באליאקספרס או מהפסקה בשירות, במידה שהדין מאפשר זאת.</p>
<h2>שימוש הוגן</h2>
<p>אין להשתמש בשירות באופן אוטומטי או מסיבי (למשל רובוטים או סריקה), אין לנסות לפגוע בו, ואין להעתיק את תוכנו לשימוש מסחרי בלי אישור.</p>
<h2>קניין רוחני</h2>
<p>העיצוב, הטקסטים, המדריכים והקוד של NiceBuy שייכים ל-NiceBuy. תמונות ופרטי המוצרים שייכים לבעליהם ומוצגים מאליאקספרס. AliExpress הוא סימן מסחר של בעליו.</p>
<h2>כללי</h2>
<p>אנחנו רשאים לעדכן את התנאים מעת לעת. על התנאים חל הדין הישראלי. לשאלות: <a href="mailto:{EMAIL}">{EMAIL}</a>. עודכן לאחרונה ב-{updated.strftime("%d/%m/%Y")}.</p>
</div>"""
    page(path, f"תנאי שימוש | {NAME}", "תנאי השימוש באתר NiceBuy ובבוט: מה השירות עושה, מחירים, קישורי שותפים ואחריות.",
         body, crumbs=[(path, "תנאי שימוש")], updated=updated,
         card={"lines": [("תנאי שימוש", "ink")], "sub": "NiceBuy"})


def build_about():
    path = "/about/"
    updated = latest(EDITED[path]) or NOW.date()
    body = f"""<header class="page-head"><h1>אודות NiceBuy</h1></header>
<div class="prose">
<p class="lead">NiceBuy הוא אתר ובוט טלגרם חינמי שעוזרים לקנות באליאקספרס בפחות.</p>
<p>הבוט בודק כל מוצר שמדביקים לו ומחזיר מחיר בשקלים, הנחה וקוד מוכר אם יש, ומציע חלופות זולות יותר. בטלגרם הבוט נקרא בוטן (@Boten_IL_bot). באתר אנחנו מפרסמים רק מה שנבדק, עם תאריך, ומתעדים גם קודים שלא עבדו.</p>
<h2>גילוי נאות</h2>
<p>הקישורים לאליאקספרס בבוט ובאתר הם קישורי שותפים. על רכישה דרכם NiceBuy מקבל עמלה קטנה מאליאקספרס, והמחיר שלכם לא משתנה. NiceBuy אינו קשור לאליאקספרס ואינו מייצג אותה.</p>
<h2>פרטיות</h2>
<p>האתר לא משתמש בעוגיות מעקב, והבוט לא שולח הודעות שלא ביקשתם. כל הפרטים ב<a href="{BASE}/privacy/">מדיניות הפרטיות</a>.</p>
<h2>יצירת קשר</h2>
<p>במייל <a href="mailto:{EMAIL}">{EMAIL}</a> או דרך <a href="{bot_link(src=src_for('inline', path))}">הבוט בטלגרם</a>. דילים חדשים מתפרסמים ב<a href="{CHANNEL}">ערוץ הדילים</a>.</p>
</div>"""
    page(path, f"אודות וגילוי נאות | {NAME}", "מי אנחנו, איך NiceBuy עובד, גילוי נאות על קישורי שותפים ופרטיות.",
         body, crumbs=[(path, "אודות")], updated=updated,
         card={"lines": [("אודות NiceBuy", "ink")], "sub": "בוט טלגרם חינמי שבודק מחירים וקודים באליאקספרס"})


def build_404():
    body = f"""<div class="notfound">
<span class="price now" aria-hidden="true">404</span>
<h1>המבצע הזה כבר נגמר</h1>
<p class="lead">הדף שחיפשתם לא קיים, או שהוסר. אבל הבוט עדיין בודק כל מוצר.</p>
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
        f"# {NAME}\n\n> קודי קופון לאליאקספרס בישראל שנבדקו בקופה, ובוט טלגרם חינמי (@Boten_IL_bot) שבודק כל מוצר.\n\n"
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
    (OUT / "assets" / "app.js").write_text(CHECKER_JS, encoding="utf-8")
    for f in [*ROOT.glob("google*.html"), *ROOT.glob("BingSiteAuth.xml")]:   # Google / Bing site verification files
        shutil.copy(f, OUT / f.name)
    try:                                          # product photos for the share cards, fetched in parallel
        import share_cards
        share_cards.prefetch([p["image"] for p in products[:3]] +
                             [p["image"] for c in categories for p in c["products"][:3]], OUT)
    except Exception as ex:
        print(f"share cards: no prefetch ({ex})")
    build_home(); build_coupons_page(); build_coupon_types(); build_not_working(); build_guides(); build_categories(); build_stores(); build_about(); build_videos(); build_accessibility(); build_privacy(); build_terms(); build_404()
    build_meta_files()
    print(f"built {len(SITEMAP)} pages into {OUT} (base={BASE or '/'}), {len(seller)} seller codes, "
          f"{len(platform_active)} platform codes active, {len(events_live)} sale events ahead")


if __name__ == "__main__":
    main()
