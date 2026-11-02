"""Storage: latest snapshot as JSON, FX history as CSV (kept in the repo)."""
import csv
import json
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FX_HIST = DATA / "history" / "fx.csv"          # daily rate shown on the site (Exchange Rate API)
FX_ALT = DATA / "history" / "fx_alt.csv"        # one consistent daily series used for 7/30-day moves


def use_dir(path):
    """Point storage somewhere else (offline test runs write to sample_output/)."""
    global DATA, FX_HIST, FX_ALT
    DATA = Path(path) / "data"
    FX_HIST = DATA / "history" / "fx.csv"
    FX_ALT = DATA / "history" / "fx_alt.csv"


def append_fx(today, rates):
    FX_HIST.parent.mkdir(parents=True, exist_ok=True)
    rows = read_fx()
    rows = [r for r in rows if r["date"] != today]  # one row per day per currency
    rows += [{"date": today, "ccy": k, "rate": v} for k, v in rates.items() if v]
    with FX_HIST.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "ccy", "rate"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["date"], r["ccy"])))


def _write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "ccy", "rate"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["date"], r["ccy"])))


def add_fx_days(days, path=None):
    """Add whole days of rates ({date: {ccy: rate}}), replacing those days if already stored."""
    path = path or FX_ALT
    rows = [r for r in read_fx(path) if r["date"] not in days]
    for d, rates in days.items():
        rows += [{"date": d, "ccy": k, "rate": v} for k, v in rates.items() if v]
    _write(path, rows)


def read_fx(path=None):
    path = path or FX_HIST
    if not path.exists():
        return []
    with path.open() as f:
        return [{"date": r["date"], "ccy": r["ccy"], "rate": float(r["rate"])} for r in csv.DictReader(f)]


def _change(rows, ccy, today, days):
    rows = [r for r in rows if r["ccy"] == ccy]
    t = datetime.fromisoformat(today).date()
    cutoff = (t - timedelta(days=days)).isoformat()
    past = [r for r in rows if r["date"] <= cutoff]
    now = [r for r in rows if r["date"] == today]
    if not past or not now:
        return None
    return round(now[0]["rate"] / past[-1]["rate"] - 1, 4)


def fx_change(ccy, today, days=30):
    """Fractional change in local units per USD vs the closest stored day >= `days` ago.
    Both ends always come from the same source: different feeds quote different rates for
    some currencies (official vs parallel), and mixing them creates fake moves."""
    alt = _change(read_fx(FX_ALT), ccy, today, days)
    return alt if alt is not None else _change(read_fx(FX_HIST), ccy, today, days)


def write_snapshot(snap):
    DATA.mkdir(exist_ok=True)
    (DATA / "latest.json").write_text(json.dumps(snap, indent=2, default=str))
    arch = DATA / "snapshots"
    arch.mkdir(exist_ok=True)
    (arch / f"{snap['as_of']}.json").write_text(json.dumps(snap, default=str))


def today():
    return date.today().isoformat()


def read_tenders(path):
    """Manual tender log (config/tenders.csv), newest first."""
    if not Path(path).exists():
        return []
    with open(path) as f:
        rows = [r for r in csv.DictReader(f) if (r.get("date") or "").strip()]
    return sorted(rows, key=lambda r: r["date"], reverse=True)
