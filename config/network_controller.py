import subprocess
import re
import os
import logging
from enum import Enum

class Environment(Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"

class NetworkController:
    def __init__(self):
        self.interface = os.getenv('WIFI_INTERFACE', 'wlan0')
        self.env = Environment.DEVELOPMENT if os.getenv('FLASK_ENV') == 'development' else Environment.PRODUCTION
        self.setup_interface()
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def setup_interface(self):
        """Initial setup for the interface based on environment"""
        if self.env == Environment.DEVELOPMENT:
            self.logger.info("Running in development mode - skipping real network setup")
            return
        
        try:
            # Production setup for Orange Pi
            with open('/proc/sys/net/ipv4/ip_forward', 'w') as f:
                f.write('1')
            
            subprocess.run(['iptables', '-t', 'nat', '-A', 'POSTROUTING', '-o', 'eth0', '-j', 'MASQUERADE'])
            subprocess.run(['iptables', '-A', 'FORWARD', '-i', self.interface, '-j', 'ACCEPT'])
            subprocess.run(['iptables', '-A', 'FORWARD', '-o', self.interface, '-j', 'ACCEPT'])
            
        except Exception as e:
            self.logger.error(f"Error setting up interface: {e}")
    
    def block_mac(self, mac_address):
        if self.env == Environment.DEVELOPMENT:
            self.logger.info(f"DEV: Blocking MAC address {mac_address}")
            return True
            
        try:
            subprocess.run([
                'iptables', '-A', 'FORWARD',
                '-m', 'mac', '--mac-source', mac_address,
                '-j', 'DROP'
            ], check=True)
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error blocking MAC: {e}")
            return False
    
    def unblock_mac(self, mac_address):
        if self.env == Environment.DEVELOPMENT:
            self.logger.info(f"DEV: Unblocking MAC address {mac_address}")
            return True
            
        try:
            subprocess.run([
                'iptables', '-D', 'FORWARD',
                '-m', 'mac', '--mac-source', mac_address,
                '-j', 'DROP'
            ], check=True)
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error unblocking MAC: {e}")
            return False
    
    def get_connected_devices(self):
        if self.env == Environment.DEVELOPMENT:
            # Return mock data for development
            return [
                "00:11:22:33:44:55",
                "AA:BB:CC:DD:EE:FF"
            ]
            
        try:
            if self.interface.startswith('wlan'):
                cmd = f"iw dev {self.interface} station dump"
            else:
                cmd = "arp -a"
                
            result = subprocess.run(cmd.split(), capture_output=True, text=True)
            mac_addresses = re.findall(r'([0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2})', result.stdout)
            return mac_addresses
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error getting connected devices: {e}")
            return [] 