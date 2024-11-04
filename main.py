import logging
import threading
import time
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from datetime import datetime
from user_manager import UserManager
from network_controller import NetworkController
from time_manager import TimeManager
from dotenv import load_dotenv
import sqlite3
import os

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Set a secret key for session management
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')  # Make sure to set this in .env

# Admin credentials (move to environment variables in production)
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['is_admin'] = True
            flash('Logged in successfully', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('is_admin', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

def init_services():
    """Initialize all services"""
    logger.info("Initializing services...")
    
    try:
        # Initialize user manager
        logger.info("Initializing user manager...")
        user_manager = UserManager()
        logger.info("User manager initialized")
        
        # Initialize network controller with retry
        logger.info("Initializing network controller...")
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                network_controller = NetworkController()
                logger.info("Network controller initialized")
                break
            except Exception as e:
                retry_count += 1
                logger.error(f"Network controller initialization failed (attempt {retry_count}/{max_retries}): {e}")
                if retry_count >= max_retries:
                    raise
                time.sleep(5)  # Wait before retrying
        
        # Initialize time manager
        logger.info("Initializing time manager...")
        time_manager = TimeManager()
        logger.info("Time manager initialized")
        
        return user_manager, network_controller, time_manager
    except Exception as e:
        logger.error(f"Error initializing services: {e}")
        raise

@app.route('/')
def index():
    try:
        logger.debug("Getting connected devices...")
        connected_devices = network_controller.get_connected_devices()
        logger.debug(f"Found devices: {connected_devices}")
        
        # Add time balance and bandwidth info to each device
        for device in connected_devices:
            mac = device['mac_address']
            device['time_balance'] = user_manager.check_balance(mac)
            
            # Get bandwidth and plan info
            conn = sqlite3.connect(user_manager.db_path)
            c = conn.cursor()
            c.execute('SELECT download_limit, upload_limit, plan, upgrade_requested FROM users WHERE mac_address = ?', (mac,))
            info = c.fetchone()
            conn.close()
            
            if info:
                device['download_limit'] = info[0]
                device['upload_limit'] = info[1]
                device['plan'] = info[2]
                device['upgrade_requested'] = info[3]
            else:
                device['download_limit'] = network_controller.DEFAULT_DOWNLOAD_SPEED
                device['upload_limit'] = network_controller.DEFAULT_UPLOAD_SPEED
                device['plan'] = 'default'
                device['upgrade_requested'] = False
        
        logger.debug(f"Devices with balance: {connected_devices}")
        return render_template('index.html', devices=connected_devices, is_admin=session.get('is_admin', False))
    except Exception as e:
        logger.error(f"Error in index route: {e}")
        return "Internal Server Error", 500

@app.route('/add_time', methods=['POST'])
def add_time():
    try:
        mac_address = request.form.get('mac_address')
        amount = int(request.form.get('amount'))
        # Convert amount to minutes (1 peso = 1 minute)
        minutes = amount * 1
        
        logger.info(f"Adding {minutes} minutes for MAC {mac_address}")
        if user_manager.add_time(mac_address, amount, minutes):
            network_controller.unblock_mac(mac_address)
            return redirect(url_for('index'))
        return "Error adding time", 400
    except Exception as e:
        logger.error(f"Error in add_time route: {e}")
        return "Internal Server Error", 500

@app.route('/deduct_time', methods=['POST'])
def deduct_time():
    try:
        mac_address = request.form.get('mac_address')
        minutes = int(request.form.get('minutes', 0))
        
        if minutes <= 0:
            flash('Please enter a valid number of minutes', 'error')
            return redirect(url_for('index'))
        
        logger.info(f"Manually deducting {minutes} minutes from {mac_address}")
        
        # Deduct time
        if user_manager.deduct_time(mac_address, minutes):
            # Check if balance is now zero
            new_balance = user_manager.check_balance(mac_address)
            if new_balance <= 0:
                network_controller.block_mac(mac_address)
                logger.info(f"Blocked {mac_address} due to zero balance after manual deduction")
            flash(f'Successfully deducted {minutes} minutes', 'success')
        else:
            flash('Error deducting time', 'error')
            
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Error in deduct_time route: {e}")
        flash('Internal Server Error', 'error')
        return redirect(url_for('index'))

@app.route('/debug/connections')
def debug_connections():
    """Debug endpoint to check connection status"""
    try:
        # Get connected devices
        devices = network_controller.get_connected_devices()
        
        # Get interface status
        ap_status = network_controller._execute_command(f"ip addr show {network_controller.ap_interface}")
        internet_status = network_controller._execute_command(f"ip addr show {network_controller.internet_interface}")
        
        # Get hostapd status
        hostapd_status = network_controller._execute_command("systemctl status hostapd")
        
        # Get iptables rules
        iptables_rules = network_controller._execute_command("iptables -L -n -v")
        
        return jsonify({
            'connected_devices': devices,
            'ap_interface_status': ap_status,
            'internet_interface_status': internet_status,
            'hostapd_status': hostapd_status,
            'iptables_rules': iptables_rules
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/set_bandwidth', methods=['POST'])
def set_bandwidth():
    try:
        mac_address = request.form.get('mac_address')
        download = int(request.form.get('download', 1024))
        upload = int(request.form.get('upload', 512))
        
        # Validate input
        if download < 32 or upload < 32:
            flash('Minimum bandwidth is 32 kbps', 'error')
            return redirect(url_for('index'))
        
        if download > 100000 or upload > 100000:
            flash('Maximum bandwidth is 100 Mbps', 'error')
            return redirect(url_for('index'))
        
        # Update database
        if user_manager.set_bandwidth(mac_address, download, upload):
            # Apply network rules
            if network_controller.set_bandwidth_limit(mac_address, download, upload):
                flash('Bandwidth limits updated successfully', 'success')
            else:
                flash('Error applying bandwidth limits', 'error')
        else:
            flash('Error updating bandwidth settings', 'error')
            
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Error in set_bandwidth route: {e}")
        flash('Internal Server Error', 'error')
        return redirect(url_for('index'))

@app.route('/request_upgrade', methods=['POST'])
def request_upgrade():
    try:
        mac_address = request.form.get('mac_address')
        
        # Update upgrade request status
        conn = sqlite3.connect(user_manager.db_path)
        c = conn.cursor()
        c.execute('UPDATE users SET upgrade_requested = 1 WHERE mac_address = ?', (mac_address,))
        conn.commit()
        conn.close()
        
        flash('Premium upgrade requested. Please wait for admin approval.', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Error requesting upgrade: {e}")
        flash('Error requesting upgrade', 'error')
        return redirect(url_for('index'))

@app.route('/manage_plan', methods=['POST'])
def manage_plan():
    try:
        if not session.get('is_admin'):
            flash('Admin access required', 'error')
            return redirect(url_for('index'))
            
        mac_address = request.form.get('mac_address')
        new_plan = request.form.get('plan')
        
        # First remove existing bandwidth limits
        network_controller.remove_bandwidth_limit(mac_address)
        
        # Update plan and speeds
        conn = sqlite3.connect(user_manager.db_path)
        c = conn.cursor()
        
        if new_plan == 'premium':
            download_speed = network_controller.PREMIUM_DOWNLOAD_SPEED
            upload_speed = network_controller.PREMIUM_UPLOAD_SPEED
        else:
            download_speed = network_controller.DEFAULT_DOWNLOAD_SPEED
            upload_speed = network_controller.DEFAULT_UPLOAD_SPEED
            
        c.execute('''
            UPDATE users 
            SET plan = ?,
                download_limit = ?,
                upload_limit = ?,
                upgrade_requested = 0
            WHERE mac_address = ?
        ''', (new_plan, download_speed, upload_speed, mac_address))
        
        conn.commit()
        conn.close()
        
        # Apply new bandwidth limits with verification
        if network_controller.set_bandwidth_limit(mac_address, download_speed, upload_speed):
            flash(f'Plan updated to {new_plan} with new bandwidth limits', 'success')
        else:
            flash(f'Plan updated to {new_plan} but bandwidth limits may not be applied correctly', 'warning')
        
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Error managing plan: {e}")
        flash('Error updating plan', 'error')
        return redirect(url_for('index'))

if __name__ == '__main__':
    try:
        logger.info("Starting PISO WIFI application...")
        
        # Initialize services
        user_manager, network_controller, time_manager = init_services()
        
        # Start time manager only (it handles connection monitoring)
        logger.info("Starting time manager...")
        time_manager.start()
        
        # Start Flask application
        logger.info("Starting web server...")
        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise