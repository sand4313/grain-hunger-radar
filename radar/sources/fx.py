"""Daily exchange rates vs USD from the ExchangeRate-API open endpoint (no key).

Attribution is required on pages that show these rates; the dashboard footer carries it.
History is kept in data/history/fx.csv so we can compute 30-day moves ourselves.
"""
URL = "https://open.er-api.com/v6/latest/USD"


def fetch(sess, countries):
    r = sess.get(URL, timeout=30)
    r.raise_for_status()
    js = r.json()
    if js.get("result") != "success":
        raise RuntimeError(f"FX feed error: {js.get('error-type')}")
    rates = js["rates"]
    date = js["time_last_update_utc"]
    return {
        "updated": date,
        "rates": {c["fx"]: rates.get(c["fx"]) for c in countries},
    }
