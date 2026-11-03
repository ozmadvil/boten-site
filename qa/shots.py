"""Marketing screenshots of the live site on a phone (1080x1920), for video tools' reference images."""
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

SITE = "https://nicebuy.co.il/"
OUT = Path(__file__).parent / "shots"
OUT.mkdir(exist_ok=True)


def wait_answer(page, before, timeout=75):
    page.wait_for_function("n => { const a = document.querySelectorAll('.cmsg.bot'); return a.length > n && !a[a.length-1].querySelector('.typing'); }",
                           arg=before, timeout=timeout * 1000)
    page.evaluate("""async () => { const imgs = [...document.querySelectorAll('img')]; imgs.forEach(i => i.loading = 'eager');
        await Promise.race([Promise.all(imgs.map(i => i.complete ? 1 : new Promise(r => { i.onload = i.onerror = r; }))), new Promise(r => setTimeout(r, 12000))]); }""")


with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(locale="he-IL", viewport={"width": 360, "height": 640}, device_scale_factor=3, is_mobile=True, has_touch=True)
    ctx.route(re.compile(r".*/(search|product)\?.*"), lambda r: r.continue_(url=r.request.url + "&qa=1"))
    p = ctx.new_page()
    p.goto(SITE, wait_until="networkidle")
    p.wait_for_timeout(1500)
    p.screenshot(path=str(OUT / "1-home.png"))                                     # hero + search
    p.evaluate("window.scrollTo(0, document.querySelector('.tiles').getBoundingClientRect().top + scrollY - 80)")
    p.wait_for_timeout(1500)
    p.screenshot(path=str(OUT / "2-deals.png"))                                    # product cards with coupons
    p.evaluate("window.scrollTo(0, 0)")
    n = p.locator(".cmsg.bot").count()
    p.fill("input.q", "https://www.aliexpress.com/item/1005008557791071.html")    # a link: product + cheaper sellers
    p.press("input.q", "Enter")
    wait_answer(p, n)
    p.locator(".cmsg.bot").last.scroll_into_view_if_needed()
    p.evaluate("document.querySelector('.cmsg.bot:last-of-type .wcard').scrollIntoView({block: 'start'}); window.scrollBy(0, -70)")
    p.wait_for_timeout(800)
    p.screenshot(path=str(OUT / "3-compare.png"))
    p.evaluate("const c = document.querySelectorAll('.cmsg.bot:last-of-type .wcard.alt'); if (c.length) { c[0].scrollIntoView({block: 'start'}); window.scrollBy(0, -90); }")
    p.wait_for_timeout(800)
    p.screenshot(path=str(OUT / "4-cheaper.png"))
    time.sleep(10)
    n = p.locator(".cmsg.bot").count()
    p.fill("input.q", "אוזניות אלחוטיות")                                        # a search: product grid in the chat
    p.press("input.q", "Enter")
    wait_answer(p, n)
    p.evaluate("const a = document.querySelectorAll('.cmsg.bot'); a[a.length-1].scrollIntoView({block: 'start'}); window.scrollBy(0, -60)")
    p.wait_for_timeout(800)
    p.screenshot(path=str(OUT / "5-search.png"))
    d = b.new_context(locale="he-IL", viewport={"width": 1440, "height": 900}, device_scale_factor=2).new_page()
    d.goto(SITE, wait_until="networkidle")
    d.wait_for_timeout(1500)
    d.screenshot(path=str(OUT / "6-desktop.png"))
    b.close()
print("shots:", sorted(x.name for x in OUT.iterdir()))
