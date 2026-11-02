"""Unit tests for the parsers and scoring. No network needed: python -m pytest -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar import score
from radar.sources import enso, fao, hapi, usda


def test_oni_parse():
    txt = "SEAS  YR   TOTAL   ANOM\nJAS 2026  28.10  1.62\nASO 2026  28.30  1.81\n"
    rows = enso.parse(txt)
    assert rows[-1] == {"season": "ASO", "year": 2026, "anom": 1.81}


def test_usda_balance():
    rows = [{"attributeId": 125, "value": 20000}, {"attributeId": 176, "value": 3000},
            {"attributeId": 57, "value": 12500}, {"attributeId": 28, "value": 9800}]
    b = usda.balance(rows)
    assert b["stocks_to_use"] == 0.15 and b["import_dependence"] == 0.625


def test_hapi_latest_national():
    rows = [
        {"ipc_phase": "3+", "reference_period_start": "2025-06-01", "population_in_phase": 1,
         "population_fraction_in_phase": 0.1, "admin1_code": None},
        {"ipc_phase": "3+", "reference_period_start": "2026-09-01", "population_in_phase": 900,
         "population_fraction_in_phase": 0.45, "admin1_code": None, "ipc_type": "projected"},
        {"ipc_phase": "1", "reference_period_start": "2026-09-01", "population_in_phase": 5,
         "population_fraction_in_phase": 0.2},
    ]
    r = hapi.latest_national(rows)
    assert r["share_phase3plus"] == 0.45 and r["period_start"] == "2026-09-01"


def test_fao_parse():
    csv = ("FAO Food Price Index,,,,,,\n,,,,,,\nDate,Food Price Index,Meat,Dairy,Cereals,Oils,Sugar\n"
           "2026-08,125.1,120,140,110,150,105\n2026-09,126.0,121,139,112,152,104\n")
    s = fao.parse(csv)
    assert s[-1]["month"] == "2026-09" and s[-1]["food"] == 126.0


WHEAT = {"consumption": 10000, "ending_stocks": 1000, "imports": 10000, "import_dependence": 1.0,
         "prev_imports": 11000, "import_momentum": 1.15, "production_vs_avg": 0.9,
         "begin_stu": 0.12, "avg5_stu": 0.20}


def test_risk_and_tender():
    c = {"ipc": {"share_phase3plus": 0.40}, "fx_change_30d": 0.10, "psd": {"wheat": WHEAT}}
    s, parts = score.risk(c)
    assert s == 100 and score.band(s) == "Severe" and parts["confidence"] == "High"
    assert score.tender_signal(c) == "High, FX may delay"   # buying up 15% and a short harvest
    assert score.tender_signal(dict(c, fx_change_30d=0.0)) == "High"
    good_harvest = {"psd": {"wheat": dict(WHEAT, production_vs_avg=1.05)}}
    assert score.tender_signal(good_harvest) == "Low"
    strong_buying = {"psd": {"wheat": dict(WHEAT, production_vs_avg=1.05, import_momentum=1.3)}}
    assert score.tender_signal(strong_buying) == "Medium"
    small = {"psd": {"wheat": dict(WHEAT, prev_imports=100, imports=100)}}
    assert score.tender_signal(small) == "Low"
    assert score.classify(1.15, None) == "Low" and score.classify(None, 0.5) is None
    assert score.tender_signal({}) == "No data"
    assert score.risk({})[0] is None


def test_thin_scores_are_capped():
    supply_only = {"psd": {"wheat": WHEAT}, "income": "LIC"}          # 2 of 4 parts
    s, parts = score.risk(supply_only)
    assert s == 69 and score.band(s) == "Elevated" and parts["confidence"] == "Low"
    fx_only = {"fx_change_30d": 0.2}
    assert score.risk(fx_only)[0] == 44
    deep_crisis = {"ipc": {"share_phase3plus": 0.5}}                   # IPC alone can be Severe
    assert score.risk(deep_crisis)[0] == 100
    mild = {"ipc": {"share_phase3plus": 0.2}, "fx_change_30d": 0.2}
    assert score.risk(mild)[0] <= 69


def test_grain_totals_combine_crops():
    psd = {"wheat": {"consumption": 100, "ending_stocks": 10, "imports": 100},
           "rice": {"consumption": 300, "ending_stocks": 90, "imports": 0}}
    g = score.grain_totals(psd)
    assert g["stocks_to_use"] == 0.25 and g["import_dependence"] == 0.25


def test_fao_link_regex():
    page = '<a href="https://www.fao.org/media/docs/x/food_price_indices_data.csv?sfvrsn=523_84&amp;download=true">CSV</a>'
    m = fao.LINK_RE.search(page)
    assert m and "food_price_indices_data.csv" in m.group(1)


def test_usda_bulk_parse():
    import pandas as pd
    rows = []
    for yr, cons, stocks in [(2025, 20000, 4000), (2026, 20000, 3000)]:
        for attr, val in [("Production", 9800), ("Imports", 12500),
                          ("Domestic Consumption", cons), ("Ending Stocks", stocks)]:
            rows.append({"Commodity_Code": "410000", "Country_Code": "EG", "Market_Year": yr,
                         "Month": 10, "Attribute_Description": attr, "Value": val})
    rows.append({"Commodity_Code": "410000", "Country_Code": "XX", "Market_Year": 2026,
                 "Month": 10, "Attribute_Description": "Imports", "Value": 1})
    out, _, hist = usda.parse_bulk(pd.DataFrame(rows), {"wheat": "0410000"}, ["EG"])
    w = out["EG"]["wheat"]
    assert w["market_year"] == 2026 and w["stocks_to_use"] == 0.15 and w["import_dependence"] == 0.625
    assert w["begin_stu"] == 0.2 and set(hist["EG"]["wheat"]) == {2025, 2026}
    assert "XX" not in out


def test_usda_derive_momentum():
    ys = {y: {"production": 1000, "imports": 1000, "consumption": 2000, "ending_stocks": 400} for y in range(2019, 2027)}
    ys[2025]["imports"] = 1600    # bought a lot last year
    ys[2026]["production"] = 800  # and a small crop this year
    v = usda.derive(ys)
    assert v["import_momentum"] == round(1600 / 1120, 3) and v["production_vs_avg"] == 0.8
    assert score.classify(v["import_momentum"], v["production_vs_avg"]) == "High"


def test_backtest_counts_hits():
    from radar import backtest
    ys = {}
    for y in range(2005, 2016):
        ys[y] = {"consumption": 1000, "ending_stocks": 200, "imports": 800, "production": 300}
    ys[2012]["imports"] = 1000         # bought 20%+ above normal...
    ys[2013]["production"] = 200       # ...then a short harvest...
    ys[2013]["imports"] = 1100         # ...and 2013 imports well above average: a hit
    cs = backtest.cases({"EG": {"wheat": ys}}, {"EG": "Egypt"}, first=2010)
    hit = [c for c in cs if c["year"] == 2013][0]
    assert hit["level"] == "High" and hit["hit"]
    r = backtest.evaluate(cs)
    assert r["high"]["n"] == 1 and r["high"]["hits"] == 1

def test_universe():
    from radar import universe
    cfg = {"countries": [{"name": "Egypt", "iso3": "EGY", "fas": "EG", "fx": "EGP", "buyer": "MM"}],
           "universe": {"min_imports_kt": 300}}
    psd = {"EG": {"wheat": {"imports": 12000}}, "VM": {"wheat": {"imports": 3500}},
           "XX": {"corn": {"imports": 50}}, "E4": {"wheat": {"imports": 9000}}}
    names = {"EG": "Egypt", "VM": "Vietnam", "XX": "Iceland", "E4": "European Union"}
    ipc = {"SOM": {"name": "Somalia", "ipc": {"share_phase3plus": 0.2}}}
    lst, unmatched = universe.build(cfg, psd, names, ipc)
    by = {c["iso3"]: c for c in lst}
    assert set(by) == {"EGY", "VNM", "SOM"}          # Iceland too small, EU is an aggregate
    assert by["VNM"]["fx"] == "VND" and by["VNM"]["fas"] == "VM"
    assert by["EGY"]["buyer"] == "MM" and by["EGY"]["core"]


def test_income_scaling():
    base = {"fx_change_30d": 0.0, "psd": {"wheat": dict(WHEAT, ending_stocks=500)}}
    poor = score.risk(dict(base, income="LIC"))[0]
    rich = score.risk(dict(base, income="HIC"))[0]
    assert rich < poor / 2


def test_changes_and_offers():
    from radar import changes, offers
    prev = {"countries": [{"iso3": "EGY", "risk": 50, "risk_band": "Elevated", "tender": "Medium"}]}
    snaps = {"2026-10-26": prev}
    rows = [{"iso3": "EGY", "name": "Egypt", "risk": 72, "risk_band": "Severe", "tender": "High",
             "fx_change_7d": 0.06, "income": "LMC", "psd": {"wheat": {"imports": 12000}, "corn": {"imports": 9000}}},
            {"iso3": "VNM", "name": "Vietnam", "risk": 30, "risk_band": "Watch", "tender": "Low", "psd": {}}]
    alerts, movers, base = changes.apply(rows, snaps, "2026-11-02")
    kinds = {a["kind"] for a in alerts if a["iso3"] == "EGY"}
    assert base == "2026-10-26" and {"band_up", "tender", "fx"} <= kinds
    assert any(a["iso3"] == "VNM" and a["kind"] == "new" for a in alerts)
    assert movers["up"][0]["change"] == 22
    o = offers.rank(rows)
    assert len(o) == 1 and o[0]["iso3"] == "EGY" and o[0]["black_sea"]
    h = changes.history(snaps, rows, "2026-11-02")
    assert [p["risk"] for p in h["EGY"]] == [50, 72]
