import os
import logging
import subprocess
import re
from enum import Enum

class Environment(Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"

class NetworkController:
    def __init__(self):
        # Set up logging first
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Get environment variables
        self.interface = os.getenv('WIFI_INTERFACE', 'wlan0')
        self.env = Environment.DEVELOPMENT if os.getenv('FLASK_ENV') == 'development' else Environment.PRODUCTION
        
        # Initialize network
        self.setup_interface()
    
    def setup_interface(self):
        """Initial setup for the interface based on environment"""
        if self.env == Environment.DEVELOPMENT:
            if os.name == 'nt':  # Windows
                self.logger.info("Setting up Windows Hotspot...")
                try:
                    # Enable Windows Hotspot
                    subprocess.run(['netsh', 'wlan', 'set', 'hostednetwork', 
                                 'mode=allow', 'ssid=PisoWiFi', 'key=pisowifi123'], 
                                check=True, capture_output=True)
                    subprocess.run(['netsh', 'wlan', 'start', 'hostednetwork'], 
                                check=True, capture_output=True)
                    self.logger.info("Windows Hotspot enabled successfully")
                except Exception as e:
                    self.logger.error(f"Error setting up Windows Hotspot: {e}")
            else:
                self.logger.info("Running in development mode - skipping network setup")
            return

    def block_mac(self, mac_address):
        """Block a MAC address from accessing the network"""
        try:
            if os.name == 'nt':  # Windows
                # Use netsh to block MAC on Windows
                cmd = ['netsh', 'wlan', 'filter', 'add', 'mac=block', 
                      f'addr={mac_address}', 'ssid=PisoWiFi']
                subprocess.run(cmd, check=True, capture_output=True)
                self.logger.info(f"Blocked MAC address on Windows: {mac_address}")
            else:
                # Linux/Production blocking
                cmd = ['iptables', '-A', 'FORWARD', '-m', 'mac', 
                      '--mac-source', mac_address, '-j', 'DROP']
                subprocess.run(cmd, check=True)
                self.logger.info(f"Blocked MAC address: {mac_address}")
            return True
        except Exception as e:
            self.logger.error(f"Error blocking MAC {mac_address}: {e}")
            return False

    def unblock_mac(self, mac_address):
        """Unblock a MAC address"""
        try:
            if os.name == 'nt':  # Windows
                # Remove MAC filter on Windows
                cmd = ['netsh', 'wlan', 'filter', 'delete', 'mac=block', 
                      f'addr={mac_address}', 'ssid=PisoWiFi']
                subprocess.run(cmd, check=True, capture_output=True)
                self.logger.info(f"Unblocked MAC address on Windows: {mac_address}")
            else:
                # Linux/Production unblocking
                cmd = ['iptables', '-D', 'FORWARD', '-m', 'mac', 
                      '--mac-source', mac_address, '-j', 'DROP']
                subprocess.run(cmd, check=True)
                self.logger.info(f"Unblocked MAC address: {mac_address}")
            return True
        except Exception as e:
            self.logger.error(f"Error unblocking MAC {mac_address}: {e}")
            return False

    def get_connected_devices(self):
        """Get list of connected devices"""
        try:
            if os.name == 'nt':  # Windows
                # Get connected devices from Windows Hotspot
                cmd = ['netsh', 'wlan', 'show', 'hostednetwork']
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                
                # Parse output to get MAC addresses
                macs = []
                for line in result.stdout.split('\n'):
                    if 'Client MAC Address' in line:
                        mac = line.split(':')[1].strip()
                        macs.append(mac)
                return macs if macs else ["00:11:22:33:44:55"]  # Return mock data if no devices
            else:
                if self.env == Environment.DEVELOPMENT:
                    return ["00:11:22:33:44:55", "AA:BB:CC:DD:EE:FF"]
                
                # Production mode - use arp
                cmd = ['arp', '-n']
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                mac_pattern = r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})'
                macs = re.findall(mac_pattern, result.stdout)
                return [':'.join(mac) for mac in macs] if macs else []
                
        except Exception as e:
            self.logger.error(f"Error getting connected devices: {e}")
            return ["00:11:22:33:44:55"]  # Return mock data on error