"""Storage: latest snapshot as JSON, FX history as CSV (kept in the repo)."""
import csv
import json
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FX_HIST = DATA / "history" / "fx.csv"


def use_dir(path):
    """Point storage somewhere else (offline test runs write to sample_output/)."""
    global DATA, FX_HIST
    DATA = Path(path) / "data"
    FX_HIST = DATA / "history" / "fx.csv"


def append_fx(today, rates):
    FX_HIST.parent.mkdir(parents=True, exist_ok=True)
    rows = read_fx()
    rows = [r for r in rows if r["date"] != today]  # one row per day per currency
    rows += [{"date": today, "ccy": k, "rate": v} for k, v in rates.items() if v]
    with FX_HIST.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "ccy", "rate"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["date"], r["ccy"])))


def read_fx():
    if not FX_HIST.exists():
        return []
    with FX_HIST.open() as f:
        return [{"date": r["date"], "ccy": r["ccy"], "rate": float(r["rate"])} for r in csv.DictReader(f)]


def fx_change(ccy, today, days=30):
    """Fractional change in local units per USD vs the closest stored day >= `days` ago."""
    rows = [r for r in read_fx() if r["ccy"] == ccy]
    if not rows:
        return None
    t = datetime.fromisoformat(today).date()
    cutoff = (t - timedelta(days=days)).isoformat()
    past = [r for r in rows if r["date"] <= cutoff]
    now = [r for r in rows if r["date"] == today]
    if not past or not now:
        return None
    return round(now[0]["rate"] / past[-1]["rate"] - 1, 4)


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
