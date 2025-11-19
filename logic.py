"""Business-logic skeleton for MoneyTracker.

Contains dataclasses, validation, and computation signatures.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple, Any

from storage import read_settings


# --- Domain models (Central Data Structure) ---

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

# --- Configuration & Constants ---

ALLOWED_TX_TYPES = {"income", "expense", "transfer"}
ALLOWED_DEVICES = {"UPI", "CREDIT_CARD", "CREDIT_CARD_UPI", "CASH", "DEBIT", "BANK_TRANSFER", "OTHER"}
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
        if not tx.effects_balance:
            continue
        
        if tx.sub_type in (DEFAULT_CREDIT_CARD_EXPENSE_SUB_TYPE, DEFAULT_CREDIT_CARD_DEBT_SUB_TYPE):
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

def compute_outstanding_debt(transactions: Sequence[Transaction]) -> float:
    """Aggregate outstanding debt from credit-card flows."""
    debt_total = 0.0
    for tx in transactions:
        if tx.sub_type == DEFAULT_CREDIT_CARD_DEBT_SUB_TYPE:
            if tx.tx_type == "income":
                debt_total += tx.amount
            elif tx.tx_type == "expense":
                debt_total -= tx.amount
        
        elif tx.sub_type == CREDIT_CARD_PAYMENT_SUB_TYPE and tx.tx_type == "expense":
            debt_total -= tx.amount
    return round(max(debt_total,0.0), 2)

def compute_savings_totals(transactions: Sequence[Transaction]) -> Dict[str, float]:
    """Aggregate savings-related flows, including withdrawals."""
    totals: Dict[str, float] = {label: 0.0 for label in SAVINGS_CATEGORY_LABELS.values()}
    
    settings = read_settings()
    initial_savings_balance = settings.get("initial_savings_balance", 0.0)
    totals["savings"] = totals.get("savings", 0.0) + initial_savings_balance
    
    for tx in transactions:
        category_key = (tx.category or "").strip().lower()

        if tx.tx_type == "expense":
            if category_key in SAVINGS_CATEGORY_LABELS:
                label = SAVINGS_CATEGORY_LABELS[category_key]
                totals[label] = totals.get(label, 0.0) + tx.amount
        elif tx.tx_type == "income" and category_key in SAVINGS_WITHDRAW_CATEGORY_KEYS:
            totals["savings"] = totals.get("savings", 0.0) - tx.amount
            
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
    ) -> Transaction:
    """Convenience helper for expense transactions."""
    
    normalized_amount = normalize_amount(amount)
    cleaned_device = device.upper() if device else "OTHER"
    if cleaned_device not in ALLOWED_DEVICES:
        cleaned_device = "OTHER"
        
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
    ) -> Transaction:
    """Convenience helper for income transactions."""

    normalized_amount = normalize_amount(amount)
    cleaned_device = device.upper() if device else "OTHER"
    if cleaned_device not in ALLOWED_DEVICES:
        cleaned_device = "OTHER"

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