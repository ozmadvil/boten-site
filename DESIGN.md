---
name: NiceBuy
description: Light, clean commerce with an indigo hand. Coupons and dated deals for Israeli AliExpress shoppers, Hebrew RTL. Replaced the sale-flyer world on 2026-11-01 at the owner's request (brief + comp from the owner).
colors:
  bg: "#F8FAFC"            # page
  card: "#FFFFFF"
  primary: "#4F46E5"       # actions, prices, emphasis in headlines, selected states
  primary-hover: "#4338CA" # also small indigo text on white (AA)
  primary-soft: "#EEF2FF"  # tints: chip hover, table head, answer box, step numbers
  primary-line: "#C7D2FE"  # outlines of secondary buttons and soft boxes
  accent: "#A3E635"        # lime: discount tags, the swoosh under the hero line
  accent-ink: "#1A2E05"    # text on lime
  text: "#111827"
  text-2: "#4B5563"        # secondary text (7:1 on white)
  text-3: "#6B7280"        # fine print
  line: "#E5E7EB"
  ok: "#15803D"
  ok-soft: "#DCFCE7"
  bad: "#B91C1C"
  bad-soft: "#FEE2E2"
typography:
  family: "Rubik (self-hosted woff2, Hebrew + Latin), system-ui, sans-serif"
  hero: { size: "clamp(40px, 6.4vw, 76px)", weight: 900, lineHeight: 1.02, letterSpacing: "-0.035em" }
  h1: { size: "clamp(32px, 5.4vw, 50px)", weight: 900, lineHeight: 1.12, letterSpacing: "-0.02em" }
  h2: { size: "clamp(26px, 3.6vw, 34px)", weight: 900 }
  h3: { size: "20px", weight: 700 }
  body: { size: "17px", weight: 400, lineHeight: 1.7, fontFeature: "\"tnum\" 1" }
  price: { weight: 900, letterSpacing: "-0.03em", note: "₪ and agorot at ~half size, agorot raised; LTR-isolated" }
rounded:
  card: "14px"
  control: "12px"   # buttons, chips, header buttons
  small: "10px"     # photo wells, logo
  pill: "99px"      # search field, discount tag, code sticker, status stickers
shadows:
  card: "0 0 0 1px #E5E7EB, 0 1px 2px rgb(17 24 39 / .05), 0 6px 20px -10px rgb(17 24 39 / .16)"
  lift: "0 0 0 1px #C7D2FE, 0 2px 4px rgb(17 24 39 / .05), 0 18px 34px -14px rgb(79 70 229 / .32)"
  primary-button: "0 8px 18px -10px rgb(79 70 229 / .8)"
motion:
  ease: "cubic-bezier(.16, 1, .3, 1)"
  hover: "cards and chips lift 1-4px; product photo scales to 1.04; menu underline grows from 0"
  ambient: "the hero's lime tag floats 8px, only without prefers-reduced-motion"
---

# NiceBuy design system

## World
Light and commercial, in the register of modern SaaS and good e-commerce: a near-white page, white cards with soft shadows, one strong indigo for everything you can act on, and lime only where money is saved (the discount tag). Hebrew, RTL, phone first.

What stays from the product, whatever the look: every price on the page is dated ("נכון ל-DD/MM"), coupon codes are never printed on the site (they wait in the bot), and failures are shown alongside successes.

Single light theme by decision (no dark mode).

## Shell
- **Header**: sticky white bar with a hairline bottom and a light blur. Logo (mascot 42px, 12px radius) + wordmark "Nice**Buy**" with "Buy" in indigo, the main menu centred, and two Telegram buttons at the end: the channel (outlined) and the bot (filled indigo, the primary). Menu items get a 3px indigo underline that grows on hover and stays on the current page. Under 1020px the menu drops to its own sideways-scrolling row; under 600px the channel button shortens to "ערוץ".
- **Footer**: white, hairline top, menu links then the disclosure lines.

## Hero (home)
Soft indigo-to-lavender wash (radial gradients on #F5F7FF), centred. Headline at the hero size with the key words in indigo, a 500-weight line under it with a short tilted lime swoosh, then the search: a white pill field with an indigo pill button (magnifier + "חפש"). The status line under it has the "paste a link" hint in a thin indigo-outlined pill. Desktop only: a lime % price tag (floating) and an indigo % rosette drawn as inline SVG at the sides. Inner pages get the slim band: one line and the search, so the page's own answer stays on the first phone screen.

## Category chips
White, 12px radius, hairline ring, a 20px indigo line icon (authored SVG, 1.8 stroke, one per category slug; unknown slugs get a price tag) before the name. Hover: indigo-soft fill, ring and a 1px lift. Current category: solid indigo, white icon and text. Phones: two rows that scroll sideways with a faded edge and a "החליקו" hint.

## Product cards
White card, 14px radius, hairline + soft shadow, 12px inner padding. Square white photo well (10px radius, contain). Lime discount pill at the photo's top right. Under the date, coupon boxes when there are codes: indigo-soft, dashed indigo outline, "קוד מוכר" / "קוד ישראל" with the amount and minimum, then the code partly hidden (ABC•••) and an indigo "העתקה" chip; a click copies the code, shows it in full, turns the box green ("הועתק ✓") and opens the product in a new tab. Price in indigo at 32px (25px on phones) with the struck original in grey beside it; two-line title; a quiet foot line (category, date); then a full-width indigo button "לצפייה במוצר" with a cart icon. The whole card is one link to AliExpress; hover lifts it 4px with the indigo shadow and darkens the button. Grid: auto-fill from 232px, two columns on phones.

## Answers as a chat
Under the hero search, answers appear as a chat (`.sresults.chat`): the visitor's text in an indigo bubble on the right, the answer in a white bubble from the left with a small "N" avatar, three bouncing dots while it works. A pasted link answers with the product as a wide card (photo beside title, indigo price, struck original, lime discount pill, rating and sales, coupon boxes, "לקנייה באליאקספרס"), then cheaper sellers as smaller wide cards with a green "חוסכים ₪X" pill, or a line saying the price is already good. A product name answers with the product cards grid inside the bubble. Each answer ends with fine print and a small link to continue in the Telegram bot. "ניקוי" clears the chat.

## Other components
- **How it works**: one white card, three steps divided by hairlines, step numbers in indigo-soft 44px squares.
- **Coupons**: white tickets, an indigo-soft strip with a dashed perforation under it, the amount in indigo.
- **Checks log**: white cards with a soft green ("עובד") or soft red ("לא עובד") strip and the date.
- **Closing band**: a rounded (22px) solid indigo panel with a lighter indigo glow, white headline, white primary button and an outlined secondary.
- **Tables**: indigo-soft head, hairline rows. **FAQ**: white details with an indigo marker.
- **Share cards** (`share_cards.py`): indigo strip with the mascot and name, indigo-soft field, Rubik 900 headline, prices in indigo.

## Rules
- One accent action colour (indigo). Lime is for savings only. Semantic green/red only for check results.
- No emoji as icons, no gradient text, no hard offset shadows, no coloured side borders.
- Keep the dated price line on every product card.
