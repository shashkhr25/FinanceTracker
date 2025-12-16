"""MoneyTracker – Final, Working, Modern UI"""

from __future__ import annotations
import csv
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Sequence
from kivymd.app import MDApp
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty, ObjectProperty, BooleanProperty, ListProperty, DictProperty, NumericProperty
from kivy.clock import Clock
from kivy.uix.modalview import ModalView
from kivy.uix.dropdown import DropDown
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.factory import Factory

# ------------------------------------------------------------------ #
# Storage & Logic
# ------------------------------------------------------------------ #
from storage import (
    append_transaction, 
    ensure_data_dir, 
    read_settings, 
    read_transactions, 
    write_settings, 
    start_new_month_transactionfile,
    CSV_COLUMNS
)
from logic import (
    Transaction,
    compute_balance,
    compute_cash_balance,
    compute_outstanding_debt,
    create_expense_transaction,
    create_income_transaction,
    transaction_from_row,
    transaction_to_row,
    compute_savings_totals,
    SharedSplit,
    summarize_shared_expenses,
    summarize_by_category,
    create_credit_card_expense,
    create_credit_card_payment,
    DEBT_CLEARED_CATEGORY,
    CREDIT_CARD_PAYMENT_SUB_TYPE,
    DEFAULT_CREDIT_CARD_DEBT_SUB_TYPE,
    CREDIT_CARD_DEVICES,
    SAVINGS_CATEGORY_LABELS,
    validate_transaction,
)

# Constants
SAVINGS_CATEGORY_LABELS = {"savings": "Savings"}  # Default value, should be loaded from settings
CREDIT_CARD_PAYMENT_CATEGORY_KEYS = ["CREDIT_CARD_PAYMENT"]

# ------------------------------------------------------------------ #
# KV file
# ------------------------------------------------------------------ #
KV_FILE = Path(__file__).with_name("ui.kv")


def _parse_date_or_today(raw: str | None) -> date:
    text = (raw or "").strip()
    if not text:
        return date.today()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return date.today()


class AddExpenseDialog(ModalView):
    """Modal dialog for capturing expense details"""
    parent_screen = ObjectProperty(None)
    amount_input=ObjectProperty(None)
    description_input = ObjectProperty(None)
    category_input = ObjectProperty(None)
    device_spinner = ObjectProperty(None)
    date_input = ObjectProperty(None)
    shared_checkbox = ObjectProperty(None)
    shared_participants_input = ObjectProperty(None)
    shared_notes_input = ObjectProperty(None)

    @staticmethod
    def _parse_shared_entries(raw_text: str) -> List[SharedSplit]:
        entries: List[SharedSplit] = []
        if not raw_text:
            return entries

        parts = [chunk.strip() for chunk in raw_text.split(",")]
        for part in parts:
            if not part:
                continue
            if ":" in part:
                name_raw, amount_raw = part.split(":", 1)
                name = name_raw.strip().lower()  # Convert name to lowercase
                if not name:
                    continue
                try:
                    amount = float(amount_raw.strip())
                except (TypeError, ValueError):
                    amount = None
                entries.append(SharedSplit(name=name, amount=amount))
            else:
                entries.append(SharedSplit(name=part.strip().lower(), amount=None))  # Convert name to lowercase
        return entries

    def handle_submit(self) -> None:
        if not self.parent_screen:
            return
        try:
            amount = float(self.amount_input.text)
        except ( TypeError, ValueError):
            print("Invalid amount")
            return

        txn_date = _parse_date_or_today(self.date_input.text if self.date_input else "")

        shared_flag = bool(self.shared_checkbox.active) if self.shared_checkbox else False
        participants_text = self.shared_participants_input.text if self.shared_participants_input else ""
        shared_splits = self._parse_shared_entries(participants_text) if shared_flag else []
        shared_notes = self.shared_notes_input.text.strip() if (self.shared_notes_input and shared_flag) else ""
        if shared_flag and not shared_splits:
            print("Shared expense selected but no participants provided")
            return

        self.parent_screen.submit_expense(
            amount=amount,
            description=self.description_input.text.strip(),
            category=self.category_input.text.strip(),
            device=self.device_spinner.text.strip(),
            txn_date=txn_date,
            shared_flag=shared_flag,
            shared_splits=shared_splits,
            shared_notes=shared_notes,
        )
        self.dismiss()


class SavingsInitialDialog(ModalView):
    """Dialog to edit initial savings balances by category."""

    parent_screen = ObjectProperty(None)
    savings_input = ObjectProperty(None)
    savings_fd_input = ObjectProperty(None)
    savings_rd_input = ObjectProperty(None)
    savings_gold_input = ObjectProperty(None)

    def populate_from_settings(self) -> None:
        settings = read_settings()
        fields = [
            (self.savings_input, "initial_savings_balance"),
            (self.savings_fd_input, "initial_savings_fd_balance"),
            (self.savings_rd_input, "initial_savings_rd_balance"),
            (self.savings_gold_input, "initial_savings_gold_balance"),
        ]
        for widget, key in fields:
            if widget is None:
                continue
            try:
                value = float(settings.get(key, 0.0))
            except (TypeError, ValueError):
                value = 0.0
            widget.text = f"{value:.2f}"

    def handle_save(self) -> None:
        settings = dict(read_settings())
        fields = [
            (self.savings_input, "initial_savings_balance"),
            (self.savings_fd_input, "initial_savings_fd_balance"),
            (self.savings_rd_input, "initial_savings_rd_balance"),
            (self.savings_gold_input, "initial_savings_gold_balance"),
        ]

        for widget, key in fields:
            text_value = widget.text.strip() if widget else ""
            try:
                amount = float(text_value or 0.0)
            except ValueError:
                print(f"Invalid value for {key}")
                return
            settings[key] = round(amount, 2)

        write_settings(settings)
        print("Savings balances updated")

        if self.parent_screen:
            self.parent_screen.refresh()

        self.dismiss()


class ThemedSpinnerDropdown(DropDown):
    """ Custom dropdown used to style spinners consistently"""
Factory.register("ThemedSpinnerDropdown",cls=ThemedSpinnerDropdown)


class AddIncomeDialog(ModalView):
    """Modal dialog for capturing income details"""
    parent_screen = ObjectProperty(None)
    amount_input = ObjectProperty(None)
    description_input = ObjectProperty(None)
    device_spinner = ObjectProperty(None)
    date_input = ObjectProperty(None)
    cash_toggle = BooleanProperty(False)
    shared_checkbox = ObjectProperty(None)
    shared_participants_input = ObjectProperty(None)
    shared_notes_input = ObjectProperty(None)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.register_event_type('on_cash_toggle')
        
    def on_cash_toggle(self, *args):
        pass

    @staticmethod
    def _parse_shared_entries(raw_text: str) -> List[SharedSplit]:
        # Reuse same parsing rules as expenses
        return AddExpenseDialog._parse_shared_entries(raw_text)

    def handle_submit(self) -> None:
        if not self.parent_screen:
            return
        try:
            amount = float(self.amount_input.text)
        except (TypeError,ValueError):
            print("Invalid Amount")
            return

        # Debug the cash toggle state
        cash_toggle_active = getattr(self, 'cash_toggle', False)
        print(f"Cash toggle active: {cash_toggle_active}")
        
        # Set device to CASH if the toggle is on, otherwise use the selected device
        if cash_toggle_active:
            device = "CASH"
            category_text = ""
            print(f"Setting device to CASH for amount: {amount}")
        else:
            device_text = (self.device_spinner.text or "").strip()
            device = device_text.upper()
            # Only apply savings withdrawal logic if not a cash transaction
            if device_text.lower() in ("savings withdraw", "taken from savings"):
                device = "SAVINGS_WITHDRAW"
                category_text = "Taken from Savings"
            else:
                category_text = ""
            print(f"Using device: {device}")

        txn_date = _parse_date_or_today(self.date_input.text if self.date_input else "")

        shared_flag = bool(self.shared_checkbox.active) if self.shared_checkbox else False
        participants_text = self.shared_participants_input.text if self.shared_participants_input else ""
        shared_splits = self._parse_shared_entries(participants_text) if shared_flag else []
        shared_notes = self.shared_notes_input.text.strip() if (self.shared_notes_input and shared_flag) else ""

        # Debug output
        print(f"Submitting income - Amount: {amount}, Device: {device}, Is Cash: {device == 'CASH'}")

        self.parent_screen.submit_income(
            amount=amount,
            description=self.description_input.text.strip(),
            category=category_text,
            device=device,  # This will be "CASH" if the toggle is on
            txn_date=txn_date,
            shared_flag=shared_flag,
            shared_splits=shared_splits,
            shared_notes=shared_notes,
        )
        self.dismiss()


class DashboardScreen(Screen):
   
    current_balance_text = StringProperty("0.00")
    balance_caption = StringProperty("")
    outstanding_debt_text = StringProperty("0.00")
    outstanding_debt_caption = StringProperty("")
    credit_card_debt_text = StringProperty("0.00")
    credit_card_debt_caption = StringProperty("")
    borrowed_debt_text = StringProperty("0.00")
    borrowed_debt_caption = StringProperty("")
    current_billing_cycle = StringProperty("")

    def on_pre_enter(self, *_) -> None:
        self.refresh_metrics()

    def on_kv_post(self, base_widget) -> None:
        Clock.schedule_once(lambda *_:self.refresh_metrics(),0)

    def open_add_expense(self) -> None:
        dialog = AddExpenseDialog()
        dialog.parent_screen = self
        if dialog.date_input:
            dialog.date_input.text = date.today().isoformat()
        dialog.open()

    def open_add_income(self) -> None:
        dialog = AddIncomeDialog()
        dialog.parent_screen = self
        if dialog.date_input:
            dialog.date_input.text = date.today().isoformat()
        dialog.open()

    def submit_expense(
        self,
        *,
        amount: float,
        description: str,
        category: str,
        device: str,
        txn_date: date | None = None,
        shared_flag: bool = False,
        shared_splits: Sequence[SharedSplit] | None = None,
        shared_notes: str = "",
    ) -> None:
        txn_date = txn_date or date.today()
        cleaned_device = device.strip().upper() if device else ""
        normalized_category = (category or "").strip().lower()

        transactions = []
        if normalized_category in CREDIT_CARD_PAYMENT_CATEGORY_KEYS:
            transactions.append(
                create_credit_card_payment(
                    amount=amount,
                    date_value=txn_date,
                    description=description,
                    category=category,
                    device="CREDIT_CARD",  # Explicitly set to CREDIT_CARD for payments
                )
            )
        elif "credit card" in description.lower() or "creditcard" in description.lower() or cleaned_device in CREDIT_CARD_DEVICES:
            # If description indicates it's a credit card transaction, ensure correct device
            device = "CREDIT_CARD_UPI" if "upi" in description.lower() or cleaned_device == "CREDIT_CARD_UPI" else "CREDIT_CARD"
            expense_tx, debt_tx = create_credit_card_expense(
                amount=amount,
                date_value=txn_date,
                description=description,
                category=category,
                device=device,
                shared_flag=shared_flag,
                shared_splits=shared_splits,
                shared_notes=shared_notes,
            )
            transactions.extend([expense_tx, debt_tx])
        else:
            transactions.append(
                create_expense_transaction(
                    amount = amount,
                    date_value=txn_date,
                    description=description,
                    category=category,
                    device=cleaned_device,
                    shared_flag=shared_flag,
                    shared_splits=shared_splits,
                    shared_notes=shared_notes,
                )
            )

        for tx in transactions:
            ok,errors = validate_transaction(tx)
            if not ok :
                for err in errors:
                    print(f"Validation error: {err}")
                return

        ensure_data_dir()
        for tx in transactions:
            append_transaction(transaction_to_row(tx))

        if cleaned_device in CREDIT_CARD_DEVICES:
            print("Credit card expense recorded; Debt increased")
        else:
            print("Expense Added")

        self.refresh_metrics()

        if self.manager:
            if "transactions" in self.manager.screen_names:
                transactions_screen = self.manager.get_screen("transactions")
                if hasattr(transactions_screen, "refresh"):
                    transactions_screen.refresh()

            if "category_totals" in self.manager.screen_names:
                category_screen = self.manager.get_screen("category_totals")
                if hasattr(category_screen, "refresh"):
                    category_screen.refresh()

            if "networth" in self.manager.screen_names:
                networth_screen = self.manager.get_screen("networth")
                if hasattr(networth_screen, "refresh"):
                    networth_screen.refresh()


    def submit_income(
        self,
        *,
        amount: float,
        description: str,
        category: str,
        device: str,
        txn_date: date | None = None,
        shared_flag: bool = False,
        shared_splits: Sequence[SharedSplit] | None = None,
        shared_notes: str = "",
    ) -> None:
        txn_date = txn_date or date.today()
        transaction = create_income_transaction(
            amount=amount,
            date_value=txn_date,
            description=description,
            category=category,
            device=device,
            shared_flag=shared_flag,
            shared_splits=shared_splits,
            shared_notes=shared_notes,
        )
        ok,errors = validate_transaction(transaction)
        if not ok :
            for err in errors:
                print(f"Validation error: {err}")
            return
        ensure_data_dir()
        append_transaction(transaction_to_row(transaction))
        print("Income Recorded")

        self.refresh_metrics()

        if self.manager:
            if "transactions" in self.manager.screen_names:
                transactions_screen = self.manager.get_screen("transactions")
                if hasattr(transactions_screen, "refresh"):
                    transactions_screen.refresh()

            if "category_totals" in self.manager.screen_names:
                category_screen = self.manager.get_screen("category_totals")
                if hasattr(category_screen, "refresh"):
                    category_screen.refresh()

    def refresh_metrics(self) -> None:
        ensure_data_dir()
        # Always reload transactions to ensure we have the latest data
        rows = read_transactions()
        transactions = [transaction_from_row(row) for row in rows]

        # Check if we need to clear the credit card debt
        if self.should_clear_debt():
            self.clear_outstanding_debt()
            self.mark_debt_cleared()
            # Force a reload of transactions after clearing debt
            rows = read_transactions()
            transactions = [transaction_from_row(row) for row in rows]
            
        # Ensure we have the latest transactions for calculations
        if not transactions:
            transactions = [transaction_from_row(row) for row in read_transactions()]

        settings = read_settings()
        initial_raw = settings.get("initial_balance",0)
        initial_cash_raw = settings.get("initial_cash_balance",0)
        try:
            initial_balance = float(initial_raw)
        except(TypeError,ValueError):
            initial_balance = 0.0

        try:
            initial_cash_balance = float(initial_cash_raw)
        except(TypeError,ValueError):
            initial_cash_balance = 0.0

        combined_initial_balance = initial_balance + initial_cash_balance

        balance_value = compute_balance(transactions, initial_balance=combined_initial_balance)
        cash_balance_value = compute_cash_balance(transactions, initial_cash_balance=initial_cash_balance)
        
        # Update billing cycle display
        cycle_start, cycle_end = self.get_current_billing_cycle()
        self.current_billing_cycle = f"Billing Cycle: {cycle_start.strftime('%d %b')} - {cycle_end.strftime('%d %b %Y')}"
        
        # Calculate debts using the updated function
        credit_card_debt, borrowed_debt = compute_outstanding_debt(transactions)
        total_debt = credit_card_debt + borrowed_debt
        
        # Update UI with separate debt values
        self.credit_card_debt_text = f"{credit_card_debt:,.2f}"
        self.credit_card_debt_caption = "Credit Card Balance" if credit_card_debt > 0 else "No Credit Card Debt"
        
        self.borrowed_debt_text = f"{borrowed_debt:,.2f}"
        self.borrowed_debt_caption = "Money Owed to People" if borrowed_debt > 0 else "No Money Owed"
        
        # Keep the total for backward compatibility
        self.outstanding_debt_text = f"{total_debt:,.2f}"
        self.outstanding_debt_caption = "Total Outstanding Debt"
        
        # Update the main balance display
        self.current_balance_text = f"{balance_value:,.2f}"
        self.balance_caption = f"Account Balance {(balance_value-cash_balance_value):,.2f} \n" + f"Cash balance: {cash_balance_value:.2f}"
            
    def get_current_billing_cycle(self) -> tuple[date, date]:
        """Get the start and end dates of the current billing cycle (19th to 18th of next month)."""
        today = date.today()
        if today.day >= 19:
            # Current month's 19th to next month's 18th
            start_date = date(today.year, today.month, 19)
            next_month = today.replace(day=28) + timedelta(days=4)  # Move to next month
            end_date = (date(next_month.year, next_month.month, 1) - timedelta(days=1)).replace(day=18)
        else:
            # Previous month's 19th to current month's 18th
            prev_month = (today.replace(day=1) - timedelta(days=1)).replace(day=19)
            end_date = date(today.year, today.month, 18)
            start_date = prev_month
        return start_date, end_date

    def get_previous_billing_cycle(self) -> tuple[date, date]:
        """Get the start and end dates of the previous billing cycle."""
        today = date.today()
        if today.day >= 19:
            # Previous cycle was last month's 19th to this month's 18th
            start_date = (today.replace(day=1) - timedelta(days=1)).replace(day=19)
            end_date = date(today.year, today.month, 18)
        else:
            # Previous cycle was two months ago 19th to last month's 18th
            two_months_ago = (today.replace(day=1) - timedelta(days=1)).replace(day=1) - timedelta(days=1)
            start_date = two_months_ago.replace(day=19)
            end_date = (today.replace(day=1) - timedelta(days=1)).replace(day=18)
        return start_date, end_date

    def get_outstanding_balance_for_cycle(self, start_date: date, end_date: date) -> float:
        """Calculate the outstanding balance for a specific billing cycle."""
        rows = read_transactions()
        total_debt = 0.0
        
        for row in rows:
            tx = transaction_from_row(row)
            tx_date = getattr(tx, 'date_value', None)
            
            # Skip if no date or not a relevant transaction type
            if not tx_date or not hasattr(tx, 'tx_type'):
                continue
                
            # Skip if outside the billing cycle
            if not (start_date <= tx_date <= end_date):
                continue
                
            # Handle credit card expenses (add to debt)
            if (tx.tx_type == 'expense' and 
                hasattr(tx, 'device') and 
                tx.device in {"CREDIT_CARD", "CREDIT_CARD_UPI"} and
                not (hasattr(tx, 'description') and 
                     any(x in tx.description.upper() 
                         for x in ["PAYMENT", "CLEARED", "RESET"]))):
                total_debt += abs(tx.amount)
                
            # Handle credit card payments (subtract from debt)
            elif (tx.tx_type == 'income' and 
                  hasattr(tx, 'description') and 
                  "CREDIT CARD PAYMENT" in tx.description.upper()):
                total_debt = max(0, total_debt - abs(tx.amount))
            
        return total_debt

    def clear_outstanding_debt(self) -> bool:
        """Clear the outstanding debt for the previous billing cycle.
        Returns:
            bool: True if debt was cleared, False otherwise
        """
        print("\n=== Starting debt clearance process ===")
        
        try:
            # Get the previous billing cycle
            prev_start, prev_end = self.get_previous_billing_cycle()
            print(f"Checking billing cycle: {prev_start} to {prev_end}")
            
            # Get all transactions
            rows = read_transactions()
            print(f"Found {len(rows)} total transactions")
            transactions = [transaction_from_row(row) for row in rows]
            
            # Calculate total credit card debt from the previous billing cycle
            total_debt = 0.0
            credit_card_txns = []
            
            for tx in transactions:
                # Skip if not in the previous billing cycle
                tx_date = getattr(tx, 'date_value', date.min)
                if not (prev_start <= tx_date <= prev_end):
                    continue
                    
                # Count credit card expenses (excluding payments and resets)
                if (hasattr(tx, 'tx_type') and tx.tx_type == 'expense' and 
                    hasattr(tx, 'device') and tx.device in {"CREDIT_CARD", "CREDIT_CARD_UPI"} and
                    not (hasattr(tx, 'description') and 
                         any(x in tx.description.upper() 
                             for x in ["PAYMENT", "CLEARED", "RESET"]))):
                    amount = abs(getattr(tx, 'amount', 0))
                    total_debt += amount
                    credit_card_txns.append(tx)
                    print(f"Found credit card expense: {getattr(tx, 'description', '')} - ₹{amount}")
                    
                # Subtract any payments made in this cycle
                elif (hasattr(tx, 'tx_type') and tx.tx_type == 'income' and 
                      hasattr(tx, 'description') and 
                      "CREDIT CARD PAYMENT" in tx.description.upper() and
                      prev_start <= tx_date <= prev_end):
                    payment = abs(getattr(tx, 'amount', 0))
                    total_debt = max(0, total_debt - payment)
                    print(f"Found existing credit card payment: ₹{payment}")
            
            print(f"\n=== Debt Calculation Summary ===")
            print(f"Total credit card expenses: ₹{total_debt:.2f}")
            print(f"Number of credit card transactions: {len(credit_card_txns)}")
            
            if total_debt <= 0:
                print("No debt to clear")
                self.show_popup('Info', 'No outstanding credit card debt found for the previous billing cycle.')
                return False
            
            print(f"\nCreating payment transaction for amount: ₹{total_debt:.2f}")
            
            # Create a payment transaction (expense) to clear the debt
            payment_desc = f"CREDIT CARD PAYMENT - {prev_start.strftime('%d %b')} to {prev_end.strftime('%d %b %Y')}"
            print(f"Payment description: {payment_desc}")
            
            # First, create an income transaction to record the payment
            payment_tx = create_income_transaction(
                amount=total_debt,
                date_value=date.today(),
                description=payment_desc,
                category="Credit Card Payment",
                device="BANK_TRANSFER",
                sub_type=CREDIT_CARD_PAYMENT_SUB_TYPE,
                effects_balance=True
            )
            
            # Then create an expense transaction to clear the debt
            clearance_tx = create_expense_transaction(
                amount=total_debt,
                date_value=date.today(),
                description=f"DEBT CLEARED - {payment_desc}",
                category=DEBT_CLEARED_CATEGORY,
                device="BANK_TRANSFER",
                sub_type=CREDIT_CARD_PAYMENT_SUB_TYPE,
                effects_balance=True
            )
            
            print(f"Created payment transaction: {payment_tx}")
            
            # Convert to rows and add payment markers
            payment_row = transaction_to_row(payment_tx)
            clearance_row = transaction_to_row(clearance_tx)
            print(f"Converted payment to row: {payment_row}")
            print(f"Converted clearance to row: {clearance_row}")
            
            # Save both transactions
            print("Saving payment and clearance transactions...")
            append_transaction(payment_row)
            append_transaction(clearance_row)
            print("Transactions saved successfully")
            
            # Force refresh transactions
            print("Refreshing transactions...")
            global _transactions_cache
            _transactions_cache = None  # Clear cache
            
            # Mark that we've cleared the debt for this month
            print("Marking debt as cleared...")
            self.mark_debt_cleared()
            
            # Force refresh transactions and update the UI
            print("Refreshing transactions and UI...")
            _transactions_cache = None  # Clear cache
            self.refresh_metrics()
            
            # Show confirmation message
            message = (
                f"Payment of ₹{total_debt:,.2f} recorded\n"
                f"Billing cycle: {prev_start.strftime('%d %b')} to {prev_end.strftime('%d %b %Y')}"
            )
            self.show_popup('Payment Recorded', message)
            
            # Refresh all screens
            if self.manager:
                for screen_name in ["transactions", "category_totals", "networth", "dashboard"]:
                    if screen_name in self.manager.screen_names:
                        screen = self.manager.get_screen(screen_name)
                        if hasattr(screen, "refresh"):
                            screen.refresh()
                            print(f"Refreshed screen: {screen_name}")
            
            print("\n=== Debt clearance completed successfully ===\n")
            return True
            
        except Exception as e:
            import traceback
            error_msg = f"Error clearing debt: {str(e)}\n\n{traceback.format_exc()}"
            print(error_msg)
            self.show_popup('Error', 'Failed to clear debt. Check console for details.')
            return False
    
    def _finalize_debt_clearance(self, prev_start, prev_end, debt_to_clear):
        """Finalize the debt clearance process after a short delay."""
        # This method is kept for backward compatibility but is no longer used
        # as the functionality has been moved to clear_outstanding_debt
        pass
        
    def should_clear_debt(self) -> bool:
        """Check if we should clear the credit card debt (19th of each month)."""
        today = date.today()
        if today.day != 19:  # Only clear on the 19th
            return False
            
        # Check if we've already cleared this month
        settings = read_settings()
        last_cleared = settings.get("last_debt_cleared")
        if last_cleared:
            try:
                last_cleared_date = datetime.strptime(last_cleared, "%Y-%m-%d").date()
                if last_cleared_date.year == today.year and last_cleared_date.month == today.month:
                    return False
            except (ValueError, TypeError):
                pass
                
        return True

    def mark_debt_cleared(self) -> None:
        """Mark that the debt has been cleared for the current month."""
        settings = read_settings()
        settings["last_debt_cleared"] = date.today().strftime("%Y-%m-%d")
        write_settings(settings)
        
    def show_popup(self, title: str, message: str) -> None:
        """Helper method to show a popup message."""
        from kivy.clock import Clock
        from kivy.uix.popup import Popup
        from kivy.uix.label import Label
        
        popup = Popup(
            title=title,
            content=Label(text=message, halign='center', valign='middle'),
            size_hint=(None, None),
            size=(400, 200)
        )
        popup.open()
        
        # Close the popup after 3 seconds
        Clock.schedule_once(lambda dt: popup.dismiss(), 3)
        
        # Also refresh other screens if they exist
        if self.manager:
            if "transactions" in self.manager.screen_names:
                transactions_screen = self.manager.get_screen("transactions")
                if hasattr(transactions_screen, "refresh"):
                    transactions_screen.refresh()
                    
            if "category_totals" in self.manager.screen_names:
                category_screen = self.manager.get_screen("category_totals")
                if hasattr(category_screen, "refresh"):
                    category_screen.refresh()
                    
            if "networth" in self.manager.screen_names:
                networth_screen = self.manager.get_screen("networth")
                if hasattr(networth_screen, "refresh"):
                    networth_screen.refresh()


class TransactionsScreen(Screen):
    rv = ObjectProperty(None)
    empty_label = ObjectProperty(None)
    filter_text_input = ObjectProperty(None)
    filter_device_input = ObjectProperty(None)
    filter_category_input = ObjectProperty(None)
    sort_ascending = BooleanProperty(False)

    def on_pre_enter(self, *_) -> None:
        self.refresh()

    def toggle_sort_order(self) -> None:
        """Toggle between ascending and descending sort order by date."""
        self.sort_ascending = not self.sort_ascending
        self.refresh()
        
    def update_sort_button_text(self, button):
        """Update the sort button text based on current sort order."""
        button.text = f"Sort: {'Oldest First' if self.sort_ascending else 'Newest First'}"
        
    def refresh(self) -> None:
        ensure_data_dir()
        rows = read_transactions()
        transactions = [transaction_from_row(row) for row in rows]
        # Sort by transaction date with order based on sort_ascending
        transactions.sort(key=lambda tx: tx.date, reverse=not self.sort_ascending)

        text_filter = (self.filter_text_input.text or "").strip().lower() if self.filter_text_input else ""
        device_filter = (self.filter_device_input.text or "").strip().lower() if self.filter_device_input else ""
        category_filter = (self.filter_category_input.text or "").strip().lower() if self.filter_category_input else ""

        def _matches_filters(tx) -> bool:
            if text_filter:
                haystack = " ".join(
                    [
                        tx.description or "",
                        tx.category or "",
                        tx.device or "",
                    ]
                ).lower()
                if text_filter not in haystack:
                    return False
            if device_filter:
                if not (tx.device or "").lower().startswith(device_filter):
                    return False
            if category_filter:
                if not (tx.category or "").lower().startswith(category_filter):
                    return False
            return True

        if text_filter or device_filter or category_filter:
            transactions = [tx for tx in transactions if _matches_filters(tx)]

        data = []
        for tx in transactions:
            sign = "-" if tx.tx_type == "expense" else "+"
            amount_color = "#FCA5A5FF" if tx.tx_type == "expense" else "#86EFACFF"
            data.append(
                {
                    "date_text" : tx.date.strftime("%d %b %Y"),
                    "category_text" : tx.category or "Uncategorised",
                    "description_text": tx.description or tx.sub_type.replace("_"," ").title(),
                    "device_text" : tx.device or "-",
                    "amount_text": f"{sign}{tx.amount:,.2f}",
                    "amount_color" : amount_color,
                    "shared_text": self._format_shared_text(tx),
                    "transaction_id": tx.id  # Add transaction ID for deletion
                }
            )

        if self.rv:
            self.rv.data=data
        if self.empty_label:
            if data:
                self.empty_label.opacity = 0
                self.empty_label.height = 0
            else:
                self.empty_label.opacity = 1
                self.empty_label.height = dp(32)

    def clear_filters(self) -> None:
        if self.filter_text_input:
            self.filter_text_input.text = ""
        if self.filter_device_input:
            self.filter_device_input.text = ""
        if self.filter_category_input:
            self.filter_category_input.text = ""
        self.refresh()

    @staticmethod
    def _format_shared_text(tx) -> str:
        if not tx.shared_flag or not tx.shared_splits:
            return ""
        names = ", ".join(split.name for split in tx.shared_splits)
        base = f"Shared with: {names}" if names else "Shared expense"
        if tx.shared_notes:
            return f"{base} | {tx.shared_notes}"
        return base
        
    def delete_transaction(self, transaction_id: str) -> None:
        """Delete a transaction by its ID and refresh the list."""
        # Read all transactions
        rows = read_transactions()
        
        # Filter out the transaction to delete
        updated_rows = [row for row in rows if row['id'] != transaction_id]
        
        # If no transaction was deleted, do nothing
        if len(updated_rows) == len(rows):
            print(f"No transaction found with ID: {transaction_id}")
            return
            
        # Write the updated transactions back to the file
        with open('data/transactions.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(updated_rows)
            
        print(f"Deleted transaction with ID: {transaction_id}")
        
        # Refresh the transactions list
        self.refresh()
        
        # Refresh other screens if they exist
        if self.manager:
            if "dashboard" in self.manager.screen_names:
                dashboard = self.manager.get_screen("dashboard")
                if hasattr(dashboard, 'refresh_metrics'):
                    dashboard.refresh_metrics()
                    
            if "category_totals" in self.manager.screen_names:
                category_screen = self.manager.get_screen("category_totals")
                if hasattr(category_screen, 'refresh'):
                    category_screen.refresh()
                    
            if "networth" in self.manager.screen_names:
                networth_screen = self.manager.get_screen("networth")
                if hasattr(networth_screen, 'refresh'):
                    networth_screen.refresh()
                    
    def edit_transaction(self, transaction_id: str) -> None:
        """Edit a transaction by its ID."""
        # Read all transactions
        rows = read_transactions()
        
        # Find the transaction to edit
        transaction_to_edit = None
        for row in rows:
            if row['id'] == transaction_id:
                transaction_to_edit = row
                break
                
        if not transaction_to_edit:
            print(f"No transaction found with ID: {transaction_id}")
            return
        
        # Determine if it's an income or expense
        is_income = transaction_to_edit.get('tx_type', '').lower() == 'income'
        
        # Use the appropriate dialog based on transaction type
        if is_income:
            dialog = AddIncomeDialog()
            # Set the cash toggle if needed
            if hasattr(dialog, 'cash_toggle'):
                dialog.cash_toggle = transaction_to_edit.get('device', '').lower() == 'cash'
        else:
            dialog = AddExpenseDialog()
        
        dialog.parent_screen = self
        dialog.transaction_id = transaction_id  # Store the transaction ID for saving
        
        # Set the title based on transaction type
        dialog.title = f"Edit {'Income' if is_income else 'Expense'}"
        
        # Pre-fill the form with existing values
        if hasattr(dialog, 'amount_input') and dialog.amount_input:
            dialog.amount_input.text = str(transaction_to_edit.get('amount', ''))
            
        if hasattr(dialog, 'description_input') and dialog.description_input:
            dialog.description_input.text = transaction_to_edit.get('description', '')
            
        if hasattr(dialog, 'date_input') and dialog.date_input:
            dialog.date_input.text = transaction_to_edit.get('date', date.today().isoformat())
        
        # Handle device selection
        if hasattr(dialog, 'device_spinner') and dialog.device_spinner:
            device = transaction_to_edit.get('device', '')
            # For income, we need to handle the device spinner differently
            if is_income:
                # Map the device to the appropriate value in the income dialog
                if device.upper() == 'CASH':
                    dialog.device_spinner.text = 'Paycheck'  # Default for cash income
                    if hasattr(dialog, 'cash_toggle'):
                        dialog.cash_toggle = True
                else:
                    dialog.device_spinner.text = device.capitalize() if device else 'Paycheck'
            else:
                # For expenses, just set the device as is
                if device.upper() in [d.upper() for d in dialog.device_spinner.values]:
                    dialog.device_spinner.text = device.upper()
                elif device:  # If device not in standard values but exists, add it
                    dialog.device_spinner.values = list(dialog.device_spinner.values) + [device.upper()]
                    dialog.device_spinner.text = device.upper()
        
        # Handle shared transaction fields
        shared_flag = transaction_to_edit.get('shared_flag', 'false').lower() == 'true'
        if hasattr(dialog, 'shared_checkbox'):
            dialog.shared_checkbox.active = shared_flag
            
            if hasattr(dialog, 'shared_participants_input'):
                if shared_flag:
                    # Get the shared splits if they exist
                    shared_splits = transaction_to_edit.get('shared_splits', '')
                    if shared_splits:
                        try:
                            # Parse the shared splits if they're in JSON format
                            import json
                            splits = json.loads(shared_splits)
                            if isinstance(splits, list) and all(isinstance(s, dict) for s in splits):
                                # Format as name:amount or just name
                                parts = []
                                for s in splits:
                                    if 'amount' in s and s['amount'] not in (None, ''):
                                        parts.append(f"{s['name']}:{s['amount']}")
                                    else:
                                        parts.append(s['name'])
                                dialog.shared_participants_input.text = ", ".join(parts)
                            else:
                                dialog.shared_participants_input.text = str(shared_splits)
                        except (json.JSONDecodeError, TypeError):
                            dialog.shared_participants_input.text = str(shared_splits)
                    else:
                        dialog.shared_participants_input.text = transaction_to_edit.get('shared_participants', '')
                
                # Show/hide the shared fields based on the shared flag
                if hasattr(dialog, 'shared_notes_input'):
                    dialog.shared_notes_input.text = transaction_to_edit.get('shared_notes', '')
                    dialog.shared_notes_input.disabled = not shared_flag
                    dialog.shared_notes_input.opacity = 1.0 if shared_flag else 0.0
                    
                    # Force update the layout to show/hide the shared fields
                    if hasattr(dialog, 'shared_participants_input'):
                        dialog.shared_participants_input.disabled = not shared_flag
                        dialog.shared_participants_input.opacity = 1.0 if shared_flag else 0.0
                        dialog.shared_participants_input.size_hint_y = 1.0 if shared_flag else 0.0
                        dialog.shared_participants_input.height = dp(46) if shared_flag else 0
                        
                        # Trigger a layout update
                        if dialog.shared_participants_input.parent:
                            dialog.shared_participants_input.parent.do_layout()
        
        # Open the dialog
        dialog.open()
        
        # Override the submit handler to use our custom save method
        original_handle_submit = dialog.handle_submit
        
        def handle_submit_wrapper():
            # Get the transaction data from the dialog
            try:
                amount = float(dialog.amount_input.text)
            except (TypeError, ValueError):
                print("Invalid amount")
                return
                
            description = dialog.description_input.text.strip()
            device = dialog.device_spinner.text.strip().upper() if hasattr(dialog, 'device_spinner') else ""
            category = dialog.category_input.text.strip() if hasattr(dialog, 'category_input') else ""
            txn_date = _parse_date_or_today(dialog.date_input.text if hasattr(dialog, 'date_input') else "")
            
            # Get shared transaction details if available
            shared_flag = dialog.shared_checkbox.active if hasattr(dialog, 'shared_checkbox') else False
            shared_participants = dialog.shared_participants_input.text if hasattr(dialog, 'shared_participants_input') else ""
            shared_notes = dialog.shared_notes_input.text.strip() if hasattr(dialog, 'shared_notes_input') else ""
            
            # Save the edited transaction
            self._save_edited_transaction(
                transaction_id=dialog.transaction_id,
                amount=amount,
                description=description,
                category=category,
                device=device,
                txn_date=txn_date,
                shared_flag=shared_flag,
                shared_participants=shared_participants,
                shared_notes=shared_notes
            )
            
            # Dismiss the dialog
            dialog.dismiss()
        
        # Replace the original submit handler
        dialog.handle_submit = handle_submit_wrapper
        
        # Open the dialog
        dialog.open()
        
    def _save_edited_transaction(
        self,
        transaction_id: str,
        amount: float,
        description: str,
        category: str,
        device: str,
        txn_date: date,
        shared_flag: bool = False,
        shared_participants: str = "",
        shared_notes: str = ""
    ) -> None:
        """Save the edited transaction details."""
        try:
            # Read all transactions
            rows = read_transactions()
            
            # Find and update the transaction
            transaction_updated = False
            for row in rows:
                if row['id'] == transaction_id:
                    # Format amount to 2 decimal places
                    row['amount'] = f"{amount:.2f}"
                    row['description'] = description
                    row['category'] = category
                    row['device'] = device
                    row['date'] = txn_date.strftime('%Y-%m-%d')
                    row['shared_flag'] = '1' if shared_flag else '0'
                    row['shared_splits'] = shared_participants  # Using shared_splits instead of shared_participants
                    row['shared_notes'] = shared_notes
                    transaction_updated = True
                    break
            
            if not transaction_updated:
                print(f"Error: Transaction with ID {transaction_id} not found")
                return
            
            # Ensure data directory exists
            os.makedirs('data', exist_ok=True)
            
            # Write the updated transactions back to the file
            with open('data/transactions.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
                writer.writeheader()
                writer.writerows(rows)
                
            print(f"Successfully updated transaction with ID: {transaction_id}")
            
            # Dismiss the dialog if it exists
            if hasattr(self, 'dialog') and self.dialog:
                self.dialog.dismiss()
            
            # Refresh the transactions list and other screens
            self.refresh()
            if self.manager:
                if "dashboard" in self.manager.screen_names:
                    dashboard = self.manager.get_screen("dashboard")
                    if hasattr(dashboard, 'refresh_metrics'):
                        dashboard.refresh_metrics()
                
                if "networth" in self.manager.screen_names:
                    networth = self.manager.get_screen("networth")
                    if hasattr(networth, 'refresh'):
                        networth.refresh()
        except Exception as e:
            print(f"Error updating transaction: {e}")


class NetWorthScreen(Screen):
    liquid_balance_text = StringProperty("0.00")
    liquid_balance_caption = StringProperty("")
    outstanding_debt_text = StringProperty("0.00")
    outstanding_debt_caption = StringProperty("")
    total_savings_text = StringProperty("0.00")
    savings_summary = ListProperty([])
    credit_card_debt_text = StringProperty("0.00")
    credit_card_debt_caption = StringProperty("")
    borrowed_debt_text = StringProperty("0.00")
    borrowed_debt_caption = StringProperty("")
    savings_display = StringProperty("0.00")
    savings_fd_display = StringProperty("0.00")
    savings_rd_display = StringProperty("0.00")
    savings_gold_display = StringProperty("0.00")

    def on_pre_enter(self, *_) -> None:
        self.refresh()
    
    def populate_settings(self) -> None:
        settings = read_settings()
        mapping = {
            "savings_display": settings.get("initial_savings_balance", 0.0),
            "savings_fd_display": settings.get("initial_savings_fd_balance", 0.0),
            "savings_rd_display": settings.get("initial_savings_rd_balance", 0.0),
            "savings_gold_display": settings.get("initial_savings_gold_balance", 0.0),
        }
        for attr, raw_value in mapping.items():
            try:
                amount = float(raw_value)
            except (TypeError, ValueError):
                amount = 0.0
            setattr(self, attr, f"{amount:,.2f}")

    def on_kv_post(self, base_widget) -> None:
        Clock.schedule_once(lambda *_:self.refresh(),0)

    def refresh(self) -> None:
        try:
            transactions = []
            for row in read_transactions():
                try:
                    transactions.append(transaction_from_row(row))
                except Exception as e:
                    print(f"Error loading transaction: {e}")
                    continue

            settings = read_settings()
            initial_balance = float(settings.get("initial_balance", 0))
            initial_cash_balance = float(settings.get("initial_cash_balance", 0))
            combined_initial_balance = initial_balance + initial_cash_balance

            # Calculate balances and debts
            balance_value = compute_balance(transactions, initial_balance=combined_initial_balance)
            cash_balance = compute_cash_balance(transactions, initial_cash_balance=initial_cash_balance)
            credit_card_debt, borrowed_debt = compute_outstanding_debt(transactions)
            total_debt = credit_card_debt + borrowed_debt
            
            # Calculate savings
            savings_total = compute_savings_totals(transactions)
            total_savings = sum(savings_total.values())
            
            # Update UI
            self.savings_display = f"{savings_total['Savings']:,.2f}"
            self.savings_fd_display = f"{savings_total['Savings FD']:,.2f}"
            self.savings_rd_display = f"{savings_total['Savings RD']:,.2f}"
            self.savings_gold_display = f"{savings_total['Savings Gold']:,.2f}"
            
            self.liquid_balance_text = f"{balance_value:,.2f}"
            self.liquid_balance_caption = f"Account: {balance_value - cash_balance:,.2f}\nCash: {cash_balance:,.2f}"
            
            # Update debt properties
            self.outstanding_debt_text = f"{total_debt:,.2f}"
            self.credit_card_debt_text = f"{credit_card_debt:,.2f}"
            self.borrowed_debt_text = f"{borrowed_debt:,.2f}"
            
            if total_debt > 0:
                self.outstanding_debt_caption = f"Credit Card: {credit_card_debt:,.2f}\nBorrowed: {borrowed_debt:,.2f}"
                self.credit_card_debt_caption = "Credit Card Balance" if credit_card_debt > 0 else "No Credit Card Debt"
                self.borrowed_debt_caption = "Money Owed to People" if borrowed_debt > 0 else "No Money Owed"
            else:
                self.outstanding_debt_caption = "No outstanding debt"
                self.credit_card_debt_caption = "No Credit Card Debt"
                self.borrowed_debt_caption = "No Money Owed"

            self.total_savings_text = f"{total_savings:,.2f}"
            
            # Update the savings summary list
            self.savings_summary = [
                {"category": key, "amount": f"{value:,.2f}"}
                for key, value in savings_total.items()
            ]
            
        except Exception as e:
            print(f"Error in refresh: {e}")
            import traceback
            traceback.print_exc()

class CategoryTotalsScreen(Screen):
    category_summary = ListProperty([])
    filter_text_input = ObjectProperty(None)
    filter_month_input = ObjectProperty(None)
    filter_year_input = ObjectProperty(None)

    def on_pre_enter(self, *_) -> None:
        self.initialize_filters()
        self.refresh()

    def refresh(self) -> None:
        ensure_data_dir()
        rows = read_transactions()
        transactions = [transaction_from_row(row) for row in rows]
        
        # Get month/year filters, default to current month
        current_date = date.today()
        month_filter = (self.filter_month_input.text or "").strip() if self.filter_month_input else str(current_date.month)
        year_filter = (self.filter_year_input.text or "").strip() if self.filter_year_input else str(current_date.year)
        
        # Filter transactions by month and year
        if month_filter.isdigit() and year_filter.isdigit():
            target_month = int(month_filter)
            target_year = int(year_filter)
            transactions = [tx for tx in transactions if tx.date.month == target_month and tx.date.year == target_year]
        
        # Get text filter
        text_filter = (self.filter_text_input.text or "").strip().lower() if self.filter_text_input else ""

        settings = read_settings()
        budget_raw = settings.get("category_budgets",{}) if isinstance(settings,dict) else {}
        budgets : Dict[str,float] = {}
        for name, value in budget_raw.items():
            try:
                budgets[name] = float(value)
            except(TypeError,ValueError):
                continue

        category_totals = summarize_by_category(transactions)
        formatted = []
        for category,totals in sorted(category_totals.items(),key=lambda item : item[0].lower()):
            # Apply text filter
            if text_filter and text_filter not in category.lower():
                continue
                
            budget =  budgets.get(category,0.0)
            if budget > 0:
                variance = budget - totals
                variance_text = f"{variance:,.2f}"
                variance_color = "#86EFACFF" if variance >=0 else "#FCA5A5FF"
                budget_text = f"{budget:,.2f}"
            else:
                variance_text = "-"
                variance_color = "#94A3B8FF" 
                budget_text = ""
            formatted.append(
                {
                    "category_text":category,
                    "amount_text": f"{totals:,.2f}",
                    "amount_color": "#FCA5A5FF",
                    "budget_text": budget_text,
                    "variance_text":variance_text,
                    "variance_color":variance_color,
                    "screen_name":"category_totals"
                }
            )

        self.category_summary = formatted
        
    def clear_filters(self) -> None:
        current_date = date.today()
        if self.filter_text_input:
            self.filter_text_input.text = ""
        if self.filter_month_input:
            self.filter_month_input.text = str(current_date.month)
        if self.filter_year_input:
            self.filter_year_input.text = str(current_date.year)
        self.refresh()
        
    def initialize_filters(self) -> None:
        current_date = date.today()
        if self.filter_month_input and not self.filter_month_input.text:
            self.filter_month_input.text = str(current_date.month)
        if self.filter_year_input and not self.filter_year_input.text:
            self.filter_year_input.text = str(current_date.year)

    def handle_budget_input(self,category:str, raw_value:str) -> None:
        text_value = (raw_value or "").strip()
        if not text_value:
            budget_value = 0.0
        else:
            cleaned = text_value.replace("","").replace(",","")
            try:
                budget_value = float(cleaned)
            except ValueError:
                return
        settings = dict(read_settings())
        budgets = dict(settings.get("category_budgets",{}))

        if budget_value <= 0:
            budgets.pop(category,None)
        else:
            budgets[category] = round(budget_value,2)

        settings["category_budgets"] = budgets
        write_settings(settings)
        self.refresh()


class SharedExpensesScreen(Screen):
    summary_data = ListProperty([])
    detail_data = ListProperty([])
    participant_input = ObjectProperty(None)
    category_input = ObjectProperty(None)
    total_shared_text = StringProperty("0.00")
    summary_caption = StringProperty("No participants yet")
    detail_caption = StringProperty("No shared transactions yet")
    filters_caption = StringProperty("All participants • All categories")

    def on_pre_enter(self, *_) -> None:
        self.refresh()

    def refresh(self) -> None:
        ensure_data_dir()
        rows = read_transactions()
        transactions = [transaction_from_row(row) for row in rows]
        participant = (self.participant_input.text or "").strip() if self.participant_input else ""
        category = (self.category_input.text or "").strip() if self.category_input else ""
        summary, details = summarize_shared_expenses(
            transactions,
            participant_filter=participant or None,
            category_filter=category or None,
        )
        sorted_summary = sorted(summary.items(), key=lambda item: item[1], reverse=True)
        self.summary_data = [
            {
                "label_text": name,
                "amount_text": f"{value:,.2f}",
            }
            for name, value in sorted_summary
        ]
        total_shared = sum(summary.values())
        self.total_shared_text = f"{total_shared:,.2f}"
        self.summary_caption = self._format_summary_caption(len(summary))
        self.detail_caption = self._format_detail_caption(len(details))
        self.filters_caption = self._format_filters_caption(participant, category)

        participant_lookup = participant.lower() if participant else ""
        detail_rows = []
        for tx, allocations in details:
            participants_text = " • ".join(
                f"{name} ({amount:,.2f})" for name, amount in sorted(allocations.items())
            )
            share_text = ""
            if participant_lookup:
                for name, amount in allocations.items():
                    if name.lower() == participant_lookup:
                        share_text = f"Your share: {amount:,.2f}"
                        break

            detail_rows.append(
                {
                    "date_text": tx.date.strftime("%d %b %Y"),
                    "category_text": tx.category or "Uncategorised",
                    "description_text": tx.description or tx.sub_type.replace("_", " ").title(),
                    "amount_text": f"{tx.amount:,.2f}",
                    "participants_text": participants_text or "No participants recorded",
                    "notes_text": tx.shared_notes or "",
                    "share_text": share_text,
                }
            )
        self.detail_data = detail_rows

    def handle_filter_change(self) -> None:
        self.refresh()

    def clear_filters(self) -> None:
        if self.participant_input:
            self.participant_input.text = ""
        if self.category_input:
            self.category_input.text = ""
        self.refresh()


    def handle_budget_input(self,category:str, raw_value:str) -> None:
        text_value = (raw_value or "").strip()
        if not text_value:
            budget_value = 0.0
        else:
            cleaned = text_value.replace("","").replace(",","")
            try:
                budget_value = float(cleaned)
            except ValueError:
                return
        settings = dict(read_settings())
        budgets = dict(settings.get("category_budgets",{}))

        if budget_value <= 0:
            budgets.pop(category,None)
        else:
            budgets[category] = round(budget_value,2)

        settings["category_budgets"] = budgets
        write_settings(settings)
        self.refresh()

    @staticmethod
    def _format_filters_caption(participant: str, category: str) -> str:
        participant_label = participant or "All participants"
        category_label = category or "All categories"
        return f"{participant_label} • {category_label}"

    @staticmethod
    def _format_summary_caption(count: int) -> str:
        if count <= 0:
            return "0 participants"
        suffix = "participant" if count == 1 else "participants"
        return f"{count} {suffix}"

    @staticmethod
    def _format_detail_caption(count: int) -> str:
        if count <= 0:
            return "0 shared transactions"
        suffix = "transaction" if count == 1 else "transactions"
        return f"{count} shared {suffix}"


class SettingsScreen(Screen):
    initial_balance_input = ObjectProperty(None)
    initial_cash_input = ObjectProperty(None)

    def on_pre_enter(self, *_) -> None:
        self.populate_settings()
    
    def populate_settings(self) -> None:
        settings = read_settings()
        initial_balance = settings.get("initial_balance", 0.0)
        initial_cash = settings.get("initial_cash_balance", 0.0)
        if self.initial_balance_input:
            self.initial_balance_input.text = f"{float(initial_balance):.2f}"
        if self.initial_cash_input:
            self.initial_cash_input.text = f"{float(initial_cash):.2f}"

    def refresh(self) -> None:
        self.populate_settings()

    def save_settings(self) -> None:
        if not self.initial_balance_input or not self.initial_cash_input:
            return
        balance_text = self.initial_balance_input.text.strip()
        cash_text = self.initial_cash_input.text.strip()
        try:
            initial_balance = float(balance_text or 0)
        except ValueError:
            print("Invalid initial balance")
            return
        try:
            initial_cash = float(cash_text or 0)
        except ValueError:
            print("Invalid initial cash balance")
            return
        settings = dict(read_settings())
        settings["initial_balance"] = round(initial_balance,2)
        settings["initial_cash_balance"] = round(initial_cash,2)
        write_settings(settings)
        print("Settings saved")

    def open_initial_savings_dialog(self) -> None:
        dialog = SavingsInitialDialog()
        dialog.parent_screen = self
        dialog.populate_from_settings()
        dialog.open()

    def clear_outstanding_debt(self) -> None:
        # Get the dashboard screen and call its clear_outstanding_debt method
        if self.manager and "dashboard" in self.manager.screen_names:
            dashboard_screen = self.manager.get_screen("dashboard")
            if hasattr(dashboard_screen, "clear_outstanding_debt"):
                # Call the method and check if it was successful
                success = dashboard_screen.clear_outstanding_debt()
                
                # Show appropriate popup based on success
                from kivy.uix.popup import Popup
                from kivy.uix.label import Label
                from kivy.clock import Clock
                
                if success:
                    popup = Popup(
                        title='Success',
                        content=Label(
                            text='Credit card debt has been cleared for the previous billing cycle.',
                            halign='center',
                            valign='middle'
                        ),
                        size_hint=(None, None), 
                        size=(400, 200)
                    )
                else:
                    popup = Popup(
                        title='Info',
                        content=Label(
                            text='No outstanding credit card debt found to clear.',
                            halign='center',
                            valign='middle'
                        ),
                        size_hint=(None, None), 
                        size=(400, 200)
                    )
                
                popup.open()
                # Close the popup after 3 seconds
                Clock.schedule_once(lambda dt: popup.dismiss(), 3)
                
                # Refresh all screens
                for screen_name in ["transactions", "category_totals", "networth", "dashboard"]:
                    if screen_name in self.manager.screen_names:
                        screen = self.manager.get_screen(screen_name)
                        if hasattr(screen, "refresh"):
                            screen.refresh()

    def start_new_month(self) -> None:
        start_new_month_transactionfile()

class MoneyTrackerScreenManager(ScreenManager):
        """ commenting block
        new line of comments
        """


class MoneyTrackerApp(MDApp):
    config_state = DictProperty({})
    def build(self) -> ScreenManager:
        ensure_data_dir()
        if KV_FILE.exists():
            return Builder.load_file(str(KV_FILE))

        return Builder.load_string("\n".join(self._fallback_kv()))

    def on_start(self) -> None:
        """ commenting block
        new line of comments
        """

    def on_stop(self) -> None:
             """ commenting block
        new line of comments
        """

    @staticmethod
    def _fallback_kv() -> list[str]:
        return [
            "<DashboardScreen>:\n name: 'dashboard'\n",
            "<TransactionsScreen>:\n name: 'transactions'\n",
            "<NetWorthScreen>:\n name: 'Networth'\n",
            "<SettingsScreen>:\n name: 'Settings'\n",
            "<MoneyTrackerScreenManager>:\n DashboardScreen:\n TransactionsScreen:\n NetWorthScreen:\n SettingsScreen:\n ",
        ]
    #comment



def main() -> None:
    MoneyTrackerApp().run()

if __name__== "__main__":
    main()
