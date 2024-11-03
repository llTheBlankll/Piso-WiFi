from flask import Flask, render_template, request, jsonify, redirect, url_for
from datetime import datetime
import sqlite3
from user_manager import UserManager
from network_controller import NetworkController
from time_manager import TimeManager

app = Flask(__name__)
user_manager = UserManager()
network_controller = NetworkController()

# Database initialization
def init_db():
    conn = sqlite3.connect('piso_wifi.db')
    c = conn.cursor()
    
    # Create users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mac_address TEXT UNIQUE,
            time_balance INTEGER DEFAULT 0,
            status TEXT DEFAULT 'inactive'
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
    conn.close()

@app.route('/')
def index():
    devices = []
    connected_macs = network_controller.get_connected_devices()
    
    for mac in connected_macs:
        balance = user_manager.check_balance(mac)
        devices.append({
            'mac_address': mac,
            'time_balance': balance
        })
    
    return render_template('index.html', devices=devices)

@app.route('/add_time', methods=['POST'])
def add_time():
    mac_address = request.form.get('mac_address')
    amount = int(request.form.get('amount'))
    # Convert amount to minutes (1 peso = 5 minutes)
    minutes = amount * 5
    
    if user_manager.add_time(mac_address, amount, minutes):
        network_controller.unblock_mac(mac_address)
        return redirect(url_for('index'))
    return "Error adding time", 400

if __name__ == '__main__':
    init_db()
    time_manager = TimeManager()
    time_manager.start()
    app.run(host='0.0.0.0', port=5000, debug=True) 