"""MoneyTracker – Final, Working, Modern UI with User Management"""

import csv
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Sequence, Optional
from kivymd.app import MDApp
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.properties import (
    StringProperty,
    ObjectProperty,
    ListProperty,
    BooleanProperty,
    NumericProperty,
    DictProperty,
)
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.modalview import ModalView
from kivy.uix.spinner import Spinner
from kivy.uix.dropdown import DropDown
from kivy.uix.checkbox import CheckBox
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.factory import Factory
from kivy.config import Config
from kivymd.app import MDApp
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.pickers.datepicker import MDDatePicker
from kivymd.uix.textfield import MDTextField
from kivymd.uix.menu import MDDropdownMenu
from kivymd.theming import ThemableBehavior
from kivymd.uix.list import OneLineIconListItem, MDList

# Import storage functions
from storage import read_transactions, write_transactions, ensure_data_dir

# Import user management
from user_manager import UserManager, user_manager

# Import and register UserScreen
from screens.user_screen import UserScreen
from kivy.factory import Factory
Factory.register('UserScreen', cls=UserScreen)

# Configure window settings
Config.set('graphics', 'resizable', '1')
Config.set('graphics', 'borderless', '0')
Config.set('graphics', 'window_state', 'visible')
Config.set('graphics', 'position', 'custom')

# Set window size and position
Config.set('graphics', 'width', '1024')
Config.set('graphics', 'height', '640')
Config.set('graphics', 'minimum_width', '800')
Config.set('graphics', 'minimum_height', '600')

# Function to handle window resize
def on_window_size(window, width, height):
    # You can add any responsive behavior here if needed
    pass

# Bind the resize event
Window.bind(on_resize=on_window_size)

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
    CSV_COLUMNS,
    get_transactions_path
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
        #self.dismiss()


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
            category_text = "CASH"
            print(f"Setting device to CASH for amount: {amount}")
        else:
            # Get the selected device text and ensure it matches the exact case from the spinner
            device_text = (self.device_spinner.text or "").strip()
            # Use the exact text from the spinner for both device and category
            device = device_text
            category_text = device_text
            print(f"Using device: {device} with category: {category_text}")

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
        #self.dismiss()


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
    current_date = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
        self._keyboard.bind(on_key_down=self._on_keyboard_down)
        Window.bind(on_resize=self._on_window_resize)

    def on_pre_enter(self, *args):
        self.current_date = date.today().strftime("%A, %B %d, %Y")
        self.refresh_metrics()
        self._update_layout()

    def on_kv_post(self, base_widget):
        self.refresh_metrics()
        self._update_layout()

    def _on_window_resize(self, window, width, height):
        self._update_layout()

    def _update_layout(self):
        # Update layout based on window size
        if not hasattr(self, 'ids'):
            return
            
        window_width = Window.width
        
        # Update navigation drawer width (25% of window width, min 240, max 320)
        if 'nav_drawer' in self.ids:
            nav_width = max(dp(240), min(dp(320), window_width * 0.25))
            self.ids.nav_drawer.width = nav_width
        
        # Update metrics row
        if 'metrics_row' in self.ids:
            metrics_row = self.ids.metrics_row
            if window_width < 900:
                metrics_row.orientation = 'vertical'
                metrics_row.height = dp(420)
                for child in metrics_row.children:
                    child.size_hint_x = 1
            else:
                metrics_row.orientation = 'horizontal'
                metrics_row.height = dp(140)
                for child in metrics_row.children:
                    child.size_hint_x = 0.33
        
        # Update quick actions
        if 'quick_actions' in self.ids:
            quick_actions = self.ids.quick_actions
            if window_width < 600:
                quick_actions.orientation = 'vertical'
                quick_actions.height = dp(160)
            else:
                quick_actions.orientation = 'horizontal'
                quick_actions.height = dp(80)

    def _keyboard_closed(self):
        self._keyboard.unbind(on_key_down=self._on_keyboard_down)
        self._keyboard = None

    def _on_keyboard_down(self, keyboard, keycode, text, modifiers):
        # Handle keyboard events if needed
        return False

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
        normalized_category = (category or "").strip().lower()  # Convert to lowercase for comparison
        
        transactions = []
        if normalized_category in CREDIT_CARD_PAYMENT_CATEGORY_KEYS:
            # Create both the payment and debt reduction transactions
            payment_tx, debt_reduction_tx = create_credit_card_payment(
                amount=amount,
                date_value=txn_date,
                description=description,
                category="Credit Card Payment",
                device="BANK_TRANSFER"
            )
            
            # Add a note to the payment
            payment_tx.notes = f"Payment of ₹{amount:.2f} towards credit card bill"
            
            # Add both transactions
            transactions.extend([payment_tx, debt_reduction_tx])
            print(f"Processed credit card payment of ₹{amount:.2f}")
            print("This will reduce both your bank balance and credit card debt.")
            return
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
        account_balance = balance_value - cash_balance_value
        self.balance_caption = f"Account: ₹{account_balance:,.2f} | Cash: ₹{cash_balance_value:,.2f}"
            
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
    filter_month_input = ObjectProperty(None)
    filter_year_input = ObjectProperty(None)
    sort_ascending = BooleanProperty(False)

    def initialize_filters(self) -> None:
        """Initialize month and year filters to current month/year"""
        current_date = date.today()
        if self.filter_month_input and not self.filter_month_input.text:
            self.filter_month_input.text = str(current_date.month)
        if self.filter_year_input and not self.filter_year_input.text:
            self.filter_year_input.text = str(current_date.year)
            
    def on_pre_enter(self, *_) -> None:
        self.initialize_filters()  # This line was missing
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
        
        # Apply month and year filters
        current_date = date.today()
        month_filter = (self.filter_month_input.text or "").strip() if self.filter_month_input else str(current_date.month)
        year_filter = (self.filter_year_input.text or "").strip() if self.filter_year_input else str(current_date.year)
        
        if month_filter.isdigit() and year_filter.isdigit():
            target_month = int(month_filter)
            target_year = int(year_filter)
            transactions = [
                tx for tx in transactions 
                if tx.date.month == target_month and tx.date.year == target_year
            ]
        
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
            amount_color = "#EF4444FF" if tx.tx_type == "expense" else "#10B981FF"
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
        # Reset month and year to current
        current_date = date.today()
        if self.filter_month_input:
            self.filter_month_input.text = str(current_date.month)
        if self.filter_year_input:
            self.filter_year_input.text = str(current_date.year)
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
        try:
            # Read all transactions
            rows = read_transactions()
            
            # Filter out the transaction to delete
            updated_rows = [row for row in rows if row['id'] != transaction_id]
            
            # If no transaction was deleted, do nothing
            if len(updated_rows) == len(rows):
                print(f"No transaction found with ID: {transaction_id}")
                return
                
            # Write the updated transactions back to the file using the proper storage function
            write_transactions(updated_rows)
            
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
            
        except Exception as e:
            print(f"Error deleting transaction: {str(e)}")
            # Show error to user if needed
            if hasattr(self, 'show_popup'):
                self.show_popup("Error", f"Failed to delete transaction: {str(e)}")
                    
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
        
        # Set category if available
        if hasattr(dialog, 'category_input') and dialog.category_input:
            dialog.category_input.text = transaction_to_edit.get('category', '')
        
        # Set date if available
        if hasattr(dialog, 'date_input') and dialog.date_input:
            dialog.date_input.text = transaction_to_edit.get('date', date.today().isoformat())
        
        # Handle device selection
        if hasattr(dialog, 'device_spinner') and dialog.device_spinner:
            device = transaction_to_edit.get('device', '')
            if is_income:
                # For income, handle special case for cash
                if device.upper() == 'CASH':
                    dialog.device_spinner.text = 'Paycheck'
                    if hasattr(dialog, 'cash_toggle'):
                        dialog.cash_toggle = True
                else:
                    dialog.device_spinner.text = device.capitalize() if device else 'Paycheck'
            else:
                # For expenses, set the device as is
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
                dialog.shared_participants_input.disabled = not shared_flag
                dialog.shared_participants_input.opacity = 1.0 if shared_flag else 0.0
                dialog.shared_participants_input.size_hint_y = 1.0 if shared_flag else 0.0
                dialog.shared_participants_input.height = dp(46) if shared_flag else 0
        
        if hasattr(dialog, 'shared_notes_input'):
            dialog.shared_notes_input.text = transaction_to_edit.get('shared_notes', '')
            dialog.shared_notes_input.disabled = not shared_flag
            dialog.shared_notes_input.opacity = 1.0 if shared_flag else 0.0
        
        # Override the submit handler to use our custom save method
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
                    # Update the transaction fields
                    row['amount'] = f"{amount:.2f}"
                    row['description'] = description
                    row['category'] = category
                    row['device'] = device
                    row['date'] = txn_date.strftime('%Y-%m-%d')
                    row['shared_flag'] = '1' if shared_flag else '0'
                    row['shared_splits'] = shared_participants
                    row['shared_notes'] = shared_notes
                    row['timestamp'] = datetime.now().isoformat()  # Update the timestamp
                    transaction_updated = True
                    break
            
            if not transaction_updated:
                print(f"Error: Transaction with ID {transaction_id} not found")
                return
            
            # Save the updated transactions
            write_transactions(rows)
            
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
                        
                if "shared_expenses" in self.manager.screen_names:
                    shared_screen = self.manager.get_screen("shared_expenses")
                    if hasattr(shared_screen, 'refresh'):
                        shared_screen.refresh()
            
            print(f"Successfully updated transaction: {description}")
            
        except Exception as e:
            print(f"Error saving transaction: {str(e)}")
            if hasattr(self, 'show_popup'):
                self.show_popup("Error", f"Failed to save transaction: {str(e)}")
            
            # Write the updated transactions back to the file
            with open(get_transactions_path(), 'w', newline='', encoding='utf-8') as f:
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
    total_spending = StringProperty("₹0.00")
    filter_text_input = ObjectProperty(None)
    filter_month_input = ObjectProperty(None)
    filter_year_input = ObjectProperty(None)
    show_income = BooleanProperty(False)  # Tracks if we're showing income (True) or expenses (False)

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
        budget_raw = settings.get("category_budgets", {}) if isinstance(settings, dict) else {}
        budgets: Dict[str, float] = {}
        for name, value in budget_raw.items():
            try:
                budgets[name] = float(value)
            except (TypeError, ValueError):
                continue

        # Filter transactions based on whether we're showing income or expenses
        tx_type = "income" if self.show_income else "expense"
        filtered_transactions = [tx for tx in transactions if tx.tx_type == tx_type]
        
        # Get category totals for the selected transaction type
        category_totals = {}
        for tx in filtered_transactions:
            category = tx.category or "Uncategorized"
            category_totals[category] = category_totals.get(category, 0.0) + tx.amount
        
        # Calculate total for the selected transaction type
        total = sum(category_totals.values())
        self.total_spending = f"₹{abs(total):,.2f}"  # Show absolute value for both income and expenses
        
        formatted = []
        for category, totals in sorted(category_totals.items(), key=lambda item: item[0].lower()):
            # Apply text filter
            if text_filter and text_filter not in category.lower():
                continue
                
            # Handle budget and variance for both income and expenses
            budget = budgets.get(category, 0.0)
            if budget > 0:
                if not self.show_income:
                    # For expenses: positive variance is good (spent less than budget)
                    variance = budget - abs(totals)
                    variance_color = "#10B981FF" if variance >= 0 else "#EF4444FF"
                else:
                    # For income: positive variance is good (earned more than budget)
                    variance = abs(totals) - budget
                    variance_color = "#10B981FF" if variance >= 0 else "#EF4444FF"
                variance_text = f"{abs(variance):,.2f}"
                budget_text = f"{budget:,.2f}"
            else:
                variance_text = "-"
                variance_color = "#94A3B8FF"
                budget_text = ""
                
            formatted.append(
                {
                    "category_text": category,
                    "amount_text": f"{abs(totals):,.2f}",  # Show absolute value
                    "amount_color": "#10B981FF" if self.show_income else "#000306ff",
                    "budget_text": budget_text,
                    "variance_text": variance_text,
                    "variance_color": variance_color,
                    "screen_name": "category_totals"
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
        # Don't reset the income/expense toggle when clearing filters
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
    selected_participant = StringProperty("")
    participant_details = ListProperty([])
    participant_net = NumericProperty(0.0)
    show_participant_details = BooleanProperty(False)

    def on_pre_enter(self, *_) -> None:
        self.refresh()

    def refresh(self) -> None:
        ensure_data_dir()
        rows = read_transactions()
        self.transactions = [transaction_from_row(row) for row in rows]
        participant = (self.participant_input.text or "").strip() if self.participant_input else ""
        category = (self.category_input.text or "").strip() if self.category_input else ""
        
        # If we have a selected participant from the detailed view, keep it
        if not participant and self.selected_participant and not self.show_participant_details:
            participant = self.selected_participant
            if self.participant_input:
                self.participant_input.text = participant
        
        self.summary, self.details = summarize_shared_expenses(
            self.transactions,
            participant_filter=participant or None,
            category_filter=category or None,
        )
        
        sorted_summary = sorted(self.summary.items(), key=lambda item: item[1], reverse=True)
        self.summary_data = [
            {
                "label_text": name,
                "amount_text": f"{value:,.2f}",
                "on_release": lambda x=name: self.show_participant_detail(x)
            }
            for name, value in sorted_summary
        ]
        
        total_shared = sum(self.summary.values())
        self.total_shared_text = f"{total_shared:,.2f}"
        self.summary_caption = self._format_summary_caption(len(self.summary))
        self.detail_caption = self._format_detail_caption(len(self.details))
        self.filters_caption = self._format_filters_caption(participant, category)

        participant_lookup = participant.lower() if participant else ""
        detail_rows = []
        for tx, allocations in self.details:
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
                    "on_release": lambda x=tx: self.show_transaction_detail(x)
                }
            )
        self.detail_data = detail_rows
        
        # If we're showing participant details, update them
        if self.show_participant_details and self.selected_participant:
            self._update_participant_details(self.selected_participant)

    def show_participant_detail(self, participant_name: str) -> None:
        """Show detailed view for a specific participant."""
        self.selected_participant = participant_name
        self.show_participant_details = True
        self._update_participant_details(participant_name)
        
    def _update_participant_details(self, participant_name: str) -> None:
        """Update the detailed view for a participant."""
        if not hasattr(self, 'transactions') or not self.transactions:
            return
            
        participant_lower = participant_name.lower()
        details = []
        net_total = 0.0
        
        # Get all transactions involving this participant
        for tx, allocations in self.details:
            for name, amount in allocations.items():
                if name.lower() == participant_lower:
                    # Determine if this is an expense (positive) or income (negative)
                    is_expense = tx.tx_type == "expense"
                    sign = 1.0 if is_expense else -1.0
                    
                    # For DEBT_BORROWED, invert the amount to show as negative in shared expenses
                    if tx.device == "DEBT_BORROWED":
                        sign *= -1.0
                    
                    net_amount = sign * amount
                    net_total += net_amount
                    
                    details.append({
                        'date': tx.date,
                        'description': tx.description or tx.sub_type.replace("_", " ").title(),
                        'amount': amount,
                        'is_expense': is_expense,
                        'total_amount': tx.amount,
                        'category': tx.category or "Uncategorised",
                        'participants': ", ".join(f"{n} (₹{a:,.2f})" for n, a in allocations.items()),
                        'notes': tx.shared_notes or ""
                    })
        
        # Sort by date, newest first
        details.sort(key=lambda x: x['date'], reverse=True)
        
        # Format for display
        formatted_details = []
        for detail in details:
            formatted_details.append({
                'date_text': detail['date'].strftime('%d %b %Y'),
                'description_text': detail['description'],
                'amount_text': f"₹{detail['amount']:,.2f}",
                'total_amount_text': f"₹{detail['total_amount']:,.2f}",
                'is_expense': detail['is_expense'],
                'category_text': detail['category'],
                'participants_text': detail['participants'],
                'notes_text': detail['notes'] or "No notes"
            })
        
        self.participant_details = formatted_details
        self.participant_net = net_total
        
    def show_transaction_detail(self, transaction):
        """Show detailed view for a specific transaction."""
        # This can be implemented to show a modal with transaction details
        pass
        
    def back_to_summary(self):
        """Return to the summary view from participant details."""
        self.show_participant_details = False
        self.selected_participant = ""
        if self.participant_input:
            self.participant_input.text = ""
        self.refresh()

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
        if count == 0:
            return "No shared transactions yet"
        elif count == 1:
            return "1 shared transaction"
        else:
            return f"{count} shared transactions"

# Register SharedExpensesScreen with Kivy's Factory after the class is defined
Factory.register('SharedExpensesScreen', cls=SharedExpensesScreen)


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
    """Main screen manager for the application with user session handling."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.transition = NoTransition()  # Disable screen transitions initially
        self._initial_screen_set = False
        
    def on_kv_post(self, base_widget):
        # This runs after the KV file is loaded
        super().on_kv_post(base_widget)
        self.set_initial_screen()
    
    def on_screens(self, instance, value):
        # This runs whenever screens are added or removed
        if not self._initial_screen_set:
            self.set_initial_screen()
    
    def set_initial_screen(self):
        if not self.screens:
            return
            
        # Check if we have a current user
        current_user = user_manager.get_current_user()
        if current_user and 'dashboard' in self.screen_names:
            # User is logged in, go to dashboard
            self.current = "dashboard"
            self._initial_screen_set = True
        elif 'user' in self.screen_names:
            # No user logged in, go to user screen
            self.current = "user"
            self._initial_screen_set = True
    
    def logout(self):
        """Log out the current user and return to the user selection screen."""
        user_manager.set_current_user(None)  # Logout
        self.transition = NoTransition()
        self.current = "user"  # Switch to user selection screen
        
        # Clear any sensitive data from screens
        for screen in self.screens:
            if hasattr(screen, 'on_logout'):
                screen.on_logout()


class MoneyTrackerApp(MDApp):
    """Main application class with user management integration."""
    config_state = DictProperty({})
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.theme_cls.theme_style = "Light"  # or "Dark"
        self.theme_cls.primary_palette = "Blue"  # You can change the color
        self.user_manager = user_manager  # Make user_manager available app-wide
        
    def build(self) -> ScreenManager:
        # Set window properties
        Window.size = (1024, 640)
        Window.minimum_width = 800
        Window.minimum_height = 600
        
        # Center window on screen
        screen_width = Window.system_size[0]
        screen_height = Window.system_size[1]
        window_width = 1024
        window_height = 640
        
        Window.left = max(0, (screen_width - window_width) / 2)
        Window.top = max(0, (screen_height - window_height) / 2)
        
        # Ensure users directory exists
        (user_manager.data_dir / "users").mkdir(parents=True, exist_ok=True)
        
        # Create screen manager first
        sm = MoneyTrackerScreenManager()
        
        # Add user screen first (imported here to avoid circular imports)
        from screens.user_screen import UserScreen
        sm.add_widget(UserScreen(name='user'))
        
        # Load KV file after adding the user screen
        Builder.load_file(str(KV_FILE))
        
        # Add other screens
        sm.add_widget(DashboardScreen(name='dashboard'))
        sm.add_widget(TransactionsScreen(name='transactions'))
        sm.add_widget(NetWorthScreen(name='networth'))
        sm.add_widget(CategoryTotalsScreen(name='category_totals'))
        sm.add_widget(SharedExpensesScreen(name='shared_expenses'))
        sm.add_widget(SettingsScreen(name='settings'))
        
        return sm

    def on_start(self) -> None:
        """Initialize the application and check for new month when a user is logged in."""
        # If we have a logged-in user, refresh the dashboard
        if user_manager.current_user:
            dashboard = self.root.get_screen('dashboard')
            if hasattr(dashboard, 'refresh_metrics'):
                dashboard.refresh_metrics()
            
            # Check if we need to start a new month's transaction file
            try:
                settings = read_settings()
                last_month = settings.get('last_month_processed')
                current_month = date.today().strftime('%Y-%m')
                
                if last_month != current_month:
                    # It's a new month, archive last month's transactions
                    start_new_month_transactionfile()
                    
                    # Update the last processed month
                    settings['last_month_processed'] = current_month
                    write_settings(settings)
                    
                    # Show a notification
                    if 'dashboard' in self.root.screen_names:
                        dashboard = self.root.get_screen('dashboard')
                        if hasattr(dashboard, 'show_popup'):
                            dashboard.show_popup("New Month", "A new transaction file has been created for this month.")
            except Exception as e:
                print(f"Error in on_start: {e}")

    def on_stop(self) -> None:
        """Clean up when the application is closed."""
        # Save any pending changes
        # Note: User session is maintained through the users.json file
        pass

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
