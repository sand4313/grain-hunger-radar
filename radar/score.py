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

The tender signal is separate and backtested: see classify() and radar/backtest.py.

Supply parts are scaled by ability to pay: a rich importer with thin stocks simply buys
more, it does not go hungry. Hunger and FX are not scaled.
"""
INCOME_FACTOR = {"HIC": 0.3, "UMC": 0.7, "LMC": 1.0, "LIC": 1.0}
WEIGHTS = {"hunger": 0.35, "fx": 0.20, "stocks": 0.25, "imports": 0.20}
GRAINS = ("wheat", "corn", "rice")

# Tender signal - backtested in radar/backtest.py on 2008-2025 USDA data; keep the two in step.
# A real buyer (300 kt+, imports 30%+ of use) that ...
TENDER_CROPS = ("wheat", "corn")
TENDER_MIN_KT = 300
TENDER_MIN_DEP = 0.30
MOMENTUM_HIGH = 1.10     # ... bought 10%+ above its 5-year norm last year
HARVEST_SHORT = 0.95     # ... and grows a smaller crop than normal this year     -> High
MOMENTUM_MEDIUM = 1.20   # ... or bought 20%+ above normal last year             -> Medium

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


def classify(momentum, harvest):
    """The tender rule itself, shared with the backtest. harvest may be None (no local crop)."""
    if momentum is None:
        return None
    if momentum >= MOMENTUM_HIGH and harvest is not None and harvest <= HARVEST_SHORT:
        return "High"
    if momentum >= MOMENTUM_MEDIUM:
        return "Medium"
    return "Low"


def crop_signal(b):
    """One crop's tender level and the numbers behind it. None if not a real buyer."""
    if not b:
        return None
    imp, cons = b.get("prev_imports", b.get("imports")) or 0, b.get("consumption") or 0
    if imp < TENDER_MIN_KT or not cons or (b.get("imports") or 0) / cons < TENDER_MIN_DEP:
        return None
    m = b.get("import_momentum")
    level = classify(m, b.get("production_vs_avg"))
    if level is None:
        return None
    stocks = round(b["begin_stu"] / b["avg5_stu"], 2) if b.get("begin_stu") is not None and (b.get("avg5_stu") or 0) > 0.02 else None
    return {"level": level, "momentum": m, "harvest": b.get("production_vs_avg"),
            "stocks_vs_normal": stocks, "imports": round(b.get("imports") or 0)}


RANK = {"High": 0, "Medium": 1, "Low": 2}


def tender_detail(c):
    psd = c.get("psd") or {}
    best = None
    for k in TENDER_CROPS:
        s = crop_signal(psd.get(k))
        if s and (best is None or (RANK[s["level"]], -s["imports"]) < (RANK[best["level"]], -best["imports"])):
            best = dict(s, crop=k)
    return best


def tender_signal(c):
    """Likely to buy more than usual in the coming months. Heavy currency stress can delay
    purchases, so it is flagged."""
    psd = c.get("psd") or {}
    if not any(psd.get(k) for k in TENDER_CROPS):
        return "No data"
    d = tender_detail(c)
    if d is None or d["level"] == "Low":
        return "Low"
    if d["level"] == "High" and (c.get("fx_change_30d") or 0) >= 0.05:
        return "High, FX may delay"
    return d["level"]

def band(score):
    if score is None:
        return "No data"
    return "Severe" if score >= 70 else "Elevated" if score >= 45 else "Watch" if score >= 25 else "Low"
