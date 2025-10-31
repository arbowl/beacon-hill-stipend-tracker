"""Visualization comparing compensation metrics between House and Senate members."""

from statistics import mean, median
from src.visualizations.base import Visualization, DataContext


class ChamberComparisonAnalysis(Visualization):
    """Visualization comparing compensation metrics between House and Senate
    members.
    """

    name = "House vs Senate Comparison"
    description = "Compare compensation metrics between chambers"
    category = "Comparison"

    def run(self, context: DataContext) -> None:
        print("\n" + "=" * 80)
        print("HOUSE vs SENATE COMPENSATION COMPARISON")
        print("=" * 80)
        msg = "Total comp = base salary + expense stipend + "
        msg += "leadership stipends"
        print(msg)
        print("=" * 80)
        house_members = [
            r for r in context.computed_rows
            if r.get("chamber") == "House"
        ]
        senate_members = [
            r for r in context.computed_rows
            if r.get("chamber") == "Senate"
        ]
        if not house_members or not senate_members:
            print("Insufficient data for comparison.")
            return
        print(f"\n{'Metric':<40} {'House':>18} {'Senate':>18}")
        print("-" * 80)
        h_cnt = len(house_members)
        s_cnt = len(senate_members)
        print(f"{'Total Members':<40} {h_cnt:>18} {s_cnt:>18}")
        house_with_stipends = sum(
            1 for r in house_members if r.get("role_stipends_total", 0) > 0
        )
        senate_with_stipends = sum(
            1 for r in senate_members if r.get("role_stipends_total", 0) > 0
        )
        print(
            f"{'Members with Leadership Stipends':<40} "
            f"{house_with_stipends:>18} {senate_with_stipends:>18}"
        )
        if house_members:
            house_stipend_pct = house_with_stipends / h_cnt * 100
        else:
            house_stipend_pct = 0
        if senate_members:
            senate_stipend_pct = senate_with_stipends / s_cnt * 100
        else:
            senate_stipend_pct = 0
        h_pct_str = f"{house_stipend_pct:.1f}%"
        s_pct_str = f"{senate_stipend_pct:.1f}%"
        print(
            f"{'% with Leadership Stipends':<40} "
            f"{h_pct_str:>18} {s_pct_str:>18}"
        )
        print()
        house_total_comp = [
            r["total_comp"] for r in house_members if r.get("total_comp")
        ]
        senate_total_comp = [
            r["total_comp"] for r in senate_members if r.get("total_comp")
        ]
        if house_total_comp:
            house_avg = mean(house_total_comp)
            house_med = median(house_total_comp)
            house_max = max(house_total_comp)
        else:
            house_avg = house_med = house_max = 0
        if senate_total_comp:
            senate_avg = mean(senate_total_comp)
            senate_med = median(senate_total_comp)
            senate_max = max(senate_total_comp)
        else:
            senate_avg = senate_med = senate_max = 0
        label = "Average Total Compensation"
        h_avg_str = self.format_currency(house_avg)
        s_avg_str = self.format_currency(senate_avg)
        print(f"{label:<40} {h_avg_str:>18} {s_avg_str:>18}")
        label = "Median Total Compensation"
        h_med_str = self.format_currency(house_med)
        s_med_str = self.format_currency(senate_med)
        print(f"{label:<40} {h_med_str:>18} {s_med_str:>18}")
        label = "Highest Total Compensation"
        h_max_str = self.format_currency(house_max)
        s_max_str = self.format_currency(senate_max)
        print(f"{label:<40} {h_max_str:>18} {s_max_str:>18}")
        print()
        house_stipends = [
            r["role_stipends_total"] for r in house_members
            if r.get("role_stipends_total", 0) > 0
        ]
        senate_stipends = [
            r["role_stipends_total"] for r in senate_members
            if r.get("role_stipends_total", 0) > 0
        ]
        if house_stipends:
            house_avg_stipend = mean(house_stipends)
            house_total_stipends = sum(house_stipends)
        else:
            house_avg_stipend = house_total_stipends = 0
        if senate_stipends:
            senate_avg_stipend = mean(senate_stipends)
            senate_total_stipends = sum(senate_stipends)
        else:
            senate_avg_stipend = senate_total_stipends = 0
        label = "Avg Leadership Stipend (recipients)"
        h_avg_str = self.format_currency(house_avg_stipend)
        s_avg_str = self.format_currency(senate_avg_stipend)
        print(f"{label:<40} {h_avg_str:>18} {s_avg_str:>18}")
        label = "Total Leadership Stipend Dollars"
        h_tot_str = self.format_currency(house_total_stipends)
        s_tot_str = self.format_currency(senate_total_stipends)
        print(f"{label:<40} {h_tot_str:>18} {s_tot_str:>18}")
        print("=" * 80 + "\n")
