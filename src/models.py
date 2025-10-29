from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


API_BASE = "https://malegislature.gov/api"
CYCLE_CONFIG: dict[str, str | int] = {
    "cycle": "2025-2026",
    "effective_date": "2025-01-01",
    "base_salary": 82_044,
    # https://www.lowellsun.com/2025/04/28/beacon-hill-roll-call-breaking-down-salaries-benefits-of-state-reps/
    "expense_bands": {"LE50": 15_000, "GT50": 20_000},
    # https://malegislature.gov/Laws/GeneralLaws/PartI/TitleI/Chapter3/Section9C
    "stipends": {
        "SPEAKER": 80_000,
        "SENATE_PRESIDENT": 80_000,
        "MAJORITY_LEADER": 60_000,
        "MINORITY_LEADER": 60_000,
        "PRESIDENT_PRO_TEMPORE": 50_000,
        "SPEAKER_PRO_TEMPORE": 50_000,
        "WAYS_MEANS_CHAIR": 65_000,
        "WAYS_MEANS_VICECHAIR": 30_000,
        "COMMITTEE_CHAIR_TIER_A": 30_000,
        "COMMITTEE_CHAIR_TIER_B": 15_000,
        "COMMITTEE_VICECHAIR": 5_200,
        "WHIP": 35_000,
        "ASST_MAJ_WHIP": 35_000,
        "ASST_MIN_WHIP": 35_000,
    },
    # https://malegislature.gov/Laws/GeneralLaws/PartI/TitleI/Chapter3/Section9b
}
STATE_HOUSE_LATLON: tuple[float, float] = (42.3570, -71.0630)
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
TIER_OVERRIDES: dict[str, str] = {
    "House Committee on Ways and Means": "WAYS_MEANS_CHAIR",
    "Senate Committee on Ways and Means": "WAYS_MEANS_CHAIR",
    "House Committee on Rules": "COMMITTEE_CHAIR_TIER_A",
    "Senate Committee on Rules": "COMMITTEE_CHAIR_TIER_A",
}
HOME_LOCALITY_OVERRIDES: dict[str, str] = {}
PAYROLL_ACTUAL: dict[str, int] = {}
GEOCODE_CACHE: dict[str, tuple[float, float]] = {}


@dataclass(frozen=True)
class Chamber:
    senate: Literal["senate"] = "senate"
    house: Literal["house"] = "house"


@dataclass
class ShapefilePaths:
    chamber: Chamber
    filepath: Path


@dataclass
class CycleConfig:
    cycle: str
    effective_date: str
    base_salary: int
    expense_bands: dict[str, int]
    stipends: CycleStipends


@dataclass
class CycleStipends:
    speaker: int
    senate_president: int
    majority_leader: int
    minority_leader: int
    president_pro_tempore: int
    speaker_pro_tempore: int
    ways_means_chair: int
    ways_means_vicechair: int
    committee_chair_tier_a: int
    committee_chair_tier_b: int
    committee_vicechair: int
    whip: int
    asst_maj_whip: int
    asst_min_whip: int
