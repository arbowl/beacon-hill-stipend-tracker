"""
Variance Analysis Tool

Analyzes CTHRU validation variances to identify patterns and reduce false positives.
This script helps determine:
1. Are variances due to annualization (partial year vs full year)?
2. Do leadership roles show systematic variance patterns?
3. What are the real outliers that need investigation?
"""

import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np


def load_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load variance and members data."""
    df_variance = pd.read_csv("out/cthru_variances.csv")
    df_members = pd.read_csv("out/members.csv")
    
    # Merge to get additional context
    df = df_variance.merge(
        df_members[["member_id", "party", "has_stipend", "role_1", "role_2"]],
        on="member_id",
        how="left"
    )
    
    return df, df_members


def calculate_cthru_percentage(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate CTHRU as percentage of model compensation."""
    df = df.copy()
    df["cthru_pct_of_model"] = (df["cthru_total"] / df["total_comp"]) * 100
    df["months_equivalent"] = (df["cthru_total"] / df["total_comp"]) * 12
    df["abs_variance"] = df["variance"].abs()
    return df


def analyze_annualization_hypothesis(df: pd.DataFrame) -> Dict:
    """
    Test hypothesis: Are most INVESTIGATE cases due to annualization?
    
    CTHRU data through Oct 18, 2025 = ~10.5 months
    Expected ratio: 10.5/12 = 87.5%
    """
    investigate = df[df["status"] == "INVESTIGATE"].copy()
    
    # Count cases where CTHRU is 75-90% of model (likely partial year)
    partial_year_mask = (investigate["cthru_pct_of_model"] >= 75) & \
                        (investigate["cthru_pct_of_model"] <= 90)
    partial_year_count = partial_year_mask.sum()
    
    # Count cases where CTHRU > model (negative variance)
    negative_variance = (investigate["variance"] < 0).sum()
    
    analysis = {
        "total_investigate": len(investigate),
        "likely_partial_year": int(partial_year_count),
        "likely_partial_year_pct": float(partial_year_count / len(investigate) * 100),
        "negative_variance_count": int(negative_variance),
        "median_cthru_pct": float(investigate["cthru_pct_of_model"].median()),
        "mean_cthru_pct": float(investigate["cthru_pct_of_model"].mean()),
        "median_months_equiv": float(investigate["months_equivalent"].median()),
        "percentiles": {
            "p25": float(investigate["cthru_pct_of_model"].quantile(0.25)),
            "p50": float(investigate["cthru_pct_of_model"].quantile(0.50)),
            "p75": float(investigate["cthru_pct_of_model"].quantile(0.75)),
            "p90": float(investigate["cthru_pct_of_model"].quantile(0.90)),
        }
    }
    
    return analysis


def analyze_by_variance_range(df: pd.DataFrame) -> pd.DataFrame:
    """Group INVESTIGATE cases by variance range."""
    investigate = df[df["status"] == "INVESTIGATE"].copy()
    
    # Define ranges
    def variance_bucket(var):
        abs_var = abs(var)
        if abs_var < 15000:
            return "10k-15k (minor)"
        elif abs_var < 20000:
            return "15k-20k"
        elif abs_var < 30000:
            return "20k-30k"
        elif abs_var < 50000:
            return "30k-50k"
        else:
            return "50k+ (major)"
    
    investigate["variance_bucket"] = investigate["variance"].apply(variance_bucket)
    
    # Summary by bucket
    summary = investigate.groupby("variance_bucket").agg({
        "member_id": "count",
        "variance": ["mean", "median"],
        "cthru_pct_of_model": ["mean", "median"],
        "months_equivalent": ["mean", "median"],
    }).round(2)
    
    summary.columns = ['_'.join(col).strip() for col in summary.columns.values]
    summary = summary.rename(columns={"member_id_count": "count"})
    
    return summary


def analyze_by_chamber(df: pd.DataFrame) -> Dict:
    """Compare variance patterns between House and Senate."""
    investigate = df[df["status"] == "INVESTIGATE"].copy()
    
    analysis = {}
    for chamber in ["House", "Senate"]:
        chamber_data = investigate[investigate["chamber"] == chamber]
        if len(chamber_data) > 0:
            analysis[chamber] = {
                "count": int(len(chamber_data)),
                "median_variance": float(chamber_data["abs_variance"].median()),
                "median_cthru_pct": float(chamber_data["cthru_pct_of_model"].median()),
                "mean_total_comp": float(chamber_data["total_comp"].mean()),
            }
    
    return analysis


def analyze_by_leadership(df: pd.DataFrame) -> Dict:
    """Compare members with and without leadership roles."""
    investigate = df[df["status"] == "INVESTIGATE"].copy()
    
    # Split by leadership (has_stipend indicates leadership/committee roles)
    analysis = {}
    for has_leadership, label in [(True, "with_leadership"), (False, "no_leadership")]:
        subset = investigate[investigate["has_stipend"] == has_leadership]
        if len(subset) > 0:
            analysis[label] = {
                "count": int(len(subset)),
                "median_variance": float(subset["abs_variance"].median()),
                "median_cthru_pct": float(subset["cthru_pct_of_model"].median()),
                "median_role_stipends": float(subset["role_stipends_total"].median()),
            }
    
    return analysis


def identify_top_outliers(df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """Get top N outliers by absolute variance with explanations."""
    investigate = df[df["status"] == "INVESTIGATE"].copy()
    
    # Sort by absolute variance
    top = investigate.nlargest(n, "abs_variance")[[
        "name", "chamber", "variance", "total_comp", "cthru_total", 
        "cthru_pct_of_model", "months_equivalent", "role_stipends_total",
        "role_1", "role_2"
    ]].copy()
    
    # Generate explanations
    def explain(row):
        explanations = []
        
        pct = row["cthru_pct_of_model"]
        months = row["months_equivalent"]
        
        if pct < 50:
            explanations.append("⚠️ Very low CTHRU (< 50% of model) - likely partial year or data issue")
        elif 75 <= pct <= 90:
            explanations.append(f"🕐 Likely annualization ({months:.1f} months paid vs 12-month model)")
        elif pct > 100:
            explanations.append("⚠️ CTHRU > Model (negative variance) - possible multi-year payment or role change")
        else:
            explanations.append(f"❓ Unusual pattern ({pct:.0f}% of model)")
        
        if row["role_stipends_total"] > 20000:
            explanations.append(f"💰 High leadership stipends (${row['role_stipends_total']:,.0f}) - may be paid irregularly")
        
        return " | ".join(explanations)
    
    top["explanation"] = top.apply(explain, axis=1)
    
    return top


def generate_enhanced_status_recommendations(df: pd.DataFrame) -> Dict:
    """
    Propose new status categories to reduce false positives.
    """
    investigate = df[df["status"] == "INVESTIGATE"].copy()
    
    # Simulate new categorization
    def new_status(row):
        abs_var = abs(row["variance"])
        pct = row["cthru_pct_of_model"]
        
        # LIKELY_ANNUALIZED: variance >= 10k BUT CTHRU is 75-90% of model
        if abs_var >= 10000 and 75 <= pct <= 90:
            return "LIKELY_ANNUALIZED"
        
        # LIKELY_ANNUALIZED_MINOR: variance 10k-15k and within annualization range
        elif 10000 <= abs_var < 15000:
            return "LIKELY_ANNUALIZED_MINOR"
        
        # PAYMENT_TIMING: CTHRU > model (negative variance) within reasonable range
        elif row["variance"] < 0 and abs_var < 30000:
            return "PAYMENT_TIMING_ISSUE"
        
        # TRUE_INVESTIGATE: Still needs investigation
        else:
            return "TRUE_INVESTIGATE"
    
    investigate["proposed_status"] = investigate.apply(new_status, axis=1)
    
    # Count new categories
    new_counts = investigate["proposed_status"].value_counts().to_dict()
    
    recommendations = {
        "current_investigate_count": int(len(investigate)),
        "proposed_categorization": {k: int(v) for k, v in new_counts.items()},
        "reduction_in_investigate": int(new_counts.get("TRUE_INVESTIGATE", 0)),
        "reduction_pct": float((1 - new_counts.get("TRUE_INVESTIGATE", 0) / len(investigate)) * 100),
    }
    
    return recommendations


def save_enhanced_variance_csv(df: pd.DataFrame):
    """Save enhanced variance CSV with new columns."""
    # Add computed columns
    df["cthru_pct_of_model"] = (df["cthru_total"] / df["total_comp"]) * 100
    df["months_equivalent"] = (df["cthru_total"] / df["total_comp"]) * 12
    
    # Generate explanation for each row
    def generate_explanation(row):
        if row["status"] == "OK":
            return "Within acceptable variance range"
        elif row["status"] == "PARTIAL_OR_ROLE_CHANGE":
            return "Partial year, role change, or multi-agency employment"
        elif row["status"] == "NO_MATCH":
            return "No CTHRU record found"
        else:
            # INVESTIGATE - provide specific explanation
            pct = row["cthru_pct_of_model"]
            months = row["months_equivalent"]
            abs_var = abs(row["variance"])
            
            if 75 <= pct <= 90:
                return f"Likely annualization: {months:.1f} months paid vs 12-month model"
            elif pct < 50:
                return f"Very low CTHRU ({pct:.0f}% of model) - partial year or data issue"
            elif pct > 110:
                return f"CTHRU exceeds model ({pct:.0f}%) - possible payment timing or role change"
            elif row["role_stipends_total"] > 30000 and abs_var < 20000:
                return "Leadership stipends may be paid irregularly"
            else:
                return "Large unexplained variance - requires investigation"
    
    df["explanation"] = df.apply(generate_explanation, axis=1)
    
    # Reorder columns to put new ones after pct_diff
    cols = df.columns.tolist()
    new_cols = ["cthru_pct_of_model", "months_equivalent", "explanation"]
    
    # Remove new cols if they exist in the list
    for col in new_cols:
        if col in cols:
            cols.remove(col)
    
    # Find index of pct_diff
    pct_diff_idx = cols.index("pct_diff") if "pct_diff" in cols else len(cols) - 1
    
    # Insert new columns after pct_diff
    for i, col in enumerate(new_cols):
        cols.insert(pct_diff_idx + 1 + i, col)
    
    df_export = df[cols]
    
    # Save
    output_path = "out/cthru_variances.csv"
    df_export.to_csv(output_path, index=False)
    print(f"✓ Enhanced variance CSV saved to {output_path}")


def main():
    """Run comprehensive variance analysis."""
    print("=" * 80)
    print("CTHRU VARIANCE ANALYSIS")
    print("=" * 80)
    
    # Load data
    print("\n[1/7] Loading data...")
    df, df_members = load_data()
    df = calculate_cthru_percentage(df)
    print(f"  Loaded {len(df)} records")
    
    # Annualization analysis
    print("\n[2/7] Analyzing annualization hypothesis...")
    annualization = analyze_annualization_hypothesis(df)
    print(f"  Total INVESTIGATE cases: {annualization['total_investigate']}")
    print(f"  Likely partial year (75-90% of model): {annualization['likely_partial_year']} ({annualization['likely_partial_year_pct']:.1f}%)")
    print(f"  Median CTHRU %: {annualization['median_cthru_pct']:.1f}%")
    print(f"  Median months equivalent: {annualization['median_months_equiv']:.1f} months")
    
    # Variance range analysis
    print("\n[3/7] Analyzing by variance range...")
    variance_ranges = analyze_by_variance_range(df)
    print(variance_ranges.to_string())
    
    # Chamber analysis
    print("\n[4/7] Analyzing by chamber...")
    chamber_analysis = analyze_by_chamber(df)
    for chamber, stats in chamber_analysis.items():
        print(f"  {chamber}: {stats['count']} cases, median variance ${stats['median_variance']:,.0f}, CTHRU {stats['median_cthru_pct']:.1f}%")
    
    # Leadership analysis
    print("\n[5/7] Analyzing by leadership status...")
    leadership_analysis = analyze_by_leadership(df)
    for label, stats in leadership_analysis.items():
        print(f"  {label}: {stats['count']} cases, median variance ${stats['median_variance']:,.0f}, CTHRU {stats['median_cthru_pct']:.1f}%")
    
    # Top outliers
    print("\n[6/7] Identifying top 20 outliers...")
    top_outliers = identify_top_outliers(df, n=20)
    print(f"  Generated explanations for top {len(top_outliers)} cases")
    
    # Enhanced status recommendations
    print("\n[7/7] Generating status recommendations...")
    recommendations = generate_enhanced_status_recommendations(df)
    print(f"  Current INVESTIGATE count: {recommendations['current_investigate_count']}")
    print(f"  Proposed TRUE_INVESTIGATE count: {recommendations['reduction_in_investigate']}")
    print(f"  Reduction: {recommendations['reduction_pct']:.1f}%")
    print(f"  New categories: {recommendations['proposed_categorization']}")
    
    # Save comprehensive analysis
    print("\n[Saving outputs...]")
    
    # Save analysis JSON
    analysis_output = {
        "annualization_analysis": annualization,
        "variance_by_range": variance_ranges.to_dict(),
        "variance_by_chamber": chamber_analysis,
        "variance_by_leadership": leadership_analysis,
        "status_recommendations": recommendations,
    }
    
    Path("out").mkdir(exist_ok=True)
    with open("out/variance_analysis.json", "w") as f:
        json.dump(analysis_output, f, indent=2)
    print("  ✓ Saved out/variance_analysis.json")
    
    # Save top outliers CSV
    top_outliers.to_csv("out/top_outliers.csv", index=False)
    print("  ✓ Saved out/top_outliers.csv")
    
    # Save enhanced variance CSV
    save_enhanced_variance_csv(df)
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print("\nKey Findings:")
    print(f"  • {annualization['likely_partial_year_pct']:.0f}% of INVESTIGATE cases are likely due to annualization")
    print(f"  • Median CTHRU is {annualization['median_cthru_pct']:.0f}% of model ({annualization['median_months_equiv']:.1f} months)")
    print(f"  • With refined status logic, INVESTIGATE count could drop to {recommendations['reduction_in_investigate']}")
    print(f"  • That's a {recommendations['reduction_pct']:.0f}% reduction in false positives!")
    print("\nNext Steps:")
    print("  1. Review out/variance_analysis.json for detailed patterns")
    print("  2. Check out/top_outliers.csv for specific high-variance cases")
    print("  3. Review out/cthru_variances.csv (now enhanced with explanations)")
    print("  4. Update validation logic in src/validate.py based on findings")
    print("=" * 80)


if __name__ == "__main__":
    main()

