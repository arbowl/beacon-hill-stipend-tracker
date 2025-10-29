import json
from typing import Optional
import urllib.error
import urllib.request
from math import radians, sin, cos, sqrt, atan2
from sys import stderr

from src.models import (
    API_BASE,
    GEOCODE_CACHE,
    STATE_HOUSE_LATLON,
    TIER_OVERRIDES
)


def list_members(members: list[str]) -> None:
    print("\nMembers (API):")
    for m in members[:10]:
        print(f"- {m['member_code']:>6} — {m['name']} ({m['branch']}, {m['district']})")
    if len(members) > 10:
        print(f"... and {len(members)-10} more")


def api_get(url_or_path: str) -> Optional[dict]:
    if url_or_path.startswith("http"):
        url = url_or_path
    else:
        url = f"{API_BASE}{url_or_path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "stipend-demo/0.1"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"[HTTP {e.code}] {url}", file=stderr)
    except Exception as e:
        print(f"[ERROR] {url}: {e}", file=stderr)
    return None


def haversine_miles(a_latlon: int, b_latlon: int) -> float:
    R = 3958.7613
    lat1, lon1 = map(radians, a_latlon)
    lat2, lon2 = map(radians, b_latlon)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return 2 * R * atan2(sqrt(h), sqrt(1 - h))


def geocode(locality: str) -> Optional[tuple[float, float]]:
    if not locality:
        return None
    key = (locality.strip()
           .replace("City of ", "")
           .replace("Town of ", "")
           .replace(" (part)", ""))
    return GEOCODE_CACHE.get(key)


def distance_band_for_locality(
    locality: str
) -> tuple[Optional[str], Optional[float]]:
    ll = geocode(locality)
    if not ll:
        return None, None
    miles = round(haversine_miles((ll[0], ll[1]), STATE_HOUSE_LATLON), 1)
    return ("LE50" if miles <= 50.0 else "GT50"), miles


def map_committee_role(committee_name: str, role_label: str) -> Optional[str]:
    role_label = (role_label or "").strip()
    if role_label not in ("Chair", "Vice Chair"):
        return None
    if role_label == "Chair":
        special = TIER_OVERRIDES.get(committee_name)
        return special or "COMMITTEE_CHAIR_TIER_A"
    return "COMMITTEE_VICECHAIR"
