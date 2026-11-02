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


# --- History backfill -------------------------------------------------------------
# The free feed above has no history, so on days missing from data/history/fx.csv we
# fill in from the open fawazahmed0 currency API (dated daily files, no key).
HIST_URLS = ("https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{d}/v1/currencies/usd.min.json",
             "https://{d}.currency-api.pages.dev/v1/currencies/usd.min.json")


def fetch_day(sess, d):
    for u in HIST_URLS:
        try:
            r = sess.get(u.format(d=d), timeout=30)
            if r.status_code == 200:
                return {k.upper(): v for k, v in (r.json().get("usd") or {}).items()}
        except Exception:  # try the mirror
            continue
    return None


def backfill(sess, ccys, have_dates, as_of, days=35):
    """Returns {date: {ccy: rate}} for missing days in the last `days` days."""
    from datetime import date, timedelta
    t = date.fromisoformat(as_of)
    out = {}
    for i in range(1, days + 1):
        d = (t - timedelta(days=i)).isoformat()
        if d in have_dates:
            continue
        rates = fetch_day(sess, d)
        if rates:
            out[d] = {c: rates.get(c) for c in ccys if rates.get(c)}
    return out
