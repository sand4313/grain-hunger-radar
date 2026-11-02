"""Weekly brief draft in Markdown, ready to paste into (or push to) beehiiv."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def pct(x):
    return "n/a" if x is None else f"{x * 100:+.1f}%"


def last_change(points, key="value"):
    if not points or len(points) < 2:
        return None, None
    a, b = points[-2][key], points[-1][key]
    return b, (b / a - 1) if a else None


def build(snap, out=ROOT):
    rows = snap["countries"]
    scored = [r for r in rows if r["risk"] is not None]
    lines = [f"# Grain & Hunger Radar — week of {snap['as_of']}", ""]
    if snap["mode"] != "live":
        lines += ["> SAMPLE DATA — offline test run, not real figures.", ""]

    lines += [f"_Watching {len(rows)} countries._", "", "## Top risks this week", ""]
    for r in scored[:5]:
        ipc = r.get("ipc") or {}
        bits = []
        if ipc:
            bits.append(f"{ipc['share_phase3plus'] * 100:.0f}% in IPC Phase 3+")
        if r.get("fx_change_30d") is not None:
            bits.append(f"currency {pct(r['fx_change_30d'])} vs USD in 30 days")
        g = r.get("grain") or {}
        if "stocks_to_use" in g:
            bits.append(f"grain stocks-to-use {g['stocks_to_use']:.2f}")
        lines.append(f"- **{r['name']}** — risk {r['risk']}/100 ({r['risk_band']}, {r.get('confidence', '?')} confidence). "
                     + "; ".join(bits) + ".")
    lines.append("")

    al, mv = snap.get("alerts") or [], snap.get("movers") or {}
    if al or mv.get("up") or mv.get("down"):
        lines += ["## What changed this week", ""]
        for a in al[:8]:
            lines.append(f"- **{a['country']}**: {a['text']}.")
        ups = ", ".join(f"{m['name']} (+{m['change']})" for m in mv.get("up", [])[:5])
        downs = ", ".join(f"{m['name']} ({m['change']})" for m in mv.get("down", [])[:5])
        if ups:
            lines.append(f"- Rising: {ups}.")
        if downs:
            lines.append(f"- Easing: {downs}.")
        lines.append("")

    bt = (snap.get("backtest") or {}).get("result") or {}
    lines += ["## Tender watch", ""]
    if bt.get("high"):
        lines += [f"_Likely to import more than usual this season. Since 2008, High has been right "
                  f"{bt['high']['rate'] * 100:.0f}% of the time vs {bt['all']['rate'] * 100:.0f}% for any big importer._", ""]
    hot = [r for r in rows if r["tender"].startswith(("High", "Medium"))]
    hot.sort(key=lambda r: (not r["tender"].startswith("High"), -(r["risk"] or 0)))
    for r in hot[:12]:
        level, _, note = r["tender"].partition(", ")
        extra = f" ({note})" if note else ""
        buyer = f" ({r['buyer']})" if r.get("buyer") else ""
        d = r.get("tender_detail") or {}
        why = ""
        if d.get("momentum") is not None:
            why = f": {d['crop']} imports last season {abs(d['momentum'] - 1) * 100:.0f}% {'above' if d['momentum'] >= 1 else 'below'} normal"
            if d.get("harvest") is not None:
                why += f", harvest {abs(d['harvest'] - 1) * 100:.0f}% {'above' if d['harvest'] >= 1 else 'below'} normal"
        lines.append(f"- **{r['name']}**{buyer} — {level}{extra}{why}.")
    if not hot:
        lines.append("- No country flags a high tender likelihood this week.")
    elif len(hot) > 12:
        lines.append(f"- Plus {len(hot) - 12} more on the dashboard.")
    lines.append("")

    opps = snap.get("opportunities") or []
    if opps:
        lines += ["## Where to offer grain", ""]
        for o in opps[:5]:
            route = ", Black Sea route" if o["black_sea"] else ""
            lines.append(f"- **{o['name']}**: {o['tender'].split(',')[0].lower()} tender signal, "
                         f"{o['wheat_kt']:,} kt wheat and {o['corn_kt']:,} kt corn imports{route}.")
        lines.append("")

    lines += ["## Prices", ""]
    for name, pts in snap["global_prices"].items():
        v, ch = last_change(pts)
        if v is not None:
            lines.append(f"- {name}: {v:,.2f} ({pct(ch)} m/m, {pts[-1]['month']})")
    v, ch = last_change(snap["fao_index"], "food")
    if v is not None:
        lines.append(f"- FAO Food Price Index: {v:.1f} ({pct(ch)} m/m)")
    lines.append("")

    e = snap.get("enso")
    if e:
        lines += ["## Climate", "", f"- ENSO: {e['phase']} (ONI {e['latest']['anom']:+.1f}, {e['latest']['season']} {e['latest']['year']}).", ""]

    lines += ["## What it means for traders", "", "_Write 2-3 lines of judgment here before sending._", ""]
    lines += ["---", "Not investment or trading advice. Indicators built from public data; they can be wrong, late or incomplete.", "",
              "Sources: WFP/IPC via HDX HAPI, USDA FAS PSD, World Bank Pink Sheet, FAO, NOAA CPC, ReliefWeb. "
              "Rates by Exchange Rate API (https://www.exchangerate-api.com)."]

    out = Path(out) / "briefs"
    out.mkdir(exist_ok=True)
    path = out / f"{snap['as_of']}.md"
    path.write_text("\n".join(lines))
    return path
