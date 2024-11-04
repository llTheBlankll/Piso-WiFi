#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root${NC}"
    exit 1
fi

# Function to check command existence
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${YELLOW}Installing $1...${NC}"
        apt-get install -y $1
    fi
}

echo -e "${GREEN}Installing system dependencies...${NC}"
apt-get update
apt-get install -y \
    python3 \
    python3-pip \
    hostapd \
    dnsmasq \
    iptables \
    iw \
    rfkill \
    net-tools \
    wireless-tools \
    bridge-utils \
    iproute2 \
    tc \
    arping \
    build-essential \
    python3-dev \
    libffi-dev \
    libssl-dev

# Install tc (traffic control) if not present
check_command tc

# Stop services that might interfere
systemctl stop NetworkManager
systemctl stop wpa_supplicant
systemctl stop systemd-resolved
systemctl disable systemd-resolved

# Backup existing configurations
echo -e "${GREEN}Backing up existing configurations...${NC}"
timestamp=$(date +%Y%m%d_%H%M%S)
[ -f /etc/hostapd/hostapd.conf ] && cp /etc/hostapd/hostapd.conf /etc/hostapd/hostapd.conf.backup_$timestamp
[ -f /etc/dnsmasq.conf ] && cp /etc/dnsmasq.conf /etc/dnsmasq.conf.backup_$timestamp
[ -f /etc/sysctl.conf ] && cp /etc/sysctl.conf /etc/sysctl.conf.backup_$timestamp

# Configure system settings
echo -e "${GREEN}Configuring system settings...${NC}"
# Enable IP forwarding
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
sysctl -p

# Configure iptables defaults
iptables -F
iptables -t nat -F
iptables -t mangle -F
iptables -X

# Save iptables rules
iptables-save > /etc/iptables.rules
echo -e "${GREEN}Saved default iptables rules${NC}"

# Create necessary directories
mkdir -p /etc/hostapd
mkdir -p /var/run/hostapd
mkdir -p logs
mkdir -p config

# Set proper permissions
chmod 755 /etc/hostapd
chmod 755 /var/run/hostapd

# Get available interfaces
echo -e "${GREEN}Available network interfaces:${NC}"
ip link show | grep -v "lo:" | grep -v "docker" | awk -F: '{print $2}' | tr -d ' '

# Select interfaces
read -p "Enter the interface for Internet connection: " INTERNET_IFACE
read -p "Enter the interface for WiFi hotspot: " WIFI_IFACE

# Verify interfaces exist
if ! ip link show $INTERNET_IFACE &> /dev/null; then
    echo -e "${RED}Internet interface $INTERNET_IFACE not found${NC}"
    exit 1
fi

if ! ip link show $WIFI_IFACE &> /dev/null; then
    echo -e "${RED}WiFi interface $WIFI_IFACE not found${NC}"
    exit 1
fi

# Install Python dependencies
echo -e "${GREEN}Installing Python dependencies...${NC}"
pip3 install --upgrade pip
pip3 install \
    wireless \
    netifaces \
    psutil \
    flask \
    flask-login \
    python-dotenv \
    requests \
    pyroute2 \
    netfilterqueue \
    scapy

# Save interface selections
echo -e "${GREEN}Saving interface configurations...${NC}"
cat > .env << EOF
WIFI_INTERFACE=${WIFI_IFACE}
INTERNET_INTERFACE=${INTERNET_IFACE}
FLASK_ENV=development
FLASK_DEBUG=True
AP_SSID=PisoWiFi
AP_PASSWORD=pisowifi123
RATE_PESOS_PER_MINUTE=0.2
DATABASE_URL=sqlite:///config/piso_wifi.db
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
LOG_LEVEL=DEBUG
LOG_FILE=logs/piso_wifi.log
CHECK_INTERVAL=60
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
DHCP_RANGE_START=192.168.4.2
DHCP_RANGE_END=192.168.4.20
NETWORK_MASK=255.255.255.0
AP_IP=192.168.4.1
SECRET_KEY=$(openssl rand -hex 32)
EOF

# Create startup script
cat > /etc/systemd/system/pisowifi.service << EOF
[Unit]
Description=PisoWiFi Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$(pwd)
Environment=PYTHONPATH=$(pwd)
ExecStart=/usr/bin/python3 $(pwd)/main.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Initialize the database
mkdir -p config
touch config/piso_wifi.db

# Set proper permissions
chown -R $SUDO_USER:$SUDO_USER .
chmod -R 755 .
chmod 644 .env
chmod 644 config/piso_wifi.db

# Enable the service
systemctl daemon-reload
systemctl enable pisowifi.service

echo -e "${GREEN}Setup completed successfully!${NC}"
echo -e "\nSelected interfaces:"
echo -e "Internet: ${YELLOW}${INTERNET_IFACE}${NC}"
echo -e "WiFi Hotspot: ${YELLOW}${WIFI_IFACE}${NC}"
echo -e "\nAccess Point:"
echo -e "SSID: PisoWiFi"
echo -e "Password: pisowifi123"
echo -e "\nAdmin Interface:"
echo -e "URL: http://192.168.4.1:5000"
echo -e "Username: admin"
echo -e "Password: admin123"
echo -e "\nTo start the service:"
echo -e "   ${YELLOW}sudo systemctl start pisowifi${NC}"
echo -e "\nTo check service status:"
echo -e "   ${YELLOW}sudo systemctl status pisowifi${NC}"
echo -e "\nTo view logs:"
echo -e "   ${YELLOW}sudo journalctl -u pisowifi -f${NC}"
echo -e "\nTo clean up and restore network settings:"
echo -e "   ${YELLOW}sudo ./cleanup_hotspot.sh${NC}"