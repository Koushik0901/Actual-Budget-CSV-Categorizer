# Bank Statement CSV Categorizer for Actual Budget

Local offline tool to process exported bank/brokerage CSV files, auto-tag categories, and generate Actual Budget-ready CSV output.

## Overview

This repository is intentionally CSV-only (no PDF parsing).

Pipeline:
1. Read exported account CSVs from `input/<account>/`.
2. Parse and normalize date/payee/amount fields.
3. Auto-categorize transactions using `config/categories.yaml`.
4. Write consolidated output to `output/<account>/`.

## Supported Inputs

- Amex:
  - `Date,Date Processed,Description,Amount`
- CIBC (credit/chequing/savings), headerless or headered:
  - `Date,Description,Debit,Credit`
  - `Date,Description,Debit,Credit,Reference`
- Wealthsimple investment exports (TFSA/RRSP/Cash style):
  - `date,transaction,description,amount,balance,currency`
  - Investment mode:
    - keeps `CONT` as contributions
    - ignores `BUY`, `SELL`, `LOAN`, `RECALL`
    - summarizes remaining investment cash deltas into one `Investment Profit/Loss` row

## Amount Sign Rules

Output always follows Actual Budget convention:
- outflow/expense: negative
- inflow/income: positive

Examples:
- Amex charge `46.19` -> `-46.19`
- Amex payment `-3090.07` -> `+3090.07`
- CIBC debit `100.00` -> `-100.00`
- CIBC credit `1186.00` -> `+1186.00`

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### 1) Prepare input folders

```text
input/
├── amex-cobalt/
├── cibc-credit/
├── cibc-chequing/
├── cibc-savings/
└── wealthsimple-tfsa/
```

Drop exported CSV files into the corresponding account folder.

### 2) Run

```bash
python main.py
```

### 3) Output

```text
output/
├── amex-cobalt/
│   └── amex-cobalt_YYYY-MM-DD-to-YYYY-MM-DD.csv
├── cibc-credit/
│   └── cibc-credit_YYYY-MM-DD-to-YYYY-MM-DD.csv
├── cibc-chequing/
│   └── cibc-chequing_YYYY-MM-DD-to-YYYY-MM-DD.csv
├── cibc-savings/
│   └── cibc-savings_YYYY-MM-DD-to-YYYY-MM-DD.csv
└── wealthsimple-tfsa/
    └── wealthsimple-tfsa_YYYY-MM-DD-to-YYYY-MM-DD.csv
```

Behavior:
- deterministic per-account/per-date-range output names
- re-running updates the same file path (no `_1`, `_2` growth)
- when a rerun expands the date range, older consolidated files for that account are removed automatically

Output CSV schema:

```csv
Date,Payee,Amount,Category,Notes
2026-01-26,Costco Wholesal,-324.08,Grocery,Grocery
2026-01-27,Electronic Funds Transfer Deposit Ae Ei,1186.00,Income,Income
```

## Categories

Category rules live in `config/categories.yaml`.

Configured category set includes:
- Grocery
- Ordering In / Delivery
- Dining Out
- Subscriptions
- Investing Contributions
- Investing Buy Orders
- Investing Sell Orders
- Investing Income
- Investing Profit/Loss
- Investing Taxes and Fees
- Fuel / Gas
- Transit and Parking
- Car Share and Rentals
- Laundry and Vending
- Entertainment and Gaming
- Misc Services
- Shopping Retail
- Shopping Home
- Outdoor Activities and Tickets
- Uber Ride and Lyft
- Education and Tuition
- Wifi and Phone Bill
- Travel and Flights
- Fees and Charges

Special helper labels:
- `Payment`
- `Transfer In`
- `Transfer Out`
- `Income`
- `Uncategorized`

Matching is case/punctuation/spacing tolerant and selects the strongest keyword score.

## Import to Actual Budget

Map columns:
- `Date` -> Date
- `Payee` -> Payee
- `Amount` -> Amount
- `Category` -> Category
- `Notes` -> Notes

Important:
- Category mapping in import works best when categories already exist in your Actual budget.
- Use `sync_actual_categories.py` to create categories from `config/categories.yaml`.

### Sync categories to Actual

Install helper dependency:

```bash
pip install actualpy
```

List available Actual budget files:

```bash
python sync_actual_categories.py --list-files --base-url http://localhost:5006 --password "<ACTUAL_SERVER_PASSWORD>"
```

Create missing categories:

```bash
python sync_actual_categories.py \
  --base-url http://localhost:5006 \
  --password "<ACTUAL_SERVER_PASSWORD>" \
  --file "<ACTUAL_BUDGET_NAME_OR_FILE_ID>"
```

## Testing

Run:

```bash
python test_setup.py
python test_comprehensive.py
```

Current comprehensive suite result: **43/43 tests passing**.

## Public Repo Safety

This project is designed so personal data stays local.

- `input/`, `output/`, `logs/`, `.actual-cache/`, `server-files/`, and `.migrate` are gitignored.
- Do not commit raw bank exports, generated categorized CSVs, Actual cache files, or Actual server database/state files.
- Never hardcode server passwords in source files.
- Before push, run:

```bash
rg -n --hidden -S "password|api_key|secret|token|ACTUAL_PASSWORD|\.csv$"
```

## Troubleshooting

- `No account folders found`:
  - Create account subfolders under `input/`.
- Wrong category tag:
  - Add or refine keywords in `config/categories.yaml`.
- Sync script says `UnknownFileId`:
  - `--file` must be the Actual budget name/file ID, not a local CSV path.
- Parsing mismatch on new export format:
  - share sample CSV structure and update parser column mapping rules.
