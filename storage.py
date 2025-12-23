"""Storage-layer helpers for MoneyTracker."""

from __future__ import annotations

import csv
import json
import os
import tempfile
import datetime
from dateutil.relativedelta import relativedelta
from pathlib import Path
from typing import Iterable, Mapping, Sequence, MutableMapping, Dict, Any, List, Optional
import shutil

# Import user manager
from user_manager import user_manager

# --- Configuration & Constants ---
DEFAULT_DATA_DIR = Path(os.getcwd() + "/MoneyTrackerdata")
USER_DATA_DIR = DEFAULT_DATA_DIR / "users"

# These are now just default filenames, actual paths will be determined at runtime
def get_transactions_path() -> Path:
    """Get the path to the current user's transactions file."""
    if not user_manager.current_user:
        raise RuntimeError("No user is currently logged in")
    user_dir = USER_DATA_DIR / user_manager.current_user
    return user_dir / "transactions.csv"

def get_settings_path() -> Path:
    """Get the path to the current user's settings file."""
    if not user_manager.current_user:
        raise RuntimeError("No user is currently logged in")
    user_dir = USER_DATA_DIR / user_manager.current_user
    return user_dir / "settings.json"

def get_older_transactions_path() -> Path:
    """Get the path for older transactions (used for monthly archiving)."""
    if not user_manager.current_user:
        raise RuntimeError("No user is currently logged in")
    user_dir = USER_DATA_DIR / user_manager.current_user
    return user_dir / "transactions_"

CSV_COLUMNS: Sequence[str] = [
    "id",
    "timestamp",
    "tx_type",
    "sub_type",
    "amount",
    "date",
    "description",
    "category",
    "device",
    "location",
    "occasion",
    "effects_balance",
    "linked_tx_id",
    "shared_flag",
    "shared_splits",
    "shared_notes",
]

# --- File System Management ---

def ensure_data_dir(data_dir: Optional[Path] = None) -> None:
    """Ensures the data directory and placeholder files exist for the current user."""
    if data_dir is None:
        if not user_manager.current_user:
            # If no user is logged in, create a temporary directory
            # This is a fallback and should only be used during initialization
            data_dir = Path("data/temp")
        else:
            data_dir = USER_DATA_DIR / user_manager.current_user
    
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Create transactions file if it doesn't exist
    transactions_path = data_dir / "transactions.csv"
    if not transactions_path.exists():
        with open(transactions_path, "w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(CSV_COLUMNS)
    
    # Create settings file if it doesn't exist
    settings_path = data_dir / "settings.json"
    if not settings_path.exists():
        write_settings_json(settings={"currency": "INR", "version": "3"}, settings_path=settings_path)

def start_new_month_transactionfile() -> None:
    """Archive the current month's transactions and start a new file."""
    if not user_manager.current_user:
        # If no user is logged in, don't do anything
        return
        
    user_dir = USER_DATA_DIR / user_manager.current_user
    transactions_path = user_dir / "transactions.csv"
    
    if not transactions_path.exists():
        return  # No transactions to archive
    
    today = datetime.date.today()
    last_month_date = today + relativedelta(months=-1)
    last_month_name = last_month_date.strftime("%B")
    
    archive_path = user_dir / f"transactions_{last_month_name}.csv"
    shutil.copyfile(transactions_path, archive_path)
    
    # Create a new empty transactions file with just the header
    with open(transactions_path, "w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(CSV_COLUMNS)

def write_settings_json(settings: Mapping[str, object], settings_path: Path) -> None:
    """Persist settings as JSON via atomic write."""
    # Helper for initial file creation
    with settings_path.open("w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, sort_keys=True)
        
# --- Settings Persistence (JSON) ---

def read_settings(settings_path: Optional[Path] = None) -> dict[str, Any]:
    """Load JSON settings into memory for the current user."""
    # Default settings
    default_settings = {
        "currency": "INR",
        "version": "3",
        "initial_balance": 0.0,
        "initial_cash_balance": 0.0,
        "initial_savings_balance": 0.0,
        "initial_savings_fd_balance": 0.0,
        "initial_savings_rd_balance": 0.0,
        "initial_savings_gold_balance": 0.0,
        "category_budgets": {}
    }
    
    # If no user is logged in and no specific path provided, return defaults
    if not user_manager.current_user and settings_path is None:
        return default_settings
        
    try:
        if settings_path is None:
            settings_path = get_settings_path()
        
        if not settings_path.exists():
            return default_settings
        
        with open(settings_path, "r", encoding="utf-8") as handle:
            try:
                data = json.load(handle)
                # Ensure all required fields exist
                for key, value in default_settings.items():
                    if key not in data:
                        data[key] = value
                # Handle legacy field names
                if "initial balance" in data and "initial_balance" not in data:
                    data["initial_balance"] = data["initial balance"]
                # Clean up legacy key if it exists
                if "initial balance" in data and "initial_balance" in data:
                    data.pop("initial balance", None)
                return data
            except json.JSONDecodeError:
                return default_settings  # Fallback if corrupted
    except (FileNotFoundError, PermissionError):
        return default_settings  # Fallback if file access fails


def write_settings(settings: Mapping[str, object], settings_path: Optional[Path] = None) -> None:
    """Persist settings as JSON via atomic write for the current user."""
    if settings_path is None:
        settings_path = get_settings_path()
    
    ensure_data_dir(settings_path.parent)
    
    with tempfile.NamedTemporaryFile(
        "w", newline="", delete=False, dir=settings_path.parent, encoding="utf-8"
    ) as tmp:
        json.dump(settings, tmp, indent=2, sort_keys=True)
        tmp.flush()

    os.replace(tmp.name, settings_path)


# --- Transaction Persistence (CSV) ---

def read_transactions(csv_path: Optional[Path] = None) -> list[dict[str, Any]]:
    """Return raw transaction rows from CSV storage for the current user."""
    # If no user is logged in and no path provided, return empty list
    if not user_manager.current_user and csv_path is None:
        return []
        
    try:
        if csv_path is None:
            csv_path = get_transactions_path()
        
        if not csv_path.exists():
            return []
        
        with open(csv_path, "r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            return list(reader)
    except (FileNotFoundError, PermissionError):
        return []  # Return empty list if file access fails


def write_transactions(transactions: Iterable[Mapping[str, object]], csv_path: Optional[Path] = None) -> None:
    """Persist entire transaction table atomically for the current user."""
    if csv_path is None:
        csv_path = get_transactions_path()
    
    ensure_data_dir(csv_path.parent)
    
    with tempfile.NamedTemporaryFile(
        "w", newline="", delete=False, dir=csv_path.parent, encoding="utf-8"
    ) as tmp:
        writer = csv.DictWriter(tmp, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        
        data_to_write: List[Dict[str, str]] = []
        for row in transactions:
            str_row = {column: str(row.get(column, "")) for column in CSV_COLUMNS}
            data_to_write.append(str_row)
            
        writer.writerows(data_to_write)
        tmp.flush()
        
    os.replace(tmp.name, csv_path)

def append_transaction(row: Mapping[str, object], csv_path: Optional[Path] = None) -> None:
    """Append one transaction row in a read-modify-write cycle for the current user."""
    if csv_path is None:
        csv_path = get_transactions_path()
        
    existing: Sequence[Mapping[str, str]] = read_transactions(csv_path)
    mutable_existing: List[Mapping[str, object]] = list(existing)
    mutable_existing.append(row)
    write_transactions(mutable_existing, csv_path)