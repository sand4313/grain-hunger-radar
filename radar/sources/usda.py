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
