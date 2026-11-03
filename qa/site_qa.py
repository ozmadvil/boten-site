"""End-to-end check of the chat on the live site, the way a shopper uses it: type a search or paste a link in the
hero field, wait for the answer, and check what is on the screen. Runs in GitHub Actions (qa.yml); writes
qa/out/report.json and a few screenshots.

Checks per search: answered in time, number of products, every product has an AliExpress affiliate link, a price,
a Hebrew title and a loaded photo, no duplicates, prices under a typed price limit, coupon buttons well formed.
Checks per link: the right kind of answer (product + cheaper sellers, or a clear message), the same link checks.
Also: answers on a phone screen without sideways scrolling, several shoppers at once, the too-many-requests
message, and JavaScript errors on the page.
"""
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

SITE = sys.argv[1] if len(sys.argv) > 1 else "https://nicebuy.co.il/"
OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)
HEB = re.compile(r"[֐-׿]")

SEARCHES = [
    ("מטען נייד", None), ("אוזניות עד 100 שקל", 100), ("כיסוי לאייפון 16 פרו", None), ("שואב אבק", None),
    ("מקלדת אלחוטית בעברית", None), ("מתנה לגבר", None), ("airpods", None), ("שעון חכם עד 200 ש\"ח", 200),
    ("asdfgh", None),
]
LINKS = [  # (case, what is pasted, expected: "product" | "error" | "client")
    ("normal link", "https://www.aliexpress.com/item/1005005875379717.html", "product"),
    ("Hebrew site with tracking params",
     "https://he.aliexpress.com/item/1005008557791071.html?spm=a2g0o.productlist.main.1&algo_pvid=abc&pdp_npi=4", "product"),
    ("mobile link", "https://m.aliexpress.com/item/1005007805694170.html", "product"),
    ("product number only", "1005005912594648", "product"),
    ("link inside shared text", "שימו לב למוצר הזה! https://www.aliexpress.com/item/1005007096963554.html?sourceType=1 תודה", "product"),
    ("NiceBuy's own affiliate link (from the channel)", "https://s.click.aliexpress.com/e/_c33uJpK3", "any"),
    ("Amazon link", "https://www.amazon.com/dp/B0CHX1W1XY", "client"),
    ("product that does not exist", "https://www.aliexpress.com/item/1005000000000001.html", "error"),
]


def price_of(text: str):
    m = re.search(r"(\d[\d,]*\.?\d*)", (text or "").replace(",", ""))
    return float(m.group(1)) if m else None


def check_items(items, cap=None) -> list[str]:
    problems = []
    titles = [i["title"].strip() for i in items]
    for n, it in enumerate(items, 1):
        if "s.click.aliexpress.com" not in it["link"]:
            problems.append(f"#{n}: link is not an affiliate link ({it['link'][:60]})")
        p = price_of(it["price"])
        if p is None or p <= 0:
            problems.append(f"#{n}: no price ({it['price']!r})")
        elif cap and p > cap + 0.01:
            problems.append(f"#{n}: ₪{p} is over the typed limit ₪{cap}")
        if not HEB.search(it["title"]):
            problems.append(f"#{n}: title not in Hebrew ({it['title'][:50]!r})")
        if not it["img"]:
            problems.append(f"#{n}: photo did not load")
        if any(not c or len(c) < 3 for c in it["coupons"]):
            problems.append(f"#{n}: coupon button without a code")
    dups = {t for t in titles if t and titles.count(t) > 1}
    if dups:
        problems.append(f"duplicate titles: {list(dups)[:3]}")
    return problems


def load_photos(ans):
    """Photos are lazy (they load when scrolled to): load them now, then the check is about the photo itself."""
    try:
        ans.evaluate("""async a => { const imgs = [...a.querySelectorAll('img')]; imgs.forEach(i => { i.loading = 'eager'; });
            await Promise.race([Promise.all(imgs.map(i => i.complete ? 1 : new Promise(r => { i.onload = i.onerror = r; }))),
                                new Promise(r => setTimeout(r, 12000))]); }""")
    except Exception:
        pass


def ask(page, text, timeout=75):
    """Type into the hero field, submit, wait for the newest answer to finish. Returns (seconds, answer element)."""
    before = page.locator(".cmsg.bot").count()
    page.fill("input.q", text)
    t0 = time.time()
    page.press("input.q", "Enter")
    try:
        page.wait_for_function(
            "n => { const a = document.querySelectorAll('.cmsg.bot'); return a.length > n && !a[a.length-1].querySelector('.typing'); }",
            arg=before, timeout=timeout * 1000)
    except Exception:
        return time.time() - t0, None
    return time.time() - t0, page.locator(".cmsg.bot").last


def main():
    report = {"site": SITE, "at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "searches": [], "links": [],
              "checks": []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(locale="he-IL", viewport={"width": 1280, "height": 900})
        # mark the test's requests (qa=1) so the bot doesn't count them as visitors' searches
        ctx.route(re.compile(r".*/(search|product)\?.*"), lambda route: route.continue_(url=route.request.url + "&qa=1"))
        page = ctx.new_page()
        console_errors = []
        page.on("console", lambda m: console_errors.append(m.text[:200]) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append(str(e)[:200]))
        page.goto(SITE, wait_until="networkidle")

        for q, cap in SEARCHES:
            secs, ans = ask(page, q)
            case = {"query": q, "seconds": round(secs, 1)}
            if ans is None:
                case.update(ok=False, problems=["no answer in time"])
            else:
                text = ans.inner_text()[:300]
                load_photos(ans)
                items = ans.evaluate("""a => [...a.querySelectorAll('.tile')].map(e => ({
                        title: (e.querySelector('.ttl')||{}).textContent||'', price: (e.querySelector('.tprice .price')||{}).textContent||'',
                        link: (e.querySelector('a.tlink')||{}).href||'',
                        img: (() => { const i = e.querySelector('img'); return i ? (i.complete && i.naturalWidth > 0) : false; })(),
                        coupons: [...e.querySelectorAll('.tcoupon')].map(b => b.dataset.code||'') }))""")
                problems = check_items(items, cap)
                if q == "asdfgh":
                    if items:
                        problems.append("nonsense search returned products")
                elif len(items) < 4:
                    problems.append(f"only {len(items)} products")
                if secs > 30:
                    problems.append(f"slow: {secs:.0f}s")
                case.update(ok=not problems, n=len(items), problems=problems, answer=text[:160],
                            titles=[i["title"][:60] for i in items[:10]],
                            prices=[price_of(i["price"]) for i in items[:10]])
            report["searches"].append(case)
            page.wait_for_timeout(8000)                          # stay under 8 searches a minute

        page.screenshot(path=str(OUT / "search.png"), full_page=False)

        for name, link, expect in LINKS:
            if expect == "client":
                page.fill("input.q", link)
                page.press("input.q", "Enter")
                page.wait_for_timeout(800)
                msg = page.inner_text(".checker .msg")
                ok = "לא לינק מאליאקספרס" in msg
                report["links"].append({"case": name, "ok": ok, "answer": msg[:120],
                                        "problems": [] if ok else ["no clear message for a non-AliExpress link"]})
                continue
            secs, ans = ask(page, link, timeout=70)
            case = {"case": name, "seconds": round(secs, 1)}
            if ans is None:
                case.update(ok=False, problems=["no answer in time"])
            else:
                text = ans.inner_text()
                load_photos(ans)
                err = ans.locator(".cerr").count() > 0
                wide = ans.evaluate("""a => [...a.querySelectorAll('.wcard')].map(e => ({
                    title: (e.querySelector('.wttl')||{}).textContent||'', price: (e.querySelector('.wprice .price')||{}).textContent||'',
                    link: (e.querySelector('a.wttl')||{}).href||'', alt: e.classList.contains('alt'),
                    save: (e.querySelector('.save')||{}).textContent||'',
                    img: (() => { const i = e.querySelector('img'); return i ? (i.complete && i.naturalWidth > 0) : false; })(),
                    coupons: [...e.querySelectorAll('.tcoupon')].map(b => b.dataset.code||'') }))""")
                problems = []
                if expect == "product":
                    if err or not wide:
                        problems.append("no product answer: " + text[:100].replace("\n", " "))
                    # the pasted product and a cheaper seller of the same product rightly share a name
                    problems += [x for x in check_items(wide) if not x.startswith("duplicate")] + \
                        [x for x in check_items([w for w in wide if w["alt"]]) if x.startswith("duplicate")]
                    base = price_of(wide[0]["price"]) if wide else None
                    for a in wide[1:]:
                        p = price_of(a["price"])
                        if base and p and p >= base:
                            problems.append(f"'cheaper' seller is not cheaper: ₪{p} vs ₪{base}")
                elif expect == "error":
                    if not err:
                        problems.append("expected a clear error message")
                    if "undefined" in text or "null" in text:
                        problems.append("raw error text shown")
                if secs > 45:
                    problems.append(f"slow: {secs:.0f}s")
                case.update(ok=not problems, problems=problems, answer=text[:200].replace("\n", " "),
                            alternatives=sum(1 for w in wide if w["alt"]),
                            cards=[{"title": w["title"][:60], "price": price_of(w["price"]), "save": w["save"]} for w in wide])
            report["links"].append(case)
            page.wait_for_timeout(11000)                         # stay under 6 link checks a minute

        page.screenshot(path=str(OUT / "link.png"), full_page=False)

        # phone screen: an answer must fit without sideways scrolling
        phone = browser.new_context(locale="he-IL", viewport={"width": 390, "height": 844}, is_mobile=True,
                                    has_touch=True, device_scale_factor=2)
        phone.route(re.compile(r".*/(search|product)\?.*"), lambda route: route.continue_(url=route.request.url + "&qa=1"))
        pp = phone.new_page()
        pp.goto(SITE, wait_until="networkidle")
        secs, ans = ask(pp, "שעון חכם")
        overflow = pp.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        pp.screenshot(path=str(OUT / "phone.png"), full_page=False)
        report["checks"].append({"case": "phone screen answer", "ok": bool(ans) and overflow <= 1,
                                 "problems": ([] if ans else ["no answer"]) + ([f"page scrolls sideways by {overflow}px"] if overflow > 1 else [])})
        phone.close()

        # several shoppers at once: 4 searches at the same moment, each must get products in time
        page.wait_for_timeout(60000)                             # fresh minute for the rate limit
        together = page.evaluate("""async () => { const url = document.querySelector('form.checker').dataset.search;
            const qs = ['מנורת לילה', 'בקבוק תרמי', 'פנס ראש', 'מחזיק טלפון לרכב'];
            return Promise.all(qs.map(async q => { const t = performance.now();
                try { const r = await fetch(url + '?q=' + encodeURIComponent(q) + '&qa=1');
                      const d = r.ok ? await r.json() : {};
                      return {query: q, status: r.status, n: (d.products || []).length, seconds: Math.round((performance.now() - t) / 100) / 10}; }
                catch (e) { return {query: q, status: 0, n: 0, seconds: 0}; } })); }""")
        report["checks"].append({"case": "4 shoppers at the same moment",
                                 "ok": all(t["status"] == 200 and t["n"] >= 4 and t["seconds"] <= 45 for t in together),
                                 "problems": [f"{t['query']}: status {t['status']}, {t['n']} products, {t['seconds']}s"
                                              for t in together if not (t["status"] == 200 and t["n"] >= 4 and t["seconds"] <= 45)],
                                 "detail": together})
        page.wait_for_timeout(60000)

        # too many searches: the shopper must see a friendly message, not a broken page
        burst = page.evaluate("""async () => { const url = document.querySelector('form.checker').dataset.search;
            return Promise.all([...Array(12).keys()].map(i => fetch(url + '?q=' + encodeURIComponent('כבל ' + i) + '&qa=1')
                .then(x => x.status).catch(() => 0))); }""")      # 12 at once from one visitor: over the 8/minute limit
        secs, ans = ask(page, "מטען לרכב", timeout=40)
        txt = ans.inner_text() if ans else ""
        friendly = ("יותר מדי" in txt) or (ans is not None and ans.locator(".tile").count() > 0)
        report["checks"].append({"case": "too many searches", "ok": friendly and 429 in burst,
                                 "problems": ([] if 429 in burst else ["no rate limit (429) after 12 searches at once"]) +
                                             ([] if friendly else ["no friendly message: " + txt[:80]]),
                                 "statuses": burst})

        real_errors = [e for e in console_errors if "status of 429" not in e]   # the 429s are the rate-limit test's own
        report["checks"].append({"case": "JavaScript errors", "ok": not real_errors, "problems": real_errors[:10]})
        browser.close()

    allc = report["searches"] + report["links"] + report["checks"]
    report["passed"] = sum(1 for c in allc if c.get("ok"))
    report["total"] = len(allc)
    report["score"] = round(report["passed"] / max(1, report["total"]), 3)
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"SITE QA: {report['passed']}/{report['total']} passed")
    for c in allc:
        if not c.get("ok"):
            print(" FAIL", c.get("query") or c.get("case"), "|", "; ".join(c.get("problems", []))[:300])


if __name__ == "__main__":
    main()
