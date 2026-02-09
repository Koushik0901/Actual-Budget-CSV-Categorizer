# Bank Statement CSV Categorizer for Actual Budget

## Project Overview

This repository converts exported bank/brokerage CSV files into categorized, Actual Budget-ready CSVs.

The project is intentionally **CSV-only**. PDF parsing was removed.

## Current Status

- Status: Production-ready for current Amex, CIBC, and Wealthsimple exports
- Processing mode: 100% local/offline
- Entry point: `main.py`
- Idempotent behavior: deterministic output names + built-in duplicate transaction removal

## Workflow

1. Export CSV files from each account.
2. Place files in the matching folder under `input/`.
3. Run:
   ```bash
   python main.py
   ```
4. Import generated files from `output/<account>/` into Actual Budget.

## Folder Structure

```text
pdf-statement-converter/
├── input/
│   ├── amex-cobalt/
│   ├── cibc-credit/
│   ├── cibc-chequing/
│   ├── cibc-savings/
│   └── wealthsimple-tfsa/
├── output/
│   ├── amex-cobalt/
│   ├── cibc-credit/
│   ├── cibc-chequing/
│   ├── cibc-savings/
│   └── wealthsimple-tfsa/
├── config/
│   └── categories.yaml
├── core/
│   ├── models.py
│   ├── csv_statement_parser.py
│   ├── category_mapper.py
│   └── csv_generator.py
├── logs/
├── main.py
├── sync_actual_categories.py
├── test_setup.py
├── test_comprehensive.py
└── README.md
```

## Core Components

### `core/csv_statement_parser.py`

- Parses bank-exported CSV layouts with tolerant column detection.
- Supports headered and headerless exports.
- Normalizes amount signs to Actual convention:
  - expenses/outflows negative
  - inflows positive
- Investment mode (Wealthsimple-style):
  - keeps contributions (`CONT`)
  - ignores internal trading mechanics (`BUY`, `SELL`, `LOAN`, `RECALL`)
  - summarizes remaining investment cash deltas into one `Investment Profit/Loss` row

### `core/category_mapper.py`

- Loads category rules from `config/categories.yaml`.
- Uses normalization + strongest keyword score for matching.
- Handles special tags:
  - `Payment`
  - `Transfer In`
  - `Transfer Out`
  - `Income`
  - `Uncategorized`
- Positive unmatched transactions default to `Income` (except fee-like rows).

### `core/csv_generator.py`

- Writes Actual-compatible CSV columns:
  - `Date,Payee,Amount,Category,Notes`
- Sorts by date.
- Generates deterministic filenames:
  - `<account>_YYYY-MM-DD-to-YYYY-MM-DD.csv`
- Writes into account-specific output folders under `output/<account>/`.
- Re-runs update the same output path instead of creating suffix duplicates.

### `main.py`

- Discovers account subfolders under `input/`.
- Parses all CSV files in each account folder.
- Deduplicates rows across overlapping statement files.
- Categorizes and exports account-level consolidated output.
- Writes timestamped logs in `logs/`.

## Supported Input Formats

### Amex

Common layout:
```csv
Date,Date Processed,Description,Amount
```

### CIBC (Credit/Chequing/Savings)

Common layouts:
```csv
Date,Description,Debit,Credit
```
or
```csv
Date,Description,Debit,Credit,Reference
```

### Wealthsimple (TFSA/RRSP/Cash-style exports)

Common layout:
```csv
date,transaction,description,amount,balance,currency
```

## Category Taxonomy

Defined in `config/categories.yaml`.

Current configured categories include:
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

Special labels:
- Payment
- Transfer In
- Transfer Out
- Income
- Uncategorized

## Actual Budget Import

Field mapping:
- Date -> Date
- Payee -> Payee
- Amount -> Amount
- Category -> Category
- Notes -> Notes

`Category` values map best when categories already exist in Actual.

### Sync Categories to Actual

Use this once per budget (or whenever categories change):

```bash
pip install actualpy
python sync_actual_categories.py \
  --base-url http://localhost:5006 \
  --password "<ACTUAL_SERVER_PASSWORD>" \
  --file "<ACTUAL_BUDGET_NAME_OR_FILE_ID>"
```

Helpful discovery command:

```bash
python sync_actual_categories.py --list-files --base-url http://localhost:5006 --password "<ACTUAL_SERVER_PASSWORD>"
```

## Installation

```bash
pip install -r requirements.txt
```

Main dependencies:
- `pandas`
- `python-dateutil`
- `tqdm`
- `PyYAML`

## Testing

```bash
python test_setup.py
python test_comprehensive.py
```

Current comprehensive suite result: **40/40 passing**.

## Customization

Edit `config/categories.yaml` to add/refine keywords:

```yaml
categories:
  my_category:
    name: "My Category"
    keywords:
      - "merchant 1"
      - "merchant 2"
```

## Known Limitations

1. CSV layouts outside current supported patterns may need parser rule updates.
2. Category quality depends on merchant text consistency from source exports.
3. Multi-currency valuation (FX-aware net-worth modeling) is not explicitly implemented.

## Future Enhancements

- Optional GUI for drag/drop imports.
- Optional rule diagnostics (why each category matched).
- Optional analytics/dashboard layer on top of categorized outputs.

## Public Repo Safety

- Treat all statement exports and generated outputs as confidential.
- Keep `input/`, `output/`, `logs/`, and `.actual-cache/` local-only (gitignored).
- Do not commit passwords, tokens, or Actual cache/database files.
