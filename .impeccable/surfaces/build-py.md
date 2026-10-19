---
version: 1
slug: "build-py"
primary_target: "build.py"
related_targets: []
---

# Surface: home (and the site shell it sets)

Scope: home page `/`, plus the shell every page inherits. Mode: Persuade (home); guides and about inherit the world in Read mode.
Audience: Israeli AliExpress shoppers on phones, from Google and from TikTok/Telegram. Action: paste a product link and open it in the bot. Proof: dated checkout checks from data/checks.csv. Constraint: coupon codes never printed on the site.

## Direction contract

THESIS: The weekly supermarket sale flyer, honest edition: every price tag on the page is a real checkout check with a date. Refuses the category default of a white card grid with an orange "get code" button.
OWN-WORLD: Fluorescent flyer yellow owns the hero and the closing band; sale red carries prices, the "מבצע" strip and the primary action; newsprint white paper for reading. Heavy Hebrew display (Rubik Black) for prices with raised agorot (₪12⁶⁵); shelf-tag labels with a red top strip; dashed "גזור ושמור" cut lines; "בתוקף עד" small print. Coupons are dashed cut-outs with a red strip and "גזור ושמור"; the checks log is a row of dated shelf tags; the footer is the flyer's fine print on newsprint under a heavy ink rule. No black boxes, no offset shadows.
STORY: I see a real price drop I can trust, I understand Boten checks it for me, I paste my own link.
FIRST VIEWPORT: Red masthead strip with logo and nav. Yellow field: giant headline right, a tilted shelf tag on the left showing the real check (₪187 → ₪145.88, checked 18/10). Below the headline, the price-checker: paste field + red "בדקו בבוטן" button (wording names where it goes), full width on mobile. A green "נבדק בקופה" rubber stamp on the tag marks it as a real check.
FORM: Supermarket sale signage / weekly flyer, candidate 1 of my list (user chose IMPECCABLE'S PICK over assigned candidate 3, thermal receipt). seed:944c7b9a2c6f761e
Signature interaction: price-checker kiosk — paste link, the tag flips to "בודק…", then opens the bot on that product (p_<id>). Motion grammar: tags drop and settle once on load, reduced-motion respected.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
