# PrivacyScope — Privacy Exposure Scanner

## Goal
A desktop GUI tool that audits what information your Windows system exposes to external observers: Microsoft, WiFi routers/ISPs, websites, and nearby devices.

## Stack
- **Language:** Python 3
- **GUI:** Tkinter (built-in, zero-install)
- **Deps:** `psutil` (system/network)
- **OS:** Windows (uses `winreg`, `netsh`, `sc`, `reg` via subprocess)

## Architecture

```
privacyscope/
├── main.py                  # Entry point, Tkinter notebook UI with 5 tabs
├── modules/
│   ├── __init__.py
│   ├── telemetry.py         # Microsoft telemetry & account inspection
│   ├── network.py           # WiFi/router/ISP visibility
│   ├── browser.py           # Browser fingerprint & web tracking audit
│   └── broadcasts.py        # Bluetooth, mDNS, NetBIOS, probe requests
├── requirements.txt         # psutil
├── plan.md                  # This file
├── lock.txt                 # Changelog / modification tracker
└── README.md                # User-facing docs
```

## GUI Tabs

### Tab 1: Dashboard
- Aggregated risk summary (green/yellow/red per category)
- Quick "What can X see?" matrix
- Overall exposure score (0-100, lower = more private)
- Refresh button

### Tab 2: Microsoft
- Telemetry level (Security / Basic / Enhanced / Full)
- Diagnostic data collection status
- Microsoft account linkage
- Advertising ID (enabled/disabled)
- Cortana / web search integration
- OneDrive sync status
- Edge sync & browsing data sharing
- Windows Update P2P sharing
- Location services

### Tab 3: WiFi & Network
- MAC address + randomization status
- Hostname & NetBIOS name
- Local IP, gateway, DHCP server
- DNS servers (and DoH/DoT status)
- Open TCP/UDP listening ports
- Saved WiFi networks (SSID list)
- VPN connection status
- Network profile type (public/private)
- SNI exposure explanation

### Tab 4: Browser
- User-Agent string
- Screen resolution & color depth
- System fonts (first 50)
- Timezone & locale
- Language preferences
- WebGL vendor/renderer
- Installed plugins/extensions
- Cookie & storage defaults
- Do Not Track status
- Pop-up blocker status

### Tab 5: Local Broadcasts
- Bluetooth adapter & discoverability
- WiFi probe request behavior
- mDNS / Bonjour service status
- NetBIOS / LLMNR status
- Network discovery & file/printer sharing
- UPnP / SSDP status
- Nearby Share / cross-device sharing
- Connected Bluetooth devices

## Features
- **Export:** Save full report as .txt or .json
- **Copy:** Each section has a copy-to-clipboard button
- **Refresh:** Re-scan individual modules
- **Auto-refresh:** Optional 60s auto-scan for network changes

## Implementation Order
1. `main.py` — Tkinter skeleton with 5 empty tabs
2. `modules/network.py` — network inspection (most straightforward)
3. `modules/telemetry.py` — registry/diagnostic data checks
4. `modules/broadcasts.py` — local broadcast services
5. `modules/browser.py` — browser fingerprint & web exposure
6. Dashboard aggregation, export, polish
