from datetime import date
import json
from pathlib import Path
from statistics import median
from typing import Optional

from src.centroids import centroid_for
from src.helpers import haversine_miles, distance_band_for_locality
from src.models import (
    CYCLE_CONFIG,
    STATE_HOUSE_LATLON,
    ROLE_MAP,
    HOME_LOCALITY_OVERRIDES,
    PAYROLL_ACTUAL,
)


def stipend_amounts_for_roles(role_keys: list[str]) -> list[tuple[str, int]]:
    table = CYCLE_CONFIG["stipends"]
    pairs = [(rk, int(table.get(rk, 0))) for rk in role_keys]
    pairs.sort(key=lambda x: x[1], reverse=True)
    return pairs[:2]


def export_leadership_metrics(rows: list[dict], path="out/leadership_power.json"):
    Path("out").mkdir(parents=True, exist_ok=True)
    totals = [r["total_comp"] for r in rows if r.get("total_comp")]
    role_sums = [r["role_stipends_total"] for r in rows if r.get("role_stipends_total") is not None]
    stipend_recipients = [r for r in rows if r.get("role_stipends_total", 0) > 0]
    top10 = sorted(totals, reverse=True)[:max(1, len(totals)//10)]
    metrics = {
        "members": len(rows),
        "members_with_stipends": len(stipend_recipients),
        "pct_with_stipends": round(100 * len(stipend_recipients) / max(1, len(rows)), 1),
        "total_stipend_dollars": sum(role_sums),
        "median_total_comp": median(totals) if totals else None,
        "top10_avg_total_comp": round(sum(top10)/len(top10), 2) if top10 else None,
        "generated_at": date.today().isoformat(),
        "notes": "Quick aggregate; full Gini optional."
    }
    Path(path).write_text(json.dumps(metrics, indent=2))
    print(f"[ok] Wrote {path}")


def band_for_member(
    member_code: str, member_record: dict
) -> tuple[Optional[str], Optional[float], Optional[str]]:
    loc = HOME_LOCALITY_OVERRIDES.get(member_code)
    if loc:
        band, miles = distance_band_for_locality(loc)
        return band, miles, loc
    loc = (member_record.get("home_locality") or None)
    if loc:
        band, miles = distance_band_for_locality(loc)
        return band, miles, loc
    ll = centroid_for(member_record)
    if ll:
        miles = round(haversine_miles(ll, STATE_HOUSE_LATLON), 1)
        band = "LE50" if miles <= 50.0 else "GT50"
        return band, miles, f"{(member_record.get('district') or '').strip()} (centroid)"
    return None, None, None


def compute_totals(
    members: list[dict],
    leadership_roles: list[dict],
    committee_roles: dict[str, list[str]]
) -> list[dict]:
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
        roles = []
        roles += lead_map.get(code, [])
        roles += committee_roles.get(code, [])
        top2 = stipend_amounts_for_roles(roles)
        role_total = sum(a for _, a in top2)
        role_1, r1_amt = (top2[0] if len(top2) > 0 else (None, 0))
        role_2, r2_amt = (top2[1] if len(top2) > 1 else (None, 0))
        band, miles, locality = band_for_member(code, m)
        band_source = ("LOCALITY" if locality and "(centroid)" not in (locality or "")
                    else "DISTRICT_CENTROID" if locality and "(centroid)" in locality
                    else None)
        clean_locality = None if band_source == "DISTRICT_CENTROID" else locality
        expense = CYCLE_CONFIG["expense_bands"].get(band, 0) if band else 0
        base = int(CYCLE_CONFIG["base_salary"])
        total = base + expense + role_total
        actual = PAYROLL_ACTUAL.get(code)
        variance = (actual - total) if actual is not None else None
        rows.append({
            "member_id": code,
            "name": m["name"],
            "chamber": m["branch"],
            "district": m["district"],
            "party": m["party"],
            "home_locality": clean_locality,
            "distance_miles": miles,
            "distance_band": band,
            "band_source": band_source,
            "base_salary": base,
            "expense_stipend": expense,
            "role_1": role_1,
            "role_1_stipend": r1_amt,
            "role_2": role_2,
            "role_2_stipend": r2_amt,
            "role_stipends_total": role_total,
            "total_comp": total,
            "has_stipend": role_total > 0,
            "payroll_actual_sample": actual,
            "variance_vs_actual_sample": variance,
            "last_updated": date.today().isoformat(),
        })
    return rows
