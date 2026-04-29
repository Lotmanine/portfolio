# OLDEV Portfolio Website

## File Structure
```
oldev-site/
├── index.html                        ← EN home
├── crm-migration-service/index.html  ← EN CRM Migration
├── contact.html                      ← EN Contact
├── free-deliverability-audit/index.html  ← EN Free Audit page
├── fr/                               ← FR mirror (4 pages, same structure)
├── partials/
│   ├── header.html                   ← Single source of truth for the header
│   ├── footer.html                   ← Single source of truth for the footer
│   └── strings.json                  ← Every translatable string, en + fr
├── build.py                          ← Idempotent build script (stdlib only)
├── css/style.css                     ← All custom styles
├── js/main.js                        ← Nav, scroll reveal, mobile toggle
├── js/lead-magnet.js                 ← Free-audit form handler (data-source per instance)
├── sitemap.xml                       ← All 8 pages with hreflang
├── robots.txt                        ← Sitemap reference
└── images/                           ← Static assets
```

## Build (after editing partials, page bodies, or strings)
After editing `partials/header.html`, `partials/footer.html`, `partials/strings.json`,
or any page body, run `python build.py` to propagate the changes into every page.
The script is idempotent — re-running it produces zero diffs.

## Setup
1. Copy your profile photo to `images/profile-photo.jfif`
2. Deploy the entire folder to your hosting (Netlify, Vercel, cPanel, etc.)

## Portfolio Gallery
The "Real Systems I've Built" section is commented out in `index.html`. To enable it:
1. Add your screenshots to `images/` (automation-workflow.jpg, landing-page.jpg, etc.)
2. Search for `PORTFOLIO GALLERY — HIDDEN` in index.html
3. Remove the `<!--` and `-->` comment markers around that block

## Quote Form
"Request a Quote" CTAs link to a Google Form (open in new tab):
`https://docs.google.com/forms/d/e/1FAIpQLSd8bSBRHmSHbgyo_nnlhqsJAgUkRwTSyS-QC83OL_RX2-ZR8g/viewform`

## WhatsApp CTA
A floating WhatsApp button is rendered on every page (bottom-right) and a header-level WhatsApp button appears in the nav of internal pages. Link: `https://wa.link/u2fc8x`.

## Dependencies (loaded via CDN)
- Tailwind CSS
- Font Awesome 6.5
- Google Fonts (Outfit + JetBrains Mono)
