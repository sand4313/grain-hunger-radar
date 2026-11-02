"""HDX HAPI: IPC food-security phases per country.

Needs HAPI_APP_IDENTIFIER (free, not secret): base64 of "app_name:email".
Generate it once at https://hapi.humdata.org/api/v2/encode_app_identifier
"""
BASE = "https://hapi.humdata.org/api/v2/food-security-nutrition-poverty/food-security"


def latest_national(rows):
    """Share of population in IPC Phase 3+ from the most recent analysis."""
    rows = [r for r in rows if str(r.get("ipc_phase")) == "3+"]
    if not rows:
        return None
    latest = max(r.get("reference_period_start") or "" for r in rows)
    cur = [r for r in rows if (r.get("reference_period_start") or "") == latest]
    # prefer national rows (no admin1); otherwise sum sub-national population
    nat = [r for r in cur if not r.get("admin1_code")]
    pick = nat or cur
    pop = sum(float(r.get("population_in_phase") or 0) for r in pick)
    frac = max(float(r.get("population_fraction_in_phase") or 0) for r in pick)
    return {"period_start": latest, "people_phase3plus": int(pop),
            "share_phase3plus": round(frac, 3), "ipc_type": pick[0].get("ipc_type")}


def fetch(sess, iso3, app_id):
    params = {"location_code": iso3, "app_identifier": app_id,
              "output_format": "json", "limit": 10000}
    r = sess.get(BASE, params=params, timeout=60)
    r.raise_for_status()
    return latest_national(r.json().get("data", []))
