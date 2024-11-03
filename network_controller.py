import subprocess
import re

class NetworkController:
    def __init__(self):
        self.interface = "wlan0"  # Change this to your WiFi interface
    
    def block_mac(self, mac_address):
        try:
            cmd = f"iptables -A FORWARD -m mac --mac-source {mac_address} -j DROP"
            subprocess.run(cmd.split(), check=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def unblock_mac(self, mac_address):
        try:
            cmd = f"iptables -D FORWARD -m mac --mac-source {mac_address} -j DROP"
            subprocess.run(cmd.split(), check=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def get_connected_devices(self):
        try:
            cmd = "arp -a"
            result = subprocess.run(cmd.split(), capture_output=True, text=True)
            mac_addresses = re.findall(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', result.stdout)
            return mac_addresses
        except subprocess.CalledProcessError:
            return [] 