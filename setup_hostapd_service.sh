#!/bin/bash

# Create systemd service file
cat > /etc/systemd/system/pisowifi-hostapd.service << EOF
[Unit]
Description=PisoWiFi Hostapd Service
After=network.target
Wants=network.target

[Service]
Type=simple
ExecStart=/usr/sbin/hostapd -dd /etc/hostapd/hostapd.conf
Restart=on-failure
RestartSec=5
KillMode=process

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

# Enable and start the service
systemctl enable pisowifi-hostapd
systemctl start pisowifi-hostapd 