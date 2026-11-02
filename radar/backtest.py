"""Backtest of the tender signal on USDA history (2008 onward).

Question: in years the radar would have flagged, did the country then import unusually
much (10%+ above its own 5-year average)? We compare the hit rate of each signal level
with the base rate for all big importers.

We also keep the result for the first rule we tried (low opening stocks vs normal), which
turned out to be no better than chance, so the Method page can say so.

Caveat, also shown on the Method page: USDA history is revised after the fact, so this
uses final figures, not the estimates traders saw in real time.
"""
from . import score
from .universe import iso3_for

UNUSUAL = 1.10   # imports 10%+ above the country's own 5-year average


def _stu(b):
    return (b.get("ending_stocks", 0) / b["consumption"]) if b and b.get("consumption") else None


def _avg(xs):
    return sum(xs) / len(xs) if xs else None


def cases(hist, names, first=2008):
    """One record per country, crop and year: the signal inputs and the outcome."""
    top = max((int(y) for crops in hist.values() for ys in crops.values() for y in ys), default=0)
    last = top - 1  # the newest year is still a forecast
    out = []
    for cc, crops in hist.items():
        iso = iso3_for(names.get(cc, cc))
        if not iso:
            continue  # aggregates like the EU, or countries that no longer exist
        for crop in score.TENDER_CROPS:
            ys = {int(y): v for y, v in (crops.get(crop) or {}).items()}
            for y in range(first, last + 1):
                prev, now = ys.get(y - 1), ys.get(y)
                if not prev or not now or not prev.get("consumption"):
                    continue
                if prev.get("imports", 0) < score.TENDER_MIN_KT or prev.get("imports", 0) / prev["consumption"] < score.TENDER_MIN_DEP:
                    continue
                imps = [ys[k].get("imports", 0) for k in range(y - 5, y) if k in ys]
                prods = [ys[k].get("production", 0) for k in range(y - 5, y) if k in ys]
                if len(imps) < 3 or not _avg(imps):
                    continue
                avg_imp, avg_prod = _avg(imps), _avg(prods)
                momentum = prev.get("imports", 0) / avg_imp
                harvest = now.get("production", 0) / avg_prod if avg_prod and avg_prod > 50 else None
                stus = [_stu(ys.get(k)) for k in range(y - 6, y - 1)]
                stus = [s for s in stus if s is not None]
                stock_ratio = (_stu(prev) / _avg(stus)) if len(stus) >= 3 and _avg(stus) > 0.02 else None
                out.append({"iso3": iso, "crop": crop, "year": y,
                            "level": score.classify(momentum, harvest),
                            "stock_ratio": stock_ratio,
                            "hit": now.get("imports", 0) >= UNUSUAL * avg_imp})
    return out


def _stats(sel, base=None):
    n = len(sel)
    h = sum(c["hit"] for c in sel)
    rate = round(h / n, 3) if n else None
    out = {"n": n, "hits": h, "rate": rate}
    if base and rate is not None:
        out["lift"] = round(rate / base, 2)
    return out


def evaluate(cs):
    base = _stats(cs)["rate"]
    return {"all": _stats(cs), **{lvl.lower(): _stats([c for c in cs if c["level"] == lvl], base)
                                  for lvl in ("High", "Medium", "Low")}}


def run(hist, names):
    cs = cases(hist, names)
    if not cs:
        return None
    years = sorted({c["year"] for c in cs})
    recent = [c for c in cs if c["year"] >= years[-1] - 4]
    old = [c for c in cs if c["stock_ratio"] is not None]
    old_base = _stats(old)["rate"]
    return {
        "question": "Did the country import 10%+ more than its own 5-year average that year?",
        "years": [years[0], years[-1]],
        "countries": len({c["iso3"] for c in cs}),
        "cases": len(cs),
        "rule": {"min_kt": score.TENDER_MIN_KT, "min_dependence": score.TENDER_MIN_DEP,
                 "momentum_high": score.MOMENTUM_HIGH, "harvest_short": score.HARVEST_SHORT,
                 "momentum_medium": score.MOMENTUM_MEDIUM},
        "result": evaluate(cs),
        "recent": dict(evaluate(recent), years=[years[-1] - 4, years[-1]]),
        "rejected_rule": {
            "name": "Opening stocks at or below 75% of the country's own norm",
            "result": _stats([c for c in old if c["stock_ratio"] <= 0.75], old_base),
            "base": old_base,
        },
        "caveat": "Uses USDA's revised figures, not the estimates available at the time.",
    }


def sanity(rows):
    """Does the non-hunger part of the score rank IPC crisis countries higher? (rank AUC)"""
    pos, neg = [], []
    for r in rows:
        comp = score.components(dict(r, ipc=None))
        if not comp:
            continue
        s = sum(comp[k] * score.WEIGHTS[k] for k in comp) / sum(score.WEIGHTS[k] for k in comp)
        share = (r.get("ipc") or {}).get("share_phase3plus")
        (pos if share is not None and share >= 0.20 else neg).append(s)
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return {"auc": round(wins / (len(pos) * len(neg)), 3), "crisis_countries": len(pos), "others": len(neg),
            "meaning": "Chance a country with 20%+ in IPC crisis scores higher on supply and currency alone than one without."}
