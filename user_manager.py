"""User management module for FinanceTracker."""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

class UserManager:
    """Manages user accounts and their data."""
    
    def __init__(self, data_dir: Path = Path("MoneyTrackerdata")):
        """Initialize the user manager with the data directory."""
        self.data_dir = data_dir
        self.users_file = data_dir / "users.json"
        self.current_user: Optional[str] = None
        self.ensure_users_file()
        
    def ensure_users_file(self) -> None:
        """Create users file if it doesn't exist."""
        if not self.users_file.exists():
            self.users_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump({"current_user": None, "users": {}}, f, indent=2)
    
    def get_users(self) -> Dict[str, Dict[str, Any]]:
        """Get all users and their data."""
        with open(self.users_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("users", {})
    
    def add_user(self, username: str) -> bool:
        """Add a new user if they don't exist."""
        users = self.get_users()
        if username in users:
            return False
            
        # Create user directory
        user_dir = self.data_dir / "users" / username
        user_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize user data
        users[username] = {
            "created_at": str(datetime.now()),
            "data_dir": str(user_dir)
        }
        self._save_users(users)
        return True
    
    def set_current_user(self, username: Optional[str]) -> bool:
        """Set the current user."""
        if username is None:
            # Logout case
            with open(self.users_file, 'r+', encoding='utf-8') as f:
                data = json.load(f)
                data["current_user"] = None
                f.seek(0)
                json.dump(data, f, indent=2)
                f.truncate()
            self.current_user = None
            return True
            
        users = self.get_users()
        if username not in users:
            return False
            
        with open(self.users_file, 'r+', encoding='utf-8') as f:
            data = json.load(f)
            data["current_user"] = username
            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()
            
        self.current_user = username
        return True
    
    def get_current_user(self) -> Optional[str]:
        """Get the current user."""
        if not self.users_file.exists():
            return None
            
        with open(self.users_file, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                return data.get("current_user")
            except json.JSONDecodeError:
                return None
    
    def get_user_dir(self, username: Optional[str] = None) -> Path:
        """Get the data directory for a user."""
        if username is None:
            username = self.get_current_user()
            if not username:
                raise ValueError("No user is currently logged in")
        return Path(self.data_dir) / "users" / username
    
    def _save_users(self, users: Dict[str, Dict[str, Any]]) -> None:
        """Save users data to the users file."""
        with open(self.users_file, 'r+', encoding='utf-8') as f:
            data = json.load(f)
            data["users"] = users
            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()

# Global instance
user_manager = UserManager(data_dir=Path("MoneyTrackerdata"))
