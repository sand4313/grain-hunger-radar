"""Builds the list of countries to watch, every run, from the data itself.

A country is included when any of these is true:
  - it is in config/countries.yaml (your core list, with buyer names)
  - USDA shows it importing at least `min_imports_kt` thousand tonnes of wheat or corn
  - IPC has a national food-security analysis for it
"""
import pycountry
from babel.numbers import get_territory_currencies

# USDA PSD country names that the standard lookup gets wrong or can't find
NAME_FIX = {
    "Burma": "MMR", "Korea, South": "KOR", "Korea, North": "PRK", "Congo (Kinshasa)": "COD",
    "Congo (Brazzaville)": "COG", "Cote d'Ivoire": "CIV", "Turkey": "TUR", "Turkiye": "TUR",
    "Vietnam": "VNM", "Iran": "IRN", "Syria": "SYR", "Russia": "RUS", "Taiwan": "TWN",
    "Bolivia": "BOL", "Venezuela": "VEN", "Tanzania": "TZA", "Laos": "LAO", "Moldova": "MDA",
    "Gambia, The": "GMB", "Bahamas, The": "BHS", "Cabo Verde": "CPV", "Cape Verde": "CPV",
    "Macedonia": "MKD", "North Macedonia": "MKD", "Eswatini": "SWZ", "Swaziland": "SWZ",
    "Hong Kong": "HKG", "Sudan": "SDN", "South Sudan": "SSD", "Gaza Strip": "PSE",
    "West Bank": "PSE", "Palestine": "PSE", "Micronesia": "FSM", "Brunei": "BRN",
    "Czechia": "CZE", "Czech Republic": "CZE", "Slovakia": "SVK",
}
SKIP_WORDS = ("european union", "eu-", "other", "world", "former", "yugoslav", "ussr", "total")


def iso3_for(name):
    if name in NAME_FIX:
        return NAME_FIX[name]
    if any(w in name.lower() for w in SKIP_WORDS):
        return None
    try:
        return pycountry.countries.lookup(name).alpha_3
    except LookupError:
        try:
            return pycountry.countries.search_fuzzy(name)[0].alpha_3
        except LookupError:
            return None


def currency_for(iso3):
    c = pycountry.countries.get(alpha_3=iso3)
    if not c:
        return None
    cur = get_territory_currencies(c.alpha_2)
    return cur[0] if cur else None


def build(cfg, psd_all, psd_names, ipc_all):
    """psd_all: {fas_code: {crop: balance}}, psd_names: {fas_code: name},
    ipc_all: {iso3: {"name": ..., "ipc": {...}}}. Returns list of country dicts."""
    min_kt = cfg.get("universe", {}).get("min_imports_kt", 300)
    core = {c["iso3"]: dict(c) for c in cfg["countries"]}
    out = dict(core)
    unmatched = []

    iso_to_fas = {}
    for fas, name in psd_names.items():
        iso = iso3_for(name)
        if not iso:
            unmatched.append(name)
            continue
        iso_to_fas.setdefault(iso, fas)
        crops = psd_all.get(fas) or {}
        imports = max((crops.get(k) or {}).get("imports", 0) for k in ("wheat", "corn")) if crops else 0
        if imports >= min_kt and iso not in out:
            out[iso] = {"name": name, "iso3": iso, "fas": fas}

    for iso, rec in ipc_all.items():
        if iso not in out:
            out[iso] = {"name": rec.get("name") or iso, "iso3": iso}

    for iso, c in out.items():
        c.setdefault("fas", iso_to_fas.get(iso))
        c.setdefault("fx", currency_for(iso))
        c.setdefault("buyer", "")
        c["core"] = iso in core
        pc = pycountry.countries.get(alpha_3=iso)
        if pc and c["name"] == iso:
            c["name"] = getattr(pc, "common_name", pc.name)
    return list(out.values()), sorted(set(unmatched))
