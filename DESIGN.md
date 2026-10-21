---
name: בוטן (Boten)
description: The weekly supermarket sale flyer, honest edition. Every price tag on the page is a real, dated checkout check.
colors:
  flyer-yellow: "#ffe500"
  sale-red: "#d8001a"
  sale-red-pressed: "#b8001a"
  sale-ink: "#b00014"
  on-sale: "#ffffff"
  flyer-ink: "#1d1606"
  ink-secondary: "#4f4428"
  ink-on-flyer: "#3d3300"
  paper: "#ffffff"
  paper-yellow: "#fff7c2"
  newsprint: "#eeede8"
  rule: "#d9d7cd"
  cut-line: "#8f8c7e"
  checked-green: "#0f7a3d"
  checked-green-soft: "#dcf3e3"
  failed-soft: "#ffe1e3"
typography:
  display:
    fontFamily: "Rubik, system-ui, sans-serif"
    fontSize: "clamp(40px, 7.2vw, 84px)"
    fontWeight: 900
    lineHeight: 0.98
    letterSpacing: "-0.03em"
  price:
    fontFamily: "Rubik, system-ui, sans-serif"
    fontSize: "clamp(64px, 9vw, 96px)"
    fontWeight: 900
    lineHeight: 0.9
    letterSpacing: "-0.03em"
    fontFeature: "\"tnum\" 1"
  headline:
    fontFamily: "Rubik, system-ui, sans-serif"
    fontSize: "clamp(32px, 6vw, 52px)"
    fontWeight: 900
    lineHeight: 1.12
    letterSpacing: "-0.015em"
  title:
    fontFamily: "Rubik, system-ui, sans-serif"
    fontSize: "clamp(26px, 4vw, 36px)"
    fontWeight: 900
    lineHeight: 1.12
    letterSpacing: "-0.015em"
  subtitle:
    fontFamily: "Rubik, system-ui, sans-serif"
    fontSize: "20px"
    fontWeight: 700
    lineHeight: 1.12
    letterSpacing: "0"
  lead:
    fontFamily: "Rubik, system-ui, sans-serif"
    fontSize: "clamp(18px, 2.2vw, 21px)"
    fontWeight: 400
    lineHeight: 1.55
  body:
    fontFamily: "Rubik, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.7
    fontFeature: "\"tnum\" 1"
  strip-label:
    fontFamily: "Rubik, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 900
    lineHeight: 1.4
  fine-print:
    fontFamily: "Rubik, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
  mono:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  print: "2px"
  tag: "4px"
  cutout: "6px"
  pill: "99px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "22px"
  xl: "32px"
  2xl: "48px"
  section: "64px"
  band: "80px"
components:
  button-primary:
    backgroundColor: "{colors.sale-red}"
    textColor: "{colors.on-sale}"
    typography: "{typography.body}"
    rounded: "{rounded.print}"
    padding: "13px 22px"
  button-primary-hover:
    backgroundColor: "{colors.sale-red-pressed}"
    textColor: "{colors.on-sale}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.flyer-ink}"
    rounded: "{rounded.print}"
    padding: "13px 22px"
  button-secondary-hover:
    backgroundColor: "{colors.flyer-ink}"
    textColor: "{colors.flyer-yellow}"
  nav-bot-pill:
    backgroundColor: "{colors.flyer-yellow}"
    textColor: "{colors.flyer-ink}"
    rounded: "{rounded.pill}"
    padding: "4px 12px"
  checker-field:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.flyer-ink}"
    rounded: "{rounded.tag}"
    padding: "5px"
  shelf-tag:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.flyer-ink}"
    rounded: "{rounded.tag}"
    padding: "0 0 18px"
  shelf-tag-strip:
    backgroundColor: "{colors.sale-red}"
    textColor: "{colors.on-sale}"
    typography: "{typography.strip-label}"
    padding: "8px 16px"
  coupon-cutout:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.flyer-ink}"
    rounded: "{rounded.cutout}"
    padding: "0 0 18px"
  coupon-cutout-lead:
    backgroundColor: "{colors.paper-yellow}"
  log-tag-strip-ok:
    backgroundColor: "{colors.checked-green}"
    textColor: "{colors.on-sale}"
    typography: "{typography.strip-label}"
    padding: "7px 16px"
  log-tag-strip-failed:
    backgroundColor: "{colors.flyer-ink}"
    textColor: "{colors.newsprint}"
    typography: "{typography.strip-label}"
    padding: "7px 16px"
  sticker-ok:
    backgroundColor: "{colors.checked-green-soft}"
    textColor: "{colors.checked-green}"
    rounded: "{rounded.pill}"
    padding: "2px 10px"
  sticker-failed:
    backgroundColor: "{colors.failed-soft}"
    textColor: "{colors.sale-ink}"
    rounded: "{rounded.pill}"
    padding: "2px 10px"
  sticker-info:
    backgroundColor: "{colors.paper-yellow}"
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.pill}"
    padding: "2px 10px"
  code-sticker:
    backgroundColor: "{colors.sale-red}"
    textColor: "{colors.on-sale}"
    rounded: "{rounded.pill}"
    padding: "6px 10px"
  answer-box:
    backgroundColor: "{colors.flyer-yellow}"
    textColor: "{colors.flyer-ink}"
    rounded: "{rounded.tag}"
    padding: "18px 20px"
  table-header:
    backgroundColor: "{colors.sale-red}"
    textColor: "{colors.on-sale}"
    padding: "11px 14px"
---

# Design System: בוטן (Boten)

## Overview

**Creative North Star: "The Honest Weekly Flyer"**

The site is a supermarket's weekly sale flyer that refuses to lie. Fluorescent yellow fields, a red masthead strip, heavy Hebrew numerals with raised agorot, shelf tags with a red top strip, dashed "גזור ושמור" cut lines and "בתוקף עד" small print: the vocabulary is borrowed wholesale from Israeli supermarket signage, because Israeli shoppers read it instantly as "a deal". What makes it Boten's is the honesty layer: every tag carries a check date, a green rubber stamp marks a real checkout check, and failed checks are printed in the same flyer as the successes.

Density is flyer-like but disciplined: one big field of yellow at the top and one at the bottom (the closing band), newsprint paper for everything in between, and reading pages that keep the flyer's furniture (red table headers, a yellow answer box, dashed cut-out calls to action) around a calm 70ch text column. The world is printed matter, so the yellow fields stay light paper with dark ink even in dark mode; only the newsprint and paper around them darken.

This world replaces the category default of a white card grid with an orange "get code" button. It is RTL Hebrew first; numerals, prices and URLs are isolated left-to-right inside it.

**Key Characteristics:**
- Fluorescent flyer yellow owns exactly two bands per page (hero and closer) plus the inline answer box.
- Sale red carries prices, strips, table headers and the one primary action.
- One family, Rubik, from 400 to 900; 900 is reserved for display, headings, prices and strip labels.
- Prices are set as ₪ + whole number + raised, underlined agorot (₪12⁶⁵).
- Shelf tags, coupon cut-outs and rubber stamps are the containers; there are no generic cards.
- Soft, warm-tinted lift on paper objects; never offset or hard shadows.

## Colors

A three-ink print palette (yellow, red, warm black) on newsprint, with a single green reserved for proof.

### Primary
- **Sale Red** (`sale-red`): the masthead strip, shelf-tag and coupon strips, red table headers, big price numerals on paper, the primary button. Its hover/pressed state is **Pressed Sale Red** (`sale-red-pressed`).
- **Sale Ink** (`sale-ink`): red at text size on white or yellow (links, "-₪" discount lines, error messages, coupon "get it in the bot" links), darker than Sale Red so small red text passes AA.

### Secondary
- **Fluorescent Flyer Yellow** (`flyer-yellow`): the hero field, the closing band, the guide answer box, and the bot pill in the masthead. Text on it is always Flyer Ink or Ink on Flyer, never red body text.

### Tertiary
- **Checked Green** (`checked-green`) with **Checked Green Wash** (`checked-green-soft`): proof only. The "נבדק בקופה" rubber stamp, the "עובד" strip on log tags, and the ok sticker. Never decorative.

### Neutral
- **Flyer Ink** (`flyer-ink`): warm near-black for text, the heavy footer rule, the instructions-box border, the failed-check strip and the focus ring.
- **Secondary Ink** (`ink-secondary`): secondary text, fine print, crumbs on paper.
- **Ink on Flyer** (`ink-on-flyer`): secondary text that sits on yellow.
- **Paper** (`paper`): shelf tags, coupons, the checker field, tables, FAQ.
- **Pale Yellow Paper** (`paper-yellow`): the lead coupon, table zebra stripes, info stickers, the instructions box.
- **Newsprint** (`newsprint`): the page itself, faintly grey so white paper objects read as laid on top.
- **Rule** (`rule`): dotted price-line dividers and table rules.
- **Cut Line** (`cut-line`): dashed coupon borders, dashed dividers, the scissors "גזור ושמור" label.
- **Failed Wash** (`failed-soft`): background of the failed sticker.

Dark scheme (redefined on `:root`, `prefers-color-scheme: dark` and `[data-theme="dark"]`): newsprint `#15130c`, paper `#201d13`, pale yellow paper `#2b2614`, rule `#3a341f`, cut line `#6e6440`, ink `#f6f0dc`, secondary ink `#cbbf98`, sale ink `#ff6b78`, red numerals `#ff4a5c`, green `#63d391` on `#12301f`.

### Named Rules
**The Printed Matter Rule.** Yellow fields (hero, closer, answer box, bot pill) re-declare light paper and dark ink locally and stay light in dark mode. A flyer does not invert.

**The Three Inks Rule.** Yellow, red and warm black do the work; green appears only where something was actually checked. No blues, no gradients, no brand-orange.

**The Red Means Price Or Go Rule.** Sale red marks money and the next action. If a red element is neither a price, a strip label, a table header nor the primary action, it is wrong.

## Typography

**Display Font:** Rubik 900 (with system-ui, sans-serif)
**Body Font:** Rubik 400/500/700 (with system-ui, sans-serif)
**Label/Mono Font:** ui-monospace stack, only for quoted AliExpress error messages

**Character:** One heavy, rounded Hebrew grotesque doing everything a supermarket flyer's sign-writer would: shouting Black for prices and headlines, medium and bold for the shelf-tag small print. Self-hosted woff2 subsets (Hebrew and Latin) at 400, 500, 700, 900; tabular numerals on by default.

### Hierarchy
- **Display** (900, clamp(40px, 7.2vw, 84px), 0.98, -0.03em): the hero headline only; the payoff phrase is set in Sale Red with no italic.
- **Price** (900, clamp(64px, 9vw, 96px), 0.9, -0.03em): shelf-tag prices; coupon amounts at clamp(56px, 7vw, 80px); the 404 at clamp(96px, 20vw, 180px). ₪ and agorot drop to 0.42em and ride the top of the numeral; agorot are underlined.
- **Headline** (900, clamp(32px, 6vw, 52px), 1.12): page h1 on reading pages.
- **Title** (900, clamp(26px, 4vw, 36px), 1.12): section h2; the closing band uses clamp(30px, 5vw, 50px) at line-height 1.
- **Subtitle** (700, 20px): h3; 18px inside coupons.
- **Lead** (400, clamp(18px, 2.2vw, 21px), 1.55, max 46ch): one paragraph under a heading.
- **Body** (400, 17px, 1.7, max 70ch on reading pages).
- **Strip label** (900, 15px): text in red/green/ink strips; the date on the strip drops to 500, 13–14px.
- **Fine print** (400, 13–14px, 1.5): "בתוקף עד", minimums, disclosures, the footer.

### Named Rules
**The Raised Agorot Rule.** Every shekel amount set large is ₪ + whole + raised underlined agorot, isolated LTR, with a visually hidden decimal point between whole and agorot, so search engines, AI answers and screen readers read ₪126.55 and never ₪12655. Inline amounts in running text stay plain (₪126.55).

**The Black Weight Is Loud Rule.** 900 is for headings, prices, strip labels and the stamp. Body copy never goes above 700.

## Layout

A single 1080px column (`--wrap`) with a 16px side gutter at every width. The hero is a two-column grid (1.25fr text, 0.9fr tag) that collapses to one column at 760px with the tag moved below the checker. The deals use a 12-column flyer grid: the first coupon spans 7 and takes the pale-yellow lead treatment, the next spans 5 (or 6/6 for more), and every coupon goes full width under 760px. The checks log is an auto-fit grid of 260px-minimum tags. The instructions box is three equal cells split by dashed rules, stacked under 760px. Reading pages hold text, answer boxes, tables and FAQs at 70ch.

Inner pages (guides, categories, coupons, about) carry the slim band instead of the full hero: a one-line title ("יש לכם לינק? בוטן בודק.") beside the checker on desktop, above it on phones, with the field and button kept on one row, so the page's own h1 and answer box are on the first phone screen.

Rhythm: section headings sit 64px below the previous block; the closing band starts 80px down; the hero pads 44px/56px (28px/40px on mobile). Inner padding on paper objects is 14–22px. Breakpoints in use: 760px (layout), 560px (nav wraps full width, bot pill hidden), 420px (checker stacks, button full width).

## Elevation & Depth

Paper objects (shelf tags, the checker field, log tags, tables, FAQ, the answer box) lift off the newsprint with one soft, warm-tinted shadow: a 1px contact line plus a diffuse drop tinted with the yellow's own dark (`rgb(61 51 0)`), deepened to black in dark mode. Coupons do not lift; they are printed into the flyer and bounded by a dashed cut line instead. Yellow bands and the red masthead are flat.

### Shadow Vocabulary
- **Laid-on paper** (`box-shadow: 0 1px 1px rgb(61 51 0 / .10), 0 8px 22px -6px rgb(61 51 0 / .28)`): every lifted paper object. Dark: `0 1px 1px rgb(0 0 0 / .3), 0 10px 24px -8px rgb(0 0 0 / .6)`.

### Named Rules
**The Laid-On Rule.** Depth means "a paper tag laid on the flyer": one soft warm shadow, never an offset block shadow, never stacked elevations.

**The Cut-Not-Lifted Rule.** Anything the shopper would "cut out and keep" (coupons, inline calls to action, empty states) is flat with a 2px dashed cut-line border, not shadowed.

## Shapes

Nearly square, like printed card stock: 2px on buttons and focus rings, 4px on tags, the checker field, tables and the answer box, 6px on dashed cut-outs and the rubber stamp, full pills only for stickers and the masthead bot pill. Strips run edge to edge across the top of their tag. The hero tag hangs at -3deg and the stamp at -9deg; nothing else rotates. Ink appears as rules and strips (6px footer rule, 3px page-head and instructions-box borders, the failed-check strip), never as a filled panel.

## Components

### Buttons
Blunt and printed, like the price sticker gun.
- **Shape:** almost square (2px).
- **Primary:** Sale Red with white 700 17px text, 13px 22px padding, optional leading inline SVG icon. Label names the destination ("בדקו בבוטן", "פתחו את בוטן").
- **Hover / Focus / Active:** darkens to Pressed Sale Red over 150ms on `cubic-bezier(.16, 1, .3, 1)`; presses 1px down; global focus ring is 3px Flyer Ink at 3px offset. While opening the bot it shows "בודק…" with `aria-busy`.
- **Secondary:** transparent with a 2px inset Flyer Ink outline; on hover it fills with ink and turns its text yellow. Used beside a primary on yellow bands.

### Price Checker
The signature interaction: a white paper field on yellow (5px inner padding, 4px radius, laid-on shadow) holding an LTR URL input and the primary button side by side; stacks under 420px (except in the slim band, where it stays one row). Input focus is a 2px Sale Red outline. One polite live status line sits under it in Ink on Flyer ("מחיר בשקלים, הנחה, קוד אם יש ומוכר זול יותר. בחינם.") and turns Sale Ink bold for errors; nothing else under the field. On submit the hero tag's strip turns ink and flips once while reading "בודק את הלינק שלכם…".

### Shelf Tag (signature)
White paper, 4px radius, laid-on shadow, a red strip across the top (label at 900 15px, date at 500 13px), a product name at 700 16px, dotted price lines (struck-through "was" price with a 3px red strike, Sale Ink minus lines), the big raised-agorot price in red, and fine print with the check date. In the hero it hangs at -3deg, drops and settles once on load (0.9s, reduced-motion respected), and carries the green "נבדק בקופה" rubber stamp.

### Coupon Cut-out
Paper with a 2px dashed Cut Line border and 6px radius, flat; red strip on top; big red amount; minimum and "בתוקף עד" fine print; a status sticker; a Sale Ink "get the code in the bot" link at the foot; a "גזור ושמור" scissors label breaking the bottom border. The first coupon is the lead (pale yellow, wider). Codes themselves are never printed.

### Product Tile
The channel's deals as flyer tiles: white paper, laid-on shadow, the photo on white, the yellow discount burst, the red raised-agorot price with the struck original, a two-line title (AliExpress's long titles are cut at the first separator), and a fine-print foot with the collection name (no emoji) and the price's date ("נכון ל-21/10"). The whole tile is one affiliate link to AliExpress. When the product has a seller code, a **code sticker** sits on the photo's top start corner: a Sale Red pill with the Telegram icon and white 700 13px text ("קוד ₪5 בבוטן", or "יש קוד הנחה בבוטן" when the code needs a bigger cart than one unit). It is a separate link that opens the bot on that product; the code itself is never printed.

### Category Note
Under a category page's head, two or three sentences of real buying advice drawn from the site's guides (16px, Secondary Ink, 70ch), ending with a bold link to that guide.

### Checks Log Tag
A shelf tag variant: green strip with check icon for "עובד", ink strip for "לא עובד", LTR date on the strip, bold "what" line, then the real AliExpress error message isolated in English.

### Chips (Stickers)
- **Style:** pill, 700 13px, 2px 10px padding, optional icon.
- **State:** ok (green on green wash), failed (red on failed wash), info (secondary ink on pale yellow with a 1px rule ring).

### Cards / Containers
- **Answer box:** Flyer Yellow, 4px radius, laid-on shadow, 18px 20px padding, 70ch max; the first answer on a guide page.
- **Instructions box ("איך בוטן עובד"):** Pale Yellow Paper inside a 3px Flyer Ink border, three cells split by 2px dashed cut lines, each led by a red 900 56px numeral.
- **Tables:** paper with laid-on shadow, red header row with white 700 text, pale-yellow zebra rows.
- **FAQ:** paper `details` with laid-on shadow, 12px 18px padding, bold summary.
- **Inline CTA:** dashed cut-out (2px Cut Line, 6px radius) holding a sentence and a primary button.

### Navigation
The red masthead strip: logo (40px mascot with a 2px white ring, 10px radius) and the name at 900 26px in white; nav links in white 500 15px with a 2px yellow underline on hover and on the current page; a yellow bot pill with Telegram icon at the end. Under 560px the nav wraps full width, spreads evenly at 14px and drops the pill. The footer is the flyer's fine print: newsprint under a 6px Flyer Ink rule, 14px secondary ink, asterisked disclosures.

## Share Cards

Every page has its own 1200x630 share picture (`share_cards.py`, drawn at build time into `_site/og/`): the red masthead strip with the mascot and the name, the fluorescent yellow field, the page's headline in Rubik 900 (as large as fits in three lines, right-aligned) with a Rubik 500 subline in Ink on Flyer, and the heavy ink rule at the foot. The home page and category pages add up to three of the page's own deals as paper tags (red strip with the discount, the product photo, the raised-agorot price); the coupons page adds the green "נבדק בקופה" stamp at its -9deg. Provenance: text comes from the page itself and product photos are the AliExpress product images the bot's feed points to, downloaded during the build and never committed. Without Pillow and python-bidi the pages fall back to the logo.

## Do's and Don'ts

### Do:
- **Do** set every large shekel amount as ₪ + whole + raised, underlined agorot, LTR-isolated, with an `aria-label` carrying the full number.
- **Do** date every price, check and coupon ("נבדק 18/10", "נכון ל-21/10", "בתוקף עד 21/10 09:59"); the date is the proof. A date on the page is the date the content changed, never just the build time.
- **Do** keep yellow fields as printed matter: light paper and dark ink in both schemes.
- **Do** use Sale Ink (`sale-ink`), not Sale Red, for red text at body or fine-print size.
- **Do** contain content in the flyer's own objects: shelf tags, dashed cut-outs, stamps, stickers, red-strip tables.
- **Do** print failed checks with the same weight as successes, on an ink strip.
- **Do** name the destination in action labels ("בדקו בבוטן", "פתחו את בוטן").
- **Do** respect `prefers-reduced-motion`: the tag drop and checker flip are the only motion, each once.

### Don't:
- **Don't** fill panels or cards with Flyer Ink; ink is for type, rules, borders and the failed-check strip only.
- **Don't** use offset or hard block shadows; depth is the single soft laid-on shadow.
- **Don't** build a white card grid with an orange "get code" button; that is the category default this world replaces.
- **Don't** print coupon codes on the site; amounts, minimums and validity only, with the code in the bot.
- **Don't** add a second typeface for headings; Rubik 900 is the display voice.
- **Don't** rotate anything except the hero shelf tag and the rubber stamp.
- **Don't** use green for decoration; it means "checked at checkout".
