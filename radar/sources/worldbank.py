"""World Bank Pink Sheet monthly commodity prices (no key).

The workbook URL carries a hash that changes each month, so we find the current
link on the commodity-markets page first, then read the 'Monthly Prices' sheet.
"""
import io
import re

import pandas as pd

PAGE = "https://www.worldbank.org/en/research/commodity-markets"
LINK_RE = re.compile(r'href="([^"]*CMO-Historical-Data-Monthly\.xlsx)"', re.I)


def find_url(sess):
    r = sess.get(PAGE, timeout=60)
    r.raise_for_status()
    m = LINK_RE.search(r.text)
    if not m:
        raise RuntimeError("Pink Sheet link not found on World Bank page")
    url = m.group(1)
    return url if url.startswith("http") else "https://www.worldbank.org" + url


def parse(xlsx_bytes, wanted):
    raw = pd.read_excel(io.BytesIO(xlsx_bytes), sheet_name="Monthly Prices", header=None)
    # Header row = the row that contains the first wanted name
    hdr = next(i for i in range(min(15, len(raw)))
               if any(str(v).strip() == wanted[0] for v in raw.iloc[i].values))
    names = [str(v).strip() for v in raw.iloc[hdr].values]
    data = raw.iloc[hdr + 1:]
    data = data[data[0].astype(str).str.match(r"^\d{4}M\d{2}$")]
    out = {}
    for w in wanted:
        if w not in names:
            continue
        col = names.index(w)
        series = pd.to_numeric(data[col], errors="coerce")
        dates = data[0].astype(str).str.replace("M", "-")
        pts = [{"month": d, "value": round(float(v), 2)}
               for d, v in zip(dates, series) if pd.notna(v)]
        out[w] = pts[-36:]  # last three years
    return out


def fetch(sess, wanted):
    url = find_url(sess)
    r = sess.get(url, timeout=120)
    r.raise_for_status()
    return {"source_url": url, "series": parse(r.content, wanted)}
