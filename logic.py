"""Business-logic skeleton for MoneyTracker.

Contains dataclasses, validation, and computation signatures.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple, Any, Optional

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
ALLOWED_DEVICES = {"UPI", "CREDIT_CARD", "CREDIT_CARD_UPI", "CASH", "DEBIT", "BANK_TRANSFER", "OTHER", "SAVINGS_WITHDRAW"}
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
    """Calculate outstanding debt, but return 0 if a reset marker exists.
    
    Returns:
        float: The outstanding debt amount, which will be 0 if a reset marker exists,
              otherwise the calculated debt amount.
    """
    # Find all reset transactions
    reset_dates = []
    for tx in transactions:
        if (hasattr(tx, 'description') and 
            getattr(tx, 'description', '') == "CREDIT CARD DEBT RESET"):
            reset_dates.append(tx.date)
    
    # If there are any reset transactions, only consider transactions after the last reset
    if reset_dates:
        last_reset = max(reset_dates)
        transactions = [tx for tx in transactions if tx.date >= last_reset]
    
    # Track processed transaction IDs to avoid double-counting
    processed_ids = set()
    debt_total = 0.0
    
    for tx in transactions:
        # Skip reset transactions in the calculation
        if hasattr(tx, 'description') and getattr(tx, 'description', '') == "CREDIT CARD DEBT RESET":
            debt_total = 0.0  # Reset to zero when we see a reset transaction
            continue
            
        # Skip if we've already processed this transaction
        if hasattr(tx, 'id') and tx.id in processed_ids:
            continue
            
        # Handle credit card debt transactions (these are the debt portions)
        if hasattr(tx, 'sub_type') and tx.sub_type == DEFAULT_CREDIT_CARD_DEBT_SUB_TYPE:
            if tx.tx_type == "income":
                debt_total += tx.amount
                if hasattr(tx, 'id'):
                    processed_ids.add(tx.id)
            
        # Handle credit card payments (reduce debt)
        elif hasattr(tx, 'sub_type') and tx.sub_type == CREDIT_CARD_PAYMENT_SUB_TYPE and tx.tx_type == "expense":
            debt_total -= tx.amount
            if hasattr(tx, 'id'):
                processed_ids.add(tx.id)
                
        # Skip regular credit card expenses as they are already counted in the debt transaction
        elif hasattr(tx, 'device') and tx.device in CREDIT_CARD_DEVICES and tx.tx_type == "expense":
            if hasattr(tx, 'id'):
                processed_ids.add(tx.id)
            continue
    
    return round(debt_total, 2)

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

    participant_key = participant_filter.strip().lower() if participant_filter else None
    category_key = category_filter.strip().lower() if category_filter else None

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

        # Expenses add to what people owe; income (refunds) reduce it
        sign = 1.0 if tx.tx_type == "expense" else -1.0

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