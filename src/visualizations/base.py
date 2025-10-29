from abc import ABC, abstractmethod
from typing import Optional


class DataContext:
    def __init__(
        self,
        members: list[dict],
        leadership_roles: list[dict],
        committee_roles: dict[str, list[str]],
        computed_rows: list[dict],
    ):
        self.members = members
        self.leadership_roles = leadership_roles
        self.committee_roles = committee_roles
        self.computed_rows = computed_rows


class Visualization(ABC):
    name: str = "Unnamed Visualization"
    description: str = "No description provided"
    category: str = "General"

    @abstractmethod
    def run(self, context: DataContext) -> None:
        raise NotImplementedError

    def format_currency(self, amount: Optional[float]) -> str:
        if amount is None:
            return "N/A"
        return f"${amount:,.2f}"

    def format_number(self, num: Optional[float]) -> str:
        if num is None:
            return "N/A"
        return f"{num:,.2f}"
