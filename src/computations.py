from datetime import date
import json
from pathlib import Path
from statistics import median
from typing import Any, Optional

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


def export_leadership_metrics(
    rows: list[dict], path="out/leadership_power.json"
):
    Path("out").mkdir(parents=True, exist_ok=True)
    totals = [r["total_comp"] for r in rows if r.get("total_comp")]
    role_sums = [
        r["role_stipends_total"] for r in rows
        if r.get("role_stipends_total") is not None
    ]
    leadership_recipients = [
        r for r in rows if r.get("role_stipends_total", 0) > 0
    ]
    expense_sums = [
        r["expense_stipend"] for r in rows if r.get("expense_stipend")
    ]
    le50_count = sum(
        1 for r in rows if r.get("distance_band") == "LE50"
    )
    gt50_count = sum(
        1 for r in rows if r.get("distance_band") == "GT50"
    )
    top10 = sorted(totals, reverse=True)[:max(1, len(totals)//10)]
    pct_with_leadership = round(
        100 * len(leadership_recipients) / max(1, len(rows)), 1
    )
    top10_avg = (
        round(sum(top10)/len(top10), 2) if top10 else None
    )
    notes = (
        "Leadership stipends = committee/leadership positions. "
        "Expense stipends = travel allowance based on distance "
        "from State House."
    )
    # Get current expense band amounts from config
    expense_bands = CYCLE_CONFIG.get("expense_bands", {})
    le50_amount = expense_bands.get("LE50", 0)
    gt50_amount = expense_bands.get("GT50", 0)

    metrics = {
        "members": len(rows),
        "members_with_leadership_stipends": len(leadership_recipients),
        "pct_with_leadership_stipends": pct_with_leadership,
        "total_leadership_stipend_dollars": sum(role_sums),
        "total_expense_stipend_dollars": sum(expense_sums),
        "expense_stipend_breakdown": {
            "le50_miles": {"count": le50_count, "amount": le50_amount},
            "gt50_miles": {"count": gt50_count, "amount": gt50_amount}
        },
        "median_total_comp": median(totals) if totals else None,
        "top10_avg_total_comp": top10_avg,
        "generated_at": date.today().isoformat(),
        "notes": notes
    }
    Path(path).write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
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
        district = (member_record.get('district') or '').strip()
        return band, miles, f"{district} (centroid)"
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
        if locality and "(centroid)" not in (locality or ""):
            band_source = "LOCALITY"
        elif locality and "(centroid)" in locality:
            band_source = "DISTRICT_CENTROID"
        else:
            band_source = None
        is_centroid = band_source == "DISTRICT_CENTROID"
        clean_locality = None if is_centroid else locality
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


def aggregate_earmark_totals(
    earmarks_by_member: dict[str, list[dict[str, Any]]]
) -> dict[str, dict[str, Any]]:
    """
    Calculate earmark totals per legislator.
    
    Args:
        earmarks_by_member: Dictionary mapping member codes to earmarks
    
    Returns:
        Dictionary with earmark statistics per member:
        {
            'member_code': {
                'total_earmark_count': int,
                'total_earmark_dollars': float,
                'average_earmark_amount': float,
                'largest_earmark': float,
                'earmarks': [list of full earmark dicts]
            },
            ...
        }
    """
    aggregated = {}
    
    for member_code, earmarks in earmarks_by_member.items():
        if member_code == 'UNKNOWN':
            continue
        
        # Extract amounts
        amounts = [
            e.get('amount', 0)
            for e in earmarks
            if e.get('amount') is not None
        ]
        
        # Calculate statistics
        total_count = len(earmarks)
        total_dollars = sum(amounts) if amounts else 0.0
        avg_amount = total_dollars / len(amounts) if amounts else 0.0
        max_amount = max(amounts) if amounts else 0.0
        
        aggregated[member_code] = {
            'total_earmark_count': total_count,
            'total_earmark_dollars': total_dollars,
            'average_earmark_amount': avg_amount,
            'largest_earmark': max_amount,
            'earmarks': earmarks
        }
    
    return aggregated


def compute_stipend_earmark_correlation(
    rows: list[dict[str, Any]],
    earmarks_by_member: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    """
    Compute correlation metrics between stipends and earmarks.
    
    Args:
        rows: Member compensation rows from compute_totals()
        earmarks_by_member: Earmarks grouped by member code
    
    Returns:
        Aggregate metrics dictionary with:
        - Total members with earmarks
        - Total earmark dollars
        - Average earmarks per member
        - Correlation between stipends and earmarks
        - Top earmark recipients
    """
    # Aggregate earmark data
    earmark_totals = aggregate_earmark_totals(earmarks_by_member)
    
    # Enrich rows with earmark data
    members_with_earmarks = []
    for row in rows:
        member_code = row.get('member_id', '')
        if member_code in earmark_totals:
            earmark_data = earmark_totals[member_code]
            members_with_earmarks.append({
                'member_code': member_code,
                'name': row.get('name'),
                'chamber': row.get('chamber'),
                'district': row.get('district'),
                'party': row.get('party'),
                'role_stipends_total': row.get('role_stipends_total', 0),
                'total_comp': row.get('total_comp', 0),
                'earmark_count': earmark_data['total_earmark_count'],
                'earmark_dollars': earmark_data['total_earmark_dollars'],
                'avg_earmark_amount': earmark_data['average_earmark_amount'],
                'largest_earmark': earmark_data['largest_earmark']
            })
    
    # Calculate aggregate statistics
    total_earmark_dollars = sum(
        m['earmark_dollars'] for m in members_with_earmarks
    )
    total_earmarks = sum(
        m['earmark_count'] for m in members_with_earmarks
    )
    
    # Top 10 by earmark dollars
    top_10_earmarks = sorted(
        members_with_earmarks,
        key=lambda x: x['earmark_dollars'],
        reverse=True
    )[:10]
    
    # Calculate percentage of members with earmarks
    pct_with_earmarks = round(
        100 * len(members_with_earmarks) / max(1, len(rows)),
        1
    )
    
    # Simple correlation: members with high stipends vs high earmarks
    # Count members in both top quartiles
    if members_with_earmarks:
        stipend_threshold = sorted(
            [m['role_stipends_total'] for m in members_with_earmarks],
            reverse=True
        )[len(members_with_earmarks) // 4] if len(
            members_with_earmarks
        ) >= 4 else 0
        
        earmark_threshold = sorted(
            [m['earmark_dollars'] for m in members_with_earmarks],
            reverse=True
        )[len(members_with_earmarks) // 4] if len(
            members_with_earmarks
        ) >= 4 else 0
        
        high_both = sum(
            1 for m in members_with_earmarks
            if (m['role_stipends_total'] >= stipend_threshold and
                m['earmark_dollars'] >= earmark_threshold)
        )
    else:
        high_both = 0
    
    metrics = {
        'total_members': len(rows),
        'members_with_earmarks': len(members_with_earmarks),
        'pct_with_earmarks': pct_with_earmarks,
        'total_earmarks': total_earmarks,
        'total_earmark_dollars': total_earmark_dollars,
        'avg_earmarks_per_member': (
            round(total_earmarks / len(members_with_earmarks), 1)
            if members_with_earmarks else 0
        ),
        'avg_dollars_per_member': (
            round(total_earmark_dollars / len(members_with_earmarks), 2)
            if members_with_earmarks else 0
        ),
        'top_10_earmark_recipients': [
            {
                'name': m['name'],
                'chamber': m['chamber'],
                'district': m['district'],
                'earmark_count': m['earmark_count'],
                'earmark_dollars': m['earmark_dollars'],
                'role_stipends': m['role_stipends_total']
            }
            for m in top_10_earmarks
        ],
        'members_high_in_both': high_both,
        'generated_at': date.today().isoformat(),
        'notes': (
            'Correlation analysis between leadership stipends and '
            'earmark activity. High_in_both counts members in top '
            'quartile for both stipends and earmarks.'
        )
    }
    
    return metrics


def export_earmark_metrics(
    metrics: dict[str, Any],
    path: str = "out/earmark_correlation.json"
) -> None:
    """
    Export earmark correlation metrics to JSON file.
    
    Args:
        metrics: Metrics dictionary from compute_stipend_earmark_correlation
        path: Output file path
    """
    Path("out").mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(metrics, indent=2),
        encoding="utf-8"
    )
    print(f"[ok] Wrote {path}")
