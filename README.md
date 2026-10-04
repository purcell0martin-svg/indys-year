# Indy's Year

Open `index.html` in a browser to try it. To put it on her iPhone properly (offline, data protected), host it free on GitHub Pages:

## Deploy with Claude Code (paste this prompt)

> In this folder: create a public GitHub repo called `indys-year` (free GitHub Pages needs public), commit everything, push to `main`, and enable GitHub Pages from the `main` branch root. Use the `gh` CLI (install and log me in with `gh auth login` if needed). When done, give me the live Pages URL and confirm it loads `index.html` and `sw.js` over HTTPS.

Note: the site address is public but obscure, and the app stores all data on her phone, not on the site, so nothing personal is exposed.

## On her iPhone
1. Open the Pages URL in **Safari**.
2. Share → **Add to Home Screen**.
3. Always open it from the Home Screen icon (that's what protects the data).
4. Set up, then use **Log → Import → Save backup** weekly (save to iCloud Drive).

## Moving data from the old Claude version
Old app: Log → Import → Export backup. New app: Log → Import → Restore from a backup file.

## Updating later
Ask Claude Code for changes, then: "bump the VERSION in sw.js, commit and push". The phone picks it up next launch.
