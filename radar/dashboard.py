"""Builds the static site: site/index.html, one page per country, data.json and assets."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "templates"


def _embed(obj):
    return json.dumps(obj, default=str).replace("</", "<\\/")  # safe inside <script>


def build(snap, out=ROOT, history=None):
    history = history or {}
    site = Path(out) / "site"
    if site.exists():
        shutil.rmtree(site)
    (site / "c").mkdir(parents=True)
    shutil.copytree(TPL / "vendor", site / "vendor")
    shutil.copy(TPL / "style.css", site / "style.css")

    (site / "index.html").write_text((TPL / "dashboard.html").read_text().replace("__DATA__", _embed(snap)))
    (site / "data.json").write_text(json.dumps(snap, indent=2, default=str))

    ctpl = (TPL / "country.html").read_text()
    for c in snap["countries"]:
        page = {"as_of": snap["as_of"], "mode": snap["mode"], "country": c,
                "history": history.get(c["iso3"], [])}
        html = ctpl.replace("__NAME__", c["name"].replace("<", "")).replace("__DATA__", _embed(page))
        (site / "c" / f"{c['iso3']}.html").write_text(html)
    (site / ".nojekyll").write_text("")
    return site / "index.html"
