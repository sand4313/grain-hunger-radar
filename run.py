"""Grain & Hunger Radar pipeline.

  python run.py              # live run: pull every source, score, build site + brief
  python run.py --offline    # use tests/fixtures (no network) to test the whole chain

Keys come from environment variables (GitHub Actions secrets). Any source whose
key is missing or that fails is skipped and reported; the rest still run.
"""
import argparse
import json
import os
import sys
import traceback
from datetime import date
from pathlib import Path

import yaml

from radar import brief, dashboard, score, store, universe
from radar.http import session
from radar.sources import enso, fao, fx, hapi, reliefweb, usda, worldbank

ROOT = Path(__file__).resolve().parent
FIX = ROOT / "tests" / "fixtures"


def load_config():
    return yaml.safe_load((ROOT / "config" / "countries.yaml").read_text())


def fixture(name):
    return json.loads((FIX / f"{name}.json").read_text())


class Log:
    def __init__(self):
        self.status = {}

    def run(self, key, fn):
        try:
            res = fn()
            self.status.setdefault(key, "ok")
            return res
        except Exception as e:  # keep the pipeline alive; report the failure
            self.status[key] = f"failed: {type(e).__name__}: {e}"[:200]
            traceback.print_exc(file=sys.stderr)
            return None

    def skip(self, key, why):
        self.status[key] = f"skipped: {why}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    log = Log()
    sess = session()
    as_of = os.environ.get("RADAR_DATE") or store.today()
    year = int(as_of[:4])

    out = ROOT
    if args.offline:
        # keep test output away from the real data, and seed 30+ days of FX history
        out = ROOT / "sample_output"
        store.use_dir(out)
        store.FX_HIST.parent.mkdir(parents=True, exist_ok=True)
        store.FX_HIST.write_text((FIX / "fx_history.csv").read_text())
        as_of = "2026-11-02"
        year = 2026

    # --- who to watch: core list + every big importer + every IPC country ----
    hapi_id = os.environ.get("HAPI_APP_IDENTIFIER")
    rw_app = os.environ.get("RELIEFWEB_APPNAME")
    fix_c = fixture("countries") if args.offline else {}
    if args.offline:
        countries, unmatched = cfg["countries"], []
        psd_all, ipc_all = {}, {}
    else:
        bulk = log.run("usda_bulk", lambda: usda.fetch_bulk(sess, cfg["commodities"])) or ({}, {})
        psd_all, psd_names = bulk
        if hapi_id:
            ipc_all = log.run("hapi", lambda: hapi.fetch_all(sess, hapi_id)) or {}
        else:
            ipc_all = {}
            log.skip("hapi", "HAPI_APP_IDENTIFIER not set")
        countries, unmatched = universe.build(cfg, psd_all, psd_names, ipc_all)
        if not rw_app:
            log.skip("reliefweb", "RELIEFWEB_APPNAME not set")

    # --- global feeds -----------------------------------------------------
    if args.offline:
        g_fx = fixture("fx")
        g_enso, g_wb, g_fao = fixture("enso"), fixture("worldbank"), fixture("fao")
        for k in ("fx", "enso", "worldbank", "fao"):
            log.status[k] = "ok (fixture)"
    else:
        g_fx = log.run("fx", lambda: fx.fetch(sess, [c for c in countries if c.get("fx")]))
        g_enso = log.run("enso", lambda: enso.fetch(sess))
        g_wb = log.run("worldbank", lambda: worldbank.fetch(sess, cfg["global_prices"]))
        g_fao = log.run("fao", lambda: fao.fetch(sess))

    if g_fx:
        store.append_fx(as_of, g_fx["rates"])

    # --- score every country ----------------------------------------------
    rows = []
    for c in countries:
        iso = c["iso3"]
        row = dict(c)
        if args.offline:
            row.update(fix_c.get(iso, {}))
        else:
            row["ipc"] = (ipc_all.get(iso) or {}).get("ipc")
            row["psd"] = psd_all.get(c.get("fas")) if c.get("fas") else None
        ipc = row.get("ipc")
        if ipc and (ipc.get("period_start") or "")[:10] < f"{year - 2}{as_of[4:]}":
            row["ipc_stale"] = ipc  # keep it visible in the data, but do not score on it
            row["ipc"] = None
        row["fx_rate"] = (g_fx or {}).get("rates", {}).get(c.get("fx"))
        row["fx_change_30d"] = store.fx_change(c["fx"], as_of) if c.get("fx") else None
        row["risk"], row["risk_parts"] = score.risk(row)
        row["risk_band"] = score.band(row["risk"])
        row["tender"] = score.tender_signal(row)
        rows.append(row)

    rows.sort(key=lambda r: (r["risk"] is None, -(r["risk"] or 0)))

    # ReliefWeb reports for the 30 highest-risk countries (one call each, keeps us polite)
    if rw_app and not args.offline:
        for r in rows[:30]:
            r["reports"] = log.run("reliefweb", lambda iso=r["iso3"]: reliefweb.fetch(sess, iso, rw_app))

    snap = {
        "as_of": as_of,
        "mode": "offline-sample" if args.offline else "live",
        "sources": log.status,
        "enso": g_enso,
        "global_prices": (g_wb or {}).get("series", {}),
        "fao_index": (g_fao or {}).get("series", []),
        "countries": rows,
        "unmatched_names": unmatched,
    }
    store.write_snapshot(snap)
    dashboard.build(snap, out)
    brief.build(snap, out)

    print(json.dumps(log.status, indent=2))
    print(f"Wrote {out.name}/data/latest.json, {out.name}/site/index.html, {out.name}/briefs/{as_of}.md")


if __name__ == "__main__":
    main()
