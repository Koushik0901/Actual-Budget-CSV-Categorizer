#!/usr/bin/env python3
"""
Create/update Actual Budget categories from config/categories.yaml.

This script avoids creating categories manually one by one in Actual.

Usage example:
    python sync_actual_categories.py \
      --base-url http://localhost:5006 \
      --password "<ACTUAL_SERVER_PASSWORD>" \
      --file "<YOUR_BUDGET_FILE>"
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List

import yaml

CATEGORY_GROUP_MAP: Dict[str, str] = {
    "Grocery": "Food",
    "Ordering In / Delivery": "Food",
    "Dining Out": "Food",
    "Subscriptions": "Bills",
    "Fuel / Gas": "Transport",
    "Transit and Parking": "Transport",
    "Car Share and Rentals": "Transport",
    "Laundry and Vending": "Living",
    "Shopping Retail": "Shopping",
    "Shopping Home": "Shopping",
    "Outdoor Activities and Tickets": "Entertainment",
    "Uber Ride and Lyft": "Transport",
    "Wifi and Phone Bill": "Bills",
    "Travel and Flights": "Travel",
    "Fees and Charges": "Banking",
    "Payment": "Transfers and Payments",
    "Transfer In": "Transfers and Payments",
    "Transfer Out": "Transfers and Payments",
    "Uncategorized": "Other",
    "Income": "Income",
}


def load_category_names(config_path: Path, include_special: bool) -> List[str]:
    with open(config_path, "r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    names: List[str] = []
    categories = config.get("categories", {})
    for item in categories.values():
        category_name = str(item.get("name", "")).strip()
        if category_name:
            names.append(category_name)

    if include_special:
        names.extend(["Payment", "Transfer In", "Transfer Out", "Income", "Uncategorized"])

    # Keep order, remove duplicates
    seen = set()
    deduped: List[str] = []
    for name in names:
        if name not in seen:
            seen.add(name)
            deduped.append(name)

    return deduped


def resolve_group(category_name: str) -> str:
    return CATEGORY_GROUP_MAP.get(category_name, "Expenses")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync categories from config/categories.yaml to Actual Budget."
    )
    parser.add_argument(
        "--config",
        default="config/categories.yaml",
        help="Path to categories YAML file (default: config/categories.yaml).",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("ACTUAL_BASE_URL", "http://localhost:5006"),
        help="Actual server URL (default: ACTUAL_BASE_URL or http://localhost:5006).",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("ACTUAL_PASSWORD"),
        help="Actual server password (or set ACTUAL_PASSWORD).",
    )
    parser.add_argument(
        "--file",
        default=os.getenv("ACTUAL_FILE"),
        help="Budget file ID/name in Actual (or set ACTUAL_FILE).",
    )
    parser.add_argument(
        "--encryption-password",
        default=os.getenv("ACTUAL_ENCRYPTION_PASSWORD"),
        help="Encryption password if your budget file uses encryption.",
    )
    parser.add_argument(
        "--data-dir",
        default=".actual-cache",
        help="Directory for Actual local cache (default: .actual-cache).",
    )
    parser.add_argument(
        "--include-special",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include Payment/Transfer/Income/Uncategorized helper categories (default: enabled).",
    )
    parser.add_argument(
        "--list-files",
        action="store_true",
        help="List available Actual budget files and exit.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        from actual import Actual
        from actual.queries import get_category, get_or_create_category
    except ImportError:
        print("Missing dependency: actualpy")
        print("Install it with: pip install actualpy")
        return 1

    config_path = Path(args.config)

    if args.list_files:
        with Actual(
            base_url=args.base_url,
            password=args.password,
            data_dir=args.data_dir,
        ) as actual:
            files = actual.list_user_files().data
            if not files:
                print("No budget files found on server.")
                return 1
            print("Available budget files:")
            for item in files:
                if item.deleted == 0:
                    print(f"- name: {item.name}")
                    print(f"  file_id: {item.file_id}")
                    print(f"  group_id: {item.group_id}")
        return 0

    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        return 1

    if not args.password:
        print("Missing --password (or ACTUAL_PASSWORD).")
        return 1

    if not args.file:
        print("Missing --file (or ACTUAL_FILE).")
        print("Use --list-files to see valid budget names/ids from your Actual server.")
        return 1

    if args.file.lower().endswith(".csv") or "\\" in args.file or "/" in args.file:
        print("Invalid --file value: looks like a local CSV path.")
        print("--file must be your Actual budget name, file_id, or group_id from the server.")
        print("Run with --list-files to find valid values.")
        return 1

    categories = load_category_names(config_path, include_special=args.include_special)
    if not categories:
        print("No categories found to sync.")
        return 1

    created = 0
    skipped = 0

    with Actual(
        base_url=args.base_url,
        password=args.password,
        file=args.file,
        encryption_password=args.encryption_password,
        data_dir=args.data_dir,
    ) as actual:
        for category_name in categories:
            existing = get_category(actual.session, category_name)
            if existing:
                skipped += 1
                continue

            group_name = resolve_group(category_name)
            get_or_create_category(actual.session, category_name, group_name)
            created += 1
            print(f"[CREATED] {category_name} -> {group_name}")

        if created > 0:
            actual.commit()

    print(f"Done. Created: {created}, Existing: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
