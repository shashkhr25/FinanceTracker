"""MoneyTracker – Final, Working, Modern UI"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Sequence
from kivy.app import App
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import DictProperty, ListProperty, ObjectProperty, StringProperty
from kivy.clock import Clock
from kivy.uix.modalview import ModalView
from kivy.uix.dropdown import DropDown
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.factory import Factory

# ------------------------------------------------------------------ #
# Storage & Logic
# ------------------------------------------------------------------ #
from storage import append_transaction, ensure_data_dir, read_settings, read_transactions, write_settings, start_new_month_transactionfile
from logic import (
    CREDIT_CARD_DEVICES,
    CREDIT_CARD_PAYMENT_CATEGORY_KEYS,
    compute_balance,
    compute_cash_balance,
    compute_outstanding_debt,
    compute_savings_totals,
    create_credit_card_expense,
    create_credit_card_payment,
    create_debt_clearance_transaction,
    create_expense_transaction,
    create_income_transaction,
    SharedSplit,
    summarize_shared_expenses,
    summarize_by_category,
    transaction_from_row,
    transaction_to_row,
    validate_transaction
)

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
                name = name_raw.strip()
                if not name:
                    continue
                try:
                    amount = float(amount_raw.strip())
                except (TypeError, ValueError):
                    amount = None
                entries.append(SharedSplit(name=name, amount=amount))
            else:
                entries.append(SharedSplit(name=part.strip(), amount=None))
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
    """Modal dialog for capturing expense details"""
    parent_screen = ObjectProperty(None)
    amount_input=ObjectProperty(None)
    description_input = ObjectProperty(None)
    device_spinner = ObjectProperty(None)
    date_input = ObjectProperty(None)
    shared_checkbox = ObjectProperty(None)
    shared_participants_input = ObjectProperty(None)
    shared_notes_input = ObjectProperty(None)

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

        category_text = ""
        device_text_raw = (self.device_spinner.text or "").strip()
        device_code = device_text_raw
        if device_text_raw.lower() == "savings withdraw" or device_text_raw.lower() == "taken from savings":
            device_code = "SAVINGS_WITHDRAW"
            category_text = "Taken from Savings"

        txn_date = _parse_date_or_today(self.date_input.text if self.date_input else "")

        shared_flag = bool(self.shared_checkbox.active) if self.shared_checkbox else False
        participants_text = self.shared_participants_input.text if self.shared_participants_input else ""
        shared_splits = self._parse_shared_entries(participants_text) if shared_flag else []
        shared_notes = self.shared_notes_input.text.strip() if (self.shared_notes_input and shared_flag) else ""

        self.parent_screen.submit_income(
            amount=amount,
            description=self.description_input.text.strip(),
            category=category_text,
            device=device_code,
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
                    device=cleaned_device or "BANK_TRANSFER",
                )
            )
        elif cleaned_device in CREDIT_CARD_DEVICES:
            expense_tx, debt_tx = create_credit_card_expense(
                amount = amount,
                date_value=txn_date,
                description=description,
                category=category,
                device=cleaned_device,
                shared_flag=shared_flag,
                shared_splits=shared_splits,
                shared_notes=shared_notes,
            )
            transactions.extend([expense_tx,debt_tx])
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
        rows = read_transactions()
        transactions = [transaction_from_row(row) for row in rows]

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
        debt_value = compute_outstanding_debt(transactions)
        self.current_balance_text = f"{balance_value:,.2f}"
        self.balance_caption = f"Account Balance {(balance_value-cash_balance_value):,.2f} \n" + f"Cash balance: {cash_balance_value:.2f}"
        self.outstanding_debt_text = f"{debt_value:,.2f}"
        if debt_value > 0 :
            self.outstanding_debt_caption = "Credit card debt outstanding"
        else:
            self.outstanding_debt_caption = "No Outstanding Debt"


class TransactionsScreen(Screen):
    rv = ObjectProperty(None)
    empty_label = ObjectProperty(None)
    filter_text_input = ObjectProperty(None)
    filter_device_input = ObjectProperty(None)
    filter_category_input = ObjectProperty(None)

    def on_pre_enter(self, *_) -> None:
        self.refresh()

    def refresh(self) -> None:
        ensure_data_dir()
        rows = read_transactions()
        transactions = [transaction_from_row(row) for row in rows]
        transactions.sort(key=lambda tx: tx.timestamp, reverse = True)

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


class NetWorthScreen(Screen):
    liquid_balance_text = StringProperty("0.00")
    liquid_balance_caption = StringProperty("")
    outstanding_debt_text = StringProperty("0.00")
    outstanding_debt_caption = StringProperty("")
    total_savings_text = StringProperty("0.00")
    savings_summary = ListProperty([])
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
        ensure_data_dir()
        self.populate_settings()
        rows = read_transactions()
        transactions = [transaction_from_row(row) for row in rows]
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
        debt_value = compute_outstanding_debt(transactions)
        savings_total = compute_savings_totals(transactions)
        total_savings = sum(savings_total.values())
        
        self.savings_display = f"{savings_total["Savings"]:,.2f}"
        self.savings_fd_display = f"{savings_total["Savings FD"]:,.2f}"
        self.savings_rd_display = f"{savings_total["Savings RD"]:,.2f}"
        self.savings_gold_display = f"{savings_total["Savings Gold"]:,.2f}"
        self.liquid_balance_text = f"{balance_value:,.2f}"
        self.liquid_balance_caption = f"{combined_initial_balance:,.2f}"
        self.outstanding_debt_text = f"{debt_value:,.2f}"
        if debt_value > 0 :
            self.outstanding_debt_caption = "Credit card outstanding Debt"
        else:
            self.outstanding_debt_caption = "No outstanding debt"

        self.total_savings_text = f"{total_savings:,.2f}"

class CategoryTotalsScreen(Screen):
    category_summary = ListProperty([])

    def on_pre_enter(self, *_) -> None:
        self.refresh()

    def refresh(self) -> None:
        ensure_data_dir()
        rows = read_transactions()
        transactions = [transaction_from_row(row) for row in rows]
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
        ensure_data_dir()
        rows = read_transactions()
        transactions = [transaction_from_row(row) for row in rows]
        debt_value = compute_outstanding_debt(transactions)

        if debt_value <= 0:
            print("No outstanding debt to clear")
            return

        clearance_tx = create_debt_clearance_transaction(
            amount=debt_value,
            date_value=date.today(),
            description="Debt cleared via settings",
        )

        ok, errors = validate_transaction(clearance_tx)
        if not ok:
            for err in errors:
                print(f"Validation error: {err}")
            return

        append_transaction(transaction_to_row(clearance_tx))
        print("Outstanding debt cleared")

        if self.manager:
            if "dashboard" in self.manager.screen_names:
                dashboard_screen = self.manager.get_screen("dashboard")
                if hasattr(dashboard_screen, "refresh_metrics"):
                    dashboard_screen.refresh_metrics()

            if "transactions" in self.manager.screen_names:
                transactions_screen = self.manager.get_screen("transactions")
                if hasattr(transactions_screen, "refresh"):
                    transactions_screen.refresh()

            if "networth" in self.manager.screen_names:
                networth_screen = self.manager.get_screen("networth")
                if hasattr(networth_screen, "refresh"):
                    networth_screen.refresh()

    def start_new_month(self) -> None:
        start_new_month_transactionfile()

class MoneyTrackerScreenManager(ScreenManager):
        """ commenting block
        new line of comments
        """


class MoneyTrackerApp(App):
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
