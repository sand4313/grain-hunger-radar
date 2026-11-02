"""Week-over-week movers, alerts and per-country history, built from saved daily snapshots."""
import json
from datetime import datetime, timedelta

BAND_ORDER = {"Low": 0, "Watch": 1, "Elevated": 2, "Severe": 3}


def load_snapshots(snap_dir):
    snaps = {}
    if snap_dir.exists():
        for p in sorted(snap_dir.glob("*.json")):
            try:
                snaps[p.stem] = json.loads(p.read_text())
            except ValueError:
                continue
    return snaps


def baseline(snaps, as_of, days=7):
    """Most recent snapshot at least `days` old; else the oldest earlier one."""
    cutoff = (datetime.fromisoformat(as_of) - timedelta(days=days)).date().isoformat()
    older = [d for d in snaps if d <= cutoff]
    if older:
        return older[-1], snaps[older[-1]]
    earlier = [d for d in snaps if d < as_of]
    return (earlier[0], snaps[earlier[0]]) if earlier else (None, None)


def apply(rows, snaps, as_of):
    """Adds risk_change / band_change to rows; returns (alerts, movers, base_date)."""
    base_date, base = baseline(snaps, as_of)
    prev = {c["iso3"]: c for c in (base or {}).get("countries", [])}
    alerts = []
    for r in rows:
        p = prev.get(r["iso3"])
        r["risk_change"] = (r["risk"] - p["risk"]) if p and r["risk"] is not None and p.get("risk") is not None else None
        if not p:
            if base:
                alerts.append({"iso3": r["iso3"], "country": r["name"], "kind": "new",
                               "text": "joined the watchlist"})
            continue
        if BAND_ORDER.get(r["risk_band"], -1) > BAND_ORDER.get(p.get("risk_band"), -1) >= 0:
            alerts.append({"iso3": r["iso3"], "country": r["name"], "kind": "band_up",
                           "text": f"risk moved up from {p['risk_band']} to {r['risk_band']}"})
        was_hot = str(p.get("tender", "")).startswith("High")
        if r["tender"].startswith("High") and not was_hot:
            alerts.append({"iso3": r["iso3"], "country": r["name"], "kind": "tender",
                           "text": "new high tender signal"})
        if (r.get("fx_change_7d") or 0) >= 0.05:
            alerts.append({"iso3": r["iso3"], "country": r["name"], "kind": "fx",
                           "text": f"currency fell {r['fx_change_7d'] * 100:.1f}% vs USD in a week"})
    moved = [r for r in rows if r.get("risk_change")]
    movers = {
        "up": sorted([r for r in moved if r["risk_change"] > 0], key=lambda r: -r["risk_change"])[:8],
        "down": sorted([r for r in moved if r["risk_change"] < 0], key=lambda r: r["risk_change"])[:8],
    }
    movers = {k: [{"iso3": r["iso3"], "name": r["name"], "risk": r["risk"], "change": r["risk_change"]}
                  for r in v] for k, v in movers.items()}
    return alerts, movers, base_date


def history(snaps, rows, today_snap_date, keep=120):
    """Risk score per country per day (last `keep` days), today's value included."""
    dates = sorted(snaps)[-keep:]
    hist = {}
    for d in dates:
        for c in snaps[d].get("countries", []):
            if c.get("risk") is not None:
                hist.setdefault(c["iso3"], []).append({"date": d, "risk": c["risk"]})
    for r in rows:
        pts = [p for p in hist.get(r["iso3"], []) if p["date"] != today_snap_date]
        if r["risk"] is not None:
            pts.append({"date": today_snap_date, "risk": r["risk"]})
        hist[r["iso3"]] = pts
    return hist
