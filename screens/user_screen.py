"""User selection and creation screen for FinanceTracker."""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.app import App
from kivy.metrics import dp
from kivy.properties import ObjectProperty
from kivy.utils import rgba
from user_manager import user_manager

class UserScreen(Screen):
    """Screen for user selection and creation."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.build_ui()
        
    def build_ui(self):
        """Build the user interface."""
        layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        
        # Title
        self.title = Label(
            text="Welcome to Finance Tracker",
            font_size='30sp',
            size_hint_y=0.2,
            color= rgba("#000306ff")
        )
        layout.add_widget(self.title)
        
        # Subtitle
        subtitle = Label(
            text="Select or create a user to continue",
            font_size='16sp',
            size_hint_y=0.1,
            color=rgba("#000306ff")
        )
        layout.add_widget(subtitle)
        
        # User list container with scroll view
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.gridlayout import GridLayout
        
        scroll_view = ScrollView(do_scroll_x=False, size_hint=(1, 1),bar_width=dp(6),scroll_type=['bars', 'content'])
        self.user_list = GridLayout(cols=1, spacing=12,padding=[dp(16), dp(16)], size_hint_y=None)
        self.user_list.bind(minimum_height=self.user_list.setter('height'))
        scroll_view.add_widget(self.user_list)
        layout.add_widget(scroll_view)
        
        # New user input
        self.new_user_input = TextInput(
            hint_text="Enter new username",
            size_hint_y=0.1,
            multiline=False,
            background_color = rgba("#F8FAFCFF"),
            foreground_color = rgba("#000306ff"),
            padding=[10, 10]
        )
        layout.add_widget(self.new_user_input)
        
        # Buttons
        button_layout = BoxLayout(size_hint_y=0.15, spacing=10)
        
        add_button = Button(
            text="Create User",
            background_color=(0.2, 0.6, 1, 1),
            color=(1, 1, 1, 1),
            bold=True
        )
        add_button.bind(on_press=self.add_user)
        
        # Bind Enter key in the text input to also add user
        self.new_user_input.bind(on_text_validate=lambda x: self.add_user(None))
        
        button_layout.add_widget(add_button)
        layout.add_widget(button_layout)
        
        self.add_widget(layout)
    
    def on_pre_enter(self, *args):
        """Called when the screen is about to be shown."""
        self.refresh_user_list()
        # Auto-focus the input field
        self.new_user_input.focus = True
    
    def refresh_user_list(self):
        """Refresh the list of available users."""
        self.user_list.clear_widgets()
        users = user_manager.get_users()
        
        if not users:
            empty_label = Label(
                text="No users found. Create a new user to get started.",
                halign='center',
                color=(0.5, 0.5, 0.5, 1),
                size_hint_y=None,
                height=dp(50)
            )
            self.user_list.add_widget(empty_label)
            return
            
        for username in sorted(users.keys()):
            btn = Button(
                text=username,
                size_hint_y=None,
                height=dp(50),
                background_color=(0.9, 0.9, 0.9, 1),
                color=(0.2, 0.2, 0.2, 1),
                background_normal='',
                background_down='atlas://data/images/defaulttheme/button_pressed'
            )
            btn.bind(on_press=lambda x, u=username: self.select_user(u))
            self.user_list.add_widget(btn)
    
    def add_user(self, instance):
        """Add a new user."""
        username = self.new_user_input.text.strip()
        if not username:
            self.show_popup("Error", "Username cannot be empty")
            return
            
        if len(username) < 3:
            self.show_popup("Error", "Username must be at least 3 characters long")
            return
            
        if user_manager.add_user(username):
            self.new_user_input.text = ""
            self.refresh_user_list()
            self.select_user(username)
        else:
            self.show_popup("Error", f"User '{username}' already exists")
    
    def select_user(self, username):
        """Select a user and proceed to the main app."""
        if user_manager.set_current_user(username):
            app = App.get_running_app()
            # Switch to dashboard or main screen
            app.root.current = "dashboard"
            
            # Refresh the dashboard to load user-specific data
            dashboard = app.root.get_screen('dashboard')
            if hasattr(dashboard, 'refresh_metrics'):
                dashboard.refresh_metrics()
        else:
            self.show_popup("Error", "Failed to select user. Please try again.")
    
    def show_popup(self, title: str, message: str):
        """Show a popup with the given title and message."""
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text=message, color=(0, 0, 0, 1)))
        
        popup = Popup(
            title=title,
            content=content,
            size_hint=(0.8, 0.4),
            title_align='center',
            title_size='20sp'
        )
        
        btn = Button(
            text="OK",
            size_hint=(1, 0.4),
            background_color=(0.2, 0.6, 1, 1),
            color=(1, 1, 1, 1)
        )
        btn.bind(on_press=popup.dismiss)
        content.add_widget(btn)
        
        popup.open()
