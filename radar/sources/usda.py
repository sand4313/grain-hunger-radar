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


def parse_bulk(df, commodity_codes, fas_codes=None):
    """Latest market year per country and commodity from the bulk CSV.
    fas_codes=None keeps every country. Returns (balances, names)."""
    import pandas as pd
    df.columns = [c.strip().lower() for c in df.columns]
    df["commodity_code"] = df["commodity_code"].astype(str).str.zfill(7)
    df = df[df["commodity_code"].isin(commodity_codes.values())]
    if fas_codes is not None:
        df = df[df["country_code"].isin(fas_codes)]
    names = {}
    if "country_name" in df.columns:
        names = dict(zip(df["country_code"], df["country_name"].str.strip()))
    df = df[df["attribute_description"].str.strip().str.lower().isin(BULK_ATTR)]
    out = {}
    code_to_crop = {v: k for k, v in commodity_codes.items()}
    for (cc, com), g in df.groupby(["country_code", "commodity_code"]):
        latest = g["market_year"].max()
        g = g[g["market_year"] == latest]
        if "month" in g.columns:  # keep the most recent estimate for that year
            g = g[g["month"] == g["month"].max()]
        rows = [{"attributeId": None, "name": BULK_ATTR[a.strip().lower()], "value": v}
                for a, v in zip(g["attribute_description"], pd.to_numeric(g["value"], errors="coerce"))]
        vals = {r["name"]: float(r["value"]) for r in rows if r["value"] == r["value"]}
        cons = vals.get("consumption") or 0
        if cons:
            vals["stocks_to_use"] = round(vals.get("ending_stocks", 0) / cons, 3)
            vals["import_dependence"] = round(vals.get("imports", 0) / cons, 3)
        vals["market_year"] = int(latest)
        out.setdefault(cc, {})[code_to_crop[com]] = vals
    return out, names


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
