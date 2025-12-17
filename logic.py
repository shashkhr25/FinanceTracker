"""Business-logic skeleton for MoneyTracker.

Contains dataclasses, validation, and computation signatures.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple, Any, Optional, Union

from storage import read_settings


# --- Domain models (Central Data Structure) ---

@dataclass(frozen=True)
class SharedSplit:
    """Represents a participant and their share of a shared expense."""
    name: str
    amount: Optional[float] = None


@dataclass
class Transaction:
    """Canonical in-memory representation of a transaction row."""
    id: str
    timestamp: datetime
    tx_type: str
    sub_type: str
    amount: float
    date: date
    description: str = ""
    category: str = ""
    device: str = ""
    location: str = ""
    occasion: str = ""
    effects_balance: bool = True
    linked_tx_id: str = ""
    shared_flag: bool = False
    shared_splits: Tuple[SharedSplit, ...] = ()
    shared_notes: str = ""


def _deserialize_shared_splits(raw: str) -> Tuple[SharedSplit, ...]:
    if not raw:
        return ()
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return ()

    splits: List[SharedSplit] = []
    for item in data:
        if not isinstance(item, Mapping):
            continue
        name_raw = str(item.get("name", "")).strip()
        if not name_raw:
            continue
        amount_raw = item.get("amount", None)
        try:
            amount_value = float(amount_raw) if amount_raw not in (None, "") else None
        except (TypeError, ValueError):
            amount_value = None
        splits.append(SharedSplit(name=name_raw, amount=amount_value))
    return tuple(splits)


def _serialize_shared_splits(splits: Sequence[SharedSplit]) -> str:
    if not splits:
        return ""
    payload = []
    for split in splits:
        payload.append({"name": split.name, "amount": split.amount})
    return json.dumps(payload)

# --- Configuration & Constants ---

ALLOWED_TX_TYPES = {"income", "expense", "transfer"}
ALLOWED_DEVICES = {"UPI", "CREDIT_CARD", "CREDIT_CARD_UPI", "CASH", "DEBIT", "BANK_TRANSFER", "OTHER", "SAVINGS_WITHDRAW", "DEBT_BORROWED"}
DEBT_CLEARED_CATEGORY = "Debt Cleared"
CREDIT_CARD_DEVICES = {"CREDIT_CARD", "CREDIT_CARD_UPI"}
DEFAULT_CREDIT_CARD_EXPENSE_SUB_TYPE = "credit_card_expense"
CREDIT_CARD_PAYMENT_SUB_TYPE = "credit_card_payment"
DEFAULT_CREDIT_CARD_DEBT_SUB_TYPE = "credit_card_debt"
DEFAULT_SUB_TYPE = "regular"
CREDIT_CARD_PAYMENT_CATEGORY_KEYS = {"credit card bill", "credit card upi bill"}
SAVINGS_WITHDRAW_CATEGORY_KEYS = {"taken from savings"}
SAVINGS_CATEGORY_LABELS = {
    "savings fd": "Savings FD",
    "savings rd": "Savings RD",
    "savings gold": "Savings Gold",
    "savings": "Savings",
}
SAVINGS_INITIAL_SETTING_KEYS = {
    "Savings": "initial_savings_balance",
    "Savings FD": "initial_savings_fd_balance",
    "Savings RD": "initial_savings_rd_balance",
    "Savings Gold": "initial_savings_gold_balance",
}

# --- Utility Functions ---

def new_transaction_id() -> str:
    """Returns a fresh unique identifier."""
    return uuid.uuid4().hex

def normalize_amount(amount: float) -> float:
    """Normalize raw amount into canonical precision."""
    return round(abs(float(amount)), 2)

# --- Conversion Helpers ---

def transaction_from_row(row: Mapping[str, str]) -> Transaction:
    """Construct a Transaction from raw storage row."""
    # ... (Implementation as previously reconstructed)
    def get(key: str, default: str = "") -> str:
        value = row.get(key)
        return str(value) if value is not None else default

    affects_balance_raw = get("effects_balance", "True").lower()
    affects_balance = affects_balance_raw in ("true", "1", "yes")

    timestamp_raw = get("timestamp")
    try:
        timestamp = datetime.fromisoformat(timestamp_raw)
    except ValueError:
        timestamp = datetime.utcnow()

    date_raw = get("date")
    try:
        date_value = date.fromisoformat(date_raw)
    except ValueError:
        date_value = date.today()

    amount_raw = get("amount", "0")
    try:
        amount_value = float(amount_raw)
    except ValueError:
        amount_value = 0.0

    shared_flag_raw = get("shared_flag", "False").lower()
    shared_flag = shared_flag_raw in ("true", "1", "yes")
    shared_splits_raw = row.get("shared_splits", "")
    shared_splits = _deserialize_shared_splits(shared_splits_raw)
    shared_notes = row.get("shared_notes", "") or ""

    return Transaction(
        id=get("id", uuid.uuid4().hex),
        timestamp=timestamp,
        tx_type=get("tx_type", "expense"),
        sub_type=get("sub_type", DEFAULT_SUB_TYPE),
        amount=amount_value,
        date=date_value,
        description=get("description"),
        category=get("category"),
        device=get("device", "OTHER"),
        location=get("location"),
        occasion=get("occasion"),
        effects_balance=affects_balance,
        linked_tx_id=get("linked_tx_id"),
        shared_flag=shared_flag and bool(shared_splits),
        shared_splits=shared_splits,
        shared_notes=shared_notes,
    )

def transaction_to_row(tx: Transaction) -> MutableMapping[str, object]:
    """Serialize a Transaction into storage friendly row mapping."""
    # ... (Implementation as previously reconstructed)
    return {
        "id": tx.id,
        "timestamp": tx.timestamp.isoformat(),
        "tx_type": tx.tx_type,
        "sub_type": tx.sub_type,
        "amount": f"{tx.amount:.2f}",
        "date": tx.date.isoformat(),
        "description": tx.description,
        "category": tx.category,
        "device": tx.device,
        "location": tx.location,
        "occasion": tx.occasion,
        "effects_balance": "True" if tx.effects_balance else "False",
        "linked_tx_id": tx.linked_tx_id,
        "shared_flag": "True" if tx.shared_flag and tx.shared_splits else "False",
        "shared_splits": _serialize_shared_splits(tx.shared_splits),
        "shared_notes": tx.shared_notes,
    }


# --- Validation & Normalization ---

def validate_transaction(tx: Transaction) -> Tuple[bool, List[str]]:
    """Return validation status plus error messages."""
    errors: List[str] = []

    if tx.tx_type not in ALLOWED_TX_TYPES:
        errors.append(f"Unsupported transaction type: {tx.tx_type}")

    if tx.device and tx.device not in ALLOWED_DEVICES:
        errors.append(f"Unsupported device: {tx.device}")

    if tx.amount <= 0:
        errors.append("Amount must be greater than zero")

    try:
        date.fromisoformat(tx.date.isoformat())
    except ValueError:
        errors.append(f"Invalid date: {tx.date}")

    return len(errors) == 0, errors

# --- Core computations ---

def compute_balance(transactions: Sequence[Transaction], initial_balance: float) -> float:
    """Compute balance from transactions that affect balance."""
    balance = float(initial_balance)
    for tx in transactions:
        # Skip transactions that don't affect balance
        if not tx.effects_balance:
            continue
        
        # Skip credit card related transactions as they're handled separately
        if tx.sub_type in (DEFAULT_CREDIT_CARD_EXPENSE_SUB_TYPE, DEFAULT_CREDIT_CARD_DEBT_SUB_TYPE):
            continue
            
        # Skip debt borrowed transactions
        if hasattr(tx, 'device') and tx.device == "DEBT_BORROWED":
            continue

        if tx.tx_type == "income":
            balance += tx.amount
        elif tx.tx_type == "expense":
            balance -= tx.amount
    return round(balance, 2)

def compute_cash_balance(transactions: Sequence[Transaction], initial_cash_balance: float) -> float:
    """Compute balance from transactions that affect balance."""
    balance = float(initial_cash_balance)
    for tx in transactions:
        if not tx.effects_balance:
            continue
        
        if tx.sub_type in (DEFAULT_CREDIT_CARD_EXPENSE_SUB_TYPE, DEFAULT_CREDIT_CARD_DEBT_SUB_TYPE):
            continue

        if tx.device == "CASH":
            if tx.tx_type == "income":
                balance += tx.amount
            elif tx.tx_type == "expense":
                balance -= tx.amount
    return round(balance, 2)

def debug_transaction(tx) -> str:
    """Return a string with all transaction attributes for debugging."""
    attrs = {}
    for attr in dir(tx):
        if not attr.startswith('__') and not callable(getattr(tx, attr)):
            attrs[attr] = getattr(tx, attr, 'N/A')
    return json.dumps(attrs, indent=2, default=str)

def get_billing_cycle(tx_date: date) -> tuple[date, date]:
    """Return the start and end dates of the billing cycle for a given date.
    
    Billing cycle runs from the 19th of the current month to the 20th of the next month.
    """
    if tx_date.day >= 19:
        # Current month's 19th to next month's 20th
        cycle_start = tx_date.replace(day=19)
        # Calculate next month's 20th
        if tx_date.month == 12:
            next_month = tx_date.replace(year=tx_date.year + 1, month=1, day=20)
        else:
            next_month = tx_date.replace(month=tx_date.month + 1, day=20)
        cycle_end = next_month
    else:
        # Previous month's 19th to current month's 20th
        if tx_date.month == 1:
            prev_month = tx_date.replace(year=tx_date.year - 1, month=12, day=19)
        else:
            prev_month = tx_date.replace(month=tx_date.month - 1, day=19)
        cycle_start = prev_month
        cycle_end = tx_date.replace(day=20)
    
    return cycle_start, cycle_end

def compute_outstanding_debt(transactions: Sequence[Transaction]) -> tuple[float, float]:
    """Calculate outstanding debt, separating credit card debt and borrowed debt.
    
    Credit card debt is calculated per billing cycle (19th to 18th of next month).
    
    Args:
        transactions: List of transactions to process
        
    Returns:
        Tuple of (credit_card_debt, borrowed_debt) as floats
    """
    print("\n=== Starting Debt Calculation ===")
    print(f"Processing {len(transactions)} transactions")
    print("=== CREDIT_CARD_DEVICES =", CREDIT_CARD_DEVICES)
    print("=== CREDIT_CARD_PAYMENT_SUB_TYPE =", CREDIT_CARD_PAYMENT_SUB_TYPE)
    
    # Track expenses and payments by billing cycle
    cycle_totals = {}
    borrowed_debt = 0.0
    
    # Get current billing cycle
    today = date.today()
    current_cycle_start, current_cycle_end = get_billing_cycle(today)
    print(f"Current billing cycle: {current_cycle_start} to {current_cycle_end}")

    # First pass: Process all transactions
    for tx in transactions:
        # Skip if not an expense or doesn't have required attributes
        if not hasattr(tx, 'tx_type') or tx.tx_type != "expense":
            continue

        # Get transaction details with safe defaults
        device = getattr(tx, 'device', '').upper()
        description = getattr(tx, 'description', '').lower()
        category = getattr(tx, 'category', '').lower()
        amount = abs(getattr(tx, 'amount', 0))
        tx_date = getattr(tx, 'date', today)
        
        # Get billing cycle for this transaction
        cycle_start, cycle_end = get_billing_cycle(tx_date)
        cycle_key = (cycle_start, cycle_end)
        
        # Initialize cycle totals if not exists
        if cycle_key not in cycle_totals:
            cycle_totals[cycle_key] = {
                'expenses': 0.0,
                'payments': 0.0,
                'is_current': (cycle_start == current_cycle_start and cycle_end == current_cycle_end)
            }
        
        # Handle DEBT_BORROWED transactions
        if device == "DEBT_BORROWED":
            if not any(term in description for term in ["payment", "cleared"]):
                borrowed_debt += amount
                print(f"DEBT_BORROWED: Added {amount} to borrowed debt")
            continue
            
        # Handle DEBT_CLEARED transactions
        if DEBT_CLEARED_CATEGORY.lower() in category:
            payment = min(borrowed_debt, amount)
            borrowed_debt = max(0, borrowed_debt - payment)
            print(f"DEBT_CLEARED: Reduced borrowed debt by {payment}")
            continue
        
        # Check if this is a credit card transaction
        is_credit_card = (
            device in CREDIT_CARD_DEVICES or
            any(term in description for term in ['credit card', 'creditcard', 'cc ']) or
            ('credit' in category and 'card' in category)
        )
        
        if not is_credit_card:
            # Check for borrowed debt in non-credit card transactions
            if any(term in category for term in ['borrowed', 'loan']):
                borrowed_debt += amount
                print(f"BORROWED: Added {amount} to borrowed debt")
            continue

        # For credit card transactions, check if it's a payment
        is_payment = any(term in description for term in ['payment', 'bill', 'paid', 'clear', 'settle', 'repay'])
        
        # Process payment or expense
        if is_payment:
            cycle_totals[cycle_key]['payments'] += amount
            print(f"CREDIT CARD PAYMENT: Added {amount} to payments for cycle {cycle_start} to {cycle_end}")
        else:
            cycle_totals[cycle_key]['expenses'] += amount
            print(f"CREDIT CARD EXPENSE: Added {amount} to expenses for cycle {cycle_start} to {cycle_end}")
    
    # Calculate total credit card debt
    credit_card_debt = 0.0
    current_cycle_debt = 0.0
    total_expenses = 0.0
    total_payments = 0.0
    
    # First, calculate total expenses and payments across all cycles
    all_expenses = sum(totals['expenses'] for totals in cycle_totals.values())
    all_payments = sum(totals['payments'] for totals in cycle_totals.values())
    
    # Process cycles in chronological order to show breakdown
    for (cycle_start, cycle_end), totals in sorted(cycle_totals.items()):
        cycle_balance = totals['expenses'] - totals['payments']
        is_current = (cycle_start, cycle_end) == (current_cycle_start, current_cycle_end)
        
        if is_current:
            # For current cycle, include all expenses in debt calculation
            current_cycle_debt = totals['expenses']  # Include all expenses, regardless of payments
            print(f"\nCurrent Cycle ({cycle_start} to {cycle_end}):")
            print(f"  Expenses: {totals['expenses']:.2f} (all included in debt)")
            print(f"  Payments: {totals['payments']:.2f} (applied to oldest debt first)")
        else:
            # For past cycles, show the balance but don't include in debt if payments exceed expenses
            print(f"\nPast Cycle ({cycle_start} to {cycle_end}):")
            print(f"  Expenses: {totals['expenses']:.2f}")
            print(f"  Payments: {totals['payments']:.2f}")
            print(f"  Balance: {cycle_balance:.2f}")
        
        total_expenses += totals['expenses']
        total_payments += totals['payments']
    
    # Total debt is all expenses minus payments, but not less than 0
    credit_card_debt = max(0, all_expenses - all_payments)
    
    # If there are payments, show how they were applied
    if all_payments > 0:
        print("\nPayment Application:")
        print(f"  - Total Expenses: {all_expenses:.2f}")
        print(f"  - Total Payments: {all_payments:.2f}")
        print(f"  - Remaining Debt: {credit_card_debt:.2f}")
    
    # Calculate current cycle's unpaid expenses (for reference)
    current_cycle_totals = next((t for (s, e), t in cycle_totals.items() 
                              if (s, e) == (current_cycle_start, current_cycle_end)), 
                             {'expenses': 0, 'payments': 0})
    current_cycle_expenses = current_cycle_totals['expenses']
    
    print(f"\n=== Debt Calculation Summary ===")
    print(f"Total Credit Card Expenses: {total_expenses:.2f}")
    print(f"Total Credit Card Payments: {total_payments:.2f}")
    print(f"\nCurrent Billing Cycle ({current_cycle_start} to {current_cycle_end}):")
    print(f"  Current Cycle Expenses: {current_cycle_totals['expenses']:.2f}")
    print(f"  Current Cycle Payments: {current_cycle_totals['payments']:.2f}")
    print(f"  Unpaid Expenses: {max(0, current_cycle_totals['expenses'] - current_cycle_totals['payments']):.2f}")
    print(f"\nTotal Credit Card Debt: {credit_card_debt:.2f}")
    print(f"Borrowed Debt: {borrowed_debt:.2f}")
    print(f"Total Debt: {credit_card_debt + borrowed_debt:.2f}")
    
    # Show how payments are being applied
    if all_payments > 0:
        print("\nNote: Payments are applied to the oldest expenses first.")
        print(f"  - {min(all_payments, all_expenses):.2f} applied to oldest expenses")
        print(f"  - {max(0, all_payments - all_expenses):.2f} remaining payments (if any)")
    print("=" * 25 + "\n")
    
    return (round(credit_card_debt, 2), round(borrowed_debt, 2))

def compute_savings_totals(transactions: Sequence[Transaction]) -> Dict[str, float]:
    """Aggregate savings-related flows, including withdrawals."""
    totals: Dict[str, float] = {label: 0.0 for label in SAVINGS_CATEGORY_LABELS.values()}

    settings = read_settings()
    savings_label = SAVINGS_CATEGORY_LABELS.get("savings", "Savings")
    for label, setting_key in SAVINGS_INITIAL_SETTING_KEYS.items():
        initial_value_raw = settings.get(setting_key, 0.0)
        try:
            initial_value = float(initial_value_raw)
        except (TypeError, ValueError):
            initial_value = 0.0
        totals[label] = totals.get(label, 0.0) + initial_value
    
    for tx in transactions:
        category_key = (tx.category or "").strip().lower()

        if tx.tx_type == "expense":
            if category_key in SAVINGS_CATEGORY_LABELS:
                label = SAVINGS_CATEGORY_LABELS[category_key]
                totals[label] = totals.get(label, 0.0) + tx.amount
        elif tx.tx_type == "income":
            if category_key in SAVINGS_WITHDRAW_CATEGORY_KEYS or tx.device == "SAVINGS_WITHDRAW":
                totals[savings_label] = totals.get(savings_label, 0.0) - tx.amount

    return {label: round(amount, 2) for label, amount in totals.items()}
    
def compute_net_worth(transactions: Sequence[Transaction], savings: float, assets: float) -> float:
    """Return net worth using balance and debt computations."""
    raise NotImplementedError

# --- Transaction orchestration ---

def summarize_by_category(transactions: Iterable[Transaction]) -> Mapping[str, float]:
    """Return aggregated expense totals keyed by category"""
    totals: Dict[str, float] = {} # <<< THIS IS THE FUNCTION YOU WERE MISSING
    
    for tx in transactions:
        if tx.tx_type != "expense":
            continue
        
        category = tx.category or "Uncategorized"
        totals[category] = totals.get(category, 0.0) + tx.amount

    return {key: round(value, 2) for key, value in totals.items()}


def compute_shared_allocations(tx: Transaction) -> Dict[str, float]:
    """Return per-participant allocations for a shared expense transaction."""

    if not tx.shared_flag or not tx.shared_splits:
        return {}

    total_amount = normalize_amount(tx.amount)
    explicit_allocations: Dict[str, float] = {}
    unspecified_participants: List[str] = []

    for split in tx.shared_splits:
        name = split.name.strip()
        if not name:
            continue

        amount_raw = split.amount
        if amount_raw in (None, ""):
            unspecified_participants.append(name)
            continue

        try:
            share_value = round(abs(float(amount_raw)), 2)
        except (TypeError, ValueError):
            unspecified_participants.append(name)
            continue

        explicit_allocations[name] = explicit_allocations.get(name, 0.0) + share_value

    specified_total = sum(explicit_allocations.values())
    remaining = max(round(total_amount - specified_total, 2), 0.0)

    allocations = dict(explicit_allocations)
    if unspecified_participants:
        count = len(unspecified_participants)
        if count == 0:
            return allocations

        base_share = remaining / count if remaining > 0 else 0.0
        distributed = 0.0
        for idx, name in enumerate(unspecified_participants):
            if idx == count - 1:
                share = round(max(remaining - distributed, 0.0), 2)
            else:
                share = round(base_share, 2)
                distributed += share
            allocations[name] = allocations.get(name, 0.0) + share

    return allocations


def summarize_shared_expenses(
    transactions: Sequence[Transaction],
    participant_filter: str | None = None,
    category_filter: str | None = None,
) -> Tuple[Dict[str, float], List[Tuple[Transaction, Dict[str, float]]]]:
    """Return per-person totals plus detailed allocations for shared expenses."""

    participant_key = (participant_filter.strip().lower() 
                      if participant_filter and participant_filter.strip() 
                      else None)
    category_key = (category_filter.strip().lower() 
                   if category_filter and category_filter.strip() 
                   else None)

    summary: Dict[str, float] = {}
    details: List[Tuple[Transaction, Dict[str, float]]] = []

    for tx in transactions:
        if not tx.shared_flag:
            continue

        # Only consider meaningful shared flows
        if tx.tx_type not in ("expense", "income"):
            continue

        category_name = (tx.category or "").strip().lower()
        if category_key and category_name != category_key:
            continue

        allocations = compute_shared_allocations(tx)
        if not allocations:
            continue

        # For DEBT_BORROWED, invert the amount to show as negative in shared expenses
        # For other transactions, expenses add to what people owe; income (refunds) reduce it
        sign = -1.0 if tx.device == "DEBT_BORROWED" else (1.0 if tx.tx_type == "expense" else -1.0)

        if participant_key:
            name_map = {name.lower(): name for name in allocations}
            if participant_key not in name_map:
                continue
            original_name = name_map[participant_key]
            filtered_allocations = {original_name: allocations[original_name]}
        else:
            filtered_allocations = allocations

        details.append((tx, allocations))

        for name, amount in filtered_allocations.items():
            summary[name] = round(summary.get(name, 0.0) + sign * amount, 2)

    # Drop near-zero entries so fully repaid people disappear
    cleaned_summary = {
        name: value for name, value in summary.items() if abs(value) >= 0.005
    }

    return cleaned_summary, details


def create_credit_card_expense(
    amount: float, 
    date_value: date, 
    description: str, 
    category: str, 
    device: str, 
    location: str = "", 
    occasion: str = "",
    expense_sub_type: str = DEFAULT_CREDIT_CARD_EXPENSE_SUB_TYPE,
    debt_sub_type: str = DEFAULT_CREDIT_CARD_DEBT_SUB_TYPE,
    shared_flag: bool = False,
    shared_splits: Optional[Sequence[SharedSplit]] = None,
    shared_notes: str = "",
    ) -> Tuple[Transaction, Transaction]:
    """Return paired transactions representing a credit-card purchase."""
    
    normalized_amount = normalize_amount(amount)
    normalized_device = device.upper() if device else "OTHER"
    if normalized_device not in CREDIT_CARD_DEVICES:
        normalized_device = "CREDIT_CARD"

    expense_tx = create_expense_transaction(
        amount=normalized_amount,
        date_value=date_value,
        description=description,
        category=category,
        device=normalized_device,
        location=location,
        occasion=occasion,
        sub_type=expense_sub_type,
        effects_balance=False,
        shared_flag=shared_flag,
        shared_splits=shared_splits,
        shared_notes=shared_notes,
    )
    
    debt_tx = create_income_transaction(
        amount=normalized_amount,
        date_value=date_value,
        description=f"Debt for: {description}",
        category="Debt",
        device=normalized_device,
        location=location,
        occasion=occasion,
        sub_type=debt_sub_type,
        effects_balance=False,
    )

    return link_transactions(expense_tx, debt_tx)


def create_credit_card_payment(
    amount: float,
    date_value: date,
    description: str,
    category: str,
    device: str,
    location: str = "",
    occasion: str = "",
) -> Transaction:
    """Return transaction representing payment of credit-card bill."""

    return create_expense_transaction(
        amount=amount,
        date_value=date_value,
        description=description,
        category=category,
        device=device,
        location=location,
        occasion=occasion,
        sub_type=CREDIT_CARD_PAYMENT_SUB_TYPE,
        effects_balance=True,
    )


def create_expense_transaction(
    amount: float,
    date_value: date,
    description: str,
    category: str,
    device: str,
    location: str = "",
    occasion: str = "",
    sub_type: str = DEFAULT_SUB_TYPE,
    effects_balance: bool = True,
    shared_flag: bool = False,
    shared_splits: Optional[Sequence[SharedSplit]] = None,
    shared_notes: str = "",
    ) -> Transaction:
    """Convenience helper for expense transactions."""
    
    normalized_amount = normalize_amount(amount)
    cleaned_device = device.upper() if device else "OTHER"
    if cleaned_device not in ALLOWED_DEVICES:
        cleaned_device = "OTHER"
        
    splits_tuple: Tuple[SharedSplit, ...] = tuple(shared_splits or ())

    return Transaction(
        id=new_transaction_id(),
        timestamp=datetime.utcnow(),
        tx_type="expense",
        sub_type=sub_type,
        amount=normalized_amount,
        date=date_value,
        description=description,
        category=category,
        device=cleaned_device,
        location=location,
        occasion=occasion,
        effects_balance=effects_balance,
        linked_tx_id="",
        shared_flag=shared_flag and bool(splits_tuple),
        shared_splits=splits_tuple,
        shared_notes=shared_notes if shared_flag and splits_tuple else "",
    )

def create_income_transaction(
    amount: float,
    date_value: date,
    description: str,
    category: str,
    device: str,
    location: str = "",
    occasion: str = "",
    sub_type: str = DEFAULT_SUB_TYPE,
    effects_balance: bool = True,
    shared_flag: bool = False,
    shared_splits: Optional[Sequence[SharedSplit]] = None,
    shared_notes: str = "",
    ) -> Transaction:
    """Convenience helper for income transactions (including shared refunds)."""

    normalized_amount = normalize_amount(amount)
    cleaned_device = device.upper() if device else "OTHER"
    if cleaned_device not in ALLOWED_DEVICES:
        cleaned_device = "OTHER"

    splits_tuple: Tuple[SharedSplit, ...] = tuple(shared_splits or ())

    return Transaction(
        id=new_transaction_id(),
        timestamp=datetime.utcnow(),
        tx_type="income",
        sub_type=sub_type,
        amount=normalized_amount,
        date=date_value,
        description=description,
        category=category,
        device=cleaned_device,
        location=location,
        occasion=occasion,
        effects_balance=effects_balance,
        linked_tx_id="",
        shared_flag=shared_flag and bool(splits_tuple),
        shared_splits=splits_tuple,
        shared_notes=shared_notes if shared_flag and splits_tuple else "",
    )
    
def link_transactions(parent: Transaction, child: Transaction) -> Tuple[Transaction, Transaction]:
    """Ensure both transactions share a linked_tx_id."""
    link_id = parent.linked_tx_id or child.linked_tx_id or uuid.uuid4().hex
    parent.linked_tx_id = link_id
    child.linked_tx_id = link_id
    return parent, child

def create_credit_card_payment(
    amount: float,
    date_value: date,
    description: str,
    category: str,
    device: str,
    location: str = "",
    occasion: str = "",
) -> Transaction:
    """Return transaction representing payment of credit-card bill."""

    return create_expense_transaction(
        amount=amount,
        date_value=date_value,
        description=description,
        category=category,
        device=device,
        location=location,
        occasion=occasion,
        sub_type=CREDIT_CARD_PAYMENT_SUB_TYPE,
        effects_balance=True,
    )

def create_debt_clearance_transaction(
    amount: float,
    date_value: date,
    description: str = "Debt cleared",
    device: str = "BANK_TRANSFER",
) -> Transaction:
    """Return an expense entry that zeros out outstanding debt."""

    return create_expense_transaction(
        amount=amount,
        date_value=date_value,
        description=description,
        category="Debt",
        device=device,
        sub_type=DEFAULT_CREDIT_CARD_DEBT_SUB_TYPE,
        effects_balance=False,
    )