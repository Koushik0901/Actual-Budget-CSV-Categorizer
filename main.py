#!/usr/bin/env python3
"""
Bank Statement CSV Categorizer
Processes exported bank CSV files and generates categorized CSV output
for Actual Budget import.

Usage:
    python main.py

Expected folder structure:
    input/
    ├── amex-cobalt/
    ├── cibc-credit/
    ├── cibc-chequing/
    └── cibc-savings/
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

from tqdm import tqdm

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.category_mapper import CategoryMapper
from core.csv_generator import CSVGenerator
from core.csv_statement_parser import CSVStatementParser


INPUT_FOLDER = project_root / "input"
OUTPUT_FOLDER = project_root / "output"
LOGS_FOLDER = project_root / "logs"
CONFIG_FOLDER = project_root / "config"


def setup_logging():
    """Setup logging configuration."""
    LOGS_FOLDER.mkdir(parents=True, exist_ok=True)

    log_file = LOGS_FOLDER / f'converter_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )

    return logging.getLogger(__name__)


def ensure_folders():
    """Ensure required folders exist."""
    for folder in [INPUT_FOLDER, OUTPUT_FOLDER, LOGS_FOLDER]:
        folder.mkdir(parents=True, exist_ok=True)


def get_account_folders():
    """
    Get account subfolders from input directory.
    Returns list of tuples: (account_name, folder_path)
    """
    accounts = []
    if not INPUT_FOLDER.exists():
        return accounts

    for item in INPUT_FOLDER.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            accounts.append((item.name, item))

    return sorted(accounts)


def get_csv_files_in_folder(folder_path: Path):
    """Get all CSV files in an account folder."""
    if not folder_path.exists():
        return []
    return sorted([p for p in folder_path.iterdir() if p.suffix.lower() == ".csv"])


def process_account_folder(
    account_name: str,
    folder_path: Path,
    statement_parser: CSVStatementParser,
    category_mapper: CategoryMapper,
    csv_generator: CSVGenerator,
    logger,
) -> Dict:
    """Process all CSV exports in an account folder."""
    logger.info(f"\nProcessing account: {account_name}")
    print(f"\n{'=' * 60}")
    print(f"Account: {account_name}")
    print(f"{'=' * 60}")

    csv_files = get_csv_files_in_folder(folder_path)
    if not csv_files:
        logger.info(f"  No CSV files found in {account_name}/")
        print("  No CSV files found")
        return {"processed": 0, "failed": 0, "transactions": []}

    logger.info(f"  Found {len(csv_files)} CSV file(s)")
    print(f"  Processing {len(csv_files)} CSV file(s)...")

    all_transactions = []
    success_count = 0
    failed_count = 0

    for csv_path in csv_files:
        logger.info(f"  Processing: {csv_path.name}")
        try:
            transactions = statement_parser.parse_csv(csv_path, account_name)
            if not transactions:
                logger.warning(f"    No transactions parsed from: {csv_path.name}")
                failed_count += 1
                continue

            logger.info(f"    Extracted {len(transactions)} transactions")
            all_transactions.extend(transactions)
            success_count += 1
        except Exception as e:
            logger.error(f"    Error processing {csv_path.name}: {e}", exc_info=True)
            failed_count += 1

    if all_transactions:
        logger.info(f"  Categorizing {len(all_transactions)} transactions")
        all_transactions = category_mapper.categorize_transactions(all_transactions)

        category_stats = category_mapper.get_category_stats(all_transactions)
        logger.info(f"  Category breakdown: {category_stats}")

        csv_path = csv_generator.generate_csv(all_transactions, account_name)
        if csv_path:
            logger.info(f"  Generated CSV: {csv_path}")
            total_amount = sum(t.amount for t in all_transactions)
            print(f"  [OK] Generated: {Path(csv_path).name}")
            print(f"    Transactions: {len(all_transactions)}")
            print(f"    Net amount: ${total_amount:,.2f}")

    return {
        "processed": success_count,
        "failed": failed_count,
        "transactions": all_transactions,
    }


def print_summary(results: Dict):
    """Print processing summary."""
    print("\n" + "=" * 60)
    print("PROCESSING SUMMARY")
    print("=" * 60)

    total_csvs = 0
    total_transactions = 0

    for account_name, result in sorted(results.items()):
        if result["processed"] > 0 or result["failed"] > 0:
            print(f"\n{account_name}:")
            print(f"  CSVs processed: {result['processed']}")
            if result["failed"] > 0:
                print(f"  CSVs failed: {result['failed']}")
            print(f"  Transactions: {len(result['transactions'])}")
            total_csvs += result["processed"] + result["failed"]
            total_transactions += len(result["transactions"])

    print(f"\n{'=' * 60}")
    print(f"Total CSV files processed: {total_csvs}")
    print(f"Total transactions: {total_transactions}")
    print(f"{'=' * 60}")
    print(f"\nOutput files location: {OUTPUT_FOLDER}")


def main():
    """Main entry point."""
    print("=" * 60)
    print("Bank Statement CSV Categorizer")
    print("Adds category tags and normalizes amounts for Actual Budget")
    print("=" * 60)
    print()

    ensure_folders()
    logger = setup_logging()

    logger.info("Starting Bank Statement CSV Categorizer")
    logger.info(f"Input folder: {INPUT_FOLDER}")
    logger.info(f"Output folder: {OUTPUT_FOLDER}")

    config_path = CONFIG_FOLDER / "categories.yaml"
    statement_parser = CSVStatementParser()
    category_mapper = CategoryMapper(str(config_path))
    csv_generator = CSVGenerator(str(OUTPUT_FOLDER))

    account_folders = get_account_folders()
    if not account_folders:
        logger.warning("No account folders found in input/")
        print("\nNo account folders found!")
        print("\nCreate account subfolders in input/, then place bank-exported CSV files:")
        print("  input/amex-cobalt/")
        print("  input/cibc-credit/")
        print("  input/cibc-chequing/")
        print("  input/cibc-savings/")
        print("  input/wealthsimple-tfsa/")
        return

    logger.info(f"Found {len(account_folders)} account folder(s)")
    print(f"Found {len(account_folders)} account folder(s):")
    for account_name, _ in account_folders:
        print(f"  - {account_name}/")
    print()

    results = {}
    for account_name, folder_path in tqdm(account_folders, desc="Processing accounts", unit="account"):
        results[account_name] = process_account_folder(
            account_name=account_name,
            folder_path=folder_path,
            statement_parser=statement_parser,
            category_mapper=category_mapper,
            csv_generator=csv_generator,
            logger=logger,
        )

    print_summary(results)
    logger.info("Processing complete")


if __name__ == "__main__":
    main()
