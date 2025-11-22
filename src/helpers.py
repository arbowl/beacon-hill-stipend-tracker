import csv
import json
from math import radians, sin, cos, sqrt, atan2
from pathlib import Path
import re
from sys import stderr
import time
from typing import Optional
import urllib.error
import urllib.request

from src.models import (
    API_BASE,
    GEOCODE_CACHE,
    STATE_HOUSE_LATLON,
    TIER_OVERRIDES,
    VICECHAIR_TIER_A_COMMITTEES
)
from src.visualizations import (
    DataContext,
    discover_visualizations,
    get_visualizations_by_category,
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


def export_csv(
    rows: list[dict], output_path: str = "out/members.csv"
):
    """Export member compensation data to CSV file."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "member_id", "name", "chamber", "district", "party",
        "home_locality", "distance_miles", "distance_band",
        "band_source", "base_salary", "expense_stipend",
        "role_1", "role_1_stipend", "role_2", "role_2_stipend",
        "role_stipends_total", "total_comp", "has_stipend",
        "payroll_actual_sample", "variance_vs_actual_sample",
        "last_updated",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=cols, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n[ok] Exported {len(rows)} members to {output_path}")
    print("\nPreview (first 10 rows):")
    for r in rows[:10]:
        mid = str(r.get("member_id") or "")
        name = str(r.get("name") or "")
        chamber = str(r.get("chamber") or "")
        band = str(r.get("distance_band") or "")
        role_sum = r.get("role_stipends_total") or 0
        total = r.get("total_comp") or 0
        print(
            f"{mid:>6} | {name:<28} | {chamber:<6} | "
            f"band={band:<5} | roleΣ=${role_sum:<7,} | "
            f"total=${total:,}"
        )


def export_earmarks_csv(
    earmarks: list[dict],
    output_path: str = "out/earmarks.csv"
) -> None:
    """
    Export earmarks to CSV file.
    
    Args:
        earmarks: List of earmark dictionaries
        output_path: Output file path
    """
    if not earmarks:
        print(f"[skip] No earmarks to export to {output_path}")
        return
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    cols = [
        "amendment_number", "fy_year", "chamber", "amount", "line_item",
        "description", "page_number", "sponsor_name", "matched_member",
        "member_code", "confidence", "is_earmark",
        "classification_confidence", "geographic_specific",
        "organization_specific", "project_specific"
    ]
    
    # Flatten earmark data for CSV export
    flattened = []
    for earmark in earmarks:
        row = {
            "amendment_number": earmark.get("amendment_number"),
            "fy_year": earmark.get("fy_year"),
            "chamber": earmark.get("chamber"),
            "amount": earmark.get("amount"),
            "line_item": earmark.get("line_item"),
            "description": earmark.get("description", "")[:200],
            "page_number": earmark.get("page_number"),
        }
        
        # Add mapping metadata if available
        mapping = earmark.get("mapping_metadata", {})
        row["sponsor_name"] = mapping.get("sponsor_name")
        row["matched_member"] = mapping.get("matched_member")
        row["member_code"] = mapping.get("member_code")
        row["confidence"] = mapping.get("confidence")
        
        # Add classification metadata if available
        classification = earmark.get("classification", {})
        row["is_earmark"] = classification.get("is_earmark")
        row["classification_confidence"] = classification.get("confidence")
        row["geographic_specific"] = classification.get("geographic_specific")
        row["organization_specific"] = classification.get(
            "organization_specific"
        )
        row["project_specific"] = classification.get("project_specific")
        
        flattened.append(row)
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=cols, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(flattened)
    
    print(f"[ok] Exported {len(earmarks)} earmarks to {output_path}")


def export_member_earmarks_csv(
    earmarks_by_member: dict[str, list[dict]],
    output_path: str = "out/member_earmarks.csv"
) -> None:
    """
    Export per-member earmark totals to CSV file.
    
    Args:
        earmarks_by_member: Dictionary mapping member codes to earmarks
        output_path: Output file path
    """
    if not earmarks_by_member:
        print(f"[skip] No member earmarks to export to {output_path}")
        return
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    cols = [
        "member_code", "member_name", "chamber", "earmark_count",
        "total_earmark_dollars", "average_earmark_amount",
        "largest_earmark", "smallest_earmark"
    ]
    
    # Aggregate per-member statistics
    rows = []
    for member_code, earmarks in earmarks_by_member.items():
        if member_code == "UNMATCHED":
            continue
        
        amounts = [
            e.get("amount", 0)
            for e in earmarks
            if e.get("amount") is not None
        ]
        
        # Get member info from first earmark's mapping metadata
        member_name = "Unknown"
        chamber = "Unknown"
        if earmarks and "mapping_metadata" in earmarks[0]:
            metadata = earmarks[0]["mapping_metadata"]
            member_name = metadata.get("matched_member", "Unknown")
            chamber = metadata.get("chamber", "Unknown")
        
        row = {
            "member_code": member_code,
            "member_name": member_name,
            "chamber": chamber,
            "earmark_count": len(earmarks),
            "total_earmark_dollars": sum(amounts) if amounts else 0,
            "average_earmark_amount": (
                sum(amounts) / len(amounts) if amounts else 0
            ),
            "largest_earmark": max(amounts) if amounts else 0,
            "smallest_earmark": min(amounts) if amounts else 0,
        }
        rows.append(row)
    
    # Sort by total dollars descending
    rows.sort(
        key=lambda x: float(x["total_earmark_dollars"]),  # type: ignore
        reverse=True
    )
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=cols, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"[ok] Exported {len(rows)} member summaries to {output_path}")
    
    # Print preview
    print("\nTop 10 earmark recipients:")
    for i, r in enumerate(rows[:10], 1):
        name = r["member_name"]
        count = r["earmark_count"]
        total = r["total_earmark_dollars"]
        print(f"  {i:2d}. {name:<30} {count:3d} earmarks  ${total:>12,.2f}")


def show_visualization_menu(context: DataContext) -> None:
    """Display interactive menu for running visualizations."""
    
    visualizations = discover_visualizations()
    by_category = get_visualizations_by_category()
    
    if not visualizations:
        print("\nNo visualizations available.")
        return
    
    while True:
        print("\n" + "=" * 80)
        print("VISUALIZATION MENU")
        print("=" * 80)
        print("\nAvailable analyses:\n")
        
        # Build a numbered list of all visualizations, grouped by category
        viz_list = []
        for category in sorted(by_category.keys()):
            print(f"  {category}:")
            for viz_class in by_category[category]:
                viz_list.append(viz_class)
                num = len(viz_list)
                print(f"    [{num}] {viz_class.name}")
                print(f"        {viz_class.description}")
            print()
        
        print("  [A] Run all visualizations")
        print("  [Q] Quit to exit\n")

        prompt = "Select a visualization (number, 'A', or 'Q'): "
        choice = input(prompt).strip().upper()
        
        if choice == 'Q':
            print("\nExiting visualization menu.")
            break
        elif choice == 'A':
            print("\nRunning all visualizations...\n")
            for viz_class in viz_list:
                try:
                    viz = viz_class()
                    viz.run(context)
                except Exception as exc:
                    print(f"Error running {viz_class.name}: {exc}\n")
            input("\nPress Enter to return to menu...")
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(viz_list):
                    viz_class = viz_list[idx]
                    try:
                        viz = viz_class()
                        viz.run(context)
                    except Exception as exc:
                        print(f"Error running {viz_class.name}: {exc}\n")
                    input("\nPress Enter to return to menu...")
                else:
                    print("Invalid selection. Please try again.")
            except ValueError:
                print("Invalid input. Please enter a number, 'A', or 'Q'.")

