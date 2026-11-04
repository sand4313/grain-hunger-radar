"""ReliefWeb v2: latest food-security reports per country.

Needs RELIEFWEB_APPNAME, a pre-approved appname requested at
https://apidoc.reliefweb.int/parameters#appname (arbitrary names get HTTP 403).
"""
URL = "https://api.reliefweb.int/v2/reports"


def fetch(sess, iso3, appname, limit=5):
    # Only reports ReliefWeb itself tags with the "Food and Nutrition" theme, so a loose
    # keyword match (say, "security" in a peace-and-security speech) cannot slip in.
    body = {
        "filter": {"operator": "AND", "conditions": [
            {"field": "country.iso3", "value": iso3.lower()},
            {"field": "theme.name", "value": "Food and Nutrition"},
        ]},
        "sort": ["date.created:desc"],
        "limit": limit,
        "fields": {"include": ["title", "url_alias", "date.created", "source.shortname"]},
    }
    r = sess.post(URL, params={"appname": appname}, json=body, timeout=60)
    r.raise_for_status()
    out = []
    for item in r.json().get("data", []):
        f = item.get("fields", {})
        out.append({
            "title": f.get("title"),
            "url": f.get("url_alias") or f"https://reliefweb.int/node/{item.get('id')}",
            "date": (f.get("date") or {}).get("created", "")[:10],
            "source": ", ".join(s.get("shortname", "") for s in f.get("source", [])),
        })
    return out
