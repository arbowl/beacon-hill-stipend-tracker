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

from src.computations import (
    compute_totals,
    export_leadership_metrics,
    compute_stipend_earmark_correlation,
    export_earmark_metrics
)
from src.earmarks.fetchers import (
    find_amendment_documents,
    download_documents,
    parse_sponsor_index
)
from src.earmarks.audit import (
    export_audit_report,
    print_audit_summary
)
from src.earmarks.parser import parse_amendment_book
from src.earmarks.classifier import classify_earmarks
from src.earmarks.mapper import map_earmarks_to_members
from src.earmarks.validation import (
    validate_assignments_against_audit,
    export_validation_report
)
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
from src.validate import run_cthru_validation
from src.visualizations import DataContext


def select_session() -> int:
    """Prompt user to select General Court session."""
    session = pick_session()
    if not session:
        return 1
    gc = get_gc_number(session)
    gc_name = get_gc_name(session)
    print(f"\n[1/5] Selected General Court: {gc} — {gc_name}")
    return gc


def fetch_members_helper(gc: int) -> list[dict]:
    """Fetch members for the selected General Court."""
    print("\n[2/5] Fetching members…")
    members = fetch_members(gc)
    if not members:
        print("No members found; exiting.")
        return []
    list_members(members)
    return members


def fetch_leadership_helper() -> list[dict]:
    """Fetch leadership roles for both chambers."""
    print("\n[3/5] Fetching leadership roles…")
    print("  → House leadership…")
    lead_house = fetch_leadership("House")
    print(f"    {len(lead_house)} entries")
    print("  → Senate leadership…")
    lead_senate = fetch_leadership("Senate")
    print(f"    {len(lead_senate)} entries")
    leadership_all = lead_house + lead_senate
    return leadership_all


def fetch_committees_helper(gc: int) -> list[dict]:
    """Fetch committees for the selected General Court."""
    print("\n[4/5] Fetching committees…")
    committees = fetch_committees(gc) or []
    print(f"  Found {len(committees)} committees")
    return committees


def fetch_all_or_limit(committees: list[dict]) -> list[dict]:
    """Prompt user to fetch all committees or limit the number."""
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
    return committees


def fetch_committee_roles(
    committees: list[dict], gc: int
) -> dict[str, list[str]]:
    """Fetch committee roles (chairs, vice chairs) for members."""
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
        name = (
            detail.get("FullName")
            or detail.get("Name")
            or detail.get("CommitteeName")
            or code
        )
        print(f"      → {name}")
        house_chair = detail.get("HouseChairperson")
        senate_chair = detail.get("SenateChairperson")
        chair: dict[str, str]
        for chair in [house_chair, senate_chair]:
            if not chair:
                continue
            member_code = chair.get("MemberCode")
            if not member_code:
                continue
            role_key = map_committee_role(name, "Chair")
            if not role_key:
                continue
            committee_roles.setdefault(
                member_code, []
            ).append(role_key)
            print(
                f"          Chair: {member_code} "
                f"({role_key})"
            )
        vice_chairs_info = detail.get("vice_chairs", {})
        house_vice = vice_chairs_info.get("house_vice_chair_code")
        senate_vice = vice_chairs_info.get("senate_vice_chair_code")
        for member_code, chamber in [
            (house_vice, "House"),
            (senate_vice, "Senate")
        ]:
            if not member_code:
                continue
            role_key = map_committee_role(name, "Vice Chair")
            if not role_key:
                continue
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
    return committee_roles


def compute_rows(
    members: list[dict],
    leadership_all: list[dict],
    committee_roles: dict[str, list[str]]
) -> list[dict]:
    """Compute compensation totals for all members."""
    print("\n[5/5] Computing compensation totals…")
    rows = compute_totals(members, leadership_all, committee_roles)
    return rows


def fetch_earmarks_helper(
    fy_year: int,
    members: list[dict]
) -> dict[str, list[dict]]:
    """
    Fetch and process earmarks for fiscal year.

    Args:
        fy_year: Fiscal year (e.g., 2026)
        gc: General Court number
        members: List of member dictionaries

    Returns:
        Dictionary mapping member codes to their earmarks
    """
    print(f"\n[Earmarks] Fetching earmark data for FY{fy_year}...")
    try:
        # Step 1: Discover documents
        print("  [1/6] Discovering amendment documents...")
        documents = find_amendment_documents(fy_year)
        # Step 2: Download PDFs (cached)
        print("  [2/6] Downloading PDF documents...")
        pdfs = download_documents(documents, fy_year)
        if not pdfs:
            print("  [Earmarks] No PDFs available, skipping...")
            return {}
        # Step 3: Parse amendment books (cached)
        print("  [3/6] Parsing amendment books...")
        house_amendments = []
        senate_amendments = []
        if 'house_amendment_book' in pdfs:
            house_amendments = parse_amendment_book(
                pdfs['house_amendment_book'],
                fy_year,
                'House'
            )
        if 'senate_amendment_book' in pdfs:
            senate_amendments = parse_amendment_book(
                pdfs['senate_amendment_book'],
                fy_year,
                'Senate'
            )
        all_amendments = house_amendments + senate_amendments
        print(f"    Found {len(all_amendments)} total amendments")
        if not all_amendments:
            print("  [Earmarks] No amendments found, skipping...")
            return {}
        # Step 4: Parse sponsor indexes
        print("  [4/6] Parsing sponsor indexes...")
        sponsor_index: dict[str, list[str]] = {}
        if 'house_sponsor_index' in pdfs:
            house_sponsors = parse_sponsor_index(
                pdfs['house_sponsor_index'],
                fy_year,
                'House'
            )
            sponsor_index.update(house_sponsors)
        if 'senate_sponsor_index' in pdfs:
            senate_sponsors = parse_sponsor_index(
                pdfs['senate_sponsor_index'],
                fy_year,
                'Senate'
            )
            sponsor_index.update(senate_sponsors)
        print(f"    Found {len(sponsor_index)} sponsor mappings")
        # Step 5: Classify earmarks
        print("  [5/6] Classifying earmarks...")
        earmarks = classify_earmarks(all_amendments)
        print(f"    Identified {len(earmarks)} earmarks")
        if not earmarks:
            print("  [Earmarks] No earmarks identified, skipping...")
            return {}
        # Step 6: Map to members
        print("  [6/6] Mapping earmarks to legislators...")
        earmarks_by_member = map_earmarks_to_members(
            earmarks,
            members,
            sponsor_index
        )
        print("\n[Earmarks] Successfully processed earmark data")
        return earmarks_by_member
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"\n[Earmarks] Error processing earmarks: {e}")
        print("[Earmarks] Continuing without earmark data...")
        return {}


def export_outputs(
    rows: list[dict],
    earmarks_by_member: dict[str, list[dict]] | None = None,
    members: list[dict] | None = None
) -> None:
    """Export outputs: members.csv, leadership metrics, and earmarks."""
    print("\n" + "=" * 60)
    export_csv(rows)
    export_leadership_metrics(rows)
    # Export earmark correlation if available
    if earmarks_by_member:
        print("\n[Earmarks] Computing earmark correlation metrics...")
        try:
            metrics = compute_stipend_earmark_correlation(
                rows,
                earmarks_by_member
            )
            export_earmark_metrics(metrics)
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"[Earmarks] Error exporting metrics: {e}")
        # Export audit report
        if members:
            print("\n[Earmarks] Generating audit reports...")
            _csv_path, _html_path = export_audit_report(
                earmarks_by_member,
                members
            )
            print_audit_summary(earmarks_by_member)
            # Validate against human audit decisions if available
            validation_results = validate_assignments_against_audit(
                earmarks_by_member
            )
            stats = validation_results['validation_stats']
            if stats.get('audit_file_available'):
                export_validation_report(validation_results)


def run_cthru_validation_helper() -> None:
    """Run CTHRU validation and print summary."""
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
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"\n[CTHRU] Validation failed: {e}")
        print("Continuing without CTHRU validation...")


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
    gc = select_session()
    members = fetch_members_helper(gc)
    leadership_all = fetch_leadership_helper()
    committees = fetch_committees_helper(gc)
    committees = fetch_all_or_limit(committees)
    committee_roles = fetch_committee_roles(committees, gc)
    rows = compute_rows(
        members,
        leadership_all,
        committee_roles
    )
    # Optional: Fetch earmark data
    earmarks_by_member = {}
    try:
        # Prompt user for fiscal year
        fy_input = input(
            "\nFetch earmark data? Enter FY year (e.g., 2026) or press "
            "Enter to skip: "
        ).strip()
        if fy_input:
            fy_year = int(fy_input)
            earmarks_by_member = fetch_earmarks_helper(fy_year, members)
    except ValueError:
        print("[Earmarks] Invalid year, skipping earmark data...")
    except KeyboardInterrupt:
        print("\n[Earmarks] Skipped by user")
    export_outputs(rows, earmarks_by_member, members)
    run_cthru_validation_helper()
    print("\n" + "=" * 60)
    print("✓ Pipeline complete!")
    print("\nOutputs:")
    print("  - out/members.csv (per-member compensation)")
    print("  - out/leadership_power.json (aggregate metrics)")
    if earmarks_by_member:
        print("  - out/earmark_correlation.json (earmark analysis)")
        print("  - out/earmark_audit_report.csv (earmark audit - spreadsheet)")
        print(
            "  - out/earmark_audit_report.html (earmark audit - interactive)"
        )
    print("  - out/cthru_variances.csv (CTHRU validation details)")
    print("  - out/cthru_summary.json (CTHRU validation summary)")
    print("=" * 60)
    print("\n" + "=" * 60)
    print("Data fetching complete! You can now run visualizations.")
    print("=" * 60)
    context = DataContext(
        members=members,
        leadership_roles=leadership_all,
        committee_roles=committee_roles,
        computed_rows=rows,
        earmarks_by_member=earmarks_by_member if earmarks_by_member else None,
    )
    show_visualization_menu(context)


if __name__ == "__main__":
    main()
