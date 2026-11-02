"""HDX HAPI: IPC food-security phases per country.

Needs HAPI_APP_IDENTIFIER (free, not secret): base64 of "app_name:email".
Generate it once at https://hapi.humdata.org/api/v2/encode_app_identifier
"""
BASE = "https://hapi.humdata.org/api/v2/food-security-nutrition-poverty/food-security"


def latest_national(rows):
    """Share of analysed population in IPC Phase 3+, national level, latest analysis.
    Prefers the 'current' analysis; falls back to projections when there is none."""
    rows = [r for r in rows if str(r.get("ipc_phase")) == "3+"]
    nat0 = [r for r in rows if str(r.get("admin_level")) == "0"]
    rows = nat0 or rows
    cur_type = [r for r in rows if r.get("ipc_type") == "current"]
    rows = cur_type or rows
    if not rows:
        return None
    latest = max(r.get("reference_period_start") or "" for r in rows)
    cur = [r for r in rows if (r.get("reference_period_start") or "") == latest]
    # prefer national rows (no admin1); otherwise sum sub-national population
    nat = [r for r in cur if not r.get("admin1_code")]
    pick = nat or cur
    if len(pick) > 1:  # several national rows for one period: keep the largest population figure
        pick = [max(pick, key=lambda r: float(r.get("population_in_phase") or 0))]
    pop = float(pick[0].get("population_in_phase") or 0)
    frac = float(pick[0].get("population_fraction_in_phase") or 0)
    return {"period_start": latest, "people_phase3plus": int(pop),
            "share_phase3plus": round(frac, 3), "ipc_type": pick[0].get("ipc_type"),
            "period_end": pick[0].get("reference_period_end")}


def fetch(sess, iso3, app_id):
    params = {"location_code": iso3, "app_identifier": app_id, "admin_level": 0,
              "ipc_phase": "3+", "output_format": "json", "limit": 10000}
    r = sess.get(BASE, params=params, timeout=60)
    r.raise_for_status()
    return latest_national(r.json().get("data", []))
