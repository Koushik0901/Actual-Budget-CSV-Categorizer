#!/usr/bin/env python3
"""
Comprehensive test suite for Bank Statement CSV Categorizer.
"""

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("COMPREHENSIVE TEST - BANK STATEMENT CSV CATEGORIZER")
print("=" * 70)

tests_passed = 0
tests_failed = 0


def test_section(name):
    print(f"\n{name}")
    print("-" * 70)


def test_assert(condition, message):
    global tests_passed, tests_failed
    if condition:
        print(f"  [PASS] {message}")
        tests_passed += 1
        return True
    print(f"  [FAIL] {message}")
    tests_failed += 1
    return False


test_section("TEST 1: Module Imports")
try:
    from core.models import Transaction
    from core import CategoryMapper, CSVGenerator, CSVStatementParser
    test_assert(True, "Imported core modules")
except Exception as exc:
    test_assert(False, f"Import failure: {exc}")
    print("\nCannot continue without imports.")
    sys.exit(1)


test_section("TEST 2: Transaction Dataclass")
t = Transaction(datetime(2026, 1, 10), "Walmart", -25.33, "WALMART #1", "Grocery")
t_dict = t.to_dict()
test_assert(t_dict["Date"] == "2026-01-10", "Date serialized as YYYY-MM-DD")
test_assert(t_dict["Payee"] == "Walmart", "Payee serialized")
test_assert(t_dict["Amount"] == -25.33, "Amount serialized")
test_assert(t_dict["Category"] == "Grocery", "Category serialized")
test_assert(t_dict["Notes"] == "Grocery", "Notes mapped from category")


test_section("TEST 3: Category Mapping Quality")
config_path = project_root / "config" / "categories.yaml"
mapper = CategoryMapper(str(config_path))

samples = [
    Transaction(datetime.now(), "WAL-MART SUPERCENTRE#11", -67.28, "WAL-MART SUPERCENTRE#11"),
    Transaction(datetime.now(), "UBER EATS HTTPS://HELP.UB", -36.50, "UBER EATS"),
    Transaction(datetime.now(), "LYFT *RIDE SAT 4PM", -13.93, "LYFT *RIDE SAT 4PM"),
    Transaction(datetime.now(), "PAYMENT THANK YOU", 244.88, "PAYMENT THANK YOU"),
    Transaction(datetime.now(), "ELECTRONIC FUNDS TRANSFER DEPOSIT AE/EI", 1186.00, "DEPOSIT AE/EI"),
    Transaction(datetime.now(), "INTERNET BANKING INTERNET TRANSFER 000000211120", -3000.00, "INTERNET TRANSFER"),
    Transaction(datetime.now(), "RABBIT HILL SKI RESORT", -186.90, "RABBIT HILL SKI RESORT"),
]
categorized = mapper.categorize_transactions(samples)

test_assert(categorized[0].category == "Grocery", "WAL-MART -> Grocery")
test_assert(categorized[1].category == "Ordering In / Delivery", "UBER EATS -> Ordering In / Delivery")
test_assert(categorized[2].category == "Uber Ride and Lyft", "LYFT -> Ride category")
test_assert(categorized[3].category == "Payment", "Payment keyword detection")
test_assert(categorized[4].category == "Income", "Deposit keyword detection")
test_assert(categorized[5].category == "Transfer Out", "Transfer out detection")
test_assert(categorized[6].category == "Outdoor Activities and Tickets", "Ski resort -> Activities")

# Investment mapping samples
investment_samples = [
    Transaction(datetime.now(), "Contribution (executed at 2026-01-21)", 100.00, "CONT Contribution (executed at 2026-01-21)"),
    Transaction(datetime.now(), "XEQT - iShares Core Equity ETF Portfolio: Bought 2.4 shares", -100.00, "BUY XEQT - iShares Core Equity ETF Portfolio: Bought 2.4 shares"),
    Transaction(datetime.now(), "HGGG - Harvest ETF: Sold 12.7 shares", 1085.89, "SELL HGGG - Harvest ETF: Sold 12.7 shares"),
    Transaction(datetime.now(), "PZA - Pizza Pizza Royalty Corp: Cash dividend distribution", 0.10, "DIV PZA - Pizza Pizza Royalty Corp: Cash dividend distribution"),
    Transaction(datetime.now(), "Non-resident tax (executed at 2025-12-05)", -0.42, "NRT Non-resident tax (executed at 2025-12-05)"),
]
investment_categorized = mapper.categorize_transactions(investment_samples)
test_assert(investment_categorized[0].category == "Investing Contributions", "CONT contribution -> Investing Contributions")
test_assert(investment_categorized[1].category == "Investing Buy Orders", "BUY/Bought -> Investing Buy Orders")
test_assert(investment_categorized[2].category == "Investing Sell Orders", "SELL/Sold -> Investing Sell Orders")
test_assert(investment_categorized[3].category == "Investing Income", "DIV dividend -> Investing Income")
test_assert(investment_categorized[4].category == "Investing Taxes and Fees", "NRT -> Investing Taxes and Fees")
test_assert(
    mapper.categorize_transaction(Transaction(datetime.now(), "Investment Profit/Loss", 12.34, "INVESTMENT_PNL_SUMMARY"))
    == "Investing Profit/Loss",
    "Investment P/L summary categorization",
)


test_section("TEST 4: CSV Parser - Amex Layout")
amex_csv = """Date,Date Processed,Description,Amount
24 Dec 2025,24 Dec 2025,UBER EATS               HTTPS://HELP.UB,36.50
01 Dec 2025,01 Dec 2025,PAYMENT RECEIVED - THANK YOU,-3090.07
"""

with tempfile.TemporaryDirectory() as tmp:
    amex_path = Path(tmp) / "amex.csv"
    amex_path.write_text(amex_csv, encoding="utf-8")
    parser = CSVStatementParser()
    amex_tx = parser.parse_csv(amex_path, "amex-cobalt")

    test_assert(len(amex_tx) == 2, "Parsed 2 Amex rows")
    test_assert(abs(amex_tx[0].amount - (-36.50)) < 0.001, "Amex charge converted to negative")
    test_assert(abs(amex_tx[1].amount - 3090.07) < 0.001, "Amex payment converted to positive")


test_section("TEST 5: CSV Parser - CIBC Credit Layout (Headerless)")
cibc_credit_csv = """2026-02-02,"Rabbit Hill Ski Resort F EDMONTON, AB",11.94,,4505********1001
2026-01-16,PAYMENT THANK YOU/PAIEMEN T MERCI,,244.88,4505********1001
"""

with tempfile.TemporaryDirectory() as tmp:
    cc_path = Path(tmp) / "cibc_credit.csv"
    cc_path.write_text(cibc_credit_csv, encoding="utf-8")
    parser = CSVStatementParser()
    cc_tx = parser.parse_csv(cc_path, "cibc-credit")

    test_assert(len(cc_tx) == 2, "Parsed 2 CIBC credit rows")
    test_assert(abs(cc_tx[0].amount - (-11.94)) < 0.001, "CIBC credit debit converted to negative")
    test_assert(abs(cc_tx[1].amount - 244.88) < 0.001, "CIBC credit payment converted to positive")


test_section("TEST 6: CSV Parser - CIBC Banking Layout (Headerless)")
cibc_banking_csv = """2026-01-30,Branch Transaction INTEREST,,1.12
2026-01-08,Internet Banking INTERNET TRANSFER 000000206167,2000.00,
"""

with tempfile.TemporaryDirectory() as tmp:
    bank_path = Path(tmp) / "cibc_bank.csv"
    bank_path.write_text(cibc_banking_csv, encoding="utf-8")
    parser = CSVStatementParser()
    bank_tx = parser.parse_csv(bank_path, "cibc-chequing")

    test_assert(len(bank_tx) == 2, "Parsed 2 CIBC banking rows")
    test_assert(abs(bank_tx[0].amount - 1.12) < 0.001, "Bank credit kept positive")
    test_assert(abs(bank_tx[1].amount - (-2000.00)) < 0.001, "Bank debit converted to negative")


test_section("TEST 6B: CSV Parser - Wealthsimple TFSA Layout")
wealthsimple_csv = '''"date","transaction","description","amount","balance","currency"
"2026-01-07","CONT","Contribution (executed at 2026-01-07)","100.0","100.02","CAD"
"2026-01-09","BUY","VGRO - Vanguard Growth ETF Portfolio: Bought 0.1387 shares at $43.81 per share","-6.08","100.54","CAD"
"2026-01-15","DIV","PZA - Pizza Pizza Royalty Corp: Cash dividend distribution","0.10","0.13","CAD"
"2026-01-13","LOAN","BBWI - Bath & Body Works Inc.: 1.0000 Shares on loan (executed at 2026-01-13)","0.0","0.03","BBWI"
'''
with tempfile.TemporaryDirectory() as tmp:
    ws_path = Path(tmp) / "wealthsimple.csv"
    ws_path.write_text(wealthsimple_csv, encoding="utf-8")
    parser = CSVStatementParser()
    ws_tx = parser.parse_csv(ws_path, "wealthsimple-tfsa")

    test_assert(len(ws_tx) == 2, "Investment mode keeps contribution + aggregated P/L")
    test_assert(ws_tx[0].payee == "Wealthsimple Contribution", "Contribution normalized for investment mode")
    test_assert(ws_tx[1].payee == "Investment Profit/Loss", "P/L summary row generated")


test_section("TEST 7: CSV Generator")
with tempfile.TemporaryDirectory() as tmp:
    csv_gen = CSVGenerator(tmp)
    tx = [
        Transaction(datetime(2026, 1, 1), "A", -10.0, "A", "Grocery"),
        Transaction(datetime(2026, 1, 3), "B", 20.0, "B", "Income"),
    ]
    out_path = csv_gen.generate_csv(tx, "test-account")
    test_assert(out_path is not None, "CSV generated")
    test_assert(os.path.exists(out_path), "Output CSV exists")

    content = Path(out_path).read_text(encoding="utf-8")
    test_assert("Date,Payee,Amount,Category,Notes" in content, "CSV header correct")
    test_assert("2026-01-01,A,-10.0,Grocery,Grocery" in content, "First row present")
    test_assert("2026-01-03,B,20.0,Income,Income" in content, "Second row present")


test_section("TEST 8: End-to-End Pipeline (CSV -> Category -> Output)")
end_to_end_csv = """Date,Date Processed,Description,Amount
13 Dec 2025,13 Dec 2025,UBER EATS HTTPS://HELP.UB,54.34
01 Dec 2025,01 Dec 2025,PAYMENT RECEIVED - THANK YOU,-3090.07
"""

with tempfile.TemporaryDirectory() as tmp:
    src_path = Path(tmp) / "statement.csv"
    src_path.write_text(end_to_end_csv, encoding="utf-8")

    parser = CSVStatementParser()
    tx = parser.parse_csv(src_path, "amex-cobalt")
    tx = mapper.categorize_transactions(tx)

    csv_gen = CSVGenerator(tmp)
    out_path = csv_gen.generate_csv(tx, "amex-cobalt")
    output = Path(out_path).read_text(encoding="utf-8")

    test_assert("Ordering In / Delivery" in output, "Category notes populated")
    test_assert("Payment" in output, "Payment tagged correctly")
    test_assert("-54.34" in output, "Expense sign normalized")
    test_assert("3090.07" in output, "Payment sign normalized")


print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)
print(f"Tests Passed: {tests_passed}")
print(f"Tests Failed: {tests_failed}")
print(f"Total Tests:  {tests_passed + tests_failed}")

if tests_failed == 0:
    print("\nALL TESTS PASSED")
    sys.exit(0)

print("\nSOME TESTS FAILED")
sys.exit(1)
