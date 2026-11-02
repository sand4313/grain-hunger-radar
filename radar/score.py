"""Country risk score (0-100) and tender signal.

A transparent heuristic, not a forecast model. Each component is scaled 0-100:
  hunger  - share of people in IPC Phase 3+          (40% share -> 100)
  fx      - local currency loss vs USD over ~30 days (10% loss -> 100)
  stocks  - wheat stocks-to-use, lower is worse      (0.10 -> 100, 0.40+ -> 0)
  imports - wheat import dependence                  (100% of use -> 100)
Missing components are skipped and the weights re-normalised.

Supply components (stocks, imports) are scaled by ability to pay: a rich importer
with thin stocks simply buys more, it does not go hungry. Hunger and FX are not scaled.
"""
INCOME_FACTOR = {"HIC": 0.3, "UMC": 0.7, "LMC": 1.0, "LIC": 1.0}
WEIGHTS = {"hunger": 0.35, "fx": 0.20, "stocks": 0.25, "imports": 0.20}


def clamp(x):
    return max(0.0, min(100.0, x))


def components(c):
    out = {}
    if c.get("ipc"):
        out["hunger"] = clamp(c["ipc"]["share_phase3plus"] / 0.40 * 100)
    if c.get("fx_change_30d") is not None:
        # positive change = more local units per USD = depreciation
        out["fx"] = clamp(c["fx_change_30d"] / 0.10 * 100)
    w = (c.get("psd") or {}).get("wheat") or {}
    if "stocks_to_use" in w:
        out["stocks"] = clamp((0.40 - w["stocks_to_use"]) / 0.30 * 100)
    if "import_dependence" in w:
        out["imports"] = clamp(w["import_dependence"] * 100)
    f = INCOME_FACTOR.get(c.get("income"), 1.0)
    for k in ("stocks", "imports"):
        if k in out:
            out[k] *= f
    return out


def risk(c):
    comp = components(c)
    if not comp:
        return None, comp
    tot = sum(WEIGHTS[k] for k in comp)
    score = sum(comp[k] * WEIGHTS[k] for k in comp) / tot
    parts = {k: round(v) for k, v in comp.items()}
    parts["coverage"] = f"{len(comp)}/4"
    return round(score), parts


def tender_signal(c):
    """Big importer + thin stocks = likely to buy soon. FX stress can delay purchases."""
    w = (c.get("psd") or {}).get("wheat") or {}
    dep, stu = w.get("import_dependence"), w.get("stocks_to_use")
    if dep is None or stu is None:
        return "No data"
    if dep >= 0.4 and stu <= 0.20:
        note = "High" if (c.get("fx_change_30d") or 0) < 0.05 else "High, FX may delay"
        return note
    if dep >= 0.4 and stu <= 0.30:
        return "Medium"
    return "Low"


def band(score):
    if score is None:
        return "No data"
    return "Severe" if score >= 70 else "Elevated" if score >= 45 else "Watch" if score >= 25 else "Low"
