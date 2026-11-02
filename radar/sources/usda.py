"""USDA FAS PSD: grain supply and demand balance per country and year.

Needs USDA_FAS_API_KEY (free) sent as the API_KEY header.
Sign up: https://apps.fas.usda.gov/opendatawebv2/#/signup
"""
BASE = "https://apps.fas.usda.gov/OpenData/api/psd"

# PSD attribute ids (verify against /api/psd/commodityAttributes on first live run)
ATTR = {28: "production", 57: "imports", 125: "consumption", 176: "ending_stocks"}


def balance(rows):
    vals = {}
    for r in rows:
        name = ATTR.get(int(r.get("attributeId", -1)))
        if name:
            vals[name] = float(r.get("value") or 0)
    cons = vals.get("consumption") or 0
    if cons:
        vals["stocks_to_use"] = round(vals.get("ending_stocks", 0) / cons, 3)
        vals["import_dependence"] = round(vals.get("imports", 0) / cons, 3)
    return vals


def _get(url, key):
    import requests  # plain request: no automatic retries, so a bad key fails fast
    r = requests.get(url, headers={"API_KEY": key.strip(), "Accept": "application/json"}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"USDA HTTP {r.status_code} on {url.split('/OpenData')[-1]}: {r.text[:150]}")
    return r.json()


def check_key(key):
    """One cheap call before the loop. Raises with USDA's own message if the key is bad."""
    rows = _get(f"{BASE}/commodities", key)
    return len(rows)


def fetch(sess, commodity_code, fas_code, year, key):
    url = f"{BASE}/commodity/{commodity_code}/country/{fas_code}/year/{year}"
    return balance(_get(url, key))


# --- Keyless fallback: USDA's bulk PSD download (same numbers, no API key) ---------
BULK_URL = "https://apps.fas.usda.gov/psdonline/downloads/psd_grains_pulses_csv.zip"
BULK_ATTR = {"production": "production", "imports": "imports",
             "domestic consumption": "consumption", "ending stocks": "ending_stocks"}


def yearly(df, commodity_codes, fas_codes=None):
    """Every market year per country and crop from the bulk CSV.
    Returns ({fas: {crop: {year: {production, imports, consumption, ending_stocks}}}}, names)."""
    import pandas as pd
    df.columns = [c.strip().lower() for c in df.columns]
    df["commodity_code"] = df["commodity_code"].astype(str).str.zfill(7)
    df = df[df["commodity_code"].isin(commodity_codes.values())]
    if fas_codes is not None:
        df = df[df["country_code"].isin(fas_codes)]
    names = {}
    if "country_name" in df.columns:
        names = dict(zip(df["country_code"], df["country_name"].str.strip()))
    df = df.assign(attr=df["attribute_description"].str.strip().str.lower())
    df = df[df["attr"].isin(BULK_ATTR)]
    df = df.assign(value=pd.to_numeric(df["value"], errors="coerce"),
                   market_year=pd.to_numeric(df["market_year"], errors="coerce"))
    if "month" in df.columns:  # keep the most recent estimate for each figure
        df = df.assign(month=pd.to_numeric(df["month"], errors="coerce").fillna(0)).sort_values("month")
    df = df.drop_duplicates(["country_code", "commodity_code", "market_year", "attr"], keep="last")
    code_to_crop = {v: k for k, v in commodity_codes.items()}
    out = {}
    for cc, com, yr, attr, val in zip(df["country_code"], df["commodity_code"], df["market_year"],
                                      df["attr"], df["value"]):
        if val != val or yr != yr:
            continue
        out.setdefault(cc, {}).setdefault(code_to_crop[com], {}).setdefault(int(yr), {})[BULK_ATTR[attr]] = float(val)
    return out, names


def derive(years):
    """Latest-year balance plus a 5-year baseline, from {year: balance}."""
    if not years:
        return None
    ys = sorted(years)
    latest = ys[-1]
    vals = dict(years[latest])
    cons = vals.get("consumption") or 0
    if cons:
        vals["stocks_to_use"] = round(vals.get("ending_stocks", 0) / cons, 3)
        vals["import_dependence"] = round(vals.get("imports", 0) / cons, 3)
    vals["market_year"] = latest
    prev = years.get(latest - 1) or {}
    if prev.get("consumption"):
        # beginning stocks of the current year, as a share of last year's use
        vals["begin_stu"] = round(prev.get("ending_stocks", 0) / prev["consumption"], 3)
    base = [years[y] for y in range(latest - 6, latest - 1) if y in years and years[y].get("consumption")]
    if len(base) >= 3:
        vals["avg5_stu"] = round(sum(b.get("ending_stocks", 0) / b["consumption"] for b in base) / len(base), 3)
        vals["avg5_imports"] = round(sum(b.get("imports", 0) for b in base) / len(base), 1)
    return vals


def parse_bulk(df, commodity_codes, fas_codes=None):
    """Latest market year per country and crop. Returns (balances, names, yearly history)."""
    hist, names = yearly(df, commodity_codes, fas_codes)
    top = max((y for crops in hist.values() for ys in crops.values() for y in ys), default=0)
    out = {}
    for cc, crops in hist.items():
        for crop, years in crops.items():
            if max(years) < top - 1:  # countries that no longer exist (USSR, Yugoslavia...)
                continue
            out.setdefault(cc, {})[crop] = derive(years)
    return out, names, hist


def fetch_bulk(sess, commodity_codes, fas_codes=None):
    import io
    import zipfile

    import pandas as pd
    r = sess.get(BULK_URL, timeout=180)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
    df = pd.read_csv(z.open(name), dtype=str)
    return parse_bulk(df, commodity_codes, fas_codes)
