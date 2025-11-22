"""
Visualizations analyzing earmarks and their correlation with stipends.
"""

from src.visualizations.base import Visualization, DataContext


class TopEarmarkRecipients(Visualization):
    """Visualization listing members with most earmarks."""

    name = "Top Earmark Recipients"
    description = "Show members with highest earmark totals"
    category = "Earmarks"

    def run(self, context: DataContext) -> None:
        if not context.earmarks_by_member:
            print("\n" + "=" * 80)
            print("TOP EARMARK RECIPIENTS")
            print("=" * 80)
            print("\nNo earmark data available.")
            print(
                "Run pipeline with earmark fetching enabled "
                "to see this report."
            )
            print("=" * 80)
            return

        print("\n" + "=" * 80)
        print("TOP EARMARK RECIPIENTS")
        print("=" * 80)

        # Aggregate earmark statistics
        member_stats = []
        for member_code, earmarks in context.earmarks_by_member.items():
            if member_code == "UNKNOWN":
                continue

            amounts = [
                e.get("amount", 0)
                for e in earmarks
                if e.get("amount") is not None
            ]

            if not amounts:
                continue

            # Get member info
            member_info = next(
                (
                    m for m in context.members
                    if m.get("member_code") == member_code
                ),
                {}
            )

            member_stats.append({
                "member_code": member_code,
                "name": member_info.get("name", "Unknown"),
                "chamber": member_info.get("branch", "Unknown"),
                "district": member_info.get("district", "Unknown"),
                "count": len(earmarks),
                "total": sum(amounts),
                "average": sum(amounts) / len(amounts),
                "max": max(amounts),
            })

        if not member_stats:
            print("\nNo earmark recipients found.")
            return

        # Sort by total dollars
        member_stats.sort(key=lambda x: x["total"], reverse=True)

        total_earmarks = sum(m["count"] for m in member_stats)
        total_dollars = sum(m["total"] for m in member_stats)

        print(f"\nTotal members with earmarks: {len(member_stats)}")
        print(f"Total earmarks (matched): {total_earmarks}")
        total_msg = "Total earmark dollars (matched): "
        total_msg += self.format_currency(total_dollars)
        print(total_msg)
        
        # Report UNKNOWN earmarks separately
        unknown_earmarks = context.earmarks_by_member.get("UNKNOWN", [])
        if unknown_earmarks:
            unknown_amounts = [
                e.get("amount", 0)
                for e in unknown_earmarks
                if e.get("amount") is not None
            ]
            unknown_total = sum(unknown_amounts)
            unknown_msg = (
                f"UNKNOWN sponsors: {len(unknown_earmarks)} earmarks, "
                f"{self.format_currency(unknown_total)}"
            )
            print(unknown_msg)
            grand_msg = "Grand total (matched + unknown): "
            grand_msg += self.format_currency(total_dollars + unknown_total)
            print(grand_msg)

        print("\nTop 20 recipients:\n")
        header = (
            f"{'Rank':<6} {'Name':<30} {'Chamber':<8} "
            f"{'Count':>7} {'Total':>15} {'Average':>15}"
        )
        print(header)
        print("-" * 90)

        for idx, member in enumerate(member_stats[:20], 1):
            name = member["name"][:28]
            chamber = member["chamber"]
            count = member["count"]
            total = self.format_currency(member["total"])
            avg = self.format_currency(member["average"])

            row = (
                f"{idx:<6} {name:<30} {chamber:<8} "
                f"{count:>7} {total:>15} {avg:>15}"
            )
            print(row)

        print("=" * 90)


class EarmarkStipendCorrelation(Visualization):
    """
    Visualization showing correlation between stipends and earmarks.
    """

    name = "Earmark-Stipend Correlation"
    description = "Compare earmark totals with leadership stipends"
    category = "Earmarks"

    def run(self, context: DataContext) -> None:
        if not context.earmarks_by_member:
            print("\n" + "=" * 80)
            print("EARMARK-STIPEND CORRELATION ANALYSIS")
            print("=" * 80)
            print("\nNo earmark data available.")
            print(
                "Run pipeline with earmark fetching enabled "
                "to see this report."
            )
            print("=" * 80)
            return

        print("\n" + "=" * 80)
        print("EARMARK-STIPEND CORRELATION ANALYSIS")
        print("=" * 80)
        msg = (
            "\nAnalyzing relationship between leadership stipends "
            "and earmarks"
        )
        print(msg)
        print("=" * 80)

        # Build combined dataset
        combined = []
        for row in context.computed_rows:
            member_code = row.get("member_id", "")
            if member_code in context.earmarks_by_member:
                earmarks = context.earmarks_by_member[member_code]
                amounts = [
                    e.get("amount", 0)
                    for e in earmarks
                    if e.get("amount") is not None
                ]

                if amounts:
                    combined.append({
                        "name": row.get("name", "Unknown"),
                        "chamber": row.get("chamber", "Unknown"),
                        "district": row.get("district", "Unknown"),
                        "leadership_stipend": row.get(
                            "role_stipends_total", 0
                        ),
                        "earmark_count": len(earmarks),
                        "earmark_total": sum(amounts),
                    })

        if not combined:
            print("\nNo members with both stipends and earmarks found.")
            return

        msg = (
            f"\nMembers with both leadership stipends and earmarks: "
            f"{len(combined)}"
        )
        print(msg)

        # Quartile analysis
        combined_by_stipend = sorted(
            combined,
            key=lambda x: x["leadership_stipend"],
            reverse=True
        )
        combined_by_earmark = sorted(
            combined, key=lambda x: x["earmark_total"], reverse=True
        )

        top_quartile_size = max(1, len(combined) // 4)

        top_stipend_members = {
            m["name"] for m in combined_by_stipend[:top_quartile_size]
        }
        top_earmark_members = {
            m["name"] for m in combined_by_earmark[:top_quartile_size]
        }

        overlap = top_stipend_members & top_earmark_members

        print(f"\nTop quartile size: {top_quartile_size} members")
        msg = (
            f"Members in top quartile for BOTH stipends and earmarks: "
            f"{len(overlap)}"
        )
        print(msg)

        if overlap:
            print("\nMembers high in both categories:")
            for member in combined:
                if member["name"] in overlap:
                    name = member["name"]
                    stipend = self.format_currency(
                        member["leadership_stipend"]
                    )
                    earmarks = member["earmark_count"]
                    total = self.format_currency(member["earmark_total"])
                    print(f"  • {name}")
                    print(f"      Leadership stipend: {stipend}")
                    print(f"      Earmarks: {earmarks} totaling {total}")

        # Show distribution
        print("\n" + "-" * 80)
        print("DISTRIBUTION BY CHAMBER")
        print("-" * 80)

        house = [m for m in combined if "house" in m["chamber"].lower()]
        senate = [m for m in combined if "senate" in m["chamber"].lower()]

        if house:
            house_earmarks = sum(m["earmark_count"] for m in house)
            house_dollars = sum(m["earmark_total"] for m in house)
            print(f"\nHouse: {len(house)} members")
            print(f"  Total earmarks: {house_earmarks}")
            print(f"  Total dollars: {self.format_currency(house_dollars)}")
            avg = house_dollars / len(house)
            print(f"  Average per member: {self.format_currency(avg)}")

        if senate:
            senate_earmarks = sum(m["earmark_count"] for m in senate)
            senate_dollars = sum(m["earmark_total"] for m in senate)
            print(f"\nSenate: {len(senate)} members")
            print(f"  Total earmarks: {senate_earmarks}")
            print(
                f"  Total dollars: {self.format_currency(senate_dollars)}"
            )
            avg = senate_dollars / len(senate)
            print(f"  Average per member: {self.format_currency(avg)}")

        print("=" * 80)


class EarmarksByDistrict(Visualization):
    """Visualization showing earmark distribution by district."""

    name = "Earmarks by District"
    description = "Geographic distribution of earmarks"
    category = "Earmarks"

    def run(self, context: DataContext) -> None:
        if not context.earmarks_by_member:
            print("\n" + "=" * 80)
            print("EARMARKS BY DISTRICT")
            print("=" * 80)
            print("\nNo earmark data available.")
            print(
                "Run pipeline with earmark fetching enabled "
                "to see this report."
            )
            print("=" * 80)
            return

        print("\n" + "=" * 80)
        print("EARMARKS BY DISTRICT")
        print("=" * 80)

        # Build district-level statistics
        district_stats = {}
        for member_code, earmarks in context.earmarks_by_member.items():
            if member_code == "UNMATCHED":
                continue

            member = next(
                (
                    m for m in context.members
                    if m.get("member_code") == member_code
                ),
                {}
            )

            district = member.get("district", "Unknown")
            chamber = member.get("branch", "Unknown")

            amounts = [
                e.get("amount", 0)
                for e in earmarks
                if e.get("amount") is not None
            ]

            if not amounts:
                continue

            if district not in district_stats:
                district_stats[district] = {
                    "district": district,
                    "chamber": chamber,
                    "count": 0,
                    "total": 0.0,
                    "members": []
                }

            district_stats[district]["count"] += len(earmarks)
            district_stats[district]["total"] += sum(amounts)
            district_stats[district]["members"].append(
                member.get("name", "Unknown")
            )

        if not district_stats:
            print("\nNo district data found.")
            return

        # Convert to list and sort
        districts = sorted(
            district_stats.values(),
            key=lambda x: x["total"],
            reverse=True
        )

        print(f"\nTotal districts with earmarks: {len(districts)}")
        print("\nTop 20 districts by total earmark dollars:\n")

        header = (
            f"{'Rank':<6} {'District':<20} {'Chamber':<8} "
            f"{'Count':>7} {'Total':>15}"
        )
        print(header)
        print("-" * 70)

        for idx, dist in enumerate(districts[:20], 1):
            district = dist["district"][:18]
            chamber = dist["chamber"]
            count = dist["count"]
            total = self.format_currency(dist["total"])

            row = (
                f"{idx:<6} {district:<20} {chamber:<8} "
                f"{count:>7} {total:>15}"
            )
            print(row)

        print("=" * 70)
