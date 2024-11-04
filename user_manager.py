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
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        try:
            # Users table with bandwidth fields and plan
            c.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mac_address TEXT UNIQUE,
                    time_balance REAL DEFAULT 0,
                    status TEXT DEFAULT 'inactive',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_deduction TIMESTAMP,
                    download_limit INTEGER DEFAULT 1024,
                    upload_limit INTEGER DEFAULT 512,
                    plan TEXT DEFAULT 'default',
                    upgrade_requested BOOLEAN DEFAULT 0
                )
            ''')
            
            # Transactions table
            c.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    minutes INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Time logs table with deduction_type
            c.execute('''
                CREATE TABLE IF NOT EXISTS time_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    mac_address TEXT,
                    minutes_deducted REAL,
                    balance_before REAL,
                    balance_after REAL,
                    deducted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    deduction_type TEXT DEFAULT 'auto',
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            conn.commit()
        except Exception as e:
            self.logger.error(f"Error initializing database: {e}")
            conn.rollback()
            raise
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
    
    def deduct_time(self, mac_address, minutes, manual=False):
        """Deduct time from user's balance and handle zero balance"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            # First check current balance
            c.execute('SELECT id, time_balance FROM users WHERE mac_address = ?', (mac_address,))
            result = c.fetchone()
            
            if not result:
                self.logger.warning(f"No user found for MAC {mac_address}")
                return False
                
            user_id, current_balance = result
            new_balance = max(0, current_balance - minutes)
            
            # Update balance and status
            c.execute('''
                UPDATE users 
                SET time_balance = ?,
                    status = CASE 
                        WHEN ? <= 0 THEN 'inactive'
                        ELSE 'active'
                    END,
                    last_deduction = CURRENT_TIMESTAMP
                WHERE mac_address = ?
            ''', (new_balance, new_balance, mac_address))
            
            # Log the deduction
            c.execute('''
                INSERT INTO time_logs (
                    user_id,
                    mac_address, 
                    minutes_deducted, 
                    balance_before,
                    balance_after,
                    deducted_at,
                    deduction_type
                ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            ''', (user_id, mac_address, minutes, current_balance, new_balance, 'manual' if manual else 'auto'))
            
            conn.commit()
            self.logger.info(f"Deducted {minutes} minutes from {mac_address}. Balance: {current_balance} -> {new_balance}")
            
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
    
    def set_bandwidth(self, mac_address, download_kbps, upload_kbps):
        """Set bandwidth limits for a user"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute('''
                UPDATE users 
                SET download_limit = ?,
                    upload_limit = ?
                WHERE mac_address = ?
            ''', (download_kbps, upload_kbps, mac_address))
            
            conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error setting bandwidth: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()