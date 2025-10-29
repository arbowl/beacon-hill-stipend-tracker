#!/usr/bin/env python3
"""
Console demo that uses the Massachusetts Legislature API for roster, leadership,
and committee chairs/vice-chairs — then calculates stipend totals using SAMPLE
cycle config + SAMPLE geocoding + SAMPLE payroll placeholders.

Replace SAMPLE sections with real data sources as you expand the pipeline.
"""

import json
import sys
import time
import urllib.request
import urllib.error
from math import radians, sin, cos, atan2, sqrt
from datetime import date
from textwrap import dedent

API_BASE = "https://malegislature.gov/api"

# =============================================================================
# SAMPLE DATA — replace with real sources in your pipeline
# =============================================================================

CYCLE_CONFIG = {
    "cycle": "2025-2026",
    "effective_date": "2025-01-01",
    "base_salary": 82000,  # SAMPLE — set from biennial update for cycle
    "expense_bands": {"LE50": 22431, "GT50": 29908},  # SAMPLE — §9C band amounts this cycle
    # SAMPLE — §9B amounts after biennial adjustment for this cycle
    "stipends": {
        "SPEAKER": 80000,
        "SENATE_PRESIDENT": 80000,
        "MAJORITY_LEADER": 60000,
        "MINORITY_LEADER": 60000,
        "PRESIDENT_PRO_TEMPORE": 50000,
        "SPEAKER_PRO_TEMPORE": 50000,
        "WAYS_MEANS_CHAIR": 65000,
        "WAYS_MEANS_VICECHAIR": 15000,
        "COMMITTEE_CHAIR_TIER_A": 30000,
        "COMMITTEE_CHAIR_TIER_B": 15000,
        "COMMITTEE_VICECHAIR": 5200,
        "WHIP": 30000,
        "ASST_MAJ_WHIP": 30000,
        "ASST_MIN_WHIP": 30000,
    },
}

# SAMPLE — Offline gazetteer for MA localities. Use MassGIS/US Census to fill fully.
GEOCODE_CACHE = {
    "Boston": [42.3601, -71.0589],
    "Springfield": [42.1015, -72.5898],
    "Worcester": [42.2626, -71.8023],
    "Framingham": [42.2793, -71.4162],
    "Pittsfield": [42.4501, -73.2454],
}
STATE_HOUSE_LATLON = (42.3570, -71.0630)

# SAMPLE — “actual payroll” placeholders for variance demo (replace with CTHRU join later)
PAYROLL_ACTUAL = {}

# SAMPLE — Home locality overrides keyed by MemberCode (API stable key)
# If API doesn’t provide a residence field, add here to compute expense band.
HOME_LOCALITY_OVERRIDES = {
    # "M123": "Framingham",
}

# =============================================================================
# Helpers
# =============================================================================

def api_get(url_or_path: str):
    # allow either relative or full URLs
    if url_or_path.startswith("http"):
        url = url_or_path
    else:
        url = f"{API_BASE}{url_or_path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "stipend-demo/0.1"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"[HTTP {e.code}] {url}", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] {url}: {e}", file=sys.stderr)
    return None

def haversine_miles(a_latlon, b_latlon):
    R = 3958.7613
    lat1, lon1 = map(radians, a_latlon)
    lat2, lon2 = map(radians, b_latlon)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return 2 * R * atan2(sqrt(h), sqrt(1 - h))

def geocode(locality: str):
    if not locality:
        return None
    key = (locality.strip()
           .replace("City of ", "")
           .replace("Town of ", "")
           .replace(" (part)", ""))
    return GEOCODE_CACHE.get(key)

def distance_band_for_locality(locality: str):
    ll = geocode(locality)
    if not ll:
        return None, None
    miles = round(haversine_miles((ll[0], ll[1]), STATE_HOUSE_LATLON), 1)
    return ("LE50" if miles <= 50.0 else "GT50"), miles

# Normalize role labels → stipend keys
ROLE_MAP = {
    # Leadership titles as they tend to appear
    "Speaker of the House": "SPEAKER",
    "President of the Senate": "SENATE_PRESIDENT",
    "Majority Leader": "MAJORITY_LEADER",
    "Minority Leader": "MINORITY_LEADER",
    "President Pro Tempore": "PRESIDENT_PRO_TEMPORE",
    "Speaker Pro Tempore": "SPEAKER_PRO_TEMPORE",
    "Majority Whip": "WHIP",
    "Minority Whip": "WHIP",
    "Assistant Majority Whip": "ASST_MAJ_WHIP",
    "Assistant Minority Whip": "ASST_MIN_WHIP",
    # Committee roles (API will give committee + role label)
    "Chair": "COMMITTEE_CHAIR_TIER_A",      # default to Tier A
    "Vice Chair": "COMMITTEE_VICECHAIR",
}

# Committees that should map to higher/lower tiers explicitly
TIER_OVERRIDES = {
    "House Committee on Ways and Means": "WAYS_MEANS_CHAIR",
    "Senate Committee on Ways and Means": "WAYS_MEANS_CHAIR",
    "House Committee on Rules": "COMMITTEE_CHAIR_TIER_A",
    "Senate Committee on Rules": "COMMITTEE_CHAIR_TIER_A",
}

def map_committee_role(committee_name: str, role_label: str) -> str | None:
    if role_label not in ("Chair", "Vice Chair"):
        return None
    if role_label == "Chair":
        return TIER_OVERRIDES.get(committee_name, "COMMITTEE_CHAIR_TIER_A")
    return "COMMITTEE_VICECHAIR"


# =============================================================================
# Data fetchers via API
# =============================================================================

def get_gc_number(session: dict) -> int:
    # tolerate either field name
    return session.get("Number") or session.get("GeneralCourtNumber")

def get_gc_name(session: dict) -> str:
    return session.get("Name", "")

def pick_session() -> dict | None:
    sessions = api_get("/GeneralCourts/Sessions")
    if not sessions:
        print("Could not fetch sessions from API.")
        return None

    # sort by the numeric GC value, descending
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

def fetch_members(gc_number: int) -> list[dict]:
    listing = api_get(f"/GeneralCourts/{gc_number}/LegislativeMembers") or []
    out = []
    for stub in listing:
        code = stub.get("MemberCode")
        details_path = stub.get("Details")
        if not code or not details_path:
            continue

        # Follow the details link (or build it explicitly)
        detail = api_get(details_path) or api_get(f"/GeneralCourts/{gc_number}/LegislativeMembers/{code}")
        if not detail:
            out.append({"member_code": code, "name": None, "branch": None, "district": None, "party": None, "details_url": details_path})
            continue

        # Field names can vary; be tolerant
        name = detail.get("Name") or detail.get("FullName") or None
        branch = detail.get("Branch") or detail.get("Chamber") or None
        district = (detail.get("District")
                    or detail.get("DistrictName")
                    or detail.get("DistrictDescription")
                    or None)
        party = detail.get("Party") or detail.get("PartyAffiliation") or None

        out.append({
            "member_code": code,
            "name": name,
            "branch": branch,
            "district": district,
            "party": party,
            "details_url": details_path,
        })
    return out

def fetch_leadership(branch: str) -> list[dict]:
    # branch: "House" or "Senate"
    data = api_get(f"/Branches/{branch}/Leadership")
    out = []
    if not data:
        return out
    for row in data:
        # Expected: {"Member": {"Details": ".../LegislativeMembers/{code}" ...}, "Position": "Majority Leader", ...}
        m = row.get("Member", {})
        out.append({
            "member_code": (m.get("Details") or "").split("/")[-1],
            "position": row.get("Position"),
        })
    return out

def fetch_committees(gc_number: int) -> list[dict]:
    data = api_get(f"/GeneralCourts/{gc_number}/Committees")
    return data or []

def fetch_committee_detail(gc_number: int, committee_code: str) -> dict | None:
    return api_get(f"/GeneralCourts/{gc_number}/Committees/{committee_code}")

# =============================================================================
# Computation
# =============================================================================

def stipend_amounts_for_roles(role_keys: list[str]) -> list[tuple[str, int]]:
    table = CYCLE_CONFIG["stipends"]
    pairs = [(rk, int(table.get(rk, 0))) for rk in role_keys]
    pairs.sort(key=lambda x: x[1], reverse=True)
    return pairs[:2]  # top two only — §9B cap

def band_for_member(member_code: str, member_record: dict) -> tuple[str | None, float | None, str | None]:
    # Decide locality: override dict, else None (you can extend this to scrape HTML profile if needed)
    loc = HOME_LOCALITY_OVERRIDES.get(member_code)
    if not loc:
        # Try to infer from district label only as last resort (very rough)
        # You should replace this with real profile scrape for residence city.
        loc = None
    if not loc:
        return None, None, None
    band, miles = distance_band_for_locality(loc)
    return band, miles, loc

def compute_totals(members: list[dict], leadership_roles: list[dict], committee_roles: dict[str, list[str]]) -> list[dict]:
    # leadership map: member_code -> list of role keys
    lead_map: dict[str, list[str]] = {}
    for item in leadership_roles:
        code = item.get("member_code")
        position = (item.get("position") or "").strip()
        role_key = ROLE_MAP.get(position)
        if not code or not role_key:
            continue
        lead_map.setdefault(code, []).append(role_key)

    rows = []
    for m in members:
        code = m["member_code"]
        # collect all roles (leadership + committee)
        roles = []
        roles += lead_map.get(code, [])
        roles += committee_roles.get(code, [])

        top2 = stipend_amounts_for_roles(roles)
        role_total = sum(a for _, a in top2)
        role_1, r1_amt = (top2[0] if len(top2) > 0 else (None, 0))
        role_2, r2_amt = (top2[1] if len(top2) > 1 else (None, 0))

        band, miles, locality = band_for_member(code, m)
        expense = CYCLE_CONFIG["expense_bands"].get(band, 0) if band else 0
        base = int(CYCLE_CONFIG["base_salary"])
        total = base + expense + role_total

        actual = PAYROLL_ACTUAL.get(code)
        variance = (actual - total) if actual is not None else None

        rows.append({
            "member_id": code,  # API MemberCode (stable)
            "name": m["name"],
            "chamber": m["branch"],
            "district": m["district"],
            "party": m["party"],
            "home_locality": locality,             # SAMPLE (None unless overridden)
            "distance_miles": miles,               # SAMPLE
            "distance_band": band,                 # SAMPLE
            "base_salary": base,
            "expense_stipend": expense,
            "role_1": role_1,
            "role_1_stipend": r1_amt,
            "role_2": role_2,
            "role_2_stipend": r2_amt,
            "role_stipends_total": role_total,
            "total_comp": total,
            "has_stipend": role_total > 0,
            "payroll_actual_sample": actual,       # SAMPLE placeholder
            "variance_vs_actual_sample": variance, # SAMPLE placeholder
            "last_updated": date.today().isoformat(),
            "notes": "SAMPLE locality/expense band — set HOME_LOCALITY_OVERRIDES or scrape profile",
        })
    return rows

# =============================================================================
# Console UI
# =============================================================================

def list_members(members):
    print("\nMembers (API):")
    for m in members[:10]:
        print(f"- {m['member_code']:>6} — {m['name']} ({m['branch']}, {m['district']})")
    if len(members) > 10:
        print(f"... and {len(members)-10} more")

def export_csv(rows: list[dict]):
    cols = [
        "member_id","name","chamber","district","party","home_locality",
        "distance_miles","distance_band","base_salary","expense_stipend",
        "role_1","role_1_stipend","role_2","role_2_stipend",
        "role_stipends_total","total_comp","has_stipend",
        "payroll_actual_sample","variance_vs_actual_sample","last_updated","notes"
    ]
    print("\nCSV OUTPUT (copy to file if needed):")
    print(",".join(cols))
    for r in rows:
        vals = []
        for c in cols:
            v = r.get(c, "")
            s = "" if v is None else str(v)
            if any(ch in s for ch in [",", '"', "\n"]):
                s = '"' + s.replace('"', '""') + '"'
            vals.append(s)
        print(",".join(vals))

def main():
    print(dedent("""
    ==========================================
    MA Stipend Demo (API-backed, SAMPLE money)
    ==========================================
    This script uses the official API for:
      - Sessions
      - Members
      - Leadership
      - Committees (to find Chairs/Vice Chairs)

    It uses SAMPLE placeholders for:
      - Dollar amounts (cycle config)
      - Home locality / expense band (override map)
      - "Actual payroll" (CTHRU) validation

    """))

    session = pick_session()
    if not session:
        return
    gc = get_gc_number(session)   # <-- was session["GeneralCourtNumber"]
    print(f"\nSelected General Court: {gc} — {get_gc_name(session)}")

    print("\nFetching members…")
    members = fetch_members(gc)
    if not members:
        print("No members found; exiting.")
        return
    list_members(members)

    # Leadership
    print("\nFetching leadership (House)…")
    lead_house = fetch_leadership("House")
    print(f"  House leadership entries: {len(lead_house)}")
    print("Fetching leadership (Senate)…")
    lead_senate = fetch_leadership("Senate")
    print(f"  Senate leadership entries: {len(lead_senate)}")
    leadership_all = lead_house + lead_senate

    # Committees
    print("\nFetching committees…")
    committees = fetch_committees(gc) or []
    print(f"  Committees returned: {len(committees)}")
    committee_roles: dict[str, list[str]] = {}
    # For brevity, limit deep fetch; remove the slice to fetch all committees
    limit = input("Fetch all committees? (y/N): ").strip().lower() == "y"
    to_fetch = committees if limit else committees[:15]

    for c in to_fetch:
        code = c.get("CommitteeCode")
        name = c.get("Name") or c.get("CommitteeName")
        if not code:
            continue
        detail = fetch_committee_detail(gc, code)
        # The detail model includes Members with Role (e.g., "Chair", "Vice Chair")
        if not detail:
            continue
        members_list = detail.get("Members") or []
        for mem in members_list:
            # Expect mem like {"Member":{"Details": ".../{code}"}, "Role":"Chair"}
            m = mem.get("Member", {})
            member_code = (m.get("Details") or "").split("/")[-1]
            role_label = (mem.get("Role") or "").strip()
            role_key = map_committee_role(name, role_label)
            if member_code and role_key:
                committee_roles.setdefault(member_code, []).append(role_key)
        time.sleep(0.1)  # be polite

    # Compute
    print("\nComputing totals (with SAMPLE money + SAMPLE locality overrides)…")
    rows = compute_totals(members, leadership_all, committee_roles)

    # Show a few
    print("\nPreview (first 8):")
    for r in rows[:8]:
        mid = str(r.get("member_id") or "")
        name = str(r.get("name") or "")
        chamber = str(r.get("chamber") or "")
        band = str(r.get("distance_band") or "")
        role_sum = r.get("role_stipends_total") or 0
        total = r.get("total_comp") or 0
        print(f"{mid:>6} | {name:<28} | {chamber:<6} | band={band:<5} | roleΣ=${role_sum:<6} | total=${total}")

    # Edit locality quick option
    while True:
        ans = input("\nEdit a member's home locality for band calc? (member_id or Enter to skip): ").strip()
        if not ans:
            break
        new_loc = input("Enter locality (e.g., 'Framingham'): ").strip()
        if new_loc:
            HOME_LOCALITY_OVERRIDES[ans] = new_loc
            print("Updated override. Recomputing this member:")
            # recompute just that one
            m = next((x for x in members if x["member_code"] == ans), None)
            if m:
                updated = compute_totals([m], leadership_all, committee_roles)[0]
                print(f"{updated['member_id']:>6} | {updated['name']:<28} | band={updated['distance_band']} | expense=${updated['expense_stipend']} | total=${updated['total_comp']}")
        else:
            print("No change.")

    # Export CSV to stdout
    export = input("\nExport CSV to stdout? (Y/n): ").strip().lower()
    if export in ("y", ""):
        export_csv(rows)
        print("\nDone.")

if __name__ == "__main__":
    main()
