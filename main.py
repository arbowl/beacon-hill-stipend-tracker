#!/usr/bin/env python3
"""
Massachusetts Legislative Stipend Tracker

A data pipeline that fetches legislative data from the MA Legislature API,
computes district centroids from MassGIS shapefiles, and calculates total
compensation (base salary + expense stipend + leadership/committee stipends)
for each member of the General Court.

Data sources:
- MA Legislature API (malegislature.gov/api)
- MassGIS shapefiles (Senate/House district boundaries)
- Statutory pay rules (M.G.L. c.3 §§9B-9C)

Outputs:
- out/members.csv - Per-member compensation breakdown
- out/leadership_power.json - Aggregate metrics
"""

from __future__ import annotations

from time import sleep
from textwrap import dedent

from src.computations import compute_totals, export_leadership_metrics
from src.validate import run_cthru_validation
from src.fetchers import (
    pick_session,
    get_gc_number,
    get_gc_name,
    fetch_members,
    fetch_leadership,
    fetch_committees,
    fetch_committee_detail,
)
from src.helpers import (
    list_members,
    map_committee_role,
    show_visualization_menu,
    export_csv
)
from src.models import CYCLE_CONFIG
from src.visualizations import DataContext


def main() -> None:
    """Main pipeline orchestration."""
    cycle = CYCLE_CONFIG.get('cycle', 'N/A')
    base = CYCLE_CONFIG.get('base_salary', 0)
    le50 = CYCLE_CONFIG['expense_bands']['LE50']
    gt50 = CYCLE_CONFIG['expense_bands']['GT50']

    print(dedent(f"""
    ========================================================
    Massachusetts Legislative Stipend Tracker
    ========================================================
    Cycle: {cycle}
    Base Salary: ${base:,}
    Expense Bands: LE50=${le50:,}, GT50=${gt50:,}

    Data Sources:
      ✓ MA Legislature API (members, leadership, committees)
      ✓ MassGIS Shapefiles (district centroids)
      ✓ M.G.L. c.3 §§9B-9C (statutory pay rules)

    Output:
      → out/members.csv
      → out/leadership_power.json
    ========================================================
    """))

    # 1. Select session
    session = pick_session()
    if not session:
        return
    gc = get_gc_number(session)
    gc_name = get_gc_name(session)
    print(f"\n[1/5] Selected General Court: {gc} — {gc_name}")

    # 2. Fetch members
    print("\n[2/5] Fetching members…")
    members = fetch_members(gc)
    if not members:
        print("No members found; exiting.")
        return
    list_members(members)

    # 3. Fetch leadership
    print("\n[3/5] Fetching leadership roles…")
    print("  → House leadership…")
    lead_house = fetch_leadership("House")
    print(f"    {len(lead_house)} entries")
    print("  → Senate leadership…")
    lead_senate = fetch_leadership("Senate")
    print(f"    {len(lead_senate)} entries")
    leadership_all = lead_house + lead_senate

    # 4. Fetch committees
    print("\n[4/5] Fetching committees…")
    committees = fetch_committees(gc) or []
    print(f"  Found {len(committees)} committees")

    # Ask if user wants to fetch all or limit (for testing)
    limit_input = input(
        "Fetch ALL committees? (Y/n): "
    ).strip().lower()
    fetch_all = limit_input in ("y", "")

    if not fetch_all:
        limit = input(
            "Enter number to fetch (default 15): "
        ).strip()
        try:
            limit_num = int(limit) if limit else 15
            committees = committees[:limit_num]
            print(
                f"  Limited to first {len(committees)} committees"
            )
        except ValueError:
            committees = committees[:15]
            print("  Invalid input, limited to first 15 committees")

    committee_roles: dict[str, list[str]] = {}
    for idx, c in enumerate(committees):
        code = c.get("CommitteeCode")
        if not code:
            continue
        print(
            f"  [{idx + 1}/{len(committees)}] Fetching {code}..."
        )
        detail = fetch_committee_detail(gc, code)
        if not detail:
            continue

        # Get committee name from detail response
        name = (
            detail.get("FullName")
            or detail.get("Name")
            or detail.get("CommitteeName")
            or code
        )

        print(f"      → {name}")

        # Extract chairs from API structure
        # API structure: HouseChairperson and SenateChairperson objects
        house_chair = detail.get("HouseChairperson")
        senate_chair = detail.get("SenateChairperson")

        for chair in [house_chair, senate_chair]:
            if chair:
                member_code = chair.get("MemberCode")
                if member_code:
                    role_key = map_committee_role(name, "Chair")
                    if role_key:
                        committee_roles.setdefault(
                            member_code, []
                        ).append(role_key)
                        print(
                            f"          Chair: {member_code} "
                            f"({role_key})"
                        )

        # Extract vice chairs from scraped data
        vice_chairs_info = detail.get("vice_chairs", {})
        house_vice = vice_chairs_info.get("house_vice_chair_code")
        senate_vice = vice_chairs_info.get("senate_vice_chair_code")

        for member_code, chamber in [
            (house_vice, "House"), (senate_vice, "Senate")
        ]:
            if member_code:
                role_key = map_committee_role(name, "Vice Chair")
                if role_key:
                    committee_roles.setdefault(
                        member_code, []
                    ).append(role_key)
                    print(
                        f"          Vice Chair ({chamber}): "
                        f"{member_code} ({role_key})"
                    )

        sleep(0.15)  # Polite delay between API calls

    print(
        f"\n  Collected roles for {len(committee_roles)} "
        f"members from committees"
    )

    # 5. Compute totals
    print("\n[5/5] Computing compensation totals…")
    rows = compute_totals(members, leadership_all, committee_roles)
    
    # 6. Export outputs
    print("\n" + "=" * 60)
    export_csv(rows)
    export_leadership_metrics(rows)

    # 7. Run CTHRU validation
    try:
        resp = run_cthru_validation(
            cthru_csv_url=(
                "https://cthru.data.socrata.com/resource/"
                "9ttk-7vz6.csv"
            ),
            members_csv_path="out/members.csv",
            year=None  # infer from last_updated
        )
        print(
            f"\n[CTHRU] {resp['rows_matched']}/"
            f"{resp['rows_model']} matched; "
            f"status: {resp['status_counts']}"
        )
    except Exception as e:
        print(f"\n[CTHRU] Validation failed: {e}")
        print("Continuing without CTHRU validation...")

    print("\n" + "=" * 60)
    print("✓ Pipeline complete!")
    print("\nOutputs:")
    print("  - out/members.csv (per-member compensation)")
    print("  - out/leadership_power.json (aggregate metrics)")
    print("  - out/cthru_variances.csv (CTHRU validation details)")
    print("  - out/cthru_summary.json (CTHRU validation summary)")
    print("=" * 60)
    
    # 8. Interactive visualization menu
    print("\n" + "=" * 60)
    print("Data fetching complete! You can now run visualizations.")
    print("=" * 60)
    
    # Create data context for visualizations
    context = DataContext(
        members=members,
        leadership_roles=leadership_all,
        committee_roles=committee_roles,
        computed_rows=rows,
    )
    
    # Show visualization menu
    show_visualization_menu(context)


if __name__ == "__main__":
    main()
