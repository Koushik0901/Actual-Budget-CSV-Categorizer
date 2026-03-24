"""
CSV Generator
Generates Actual Budget compatible CSV files from transactions.
"""

import pandas as pd
from datetime import datetime
from typing import List
from pathlib import Path
import re

from core.models import Transaction


class CSVGenerator:
    """Generates CSV files for Actual Budget import."""
    
    # CSV columns optimized for Actual Budget
    COLUMNS = ['Date', 'Payee', 'Amount', 'Category', 'Notes']
    
    def __init__(self, output_folder: str = None):
        """
        Initialize CSV generator.
        
        Args:
            output_folder: Path to output folder for CSV files
        """
        if output_folder is None:
            current_dir = Path(__file__).parent.parent
            output_folder = current_dir / 'output'
        
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)
    
    def generate_csv(self, transactions: List[Transaction], 
                    account_type: str, 
                    statement_period: tuple = None,
                    suffix: str = "") -> str:
        """
        Generate CSV file from transactions.
        Automatically detects month from transaction dates for filename.
        
        Args:
            transactions: List of Transaction objects
            account_type: Type of account (e.g., 'amex_cobalt', 'cibc_credit')
            statement_period: Tuple of (start_date, end_date) - optional
            suffix: Optional suffix for filename
            
        Returns:
            Path to generated CSV file
        """
        if not transactions:
            print(f"No transactions to export for {account_type}")
            return None
        
        # Convert transactions to DataFrame
        data = [t.to_dict() for t in transactions]
        df = pd.DataFrame(data)
        
        # Ensure columns are in correct order
        df = df[self.COLUMNS]
        
        # Sort by date
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values(by='Date')
        
        # Extract date range for filename
        min_date = pd.to_datetime(df['Date'].min()).to_pydatetime()
        max_date = pd.to_datetime(df['Date'].max()).to_pydatetime()
        df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
        
        # Generate filename and account-specific output folder
        filename = self._generate_filename(account_type, min_date, max_date, suffix)
        account_folder = self._get_account_output_folder(account_type)
        account_folder.mkdir(parents=True, exist_ok=True)
        output_path = account_folder / filename

        if not suffix:
            self._cleanup_stale_consolidated_outputs(account_folder, account_type, filename)
        
        file_exists = output_path.exists()
        
        # Write CSV
        df.to_csv(output_path, index=False, encoding='utf-8')
        
        status = "Updated existing CSV" if file_exists else "Generated CSV"
        print(f"{status}: {output_path}")
        print(f"  Total transactions: {len(transactions)}")
        print(f"  Date range: {df['Date'].min()} to {df['Date'].max()}")
        print(f"  Total amount: ${df['Amount'].sum():,.2f}")
        
        return str(output_path)
    
    def _get_account_output_folder(self, account_type: str) -> Path:
        """
        Return output subfolder for the account.
        Mirrors input account-style grouping: output/<account>/
        """
        account_clean = account_type.replace('_', '-').strip()
        return self.output_folder / account_clean
    
    def _generate_filename(self, account_type: str, 
                          min_date: datetime,
                          max_date: datetime,
                          suffix: str = "") -> str:
        """Generate filename for CSV output with from/to dates."""
        # Clean account type for filename
        account_clean = account_type.replace('_', '-')
        
        # Generate date string with from/to dates: YYYY-MM-DD-to-YYYY-MM-DD
        date_str = f"{min_date.strftime('%Y-%m-%d')}-to-{max_date.strftime('%Y-%m-%d')}"
        
        # Build filename
        parts = [account_clean, date_str]
        if suffix:
            parts.append(suffix)
        
        filename = '_'.join(parts) + '.csv'
        
        return filename

    def _cleanup_stale_consolidated_outputs(
        self,
        account_folder: Path,
        account_type: str,
        keep_filename: str,
    ) -> None:
        """Remove older consolidated outputs for the same account/date-range pattern."""
        account_clean = account_type.replace('_', '-').strip()
        filename_pattern = re.compile(
            rf"^{re.escape(account_clean)}_\d{{4}}-\d{{2}}-\d{{2}}-to-\d{{4}}-\d{{2}}-\d{{2}}\.csv$"
        )

        for existing_file in account_folder.glob("*.csv"):
            if existing_file.name == keep_filename:
                continue
            if filename_pattern.match(existing_file.name):
                existing_file.unlink()
    
    def get_summary(self, transactions: List[Transaction]) -> dict:
        """
        Get summary statistics for transactions.
        
        Args:
            transactions: List of Transaction objects
            
        Returns:
            Dictionary with summary statistics
        """
        if not transactions:
            return {}
        
        amounts = [t.amount for t in transactions]
        dates = [t.date for t in transactions]
        
        income = sum(a for a in amounts if a > 0)
        expenses = sum(a for a in amounts if a < 0)
        
        return {
            'total_transactions': len(transactions),
            'income': income,
            'expenses': expenses,
            'net': income + expenses,
            'date_range': (min(dates), max(dates)),
            'avg_transaction': sum(amounts) / len(amounts)
        }
    
    def export_by_category(self, transactions: List[Transaction],
                          account_type: str) -> List[str]:
        """
        Export transactions to separate CSVs by category.
        
        Args:
            transactions: List of Transaction objects
            account_type: Type of account
            
        Returns:
            List of generated CSV file paths
        """
        from collections import defaultdict
        
        # Group by category
        by_category = defaultdict(list)
        for t in transactions:
            category = t.category or 'Uncategorized'
            by_category[category].append(t)
        
        generated_files = []
        for category, trans_list in by_category.items():
            safe_category = category.replace('/', '-').replace(' ', '_')
            filename = self.generate_csv(
                trans_list, 
                account_type, 
                suffix=f"category_{safe_category}"
            )
            if filename:
                generated_files.append(filename)
        
        return generated_files
