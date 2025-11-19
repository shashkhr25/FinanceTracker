"""Storage-layer helpers for MoneyTracker."""

from __future__ import annotations

import csv
import json
import os
import tempfile
import datetime
from dateutil.relativedelta import relativedelta
from pathlib import Path
from typing import Iterable, Mapping, Sequence, MutableMapping, Dict, Any, List
import shutil
# --- Configuration & Constants ---

DEFAULT_DATA_DIR = Path("data")
TRANSACTIONS_CSV = DEFAULT_DATA_DIR / "transactions.csv"
OLDER_TRANSACTIONS_CSV = DEFAULT_DATA_DIR / "transactions_"
SETTINGS_JSON = DEFAULT_DATA_DIR / "settings.json"

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
# ... (ensure_data_dir implementation is correct from previous response)
def ensure_data_dir(data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Ensures the data directory and placeholder files exist."""
    data_dir.mkdir(parents=True, exist_ok=True)
    if not TRANSACTIONS_CSV.exists():
        with open(TRANSACTIONS_CSV, "w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(CSV_COLUMNS) # Simplified header writing
    if not SETTINGS_JSON.exists():
        write_settings_json(settings={"currency": "INR", "version": "3"}, settings_path=SETTINGS_JSON)

def start_new_month_transactionfile(data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Ensures the data directory and placeholder files exist."""
    data_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today()
    last_month_date = today + relativedelta(months=-1)
    last_month_name = last_month_date.strftime("%B")
    if TRANSACTIONS_CSV.exists():
        shutil.copyfile(TRANSACTIONS_CSV , str(OLDER_TRANSACTIONS_CSV) +last_month_name+".csv" )
        os.remove(TRANSACTIONS_CSV)

def write_settings_json(settings: Mapping[str, object], settings_path: Path) -> None:
    """Persist settings as JSON via atomic write."""
    # Helper for initial file creation
    with settings_path.open("w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, sort_keys=True)
        
# --- Settings Persistence (JSON) ---

def read_settings(settings_path: Path = SETTINGS_JSON) -> Mapping[str, Any]:
    """Load JSON settings into memory."""
    ensure_data_dir(settings_path.parent)

    if not settings_path.exists():
        return {
            "initial_balance": 0.0,
            "initial_cash_balance": 0.0,
            "initial_savings_balance": 0.0,
            "initial_savings_fd_balance": 0.0,
            "initial_savings_rd_balance": 0.0,
            "initial_savings_gold_balance": 0.0,
            "category_budgets": {},
        }

    with settings_path.open("r", encoding="utf-8") as handle:
        try:
            data: Dict[str, Any] = json.load(handle)
            if "initial_balance" not in data:
                data["initial_balance"] = data.get("initial balance", 0.0)
            if "initial_cash_balance" not in data:
                data["initial_cash_balance"] = 0.0
            if "initial_savings_balance" not in data:
                data["initial_savings_balance"] = 0.0
            if "initial_savings_fd_balance" not in data:
                data["initial_savings_fd_balance"] = 0.0
            if "initial_savings_rd_balance" not in data:
                data["initial_savings_rd_balance"] = 0.0
            if "initial_savings_gold_balance" not in data:
                data["initial_savings_gold_balance"] = 0.0
            if "category_budgets" not in data or not isinstance(data["category_budgets"], dict):
                data["category_budgets"] = {}
            # Clean legacy key
            if "initial balance" in data and "initial_balance" in data:
                data.pop("initial balance", None)
            return data
        except json.JSONDecodeError:
            return {
                "initial_balance": 0.0,
                "initial_cash_balance": 0.0,
                "initial_savings_balance": 0.0,
                "initial_savings_fd_balance": 0.0,
                "initial_savings_rd_balance": 0.0,
                "initial_savings_gold_balance": 0.0,
                "category_budgets": {},
            }


def write_settings(settings: Mapping[str, object], settings_path: Path = SETTINGS_JSON) -> None:
    """Persist settings as JSON via atomic write."""
    ensure_data_dir(settings_path.parent)
    
    with tempfile.NamedTemporaryFile(
        "w", newline="", delete=False, dir=settings_path.parent, encoding="utf-8"
    ) as tmp:
        json.dump(settings, tmp, indent=2, sort_keys=True)
        tmp.flush()

    os.replace(tmp.name, settings_path)


# --- Transaction Persistence (CSV) ---

def read_transactions(csv_path: Path = TRANSACTIONS_CSV) -> Sequence[Mapping[str, str]]:
    """Return raw transaction rows from CSV storage."""
    ensure_data_dir(csv_path.parent)

    if not csv_path.exists():
        return []

    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def write_transactions(transactions: Iterable[Mapping[str, object]], csv_path: Path = TRANSACTIONS_CSV) -> None:
    """Persist entire transaction table atomically."""
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

def append_transaction(row: Mapping[str, object], csv_path: Path = TRANSACTIONS_CSV) -> None:
    """Append one transaction row in a read-modify-write cycle."""
    existing: Sequence[Mapping[str, str]] = read_transactions(csv_path)
    mutable_existing: List[Mapping[str, object]] = list(existing)
    mutable_existing.append(row)
    write_transactions(mutable_existing, csv_path)