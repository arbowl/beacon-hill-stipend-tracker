"""
CTHRU Compensation Validation Module

Validates model-computed compensation against actual payroll data from the
Massachusetts Comptroller's CTHRU transparency portal.

Data source: https://cthru.data.socrata.com/resource/9ttk-7vz6.csv
"""

from __future__ import annotations

import json
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any
import hashlib

import pandas as pd


# Variance status thresholds
THRESHOLD_OK = 1500
THRESHOLD_PARTIAL = 10000

# Annualization detection thresholds
# CTHRU data is typically through Oct 18 (~10.5 months), while model is annualized
# If CTHRU is 75-90% of model, likely explanation is partial year rather than error
ANNUALIZATION_MIN_PCT = 75
ANNUALIZATION_MAX_PCT = 90

# Investigation tier thresholds
PARTIAL_YEAR_THRESHOLD = 50  # CTHRU < 50% suggests mid-year appointment
LEADERSHIP_HIGH_THRESHOLD = 60  # For cases with high leadership stipends
LEADERSHIP_LOW_THRESHOLD = 75
OVERPAYMENT_THRESHOLD = 110  # CTHRU > 110% suggests payment timing issue
HIGH_LEADERSHIP_STIPEND = 50000  # Threshold for "high" leadership compensation

# Common nickname mappings (bidirectional)
NICKNAME_MAP = {
    # Both directions to catch either format
    "mike": "michael",
    "michael": "michael",
    "nick": "nicholas",
    "nicholas": "nicholas",
    "bill": "william",
    "william": "william",
    "will": "william",
    "bob": "robert",
    "robert": "robert",
    "rob": "robert",
    "dick": "richard",
    "richard": "richard",
    "rick": "richard",
    "jim": "james",
    "james": "james",
    "jimmy": "james",
    "jay": "james",  # Sometimes Jay = James
    "joe": "joseph",
    "joseph": "joseph",
    "dan": "daniel",
    "daniel": "daniel",
    "tom": "thomas",
    "thomas": "thomas",
    "tommy": "thomas",
    "pat": "patricia",
    "patricia": "patricia",
    "patty": "patricia",
    "tricia": "patricia",
    "beth": "elizabeth",
    "elizabeth": "elizabeth",
    "liz": "elizabeth",
    "betsy": "elizabeth",
    "sue": "susan",
    "susan": "susan",
    # Kate can be Katherine OR Kathleen - normalize to kathleen
    "kate": "kathleen",
    "katherine": "kathleen",
    "kathleen": "kathleen",
    "katie": "kathleen",
    "kathy": "kathleen",
    "cindy": "cynthia",
    "cynthia": "cynthia",
    "matt": "matthew",
    "matthew": "matthew",
    "chris": "christopher",
    "christopher": "christopher",
    "steve": "steven",
    "steven": "steven",
    "dave": "david",
    "david": "david",
    "ed": "edward",
    "edward": "edward",
    "ted": "edward",
    "greg": "gregory",
    "gregory": "gregory",
    "tony": "anthony",
    "anthony": "anthony",
    "jen": "jennifer",
    "jennifer": "jennifer",
    "jenny": "jennifer",
    "manny": "emmanuel",
    "emmanuel": "emmanuel",
    "buddy": "buddy",
    "bud": "buddy",
}

# Manual name mapping: Model name → CTHRU name
# 
# WHY MANUAL MAPPING IS THE RIGHT APPROACH:
# =========================================
# 
# After attempting multiple algorithmic approaches (compound surname detection,
# middle name heuristics, aggressive nickname normalization), we discovered that
# legislative name matching has too many edge cases for a purely algorithmic
# solution:
#
# 1. **Ambiguity is unavoidable**:
#    - "Christopher Richard Flanagan" - is "Richard" a middle name or part of 
#      compound surname?
#    - "Kate Lipper-Garabedian" - is Kate short for Katherine or Kathleen?
#    - Without external data, these are fundamentally unsolvable
#
# 2. **Each "clever" heuristic breaks more than it fixes**:
#    - 3-word compound surname detection: Fixed 1 case, broke 15 cases
#    - Kate→Kathleen normalization: Fixed some, broke others where Kate→Katherine
#    - The more logic we add, the more fragile the system becomes
#
# 3. **The dataset is small and stable**:
#    - ~200 legislators (not 200,000)
#    - Names change rarely (elections every 2 years)
#    - Adding 20 manual mappings is trivial vs maintaining complex heuristics
#
# 4. **Manual mapping is:**
#    - **Explicit**: Each mapping documents an actual mismatch
#    - **Debuggable**: Clear why each exists
#    - **Maintainable**: Easy to add/remove entries
#    - **Reliable**: Won't break when edge cases change
#    - **Auditable**: Journalists/researchers can verify each mapping
#
# 5. **Real-world precedent**:
#    - Tax systems use manual SSN overrides
#    - Healthcare uses manual patient matching for edge cases
#    - Financial systems use manual transaction reconciliation rules
#    - This is standard practice for high-stakes data matching
#
# MAINTENANCE INSTRUCTIONS:
# - When adding entries, document why (middle name? nickname? compound surname?)
# - Use normalized form (lowercase, no punctuation, sorted alphabetically)
# - Test that both sides produce same normalized output
# - Run validation, check NO_MATCH list, add mappings as needed

NAME_MANUAL_MAP = {
    # Compound surnames (space-separated in model, hyphenated in reality)
    # Note: hyphens are removed during normalization, so keys have spaces
    "alice hanlon peisch": "alice hanlon",  # "Hanlon Peisch" compound → CTHRU splits as "hanlon peisch alice"
    
    # Full/middle names in model vs abbreviated in CTHRU
    "christopher flanagan richard": "christopher flanagan",  # Richard is middle name
    "carmine gentile lawrence": "carmine gentile",  # Lawrence is middle name
    "david linsky paul": "david linsky",  # Paul is middle name
    "david robertson allen": "david robertson",  # Allen is middle name
    "jack lewis patrick": "jack lewis",  # Patrick is middle name
    "patrick kearney joseph": "kearney patrick",  # Joseph is middle name
    "jeffrey rosario turco": "jeffrey turco",  # Rosario is middle name
    "giannino jessica ann": "giannino jessica",  # Ann is middle name
    "john francis moran": "john moran",  # Francis is middle name
    "steven george xiarhos": "steven xiarhos",  # George is middle name
    
    # Nickname mismatches requiring specific mapping
    "creem cynthia stone": "creem cynthia",  # Stone is middle name
    
    # Hyphenated surnames (hyphens removed during normalization)
    # Model has hyphen in surname, gets split into separate words
    # NOTE: Include middle initials in keys since they're preserved during normalization
    "james c arena derosa": "arena james",  # Arena-DeRosa with middle initial C
    "alyson m sullivan almeida": "alyson sullivan",  # Sullivan-Almeida with middle initial M
    "patricia farley bouvier": "farley patricia",  # Farley-Bouvier (after Tricia→Patricia)
    "brandy fluker reid": "brandy fluker",  # Fluker-Reid → picks "reid" but should be "fluker"
    
    # Hyphenated FIRST names (not surnames!)
    "ann margaret ferrante": "ferrante margaret",  # Ann-Margaret is first name, not surname
    
    # Kathleen/Katherine ambiguity with hyphenated surname
    # Kate normalizes to "kathleen" per NICKNAME_MAP, hyphen removed
    "kathleen lipper garabedian": "kathleen lipper",  # Fixed: CTHRU produces "kathleen lipper"
    
    # O'Name apostrophe issues (apostrophe replaced with space, creates extra word "o")
    # Model: "James J. O'Day" → ["james", "j", "o", "day"]
    # CTHRU: "O'Day, James" → ["o", "day", "james"] → algorithm picks "james o"
    "james j o day": "james o",  # O'Day apostrophe creates extra "o" word
    
    # Model: "Patrick M. O'Connor" → ["patrick", "m", "o", "connor"]  
    # CTHRU: "O'Connor, Patrick" → ["o", "connor", "patrick"] → algorithm picks "o patrick"
    "patrick m o connor": "o patrick",  # O'Connor apostrophe creates extra "o" word
    
    # Legal name vs nickname variations
    "emmanuel cruz": "cruz victor",  # Manny (Emmanuel) Cruz → Victor Cruz in CTHRU (legal name)
}


def remove_accents(s: str) -> str:
    """
    Remove accents from unicode characters.
    
    Examples:
        "José" -> "Jose"
        "Gómez" -> "Gomez"
        "Hernández" -> "Hernandez"
    """
    # Normalize to NFD (decomposed form), then filter out combining marks
    nfd = unicodedata.normalize('NFD', s)
    return ''.join(char for char in nfd
                   if unicodedata.category(char) != 'Mn')


def remove_suffix(s: str) -> str:
    """
    Remove generational suffixes from names.
    
    Examples:
        "William J. Driscoll, Jr." -> "William J. Driscoll"
        "John Barrett, III" -> "John Barrett"
        "Angelo Jr. Puppolo" -> "Angelo Puppolo"
    """
    # Remove common suffixes at end (after comma or space)
    suffixes = [
        ", Jr.", ", Jr", ", Sr.", ", Sr",
        ", II", ", III", ", IV", ", V",
        ", 2nd", ", 3rd", ", 4th",
        " Jr.", " Jr", " Sr.", " Sr",
        " II", " III", " IV", " V",
    ]
    
    for suffix in suffixes:
        if s.endswith(suffix):
            s = s[:-len(suffix)]
            break
    
    # Also remove if Jr/Sr appears mid-name (rare but happens)
    # "John Jr. Smith" -> "John Smith"
    s = s.replace(" Jr. ", " ").replace(" Sr. ", " ")
    
    return s.strip()


def normalize_nickname(name: str) -> str:
    """
    Normalize common nicknames to their formal equivalents.
    
    Examples:
        "mike" -> "michael"
        "nick" -> "nicholas"
    """
    return NICKNAME_MAP.get(name, name)


def norm_name(s: str) -> str:
    """
    Normalize names for joining CTHRU with model data.

    Strategy (simplified for reliability):
    1. Remove generational suffixes (Jr., III, etc.)
    2. Remove accents (José -> Jose)
    3. Lowercase, strip punctuation, collapse spaces
    4. Normalize common nicknames
    5. Check manual override map
    6. Extract FIRST word + LAST word only (ignore middle)
    7. Sort alphabetically for consistency
    
    Note: We intentionally use a SIMPLE algorithm + manual overrides
    rather than complex heuristics. See NAME_MANUAL_MAP docstring for why.
    """
    s = (s or "").strip()
    
    # Remove suffixes first (Jr., Sr., III, etc.)
    s = remove_suffix(s)
    
    # Remove accents
    s = remove_accents(s)
    
    # Lowercase and remove punctuation (but keep hyphens for now)
    s = s.lower()
    for ch in ",.''-–—":
        s = s.replace(ch, " ")
    s = " ".join(s.split())

    # Apply nickname normalization to full string first
    parts = s.split()
    normalized_parts = [normalize_nickname(p) for p in parts]
    normalized_full = " ".join(normalized_parts)
    
    # Check manual override map
    if normalized_full in NAME_MANUAL_MAP:
        override = NAME_MANUAL_MAP[normalized_full]
        if override == "SKIP":
            return normalized_full  # Return as-is, won't match anything
        return override

    # Simple algorithm: first word + last word, sorted
    if not normalized_parts:
        return ""
    if len(normalized_parts) == 1:
        return normalized_parts[0]
    
    # Use first and last word only (drop middle names/initials)
    first_word = normalized_parts[0]
    last_word = normalized_parts[-1]
    
    # Sort alphabetically for consistency
    words = sorted([first_word, last_word])
    return " ".join(words)


def get_cache_path(url: str, year: int | None) -> Path:
    """Generate cache file path based on URL and year."""
    # Create a hash of the URL + year for the cache filename
    cache_key = f"{url}_{year}"
    cache_hash = hashlib.md5(cache_key.encode()).hexdigest()[:12]
    cache_dir = Path("data/cache/cthru")
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"cthru_{year or 'all'}_{cache_hash}.csv"


def is_cache_valid(cache_path: Path, max_age_hours: int = 24) -> bool:
    """Check if cache file exists and is recent enough."""
    if not cache_path.exists():
        return False
    
    # Check if cache is fresh (less than max_age_hours old)
    cache_age = time.time() - cache_path.stat().st_mtime
    return cache_age < (max_age_hours * 3600)


def fetch_cthru_data(
    url: str,
    agency_filter: str = "LEGISLATURE",
    year: int | None = None,
    max_retries: int = 3,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Fetch and filter CTHRU data from Socrata CSV endpoint.

    Args:
        url: CTHRU CSV endpoint
        agency_filter: Filter to agencies containing this string
        year: Calendar year to filter to (if None, no year filter)
        max_retries: Number of retry attempts for rate limiting
        use_cache: Whether to use cached data if available

    Returns:
        DataFrame with filtered CTHRU records
    """
    # Check cache first
    cache_path = get_cache_path(url, year)
    if use_cache and is_cache_valid(cache_path):
        print(f"  Using cached CTHRU data from {cache_path}")
        df = pd.read_csv(cache_path, encoding="utf-8")
        print(f"  Loaded {len(df)} cached records")
        return df
    
    backoff_delays = [0.8, 1.6, 3.2]

    for attempt in range(max_retries):
        try:
            print(
                f"  Fetching CTHRU data from Socrata "
                f"(attempt {attempt + 1}/{max_retries})..."
            )

            # Build URL with parameters to filter and increase limit
            # Socrata default limit is 1000, we need ALL records
            fetch_url = url
            params = []
            
            # Add year filter if provided (filter server-side)
            if year:
                params.append(f"year={year}")
            
            # Request ALL records - no limit
            # (Socrata will return everything available)
            params.append("$limit=999999")
            
            if params:
                fetch_url = url + "?" + "&".join(params)
            
            print("  Fetching from Socrata (this may take 10-30 sec)...")

            # Read CSV with pandas
            df = pd.read_csv(fetch_url, encoding="utf-8")

            # Check for required columns (actual CTHRU schema)
            required_cols = ["name_last", "name_first",
                             "department_division"]
            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                available = ", ".join(df.columns.tolist())
                raise ValueError(
                    f"Missing required columns: {missing}. "
                    f"Available columns: {available}"
                )

            # Combine name_last and name_first into employee_name
            df["employee_name"] = (
                df["name_last"].fillna("") + ", " +
                df["name_first"].fillna("")
            ).str.strip(", ")

            # Rename columns to match expected schema
            df = df.rename(columns={
                "department_division": "agency_name",
                "year": "calendar_year",
                "pay_total_actual": "total_pay",
                "pay_base_actual": "regular_pay",
                "pay_other_actual": "other_pay",
            })

            print(f"  Fetched {len(df)} total CTHRU records")

            # Filter to Legislature - check multiple possible values
            legislature_keywords = [
                "LEGISLATURE", "HOUSE", "SENATE",
                "GENERAL COURT", "REPRESENTATIVE"
            ]
            
            # Create mask for any matching keyword
            mask = df["agency_name"].str.upper().str.contains(
                "|".join(legislature_keywords), na=False, regex=True
            )
            
            if mask.sum() == 0:
                # No matches found - print diagnostic info
                print("  Warning: No Legislature records found!")
                print("  Sample department_division values:")
                sample_depts = df["agency_name"].value_counts().head(10)
                for dept, count in sample_depts.items():
                    print(f"    - {dept} ({count} records)")
            
            df = df[mask]
            print(f"  Filtered to {len(df)} Legislature records")

            # Filter to specific year if provided
            if year and "calendar_year" in df.columns:
                df = df[df["calendar_year"] == year]
                print(
                    f"  Filtered to {len(df)} records for year {year}"
                )

            # Cache the results
            if use_cache and len(df) > 0:
                df.to_csv(cache_path, index=False, encoding="utf-8")
                print(f"  Cached {len(df)} records to {cache_path}")

            return df

        except Exception as e:
            if attempt < max_retries - 1:
                delay = backoff_delays[attempt]
                print(f"  Error fetching CTHRU data: {e}")
                print(f"  Retrying in {delay}s...")
                time.sleep(delay)
            else:
                msg = (
                    f"  Failed to fetch CTHRU data after "
                    f"{max_retries} attempts"
                )
                print(msg)
                raise

    return pd.DataFrame()  # Should never reach here


def aggregate_cthru_by_person(
    df_raw: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Aggregate CTHRU data per person per year.

    Returns:
        (df_person, df_agencies) where:
        - df_person: aggregated by employee_name + calendar_year
        - df_agencies: aggregated by employee_name + calendar_year
          + agency_name
    """
    # Ensure numeric columns exist and are numeric
    pay_cols = ["regular_pay", "other_pay", "total_pay"]
    for col in pay_cols:
        if col not in df_raw.columns:
            df_raw[col] = 0.0
        else:
            df_raw[col] = pd.to_numeric(
                df_raw[col], errors="coerce"
            ).fillna(0.0)

    # Aggregate by person + year
    df_person = (
        df_raw.groupby(
            ["employee_name", "calendar_year"], as_index=False
        )
        .agg({
            "regular_pay": "sum",
            "other_pay": "sum",
            "total_pay": "sum",
        })
    )

    # Auxiliary table: agency-level aggregation (to detect
    # split-year records)
    df_agencies = (
        df_raw.groupby(
            ["employee_name", "calendar_year", "agency_name"],
            as_index=False
        )
        .agg({"total_pay": "sum"})
    )

    return df_person, df_agencies


def build_agency_summary(df_agencies: pd.DataFrame) -> dict[str, str]:
    """
    Build a summary of agencies per employee for display.

    Returns:
        Dict mapping employee_name to summary like
        "House($72,331); Senate($42,774)"
    """
    summary_map = {}

    for employee_name, group in df_agencies.groupby("employee_name"):
        parts = []
        for _, row in group.iterrows():
            agency = row["agency_name"]
            amount = row["total_pay"]
            parts.append(f"{agency}(${amount:,.0f})")
        summary_map[employee_name] = "; ".join(parts)

    return summary_map


def infer_year_from_csv(csv_path: str) -> int:
    """
    Infer the year from last_updated column in members.csv.
    Falls back to current year if not found.
    """
    try:
        df = pd.read_csv(csv_path)
        if "last_updated" in df.columns and len(df) > 0:
            # Parse first non-null last_updated value
            last_updated = df["last_updated"].dropna().iloc[0]
            # Expect format like "2025-10-30"
            year = datetime.fromisoformat(str(last_updated)).year
            return year
    except Exception as e:
        print(f"  Warning: Could not infer year from CSV: {e}")

    # Fallback to current year
    return datetime.now().year


def compute_variance_status(
    variance: float,
    cthru_total: float,
    model_total: float,
    agency_count: int,
    role_stipends_total: float = 0,
) -> str:
    """
    Determine variance status bucket using transparent,
    audit-friendly rules.

    Enhanced to detect annualization patterns and specific investigation
    tiers for better prioritization.

    Args:
        variance: model_total - cthru_total
        cthru_total: Total compensation from CTHRU
        model_total: Total compensation from model (annualized)
        agency_count: Number of distinct agencies employee appears in
        role_stipends_total: Total leadership/committee stipends

    Returns:
        Status string: OK, PARTIAL_OR_ROLE_CHANGE, LIKELY_ANNUALIZED,
        INVESTIGATE_PARTIAL_YEAR, INVESTIGATE_LEADERSHIP,
        INVESTIGATE_OVERPAYMENT, INVESTIGATE, or NO_MATCH
    """
    abs_var = abs(variance)

    if cthru_total == 0:
        return "NO_MATCH"
    elif abs_var < THRESHOLD_OK:
        return "OK"
    elif abs_var < THRESHOLD_PARTIAL or agency_count > 1:
        return "PARTIAL_OR_ROLE_CHANGE"
    else:
        # Large variance (≥ $10k) - check patterns
        cthru_pct = (cthru_total / model_total) * 100 if model_total > 0 else 0

        # If CTHRU is 75-90% of model, likely partial year rather than error
        if ANNUALIZATION_MIN_PCT <= cthru_pct <= ANNUALIZATION_MAX_PCT:
            return "LIKELY_ANNUALIZED"

        # Tier 1: Very low CTHRU (< 50%) - likely mid-year appointment/data issue
        elif cthru_pct < PARTIAL_YEAR_THRESHOLD:
            return "INVESTIGATE_PARTIAL_YEAR"

        # Tier 2: Overpayment (CTHRU > 110%) - payment timing issue
        elif cthru_pct > OVERPAYMENT_THRESHOLD:
            return "INVESTIGATE_OVERPAYMENT"

        # Tier 3: High leadership with 60-75% CTHRU - irregular payment schedule
        elif (
            role_stipends_total >= HIGH_LEADERSHIP_STIPEND
            and LEADERSHIP_HIGH_THRESHOLD <= cthru_pct < LEADERSHIP_LOW_THRESHOLD
        ):
            return "INVESTIGATE_LEADERSHIP"

        # Everything else
        else:
            return "INVESTIGATE"


def run_cthru_validation(
    cthru_csv_url: str,
    members_csv_path: str,
    year: int | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """
    Main validation function: fetch CTHRU data, join with model,
    compute variances.

    Args:
        cthru_csv_url: Socrata CSV endpoint URL
        members_csv_path: Path to out/members.csv
        year: Calendar year to validate (if None, infer from
              members.csv)
        use_cache: Whether to use cached CTHRU data (default True)

    Returns:
        Summary dict with validation statistics
    """
    print("\n" + "=" * 80)
    print("CTHRU VALIDATION")
    print("=" * 80)

    # 1. Infer year if not provided
    if year is None:
        year = infer_year_from_csv(members_csv_path)
    print(f"\nValidating compensation for year: {year}")
    
    if use_cache:
        print("Cache: Enabled (data cached for 24 hours)")
    else:
        print("Cache: Disabled (forcing fresh fetch)")

    # 2. Fetch and filter CTHRU data
    print("\n[1/4] Fetching CTHRU data...")
    df_raw = fetch_cthru_data(
        cthru_csv_url, year=year, use_cache=use_cache
    )

    if df_raw.empty:
        print("  No CTHRU data found; skipping validation.")
        return {
            "year": year,
            "rows_model": 0,
            "rows_matched": 0,
            "status_counts": {},
        }

    # 3. Aggregate CTHRU data
    print("\n[2/4] Aggregating CTHRU data...")
    df_cthru, df_agencies = aggregate_cthru_by_person(df_raw)
    print(f"  Aggregated to {len(df_cthru)} unique employees")

    # Build agency summary map
    agency_summary_map = build_agency_summary(df_agencies)

    # Count agencies per employee
    agency_counts = (
        df_agencies.groupby("employee_name")["agency_name"]
        .nunique()
        .to_dict()
    )

    # 4. Read model data
    print("\n[3/4] Loading model data...")
    df_model = pd.read_csv(members_csv_path)
    print(f"  Loaded {len(df_model)} members from model")

    # 5. Normalize names for joining
    print("\n[4/4] Joining and computing variances...")
    df_model["norm"] = df_model["name"].apply(norm_name)
    df_cthru["norm"] = df_cthru["employee_name"].apply(norm_name)

    # 6. Left join model to CTHRU
    df = df_model.merge(
        df_cthru[["norm", "regular_pay", "other_pay", "total_pay"]],
        on="norm",
        how="left",
        suffixes=("_model", "_cthru"),
    )

    # 7. Compute variance metrics
    df["cthru_total"] = df["total_pay"].fillna(0.0)
    df["regular_pay"] = df["regular_pay"].fillna(0.0)
    df["other_pay"] = df["other_pay"].fillna(0.0)
    df["variance"] = df["total_comp"] - df["cthru_total"]
    df["pct_diff"] = 100 * df["variance"] / df["cthru_total"].replace(
        0, 1
    )
    
    # Add annualization metrics
    df["cthru_pct_of_model"] = (
        df["cthru_total"] / df["total_comp"]
    ).replace([float('inf'), -float('inf')], 0) * 100
    df["months_equivalent"] = (
        df["cthru_total"] / df["total_comp"]
    ).replace([float('inf'), -float('inf')], 0) * 12

    # Add agency summary
    df["agencies_summary"] = df["name"].apply(
        lambda name: agency_summary_map.get(norm_name(name), "")
    )

    # Add agency count for status bucketing
    df["agency_count"] = df["name"].apply(
        lambda name: agency_counts.get(norm_name(name), 0)
    )

    # Compute status
    df["status"] = df.apply(
        lambda row: compute_variance_status(
            row["variance"],
            row["cthru_total"],
            row["total_comp"],
            row["agency_count"],
            row.get("role_stipends_total", 0),
        ),
        axis=1,
    )

    # 8. Add human-readable explanations
    def generate_explanation(row):
        status = row["status"]
        pct = row["cthru_pct_of_model"]
        months = row["months_equivalent"]

        if status == "OK":
            return "Within acceptable variance range"
        elif status == "PARTIAL_OR_ROLE_CHANGE":
            return "Partial year, role change, or multi-agency employment"
        elif status == "NO_MATCH":
            return "No CTHRU record found"
        elif status == "LIKELY_ANNUALIZED":
            return f"Likely annualization: {months:.1f} months paid vs 12-month model"
        elif status == "INVESTIGATE_PARTIAL_YEAR":
            return f"🔴 HIGH PRIORITY: Very low CTHRU ({pct:.0f}%) - likely mid-year appointment or data issue"
        elif status == "INVESTIGATE_OVERPAYMENT":
            return f"⚠️ MEDIUM PRIORITY: CTHRU exceeds model ({pct:.0f}%) - check payment timing or multi-year adjustment"
        elif status == "INVESTIGATE_LEADERSHIP":
            leadership = row.get("role_stipends_total", 0)
            return f"⚠️ MEDIUM PRIORITY: High leadership stipends (${leadership:,.0f}) at {pct:.0f}% - likely irregular payment schedule"
        else:  # INVESTIGATE (catch-all)
            return f"🔍 REVIEW NEEDED: Unexplained variance ({pct:.0f}% of model) - requires investigation"
    
    df["explanation"] = df.apply(generate_explanation, axis=1)
    
    # 9. Export variance details CSV
    output_cols = [
        "member_id", "name", "chamber", "district",
        "total_comp", "role_stipends_total", "expense_stipend",
        "base_salary",
        "cthru_total", "regular_pay", "other_pay",
        "variance", "pct_diff", 
        "cthru_pct_of_model", "months_equivalent",
        "status", "explanation",
        "agencies_summary",
    ]

    # Only include columns that exist in df
    export_cols = [c for c in output_cols if c in df.columns]
    df_export = df[export_cols].copy()

    variance_path = "out/cthru_variances.csv"
    Path(variance_path).parent.mkdir(parents=True, exist_ok=True)
    df_export.to_csv(variance_path, index=False)
    print(f"\n  ✓ Wrote {variance_path}")

    # 10. Compute aggregate metrics
    status_counts = df["status"].value_counts().to_dict()
    rows_matched = len(df[df["cthru_total"] > 0])

    abs_variances = df["variance"].abs()
    median_abs_var = abs_variances.median()
    p90_abs_var = abs_variances.quantile(0.90)

    # Top outliers (by absolute variance)
    df_outliers = df.nlargest(10, "variance", keep="all")[
        ["name", "variance", "status", "agencies_summary"]
    ]
    top_outliers = []
    for _, row in df_outliers.iterrows():
        top_outliers.append({
            "name": row["name"],
            "variance": float(row["variance"]),
            "status": row["status"],
            "notes": row["agencies_summary"] or "No agency split",
        })

    # 11. Chamber and role breakdowns
    variance_by_chamber = {}
    for chamber in ["House", "Senate"]:
        chamber_df = df[df["chamber"] == chamber]
        variance_by_chamber[chamber] = {
            "total_members": int(len(chamber_df)),
            "status_counts": chamber_df["status"].value_counts().to_dict(),
            "median_variance": float(chamber_df["variance"].abs().median()),
            "median_cthru_pct": float(chamber_df["cthru_pct_of_model"].median()),
        }
    
    variance_by_role = {
        "with_leadership": {},
        "no_leadership": {},
    }
    for has_leadership, label in [(True, "with_leadership"), (False, "no_leadership")]:
        role_df = df[df.get("has_stipend", False) == has_leadership] if "has_stipend" in df.columns else pd.DataFrame()
        if len(role_df) > 0:
            variance_by_role[label] = {
                "count": int(len(role_df)),
                "status_counts": role_df["status"].value_counts().to_dict(),
                "median_variance": float(role_df["variance"].abs().median()),
            }
    
    # Annualization analysis
    investigate_df = df[df["status"] == "INVESTIGATE"]
    annualized_df = df[df["status"] == "LIKELY_ANNUALIZED"]
    annualization_analysis = {
        "likely_annualized_count": int(len(annualized_df)),
        "median_cthru_pct_all": float(df["cthru_pct_of_model"].median()),
        "median_months_equivalent": float(df["months_equivalent"].median()),
        "hypothesis": f"Median {df['months_equivalent'].median():.1f} months suggests partial year (CTHRU through Oct vs 12-month model)",
    }
    
    # 12. Build summary JSON
    summary = {
        "year": year,
        "rows_model": len(df_model),
        "rows_matched": rows_matched,
        "status_counts": status_counts,
        "median_abs_variance": float(median_abs_var),
        "p90_abs_variance": float(p90_abs_var),
        "variance_by_chamber": variance_by_chamber,
        "variance_by_role": variance_by_role,
        "annualization_analysis": annualization_analysis,
        "top_outliers": top_outliers,
        "notes": {
            "thresholds": {
                "OK": f"Variance < ${THRESHOLD_OK:,}",
                "PARTIAL_OR_ROLE_CHANGE": (
                    f"Variance < ${THRESHOLD_PARTIAL:,} OR "
                    "employee appears in >1 agency"
                ),
                "LIKELY_ANNUALIZED": (
                    f"Variance ≥ ${THRESHOLD_PARTIAL:,} BUT "
                    f"CTHRU is {ANNUALIZATION_MIN_PCT}-{ANNUALIZATION_MAX_PCT}% of model "
                    "(partial year vs annualized model)"
                ),
                "INVESTIGATE_PARTIAL_YEAR": (
                    f"🔴 HIGH PRIORITY: CTHRU < {PARTIAL_YEAR_THRESHOLD}% "
                    "(likely mid-year appointment or data issue)"
                ),
                "INVESTIGATE_OVERPAYMENT": (
                    f"⚠️ MEDIUM PRIORITY: CTHRU > {OVERPAYMENT_THRESHOLD}% "
                    "(payment timing or multi-year adjustment)"
                ),
                "INVESTIGATE_LEADERSHIP": (
                    f"⚠️ MEDIUM PRIORITY: High leadership stipends (≥${HIGH_LEADERSHIP_STIPEND:,}) "
                    f"with CTHRU {LEADERSHIP_HIGH_THRESHOLD}-{LEADERSHIP_LOW_THRESHOLD}% "
                    "(irregular payment schedule)"
                ),
                "INVESTIGATE": "🔍 Other unexplained variance requiring investigation",
                "NO_MATCH": "No CTHRU record found for employee",
            },
            "common_variance_reasons": [
                "Partial year or chamber/role change "
                "(cash basis vs annualized model)",
                "Timing effects (stipends start on appointment date; "
                "expense allowances paid unevenly)",
                "Name mismatches (normalization + aliases required)",
            ],
        },
    }

    summary_path = "out/cthru_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"  ✓ Wrote {summary_path}")

    # 11. Print summary to console
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print(f"  Year: {year}")
    print(f"  Model records: {len(df_model)}")
    matched_pct = 100 * rows_matched / len(df_model)
    print(f"  Matched to CTHRU: {rows_matched} ({matched_pct:.1f}%)")
    print("\n  Status distribution:")
    for status, count in sorted(status_counts.items()):
        pct = 100 * count / len(df_model)
        print(f"    {status:25s}: {count:3d} ({pct:5.1f}%)")
    print(f"\n  Median absolute variance: ${median_abs_var:,.0f}")
    print(f"  P90 absolute variance:    ${p90_abs_var:,.0f}")
    print("=" * 80)

    return summary


if __name__ == "__main__":
    # Standalone test
    run_cthru_validation(
        cthru_csv_url=(
            "https://cthru.data.socrata.com/resource/9ttk-7vz6.csv"
        ),
        members_csv_path="out/members.csv",
        year=None,
    )
