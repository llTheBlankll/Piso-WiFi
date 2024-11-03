import sqlite3
from datetime import datetime

class UserManager:
    def __init__(self):
        self.db_name = 'piso_wifi.db'
    
    def add_time(self, mac_address, amount, minutes):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        try:
            # Check if user exists
            c.execute('SELECT id, time_balance FROM users WHERE mac_address = ?', (mac_address,))
            user = c.fetchone()
            
            if user is None:
                # Create new user
                c.execute('INSERT INTO users (mac_address, time_balance) VALUES (?, ?)',
                         (mac_address, minutes))
                user_id = c.lastrowid
            else:
                user_id, current_balance = user
                # Update existing user's balance
                c.execute('UPDATE users SET time_balance = time_balance + ? WHERE id = ?',
                         (minutes, user_id))
            
            # Record transaction
            c.execute('''INSERT INTO transactions (user_id, amount, minutes)
                        VALUES (?, ?, ?)''', (user_id, amount, minutes))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Error: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def check_balance(self, mac_address):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        try:
            c.execute('SELECT time_balance FROM users WHERE mac_address = ?', (mac_address,))
            result = c.fetchone()
            return result[0] if result else 0
        finally:
            conn.close() 