"""World Bank income group per country (no key). HIC / UMC / LMC / LIC."""
URL = "https://api.worldbank.org/v2/country"


def fetch(sess):
    r = sess.get(URL, params={"format": "json", "per_page": 400}, timeout=60)
    r.raise_for_status()
    meta, rows = r.json()
    return {c["id"]: c["incomeLevel"]["id"] for c in rows
            if c.get("incomeLevel", {}).get("id") not in (None, "", "NA")}
