from statistics import mean, median
from src.visualizations.base import Visualization, DataContext


class StipendTypeComparison(Visualization):
    name = "Expense vs Leadership Stipends"
    description = "Compare travel expense stipends vs leadership stipends"
    category = "Comparison"

    def run(self, context: DataContext) -> None:
        print("\n" + "=" * 80)
        print("EXPENSE STIPENDS vs LEADERSHIP STIPENDS")
        print("=" * 80)
        print("\nTWO TYPES OF STIPENDS:")
        print("  1. EXPENSE STIPENDS = Travel allowance based on distance")
        print("     from State House (≤50mi = $15k, >50mi = $20k)")
        print("  2. LEADERSHIP STIPENDS = Committee chairs, Speaker, etc.")
        print("=" * 80)
        le50_members = [
            r for r in context.computed_rows
            if r.get("distance_band") == "LE50"
        ]
        gt50_members = [
            r for r in context.computed_rows
            if r.get("distance_band") == "GT50"
        ]
        total_expense = sum(
            r.get("expense_stipend", 0)
            for r in context.computed_rows
        )
        leadership_recipients = [
            r for r in context.computed_rows
            if r.get("role_stipends_total", 0) > 0
        ]
        total_leadership = sum(
            r.get("role_stipends_total", 0)
            for r in context.computed_rows
        )
        print("\n" + "-" * 80)
        print("EXPENSE STIPENDS (Travel Allowance)")
        print("-" * 80)
        exp_total = self.format_currency(total_expense)
        print(f"Total expense stipend dollars: {exp_total}")
        print(f"\n  Members ≤50 miles: {len(le50_members)} × $15,000")
        print(f"  Members >50 miles:  {len(gt50_members)} × $20,000")
        total_receiving = len(le50_members) + len(gt50_members)
        print(f"  Total members receiving: {total_receiving}")
        print("\n" + "-" * 80)
        print("LEADERSHIP STIPENDS (Committee/Leadership Positions)")
        print("-" * 80)
        msg = "Total leadership stipend dollars: "
        msg += self.format_currency(total_leadership)
        print(msg)
        count = len(leadership_recipients)
        print(f"  Members with leadership roles: {count}")
        if leadership_recipients:
            avg_lead = mean(
                [r["role_stipends_total"] for r in leadership_recipients]
            )
            med_lead = median(
                [r["role_stipends_total"] for r in leadership_recipients]
            )
            avg_str = self.format_currency(avg_lead)
            med_str = self.format_currency(med_lead)
            print(f"  Average leadership stipend: {avg_str}")
            print(f"  Median leadership stipend: {med_str}")
        print("\n" + "-" * 80)
        print("COMPARISON")
        print("-" * 80)
        total_all_stipends = total_expense + total_leadership
        expense_pct = (
            (total_expense / total_all_stipends * 100)
            if total_all_stipends > 0 else 0
        )
        leadership_pct = (
            (total_leadership / total_all_stipends * 100)
            if total_all_stipends > 0 else 0
        )
        total_str = self.format_currency(total_all_stipends)
        print(f"Total all stipends: {total_str}")
        exp_str = self.format_currency(total_expense)
        lead_str = self.format_currency(total_leadership)
        print(f"\n  Expense stipends:    {exp_str:>15} "
              f"({expense_pct:.1f}%)")
        print(f"  Leadership stipends: {lead_str:>15} "
              f"({leadership_pct:.1f}%)")
        both_types = [
            r for r in context.computed_rows
            if (r.get("role_stipends_total", 0) > 0 and
                r.get("expense_stipend", 0) > 0)
        ]
        print(f"\n  Members receiving BOTH types: {len(both_types)}")
        neither = [
            r for r in context.computed_rows
            if (r.get("role_stipends_total", 0) == 0 and
                r.get("expense_stipend", 0) == 0)
        ]
        print(f"  Members receiving NEITHER: {len(neither)}")
        print("\n" + "=" * 80)
        print("KEY TAKEAWAY:")
        if total_leadership > total_expense:
            ratio = (total_leadership / total_expense
                     if total_expense > 0 else 0)
            print(f"Leadership stipends are {ratio:.1f}x larger than "
                  f"expense stipends")
        else:
            ratio = (total_expense / total_leadership
                     if total_leadership > 0 else 0)
            print(f"Expense stipends are {ratio:.1f}x larger than "
                  f"leadership stipends")
        print("=" * 80 + "\n")
