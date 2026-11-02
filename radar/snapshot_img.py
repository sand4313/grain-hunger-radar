"""Saves daily share images of the dashboard (site/og/*.png) for the beehiiv site and social posts.

Run after the site is built:  python -m radar.snapshot_img
Needs Playwright with Chromium (installed in the GitHub workflow). Never fails the run.
"""
import functools
import http.server
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not installed; skipping images")
        return 0
    (SITE / "og").mkdir(exist_ok=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
            pg.emulate_media(color_scheme="light")
            pg.goto(url, wait_until="networkidle")
            pg.wait_for_selector("#map path.c", timeout=20000)
            pg.locator(".mapbox").screenshot(path=str(SITE / "og" / "map.png"))
            pg.locator(".hero").screenshot(path=str(SITE / "og" / "overview.png"))
            pg.click("[data-tab=opps]")
            pg.locator("#opps").screenshot(path=str(SITE / "og" / "opportunities.png"))
            b.close()
        print("saved site/og/map.png, overview.png, opportunities.png")
    except Exception as e:  # images are a nice-to-have; never break the daily run
        print(f"image capture failed: {e}", file=sys.stderr)
    finally:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
