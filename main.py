#!/usr/bin/env python3
"""
Console demo that uses the Massachusetts Legislature API for roster, leadership,
and committee chairs/vice-chairs — then calculates stipend totals using SAMPLE
cycle config + SAMPLE geocoding + SAMPLE payroll placeholders.

Replace SAMPLE sections with real data sources as you expand the pipeline.
"""

from __future__ import annotations

from time import sleep
from textwrap import dedent

from src.computations import compute_totals
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
    map_committee_role,
    list_members,
)
from src.models import HOME_LOCALITY_OVERRIDES


def export_csv(rows: list[dict]):
    cols = [
        "member_id","name","chamber","district","party","home_locality",
        "distance_miles","distance_band","band_source","base_salary","expense_stipend",
        "role_1","role_1_stipend","role_2","role_2_stipend",
        "role_stipends_total","total_comp","has_stipend",
        "payroll_actual_sample","variance_vs_actual_sample","last_updated",
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


def main() -> None:
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
    gc = get_gc_number(session)
    print(f"\nSelected General Court: {gc} — {get_gc_name(session)}")
    print("\nFetching members…")
    members = fetch_members(gc)
    if not members:
        print("No members found; exiting.")
        return
    list_members(members)
    print("\nFetching leadership (House)…")
    lead_house = fetch_leadership("House")
    print(f"  House leadership entries: {len(lead_house)}")
    print("Fetching leadership (Senate)…")
    lead_senate = fetch_leadership("Senate")
    print(f"  Senate leadership entries: {len(lead_senate)}")
    leadership_all = lead_house + lead_senate
    print("\nFetching committees…")
    committees = fetch_committees(gc) or []
    print(f"  Committees returned: {len(committees)}")
    committee_roles: dict[str, list[str]] = {}
    limit = input("Fetch all committees? (y/N): ").strip().lower() == "y"
    to_fetch = committees if limit else committees
    for idx, c in enumerate(to_fetch):
        print(f"Fetching committee {c} ({idx + 1}/{len(to_fetch)})...")
        code = c.get("CommitteeCode")
        name = c.get("Name") or c.get("CommitteeName")
        if not code:
            continue
        detail = fetch_committee_detail(gc, code)
        if not detail:
            continue
        members_list = detail.get("Members") or []
        mem: dict[str, str]
        for mem in members_list:
            m = mem.get("Member", {})
            member_code = (m.get("Details") or "").split("/")[-1]
            role_label = (mem.get("Role") or "").strip()
            role_key = map_committee_role(name, role_label)
            if member_code and role_key:
                committee_roles.setdefault(member_code, []).append(role_key)
        sleep(0.1)
    print("\nComputing totals (with SAMPLE money + SAMPLE locality overrides)…")
    rows = compute_totals(members, leadership_all, committee_roles)
    print("\nPreview (first 8):")
    for r in rows[:8]:
        mid = str(r.get("member_id") or "")
        name = str(r.get("name") or "")
        chamber = str(r.get("chamber") or "")
        band = str(r.get("distance_band") or "")
        role_sum = r.get("role_stipends_total") or 0
        total = r.get("total_comp") or 0
        print(
            f"{mid:>6} | {name:<28} | {chamber:<6} | band={band:<5} | "
            f"roleΣ=${role_sum:<6} | total=${total}"
        )
    while True:
        ans = input(
            "\nEdit a member's home locality for band calc? (member_id "
            "or Enter to skip): "
        ).strip()
        if not ans:
            break
        new_loc = input("Enter locality (e.g., 'Framingham'): ").strip()
        if new_loc:
            HOME_LOCALITY_OVERRIDES[ans] = new_loc
            print("Updated override. Recomputing this member:")
            m = next((x for x in members if x["member_code"] == ans), None)
            if m:
                updated = compute_totals([m], leadership_all, committee_roles)[0]
                print(
                    f"{updated['member_id']:>6} | {updated['name']:<28} | "
                    f"band={updated['distance_band']} | expense=${updated['expense_stipend']} "
                    f"| total=${updated['total_comp']}"
                )
        else:
            print("No change.")
    export = input("\nExport CSV to stdout? (Y/n): ").strip().lower()
    if export in ("y", ""):
        export_csv(rows)
        print("\nDone.")


if __name__ == "__main__":
    main()
