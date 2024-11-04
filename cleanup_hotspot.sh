#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Check if script is run as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root${NC}"
    exit 1
fi

# Stop services
echo -e "${GREEN}Stopping hostapd and dnsmasq...${NC}"
systemctl stop hostapd
systemctl stop dnsmasq

# Remove configurations
echo -e "${GREEN}Removing configurations...${NC}"
#rm -f /etc/hostapd/hostapd.conf
mv /etc/dnsmasq.conf.orig /etc/dnsmasq.conf 2>/dev/null

# Clear iptables rules
echo -e "${GREEN}Clearing iptables rules...${NC}"
iptables -F
iptables -t nat -F
iptables -X
iptables -P FORWARD ACCEPT
iptables -P INPUT ACCEPT
iptables -P OUTPUT ACCEPT

# Disable IP forwarding
echo -e "${GREEN}Disabling IP forwarding...${NC}"
echo 0 > /proc/sys/net/ipv4/ip_forward

# Restart network services
echo -e "${GREEN}Restarting network services...${NC}"
systemctl restart NetworkManager
systemctl restart wpa_supplicant
systemctl restart systemd-networkd

echo -e "${GREEN}Cleanup complete! Network interfaces restored to normal operation.${NC}" 
