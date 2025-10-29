from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


API_BASE = "https://malegislature.gov/api"
STATE_HOUSE_LATLON: tuple[float, float] = (42.3570, -71.0630)


def load_cycle_config(cycle: str = "2025-2026") -> dict:
    """Load cycle configuration from JSON file."""
    config_path = (
        Path(__file__).parent.parent / "data" / "cycle" / f"{cycle}.json"
    )
    if not config_path.exists():
        raise FileNotFoundError(f"Cycle config not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


# Load the current cycle configuration
CYCLE_CONFIG = load_cycle_config()


# Leadership role mapping
ROLE_MAP: dict[str, str] = {
    "Speaker of the House": "SPEAKER",
    "President of the Senate": "SENATE_PRESIDENT",
    "Majority Leader": "MAJORITY_LEADER",
    "Minority Leader": "MINORITY_LEADER",
    "President Pro Tempore": "PRESIDENT_PRO_TEMPORE",
    "Speaker Pro Tempore": "SPEAKER_PRO_TEMPORE",
    "Majority Whip": "WHIP",
    "Minority Whip": "WHIP",
    "Assistant Majority Whip": "ASST_MAJ_WHIP",
    "Assistant Minority Whip": "ASST_MIN_WHIP",
    "Chair": "COMMITTEE_CHAIR_TIER_A",
    "Vice Chair": "COMMITTEE_VICECHAIR",
}


# Committee chair tier overrides (Tier A gets higher stipend)
# Ways & Means is special ($65k), other Tier A get $30k, Tier B get $15k
TIER_OVERRIDES: dict[str, str] = {
    # Special: Ways & Means chairs
    "House Committee on Ways and Means": "WAYS_MEANS_CHAIR",
    "Senate Committee on Ways and Means": "WAYS_MEANS_CHAIR",
    # Tier A committees ($30k for chairs)
    "House Committee on Rules": "COMMITTEE_CHAIR_TIER_A",
    "Senate Committee on Rules": "COMMITTEE_CHAIR_TIER_A",
    "Joint Committee on Rules": "COMMITTEE_CHAIR_TIER_A",
    "House Committee on Steering, Policy and Scheduling": (
        "COMMITTEE_CHAIR_TIER_A"
    ),
    "Senate Committee on Steering and Policy": "COMMITTEE_CHAIR_TIER_A",
    "House Committee on Bonding, Capital Expenditures and State Assets": (
        "COMMITTEE_CHAIR_TIER_A"
    ),
    "Senate Committee on Bonding, Capital Expenditures and State Assets": (
        "COMMITTEE_CHAIR_TIER_A"
    ),
    "Joint Committee on Ethics": "COMMITTEE_CHAIR_TIER_A",
    "Joint Committee on Global Warming and Climate Change": (
        "COMMITTEE_CHAIR_TIER_A"
    ),
    "Joint Committee on Health Care Financing": "COMMITTEE_CHAIR_TIER_A",
    "Joint Committee on Post Audit and Oversight": "COMMITTEE_CHAIR_TIER_A",
    "Joint Committee on Revenue": "COMMITTEE_CHAIR_TIER_A",
    "Joint Committee on Transportation": "COMMITTEE_CHAIR_TIER_A",
}


# Vice chair tier overrides (Tier A vice chairs - per MA Almanac)
# Note: Vice chair Tier A list differs from chair Tier A list
VICECHAIR_TIER_A_COMMITTEES = {
    "Bonding",
    "Economic Development",
    "Education",
    "Financial Services",
    "Health Care Financing",
    "Judiciary",
    "Post-Audit",
    "Post Audit",  # Alternative spelling
    "Revenue",
    "Rules",
    "State Administration",
    "Steering",
    "Telecommunications",
    "Third Reading",
    "Transportation",
}


# Runtime overrides and caches
HOME_LOCALITY_OVERRIDES: dict[str, str] = {}
PAYROLL_ACTUAL: dict[str, int] = {}
GEOCODE_CACHE: dict[str, tuple[float, float]] = {}


@dataclass(frozen=True)
class Chamber:
    senate: Literal["senate"] = "senate"
    house: Literal["house"] = "house"
