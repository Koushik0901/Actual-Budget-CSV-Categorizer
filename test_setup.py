#!/usr/bin/env python3
"""
Quick validation script for the CSV categorizer implementation.
"""

import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("Testing Bank Statement CSV Categorizer")
print("=" * 60)

print("\n1. Testing module imports...")
try:
    from core.models import Transaction
    from core import CategoryMapper, CSVGenerator, CSVStatementParser
    print("   [OK] Imports successful")
except Exception as exc:
    print(f"   [ERROR] Import error: {exc}")
    sys.exit(1)

print("\n2. Checking folder structure...")
required_folders = ["input", "output", "logs", "config", "core"]
for folder in required_folders:
    folder_path = project_root / folder
    if folder_path.exists():
        print(f"   [OK] {folder}/")
    else:
        print(f"   [MISSING] {folder}/")

print("\n3. Checking category configuration...")
config_path = project_root / "config" / "categories.yaml"
try:
    mapper = CategoryMapper(str(config_path))
    print(f"   [OK] Loaded categories: {len(mapper.categories)}")
except Exception as exc:
    print(f"   [ERROR] Config load failed: {exc}")
    sys.exit(1)

print("\n4. Testing category mapping...")
sample_transactions = [
    Transaction(datetime.now(), "WALMART #1234", -45.67, "WALMART #1234"),
    Transaction(datetime.now(), "UBER EATS", -23.99, "UBER EATS"),
    Transaction(datetime.now(), "PAYMENT THANK YOU", 300.00, "PAYMENT THANK YOU"),
    Transaction(datetime.now(), "ELECTRONIC FUNDS TRANSFER DEPOSIT AE/EI", 1186.00, "DEPOSIT AE/EI"),
]

categorized = mapper.categorize_transactions(sample_transactions)
for tx in categorized:
    print(f"   {tx.payee:45} -> {tx.category}")

print("\n5. Testing CSV generation...")
csv_gen = CSVGenerator(str(project_root / "output"))
csv_path = csv_gen.generate_csv(categorized, "test-account")
if csv_path:
    print(f"   [OK] CSV generated: {csv_path}")
    Path(csv_path).unlink(missing_ok=True)
else:
    print("   [ERROR] CSV generation failed")
    sys.exit(1)

print("\n6. Testing CSV statement parser on sample exports...")
parser = CSVStatementParser()
sample_files = [
    project_root / "input" / "amex-cobalt" / "24 December 2025.csv",
    project_root / "input" / "cibc-credit" / "cibc credit sept 2025 to feb 2026.csv",
    project_root / "input" / "cibc-chequing" / "cibc chequing sept 2024 - feb 2025.csv",
    project_root / "input" / "Weathsimple-TFSA" / "TFSA-monthly-statement-transactions-HQ6R97BK0CAD-2025-10-01.csv",
]

for sample_file in sample_files:
    if sample_file.exists():
        account_name = sample_file.parent.name
        txs = parser.parse_csv(sample_file, account_name)
        print(f"   [OK] {sample_file.name}: {len(txs)} transaction(s)")
    else:
        print(f"   [INFO] Sample not found: {sample_file.name}")

print("\n" + "=" * 60)
print("Validation complete")
print("Run `python main.py` to process account CSV files.")
print("=" * 60)
