"""
Category Mapper
Automatically categorizes transactions based on merchant names.
"""

import re
import yaml
from typing import Dict, List
from pathlib import Path

from core.models import Transaction


class CategoryMapper:
    """Maps merchant names to categories."""
    
    def __init__(self, config_path: str = None):
        """
        Initialize the category mapper.
        
        Args:
            config_path: Path to categories.yaml config file
        """
        if config_path is None:
            # Default to config folder in project
            current_dir = Path(__file__).parent.parent
            config_path = current_dir / 'config' / 'categories.yaml'
        
        self.config_path = config_path
        self.categories: Dict[str, Dict] = {}
        self.default_category = "Uncategorized"
        self.payment_keywords: List[str] = []
        self.income_keywords: List[str] = []
        self.transfer_keywords: List[str] = []
        self._category_rules: List[Dict[str, str]] = []
        self._payment_rules: List[str] = []
        self._income_rules: List[str] = []
        self._transfer_rules: List[str] = []
        
        self._load_config()
    
    def _load_config(self):
        """Load category configuration from YAML file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            self.categories = config.get('categories', {})
            self.default_category = config.get('default_category', 'Uncategorized')
            self.payment_keywords = config.get('payment_keywords', [])
            self.income_keywords = config.get('income_keywords', [])
            self.transfer_keywords = config.get('transfer_keywords', [])
            self._build_rules()
            
            print(f"Loaded {len(self.categories)} categories from config")
            
        except FileNotFoundError:
            print(f"Category config not found at {self.config_path}")
            print("Using default empty categories")
        except yaml.YAMLError as e:
            print(f"Error parsing category config: {e}")
            print("Using default empty categories")
    
    def _build_rules(self):
        """Precompute normalized keyword rules for fast matching."""
        self._category_rules = []
        
        for category_key, category_data in self.categories.items():
            category_name = category_data.get('name', category_key)
            for keyword in category_data.get('keywords', []):
                normalized = self._normalize(keyword)
                compact = self._compact(normalized)
                if normalized:
                    self._category_rules.append({
                        'category': category_name,
                        'normalized': normalized,
                        'compact': compact,
                        'score': len(compact)
                    })
        
        self._payment_rules = [self._normalize(k) for k in self.payment_keywords if self._normalize(k)]
        self._income_rules = [self._normalize(k) for k in self.income_keywords if self._normalize(k)]
        self._transfer_rules = [self._normalize(k) for k in self.transfer_keywords if self._normalize(k)]
    
    def categorize_transaction(self, transaction: Transaction) -> str:
        """
        Categorize a single transaction based on payee name.
        
        Args:
            transaction: Transaction object
            
        Returns:
            Category name
        """
        haystack = f"{transaction.payee} {transaction.raw_description or ''}".strip()
        normalized_text = self._normalize(haystack)
        compact_text = self._compact(normalized_text)

        # Investment account helper labels should beat generic transfer/income logic.
        if (
            "wealthsimple contribution" in normalized_text
            or "cont contribution" in normalized_text
            or "contribution executed at" in normalized_text
        ):
            return "Investing Contributions"
        if "investment pnl summary" in normalized_text or "investment profit loss" in normalized_text:
            return "Investing Profit/Loss"
        
        # Check if it's a payment
        if self._matches_any(normalized_text, compact_text, self._payment_rules):
            return "Payment"
        
        # Check if it's an account transfer
        if self._matches_any(normalized_text, compact_text, self._transfer_rules):
            if transaction.amount > 0:
                return "Transfer In"
            if transaction.amount < 0:
                return "Transfer Out"
            return "Transfer"
        
        # Score all category matches and choose the strongest.
        best_category = None
        best_score = 0
        
        for rule in self._category_rules:
            if self._contains(normalized_text, compact_text, rule['normalized'], rule['compact']):
                if rule['score'] > best_score:
                    best_score = rule['score']
                    best_category = rule['category']
        
        if best_category:
            return best_category
        
        # Check if it's income
        if transaction.amount > 0:
            if self._matches_any(normalized_text, compact_text, self._income_rules):
                return "Income"
            # Positive unmatched transactions are usually deposits/refunds.
            if "refund" in normalized_text or "cashback" in normalized_text:
                return "Income"
        
        # Positive unmatched transactions default to Income for budget import quality.
        if transaction.amount > 0:
            # Avoid tagging obvious fees as income when parsing reversals.
            if "fee" in normalized_text or "charge" in normalized_text:
                return self.default_category
            return "Income"
        
        return self.default_category
    
    def _normalize(self, text: str) -> str:
        normalized = re.sub(r'[^a-z0-9]+', ' ', text.lower())
        return ' '.join(normalized.split())
    
    def _compact(self, text: str) -> str:
        return text.replace(' ', '')
    
    def _contains(self, normalized_text: str, compact_text: str, keyword_norm: str, keyword_compact: str) -> bool:
        return keyword_norm in normalized_text or keyword_compact in compact_text
    
    def _matches_any(self, normalized_text: str, compact_text: str, keywords: List[str]) -> bool:
        for keyword in keywords:
            if self._contains(normalized_text, compact_text, keyword, self._compact(keyword)):
                return True
        return False
    
    def categorize_transactions(self, transactions: List[Transaction]) -> List[Transaction]:
        """
        Categorize a list of transactions.
        
        Args:
            transactions: List of Transaction objects
            
        Returns:
            List of categorized Transaction objects
        """
        categorized = []
        for transaction in transactions:
            category = self.categorize_transaction(transaction)
            transaction.category = category
            transaction.notes = category  # For Actual Budget import
            categorized.append(transaction)
        
        return categorized
    
    def get_category_stats(self, transactions: List[Transaction]) -> Dict[str, int]:
        """
        Get statistics on categorized transactions.
        
        Args:
            transactions: List of Transaction objects
            
        Returns:
            Dictionary mapping categories to transaction counts
        """
        stats = {}
        for transaction in transactions:
            category = transaction.category or self.default_category
            stats[category] = stats.get(category, 0) + 1
        
        return stats
    
    def add_custom_rule(self, keyword: str, category: str):
        """
        Add a custom categorization rule.
        
        Args:
            keyword: Keyword to match
            category: Category to assign
        """
        # Find or create category
        for cat_key, cat_data in self.categories.items():
            if cat_data.get('name') == category:
                cat_data['keywords'].append(keyword)
                return
        
        # Create new category
        new_key = category.lower().replace(' ', '_')
        self.categories[new_key] = {
            'name': category,
            'keywords': [keyword]
        }
    
    def save_config(self):
        """Save current configuration back to YAML file."""
        config = {
            'categories': self.categories,
            'default_category': self.default_category,
            'payment_keywords': self.payment_keywords,
            'income_keywords': self.income_keywords,
            'transfer_keywords': self.transfer_keywords
        }
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
