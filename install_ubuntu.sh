#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if script is run as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root${NC}"
    exit 1
fi

echo -e "${GREEN}Installing PISO WIFI System on Ubuntu...${NC}"

# Install system dependencies
echo -e "${GREEN}Installing system dependencies...${NC}"
apt-get update
apt-get install -y \
    python3 \
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
    linux-headers-$(uname -r)

# Create application directory
APP_DIR="/opt/piso_wifi"
mkdir -p $APP_DIR
cd $APP_DIR

# Create Python virtual environment
echo -e "${GREEN}Setting up Python virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo -e "${GREEN}Installing Python dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
mkdir -p config logs

# Set up environment variables
cat > .env << EOF
WIFI_INTERFACE=wlan0
FLASK_ENV=production
AP_SSID=PisoWiFi
AP_PASSWORD=pisowifi123
RATE_PESOS_PER_MINUTE=0.2
DATABASE_URL=sqlite:///config/piso_wifi.db
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=False
LOG_LEVEL=INFO
LOG_FILE=logs/piso_wifi.log
CHECK_INTERVAL=60
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
DHCP_RANGE_START=192.168.4.2
DHCP_RANGE_END=192.168.4.20
NETWORK_MASK=255.255.255.0
AP_IP=192.168.4.1
EOF

# Create systemd service
echo -e "${GREEN}Creating system service...${NC}"
cat > /etc/systemd/system/pisowifi.service << EOF
[Unit]
Description=PISO WIFI Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/piso_wifi
Environment=PATH=/opt/piso_wifi/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/opt/piso_wifi/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable pisowifi
systemctl start pisowifi

echo -e "${GREEN}Installation complete!${NC}"
echo -e "Access the PISO WIFI system at: http://192.168.4.1:5000"
echo -e "WiFi SSID: PisoWiFi"
echo -e "WiFi Password: pisowifi123"
echo -e "Admin Username: admin"
echo -e "Admin Password: admin123"
echo -e "${YELLOW}Please change the default passwords in production!${NC}"