# Indy's Year — project notes for Claude Code

Personal fitness + weight + blood-sugar tracker for one user (NZ mum, postpartum, type 2 diabetes / prediabetes).
Goals: −5 kg in 3 months, −15 kg by Indy's first birthday, HbA1c into the NZ non-diabetic range (≤40 mmol/mol).

## Stack (keep it this way)
- Single-file app: `index.html` (all CSS + JS inline, no build step, no frameworks, no CDN).
- `sw.js` offline cache, `manifest.webmanifest`, icons. Static hosting over HTTPS on Vercel (`vercel.json` sets headers; `robots.txt` blocks indexing).
- Storage: IndexedDB (`indy-tracker` db, `kv` store, key `state`) with localStorage mirror (`indy-tracker-v1`).
- Data schema is backward-compatible with the v1 backup JSON. Never break `migrate()`.

## Rules
- Bump `VERSION` in `sw.js` on every change to `index.html`, then commit and push (Vercel auto-deploys from `main`).
- Deterministic analytics only (no AI calls). NZ units: kg, cm, mmol/L, mmol/mol.
- Safety thresholds live in `insights()` and `preStart()` in index.html. Do not loosen: breastfeeding pace cap 0.5 kg/wk, hypo < 3.9 mmol/L, NZ HbA1c bands 40/41–49/50+.
- No remote images or tracking. Exercise figures are inline SVG poses in `POSES`.
- Not medical advice; never add medication-dose advice.

## Deploy
Hosted on Vercel (project `indys-year`, framework Other, no build, output dir `.`), auto-deploys from the private GitHub repo `indys-year` on every push to `main`. First install: open the production URL in Safari on iPhone → Share → Add to Home Screen.
