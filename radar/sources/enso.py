"""NOAA Oceanic Nino Index (ONI). El Nino when anomaly >= +0.5, strong when >= +1.5."""
URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"


def parse(text):
    rows = []
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 4:
            try:
                rows.append({"season": parts[0], "year": int(parts[1]), "anom": float(parts[3])})
            except ValueError:
                continue
    return rows


def fetch(sess):
    r = sess.get(URL, timeout=30)
    r.raise_for_status()
    rows = parse(r.text)
    last = rows[-1]
    a = last["anom"]
    phase = ("Strong El Nino" if a >= 1.5 else "El Nino" if a >= 0.5
             else "La Nina" if a <= -0.5 else "Neutral")
    return {"latest": last, "phase": phase, "recent": rows[-12:]}
