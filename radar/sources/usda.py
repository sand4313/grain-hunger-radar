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


def fetch(sess, commodity_code, fas_code, year, key):
    url = f"{BASE}/commodity/{commodity_code}/country/{fas_code}/year/{year}"
    r = sess.get(url, headers={"API_KEY": key, "Accept": "application/json"}, timeout=60)
    r.raise_for_status()
    return balance(r.json())
