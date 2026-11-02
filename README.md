# Grain & Hunger Radar — data engine

Pulls hunger, grain-balance, price, currency and climate data every day, scores
15 importing countries, and publishes a dashboard plus a weekly brief draft.

```
APIs ──► run.py ──► data/latest.json ──► site/index.html  (GitHub Pages dashboard)
                     data/history/      └► briefs/YYYY-MM-DD.md (paste into beehiiv)
                     data/snapshots/
```

## Data sources

| Source | What it gives | Key needed | Secret name |
|---|---|---|---|
| ExchangeRate-API open endpoint | Daily FX vs USD (30-day moves built from our own history) | No | — |
| NOAA CPC ONI | El Niño / La Niña phase | No | — |
| World Bank Pink Sheet | Monthly wheat, maize, sunflower oil, urea, DAP prices | No | — |
| FAO Food Price Index | Monthly food, cereal, oil indices | No | — |
| HDX HAPI (IPC) | Share of people in IPC Phase 3+ | Free identifier | `HAPI_APP_IDENTIFIER` |
| USDA FAS PSD | Wheat & corn stocks, imports, consumption | Free key | `USDA_FAS_API_KEY` |
| ReliefWeb v2 | Latest food-security reports per country | Approved appname | `RELIEFWEB_APPNAME` |

A source with no key is skipped and listed on the dashboard; everything else still runs.
The first four work with zero setup.

## Setup (one time, ~20 minutes)

1. **Create the repo.** On GitHub: New repository → name `grain-hunger-radar` → Create.
   Upload all files from this folder (drag and drop works), including the `.github` folder.
2. **Turn on Pages.** Settings → Pages → Source: **GitHub Actions**.
3. **Get the keys** (all free):
   - HAPI: open `https://hapi.humdata.org/api/v2/encode_app_identifier?application=grain-hunger-radar&email=YOUR_EMAIL`
     and copy `encoded_app_identifier`.
   - USDA FAS: sign up at https://apps.fas.usda.gov/opendatawebv2/#/signup — the key arrives by email.
   - ReliefWeb: request an appname at https://apidoc.reliefweb.int/parameters#appname —
     they review it and email the approved name (can take a few days).
4. **Add them as secrets.** Settings → Secrets and variables → Actions → New repository secret,
   using the secret names in the table above.
5. **First run.** Actions → "Radar daily run" → Run workflow. When it's green, the dashboard
   link is in Settings → Pages. After that it runs by itself every day at 05:17 UTC.

## Test locally without internet

```
pip install -r requirements.txt
python -m pytest -q tests
python run.py --offline     # writes sample_output/ with clearly labelled sample data
```

## Things to verify on the first live run

- **USDA country codes and attribute ids** (`config/countries.yaml`, `radar/sources/usda.py`):
  check against `/api/psd/countries` and `/api/psd/commodityAttributes`.
- **USDA marketing year:** the run asks for the calendar year; some countries' wheat
  year starts mid-year, so compare with PSD Online once.
- **World Bank / FAO links** are found by scanning their download pages; if either page is
  redesigned the source shows "failed" on the dashboard and the regex needs a tweak.
- **FX moves need 30 days of history.** The FX 30d column fills in a month after the first run.

## The risk score

A transparent heuristic, not a forecast: hunger (IPC 3+ share) 35%, currency loss 20%,
wheat stocks-to-use 25%, wheat import dependence 20%. Weights are in `radar/score.py`.
The tender signal flags big importers with thin stocks. Tune both as you learn the market.

## Paywall note

GitHub Pages is public. Keep the full dashboard for Pro readers by either (a) linking it
only from paid beehiiv posts, or (b) later moving `site/` behind Cloudflare Access or a
beehiiv premium page.

Rates By Exchange Rate API — https://www.exchangerate-api.com
