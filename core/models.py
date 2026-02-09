"""
Core data models.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict


@dataclass
class Transaction:
    """Represents a single bank transaction."""

    date: datetime
    payee: str
    amount: float  # Positive for inflow, negative for outflow
    raw_description: str = ""
    category: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Date": self.date.strftime("%Y-%m-%d"),
            "Payee": self.payee,
            "Amount": self.amount,
            "Category": self.category,
            "Notes": self.notes if self.notes else self.category,
        }
