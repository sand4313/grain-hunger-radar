"""Shared HTTP session with retries and a polite User-Agent."""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

UA = "GrainHungerRadar/1.0 (+https://github.com)"


def session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET", "POST"))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers["User-Agent"] = UA
    return s
