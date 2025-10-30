# Massachusetts Legislative Stipend Tracker

A comprehensive data pipeline that calculates total compensation for members of the Massachusetts General Court by combining:
- **MA Legislature API** data (members, leadership positions, committee assignments)
- **MassGIS shapefiles** (district boundary centroids for distance calculations)
- **Statutory pay rules** (M.G.L. c.3 §§9B-9C)

## Features

✅ **Automated Data Fetching**
- Fetches member rosters, leadership positions, and committee assignments via MA Legislature API
- Intelligent caching to avoid redundant API calls
- Retry logic with exponential backoff for robustness

✅ **Geographic Distance Calculation**
- Downloads and processes Senate/House district shapefiles from MassGIS
- Computes district centroids for expense stipend band determination
- Fallback to centroid-based calculations when residence data unavailable

✅ **Comprehensive Stipend Calculation**
- Base salary: $82,044 (2025-2026 cycle)
- **Expense stipends** (travel allowance): ≤50 miles = $15,000 | >50 miles = $20,000
- **Leadership stipends** (positions): Speaker/President ($80k), Majority/Minority Leaders ($60k), etc.
- Committee chair stipends: Ways & Means ($65k), Tier A ($30k), Tier B ($15k)
- Automatically selects top two stipends per member (per statute)

✅ **Interactive Visualization System**
- Plugin-based architecture - add new analyses by dropping files in `src/visualizations/`
- Built-in visualizations: Top Leadership Earners, Stipend Distribution, Chamber Comparison, Expense vs Leadership
- Interactive menu for running analyses after data pipeline completes
- Zero-configuration auto-discovery of visualization modules

✅ **Transparency & Provenance**
- Clear distinction between expense stipends (travel) and leadership stipends (positions)
- Tracks data source for each distance calculation (`band_source`: LOCALITY vs DISTRICT_CENTROID)
- Validates against statutory amounts from M.G.L. c.3
- Exports detailed aggregate metrics with stipend type breakdowns

## Architecture

### Pipeline Flow

```
1. Session Selection → User picks General Court (e.g., 194th, 2025-2026)
2. Member Fetch → API: /GeneralCourts/{gc}/LegislativeMembers
3. Leadership Fetch → API: /Branches/{House|Senate}/Leadership
4. Committee Fetch → API: /GeneralCourts/{gc}/Committees/{code}
5. Centroid Calculation → MassGIS shapefiles → district_centroids.json
6. Compensation Computation → Applies cycle config + top-two rule
7. Export → CSV (per-member detail) + JSON (aggregate metrics)
8. Interactive Menu → Run visualizations and analyses
```

### File Structure

```
beacon-hill-stipend-tracker/
├── main.py                    # Pipeline orchestration
├── requirements.txt           # Python dependencies
├── data/
│   ├── cycle/
│   │   └── 2025-2026.json     # Cycle configuration (salaries, stipends)
│   ├── cache/
│   │   ├── members_*.json     # Cached API responses
│   │   └── committee_*.json
│   ├── shapefiles/
│   │   ├── SENATE2021_POLY.*  # Senate district boundaries
│   │   └── HOUSE2021_POLY.*   # House district boundaries
│   └── district_centroids.json # Computed lat/lon for each district
├── out/
│   ├── members.csv            # Per-member compensation breakdown
│   ├── leadership_power.json  # Aggregate metrics with stipend breakdowns
│   ├── cthru_variances.csv    # Model vs actual payroll comparison
│   ├── cthru_summary.json     # Validation statistics and status counts
│   └── variance_analysis.json # Detailed variance pattern analysis
└── src/
    ├── centroids.py           # Shapefile download & centroid computation
    ├── computations.py        # Stipend calculation logic
    ├── fetchers.py            # API client with caching
    ├── helpers.py             # Utilities (distance, role mapping)
    ├── models.py              # Configuration & constants
    ├── normalizer.py          # District name normalization
    ├── validate.py            # CTHRU payroll validation with variance detection
    ├── variances.py           # Variance pattern analysis and categorization
    └── visualizations/        # Plugin-based visualization system
        ├── base.py            # Base classes for visualizations
        ├── __init__.py        # Auto-discovery registry
        ├── stipend_analysis.py      # Top earners & distribution
        ├── chamber_comparison.py    # House vs Senate metrics
        └── stipend_breakdown.py     # Expense vs leadership comparison
```

## Installation

### Prerequisites
- Python 3.10+ (tested on 3.11)
- Internet connection (for API and shapefile downloads)

### Setup

```bash
# Clone repository
git clone https://github.com/arbowl/beacon-hill-stipend-tracker/
cd beacon-hill-stipend-tracker

# Install dependencies
pip install -r requirements.txt

# Run pipeline
python main.py
```

## Usage

### Basic Run

```bash
python main.py
```

**Interactive Prompts:**
1. Select General Court (default: most recent)
2. Choose whether to fetch all committees or limit (for testing)
3. Pipeline automatically exports results to `out/`
4. **Visualization menu** appears with analysis options:
   - Top Leadership Stipend Earners
   - Leadership Stipend Distribution
   - House vs Senate Comparison
   - Expense vs Leadership Stipends
   - Run all visualizations at once

### Output Files

#### 1. `out/members.csv`
Per-member compensation breakdown with columns:
- `member_id`, `name`, `chamber`, `district`, `party`
- `distance_miles`, `distance_band` (LE50/GT50), `band_source`
- `base_salary`, `expense_stipend`
- `role_1`, `role_1_stipend`, `role_2`, `role_2_stipend`
- `role_stipends_total`, `total_comp`
- `has_stipend` (boolean), `last_updated`

**Example Row:**
```csv
MAH001,Jane Smith,House,1st Suffolk,Democratic,,42.3,LE50,DISTRICT_CENTROID,82044,15000,SPEAKER,80000,COMMITTEE_CHAIR_TIER_A,30000,110000,192044,true,2025-10-29
```

#### 2. `out/leadership_power.json`
Aggregate metrics with stipend type breakdowns:
```json
{
  "members": 202,
  "members_with_leadership_stipends": 125,
  "pct_with_leadership_stipends": 61.9,
  "total_leadership_stipend_dollars": 3717766,
  "total_expense_stipend_dollars": 3630000,
  "expense_stipend_breakdown": {
    "le50_miles": {"count": 42, "amount": 15000},
    "gt50_miles": {"count": 160, "amount": 20000}
  },
  "median_total_comp": 109822.0,
  "top10_avg_total_comp": 188504.2,
  "generated_at": "2025-10-29",
  "notes": "Leadership stipends = committee/leadership positions. Expense stipends = travel allowance based on distance from State House."
}
```

**Key Distinction:**
- `total_leadership_stipend_dollars`: Committee chairs, Speaker, leadership positions
- `total_expense_stipend_dollars`: Travel allowance based on distance from State House

## Configuration

### Cycle Config (`data/cycle/2025-2026.json`)

Defines all monetary values for a legislative cycle with biennial adjustment tracking:

```json
{
  "cycle": "2025-2026",
  "effective_date": "2025-01-01",
  
  "authority": {
    "base_adjustment": "Mass. Constitution Article CXVIII (median household income, biennial)",
    "stipends_and_expenses": "Applied by practice to M.G.L. c.3 §9B and §9C"
  },
  
  "adjustment_history": [
    {"year": 2019, "percent": 5.93, "factor": 1.0593},
    {"year": 2021, "percent": 6.46, "factor": 1.0646},
    {"year": 2023, "percent": 4.41, "factor": 1.0441},
    {"year": 2025, "percent": 11.39, "factor": 1.1139}
  ],
  
  "cumulative_adjustment": {
    "factor": 1.3116,
    "percent": 31.16,
    "calculation": "1.0593 × 1.0646 × 1.0441 × 1.1139 = 1.3116",
    "applies_to": {
      "base_salary": true,
      "expense_bands": true,
      "stipends": true
    }
  },
  
  "amounts_nominal_2017": {
    "base_salary": 62548,
    "expense_bands": {
      "LE50": 15000,
      "GT50": 20000
    },
    "stipends": {
      "SPEAKER": 72000,
      "SENATE_PRESIDENT": 72000,
      "WAYS_MEANS_CHAIR": 60000,
      "COMMITTEE_CHAIR_TIER_A": 27000,
      "COMMITTEE_CHAIR_TIER_B": 13500,
      "COMMITTEE_VICECHAIR_TIER_A": 4700,
      "COMMITTEE_VICECHAIR_TIER_B": 4700,
      ...
    }
  },
  
  "tier_a_committees": [
    "House Committee on Ways and Means",
    "Senate Committee on Rules",
    "Joint Committee on Ethics",
    ...
  ]
}
```

**Key Features:**
- Stores **2017 baseline amounts** from M.G.L. c.3 §9B-9C
- Tracks **biennial adjustment history** (2019, 2021, 2023, 2025)
- Computes **current amounts** by applying cumulative adjustment factor (1.3116 for 2025-2026)
- Example: Base salary = $62,548 × 1.3116 = **$82,038** (rounded)

**Tier A Committees** (chairs get $30k):
- Ways & Means (special: $65k)
- Rules, Steering & Policy, Bonding, Ethics
- Global Warming, Health Care Financing, Post Audit & Oversight
- Revenue, Transportation

**All Other Committees** default to Tier B ($15k).

### Committee Tier Overrides (`src/models.py`)

The `TIER_OVERRIDES` dict maps committee names to stipend keys:

```python
TIER_OVERRIDES = {
    "House Committee on Ways and Means": "WAYS_MEANS_CHAIR",
    "Senate Committee on Rules": "COMMITTEE_CHAIR_TIER_A",
    # ... all Tier A committees listed
}
```

If a committee is **not** in `TIER_OVERRIDES`, its chair defaults to **Tier B** (`COMMITTEE_CHAIR_TIER_B`).

## Data Sources & Provenance

### 1. MA Legislature API
- **Base URL:** `https://malegislature.gov/api`
- **Endpoints Used:**
  - `/GeneralCourts/Sessions` - Available sessions
  - `/GeneralCourts/{gc}/LegislativeMembers` - Member roster
  - `/Branches/{House|Senate}/Leadership` - Leadership positions
  - `/GeneralCourts/{gc}/Committees` - Committee list
  - `/GeneralCourts/{gc}/Committees/{code}` - Committee membership
- **Caching:** All responses cached in `data/cache/` to avoid redundant calls
- **Rate Limiting:** 0.15s delay between committee fetches (polite usage)

### 2. MassGIS Shapefiles
- **Source:** `s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/shapefiles/state/`
- **Files:** `SENATE2021.zip`, `HOUSE2021.zip`
- **Processing:**
  1. Download & extract if not present in `data/shapefiles/`
  2. Compute representative point (centroid) for each district polygon
  3. Convert to WGS84 (EPSG:4326) for haversine distance calculation
  4. Cache in `data/district_centroids.json`

### 3. Statutory Pay Rules
- **M.G.L. c.3 §9:** Base salary ($82,044 for 2025-2026)
- **M.G.L. c.3 §9B:** Expense stipends (distance-based)
- **M.G.L. c.3 §9C:** Leadership & committee stipends
- **Note:** Amounts subject to biennial adjustment; verify against [malegislature.gov](https://malegislature.gov/Laws/GeneralLaws/PartI/TitleI/Chapter3)

## Distance Band Calculation

### Methodology

1. **Preferred:** Member's home locality (if available)
   - Geocode locality → compute distance to State House (42.3570°N, 71.0630°W)
   - Source: `band_source = "LOCALITY"`

2. **Fallback:** District centroid (computed from shapefiles)
   - Use district polygon's representative point
   - Source: `band_source = "DISTRICT_CENTROID"`

### Expense Stipend Bands

- **LE50:** Distance ≤ 50 miles → $15,000/year
- **GT50:** Distance > 50 miles → $20,000/year

**Example:** A member from Springfield (90 miles) gets GT50 = $20,000.

### District Name Normalization

The `normalizer.py` module handles discrepancies between API district names and shapefile keys:

- **House:** "First Middlesex" → `MIDDLE01`
- **Senate:** "Middlesex and Worcester" → exact match or token-based fuzzy match

## Stipend Rules

### Top-Two Selection

Per M.G.L. c.3 §9C, members holding multiple leadership/committee positions receive **only the two highest stipends**.

**Example:**
- Member is: Majority Whip ($35k) + Ways & Means Chair ($65k) + Ethics Chair ($30k)
- **Paid:** $65k + $35k = $100k (top two)
- **Unpaid:** Ethics Chair ($30k) - third stipend discarded

### Leadership Stipends

| Position                      | Amount  |
|-------------------------------|---------|
| Speaker / Senate President    | $80,000 |
| Majority / Minority Leader    | $60,000 |
| President/Speaker Pro Tempore | $50,000 |
| Whip                          | $35,000 |
| Assistant Whip                | $35,000 |

### Committee Stipends

| Role                      | Tier     | Amount  |
|---------------------------|----------|---------|
| Ways & Means Chair        | Special  | $65,000 |
| Tier A Committee Chair    | A        | $30,000 |
| Tier B Committee Chair    | B        | $15,000 |
| Any Vice Chair            | -        | $5,200  |

## Visualizations

The system includes a plugin-based visualization framework that auto-discovers and runs analyses.

### Built-in Visualizations

1. **Top Leadership Stipend Earners**
   - Shows top 15 members by leadership/committee stipend amount
   - Displays concentration metrics (e.g., "Top 10 control X% of stipend dollars")

2. **Leadership Stipend Distribution**
   - Breakdown of who has leadership positions vs. who doesn't
   - Chamber-by-chamber analysis

3. **House vs Senate Comparison**
   - Compare compensation metrics between chambers
   - Average, median, and maximum total compensation
   - Leadership stipend statistics

4. **Expense vs Leadership Stipends**
   - Side-by-side comparison of travel vs position stipends
   - Shows total dollars for each type
   - Member overlap analysis

### Adding Custom Visualizations

Create a new file in `src/visualizations/` (e.g., `party_analysis.py`):

```python
from src.visualizations.base import Visualization, DataContext

class PartyBreakdown(Visualization):
    name = "Stipend Breakdown by Party"
    description = "Compare stipends across political parties"
    category = "Analysis"
    
    def run(self, context: DataContext) -> None:
        # Access data from context
        members = context.computed_rows
        
        # Your analysis logic here
        print("Running party breakdown...")
```

**That's it!** Your visualization automatically appears in the menu. No registration needed.

See `src/visualizations/README.md` for full documentation.

## Extensibility

### Adding New Cycles

1. Create `data/cycle/2027-2028.json` with updated amounts
2. Update `models.py` default: `load_cycle_config("2027-2028")`
3. Run pipeline

### Residence-Based Distance (Future)

To replace centroid-based distance with actual residence:

1. Create `residence_scraper.py` to fetch home addresses
2. Geocode addresses → `(lat, lon)`
3. Update `band_for_member()` in `computations.py` to prioritize residence
4. Maintain `band_source` transparency

### Adding Tier A Committees

Edit `TIER_OVERRIDES` in `src/models.py`:

```python
TIER_OVERRIDES = {
    ...
    "Joint Committee on New Priority": "COMMITTEE_CHAIR_TIER_A",
}
```

## Validation & Accuracy

### Checks Performed
- ✅ Base salary matches M.G.L. c.3 §9
- ✅ Expense bands align with distance thresholds
- ✅ Leadership stipends match statutory amounts
- ✅ Top-two rule enforced in computation
- ✅ All data sources logged with provenance
- ✅ Model validated against actual CTHRU payroll data

### Known Limitations
1. **Centroid Approximation:** District centroids may differ from actual member residences by 5-15 miles in rural areas
2. **Committee Coverage:** Relies on API completeness; some interim appointments may lag
3. **Static Shapefiles:** Uses 2021 boundaries; redistricting updates require new shapefiles
4. **Annualization Timing:** Model shows 12-month annualized amounts; CTHRU shows actual YTD cash payments

## CTHRU Payroll Validation

The system validates model-computed compensation against actual payroll data from the Massachusetts Comptroller's **CTHRU transparency portal**.

### Validation Pipeline

```bash
python src/validate.py
```

**Process:**
1. Fetches actual payroll data from CTHRU API (cached 24 hours)
2. Normalizes employee names for matching (handles nicknames, suffixes, hyphens)
3. Compares model compensation vs actual CTHRU payments
4. Categorizes variances into actionable statuses
5. Exports detailed variance analysis

### Variance Status Categories

| Status | Criteria | Priority | Meaning |
|--------|----------|----------|---------|
| **OK** | Variance < $1,500 | ✅ None | Within acceptable range |
| **PARTIAL_OR_ROLE_CHANGE** | Variance < $10k or multi-agency | ✅ None | Explainable timing/role changes |
| **LIKELY_ANNUALIZED** | CTHRU is 75-90% of model | ✅ None | Partial year (10 months actual vs 12-month model) |
| **INVESTIGATE_PARTIAL_YEAR** | CTHRU < 50% of model | 🔴 High | Mid-year appointment or data issue |
| **INVESTIGATE_LEADERSHIP** | High stipends (≥$50k) at 60-75% CTHRU | ⚠️ Medium | Irregular payment schedule |
| **INVESTIGATE_OVERPAYMENT** | CTHRU > 110% of model | ⚠️ Medium | Payment timing or multi-year adjustment |
| **INVESTIGATE** | Other large unexplained variance | 🔍 Review | Requires individual review |

### Output Files

#### `out/cthru_variances.csv`
Per-member variance breakdown with diagnostic columns:
- Model amounts: `total_comp`, `base_salary`, `role_stipends_total`, `expense_stipend`
- CTHRU actuals: `cthru_total`, `regular_pay`, `other_pay`
- Analysis: `variance`, `pct_diff`, `cthru_pct_of_model`, `months_equivalent`
- Status: `status`, `explanation` (human-readable)

#### `out/cthru_summary.json`
Aggregate statistics with breakdowns by:
- Status distribution counts
- Chamber (House vs Senate)
- Leadership role (with vs without stipends)
- Annualization hypothesis testing

**Example:**
```json
{
  "status_counts": {
    "LIKELY_ANNUALIZED": 104,
    "PARTIAL_OR_ROLE_CHANGE": 33,
    "INVESTIGATE_OVERPAYMENT": 21,
    "INVESTIGATE": 20,
    "OK": 11,
    "INVESTIGATE_LEADERSHIP": 9,
    "INVESTIGATE_PARTIAL_YEAR": 4
  },
  "annualization_analysis": {
    "median_cthru_pct_all": 88.7,
    "median_months_equivalent": 10.6,
    "hypothesis": "Median 10.6 months suggests partial year"
  }
}
```

### Variance Analysis Tool

For deep-dive pattern analysis:

```bash
python src/variances.py
```

**Features:**
- Tests annualization hypothesis (CTHRU % vs expected)
- Analyzes variance patterns by magnitude, chamber, and role
- Identifies top outliers with specific explanations
- Generates enhanced status recommendations
- Exports detailed statistical breakdowns

**Outputs:**
- `out/variance_analysis.json` - Statistical analysis
- `out/top_outliers.csv` - Top 20 cases prioritized by variance
- Enhanced `cthru_variances.csv` with explanation columns

### Name Normalization

The validator uses sophisticated name matching to achieve **100% match rate**:

**Automated Normalization:**
- Remove generational suffixes (Jr., III, etc.)
- Handle common nicknames (Mike→Michael, Kate→Kathleen)
- Strip accents and punctuation
- First + last word extraction (ignore middle names)

**Manual Mapping:** For edge cases like compound surnames, hyphens, apostrophes:
```python
NAME_MANUAL_MAP = {
    "alice hanlon peisch": "alice hanlon",  # Compound surname
    "james j o day": "james o",  # O'Day apostrophe handling
}
```

### Key Findings (2025-2026 Cycle)

Based on October 2025 CTHRU data:
- **202 legislators validated** (100% match rate)
- **104 cases (51.5%)** flagged as LIKELY_ANNUALIZED (expected - CTHRU through Oct vs 12-month model)
- **54 cases (26.7%)** require investigation vs 158 originally (66% false-positive reduction)
- **Median CTHRU: 87.7%** of model = 10.5 months equivalent (validates annualization hypothesis)

### Typical Variance Causes

1. **Annualization Timing (51%):** CTHRU shows YTD actuals (Jan-Oct); model shows full-year projection
2. **Payment Timing (10%):** Stipends/allowances paid ahead of schedule or retroactively
3. **Leadership Schedules (5%):** Top positions (Speaker, President) have irregular payment schedules
4. **Mid-Year Appointments (2%):** New members appointed after session start
5. **Other (5%):** Role changes, multi-agency employment, data issues

## Troubleshooting

### "Cycle config not found"
**Cause:** Missing `data/cycle/2025-2026.json`  
**Fix:** Ensure file exists or create from template in this README

### "Shapefiles download failed"
**Cause:** MassGIS server unreachable or URL changed  
**Fix:** Check network connection; verify URLs in `src/centroids.py`

### "No members found"
**Cause:** API endpoint changed or General Court number invalid  
**Fix:** Verify session selection; check API base URL in `src/models.py`

### Type Errors / Linter Warnings
**Fix:** Run linter and address issues:
```bash
python -m pylint src/ main.py
python -m mypy src/ main.py --ignore-missing-imports
```

## Development

### Code Style
- **Formatter:** Black-compatible (79-char line limit)
- **Type Hints:** Full annotations in function signatures
- **Docstrings:** Google-style for public functions

### Testing Strategy
1. **Unit Tests:** Mock API responses, test computation logic
2. **Integration Tests:** Use cached data, verify CSV output format
3. **Validation:** Compare subset against official payroll (CTHRU database)

### Contributing
Contributions welcome! Focus areas:
- Residence geocoding for improved distance accuracy
- Historical cycle data (2023-2024, 2021-2022, etc.)
- Additional visualizations (party analysis, district comparisons, etc.)
- Export to additional formats (Excel, HTML reports)
- Web dashboard for interactive exploration

## License

This project processes public data from official Massachusetts government sources. All statutory amounts are subject to M.G.L. c.3 and biennial legislative adjustments.

**Data License:** Public domain (MA.gov APIs and MassGIS shapefiles)  
**Code License:** [Specify your license, e.g., MIT]

## References

- [MA Legislature API](https://malegislature.gov/api)
- [MassGIS Data Portal](https://www.mass.gov/info-details/massgis-data-layers)
- [M.G.L. c.3 §9-9C (Compensation)](https://malegislature.gov/Laws/GeneralLaws/PartI/TitleI/Chapter3)
- [2025-2026 Session Info](https://malegislature.gov/GeneralCourt/194)

---

**Last Updated:** October 30, 2025  
**Pipeline Version:** 1.2  
**Cycle:** 2025-2026 (194th General Court)

### Recent Updates (v1.2)
- ✅ **CTHRU payroll validation** with intelligent variance categorization
- 🎯 **Granular investigation tiers** (Partial Year, Leadership, Overpayment) for prioritization
- 📊 **Annualization detection** (75-90% CTHRU = partial year, not error)
- 🔍 **100% name match rate** with sophisticated normalization + manual overrides
- 📈 **Variance analysis tool** for pattern detection and outlier identification
- 🎨 66% reduction in false-positive INVESTIGATE cases

### Previous Updates (v1.1)
- ✨ Added plugin-based visualization system with interactive menu
- 🎯 Clarified distinction between expense stipends (travel) and leadership stipends (positions)
- 📊 Four built-in visualizations: Top Earners, Distribution, Chamber Comparison, Stipend Types
- 📈 Enhanced `leadership_power.json` with expense vs leadership stipend breakdowns

