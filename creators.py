"""Creators who work with NiceBuy: what data/creators.json holds, checked, for build.py to turn into pages.

A topic ("nails") has creators; a creator has the products she works with; a product may have her video and a
short text in her words. Three kinds of page come out of it (build.py: build_creators):
    /<topic>/                       the topic: its creators and their products
    /<topic>/<creator>/             one creator: who she is, her products
    /<topic>/<creator>/<product>/   one product: her video, the price and the link, her text

The file says who and what; today's price and the affiliate link (made with the creator's own tracking ID, so
her orders are counted apart) come from the bot's /picks when the site is built.

What must be true before anything of a creator is shown, and is checked here:
  - "videos_ok": the date she agreed in writing that her videos and name appear on the site;
  - a product's "text" is shown only with "text_ok", the date she approved the wording written in her name;
  - a video is shown only when its address is a YouTube, Instagram or TikTok video this file can embed.
Anything that fails a check is left out with a line in the build log; a bad entry never breaks the build.
"""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*$")
TRACKING = re.compile(r"[A-Za-z][A-Za-z0-9_]{1,31}$")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")
RESERVED = {"c", "assets", "feed", "guides", "coupons", "videos", "about", "privacy", "terms", "accessibility", "stores"}
SOCIAL = {"instagram": ("instagram.com",), "tiktok": ("tiktok.com",), "youtube": ("youtube.com", "youtu.be")}
NAMES = {"youtube": "יוטיוב", "instagram": "אינסטגרם", "tiktok": "טיקטוק"}


def _host(url: str) -> str:
    try:
        p = urlsplit(url)
    except ValueError:
        return ""
    return (p.hostname or "").lower().removeprefix("www.").removeprefix("m.") if p.scheme == "https" else ""


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
        # /reel/<code>/, /p/<code>/, /tv/<code>/, also behind a user name: /<user>/reel/<code>/
        for i, x in enumerate(parts[:-1]):
            if x in ("reel", "reels", "p", "tv") and re.fullmatch(r"[A-Za-z0-9_-]{5,40}", parts[i + 1]):
                code = parts[i + 1]
                kind = "p" if x == "p" else "reel"
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
    return url if _host(url or "") in SOCIAL[kind] and len(url) <= 200 and '"' not in url and "<" not in url else None


def load(path: Path, assets: Path, say=print) -> dict:
    """{"topics": [{slug, name, h1, lead, creators: [...]}]} with only what passed the checks. Missing or broken
    file: no topics."""
    if not path.exists():
        return {"topics": []}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ex:
        say(f"creators: {path.name} not read ({ex})")
        return {"topics": []}
    topics, seen_topics = [], set()
    for t in raw.get("topics") or []:
        slug = str(t.get("slug") or "")
        if not SLUG.match(slug) or slug in RESERVED or slug in seen_topics or not str(t.get("name") or "").strip():
            say(f"creators: topic {slug!r} skipped (slug taken, reserved or not a-z0-9-; or no name)")
            continue
        seen_topics.add(slug)
        topics.append({"slug": slug, "name": str(t["name"]).strip(), "h1": str(t.get("h1") or t["name"]).strip(),
                       "lead": str(t.get("lead") or "").strip(), "people": str(t.get("people") or "").strip()[:30],
                       "chip": str(t.get("chip") or "").strip()[:30], "creators": []})
    by_slug = {t["slug"]: t for t in topics}
    seen, tracking_of = set(), {}
    for c in raw.get("creators") or []:
        slug, topic, name = str(c.get("slug") or ""), by_slug.get(str(c.get("topic") or "")), str(c.get("name") or "").strip()
        tid = str(c.get("tracking") or "")
        why = ("slug not a-z0-9-" if not SLUG.match(slug) else "unknown topic" if not topic else "no name" if not name else
               "slug used twice" if (topic["slug"], slug) in seen else "tracking id missing or malformed" if not TRACKING.match(tid) else
               "tracking id already used by another creator" if tid in tracking_of else
               "no videos_ok date (her written consent)" if not DATE.match(str(c.get("videos_ok") or "")) else "")
        if why:
            say(f"creators: creator {slug or name!r} skipped: {why}")
            continue
        seen.add((topic["slug"], slug))
        tracking_of[tid] = slug
        photo = str(c.get("photo") or "")
        photo = photo if re.fullmatch(r"[a-z0-9][a-z0-9/_-]*\.(?:jpg|jpeg|png|webp)", photo) and (assets / photo).is_file() else ""
        prods, seen_p, seen_id = [], set(), set()
        for p in c.get("products") or []:
            ps, pid, pname = str(p.get("slug") or ""), str(p.get("id") or ""), str(p.get("name") or "").strip()
            why = ("slug not a-z0-9-" if not SLUG.match(ps) else "slug used twice" if ps in seen_p else
                   "product id not a number" if not re.fullmatch(r"\d{6,20}", pid) else "product listed twice" if pid in seen_id else
                   "no name" if not pname else "")
            if why:
                say(f"creators: {slug}: product {ps or pid!r} skipped: {why}")
                continue
            seen_p.add(ps); seen_id.add(pid)
            video = embed(str(p.get("video") or "")) if p.get("video") else None
            if p.get("video") and not video:
                say(f"creators: {slug}/{ps}: video address not understood, shown without a video: {str(p['video'])[:80]!r}")
            text = [str(x).strip() for x in (p.get("text") or []) if str(x).strip()] if isinstance(p.get("text"), list) else []
            if text and not DATE.match(str(p.get("text_ok") or "")):
                say(f"creators: {slug}/{ps}: text not shown, no text_ok date (her approval of the wording)")
                text = []
            poster = str(p.get("poster") or "")
            poster = poster if re.fullmatch(r"[a-z0-9][a-z0-9/_-]*\.(?:jpg|jpeg|png|webp)", poster) and (assets / poster).is_file() else ""
            prods.append({"slug": ps, "id": pid, "name": pname, "video": video, "poster": poster, "text": text,
                          "quote": str(p.get("quote") or "").strip()[:90] if text or DATE.match(str(p.get("text_ok") or "")) else ""})
        if len(prods) > 40:                               # /picks answers up to 40 products at a time
            say(f"creators: {slug}: {len(prods)} products, only the first 40 are used")
            prods = prods[:40]
        links = {k: social(k, str(c.get(k) or "")) for k in SOCIAL}
        topic["creators"].append({"slug": slug, "name": name, "about": str(c.get("about") or "").strip()[:160], "tracking": tid,
                                  "photo": photo, "links": {k: v for k, v in links.items() if v}, "products": prods})
    return {"topics": topics}
