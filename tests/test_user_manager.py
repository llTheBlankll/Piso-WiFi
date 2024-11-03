import pytest
import sqlite3
import os
from user_manager import UserManager

@pytest.fixture
def user_manager():
    # Use a test database
    um = UserManager()
    um.db_name = 'test_piso_wifi.db'
    
    # Initialize test database
    conn = sqlite3.connect(um.db_name)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mac_address TEXT UNIQUE,
            time_balance INTEGER DEFAULT 0,
            status TEXT DEFAULT 'inactive'
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            minutes INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()
    
    yield um
    
    # Cleanup
    os.remove(um.db_name)

def test_add_time(user_manager):
    # Test adding time for a new user
    assert user_manager.add_time("00:11:22:33:44:55", 5, 25) == True
    assert user_manager.check_balance("00:11:22:33:44:55") == 25
    
    # Test adding time for existing user
    assert user_manager.add_time("00:11:22:33:44:55", 5, 25) == True
    assert user_manager.check_balance("00:11:22:33:44:55") == 50

def test_check_balance_nonexistent_user(user_manager):
    assert user_manager.check_balance("11:22:33:44:55:66") == 0 