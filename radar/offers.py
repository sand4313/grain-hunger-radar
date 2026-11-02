"""Export opportunities for a Black Sea origin seller.

Ranks countries that (1) are likely to buy soon, (2) import real volume, and
(3) can pay. Natural Black Sea destinations rank well ahead of the rest.
"""
# Natural markets for Ukrainian / Black Sea wheat, corn and oil
BLACK_SEA_MARKETS = {
    "EGY", "DZA", "MAR", "TUN", "LBY", "TUR", "SAU", "ARE", "OMN", "YEM", "JOR", "LBN", "ISR",
    "IRQ", "IRN", "SYR", "KWT", "QAT", "BHR", "SDN", "ETH", "KEN", "SOM", "DJI", "TZA", "UGA",
    "PAK", "BGD", "IND", "LKA", "IDN", "MYS", "PHL", "VNM", "THA", "CHN", "KOR", "ESP", "ITA",
    "PRT", "NLD", "GRC", "MRT", "SEN", "NGA", "GHA", "CMR", "CIV", "MOZ", "AGO", "AZE", "GEO",
}
PAY_WEIGHT = {"HIC": 1.0, "UMC": 0.9, "LMC": 0.75, "LIC": 0.5}
TENDER_WEIGHT = {"High": 1.0, "Medium": 0.6}


def rank(rows, crops=("wheat", "corn"), min_kt=300, top=25):
    out = []
    for r in rows:
        psd = r.get("psd") or {}
        tw = TENDER_WEIGHT.get(r["tender"].split(",")[0])
        if not tw:
            continue
        vols = {k: (psd.get(k) or {}).get("imports", 0) for k in crops}
        vol = sum(vols.values())
        if vol < min_kt:
            continue
        pay = PAY_WEIGHT.get(r.get("income"), 0.6)
        bs = r["iso3"] in BLACK_SEA_MARKETS
        d = r.get("tender_detail") or {}
        pressure = min(1.5, max(0.7, d.get("momentum") or 1.0))  # already buying above normal = more urgent
        score = tw * pay * pressure * (1.0 if bs else 0.35) * (vol ** 0.5)  # off-route markets rarely buy Black Sea
        out.append({
            "iso3": r["iso3"], "name": r["name"], "buyer": r.get("buyer", ""),
            "tender": r["tender"], "income": r.get("income"),
            "wheat_kt": round(vols.get("wheat", 0)), "corn_kt": round(vols.get("corn", 0)),
            "black_sea": bs, "fx_change_30d": r.get("fx_change_30d"),
            "crop": d.get("crop"), "momentum": d.get("momentum"), "harvest": d.get("harvest"),
            "score": round(score, 1),
        })
    out.sort(key=lambda x: -x["score"])
    for i, o in enumerate(out[:top], 1):
        o["rank"] = i
    return out[:top]
