"""Power Concentration Report - Comprehensive stipend inequality analysis.

Generates a multi-section report quantifying leadership-controlled stipend
distribution, concentration metrics, and geographic equity across the
Massachusetts General Court.

Outputs:
- Interactive HTML report with Plotly visualizations
- Printable PDF summary
- JSON data export for external dashboards
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from datetime import datetime
from statistics import mean, median

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle
    )
    from reportlab.lib.enums import TA_CENTER
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from src.visualizations.base import Visualization, DataContext
from src.models import CYCLE_CONFIG, STATE_HOUSE_LATLON


class PowerConcentrationReport(Visualization):
    """Comprehensive stipend inequality & geographic equity analysis."""

    name = "Power Concentration Report"
    description = (
        "Comprehensive inequality & geographic equity analysis (HTML/PDF)"
    )
    category = "Reports"

    def __init__(self):
        self.output_dir = Path("out")
        self.output_dir.mkdir(exist_ok=True)

    def run(self, context: DataContext) -> None:
        """Generate the complete power concentration report."""
        print("\n" + "=" * 80)
        print("POWER CONCENTRATION REPORT")
        print("=" * 80)
        print("Generating comprehensive stipend inequality analysis...")
        print()
        metrics = self._calculate_metrics(context)
        narrative = self._generate_narrative(metrics)
        print("Creating visualizations...")
        fig_lorenz = self._create_lorenz_curve(metrics)
        fig_geo = self._create_geographic_map(context, metrics)
        fig_hierarchy = self._create_hierarchy_sankey(context, metrics)
        fig_kpis = self._create_kpi_dashboard(metrics)
        print("Assembling HTML report...")
        self._export_html(
            narrative,
            fig_lorenz,
            fig_geo,
            fig_hierarchy,
            fig_kpis,
            metrics
        )
        print("Exporting data...")
        self._export_json(metrics)
        if REPORTLAB_AVAILABLE:
            print("Generating PDF report...")
            self._export_pdf(narrative, metrics)
        else:
            print("(Skipping PDF - reportlab not available)")
        print("\n" + "=" * 80)
        print("✓ Report generation complete!")
        print()
        print("Outputs:")
        html_path = self.output_dir / "power_concentration_report.html"
        print(f"  → {html_path}")
        json_path = self.output_dir / "power_concentration_data.json"
        print(f"  → {json_path}")
        if REPORTLAB_AVAILABLE:
            pdf_path = self.output_dir / "power_concentration_report.pdf"
            print(f"  → {pdf_path}")
        print("=" * 80 + "\n")

    def _calculate_metrics(self, context: DataContext) -> dict:
        """Calculate all concentration and inequality metrics."""
        rows = context.computed_rows
        total_members = len(rows)
        with_leadership = [
            r for r in rows if r.get("role_stipends_total", 0) > 0
        ]
        leadership_stipends = [
            r.get("role_stipends_total", 0) for r in rows
        ]
        expense_stipends = [r.get("expense_stipend", 0) for r in rows]
        total_comp = [r.get("total_comp", 0) for r in rows]
        leadership_sorted = sorted(leadership_stipends, reverse=True)
        comp_sorted = sorted(total_comp, reverse=True)
        gini = self._calculate_gini(total_comp)
        leadership_nonzero = [s for s in leadership_stipends if s > 0]
        if leadership_nonzero:
            gini_leadership = self._calculate_gini(leadership_nonzero)
        else:
            gini_leadership = 0
        total_leadership = sum(leadership_stipends)
        total_expense = sum(expense_stipends)
        total_all_comp = sum(total_comp)
        top10_leadership = sum(leadership_sorted[:10])
        top20_leadership = sum(leadership_sorted[:20])
        top10_comp = sum(comp_sorted[:10])
        if total_members:
            pct_with_leadership = (
                len(with_leadership) / total_members * 100
            )
        else:
            pct_with_leadership = 0
        if total_leadership:
            pct_top10_leadership = (
                top10_leadership / total_leadership * 100
            )
            pct_top20_leadership = (
                top20_leadership / total_leadership * 100
            )
        else:
            pct_top10_leadership = 0
            pct_top20_leadership = 0
        if total_all_comp:
            pct_top10_comp = top10_comp / total_all_comp * 100
        else:
            pct_top10_comp = 0
        median_comp = median(total_comp) if total_comp else 0
        mean_comp = mean(total_comp) if total_comp else 0
        if leadership_nonzero:
            median_leadership = median(leadership_nonzero)
            mean_leadership = mean(leadership_nonzero)
        else:
            median_leadership = 0
            mean_leadership = 0
        house_members = [r for r in rows if r.get("chamber") == "House"]
        senate_members = [
            r for r in rows if r.get("chamber") == "Senate"
        ]
        house_with_leadership = [
            r for r in house_members
            if r.get("role_stipends_total", 0) > 0
        ]
        senate_with_leadership = [
            r for r in senate_members
            if r.get("role_stipends_total", 0) > 0
        ]
        house_leadership_total = sum(
            r.get("role_stipends_total", 0) for r in house_members
        )
        senate_leadership_total = sum(
            r.get("role_stipends_total", 0) for r in senate_members
        )
        if house_members:
            house_avg_comp = mean(
                [r.get("total_comp", 0) for r in house_members]
            )
        else:
            house_avg_comp = 0
        if senate_members:
            senate_avg_comp = mean(
                [r.get("total_comp", 0) for r in senate_members]
            )
        else:
            senate_avg_comp = 0
        if total_expense > 0:
            leadership_expense_ratio = total_leadership / total_expense
        else:
            leadership_expense_ratio = 0
        distant_members = [
            r for r in rows if r.get("distance_miles", 0) > 50
        ]
        close_members = [
            r for r in rows if r.get("distance_miles", 0) <= 50
        ]
        if distant_members:
            distant_avg_comp = mean(
                [r.get("total_comp", 0) for r in distant_members]
            )
        else:
            distant_avg_comp = 0
        if close_members:
            close_avg_comp = mean(
                [r.get("total_comp", 0) for r in close_members]
            )
        else:
            close_avg_comp = 0
        if distant_members:
            distant_leadership_pct = (
                len([
                    r for r in distant_members
                    if r.get("role_stipends_total", 0) > 0
                ]) /
                len(distant_members) * 100
            )
        else:
            distant_leadership_pct = 0
        if close_members:
            close_leadership_pct = (
                len([
                    r for r in close_members
                    if r.get("role_stipends_total", 0) > 0
                ]) /
                len(close_members) * 100
            )
        else:
            close_leadership_pct = 0
        top_earners_list = sorted(
            rows,
            key=lambda r: r.get("total_comp", 0),
            reverse=True
        )[:10]
        return {
            "timestamp": datetime.now().isoformat(),
            "cycle": CYCLE_CONFIG.get("cycle", "N/A"),
            "base_salary": CYCLE_CONFIG.get("base_salary", 0),
            "total_members": total_members,
            "members_with_leadership_stipends": len(with_leadership),
            "pct_with_leadership_stipends": pct_with_leadership,
            "total_leadership_stipends": total_leadership,
            "total_expense_stipends": total_expense,
            "total_all_compensation": total_all_comp,
            "gini_coefficient": gini,
            "gini_leadership": gini_leadership,
            "top10_leadership_share": pct_top10_leadership,
            "top20_leadership_share": pct_top20_leadership,
            "top10_comp_share": pct_top10_comp,
            "top10_leadership_dollars": top10_leadership,
            "top10_comp_dollars": top10_comp,
            "median_total_comp": median_comp,
            "mean_total_comp": mean_comp,
            "median_leadership_stipend": median_leadership,
            "mean_leadership_stipend": mean_leadership,
            "median_mean_gap": mean_comp - median_comp,
            "house_count": len(house_members),
            "senate_count": len(senate_members),
            "house_with_leadership": len(house_with_leadership),
            "senate_with_leadership": len(senate_with_leadership),
            "house_leadership_total": house_leadership_total,
            "senate_leadership_total": senate_leadership_total,
            "house_avg_comp": house_avg_comp,
            "senate_avg_comp": senate_avg_comp,
            "chamber_avg_gap": senate_avg_comp - house_avg_comp,
            "leadership_expense_ratio": leadership_expense_ratio,
            "distant_members_count": len(distant_members),
            "close_members_count": len(close_members),
            "distant_avg_comp": distant_avg_comp,
            "close_avg_comp": close_avg_comp,
            "distant_leadership_pct": distant_leadership_pct,
            "close_leadership_pct": close_leadership_pct,
            "geographic_comp_gap": close_avg_comp - distant_avg_comp,
            "top_earners": [
                {
                    "name": r.get("name", "Unknown"),
                    "chamber": r.get("chamber", "N/A"),
                    "district": r.get("district", "N/A"),
                    "total_comp": r.get("total_comp", 0),
                    "role_stipends_total": r.get(
                        "role_stipends_total",
                        0
                    ),
                    "expense_stipend": r.get("expense_stipend", 0),
                    "distance_miles": r.get("distance_miles", 0),
                    "role_1": r.get("role_1", ""),
                    "role_2": r.get("role_2", ""),
                }
                for r in top_earners_list
            ],
            "leadership_stipends_array": leadership_stipends,
            "total_comp_array": total_comp,
            "rows": rows,
        }

    def _calculate_gini(self, values: list[float]) -> float:
        """
        Calculate Gini coefficient for a list of values.
        Returns value between 0 (perfect equality) and 1 (inequality).
        """
        if not values or len(values) == 0:
            return 0.0
        sorted_values = np.sort(np.array(values))
        n = len(sorted_values)
        if sorted_values.sum() == 0:
            return 0.0
        cumsum = np.cumsum(sorted_values)
        numerator = (
            2 * np.sum((np.arange(n) + 1) * sorted_values) -
            (n + 1) * cumsum[-1]
        )
        return numerator / (n * cumsum[-1])

    def _create_lorenz_curve(self, metrics: dict) -> go.Figure:
        """Create Lorenz curve showing stipend concentration."""
        stipends = [
            s for s in metrics["leadership_stipends_array"] if s > 0
        ]
        stipends_sorted = np.sort(stipends)
        n = len(stipends_sorted)
        cumulative_stipends = np.cumsum(stipends_sorted)
        total = cumulative_stipends[-1] if n > 0 else 1
        pop_pct = np.arange(1, n + 1) / n * 100
        stipend_pct = cumulative_stipends / total * 100
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[0, 100],
            y=[0, 100],
            mode='lines',
            name='Perfect Equality',
            line=dict(color='gray', dash='dash'),
            hoverinfo='skip'
        ))
        # Convert numpy arrays to lists for proper HTML serialization
        lorenz_x = np.concatenate([[0], pop_pct]).tolist()
        lorenz_y = np.concatenate([[0], stipend_pct]).tolist()
        fig.add_trace(go.Scatter(
            x=lorenz_x,
            y=lorenz_y,
            mode='lines',
            name='Actual Distribution',
            line=dict(color='#d62728', width=3),
            fill='tonexty',
            fillcolor='rgba(214, 39, 40, 0.2)',
            hovertemplate=(
                '<b>Bottom %{x:.1f}% of legislators</b><br>' +
                'Control %{y:.1f}% of stipends<extra></extra>'
            )
        ))
        if n >= 10:
            top10_idx = n - 10
            top10_share = metrics["top10_leadership_share"]
            fig.add_trace(go.Scatter(
                x=[float(pop_pct[top10_idx])],
                y=[float(stipend_pct[top10_idx])],
                mode='markers+text',
                marker=dict(size=12, color='darkred', symbol='diamond'),
                text=['Top 10'],
                textposition='top center',
                name='Top 10',
                hovertemplate=(
                    '<b>Top 10 legislators</b><br>' +
                    f'Control {top10_share:.1f}% of stipends' +
                    '<extra></extra>'
                )
            ))
        top10_text = (
            f"Top 10 control {metrics['top10_leadership_share']:.1f}%"
            " of stipends"
        )
        fig.update_layout(
            title=dict(
                text=(
                    'Leadership Stipend Concentration '
                    f'(Gini: {metrics["gini_leadership"]:.3f})'
                ),
                font=dict(size=20, color='#1f77b4')
            ),
            xaxis_title="Cumulative % of Legislators (with stipends)",
            yaxis_title="Cumulative % of Leadership Stipend Dollars",
            hovermode='closest',
            showlegend=True,
            height=500,
            template='plotly_white',
            annotations=[
                dict(
                    text=top10_text,
                    xref="paper",
                    yref="paper",
                    x=0.02,
                    y=0.98,
                    showarrow=False,
                    font=dict(size=14, color='darkred'),
                    bgcolor='rgba(255, 255, 255, 0.8)',
                    bordercolor='darkred',
                    borderwidth=2,
                    borderpad=4
                )
            ]
        )
        return fig

    def _create_geographic_map(
        self,
        context: DataContext,  # noqa: ARG002
        metrics: dict
    ) -> go.Figure:
        """Create choropleth map showing geographic compensation."""
        try:
            centroids_path = Path("data/district_centroids.json")
            with open(centroids_path, encoding='utf-8') as f:
                centroids_data = json.load(f)
            map_data = []
            for row in metrics["rows"]:
                district = row.get("district", "")
                chamber = row.get("chamber", "")
                coords = None
                if (chamber in centroids_data and
                        district in centroids_data[chamber]):
                    coords = centroids_data[chamber][district]
                if coords:
                    stipend_above_base = (
                        row.get("total_comp", 0) -
                        CYCLE_CONFIG.get("base_salary", 0)
                    )
                    map_data.append({
                        "lat": coords[0],
                        "lon": coords[1],
                        "name": row.get("name", "Unknown"),
                        "district": f"{chamber} {district}",
                        "stipend_above_base": stipend_above_base,
                        "total_comp": row.get("total_comp", 0),
                        "distance": row.get("distance_miles", 0),
                        "role_stipend": row.get("role_stipends_total", 0),
                        "expense_stipend": row.get("expense_stipend", 0),
                    })
            fig = go.Figure()
            stipend_values = [d["stipend_above_base"] for d in map_data]
            marker_sizes = [
                min(max(d["stipend_above_base"] / 3000, 5), 30)
                for d in map_data
            ]
            fig.add_trace(go.Scattergeo(
                lon=[d["lon"] for d in map_data],
                lat=[d["lat"] for d in map_data],
                mode='markers',
                marker=dict(
                    size=marker_sizes,
                    color=stipend_values,
                    colorscale='RdYlGn_r',
                    cmin=min(stipend_values),
                    cmax=max(stipend_values),
                    colorbar=dict(
                        title="Stipends<br>Above Base",
                        tickprefix="$",
                        tickformat=",.0f"
                    ),
                    line=dict(width=0.5, color='white')
                ),
                text=[d["name"] for d in map_data],
                customdata=[
                    [
                        d["district"],
                        d["total_comp"],
                        d["role_stipend"],
                        d["expense_stipend"],
                        d["distance"]
                    ]
                    for d in map_data
                ],
                hovertemplate=(
                    '<b>%{text}</b><br>' +
                    '%{customdata[0]}<br>' +
                    'Total Comp: $%{customdata[1]:,.0f}<br>' +
                    'Leadership: $%{customdata[2]:,.0f}<br>' +
                    'Expense: $%{customdata[3]:,.0f}<br>' +
                    'Distance: %{customdata[4]:.1f} mi<extra></extra>'
                )
            ))
            fig.add_trace(go.Scattergeo(
                lon=[STATE_HOUSE_LATLON[1]],
                lat=[STATE_HOUSE_LATLON[0]],
                mode='markers+text',
                marker=dict(
                    size=15,
                    color='gold',
                    symbol='star',
                    line=dict(width=2, color='black')
                ),
                text=['State House'],
                textposition='top center',
                name='State House',
                hoverinfo='text',
                hovertext='Massachusetts State House<br>Boston, MA'
            ))
            fig.update_geos(
                scope='usa',
                center=dict(lat=42.3, lon=-71.8),
                projection_scale=30,
                showland=True,
                landcolor='rgb(243, 243, 243)',
                coastlinecolor='rgb(204, 204, 204)',
                showlakes=True,
                lakecolor='rgb(230, 240, 255)',
            )
            fig.update_layout(
                title=dict(
                    text=(
                        'Geographic Distribution: '
                        'Stipends Above Base Salary'
                    ),
                    font=dict(size=20, color='#1f77b4')
                ),
                height=600,
                showlegend=False,
            )
            return fig
        except Exception as e:
            print(f"Warning: Could not create geographic map: {e}")
            fig = go.Figure()
            fig.add_annotation(
                text=(
                    f"Geographic map unavailable<br>(Error: {str(e)})"
                ),
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=16)
            )
            fig.update_layout(height=400)
            return fig

    def _create_hierarchy_sankey(
        self,
        context: DataContext,  # noqa: ARG002
        metrics: dict
    ) -> go.Figure:
        """Create Sankey diagram showing compensation flow."""
        nodes = ["All Legislators", "With Leadership", "No Leadership"]
        node_colors = ['lightblue', 'lightcoral', 'lightgray']
        role_categories = {}
        for row in metrics["rows"]:
            role1 = row.get("role_1", "")
            if role1:
                role_cat = self._simplify_role(role1)
                if role_cat not in role_categories:
                    role_categories[role_cat] = 0
                role_categories[role_cat] += row.get(
                    "role_stipends_total",
                    0
                )
        top_roles = sorted(
            role_categories.items(),
            key=lambda x: x[1],
            reverse=True
        )[:8]
        for role, _ in top_roles:
            nodes.append(role)
            node_colors.append('lightyellow')
        source = []
        target = []
        value = []
        link_colors = []
        with_leadership_total = sum(
            r.get("total_comp", 0) for r in metrics["rows"]
            if r.get("role_stipends_total", 0) > 0
        )
        without_leadership_total = sum(
            r.get("total_comp", 0) for r in metrics["rows"]
            if r.get("role_stipends_total", 0) == 0
        )
        source.append(0)  # All Legislators
        target.append(1)  # With Leadership
        value.append(with_leadership_total)
        link_colors.append('rgba(255, 182, 193, 0.4)')
        source.append(0)  # All Legislators
        target.append(2)  # No Leadership
        value.append(without_leadership_total)
        link_colors.append('rgba(211, 211, 211, 0.4)')
        role_node_map = {
            role: idx + 3
            for idx, (role, _) in enumerate(top_roles)
        }
        role_totals = {role: 0 for role, _ in top_roles}
        for row in metrics["rows"]:
            role1 = row.get("role_1", "")
            if role1:
                role_cat = self._simplify_role(role1)
                if role_cat in role_totals:
                    role_totals[role_cat] += row.get("total_comp", 0)
        for role, total in role_totals.items():
            if total > 0:
                source.append(1)  # With Leadership
                target.append(role_node_map[role])
                value.append(total)
                link_colors.append('rgba(255, 255, 224, 0.4)')
        fig = go.Figure(data=[go.Sankey(
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color='black', width=0.5),
                label=nodes,
                color=node_colors
            ),
            link=dict(
                source=source,
                target=target,
                value=value,
                color=link_colors
            )
        )])
        fig.update_layout(
            title=dict(
                text='Compensation Flow Through Leadership Hierarchy',
                font=dict(size=20, color='#1f77b4')
            ),
            height=600,
            font=dict(size=12)
        )
        return fig

    def _simplify_role(self, role: str) -> str:
        """Simplify role names for display."""
        role_upper = role.upper()
        if "SPEAKER" in role_upper:
            return "Speaker/President"
        elif "WAYS" in role_upper and "MEANS" in role_upper:
            return "Ways & Means"
        elif "CHAIR" in role_upper and "TIER_A" in role_upper:
            return "Committee Chair (Tier A)"
        elif "CHAIR" in role_upper:
            return "Committee Chair (Other)"
        elif "VICE" in role_upper:
            return "Vice Chair"
        elif "WHIP" in role_upper:
            return "Whip"
        elif "LEADER" in role_upper:
            return "Party Leader"
        else:
            return "Other Leadership"

    def _create_kpi_dashboard(self, metrics: dict) -> go.Figure:
        """Create KPI dashboard with key metrics."""
        fig = make_subplots(
            rows=2,
            cols=4,
            subplot_titles=(
                'Gini Coefficient',
                'Top 10 Share',
                'Median vs Mean Gap',
                'Leadership:Expense',
                'Chamber Disparity',
                'Geographic Gap',
                'With Leadership',
                'Concentration Index'
            ),
            specs=[[{'type': 'indicator'}] * 4,
                   [{'type': 'indicator'}] * 4],
            vertical_spacing=0.25,
            horizontal_spacing=0.15
        )
        gini = metrics["gini_coefficient"]
        bar_color = 'darkred' if gini > 0.5 else 'orange'
        fig.add_trace(go.Indicator(
            mode="gauge+number",
            value=gini,
            number={'font': {'size': 32}, 'valueformat': '.3f'},
            gauge={
                'axis': {
                    'range': [0, 1],
                    'tickwidth': 1,
                    'tickcolor': 'darkgray',
                    'tickmode': 'linear',
                    'tick0': 0,
                    'dtick': 0.2
                },
                'bar': {'color': bar_color, 'thickness': 0.6},
                'bgcolor': 'white',
                'borderwidth': 2,
                'bordercolor': 'lightgray',
                'steps': [
                    {'range': [0, 0.3], 'color': 'lightgreen'},
                    {'range': [0.3, 0.5], 'color': 'yellow'},
                    {'range': [0.5, 1], 'color': 'lightcoral'}
                ],
                'threshold': {
                    'line': {'color': 'red', 'width': 3},
                    'thickness': 0.75,
                    'value': 0.5
                }
            },
            domain={'x': [0.15, 0.85], 'y': [0.35, 0.65]}
        ), row=1, col=1)
        fig.add_trace(go.Indicator(
            mode="number+delta",
            value=metrics["top10_leadership_share"],
            delta={
                'reference': 10,
                'relative': False,
                'suffix': 'pp'
            },
            number={'suffix': '%', 'font': {'size': 48}},
            domain={'x': [0, 1], 'y': [0, 1]}
        ), row=1, col=2)
        fig.add_trace(go.Indicator(
            mode="number",
            value=metrics["median_mean_gap"],
            number={
                'prefix': '$',
                'valueformat': ',.0f',
                'font': {'size': 40}
            },
            domain={'x': [0, 1], 'y': [0, 1]}
        ), row=1, col=3)
        fig.add_trace(go.Indicator(
            mode="number",
            value=metrics["leadership_expense_ratio"],
            number={
                'suffix': ':1',
                'valueformat': '.2f',
                'font': {'size': 40}
            },
            domain={'x': [0, 1], 'y': [0, 1]}
        ), row=1, col=4)
        fig.add_trace(go.Indicator(
            mode="number+delta",
            value=metrics["senate_avg_comp"],
            delta={
                'reference': metrics["house_avg_comp"],
                'relative': False,
                'prefix': '+$'
            },
            number={
                'prefix': '$',
                'valueformat': ',.0f',
                'font': {'size': 36}
            },
            title={'text': 'Senate Avg'},
            domain={'x': [0, 1], 'y': [0, 1]}
        ), row=2, col=1)
        geo_gap = metrics["geographic_comp_gap"]
        geo_color = 'darkred' if geo_gap > 0 else 'darkgreen'
        fig.add_trace(go.Indicator(
            mode="number",
            value=geo_gap,
            number={
                'prefix': '$',
                'valueformat': ',.0f',
                'font': {'size': 40, 'color': geo_color}
            },
            domain={'x': [0, 1], 'y': [0, 1]}
        ), row=2, col=2)
        fig.add_trace(go.Indicator(
            mode="number+gauge",
            value=metrics["pct_with_leadership_stipends"],
            gauge={
                'axis': {
                    'range': [0, 100],
                    'tickwidth': 1,
                    'tickcolor': 'darkgray',
                    'tickmode': 'linear',
                    'tick0': 0,
                    'dtick': 20
                },
                'bar': {'color': 'steelblue', 'thickness': 0.6},
                'bgcolor': 'white',
                'borderwidth': 2,
                'bordercolor': 'lightgray',
                'shape': 'angular'
            },
            number={
                'suffix': '%',
                'font': {'size': 32},
                'valueformat': '.1f'
            },
            domain={'x': [0.15, 0.85], 'y': [0.35, 0.65]}
        ), row=2, col=3)
        comp_array = [r.get("total_comp", 0) for r in metrics["rows"]]
        top10_comp_total = sum(
            sorted(comp_array, reverse=True)[:10]
        )
        bottom_half_count = metrics["total_members"] // 2
        bottom_half = sorted(comp_array)[:bottom_half_count]
        bottom50_avg = mean(bottom_half) if bottom_half else 1
        top10_avg = top10_comp_total / 10 if top10_comp_total else 0
        if bottom50_avg > 0:
            concentration_index = top10_avg / bottom50_avg
        else:
            concentration_index = 0
        fig.add_trace(go.Indicator(
            mode="number",
            value=concentration_index,
            number={
                'suffix': 'x',
                'valueformat': '.2f',
                'font': {'size': 40}
            },
            title={'text': 'Top10/Bottom50'},
            domain={'x': [0, 1], 'y': [0, 1]}
        ), row=2, col=4)
        fig.update_layout(
            title=dict(
                text='Key Inequality Metrics Dashboard',
                font=dict(size=24, color='#1f77b4'),
                x=0.5,
                xanchor='center'
            ),
            height=600,
            showlegend=False
        )
        return fig

    def _generate_narrative(self, metrics: dict) -> str:
        """Generate auto-narrative summary in plain English."""
        m = metrics
        top10_avg = m['top10_comp_dollars'] / 10
        pct_with_lead = m['pct_with_leadership_stipends']
        top10_share = m['top10_leadership_share']
        lead_exp_ratio = m['leadership_expense_ratio']
        narrative = f"""
## Executive Summary

**Massachusetts General Court - {m['cycle']} Compensation Analysis**
*Generated: {datetime.now().strftime('%B %d, %Y')}*

**Data Note:** *This analysis is based on modeled compensation \
calculated from statutory pay rules (M.G.L. c.3 §§9B-9C) and \
publicly available committee/leadership assignments. These are \
projected amounts based on positional stipends and distance bands, \
not actual payroll disbursements.*

---

### The Two-Tier Legislature: Base Equality, Leadership Concentration

**All {m['total_members']} legislators** receive the same base salary \
(**${m['base_salary']:,.0f}**) plus a distance-based travel stipend \
(**$15,000-$20,000**), creating a fundamentally **flat compensation \
structure** for the legislative rank-and-file.

However, **discretionary leadership stipends** introduce sharp \
stratification: only **{m['members_with_leadership_stipends']} \
legislators ({pct_with_lead:.1f}%)** hold positions that carry \
additional compensation.

Among these position-holders, the **top 10 captured {top10_share:.1f}%** \
of all leadership dollars—an average of **${top10_avg:,.0f}** versus \
the median of **${m['median_total_comp']:,.0f}** for all members.

**Result:** While base and travel pay create equality, \
**discretionary stipends concentrate power and compensation among a \
small leadership cluster**, producing a two-tier system within an \
otherwise egalitarian pay structure.

---

### Concentration Metrics

**Gini Coefficient:** {m['gini_coefficient']:.3f}
*(0 = perfect equality, 1 = perfect inequality)*

This moderate Gini reflects the **dual structure**: a flat base for \
all members (high equality) combined with concentrated leadership \
stipends (high inequality).

The **mean-median gap** of **${m['median_mean_gap']:,.0f}** reveals \
the impact of the leadership cluster: a small number of high earners \
elevate the average substantially above the median.

**Top 20 legislators** control **{m['top20_leadership_share']:.1f}%** \
of leadership stipend dollars, demonstrating extreme concentration at \
the apex of the hierarchy.

While **travel allowances exceed leadership stipends in aggregate** \
({lead_exp_ratio:.2f}:1 ratio), leadership dollars **concentrate among \
fewer recipients** (only {pct_with_lead:.0f}% hold positions), creating \
much higher per-capita amounts for position-holders. This concentration—not \
geographic distance—drives the top compensation tiers.

---

### Chamber Disparity

**Senate** members average **${m['senate_avg_comp']:,.0f}** in total \
compensation, compared to
**${m['house_avg_comp']:,.0f}** for **House** members—a gap of \
**${m['chamber_avg_gap']:,.0f}**.

While the Senate is smaller (40 vs 160 members), Senate members are \
**{m['senate_with_leadership'] / m['senate_count'] * 100:.1f}%**
likely to hold leadership positions compared to \
**{m['house_with_leadership'] / m['house_count'] * 100:.1f}%** \
in the House.

---

### Geographic Patterns: Not a Strong Predictor

Members from districts **>50 miles from Boston** \
({m['distant_members_count']} legislators) earn an average of
**${m['distant_avg_comp']:,.0f}**, while those **≤50 miles** \
({m['close_members_count']} legislators) average
**${m['close_avg_comp']:,.0f}**.

"""

        geo_gap = m['geographic_comp_gap']
        direction = 'more' if geo_gap > 0 else 'less'

        narrative += f"""
The **${abs(geo_gap):,.0f} difference** ({direction} for closer \
districts) represents only \
**{abs(geo_gap) / m['median_total_comp'] * 100:.1f}%** of median \
compensation—**not a strong predictor** of total earnings.

**Why geography matters less than expected:** Travel stipends \
($15,000-$20,000) are distance-based and equalize routine costs. \
The real variance comes from **discretionary leadership positions**, \
which are distributed based on political factors—not geography.

**Leadership distribution:** {m['distant_leadership_pct']:.1f}% of \
distant members vs {m['close_leadership_pct']:.1f}% of close members \
hold leadership positions. Any geographic skew reflects **political \
centralization**, not travel compensation design.

**Bottom line:** Distance from Boston is a weak proxy for \
compensation. Leadership position is the determining factor.

---

### Top 10 Earners

| Rank | Name | Chamber | Total Comp | Leadership | Expense | \
Distance |
|------|------|---------|------------|------------|---------|----------|
"""

        for idx, earner in enumerate(m['top_earners'], 1):
            name = earner['name'][:25]
            chamber = earner['chamber']
            total = earner['total_comp']
            role_stip = earner['role_stipends_total']
            exp_stip = earner['expense_stipend']
            dist = earner['distance_miles']

            narrative += (
                f"| {idx} | {name} | {chamber} | "
                f"${total:,.0f} | ${role_stip:,.0f} | "
                f"${exp_stip:,.0f} | {dist:.1f} mi |\n"
            )

        narrative += f"""

---

### Key Takeaways

1. **Flat Base, Concentrated Leadership**: All legislators receive \
equal base salary + travel stipends, but discretionary leadership \
positions create a small cluster of high earners (top 10 control \
{top10_share:.1f}% of leadership dollars).

2. **Position Trumps Geography**: While travel allowances are larger \
in total ({lead_exp_ratio:.2f}:1), leadership dollars concentrate among \
62% of members, creating higher per-capita amounts. Distance from \
Boston predicts only ~{abs(geo_gap) / m['median_total_comp'] * 100:.0f}% \
of variance. Political position is the determining factor.

3. **Modeled Projections**: These figures represent **calculated \
statutory amounts**, not actual payroll. They show what the rules \
prescribe, not verified disbursements.

4. **Chamber Structure**: Senate members earn ${m['chamber_avg_gap']:,.0f} \
more on average, driven by higher leadership position density (smaller \
chamber, similar leadership roles).

5. **Dual Inequality Structure**: Gini of {m['gini_coefficient']:.3f} \
reflects egalitarian base pay (low inequality) combined with concentrated \
leadership pay (high inequality).

---

*This analysis quantifies how Massachusetts' compensation system creates \
a two-tier legislature: a fundamentally equal baseline for all members, \
with a small leadership cluster receiving substantial positional stipends.*

**Data Methodology**: Compensation modeled from statutory rules \
(M.G.L. c.3 §§9B-9C), MA Legislature API positions, MassGIS distance \
calculations, and published stipend schedules. **These are projected \
amounts based on position and distance, not verified payroll records.**
"""

        return narrative

    def _markdown_to_html(self, markdown: str) -> str:
        """Convert markdown to HTML with proper formatting."""
        import re
        lines = markdown.split('\n')
        html_lines = []
        in_table = False
        table_header_done = False
        for line in lines:
            if not line.strip():
                if in_table:
                    html_lines.append('</table>')
                    in_table = False
                    table_header_done = False
                html_lines.append('<br>')
                continue
            if line.startswith('### '):
                if in_table:
                    html_lines.append('</table>')
                    in_table = False
                    table_header_done = False
                html_lines.append(f'<h3>{line[4:]}</h3>')
                continue
            elif line.startswith('## '):
                if in_table:
                    html_lines.append('</table>')
                    in_table = False
                    table_header_done = False
                html_lines.append(f'<h2>{line[3:]}</h2>')
                continue
            elif line.startswith('# '):
                if in_table:
                    html_lines.append('</table>')
                    in_table = False
                    table_header_done = False
                html_lines.append(f'<h2>{line[2:]}</h2>')
                continue
            if line.strip() == '---':
                if in_table:
                    html_lines.append('</table>')
                    in_table = False
                    table_header_done = False
                html_lines.append('<hr>')
                continue
            if line.strip().startswith('|') and line.strip().endswith('|'):
                if re.match(r'^\|[\s\-:|]+\|$', line.strip()):
                    continue  # Skip separator lines
                cells = [
                    cell.strip()
                    for cell in line.strip().split('|')[1:-1]
                ]
                if not in_table:
                    html_lines.append(
                        '<table style="width:100%; border-collapse: '
                        'collapse; margin: 20px 0;">'
                    )
                    in_table = True
                    table_header_done = False
                if not table_header_done:
                    html_lines.append('<thead><tr>')
                    for cell in cells:
                        cell_html = self._format_inline_markdown(cell)
                        html_lines.append(
                            f'<th style="padding: 12px; text-align: left; '
                            f'background-color: #1f77b4; color: white; '
                            f'border: 1px solid #ddd;">{cell_html}</th>'
                        )
                    html_lines.append('</tr></thead><tbody>')
                    table_header_done = True
                else:
                    html_lines.append('<tr>')
                    for cell in cells:
                        cell_html = self._format_inline_markdown(cell)
                        html_lines.append(
                            f'<td style="padding: 12px; text-align: left; '
                            f'border: 1px solid #ddd;">{cell_html}</td>'
                        )
                    html_lines.append('</tr>')
                continue
            if in_table:
                html_lines.append('</tbody></table>')
                in_table = False
                table_header_done = False
            line_html = self._format_inline_markdown(line)
            html_lines.append(f'<p>{line_html}</p>')
        if in_table:
            html_lines.append('</tbody></table>')
        return '\n'.join(html_lines)

    def _format_inline_markdown(self, text: str) -> str:
        """Format inline markdown (bold, italic, etc.)."""
        text = re.sub(
            r'\*\*(.+?)\*\*',
            r'<strong>\1</strong>',
            text
        )
        text = re.sub(
            r'__(.+?)__',
            r'<strong>\1</strong>',
            text
        )
        text = re.sub(
            r'(?<!\w)\*([^*]+?)\*(?!\w)',
            r'<em>\1</em>',
            text
        )
        text = re.sub(
            r'(?<!\w)_([^_]+?)_(?!\w)',
            r'<em>\1</em>',
            text
        )
        return text

    def _export_html(
        self,
        narrative: str,
        fig_lorenz: go.Figure,
        fig_geo: go.Figure,
        fig_hierarchy: go.Figure,
        fig_kpis: go.Figure,
        metrics: dict
    ) -> None:
        """Export complete interactive HTML report."""
        narrative_html = self._markdown_to_html(narrative)
        lorenz_html = fig_lorenz.to_html(
            full_html=False,
            include_plotlyjs=False
        )
        geo_html = fig_geo.to_html(
            full_html=False,
            include_plotlyjs=False
        )
        hierarchy_html = fig_hierarchy.to_html(
            full_html=False,
            include_plotlyjs=False
        )
        kpis_html = fig_kpis.to_html(
            full_html=False,
            include_plotlyjs=False
        )
        timestamp = datetime.now().strftime('%B %d, %Y at %I:%M %p')
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Power Concentration Report - Massachusetts Legislature</title>
    <script src="https://cdn.plot.ly/plotly-2.26.0.min.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #1f77b4 0%, #2ca02c 100%);
            color: white;
            padding: 40px;
            border-radius: 10px;
            text-align: center;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
        }}
        .header p {{
            margin: 10px 0 0 0;
            font-size: 1.2em;
            opacity: 0.9;
        }}
        .section {{
            background: white;
            padding: 30px;
            margin-bottom: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .narrative {{
            line-height: 1.8;
            color: #333;
            font-size: 16px;
        }}
        .narrative h2 {{
            color: #1f77b4;
            border-bottom: 3px solid #1f77b4;
            padding-bottom: 10px;
            margin-top: 30px;
            margin-bottom: 15px;
            font-size: 1.8em;
        }}
        .narrative h3 {{
            color: #2ca02c;
            margin-top: 25px;
            margin-bottom: 12px;
            font-size: 1.4em;
        }}
        .narrative p {{
            margin: 10px 0;
            text-align: justify;
        }}
        .narrative hr {{
            border: none;
            border-top: 2px solid #ddd;
            margin: 25px 0;
        }}
        .narrative strong {{
            color: #1f77b4;
            font-weight: 600;
        }}
        .narrative em {{
            font-style: italic;
            color: #555;
        }}
        .narrative table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .narrative th, .narrative td {{
            padding: 12px;
            text-align: left;
            border: 1px solid #ddd;
        }}
        .narrative th {{
            background-color: #1f77b4;
            color: white;
            font-weight: bold;
        }}
        .narrative tbody tr:hover {{
            background-color: #f0f8ff;
        }}
        .narrative tbody tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .chart-container {{
            margin: 20px 0;
        }}
        .footer {{
            text-align: center;
            color: #666;
            margin-top: 40px;
            padding: 20px;
            border-top: 2px solid #ddd;
        }}
        .disclaimer {{
            background: #fff9e6;
            border-left: 4px solid #ff9800;
            padding: 20px;
            margin: 20px 0;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .disclaimer h3 {{
            margin-top: 0;
            color: #e65100;
        }}
        .disclaimer p {{
            margin: 8px 0;
            line-height: 1.6;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🏛️ Power Concentration Report</h1>
        <p>Massachusetts General Court - Stipend Inequality & \
Geographic Equity Analysis</p>
        <p style="font-size: 0.9em;">Cycle: {metrics['cycle']} | \
Generated: {timestamp}</p>
    </div>

    <div class="disclaimer">
        <h3>📊 Data Note: Modeled Projections</h3>
        <p><strong>This analysis presents calculated compensation based \
on statutory rules, not actual payroll data.</strong></p>
        <p>Figures represent what Massachusetts law prescribes based on \
positional stipends (M.G.L. c.3 §§9B-9C) and distance calculations, not \
verified disbursements. These are projections of what legislators \
<em>should receive</em> according to published schedules, committee \
assignments, and geographic formulas.</p>
        <p><strong>Key findings:</strong> (1) Base + travel pay are \
equalized for all members, (2) Leadership stipends concentrate among \
62% of members (creating per-capita differences), (3) Geography is not \
a strong income predictor.</p>
    </div>

    <div class="section">
        <h2 style="color: #1f77b4; margin-top: 0;">\
📊 Key Metrics Dashboard</h2>
        <div class="chart-container">
            {kpis_html}
        </div>
    </div>

    <div class="section">
        <h2 style="color: #1f77b4; margin-top: 0;">\
📈 Concentration Pyramid</h2>
        <p style="font-size: 1.1em; color: #555;">
            The Lorenz curve below visualizes how leadership stipends \
are distributed.
            The further the curve deviates from the diagonal \
"perfect equality" line,
            the more concentrated power and compensation become.
        </p>
        <div class="chart-container">
            {lorenz_html}
        </div>
    </div>

    <div class="section">
        <h2 style="color: #1f77b4; margin-top: 0;">\
🗺️ Geographic Distribution</h2>
        <p style="font-size: 1.1em; color: #555;">
            This map shows total compensation above base salary for \
each legislator.
            Larger circles and redder colors indicate higher stipend \
accumulation.
            Notice the clustering of high earners near the State House \
(⭐).
        </p>
        <div class="chart-container">
            {geo_html}
        </div>
    </div>

    <div class="section">
        <h2 style="color: #1f77b4; margin-top: 0;">\
🔀 Compensation Flow Hierarchy</h2>
        <p style="font-size: 1.1em; color: #555;">
            This Sankey diagram traces how total compensation flows \
through the
            legislative hierarchy, from all members into leadership \
tiers and specific roles.
        </p>
        <div class="chart-container">
            {hierarchy_html}
        </div>
    </div>

    <div class="section narrative">
        <h2 style="color: #1f77b4; margin-top: 0; border: none;">\
📝 Narrative Summary</h2>
        {narrative_html}
    </div>

    <div class="footer">
        <p><strong>Data Sources:</strong> MA Legislature API • \
MassGIS Shapefiles • M.G.L. c.3 §§9B-9C</p>
        <p><strong>Report Generated By:</strong> Massachusetts \
Legislative Stipend Tracker</p>
        <p style="font-size: 0.9em; color: #999;">
            This analysis is provided for transparency and public \
accountability.
            All data is publicly available and methodology is open \
source.
        </p>
    </div>
</body>
</html>
"""
        output_path = self.output_dir / "power_concentration_report.html"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"  ✓ HTML report saved to {output_path}")

    def _export_json(self, metrics: dict) -> None:
        """Export metrics as JSON for external dashboards."""
        export_metrics = {
            k: v for k, v in metrics.items()
            if not k.endswith('_array') and k != 'rows'
        }
        output_path = self.output_dir / "power_concentration_data.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_metrics, f, indent=2)
        print(f"  ✓ Data JSON saved to {output_path}")

    def _export_pdf(
        self,
        narrative: str,  # noqa: ARG002
        metrics: dict
    ) -> None:
        """Export PDF summary report."""
        if not REPORTLAB_AVAILABLE:
            return
        output_path = self.output_dir / "power_concentration_report.pdf"
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )
        story = []
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f77b4'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1f77b4'),
            spaceAfter=12,
            spaceBefore=12
        )
        story.append(
            Paragraph("Power Concentration Report", title_style)
        )
        story.append(Paragraph(
            f"Massachusetts General Court - {metrics['cycle']}",
            styles['Normal']
        ))
        story.append(Paragraph(
            f"Generated: {datetime.now().strftime('%B %d, %Y')}",
            styles['Normal']
        ))
        story.append(Spacer(1, 0.3 * inch))
        story.append(Paragraph("Executive Summary", heading_style))
        pct_with = metrics['pct_with_leadership_stipends']
        summary_data = [
            ["Metric", "Value"],
            ["Total Legislators", str(metrics['total_members'])],
            [
                "With Leadership Stipends",
                (
                    f"{metrics['members_with_leadership_stipends']} "
                    f"({pct_with:.1f}%)"
                )
            ],
            [
                "Gini Coefficient",
                f"{metrics['gini_coefficient']:.3f}"
            ],
            [
                "Top 10 Control",
                f"{metrics['top10_leadership_share']:.1f}% of stipends"
            ],
            [
                "Median Compensation",
                f"${metrics['median_total_comp']:,.0f}"
            ],
            [
                "Mean Compensation",
                f"${metrics['mean_total_comp']:,.0f}"
            ],
            [
                "Leadership:Expense Ratio",
                f"{metrics['leadership_expense_ratio']:.1f}:1"
            ],
        ]
        summary_table = Table(summary_data, colWidths=[3*inch, 3*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0),
             colors.HexColor('#1f77b4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.3 * inch))
        story.append(Paragraph("Key Findings", heading_style))
        top10_share = metrics['top10_leadership_share']
        lead_exp_ratio = metrics['leadership_expense_ratio']
        chamber_gap = metrics['chamber_avg_gap']
        geo_gap = metrics['geographic_comp_gap']
        geo_dir = 'more' if geo_gap > 0 else 'less'
        findings = [
            (
                f"• Top 10 legislators control {top10_share:.1f}% "
                "of all leadership stipend dollars"
            ),
            (
                f"• Leadership stipends are {lead_exp_ratio:.1f}x "
                "larger than expense stipends"
            ),
            (
                f"• Senate members earn ${chamber_gap:,.0f} more "
                "on average than House members"
            ),
            (
                f"• Members near Boston earn ${abs(geo_gap):,.0f} "
                f"{geo_dir} than distant members"
            ),
            (
                f"• Only {pct_with:.1f}% of legislators receive "
                "leadership stipends"
            ),
        ]
        for finding in findings:
            story.append(Paragraph(finding, styles['Normal']))
            story.append(Spacer(1, 0.1 * inch))
        story.append(Spacer(1, 0.2 * inch))
        story.append(
            Paragraph("Top 10 Compensation Earners", heading_style)
        )
        top10_data = [["Rank", "Name", "Chamber", "Total Comp"]]
        for idx, earner in enumerate(metrics['top_earners'], 1):
            top10_data.append([
                str(idx),
                earner['name'][:30],
                earner['chamber'],
                f"${earner['total_comp']:,.0f}"
            ])
        col_widths = [0.5*inch, 2.5*inch, 1*inch, 1.5*inch]
        top10_table = Table(top10_data, colWidths=col_widths)
        top10_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0),
             colors.HexColor('#1f77b4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        story.append(top10_table)
        story.append(Spacer(1, 0.3 * inch))
        story.append(
            Paragraph("Methodology & Data Sources", heading_style)
        )
        methodology_text = (
            "This analysis combines data from the MA Legislature API, "
            "MassGIS district shapefiles, and statutory pay schedules "
            "(M.G.L. c.3 §§9B-9C). The Gini coefficient measures "
            "inequality on a scale from 0 (perfect equality) to 1 "
            "(perfect inequality). Geographic analysis uses "
            "straight-line distance from each district centroid to "
            "the State House."
        )
        story.append(Paragraph(methodology_text, styles['Normal']))
        story.append(Spacer(1, 0.2 * inch))
        footer_text = (
            "<i>For interactive visualizations and complete analysis, "
            "see power_concentration_report.html</i>"
        )
        story.append(Paragraph(footer_text, styles['Normal']))
        doc.build(story)
        print(f"  ✓ PDF report saved to {output_path}")
