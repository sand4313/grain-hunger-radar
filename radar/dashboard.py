"""Builds site/index.html (static, GitHub Pages) and site/data.json from the snapshot."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build(snap, out=ROOT):
    tpl = (ROOT / "templates" / "dashboard.html").read_text()
    payload = json.dumps(snap, default=str).replace("</", "<\\/")  # safe inside <script>
    site = Path(out) / "site"
    site.mkdir(exist_ok=True)
    (site / "index.html").write_text(tpl.replace("__DATA__", payload))
    (site / "data.json").write_text(json.dumps(snap, indent=2, default=str))
    return site / "index.html"
