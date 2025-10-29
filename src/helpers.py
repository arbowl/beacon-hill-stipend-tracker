import json
import re
import time
from typing import Optional
import urllib.error
import urllib.request
from math import radians, sin, cos, sqrt, atan2
from sys import stderr

from src.models import (
    API_BASE,
    GEOCODE_CACHE,
    STATE_HOUSE_LATLON,
    TIER_OVERRIDES,
    VICECHAIR_TIER_A_COMMITTEES
)


def list_members(members: list[dict]) -> None:
    print("\nMembers (API):")
    for m in members[:10]:
        code = m['member_code']
        name = m['name']
        branch = m['branch']
        district = m['district']
        print(f"- {code:>6} — {name} ({branch}, {district})")
    if len(members) > 10:
        print(f"... and {len(members)-10} more")


def api_get(
    url_or_path: str, max_retries: int = 3, backoff: float = 1.0
) -> Optional[dict]:
    """
    Fetch data from MA Legislature API with retry logic.

    Args:
        url_or_path: Full URL or path (will be prefixed with API_BASE)
        max_retries: Maximum number of retry attempts
        backoff: Initial backoff delay in seconds (doubles on each retry)

    Returns:
        Parsed JSON response or None on failure
    """
    if url_or_path.startswith("http"):
        url = url_or_path
    else:
        url = f"{API_BASE}{url_or_path}"

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "stipend-tracker/1.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):  # Retryable errors
                if attempt < max_retries - 1:
                    delay = backoff * (2 ** attempt)
                    print(
                        f"[HTTP {e.code}] {url} - "
                        f"retrying in {delay:.1f}s...",
                        file=stderr,
                    )
                    time.sleep(delay)
                    continue
            print(f"[HTTP {e.code}] {url}", file=stderr)
            return None
        except urllib.error.URLError as e:
            if attempt < max_retries - 1:
                delay = backoff * (2 ** attempt)
                print(
                    f"[Network error] {url} - "
                    f"retrying in {delay:.1f}s...",
                    file=stderr,
                )
                time.sleep(delay)
                continue
            print(f"[Network error] {url}: {e.reason}", file=stderr)
            return None
        except (OSError, ValueError) as e:
            print(f"[ERROR] {url}: {e}", file=stderr)
            return None

    return None


def haversine_miles(
    a_latlon: tuple[float, float], b_latlon: tuple[float, float]
) -> float:
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


def map_committee_role(
    committee_name: str, role_label: str
) -> Optional[str]:
    """
    Map a committee role to its stipend key.

    Args:
        committee_name: Full name of the committee
        role_label: Role label from API (e.g., "Chair", "Vice Chair")

    Returns:
        Stipend key (e.g., "WAYS_MEANS_CHAIR", "COMMITTEE_VICECHAIR_TIER_A")
        or None
    """
    role_label = (role_label or "").strip()
    if role_label not in ("Chair", "Vice Chair"):
        return None

    if role_label == "Chair":
        # Check if this committee has a special tier override
        special = TIER_OVERRIDES.get(committee_name)
        if special:
            return special
        # Default to Tier B for all other committees
        return "COMMITTEE_CHAIR_TIER_B"

    # Vice chairs have tiered stipends
    if role_label == "Vice Chair":
        # Ways & Means vice chairs get special higher stipend
        if "Ways and Means" in committee_name:
            return "WAYS_MEANS_VICECHAIR"
        # Check if this is a Tier A committee for vice chairs
        # Note: Vice chair Tier A list differs from chair Tier A list
        # Check if any of the keywords appear in the committee name
        for keyword in VICECHAIR_TIER_A_COMMITTEES:
            if keyword in committee_name:
                return "COMMITTEE_VICECHAIR_TIER_A"
        # All other vice chairs get Tier B stipend
        return "COMMITTEE_VICECHAIR_TIER_B"

    return None


def normalize_legislator_name(name: str) -> str:
    """
    Normalize a legislator name for matching purposes.

    Args:
        name: Raw name from HTML (e.g., "Rep. John Q. Smith, Jr.")

    Returns:
        Normalized name (e.g., "john q smith jr")
    """
    if not name:
        return ""

    # Remove titles
    pattern = r'\b(Rep\.|Sen\.|Representative|Senator)\b'
    name = re.sub(pattern, '', name, flags=re.I)

    # Remove punctuation except spaces and hyphens
    name = re.sub(r'[^\w\s\-]', ' ', name)

    # Normalize whitespace
    name = ' '.join(name.split())

    # Lowercase
    return name.lower().strip()
