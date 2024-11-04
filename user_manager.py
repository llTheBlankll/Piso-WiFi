import sqlite3
import os
from datetime import datetime
import logging

class UserManager:
    def __init__(self):
        self.db_path = 'config/piso_wifi.db'
        self.logger = logging.getLogger(__name__)
        
        # Ensure config directory exists
        os.makedirs('config', exist_ok=True)
        
        # Initialize database on startup
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            # Create users table
            c.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mac_address TEXT UNIQUE,
                    time_balance INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'inactive',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create transactions table
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
            self.logger.info("Database initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing database: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def add_time(self, mac_address, amount, minutes):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            # Check if user exists
            c.execute('SELECT id, time_balance FROM users WHERE mac_address = ?', (mac_address,))
            user = c.fetchone()
            
            if user is None:
                # Create new user
                c.execute('INSERT INTO users (mac_address, time_balance, status) VALUES (?, ?, ?)',
                         (mac_address, minutes, 'active'))
                user_id = c.lastrowid
            else:
                user_id, current_balance = user
                # Update existing user's balance
                c.execute('UPDATE users SET time_balance = time_balance + ?, status = ? WHERE id = ?',
                         (minutes, 'active', user_id))
            
            # Record transaction
            c.execute('''INSERT INTO transactions (user_id, amount, minutes)
                        VALUES (?, ?, ?)''', (user_id, amount, minutes))
            
            conn.commit()
            self.logger.info(f"Added {minutes} minutes for MAC {mac_address}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding time: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def check_balance(self, mac_address):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute('SELECT time_balance FROM users WHERE mac_address = ?', (mac_address,))
            result = c.fetchone()
            return result[0] if result else 0
        except Exception as e:
            self.logger.error(f"Error checking balance: {e}")
            return 0
        finally:
            conn.close()
    
    def deduct_time(self, mac_address, minutes):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            # Update balance and status if balance becomes 0
            c.execute('''
                UPDATE users 
                SET time_balance = MAX(0, time_balance - ?),
                    status = CASE 
                        WHEN time_balance - ? <= 0 THEN 'inactive'
                        ELSE 'active'
                    END
                WHERE mac_address = ?
            ''', (minutes, minutes, mac_address))
            
            conn.commit()
            self.logger.debug(f"Deducted {minutes} minutes from MAC {mac_address}")
            return True
        except Exception as e:
            self.logger.error(f"Error deducting time: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def check_health(self):
        """Check if database is accessible"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('SELECT 1')
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return False