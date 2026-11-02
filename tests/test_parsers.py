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


def test_risk_and_tender():
    c = {"ipc": {"share_phase3plus": 0.40}, "fx_change_30d": 0.10,
         "psd": {"wheat": {"stocks_to_use": 0.10, "import_dependence": 1.0}}}
    s, parts = score.risk(c)
    assert s == 100 and score.band(s) == "Severe"
    assert score.tender_signal(c).startswith("High")
    assert score.risk({})[0] is None


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
    out, _ = usda.parse_bulk(pd.DataFrame(rows), {"wheat": "0410000"}, ["EG"])
    w = out["EG"]["wheat"]
    assert w["market_year"] == 2026 and w["stocks_to_use"] == 0.15 and w["import_dependence"] == 0.625
    assert "XX" not in out


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
