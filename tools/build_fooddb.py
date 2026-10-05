#!/usr/bin/env python3
"""
Indy's Year — food database builder.

Downloads the official USDA FoodData Central and Australian AUSNUT bulk files,
normalises everything to per-100 g, de-duplicates, adds NZ synonyms and portion
sizes, and writes a compressed foods.json.gz the app loads offline.

USDA FoodData Central: U.S. public domain.
AUSNUT 2023 (FSANZ): © Food Standards Australia New Zealand, CC BY 4.0 AU (FSANZ site licence; attribute and say if changed).

Run:  python3 build_fooddb.py
Output: ./out/foods.json.gz  and ./out/foods.meta.json
Needs: pandas, openpyxl   (pip install pandas openpyxl)

If an automatic download fails (sites change), the script prints the page to
download from by hand and where to drop the file, then re-run.
"""
import os, io, json, gzip, re, sys, zipfile, urllib.request, urllib.parse, ssl

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw"); OUT = os.path.join(HERE, "out")
os.makedirs(RAW, exist_ok=True); os.makedirs(OUT, exist_ok=True)

# ---- official sources (bulk downloads) ----
# Checked 2026-10-05. USDA bundles are named by release date; if one 404s, get the current
# SR Legacy / Foundation CSV links from https://fdc.nal.usda.gov/download-datasets and update below.
USDA_SR = "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_csv_2018-04.zip"
USDA_FOUND = "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_foundation_food_csv_2025-04-24.zip"
# AUSNUT 2023 replaced the 2011-13 database. Per-100 g nutrients for ~3,700 foods are in the
# "Food nutrient profiles" workbook. FSANZ renames/moves files, so try the pinned link first and
# otherwise find the current link on the data-files page.
AUSNUT_PAGE = "https://www.foodstandards.gov.au/science-data/food-nutrient-databases/ausnut/data-files"
AUSNUT_FOOD = "https://www.foodstandards.gov.au/sites/default/files/2025-09/AUSNUT%202023%20-%20Food%20nutrient%20profiles.xlsx?v=20250903"

ctx = ssl.create_default_context()   # normal certificate verification (do not disable)
UA = {"User-Agent": "Mozilla/5.0 (compatible; IndysYear-foodbuild/1.0)"}

def fetch(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        print(f"  have {os.path.basename(dest)}"); return True
    try:
        print(f"  downloading {url}")
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, context=ctx, timeout=180) as r, open(dest, "wb") as f:
            f.write(r.read())
        return os.path.getsize(dest) > 1000
    except Exception as e:
        print(f"  FAILED: {e}")
        if os.path.exists(dest) and os.path.getsize(dest) <= 1000: os.remove(dest)
        return False

def resolve_ausnut_url():
    """Find the current 'Food nutrient profiles' xlsx link on FSANZ's AUSNUT data-files page."""
    try:
        req = urllib.request.Request(AUSNUT_PAGE, headers=UA)
        html = urllib.request.urlopen(req, context=ctx, timeout=60).read().decode("utf-8", "ignore")
        for href in re.findall(r'href="([^"]+\.xlsx[^"]*)"', html):
            if "nutrient%20profiles" in href.lower() and "supplement" not in href.lower() and "guidelines" not in href.lower():
                return urllib.parse.urljoin(AUSNUT_PAGE, href.replace("&amp;", "&"))
    except Exception as e:
        print(f"  could not read {AUSNUT_PAGE}: {e}")
    return None

# ---- normalisation helpers ----
def num(x):
    try:
        v = float(x); return v if v == v else None  # NaN guard
    except: return None

def clean_name(n):
    n = re.sub(r"\s+", " ", str(n)).strip()
    # USDA names are long ("Chicken, broilers or fryers, breast, meat only, cooked, braised") and the tail says
    # raw vs cooked, which changes the calories, so never cut it short (the app truncates for display).
    return n[:160]

# Filter out US fast-food chains and generic "Restaurant," entries (clutter for NZ users).
# Set DROP_FASTFOOD = False to keep them.
DROP_FASTFOOD = True
_CHAINS = re.compile(r"(KFC|POPEYES|MCDONALD|BURGER KING|WENDY|TACO BELL|PIZZA HUT|DOMINO|SUBWAY|STARBUCKS|DENNY|CRACKER BARREL|APPLEBEE|OLIVE GARDEN|CHICK-FIL|CHIPOTLE|PANERA|ARBY|DAIRY QUEEN|LITTLE CAESAR|PAPA JOHN|SONIC|CARL'S|HARDEE|WHATABURGER|JACK IN THE BOX|IN-N-OUT|FIVE GUYS|PANDA EXPRESS|DUNKIN|T\.G\.I|NATHAN'S|AUNTIE ANNE|BOJANGLE|CHECKERS|CHURCH'S|DEL TACO|EL POLLO|JAMBA|JIMMY JOHN|KRISPY KREME|LONG JOHN|NOODLES & CO|QDOBA|RALLY'S|RED LOBSTER|SHAKE SHACK|WAWA|WINGSTOP)")
def is_fastfood(name):
    u = name.upper()
    if _CHAINS.search(u): return True
    if u.startswith("RESTAURANT,"): return True
    if u.startswith("FAST FOODS"): return True
    return False

# NZ synonyms added as searchable alt terms (not changing the food)
NZ_SYN = {
 "sweet potato":"kumara kūmara","zucchini":"courgette","bell pepper":"capsicum",
 "chard":"silverbeet","ground beef":"mince","candy":"lolly lollies","french fries":"hot chips chippies",
 "chips":"crisps chippies","ketchup":"tomato sauce","soft drink":"fizzy drink","cantaloupe":"rockmelon",
 "shrimp":"prawns","eggplant":"aubergine","cilantro":"coriander","arugula":"rocket",
 "green onion":"spring onion","cookie":"biscuit","oatmeal":"porridge","soda":"fizzy",
}
def syn_for(name):
    low = name.lower(); out = []
    for us, nz in NZ_SYN.items():
        if us in low: out.append(nz)
    return " ".join(out)

def dump_usda_csv(zip_path, src_tag, out):
    """Parse a FoodData Central CSV zip: food.csv + food_nutrient.csv + nutrient.csv."""
    if not os.path.exists(zip_path): return
    z = zipfile.ZipFile(zip_path)
    names = z.namelist()
    def find(n): 
        for x in names:
            if os.path.basename(x) == n: return x   # exact filename (endswith("food.csv") also matched foundation_food.csv)
        return None
    import csv
    # map nutrient_id -> our key for the handful we want
    WANT = {"Energy":"k","Protein":"p","Carbohydrate, by difference":"c","Total Sugars":"sug",
            "Sugars, Total":"sug","Sugars, total including NLEA":"sug",
            "Fiber, total dietary":"fib","Total lipid (fat)":"f","Fatty acids, total saturated":"sat","Sodium, Na":"na",
            # Foundation Foods often report energy only under the Atwater names; used when plain Energy is missing
            "Energy (Atwater General Factors)":"k_alt1","Energy (Atwater Specific Factors)":"k_alt2"}
    nutr_file = find("nutrient.csv")
    id2key = {}
    with z.open(nutr_file) as fh:
        for row in csv.DictReader(io.TextIOWrapper(fh, "utf-8")):
            nm = row.get("name","")
            if nm in WANT and (row.get("unit_name","").lower() in ("kcal","g","mg")):
                # energy must be kcal (not kJ)
                if nm.startswith("Energy") and row.get("unit_name","").lower()!="kcal": continue
                id2key[row["id"]] = WANT[nm]
    foods = {}
    with z.open(find("food.csv")) as fh:
        for row in csv.DictReader(io.TextIOWrapper(fh, "utf-8")):
            foods[row["fdc_id"]] = {"n":clean_name(row["description"]),"src":src_tag}
    with z.open(find("food_nutrient.csv")) as fh:
        for row in csv.DictReader(io.TextIOWrapper(fh, "utf-8")):
            fid=row["fdc_id"]; nid=row.get("nutrient_id")
            if fid in foods and nid in id2key:
                v=num(row.get("amount"))
                if v is not None: foods[fid][id2key[nid]] = round(v,2)
    kept=0
    for fid,f in foods.items():
        if "k" not in f:
            for alt in ("k_alt1","k_alt2"):
                if alt in f: f["k"]=f[alt]; break
        f.pop("k_alt1",None); f.pop("k_alt2",None)
        if "k" in f and ("p" in f or "c" in f):  # needs energy + a macro
            f.setdefault("p",0);f.setdefault("c",0);f.setdefault("f",0);f.setdefault("fib",0);f.setdefault("sug",0);f.setdefault("na",0)
            out.append(f); kept+=1
    print(f"  {src_tag}: kept {kept} foods")

def dump_ausnut(xlsx_path, out):
    if not os.path.exists(xlsx_path): return
    try:
        import pandas as pd
    except ImportError:
        print("  pandas needed for AUSNUT; pip install pandas openpyxl"); return
    try:
        xl = pd.ExcelFile(xlsx_path)
        # the food-nutrient sheet name varies; pick the widest sheet
        best=None;bestc=0
        for s in xl.sheet_names:
            d=xl.parse(s,nrows=3)
            if d.shape[1]>bestc: best=s;bestc=d.shape[1]
        # FSANZ sheets have title rows above the real header: find the row that has "Food name"
        raw=xl.parse(best,header=None)
        hdr=next((i for i in range(min(15,len(raw))) if any(str(v).strip().lower()=="food name" for v in raw.iloc[i].tolist())),0)
        df=raw.iloc[hdr+1:].copy(); df.columns=[str(c).strip() for c in raw.iloc[hdr].tolist()]
        df=df.reset_index(drop=True)
        cols={c.lower():c for c in df.columns}
        def col(*keys):
            for k in keys:
                for lc,orig in cols.items():
                    if k in lc: return orig
            return None
        def colx(include, exclude=()):
            for lc,orig in cols.items():
                if any(k in lc for k in include) and not any(x in lc for x in exclude): return orig
            return None
        cname=colx(["food name","name","description"])
        ck=colx(["energy with dietary fibre","energy, with dietary fibre","energy"],["without"])
        cp=colx(["protein"])
        cc=colx(["available carbohydrate","carbohydrate"],["fibre","fiber"])
        csu=colx(["total sugars","sugars"])
        cfi=colx(["dietary fibre","dietary fiber","fibre","fiber"],["energy"])
        cf=colx(["fat, total","total fat","fat"],["fatty","satur"])
        cna=colx(["sodium"])
        kept=0
        for _,r in df.iterrows():
            nm=r.get(cname)
            if not isinstance(nm,str) or not nm.strip(): continue
            kj=num(r.get(ck))
            kcal=round(kj/4.184,1) if kj else None
            if kcal is None: continue
            out.append({"n":clean_name(nm),"src":"AUSNUT",
                "k":kcal,"p":round(num(r.get(cp)) or 0,2),"c":round(num(r.get(cc)) or 0,2),
                "sug":round(num(r.get(csu)) or 0,2),"fib":round(num(r.get(cfi)) or 0,2),
                "f":round(num(r.get(cf)) or 0,2),"na":round(num(r.get(cna)) or 0,2)})
            kept+=1
        print(f"  AUSNUT: kept {kept} foods")
    except Exception as e:
        print(f"  AUSNUT parse failed: {e}")

def main():
    print("1. Downloading official bulk files…")
    ok_sr=fetch(USDA_SR, os.path.join(RAW,"usda_sr.zip"))
    ok_fd=fetch(USDA_FOUND, os.path.join(RAW,"usda_foundation.zip"))
    ok_au=fetch(AUSNUT_FOOD, os.path.join(RAW,"ausnut.xlsx"))
    if not ok_au:
        cur=resolve_ausnut_url()
        if cur: ok_au=fetch(cur, os.path.join(RAW,"ausnut.xlsx"))
    if not (ok_sr and ok_fd and ok_au):
        print("\nSome files did not download. Get them by hand, drop into ./raw, re-run:")
        if not (ok_sr and ok_fd): print("  USDA: https://fdc.nal.usda.gov/download-datasets  (SR Legacy + Foundation CSV) → raw/usda_sr.zip, raw/usda_foundation.zip")
        if not ok_au: print("  AUSNUT 2023 'Food nutrient profiles' (xlsx): "+AUSNUT_PAGE+"  → raw/ausnut.xlsx")
        if not any([ok_sr,ok_fd,ok_au]): sys.exit(1)
        print("  (continuing with what is available)")

    print("2. Parsing + normalising to per-100 g…")
    foods=[]
    dump_usda_csv(os.path.join(RAW,"usda_foundation.zip"),"USDA-Foundation",foods)
    dump_usda_csv(os.path.join(RAW,"usda_sr.zip"),"USDA-SR",foods)
    dump_ausnut(os.path.join(RAW,"ausnut.xlsx"),foods)

    print("3. De-duplicating + enriching…")
    seen={}; final=[]
    PRI={"AUSNUT":3,"USDA-Foundation":2,"USDA-SR":1}  # AUSNUT first (NZ-closest)
    dropped=0
    for f in foods:
        if DROP_FASTFOOD and is_fastfood(f["n"]): dropped+=1; continue
        key=re.sub(r"[^a-z0-9]","",f["n"].lower())   # full name: a prefix key merged raw/cooked/fried variants
        if key in seen:
            if PRI.get(f["src"],0)>PRI.get(final[seen[key]]["src"],0): final[seen[key]]=f
            continue
        seen[key]=len(final); final.append(f)
    for f in final:   # USDA "carbohydrate by difference" can be slightly negative (e.g. -0.4): clamp
        for k in ("k","p","c","f","fib","sug","na","sat"):
            if k in f and f[k] < 0: f[k] = 0
    for i,f in enumerate(final):
        s=syn_for(f["n"])
        if s: f["syn"]=s
        f["id"]="f"+str(i)

    print(f"   total unique foods: {len(final)}  (dropped {dropped} fast-food/restaurant entries)")
    # compact record: keep short keys
    data={"v":1,"built":__import__("datetime").date.today().isoformat(),
          "attribution":"USDA FoodData Central (public domain); AUSNUT 2023 © Food Standards Australia New Zealand (FSANZ), CC BY 4.0 AU; values converted to per 100 g, kJ to kcal",
          "foods":final}
    raw=json.dumps(data,separators=(",",":")).encode()
    with gzip.open(os.path.join(OUT,"foods.json.gz"),"wb",compresslevel=9) as f:
        f.write(raw)
    json.dump({"count":len(final),"raw_bytes":len(raw),"gz_bytes":os.path.getsize(os.path.join(OUT,"foods.json.gz"))},
              open(os.path.join(OUT,"foods.meta.json"),"w"),indent=2)
    print(f"4. Wrote out/foods.json.gz  ({os.path.getsize(os.path.join(OUT,'foods.json.gz'))//1024} KB gz, {len(raw)//1024} KB raw)")
    print("   Done. Copy out/foods.json.gz into the app folder and tell Claude Code to wire it in.")

if __name__=="__main__":
    main()
