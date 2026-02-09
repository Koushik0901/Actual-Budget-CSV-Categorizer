"""
CSV Statement Parser
Parses exported bank CSV files into normalized Transaction objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import re

import pandas as pd
from dateutil import parser as date_parser

from core.models import Transaction


@dataclass(frozen=True)
class ColumnMapping:
    """Resolved source columns used to build transactions."""

    date: str
    description: str
    transaction_code: Optional[str] = None
    amount: Optional[str] = None
    debit: Optional[str] = None
    credit: Optional[str] = None


class CSVStatementParser:
    """Parser for bank-exported CSV files (Amex, CIBC, Wealthsimple, others)."""

    DATE_COLUMNS = ("date", "transaction date", "posted date", "posting date", "trans date")
    DESCRIPTION_COLUMNS = ("description", "merchant", "payee", "details", "memo")
    TRANSACTION_CODE_COLUMNS = ("transaction", "type", "activity", "code")
    AMOUNT_COLUMNS = ("amount", "transaction amount", "value")
    DEBIT_COLUMNS = ("debit", "withdrawal", "money out", "charges")
    CREDIT_COLUMNS = ("credit", "deposit", "money in", "payment", "refund")
    INVESTMENT_IGNORE_CODES = {"BUY", "SELL", "LOAN", "RECALL"}
    INVESTMENT_CONTRIBUTION_CODES = {"CONT"}

    def parse_csv(self, csv_path: Path, account_name: str) -> List[Transaction]:
        """
        Parse one CSV file into a list of transactions.

        Args:
            csv_path: Path to source CSV
            account_name: Account folder name used for sign conventions
        """
        df = self._read_csv(csv_path)
        if df.empty:
            return []

        mapping = self._resolve_columns(df)
        if not mapping:
            raise ValueError(f"Could not map required columns in file: {csv_path}")

        is_credit_account = self._is_credit_account(account_name)
        is_investment_account = self._is_investment_account(account_name)

        if is_investment_account and mapping.transaction_code:
            return self._parse_investment_csv(df, mapping)

        transactions: List[Transaction] = []

        for _, row in df.iterrows():
            date_value = self._parse_date(str(row.get(mapping.date, "")).strip())
            if not date_value:
                continue

            description = str(row.get(mapping.description, "")).strip()
            if not description:
                continue

            amount = self._parse_amount_from_row(row, mapping, is_credit_account)
            if amount is None:
                continue
            transaction_code = (
                str(row.get(mapping.transaction_code, "")).strip()
                if mapping.transaction_code
                else ""
            )
            raw_description = description
            if transaction_code:
                raw_description = f"{transaction_code} {description}"

            cleaned_payee = self._clean_payee(description)
            transactions.append(
                Transaction(
                    date=date_value,
                    payee=cleaned_payee,
                    amount=amount,
                    raw_description=raw_description,
                )
            )

        return transactions

    def _parse_investment_csv(self, df: pd.DataFrame, mapping: ColumnMapping) -> List[Transaction]:
        """
        Parse investment exports in simplified mode:
        - Keep contributions as explicit inflows
        - Ignore internal trade mechanics (BUY/SELL/LOAN/RECALL)
        - Aggregate remaining non-contribution cash effects into one Investment Profit/Loss row
        """
        transactions: List[Transaction] = []
        pnl_total = 0.0
        pnl_date: Optional[datetime] = None

        for _, row in df.iterrows():
            date_value = self._parse_date(str(row.get(mapping.date, "")).strip())
            if not date_value:
                continue

            description = str(row.get(mapping.description, "")).strip()
            if not description:
                continue

            amount = self._parse_amount_from_row(row, mapping, is_credit_account=False)
            if amount is None or amount == 0.0:
                continue

            code = (
                str(row.get(mapping.transaction_code, "")).strip().upper()
                if mapping.transaction_code
                else ""
            )
            raw_description = f"{code} {description}".strip()

            if code in self.INVESTMENT_IGNORE_CODES:
                continue

            if code in self.INVESTMENT_CONTRIBUTION_CODES:
                transactions.append(
                    Transaction(
                        date=date_value,
                        payee="Wealthsimple Contribution",
                        amount=amount,
                        raw_description=raw_description,
                    )
                )
                continue

            pnl_total += amount
            if pnl_date is None or date_value > pnl_date:
                pnl_date = date_value

        if abs(pnl_total) > 1e-9:
            transactions.append(
                Transaction(
                    date=pnl_date or datetime.now(),
                    payee="Investment Profit/Loss",
                    amount=round(pnl_total, 2),
                    raw_description="INVESTMENT_PNL_SUMMARY",
                )
            )

        return sorted(transactions, key=lambda t: t.date)

    def _read_csv(self, csv_path: Path) -> pd.DataFrame:
        """Read CSV with support for files that may not include headers."""
        df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
        df.columns = [str(c).strip() for c in df.columns]

        if self._looks_like_header(df.columns):
            return df

        # Re-read as headerless (CIBC export format)
        headerless = pd.read_csv(csv_path, dtype=str, keep_default_na=False, header=None)
        headerless = headerless.fillna("")
        headerless.columns = self._default_columns_for_width(headerless.shape[1])
        return headerless

    def _default_columns_for_width(self, width: int) -> List[str]:
        """Fallback column names for headerless exports."""
        if width == 4:
            return ["Date", "Description", "Debit", "Credit"]
        if width == 5:
            return ["Date", "Description", "Debit", "Credit", "Reference"]
        return [f"Column{i + 1}" for i in range(width)]

    def _looks_like_header(self, columns: List[str]) -> bool:
        """Heuristic to determine whether first row was parsed as header."""
        if len(columns) > 0 and self._parse_date(str(columns[0]).strip()):
            # Headerless exports often start with a date in first column.
            return False

        normalized = [self._normalize_text(c) for c in columns]
        date_hits = sum(1 for name in normalized if any(token in name for token in self.DATE_COLUMNS))
        descriptor_hits = sum(
            1
            for name in normalized
            if any(
                token in name
                for token in (
                    *self.DESCRIPTION_COLUMNS,
                    *self.AMOUNT_COLUMNS,
                    *self.DEBIT_COLUMNS,
                    *self.CREDIT_COLUMNS,
                )
            )
        )
        return date_hits >= 1 and descriptor_hits >= 1

    def _resolve_columns(self, df: pd.DataFrame) -> Optional[ColumnMapping]:
        """Resolve source columns by fuzzy matching expected names."""
        columns = list(df.columns)
        normalized: Dict[str, str] = {self._normalize_text(c): c for c in columns}

        date_col = self._find_first_match(normalized, self.DATE_COLUMNS) or columns[0]
        description_col = self._find_first_match(normalized, self.DESCRIPTION_COLUMNS)
        transaction_code_col = self._find_first_match(normalized, self.TRANSACTION_CODE_COLUMNS)
        amount_col = self._find_first_match(normalized, self.AMOUNT_COLUMNS)
        debit_col = self._find_first_match(normalized, self.DEBIT_COLUMNS)
        credit_col = self._find_first_match(normalized, self.CREDIT_COLUMNS)

        if not description_col:
            # Headerless fallback: assume second column is description if present
            if len(columns) >= 2:
                description_col = columns[1]

        if not description_col:
            return None

        if not amount_col and not (debit_col or credit_col):
            # Final fallback: assume debit/credit layout if enough columns
            if len(columns) >= 4:
                debit_col = columns[2]
                credit_col = columns[3]
            else:
                return None

        return ColumnMapping(
            date=date_col,
            description=description_col,
            transaction_code=transaction_code_col,
            amount=amount_col,
            debit=debit_col,
            credit=credit_col,
        )

    def _find_first_match(self, normalized_columns: Dict[str, str], candidates: tuple[str, ...]) -> Optional[str]:
        for normalized_name, original_name in normalized_columns.items():
            if any(candidate in normalized_name for candidate in candidates):
                return original_name
        return None

    def _parse_amount_from_row(
        self,
        row: pd.Series,
        mapping: ColumnMapping,
        is_credit_account: bool,
    ) -> Optional[float]:
        """Normalize amount signs to Actual format: expense negative, inflow positive."""
        if mapping.amount:
            raw_amount = str(row.get(mapping.amount, "")).strip()
            if raw_amount == "":
                return None

            amount = self._clean_amount(raw_amount)
            if is_credit_account:
                # Credit card exports typically use positive charges and negative payments.
                amount = -amount
            return amount

        debit = self._clean_amount(str(row.get(mapping.debit, "")).strip()) if mapping.debit else 0.0
        credit = self._clean_amount(str(row.get(mapping.credit, "")).strip()) if mapping.credit else 0.0

        if debit == 0.0 and credit == 0.0:
            return None

        # Standard bank CSV: debit is money out, credit is money in.
        return credit - debit

    def _clean_amount(self, amount_str: str) -> float:
        """Parse money amounts with symbols/commas/parentheses and CR/DR markers."""
        if not amount_str:
            return 0.0

        cleaned = re.sub(r"[$€£¥,\s]", "", amount_str)
        is_negative = False

        if cleaned.startswith("(") and cleaned.endswith(")"):
            is_negative = True
            cleaned = cleaned[1:-1]
        elif cleaned.lower().endswith("dr"):
            is_negative = True
            cleaned = cleaned[:-2]
        elif cleaned.lower().endswith("cr"):
            cleaned = cleaned[:-2]
        elif cleaned.startswith("-"):
            is_negative = True
            cleaned = cleaned[1:]

        try:
            amount = float(cleaned)
        except ValueError:
            return 0.0

        return -amount if is_negative else amount

    def _clean_payee(self, text: str) -> str:
        """Normalize whitespace and preserve readable casing."""
        text = " ".join(text.split())
        if not text:
            return ""
        return text.title()

    def _parse_date(self, text: str) -> Optional[datetime]:
        """Parse many bank date formats safely."""
        if not text:
            return None
        try:
            return date_parser.parse(text, dayfirst=False, fuzzy=True)
        except (ValueError, TypeError, OverflowError):
            return None

    def _normalize_text(self, text: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", " ", text.lower())
        return " ".join(normalized.split())

    def _is_credit_account(self, account_name: str) -> bool:
        account = account_name.lower()
        return any(token in account for token in ("amex", "credit", "visa", "mastercard"))

    def _is_investment_account(self, account_name: str) -> bool:
        account = account_name.lower()
        return any(
            token in account
            for token in ("wealthsimple", "weathsimple", "tfsa", "rrsp", "investment", "brokerage")
        )
