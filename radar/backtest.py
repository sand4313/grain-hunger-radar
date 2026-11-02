"""Backtest of the tender signal on 15+ years of USDA history.

Question it answers: when a big importer opened a marketing year with stocks well below
its own 5-year norm (what the radar flags as High), did it then import unusually much
that year (10%+ above its own 5-year average)?

Caveat, also shown on the Method page: USDA history is revised after the fact, so this
uses final figures, not the numbers traders saw in real time.
"""
from . import score
from .universe import iso3_for

UNUSUAL = 1.10   # imports 10%+ above the country's own 5-year average


def _stu(b):
    return (b.get("ending_stocks", 0) / b["consumption"]) if b and b.get("consumption") else None


def cases(hist, names, first=2008):
    """One record per country, crop and year: the signal inputs and the outcome."""
    top = max((y for crops in hist.values() for ys in crops.values() for y in ys), default=0)
    last = top - 1  # the newest year is still a forecast
    out = []
    for cc, crops in hist.items():
        iso = iso3_for(names.get(cc, cc))
        if not iso:
            continue  # aggregates like the EU, or countries that no longer exist
        for crop in score.TENDER_CROPS:
            ys = crops.get(crop) or {}
            for y in range(first, last + 1):
                prev = ys.get(y - 1)
                now = ys.get(y)
                if not prev or not now or not prev.get("consumption"):
                    continue
                dep = (prev.get("imports", 0) / prev["consumption"])
                if prev.get("imports", 0) < score.TENDER_MIN_KT or dep < score.TENDER_MIN_DEP:
                    continue
                base = [_stu(ys.get(k)) for k in range(y - 6, y - 1)]
                base = [b for b in base if b is not None]
                imps = [ys[k].get("imports", 0) for k in range(y - 5, y) if k in ys]
                if len(base) < 3 or len(imps) < 3:
                    continue
                avg = sum(base) / len(base)
                if avg < 0.02:
                    continue
                out.append({"iso3": iso, "crop": crop, "year": y,
                            "ratio": round(_stu(prev) / avg, 3),
                            "hit": now.get("imports", 0) >= UNUSUAL * (sum(imps) / len(imps))})
    return out


def evaluate(cs, high=score.TENDER_HIGH, medium=score.TENDER_MEDIUM):
    def stats(sel):
        n = len(sel)
        h = sum(c["hit"] for c in sel)
        return {"n": n, "hits": h, "rate": round(h / n, 3) if n else None}
    allc = stats(cs)
    hi = stats([c for c in cs if c["ratio"] <= high])
    med = stats([c for c in cs if high < c["ratio"] <= medium])
    low = stats([c for c in cs if c["ratio"] > medium])
    lift = round(hi["rate"] / allc["rate"], 2) if hi["rate"] and allc["rate"] else None
    return {"all": allc, "high": hi, "medium": med, "low": low, "lift_high": lift}


def run(hist, names):
    cs = cases(hist, names)
    if not cs:
        return None
    years = sorted({c["year"] for c in cs})
    res = {
        "question": "After opening the year with low stocks, did the country import 10%+ more than its 5-year average?",
        "years": [years[0], years[-1]],
        "countries": len({c["iso3"] for c in cs}),
        "rule": {"high": score.TENDER_HIGH, "medium": score.TENDER_MEDIUM,
                 "min_kt": score.TENDER_MIN_KT, "min_dependence": score.TENDER_MIN_DEP},
        "result": evaluate(cs),
        "grid": [dict(threshold=t, **evaluate(cs, high=t)["high"], lift=evaluate(cs, high=t)["lift_high"])
                 for t in (0.5, 0.6, 0.7, 0.75, 0.8, 0.9)],
        "recent": evaluate([c for c in cs if c["year"] >= years[-1] - 4]),
        "caveat": "Uses USDA's revised figures, not the estimates available at the time.",
    }
    return res


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
