"""Base classes and data structures for visualizations."""

from abc import ABC, abstractmethod
from typing import Optional


class DataContext:
    """Holds data needed for visualizations."""

    def __init__(
        self,
        members: list[dict],
        leadership_roles: list[dict],
        committee_roles: dict[str, list[str]],
        computed_rows: list[dict],
        earmarks_by_member: Optional[dict[str, list[dict]]] = None,
    ):
        self.members = members
        self.leadership_roles = leadership_roles
        self.committee_roles = committee_roles
        self.computed_rows = computed_rows
        self.earmarks_by_member = earmarks_by_member or {}


class Visualization(ABC):
    """Abstract base class for visualizations."""

    name: str = "Unnamed Visualization"
    description: str = "No description provided"
    category: str = "General"

    @abstractmethod
    def run(self, context: DataContext) -> None:
        """Run the visualization with the provided data context."""
        raise NotImplementedError

    def format_currency(self, amount: Optional[float]) -> str:
        """Format a number as currency."""
        if amount is None:
            return "N/A"
        return f"${amount:,.2f}"

    def format_number(self, num: Optional[float]) -> str:
        """Format a number with commas and two decimal places."""
        if num is None:
            return "N/A"
        return f"{num:,.2f}"
