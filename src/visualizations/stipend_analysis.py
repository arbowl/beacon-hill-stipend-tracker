"""Visualizations analyzing leadership/committee stipends among legislators."""

from src.visualizations.base import Visualization, DataContext


class TopStipendEarners(Visualization):
    """Visualization listing members with highest leadership/committee stipends."""

    name = "Top Leadership Stipend Earners"
    description = "Show members with highest leadership/committee stipends"
    category = "Analysis"

    def run(self, context: DataContext) -> None:
        print("\n" + "=" * 80)
        print("TOP LEADERSHIP STIPEND EARNERS")
        print("=" * 80)
        print("(Leadership stipends = committee chairs/vice chairs, ")
        print("Speaker, President, Whips, etc.)")
        print("(Does NOT include travel/expense stipends)")
        print("=" * 80)
        stipend_recipients = [
            row for row in context.computed_rows
            if row.get("role_stipends_total", 0) > 0
        ]
        if not stipend_recipients:
            print("No leadership stipend recipients found.")
            return
        stipend_recipients.sort(
            key=lambda x: x.get("role_stipends_total", 0),
            reverse=True
        )
        total_stipends = sum(
            r["role_stipends_total"] for r in stipend_recipients
        )
        count = len(stipend_recipients)
        print(f"\nTotal members with leadership stipends: {count}")
        total_msg = "Total leadership stipend dollars: "
        total_msg += self.format_currency(total_stipends)
        print(total_msg)
        print("\nTop 15 earners:\n")
        header = (
            f"{'Rank':<6} {'Name':<30} {'Chamber':<8} "
            f"{'Role 1':<20} {'Role 2':<20} {'Leadership $':>15}"
        )
        print(header)
        print("-" * 110)
        for idx, member in enumerate(stipend_recipients[:15], 1):
            name = member.get("name", "Unknown")[:28]
            chamber = member.get("chamber", "N/A")
            role1 = (member.get("role_1") or "")[:18]
            role2 = (member.get("role_2") or "")[:18]
            stipend_total = member.get("role_stipends_total", 0)
            print(
                f"{idx:<6} {name:<30} {chamber:<8} {role1:<20} {role2:<20} "
                f"{self.format_currency(stipend_total):>15}"
            )
        if len(stipend_recipients) >= 10:
            top_10_total = sum(
                r["role_stipends_total"]
                for r in stipend_recipients[:10]
            )
            if total_stipends > 0:
                top_10_pct = top_10_total / total_stipends * 100
            else:
                top_10_pct = 0
            print("\n" + "=" * 80)
            msg = f"Top 10 members control {top_10_pct:.1f}% "
            msg += "of all leadership stipend dollars"
            print(msg)
            print("=" * 80 + "\n")


class StipendDistribution(Visualization):
    """Visualization showing distribution of leadership stipends among members."""

    name = "Leadership Stipend Distribution"
    description = "Breakdown of who has leadership stipends vs. who doesn't"
    category = "Analysis"

    def run(self, context: DataContext) -> None:
        print("\n" + "=" * 80)
        print("LEADERSHIP STIPEND DISTRIBUTION")
        print("=" * 80)
        print("(Committee/leadership positions only - NOT expense stipends)")
        print("=" * 80)
        total_members = len(context.computed_rows)
        with_stipends = [
            r for r in context.computed_rows
            if r.get("role_stipends_total", 0) > 0
        ]
        without_stipends = total_members - len(with_stipends)
        print(f"\nTotal Members: {total_members}")
        pct_with = len(with_stipends) / total_members * 100
        pct_without = without_stipends / total_members * 100
        print(
            f"  With leadership stipends: {len(with_stipends)} "
            f"({pct_with:.1f}%)"
        )
        print(
            f"  Without leadership stipends: {without_stipends} "
            f"({pct_without:.1f}%)"
        )
        house_with = sum(
            1 for r in with_stipends if r.get("chamber") == "House"
        )
        senate_with = sum(
            1 for r in with_stipends if r.get("chamber") == "Senate"
        )
        house_total = sum(
            1 for r in context.computed_rows
            if r.get("chamber") == "House"
        )
        senate_total = sum(
            1 for r in context.computed_rows
            if r.get("chamber") == "Senate"
        )
        print("\nBy Chamber:")
        house_pct = house_with / house_total * 100
        senate_pct = senate_with / senate_total * 100
        print(
            f"  House: {house_with}/{house_total} have leadership stipends "
            f"({house_pct:.1f}%)"
        )
        print(
            f"  Senate: {senate_with}/{senate_total} have leadership stipends "
            f"({senate_pct:.1f}%)"
        )
        if with_stipends:
            total = sum(r["role_stipends_total"] for r in with_stipends)
            avg_stipend = total / len(with_stipends)
            msg = "Average leadership stipend (among recipients): "
            msg += self.format_currency(avg_stipend)
            print(f"\n{msg}")
        print("=" * 80 + "\n")
