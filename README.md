# בוטן — האתר

אתר סטטי של בוטן: קודי קופון לאליאקספרס בישראל שנבדקו, ומדריכים. נבנה מ-`data/*.csv` ע"י `build.py`
ומתפרסם ב-GitHub Pages (בכל push ופעם ביום, כך שקודים שפג תוקפם נעלמים לבד).

## עדכון תוכן
- `data/seller_codes.csv` — קודי מוכר (רק שנבדקו: `checkout` או `portal`)
- `data/platform_codes.csv` — סטים של קודי ישראל (ILAFF…) עם חלון תוקף רשמי
- `data/checks.csv` — יומן בדיקות בקופה (כולל מה שלא עבד)

## דומיין משלכם
ב-Settings → Secrets and variables → Actions → Variables: `SITE_URL=https://example.co.il` ו-`CNAME=example.co.il`,
ואז Settings → Pages → Custom domain.

## הרצה מקומית
`python build.py` ← התוצאה ב-`_site/`
