# Food database builder

The repo's `foods.json.gz` is the full food database (about 11,300 foods: USDA FoodData Central
SR Legacy and Foundation, plus AUSNUT 2023), normalised to per 100 g, minus US fast-food chains
and "Restaurant," entries (`DROP_FASTFOOD = True` in the script; set it to False to keep them). The app precaches it
(`sw.js`), loads it once, keeps it in IndexedDB and searches it offline. Rebuild it with:

## One-time setup
    pip install pandas openpyxl

## Build it
    cd tools
    python build_fooddb.py

This downloads the official bulk files (TLS certificates are verified), converts everything to
per 100 g (AUSNUT energy kJ to kcal), de-duplicates on the full food name, adds NZ synonyms
(kumara, courgette, capsicum, mince, ...), and writes:

    tools/out/foods.json.gz      (plus tools/out/foods.meta.json with the count)

`tools/raw/` (downloads) and `tools/out/` are git-ignored.

## Install it
    (Windows) copy tools\out\foods.json.gz foods.json.gz

Then do BOTH of these, or phones keep the old cached copy:
1. In `index.html` set `FOODDB_VER` to the new build: the `built` date plus the food count,
   for example `"2026-10-05-11690"`.
2. Bump `VERSION` in `sw.js`, commit and push.

## If a download 404s
Government sites rename files. The USDA links are pinned in the script. For AUSNUT the script
first tries the pinned link, then looks the current "Food nutrient profiles" workbook up on
FSANZ's data-files page. If that still fails it prints where to download by hand; put the
files in `tools/raw/` as `usda_sr.zip`, `usda_foundation.zip`, `ausnut.xlsx` and re-run. Or ask
Claude Code: "the download URLs in build_fooddb.py are stale, find the current ones and update
them."

## Data sources and attribution (shown in the app's About card)
- USDA FoodData Central: U.S. public domain.
- AUSNUT 2023, Food nutrient profiles: (c) Food Standards Australia New Zealand, CC BY 4.0 AU
  (FSANZ site licence). Values converted to per 100 g and kJ to kcal.
- Barcodes: Open Food Facts contributors, ODbL (looked up live, not bundled).

## Build notes (2026-10-05)
- FSANZ replaced the 2011-13 database with AUSNUT 2023, so the AUSNUT parser reads the new
  workbook (title rows above the header) and finds the current link if the pinned one dies.
- Names are never truncated and de-duplication uses the full name. (A 40-character key used to
  merge raw, cooked and fried variants, which gave wrong calories.)
- Negative "carbohydrate by difference" values are clamped to 0.
- 2026-10-05 (later): `DROP_FASTFOOD` removes ~370 fast-food/restaurant entries (11,690 -> 11,322 foods).
