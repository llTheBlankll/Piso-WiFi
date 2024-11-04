import os
import logging
import subprocess
import re
import time
import netifaces
from enum import Enum

class NetworkController:
    def __init__(self):
        """Initialize Network Controller"""
        try:
            # Set up logging first
            logging.basicConfig(level=logging.DEBUG)
            self.logger = logging.getLogger(__name__)
            self.logger.info("Initializing Network Controller...")
            
            # Get environment variables
            self.ap_interface = os.getenv('WIFI_INTERFACE', 'wlan0')
            self.internet_interface = os.getenv('INTERNET_INTERFACE', 'wlan1')
            self.ssid = os.getenv('AP_SSID', 'PisoWiFi')
            self.password = os.getenv('AP_PASSWORD', 'pisowifi123')
            self.ip = os.getenv('AP_IP', '192.168.4.1')
            
            self.logger.info(f"Using AP interface: {self.ap_interface}")
            self.logger.info(f"Using Internet interface: {self.internet_interface}")
            self.logger.info(f"SSID: {self.ssid}")
            self.logger.info(f"IP: {self.ip}")
            
            # Paths for config files
            self.hostapd_conf = '/etc/hostapd/hostapd.conf'
            self.dnsmasq_conf = '/etc/dnsmasq.conf'
            
            # Keep track of connected devices
            self.connected_devices = set()
            
            # Verify system requirements
            self._verify_requirements()
            
            # Configure and start AP
            self.logger.info("Configuring access point...")
            self._configure_ap()
            
            self.logger.info("Starting access point...")
            self.start_ap()
            
            # Verify AP is running
            if not self._check_ap_status():
                raise Exception("AP failed to start properly")
            
            self.logger.info("Network Controller initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Network Controller: {e}")
            self._dump_debug_info()
            raise

    def _verify_requirements(self):
        """Verify system requirements are met"""
        try:
            self.logger.info("Verifying system requirements...")
            
            # Check if running as root
            if os.geteuid() != 0:
                raise Exception("Must run as root")
            
            # Check if interface exists
            if not os.path.exists(f"/sys/class/net/{self.ap_interface}"):
                raise Exception(f"Interface {self.ap_interface} does not exist")
            
            # Check for required commands
            required_commands = ['hostapd', 'dnsmasq', 'iw', 'ip', 'iptables']
            for cmd in required_commands:
                if not self._command_exists(cmd):
                    raise Exception(f"Required command '{cmd}' not found")
            
            # Check if interface supports AP mode
            try:
                iw_output = self._execute_command(f"iw list | grep -A 4 'Supported interface modes'")
                if "AP" not in iw_output:
                    raise Exception(f"Interface {self.ap_interface} does not support AP mode")
            except Exception as e:
                self.logger.warning(f"Could not verify AP mode support: {e}")
            
            self.logger.info("System requirements verified")
            
        except Exception as e:
            self.logger.error(f"System requirements check failed: {e}")
            raise

    def _command_exists(self, cmd):
        """Check if a command exists"""
        return subprocess.run(f"which {cmd}", shell=True, capture_output=True).returncode == 0

    def _configure_ap(self):
        """Configure hostapd and dnsmasq"""
        try:
            # Create hostapd directory if it doesn't exist
            os.makedirs('/etc/hostapd', exist_ok=True)
            
            # Configure hostapd with open network settings
            hostapd_config = f"""
# Interface configuration
interface={self.ap_interface}
driver=nl80211
ssid={self.ssid}

# Hardware configuration
hw_mode=g
channel=7
ieee80211n=1
wmm_enabled=0

# Open network configuration
auth_algs=1
ignore_broadcast_ssid=0

# Debugging
logger_syslog=-1
logger_syslog_level=2
logger_stdout=-1
logger_stdout_level=2

# Stability settings
beacon_int=100
dtim_period=2
max_num_sta=10
rts_threshold=2347
fragm_threshold=2346
"""
            # Write hostapd configuration
            with open(self.hostapd_conf, 'w') as f:
                f.write(hostapd_config.strip())
            
            # Set proper ownership and permissions
            self._execute_command(f"chown root:root {self.hostapd_conf}")
            self._execute_command(f"chmod 644 {self.hostapd_conf}")
            
            # Configure dnsmasq
            dnsmasq_config = f"""
# Interface configuration
interface={self.ap_interface}
no-dhcp-interface=lo
bind-interfaces

# DHCP server configuration
dhcp-range={os.getenv('DHCP_RANGE_START', '192.168.4.2')},{os.getenv('DHCP_RANGE_END', '192.168.4.20')},{os.getenv('NETWORK_MASK', '255.255.255.0')},24h
dhcp-option=option:router,{self.ip}
dhcp-option=option:dns-server,{self.ip}
dhcp-option=option:netmask,{os.getenv('NETWORK_MASK', '255.255.255.0')}

# DNS configuration
no-resolv
no-poll
server=8.8.8.8
server=8.8.4.4

# Logging
log-queries
log-dhcp
"""
            # Write dnsmasq configuration
            with open(self.dnsmasq_conf, 'w') as f:
                f.write(dnsmasq_config.strip())
            
            self._execute_command(f"chown root:root {self.dnsmasq_conf}")
            self._execute_command(f"chmod 644 {self.dnsmasq_conf}")
            
            self.logger.info("AP configuration completed")
            
        except Exception as e:
            self.logger.error(f"Error configuring AP: {e}")
            raise
    
    def start_ap(self):
        """Start the WiFi Access Point"""
        try:
            # Stop any existing processes - ignore if not running
            try:
                self._execute_command("killall hostapd", ignore_errors=True)
            except subprocess.CalledProcessError as e:
                if "no process found" in str(e.stderr):
                    self.logger.debug("No hostapd process found to kill")
                else:
                    self.logger.warning(f"Error killing hostapd: {e}")
                
            try:
                self._execute_command("killall dnsmasq", ignore_errors=True)
            except subprocess.CalledProcessError as e:
                if "no process found" in str(e.stderr):
                    self.logger.debug("No dnsmasq process found to kill")
                else:
                    self.logger.warning(f"Error killing dnsmasq: {e}")
            
            time.sleep(1)
            
            # Stop NetworkManager only for AP interface
            try:
                self._execute_command(f"nmcli device set {self.ap_interface} managed no")
            except subprocess.CalledProcessError as e:
                self.logger.warning(f"Could not set {self.ap_interface} to unmanaged: {e}")
            
            # Configure AP interface
            self._execute_command("rfkill unblock wifi")
            self._execute_command(f"ip link set {self.ap_interface} down")
            self._execute_command(f"iw dev {self.ap_interface} set type __ap")
            self._execute_command(f"ip addr flush dev {self.ap_interface}")
            self._execute_command(f"ip addr add {self.ip}/24 dev {self.ap_interface}")
            self._execute_command(f"ip link set {self.ap_interface} up")
            time.sleep(1)
            
            # Start hostapd with explicit configuration
            self._execute_command(f"hostapd -B -P /run/hostapd.pid {self.hostapd_conf}")
            time.sleep(2)
            self._check_ap_status()
            
            # Start dnsmasq
            self._execute_command("systemctl restart dnsmasq")
            
            # Enable IP forwarding and NAT with better control
            self._execute_command("echo 1 > /proc/sys/net/ipv4/ip_forward")
            self._execute_command("iptables -t nat -F")
            self._execute_command("iptables -F")
            
            # Default policies
            self._execute_command("iptables -P FORWARD DROP")  # Default deny
            self._execute_command("iptables -P INPUT ACCEPT")
            self._execute_command("iptables -P OUTPUT ACCEPT")
            
            # Allow established connections
            self._execute_command("iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT")
            
            # NAT rules
            self._execute_command(f"iptables -t nat -A POSTROUTING -o {self.internet_interface} -j MASQUERADE")
            
            # Allow DNS and DHCP
            self._execute_command(f"iptables -A FORWARD -i {self.ap_interface} -p udp --dport 53 -j ACCEPT")
            self._execute_command(f"iptables -A FORWARD -i {self.ap_interface} -p udp --dport 67:68 -j ACCEPT")
            
            # Allow access to local web interface
            self._execute_command(f"iptables -A FORWARD -i {self.ap_interface} -d {self.ip} -j ACCEPT")
            
            # Block all other forward traffic by default (redundant but explicit)
            self._execute_command(f"iptables -A FORWARD -i {self.ap_interface} -j DROP")
            
            # Verify hostapd is running
            if not self._check_hostapd_running():
                raise Exception("Hostapd failed to start")
                
            self.logger.info(f"Started WiFi Access Point: {self.ssid}")
            
        except Exception as e:
            self.logger.error(f"Failed to start WiFi Access Point: {e}")
            self._dump_debug_info()
            raise

    def _check_hostapd_running(self):
        """Check if hostapd is running"""
        try:
            # Multiple checks for hostapd
            ps_output = self._execute_command("ps aux | grep '[h]ostapd'")
            if not ps_output:
                self.logger.error("No hostapd process found")
                return False

            # Check if hostapd is responding
            try:
                hostapd_cli = self._execute_command("hostapd_cli status")
                if "state=ENABLED" not in hostapd_cli:
                    self.logger.error("Hostapd is not in ENABLED state")
                    return False
            except:
                self.logger.warning("Could not check hostapd_cli status")

            # Check if interface is in AP mode
            iw_info = self._execute_command(f"iw dev {self.ap_interface} info")
            if "type AP" not in iw_info:
                self.logger.error("Interface not in AP mode")
                return False

            self.logger.debug("Hostapd check passed")
            return True

        except Exception as e:
            self.logger.error(f"Error checking hostapd: {e}")
            return False

    def _dump_debug_info(self):
        """Dump debug information when something goes wrong"""
        try:
            self.logger.error("=== Debug Information ===")
            
            # Check interface status
            self.logger.error("Interface Status:")
            self.logger.error(self._execute_command(f"ip addr show {self.ap_interface}"))
            
            # Check hostapd status
            self.logger.error("Hostapd Status:")
            self.logger.error(self._execute_command("systemctl status hostapd"))
            
            # Check hostapd logs
            self.logger.error("Hostapd Logs:")
            self.logger.error(self._execute_command("journalctl -u hostapd -n 50"))
            
            # Check dnsmasq status
            self.logger.error("Dnsmasq Status:")
            self.logger.error(self._execute_command("systemctl status dnsmasq"))
            
            # Check RF kill status
            self.logger.error("RF Kill Status:")
            self.logger.error(self._execute_command("rfkill list"))
            
            # Check network interfaces
            self.logger.error("Network Interfaces:")
            self.logger.error(self._execute_command("iwconfig"))
            
            self.logger.error("=====================")
        except Exception as e:
            self.logger.error(f"Error dumping debug info: {e}")
    
    def stop_ap(self):
        """Stop the WiFi Access Point"""
        try:
            self._execute_command("systemctl stop hostapd")
            self._execute_command("systemctl stop dnsmasq")
            self._execute_command(f"ip link set {self.ap_interface} down")
            
            # Re-enable NetworkManager for both interfaces
            self._execute_command(f"nmcli device set {self.ap_interface} managed yes")
            self._execute_command(f"nmcli device set {self.internet_interface} managed yes")
            
            self.logger.info("WiFi Access Point stopped")
        except Exception as e:
            self.logger.error(f"Failed to stop WiFi Access Point: {e}")

    def get_connected_devices(self):
        """Get list of connected devices with detailed information"""
        try:
            connected_devices = []
            
            # Get DHCP leases first for hostname and IP information
            dhcp_info = {}
            try:
                leases_file = "/var/lib/misc/dnsmasq.leases"
                if os.path.exists(leases_file):
                    current_time = int(time.time())
                    with open(leases_file, 'r') as f:
                        for line in f:
                            parts = line.strip().split()
                            if len(parts) >= 5:
                                lease_expiry = int(parts[0])
                                mac = parts[1].upper()
                                ip = parts[2]
                                hostname = parts[3] if parts[3] != '*' else 'Unknown'
                                
                                # Only include active leases in our subnet
                                if lease_expiry > current_time and ip.startswith("192.168.4."):
                                    dhcp_info[mac] = {
                                        'ip': ip,
                                        'hostname': hostname,
                                        'lease_expiry': lease_expiry
                                    }
                self.logger.debug(f"DHCP info found: {dhcp_info}")
            except Exception as e:
                self.logger.warning(f"DHCP leases check failed: {e}")

            # Get currently connected devices
            try:
                result = self._execute_command(f"iw dev {self.ap_interface} station dump")
                for line in result.split('\n'):
                    if "Station" in line:
                        mac = line.split()[1].upper()
                        if self._is_valid_mac(mac):
                            device_info = {
                                'mac_address': mac,
                                'ip': dhcp_info.get(mac, {}).get('ip', 'Unknown'),
                                'hostname': dhcp_info.get(mac, {}).get('hostname', 'Unknown'),
                                'connected': True
                            }
                            
                            # Get signal strength and other stats
                            try:
                                info = self._execute_command(f"iw dev {self.ap_interface} station get {mac}")
                                signal = re.search(r"signal:\s*([-\d]+)\s*dBm", info)
                                if signal:
                                    device_info['signal'] = f"{signal.group(1)} dBm"
                            except Exception as e:
                                self.logger.debug(f"Could not get signal info for {mac}: {e}")
                            
                            connected_devices.append(device_info)
                            
                self.logger.debug(f"Connected devices with info: {connected_devices}")
            except Exception as e:
                self.logger.warning(f"IW station dump failed: {e}")

            # Update connected devices set
            current_macs = {device['mac_address'] for device in connected_devices}
            new_devices = current_macs - self.connected_devices
            disconnected_devices = self.connected_devices - current_macs

            # Log new connections and disconnections
            for mac in new_devices:
                self.logger.info(f"New device connected: {mac}")
                self._log_device_details(mac)
                # Block new devices by default
                self.block_mac(mac)

            for mac in disconnected_devices:
                self.logger.info(f"Device disconnected: {mac}")

            # Update connected devices
            self.connected_devices = current_macs

            # Debug output
            self.logger.info(f"Total connected devices: {len(connected_devices)}")
            return connected_devices

        except Exception as e:
            self.logger.error(f"Error getting connected devices: {e}")
            self._dump_debug_info()
            return []

    def _is_valid_mac(self, mac):
        """Validate MAC address format"""
        try:
            return bool(re.match(r'^([0-9A-F]{2}:){5}[0-9A-F]{2}$', mac.upper()))
        except:
            return False

    def _log_device_details(self, mac):
        """Log additional details about a connected device"""
        try:
            # Get station info
            info = self._execute_command(f"iw dev {self.ap_interface} station get {mac}")
            
            # Extract useful information
            signal = re.search(r"signal:\s*([-\d]+)\s*dBm", info)
            rx_bytes = re.search(r"rx bytes:\s*(\d+)", info)
            tx_bytes = re.search(r"tx bytes:\s*(\d+)", info)
            connected_time = re.search(r"connected time:\s*(\d+)\s*seconds", info)
            
            details = []
            if signal:
                details.append(f"Signal: {signal.group(1)}dBm")
            if rx_bytes:
                details.append(f"RX: {int(rx_bytes.group(1))/1024:.2f}KB")
            if tx_bytes:
                details.append(f"TX: {int(tx_bytes.group(1))/1024:.2f}KB")
            if connected_time:
                details.append(f"Connected time: {connected_time.group(1)}s")
                
            self.logger.info(f"Device {mac} details: {', '.join(details)}")
            
        except Exception as e:
            self.logger.debug(f"Could not get detailed info for {mac}: {e}")

    def block_mac(self, mac_address):
        """Block a MAC address using iptables"""
        try:
            # Remove any existing rules for this MAC
            self._execute_command(f"iptables -D FORWARD -m mac --mac-source {mac_address} -j ACCEPT", ignore_errors=True)
            self._execute_command(f"iptables -D FORWARD -m mac --mac-source {mac_address} -j DROP", ignore_errors=True)
            
            # Add block rule
            self._execute_command(f"iptables -I FORWARD 1 -m mac --mac-source {mac_address} -j DROP")
            self.logger.info(f"Blocked MAC address: {mac_address}")
            return True
        except Exception as e:
            self.logger.error(f"Error blocking MAC {mac_address}: {e}")
            return False

    def unblock_mac(self, mac_address):
        """Unblock a MAC address using iptables"""
        try:
            # Remove any existing rules for this MAC
            self._execute_command(f"iptables -D FORWARD -m mac --mac-source {mac_address} -j ACCEPT", ignore_errors=True)
            self._execute_command(f"iptables -D FORWARD -m mac --mac-source {mac_address} -j DROP", ignore_errors=True)
            
            # Add allow rule
            self._execute_command(f"iptables -I FORWARD 1 -m mac --mac-source {mac_address} -j ACCEPT")
            self.logger.info(f"Unblocked MAC address: {mac_address}")
            return True
        except Exception as e:
            self.logger.error(f"Error unblocking MAC {mac_address}: {e}")
            return False

    def _execute_command(self, command, ignore_errors=False):
        """Execute a shell command and return output"""
        try:
            self.logger.debug(f"Executing command: {command}")
            result = subprocess.run(
                command, 
                shell=True,
                check=not ignore_errors,  # Only raise CalledProcessError if ignore_errors is False
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            if result.stdout:
                self.logger.debug(f"Command output: {result.stdout}")
            if result.stderr:
                self.logger.debug(f"Command stderr: {result.stderr}")
                
            return result.stdout
            
        except subprocess.CalledProcessError as e:
            if ignore_errors:
                self.logger.debug(f"Ignored error in command '{command}': {e}")
                return ""
            else:
                self.logger.error(f"Command failed: {command}")
                self.logger.error(f"Error output: {e.stderr}")
                raise

    def monitor_connections(self):
        """Monitor for new connections"""
        while True:
            self.get_connected_devices()
            time.sleep(5)

    def _check_ap_status(self):
        """Check if AP is running properly"""
        try:
            # Check hostapd process
            hostapd_running = self._check_hostapd_running()
            if not hostapd_running:
                self.logger.error("Hostapd is not running")
                return False

            # Check interface status
            interface_status = self._execute_command(f"ip addr show {self.ap_interface}")
            if "UP" not in interface_status:
                self.logger.error(f"Interface {self.ap_interface} is not UP")
                return False

            # Check if interface has correct IP
            if self.ip not in interface_status:
                self.logger.error(f"Interface {self.ap_interface} does not have IP {self.ip}")
                return False

            # Check dnsmasq
            dnsmasq_running = "running" in self._execute_command("systemctl status dnsmasq")
            if not dnsmasq_running:
                self.logger.error("Dnsmasq is not running")
                return False

            self.logger.debug("AP status check passed")
            return True

        except Exception as e:
            self.logger.error(f"Error checking AP status: {e}")
            return False

    def _check_iptables_rules(self):
        """Debug function to check iptables rules"""
        try:
            rules = self._execute_command("iptables-save")
            self.logger.debug("Current iptables rules:")
            self.logger.debug(rules)
            return rules
        except Exception as e:
            self.logger.error(f"Error checking iptables rules: {e}")
            return None