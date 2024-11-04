#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Function to list available interfaces
list_interfaces() {
    echo -e "\nAvailable network interfaces:"
    ip link show | grep -E '^[0-9]+: ' | cut -d: -f2 | awk '{print $1}'
}

# Function to validate interface exists
validate_interface() {
    ip link show "$1" >/dev/null 2>&1
    return $?
}

echo -e "${GREEN}Setting up PISO WIFI development environment...${NC}"

# Check if script is run as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root${NC}"
    exit 1
fi

# Install system dependencies
echo -e "${GREEN}Installing system dependencies...${NC}"
apt-get update
apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    libnl-3-dev \
    libnl-genl-3-dev \
    libssl-dev \
    net-tools \
    wireless-tools \
    sqlite3 \
    rfkill \
    build-essential \
    pkg-config \
    dnsmasq \
    hostapd \
    linux-headers-$(uname -r) \
    conntrack

# Select interfaces
list_interfaces
echo -e "\n${YELLOW}Select interfaces for setup:${NC}"

# Internet interface selection
while true; do
    read -p "Enter the interface for internet connection (e.g., eth0): " INTERNET_IFACE
    if validate_interface "$INTERNET_IFACE"; then
        break
    else
        echo -e "${RED}Invalid interface. Please select from the list above.${NC}"
    fi
done

# WiFi interface selection
while true; do
    read -p "Enter the interface for WiFi hotspot (e.g., wlan0): " WIFI_IFACE
    if validate_interface "$WIFI_IFACE"; then
        if [ "$WIFI_IFACE" != "$INTERNET_IFACE" ]; then
            break
        else
            echo -e "${RED}Please select a different interface for WiFi hotspot.${NC}"
        fi
    else
        echo -e "${RED}Invalid interface. Please select from the list above.${NC}"
    fi
done

# Create project structure
echo -e "${GREEN}Creating project directories...${NC}"
mkdir -p config logs

# Create Python virtual environment
echo -e "${GREEN}Creating Python virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# Install development dependencies
echo -e "${GREEN}Installing Python dependencies...${NC}"
pip install --upgrade pip
pip install wireless netifaces psutil
pip install PyAccessPoint==0.2.5
pip install -r requirements.txt

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
EOF

# Initialize the database
mkdir -p config
touch config/piso_wifi.db

echo -e "${GREEN}Starting PISO WIFI application...${NC}"
echo -e "\nSelected interfaces:"
echo -e "Internet: ${YELLOW}${INTERNET_IFACE}${NC}"
echo -e "WiFi Hotspot: ${YELLOW}${WIFI_IFACE}${NC}"
echo -e "\nAccess Points:"
echo -e "SSID: PisoWiFi"
echo -e "Password: pisowifi123"
echo -e "\nAdmin Interface:"
echo -e "URL: http://192.168.4.1:5000"
echo -e "Username: admin"
echo -e "Password: admin123"
echo -e "\nTo clean up and restore network settings later:"
echo -e "   ${YELLOW}sudo ./cleanup_hotspot.sh${NC}"

# Start the Flask application
python main.py