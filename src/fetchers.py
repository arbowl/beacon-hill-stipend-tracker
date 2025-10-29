from datetime import datetime
import json
from pathlib import Path
from sys import stderr
from typing import Optional

from src.helpers import api_get


def get_gc_number(session: dict) -> int:
    return session.get("Number") or session.get("GeneralCourtNumber")


def get_gc_name(session: dict) -> str:
    return session.get("Name", "")


def pick_session() -> Optional[dict]:
    sessions = api_get("/GeneralCourts/Sessions")
    if not sessions:
        print("Could not fetch sessions from API.")
        return None
    sessions_sorted = sorted(
        sessions,
        key=lambda s: get_gc_number(s) or 0,
        reverse=True
    )
    print("\nAvailable General Courts (most recent first):")
    for i, s in enumerate(sessions_sorted[:12], 1):
        print(f"{i:2d}) GC {get_gc_number(s)} — {get_gc_name(s)}")
    sel = input("Select a session by number (default 1): ").strip() or "1"
    try:
        choice = int(sel)
        if choice < 1 or choice > len(sessions_sorted[:12]):
            raise ValueError
    except ValueError:
        print("Invalid. Using most recent.")
        choice = 1
    return sessions_sorted[choice - 1]


def load_members_cache(gc_number: int) -> tuple[Optional[list[dict]], Optional[str]]:
    """Attempts to load members from cache, returns (members, cache_date) or (None, None)."""
    cache_dir = Path(__file__).parent.parent / "data" / "cache"
    cache_file = cache_dir / f"members_{gc_number}.json"
    if not cache_file.exists():
        return None, None
    try:
        with open(cache_file, "r") as f:
            data = json.load(f)
            return data["members"], data["cached_at"]
    except Exception as e:
        print(f"Error loading cache: {e}", file=stderr)
        return None, None


def save_members_cache(gc_number: int, members: list[dict]) -> None:
    """Saves members data to cache file."""
    cache_dir = Path(__file__).parent / "data" / "cache"
    cache_file = cache_dir / f"members_{gc_number}.json"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "members": members,
            "cached_at": datetime.now().isoformat(),
        }
        with open(cache_file, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving cache: {e}", file=stderr)


def fetch_members(gc_number: int) -> list[dict]:
    cached_members, cache_date = load_members_cache(gc_number)
    if cached_members:
        print(f"Using cached members data from {cache_date}")
        return cached_members
    print("Fetching members from API...")
    listing = api_get(f"/GeneralCourts/{gc_number}/LegislativeMembers") or []
    members = []
    stub: dict[str, str]
    for idx, stub in enumerate(listing):
        print(f"Fetching {stub} ({idx + 1}/{len(listing)})...")
        code = stub.get("MemberCode")
        details_path = stub.get("Details")
        if not code or not details_path:
            continue
        detail = api_get(details_path)
        if not detail:
            continue
        name = detail.get("Name") or detail.get("FullName")
        branch = detail.get("Branch") or detail.get("Chamber")
        district = detail.get("District")
        party = detail.get("Party") or detail.get("PartyAffiliation")
        members.append({
            "member_code": code,
            "name": name,
            "branch": branch,
            "district": district,
            "party": party,
            "details_url": details_path,
        })
    save_members_cache(gc_number, members)
    return members


def fetch_leadership(branch: str) -> list[dict]:
    data = api_get(f"/Branches/{branch}/Leadership")
    out = []
    if not data:
        return out
    row: dict[str, str]
    for row in data:
        m = row.get("Member", {})
        out.append({
            "member_code": (m.get("Details") or "").split("/")[-1],
            "position": row.get("Position"),
        })
    return out


def fetch_committees(gc_number: int) -> list[dict]:
    data = api_get(f"/GeneralCourts/{gc_number}/Committees")
    return data or []


def load_committee_cache(
    gc_number: int, committee_code: str
) -> tuple[Optional[dict], Optional[str]]:
    """Load cached committee detail if it exists. Returns (detail, cached_at)
    or (None, None).
    """
    cache_dir = Path(__file__).parent.parent / "data" / "cache"
    safe_code = str(committee_code).replace("/", "_").replace(" ", "_")
    cache_file = cache_dir / f"committee_{gc_number}_{safe_code}.json"
    if not cache_file.exists():
        return None, None
    try:
        with open(cache_file, "r") as f:
            data = json.load(f)
            return data.get("detail"), data.get("cached_at")
    except Exception as e:
        print(f"Error loading committee cache: {e}", file=stderr)
        return None, None


def save_committee_cache(gc_number: int, committee_code: str, detail: dict) -> None:
    """Save committee detail to cache file."""
    cache_dir = Path(__file__).parent / "data" / "cache"
    safe_code = str(committee_code).replace("/", "_").replace(" ", "_")
    cache_file = cache_dir / f"committee_{gc_number}_{safe_code}.json"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "detail": detail,
            "cached_at": datetime.now().isoformat(),
        }
        with open(cache_file, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving committee cache: {e}", file=stderr)


def fetch_committee_detail(gc_number: int, committee_code: str) -> Optional[dict]:
    cached, cached_at = load_committee_cache(gc_number, committee_code)
    if cached:
        print(f"Using cached committee detail for {committee_code} from {cached_at}")
        return cached
    print(f"Fetching committee detail from API for {committee_code}...")
    detail = api_get(f"/GeneralCourts/{gc_number}/Committees/{committee_code}")
    if detail:
        save_committee_cache(gc_number, committee_code, detail)
    return detail
