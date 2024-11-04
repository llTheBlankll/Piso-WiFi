#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Checking WiFi Hotspot Status...${NC}"

# Check hostapd process
if pgrep hostapd > /dev/null; then
    echo -e "${GREEN}hostapd is running${NC}"
else
    echo -e "${RED}hostapd is not running${NC}"
fi

# Check dnsmasq process
if pgrep dnsmasq > /dev/null; then
    echo -e "${GREEN}dnsmasq is running${NC}"
else
    echo -e "${RED}dnsmasq is not running${NC}"
fi

# Show hostapd configuration
echo -e "\n${YELLOW}hostapd configuration:${NC}"
cat /etc/hostapd/hostapd.conf

# Show interface status
echo -e "\n${YELLOW}Interface status:${NC}"
ip addr show ${WIFI_IFACE}

# Show active connections
echo -e "\n${YELLOW}Connected devices:${NC}"
iw dev ${WIFI_IFACE} station dump

# Show hostapd logs
echo -e "\n${YELLOW}Recent hostapd logs:${NC}"
journalctl -u hostapd -n 20 --no-pager 