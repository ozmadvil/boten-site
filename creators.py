"""Creators who work with NiceBuy: what data/creators.json holds, checked, for build.py to turn into pages.

A topic ("nails") has creators; a creator has the products she works with; a product may have her video and a
short text in her words. Three kinds of page come out of it (build.py: build_creators):
    /<topic>/                       the topic: its creators and their products
    /<topic>/<creator>/             one creator: who she is, her products
    /<topic>/<creator>/<product>/   one product: her video, the price and the link, her text

The file says who and what; today's price and the affiliate link (made with the creator's own tracking ID, so
her orders are counted apart) come from the bot's /picks when the site is built.

What must be true before anything of a creator is shown, and is checked here:
  - "videos_ok": the date the creator agreed in writing that their videos and name appear on the site;
  - the line about the creator ("about") is shown only with "about_ok", and a product's "text" and "quote" only
    with "text_ok": the dates the creator approved the wording written in their name;
  - a video is shown only when its address is a YouTube, Instagram or TikTok video this file can embed.
Anything that fails a check is left out with a line in the build log; a bad entry never breaks the build.

"demo": true marks a made-up creator, for showing what a page looks like before anyone has signed: no consent
dates are asked of it, and build.py marks its pages as an example, keeps them out of search engines and the
sitemap, and links to them from nowhere.
"""
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
TRACKING = re.compile(r"[A-Za-z][A-Za-z0-9_]{1,31}")
FILE = re.compile(r"[a-z0-9][a-z0-9/_-]*\.(?:jpg|jpeg|png|webp)")
# top-level paths the site already uses: a topic may not take one of them
RESERVED = {"c", "assets", "feed", "guides", "coupons", "videos", "about", "privacy", "terms", "accessibility", "stores", "og", "404"}
SOCIAL = {"instagram": ("instagram.com",), "tiktok": ("tiktok.com",), "youtube": ("youtube.com", "youtu.be")}
NAMES = {"youtube": "יוטיוב", "instagram": "אינסטגרם", "tiktok": "טיקטוק"}
FROM = {"youtube": "מיוטיוב", "instagram": "מאינסטגרם", "tiktok": "מטיקטוק"}


def a_date(v) -> str:
    """"2026-11-19" when v is a real date that is not in the future, else "". A consent or an approval is
    something that already happened."""
    try:
        d = date.fromisoformat(str(v))
    except (TypeError, ValueError):
        return ""
    return d.isoformat() if d <= date.today() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(v)) else ""


def _host(url: str) -> str:
    if not re.fullmatch(r"https://[A-Za-z0-9:/._@?=&%+~-]{4,300}", url or ""):   # no backslash, quote, space or bracket:
        return ""                                    # a browser and this code must read the same host out of it
    try:
        p = urlsplit(url)
    except ValueError:
        return ""
    return (p.hostname or "").lower().removeprefix("www.").removeprefix("m.") if not p.username and "@" not in p.netloc else ""


def embed(url: str) -> dict | None:
    """{"kind", "id", "src" (the player to put in an iframe), "watch" (the video on its own site), "tall"} for a
    YouTube, Instagram or TikTok video address; None for anything else. The ids are checked character by
    character, because they go into the page as part of an address."""
    host, p = _host(url or ""), urlsplit(url or "")
    parts = [x for x in p.path.split("/") if x]
    if host == "youtu.be" and parts:
        vid, tall = parts[0], False
    elif host == "youtube.com" and parts[:1] == ["watch"]:
        vid, tall = (parse_qs(p.query).get("v") or [""])[0], False
    elif host == "youtube.com" and len(parts) >= 2 and parts[0] in ("shorts", "embed", "live"):
        vid, tall = parts[1], parts[0] == "shorts"
    else:
        vid = None
    if vid is not None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", vid):
            return None
        return {"kind": "youtube", "id": vid, "tall": tall, "src": f"https://www.youtube-nocookie.com/embed/{vid}?autoplay=1&rel=0",
                "watch": f"https://www.youtube.com/{'shorts/' if tall else 'watch?v='}{vid}"}
    if host == "instagram.com":
        # /reel/<code>/, /p/<code>/, /tv/<code>/, also behind a user name: /<user>/reel/<code>/. Nothing else:
        # /share/reel/<x>/ carries a share code, not the video's, and /reels/audio/<n>/ is not a video at all
        at = 1 if len(parts) >= 3 and parts[0] not in ("reel", "reels", "p", "tv", "share", "explore", "stories") else 0
        if len(parts) >= at + 2 and parts[at] in ("reel", "reels", "p", "tv") and re.fullmatch(r"[A-Za-z0-9_-]{5,40}", parts[at + 1]) \
                and parts[at + 1] != "audio":
            code, kind = parts[at + 1], "p" if parts[at] == "p" else "reel"
            return {"kind": "instagram", "id": code, "tall": True, "src": f"https://www.instagram.com/{kind}/{code}/embed/",
                    "watch": f"https://www.instagram.com/{kind}/{code}/"}
        return None
    if host == "tiktok.com":
        # /@user/video/<digits>  (a short vm.tiktok.com link hides the id: the full address is needed)
        for i, x in enumerate(parts[:-1]):
            if x == "video" and re.fullmatch(r"\d{8,25}", parts[i + 1]):
                vid = parts[i + 1]
                user = parts[i - 1] if i and re.fullmatch(r"@[A-Za-z0-9_.]{1,40}", parts[i - 1]) else "@_"
                return {"kind": "tiktok", "id": vid, "tall": True, "src": f"https://www.tiktok.com/player/v1/{vid}?autoplay=1&rel=0",
                        "watch": f"https://www.tiktok.com/{user}/video/{vid}"}
        return None
    return None


def social(kind: str, url: str) -> str | None:
    """The creator's own profile address, only on the network it claims to be on."""
    return url if _host(url or "") in SOCIAL[kind] else None


def _list(v) -> list:
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def load(path: Path, assets: Path, say=print) -> dict:
    """{"topics": [{slug, name, h1, lead, people, chip, creators: [...]}]} with only what passed the checks.
    Missing, broken or wrongly shaped file: no topics, and a line in the log; the build goes on."""
    if not path.exists():
        return {"topics": []}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ex:
        say(f"creators: {path.name} not read ({ex})")
        return {"topics": []}
    if not isinstance(raw, dict):
        say(f"creators: {path.name} is not an object with topics and creators, nothing used")
        return {"topics": []}
    topics, seen_topics = [], set()
    for t in _list(raw.get("topics")):
        slug = str(t.get("slug") or "")
        if not SLUG.fullmatch(slug) or slug in RESERVED or slug in seen_topics or not str(t.get("name") or "").strip():
            say(f"creators: topic {slug!r} skipped (slug taken, reserved or not a-z0-9-; or no name)")
            continue
        seen_topics.add(slug)
        topics.append({"slug": slug, "name": str(t["name"]).strip()[:40], "h1": str(t.get("h1") or t["name"]).strip()[:90],
                       "lead": str(t.get("lead") or "").strip()[:200], "people": str(t.get("people") or "").strip()[:30],
                       "chip": str(t.get("chip") or "").strip()[:30], "creators": []})
    by_slug = {t["slug"]: t for t in topics}
    seen, tracking_of = set(), {}
    for c in _list(raw.get("creators")):
        slug, topic, name = str(c.get("slug") or ""), by_slug.get(str(c.get("topic") or "")), str(c.get("name") or "").strip()[:60]
        tid, demo = str(c.get("tracking") or ""), c.get("demo") is True
        why = ("slug not a-z0-9-" if not SLUG.fullmatch(slug) else "unknown topic" if not topic else "no name" if not name else
               "slug used twice" if (topic["slug"], slug) in seen else "tracking id missing or malformed" if not TRACKING.fullmatch(tid) else
               "tracking id already used by another creator" if tid.lower() in tracking_of else
               "no videos_ok date (the creator's written consent; a real date, not in the future)" if not demo and not a_date(c.get("videos_ok")) else "")
        if why:
            say(f"creators: creator {slug or name!r} skipped: {why}")
            continue
        seen.add((topic["slug"], slug))
        tracking_of[tid.lower()] = slug
        photo = str(c.get("photo") or "")
        if photo and not (FILE.fullmatch(photo) and (assets / photo).is_file()):
            say(f"creators: {slug}: photo {photo[:60]!r} not found under assets/ or badly named, the initial is shown")
            photo = ""
        about = str(c.get("about") or "").strip()[:160]
        if about and not demo and not a_date(c.get("about_ok")):
            say(f"creators: {slug}: the line about the creator is not shown, no about_ok date (the creator's approval of it)")
            about = ""
        prods, seen_p, seen_id = [], set(), set()
        for p in _list(c.get("products")):
            ps, pid, pname = str(p.get("slug") or ""), str(p.get("id") or ""), str(p.get("name") or "").strip()[:70]
            why = ("slug not a-z0-9-" if not SLUG.fullmatch(ps) else "slug used twice" if ps in seen_p else
                   "product id not a number" if not re.fullmatch(r"\d{6,20}", pid) else "product listed twice" if pid in seen_id else
                   "no name" if not pname else "")
            if why:
                say(f"creators: {slug}: product {ps or pid!r} skipped: {why}")
                continue
            seen_p.add(ps); seen_id.add(pid)
            video = embed(str(p.get("video") or "")) if p.get("video") else None
            if p.get("video") and not video:
                say(f"creators: {slug}/{ps}: video address not understood, shown without a video: {str(p['video'])[:80]!r}")
            approved = demo or bool(a_date(p.get("text_ok")))
            if p.get("text") and not isinstance(p.get("text"), list):
                say(f"creators: {slug}/{ps}: text must be a list of paragraphs, not shown")
            text = [str(x).strip()[:900] for x in p["text"] if str(x).strip()][:6] if isinstance(p.get("text"), list) else []
            if (text or p.get("quote")) and not approved:
                say(f"creators: {slug}/{ps}: text and quote not shown, no text_ok date (the creator's approval of the wording)")
                text = []
            poster = str(p.get("poster") or "")
            if poster and not (FILE.fullmatch(poster) and (assets / poster).is_file()):
                say(f"creators: {slug}/{ps}: poster {poster[:60]!r} not found under assets/ or badly named, the product photo is shown")
                poster = ""
            prods.append({"slug": ps, "id": pid, "name": pname, "video": video, "poster": poster, "text": text,
                          "quote": str(p.get("quote") or "").strip()[:90] if approved else ""})
        if len(prods) > 40:                               # /picks answers up to 40 products at a time
            say(f"creators: {slug}: {len(prods)} products, only the first 40 are used")
            prods = prods[:40]
        links = {k: social(k, str(c.get(k) or "")) for k in SOCIAL}
        for k in SOCIAL:
            if c.get(k) and not links[k]:
                say(f"creators: {slug}: {k} address not shown (not an https address on that network): {str(c[k])[:60]!r}")
        topic["creators"].append({"slug": slug, "name": name, "about": about, "tracking": tid, "demo": demo,
                                  "since": "" if demo else a_date(c.get("videos_ok")),
                                  "photo": photo, "links": {k: v for k, v in links.items() if v}, "products": prods})
    return {"topics": topics}
