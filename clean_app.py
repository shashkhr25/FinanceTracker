from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.core.window import Window
from kivy.metrics import dp
from datetime import datetime

class TransactionItem(BoxLayout):
    def __init__(self, description, amount, date, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = dp(40)
        self.padding = [0, dp(5)]
        
        # Add description
        desc_label = Label(
            text=description,
            halign='left',
            text_size=(Window.width * 0.5, None),
            shorten=True,
            shorten_from='right'
        )
        
        # Format amount with color
        amount_str = f'${abs(amount):.2f}'
        amount_color = (0.2, 0.8, 0.2, 1) if amount >= 0 else (0.8, 0.2, 0.2, 1)
        amount_label = Label(
            text=amount_str,
            color=amount_color,
            halign='right',
            bold=True
        )
        
        # Format date
        date_str = date.strftime('%b %d')
        date_label = Label(
            text=date_str,
            color=(0.5, 0.5, 0.5, 1),
            size_hint_x=0.3
        )
        
        self.add_widget(desc_label)
        self.add_widget(amount_label)
        self.add_widget(date_label)

class MainScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.balance = 0.0
        self.transactions = []
        
        # Main layout
        layout = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        
        # Header
        header = BoxLayout(size_hint_y=None, height=dp(50))
        title = Label(
            text='💰 Money Tracker',
            font_size='24sp',
            halign='left',
            bold=True
        )
        header.add_widget(title)
        
        # Balance card
        balance_card = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=dp(100),
            padding=dp(15),
            spacing=dp(5)
        )
        
        balance_card.add_widget(Label(
            text='Total Balance',
            font_size='16sp',
            color=(0.5, 0.5, 0.5, 1),
            size_hint_y=None,
            height=dp(25)
        ))
        
        self.balance_label = Label(
            text=f'${self.balance:.2f}',
            font_size='32sp',
            bold=True,
            size_hint_y=None,
            height=dp(40)
        )
        balance_card.add_widget(self.balance_label)
        
        # Buttons
        button_row = BoxLayout(
            size_hint_y=None,
            height=dp(50),
            spacing=dp(10),
            padding=[0, dp(5)]
        )
        
        add_income = Button(
            text='+ Income',
            background_color=(0.2, 0.8, 0.2, 1),
            bold=True
        )
        
        add_expense = Button(
            text='- Expense',
            background_color=(0.8, 0.2, 0.2, 1),
            bold=True
        )
        
        clear_btn = Button(
            text='Clear All',
            size_hint_x=0.3,
            background_color=(0.3, 0.3, 0.3, 1)
        )
        
        button_row.add_widget(add_income)
        button_row.add_widget(add_expense)
        button_row.add_widget(clear_btn)
        
        # Transactions header
        transactions_header = BoxLayout(
            size_hint_y=None,
            height=dp(30),
            spacing=dp(10)
        )
        transactions_header.add_widget(Label(
            text='Description',
            color=(0.5, 0.5, 0.5, 1),
            halign='left'
        ))
        transactions_header.add_widget(Label(
            text='Amount',
            color=(0.5, 0.5, 0.5, 1)
        ))
        transactions_header.add_widget(Label(
            text='Date',
            color=(0.5, 0.5, 0.5, 1),
            size_hint_x=0.3
        ))
        
        # Transactions list with scroll
        from kivy.uix.scrollview import ScrollView
        scroll = ScrollView(do_scroll_x=False)
        
        self.transactions_container = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=dp(5),
            padding=[0, dp(5)]
        )
        self.transactions_container.bind(
            minimum_height=self.transactions_container.setter('height')
        )
        
        scroll.add_widget(self.transactions_container)
        
        # Add widgets to main layout
        layout.add_widget(header)
        layout.add_widget(balance_card)
        layout.add_widget(button_row)
        layout.add_widget(transactions_header)
        layout.add_widget(scroll)
        
        # Add sample transactions
        self.add_transaction('Lunch', -15.99)
        self.add_transaction('Salary', 2500.00)
        self.add_transaction('Groceries', -85.75)
        
        # Bind buttons
        add_income.bind(on_press=self.show_add_income)
        add_expense.bind(on_press=self.show_add_expense)
        clear_btn.bind(on_press=self.clear_transactions)
        
        self.add_widget(layout)
    
    def update_balance(self):
        self.balance = sum(t[1] for t in self.transactions)
        self.balance_label.text = f'${self.balance:.2f}'
        # Change color based on balance
        self.balance_label.color = (0.2, 0.8, 0.2, 1) if self.balance >= 0 else (0.8, 0.2, 0.2, 1)
    
    def add_transaction(self, description, amount):
        # Add to transactions list
        transaction = (description, amount, datetime.now())
        self.transactions.append(transaction)
        
        # Add to UI
        transaction_item = TransactionItem(
            description=description,
            amount=amount,
            date=transaction[2]
        )
        self.transactions_container.add_widget(transaction_item, index=0)  # Add to top
        
        # Update balance
        self.update_balance()
    
    def show_add_income(self, instance):
        from kivy.uix.popup import Popup
        from kivy.uix.textinput import TextInput
        from kivy.uix.gridlayout import GridLayout
        
        content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        
        # Input fields
        amount_input = TextInput(
            hint_text='Amount',
            input_filter='float',
            multiline=False,
            size_hint_y=None,
            height=dp(50)
        )
        
        desc_input = TextInput(
            hint_text='Description',
            multiline=False,
            size_hint_y=None,
            height=dp(50)
        )
        
        # Buttons
        btn_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        
        cancel_btn = Button(text='Cancel')
        add_btn = Button(text='Add Income', background_color=(0.2, 0.8, 0.2, 1))
        
        btn_layout.add_widget(cancel_btn)
        btn_layout.add_widget(add_btn)
        
        # Add to content
        content.add_widget(Label(text='Add Income', font_size='20sp', size_hint_y=None, height=dp(40)))
        content.add_widget(desc_input)
        content.add_widget(amount_input)
        content.add_widget(btn_layout)
        
        # Create and open popup
        popup = Popup(
            title='',
            content=content,
            size_hint=(0.9, 0.6),
            auto_dismiss=False
        )
        
        def add_income(btn):
            try:
                amount = float(amount_input.text)
                if amount > 0:
                    self.add_transaction(
                        desc_input.text or 'Income',
                        amount
                    )
                    popup.dismiss()
            except ValueError:
                pass
        
        add_btn.bind(on_press=add_income)
        cancel_btn.bind(on_press=lambda x: popup.dismiss())
        
        popup.open()
    
    def show_add_expense(self, instance):
        from kivy.uix.popup import Popup
        from kivy.uix.textinput import TextInput
        
        content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        
        # Input fields
        amount_input = TextInput(
            hint_text='Amount',
            input_filter='float',
            multiline=False,
            size_hint_y=None,
            height=dp(50)
        )
        
        desc_input = TextInput(
            hint_text='Description',
            multiline=False,
            size_hint_y=None,
            height=dp(50)
        )
        
        # Buttons
        btn_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        
        cancel_btn = Button(text='Cancel')
        add_btn = Button(text='Add Expense', background_color=(0.8, 0.2, 0.2, 1))
        
        btn_layout.add_widget(cancel_btn)
        btn_layout.add_widget(add_btn)
        
        # Add to content
        content.add_widget(Label(text='Add Expense', font_size='20sp', size_hint_y=None, height=dp(40)))
        content.add_widget(desc_input)
        content.add_widget(amount_input)
        content.add_widget(btn_layout)
        
        # Create and open popup
        popup = Popup(
            title='',
            content=content,
            size_hint=(0.9, 0.6),
            auto_dismiss=False
        )
        
        def add_expense(btn):
            try:
                amount = -abs(float(amount_input.text))  # Ensure negative for expenses
                if amount < 0:
                    self.add_transaction(
                        desc_input.text or 'Expense',
                        amount
                    )
                    popup.dismiss()
            except ValueError:
                pass
        
        add_btn.bind(on_press=add_expense)
        cancel_btn.bind(on_press=lambda x: popup.dismiss())
        
        popup.open()
    
    def clear_transactions(self, instance):
        self.transactions = []
        self.transactions_container.clear_widgets()
        self.update_balance()
    
    # Removed old add_income and add_expense methods, replaced with popup versions

class MoneyTrackerApp(App):
    def build(self):
        # Set window background to light gray
        Window.clearcolor = (0.9, 0.9, 0.9, 1)
        
        # Create screen manager
        sm = ScreenManager()
        
        # Add main screen
        main_screen = MainScreen(name='main')
        sm.add_widget(main_screen)
        
        return sm

if __name__ == '__main__':
    MoneyTrackerApp().run()
