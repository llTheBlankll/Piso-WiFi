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

echo -e "${GREEN}Cleaning up PisoWiFi configuration...${NC}"

# Stop the service
systemctl stop pisowifi
systemctl disable pisowifi

# Stop services
systemctl stop hostapd
systemctl stop dnsmasq

# Remove service file
rm -f /etc/systemd/system/pisowifi.service
systemctl daemon-reload

# Clean up iptables rules
echo -e "${YELLOW}Cleaning up iptables rules...${NC}"
iptables -F
iptables -t nat -F
iptables -t mangle -F
iptables -X
iptables -P INPUT ACCEPT
iptables -P FORWARD ACCEPT
iptables -P OUTPUT ACCEPT

# Remove QoS rules
echo -e "${YELLOW}Cleaning up QoS rules...${NC}"
for interface in $(ip link show | grep -v lo: | cut -d: -f2 | tr -d ' '); do
    tc qdisc del dev $interface root 2>/dev/null
    tc qdisc del dev $interface ingress 2>/dev/null
done

# Restore original configurations if they exist
echo -e "${YELLOW}Restoring original configurations...${NC}"
timestamp=$(find /etc/hostapd/ -name "hostapd.conf.backup_*" | sort -r | head -n1)
if [ -n "$timestamp" ]; then
    cp $timestamp /etc/hostapd/hostapd.conf
fi

timestamp=$(find /etc/ -name "dnsmasq.conf.backup_*" | sort -r | head -n1)
if [ -n "$timestamp" ]; then
    cp $timestamp /etc/dnsmasq.conf
fi

timestamp=$(find /etc/ -name "sysctl.conf.backup_*" | sort -r | head -n1)
if [ -n "$timestamp" ]; then
    cp $timestamp /etc/sysctl.conf
fi

# Restore IP forwarding to default
sed -i '/net.ipv4.ip_forward=1/d' /etc/sysctl.conf
echo "net.ipv4.ip_forward=0" >> /etc/sysctl.conf
sysctl -p

# Restart network services
echo -e "${YELLOW}Restarting network services...${NC}"
systemctl enable systemd-resolved
systemctl start systemd-resolved
systemctl start NetworkManager
systemctl start wpa_supplicant

# Clean up temporary files
echo -e "${YELLOW}Cleaning up temporary files...${NC}"
rm -f /var/run/hostapd.pid
rm -f /var/run/dnsmasq.pid

echo -e "${GREEN}Cleanup completed successfully!${NC}"
echo -e "\nNetwork services have been restored to their default state."
echo -e "You may need to reconnect to your network manually."
