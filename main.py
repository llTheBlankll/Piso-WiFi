import logging
import threading
import time
from flask import Flask, render_template, request, jsonify, redirect, url_for
from datetime import datetime
from user_manager import UserManager
from network_controller import NetworkController
from time_manager import TimeManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

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
        
        # Add time balance to each device
        for device in connected_devices:
            device['time_balance'] = user_manager.check_balance(device['mac_address'])
        
        logger.debug(f"Devices with balance: {connected_devices}")
        return render_template('index.html', devices=connected_devices)
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