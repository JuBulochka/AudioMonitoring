#!/bin/bash
# noVNC WebSocket proxy with token-based routing.
# Token file format: <device_uuid>: <host>:<vnc_port>
# Written by Django when an operator opens the VNC page.

mkdir -p /tokens
touch /tokens/tokens.cfg

exec websockify \
    --web /usr/share/novnc \
    --token-plugin=TokenFile \
    --token-source=/tokens/tokens.cfg \
    --heartbeat=30 \
    6080
