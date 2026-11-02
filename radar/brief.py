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

    lines += ["## Top risks this week", ""]
    for r in scored[:5]:
        ipc = r.get("ipc") or {}
        bits = []
        if ipc:
            bits.append(f"{ipc['share_phase3plus'] * 100:.0f}% in IPC Phase 3+")
        if r.get("fx_change_30d") is not None:
            bits.append(f"currency {pct(r['fx_change_30d'])} vs USD in 30 days")
        w = (r.get("psd") or {}).get("wheat") or {}
        if "stocks_to_use" in w:
            bits.append(f"wheat stocks-to-use {w['stocks_to_use']:.2f}")
        lines.append(f"- **{r['name']}** — risk {r['risk']}/100 ({r['risk_band']}). " + "; ".join(bits) + ".")
    lines.append("")

    lines += ["## Tender watch", ""]
    hot = [r for r in rows if r["tender"].startswith(("High", "Medium"))]
    hot.sort(key=lambda r: (not r["tender"].startswith("High"), -(r["risk"] or 0)))
    for r in hot:
        level, _, note = r["tender"].partition(", ")
        extra = f" ({note})" if note else ""
        lines.append(f"- **{r['name']}** ({r['buyer']}): {level} chance of wheat buying in the next 60 days{extra}.")
    if not hot:
        lines.append("- No country flags a high tender likelihood this week.")
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
    lines += ["---", "Sources: WFP/IPC via HDX HAPI, USDA FAS PSD, World Bank Pink Sheet, FAO, NOAA CPC, ReliefWeb. "
              "Rates by Exchange Rate API (https://www.exchangerate-api.com)."]

    out = Path(out) / "briefs"
    out.mkdir(exist_ok=True)
    path = out / f"{snap['as_of']}.md"
    path.write_text("\n".join(lines))
    return path
