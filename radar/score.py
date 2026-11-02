"""Country risk score (0-100), confidence label and tender signal.

A transparent heuristic, not a forecast model. Each part is scaled 0-100:
  hunger  - share of people in IPC Phase 3+                      (40% share -> 100)
  fx      - local currency loss vs USD over 30 days              (10% loss -> 100)
  stocks  - grain stocks-to-use (wheat + corn + rice), lower=worse (0.10 -> 100, 0.40+ -> 0)
  imports - grain import dependence (wheat + corn + rice)        (100% of use -> 100)
Missing parts are skipped and the weights re-normalised, but a thin score is capped:
  - "Severe" (70+) needs three parts, or an IPC analysis showing 30%+ in crisis
  - a score built on one non-hunger part stays below "Elevated"
Every score carries a confidence label (High / Medium / Low) based on what it rests on.

Supply parts are scaled by ability to pay: a rich importer with thin stocks simply buys
more, it does not go hungry. Hunger and FX are not scaled.
"""
INCOME_FACTOR = {"HIC": 0.3, "UMC": 0.7, "LMC": 1.0, "LIC": 1.0}
WEIGHTS = {"hunger": 0.35, "fx": 0.20, "stocks": 0.25, "imports": 0.20}
GRAINS = ("wheat", "corn", "rice")

# Tender signal (backtested in radar/backtest.py; keep the two in step)
TENDER_CROPS = ("wheat", "corn")
TENDER_MIN_KT = 300      # a real buyer of this crop
TENDER_MIN_DEP = 0.30    # imports at least 30% of what it uses
TENDER_HIGH = 0.75       # opening stocks at or below 75% of the country's own 5-year norm
TENDER_MEDIUM = 0.90


def clamp(x):
    return max(0.0, min(100.0, x))


def grain_totals(psd):
    """Combined wheat + corn + rice balance. None when USDA has no use figure."""
    cons = stocks = imports = 0.0
    for k in GRAINS:
        b = (psd or {}).get(k) or {}
        if b.get("consumption"):
            cons += b["consumption"]
            stocks += b.get("ending_stocks", 0) or 0
            imports += b.get("imports", 0) or 0
    if cons <= 0:
        return None
    return {"stocks_to_use": round(stocks / cons, 3), "import_dependence": round(imports / cons, 3),
            "imports": round(imports), "consumption": round(cons)}


def components(c):
    out = {}
    if c.get("ipc"):
        out["hunger"] = clamp(c["ipc"]["share_phase3plus"] / 0.40 * 100)
    if c.get("fx_change_30d") is not None:
        # positive change = more local units per USD = depreciation
        out["fx"] = clamp(c["fx_change_30d"] / 0.10 * 100)
    g = grain_totals(c.get("psd"))
    if g:
        out["stocks"] = clamp((0.40 - g["stocks_to_use"]) / 0.30 * 100)
        out["imports"] = clamp(min(g["import_dependence"], 1.0) * 100)
    f = INCOME_FACTOR.get(c.get("income"), 1.0)
    for k in ("stocks", "imports"):
        if k in out:
            out[k] *= f
    return out


def confidence(comp):
    n, h = len(comp), "hunger" in comp
    if n == 4 or (n == 3 and h):
        return "High"
    if n == 3 or (n == 2 and h):
        return "Medium"
    return "Low"


def risk(c):
    comp = components(c)
    if not comp:
        return None, {}
    tot = sum(WEIGHTS[k] for k in comp)
    score = sum(comp[k] * WEIGHTS[k] for k in comp) / tot
    share = (c.get("ipc") or {}).get("share_phase3plus") or 0
    if len(comp) < 3 and share < 0.30:
        score = min(score, 69)
    if len(comp) == 1 and "hunger" not in comp:
        score = min(score, 44)
    parts = {k: round(v) for k, v in comp.items()}
    parts["coverage"] = f"{len(comp)}/4"
    parts["confidence"] = confidence(comp)
    return round(score), parts


def crop_pressure(b):
    """Opening stocks vs the country's own 5-year norm, for one crop. None if not a real buyer."""
    if not b:
        return None
    if (b.get("imports") or 0) < TENDER_MIN_KT or (b.get("import_dependence") or 0) < TENDER_MIN_DEP:
        return None
    bs, avg = b.get("begin_stu"), b.get("avg5_stu")
    if bs is None or not avg or avg < 0.02:
        return None
    return round(bs / avg, 2)


def tender_detail(c):
    psd = c.get("psd") or {}
    best = None
    for k in TENDER_CROPS:
        r = crop_pressure(psd.get(k))
        if r is not None and (best is None or r < best["ratio"]):
            best = {"crop": k, "ratio": r, "imports": round(psd[k].get("imports", 0))}
    return best


def tender_signal(c):
    """Big importer opening the year with stocks well below its own norm = likely to buy more.
    Heavy currency stress can delay purchases, so it is flagged."""
    psd = c.get("psd") or {}
    if not any(psd.get(k) for k in TENDER_CROPS):
        return "No data"
    d = tender_detail(c)
    if d is None:
        return "Low"
    if d["ratio"] <= TENDER_HIGH:
        return "High" if (c.get("fx_change_30d") or 0) < 0.05 else "High, FX may delay"
    if d["ratio"] <= TENDER_MEDIUM:
        return "Medium"
    return "Low"


def band(score):
    if score is None:
        return "No data"
    return "Severe" if score >= 70 else "Elevated" if score >= 45 else "Watch" if score >= 25 else "Low"
