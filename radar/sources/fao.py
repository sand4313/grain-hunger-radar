"""FAO Food Price Index (monthly). The download link is read from the FAO page."""
import io
import re

import pandas as pd

PAGE = "https://www.fao.org/worldfoodsituation/foodpricesindex/en/"
LINK_RE = re.compile(r'href="([^"]*Food_price_indices_data[^"]*\.csv)"', re.I)


def parse(csv_text):
    raw = pd.read_csv(io.StringIO(csv_text), header=None, dtype=str)
    hdr = next(i for i in range(min(10, len(raw))) if str(raw.iloc[i, 0]).strip().lower() == "date")
    df = raw.iloc[hdr + 1:, :7]
    df.columns = ["date", "food", "meat", "dairy", "cereals", "oils", "sugar"]
    df = df.dropna(subset=["food"])
    for c in df.columns[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["food"])
    return [{"month": d, "food": f, "cereals": c, "oils": o}
            for d, f, c, o in zip(df["date"], df["food"], df["cereals"], df["oils"])][-36:]


def fetch(sess):
    r = sess.get(PAGE, timeout=60)
    r.raise_for_status()
    m = LINK_RE.search(r.text)
    if not m:
        raise RuntimeError("FAO CSV link not found")
    url = m.group(1)
    if not url.startswith("http"):
        url = "https://www.fao.org" + url
    csv = sess.get(url, timeout=60)
    csv.raise_for_status()
    return {"source_url": url, "series": parse(csv.text)}
