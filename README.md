# PrivacyScope

A desktop application that audits what information your Windows system exposes to external observers — Microsoft, WiFi routers/ISPs, websites, and nearby devices — and lets you fix the risks with one click.

## Screenshot

```
┌──────────────────────────────────────────────────────┐
│  ◉ PRIVACYSCOPE    Scan All  Export  Copy   auto    │
├──────────────────────────────────────────────────────┤
│ Dashboard │ MS │ WiFi │ Web │ Nearby │ FW │ Terminal │
├──────────────────────────────────────────────────────┤
│    ╭──────╮         Well locked down                │
│   ╱ 67  ╲ ██░░░░░░░░  ● 8 High  ● 12 Med  ● 14 Low │
│  │ exp.  │                                           │
│   ╲     ╱                                            │
│  ┌─ Microsoft ─────────────┐  ┌─ WiFi / ISP ───────┐│
│  │ ██████░░░░░░░░░░░░░░░░░ │  │ ██████████░░░░░░░░ ││
│  │ ● Telemetry: Full (3)   │  │ ● Hostname: DESK... ││
│  │ ● Ad ID: Enabled        │  │ ● DNS: 8.8.8.8     ││
│  │ + 7 more →              │  │ + 14 more →        ││
│  └─────────────────────────┘  └────────────────────┘│
│  $ terminal                                         │
│  > active connections: 12 established               │
├──────────────────────────────────────────────────────┤
│  > 58 items exposed                   12:34:56       │
└──────────────────────────────────────────────────────┘
```

## What It Scans

| Tab | Checks | Who Can See It |
|-----|--------|----------------|
| **Dashboard** | Visual score gauge, category overview, live terminal | — |
| **Microsoft** | Telemetry level, ad ID, MS account, Cortana, OneDrive, location, activity history | Microsoft |
| **WiFi / ISP** | MAC, hostname, IP, DNS servers, open ports, saved WiFi, VPN, network profile | Router admin, ISP |
| **Websites** | User-Agent, screen res, fonts, WebGL GPU, timezone, locale, DNT, cookies | Every website you visit |
| **Nearby** | Bluetooth, WiFi probes, NetBIOS, LLMNR, mDNS, SSDP/UPnP, SMB shares | Devices on same network |
| **Firewall** | Service status, 3 profiles, rule counts, risky inbound rules, logging | Attackers scanning your ports |
| **Terminal** | Live connections, DNS cache, ARP table, hostname/IP | Network admin, ISP |

## Quick Start

### Option 1: Run from source
```powershell
cd privacyscope
pip install -r requirements.txt
python main.py
```

### Option 2: Run as .exe
Double-click `launch.bat` or run `dist\PrivacyScope.exe` directly.

## Features

- **Read-only scanning** — never sends your data anywhere
- **One-click fixes** — Disable telemetry, hide Bluetooth, block cookies, enable firewall — 25+ actions with admin elevation
- **Live progress** — status bar shows `[2/5] WiFi / ISP ok` during scanning
- **Smooth reload** — auto-refresh keeps old data visible, swaps silently
- **Responsive layout** — text reflows at any window size (min 800x550)
- **Export** — save full report as `.txt` or `.json`
- **Copy** — any section to clipboard

## Actions Available

Each high/medium-risk item has a **Fix** button. Examples:
- Set Telemetry to Basic
- Disable Advertising ID, Cortana, Location
- Enable DNS over HTTPS
- Hide Bluetooth, Disable NetBIOS/LLMNR
- Stop SSDP/UPnP, Disable Nearby Share
- Enable Do Not Track, Block All Cookies
- Enable Firewall, Review Risky Rules

## Requirements

- Windows 10/11
- Python 3.8+ (for source run)
- `psutil` (auto-installed via `pip install -r requirements.txt`)

## Project Structure

```
privacyscope/
├── main.py                  # Tkinter GUI (VS Code-style dark theme)
├── modules/
│   ├── telemetry.py         # Microsoft data collection checks
│   ├── network.py           # WiFi/router/ISP visibility
│   ├── browser.py           # Web browser fingerprinting
│   ├── broadcasts.py        # Bluetooth, mDNS, NetBIOS, etc.
│   ├── firewall.py          # Windows Firewall inspection
│   └── monitor.py           # Live network connection terminal
├── launch.bat               # One-click launcher
├── requirements.txt         # Python dependencies
├── plan.md                  # Architecture & design plan
├── lock.txt                 # Changelog
├── .gitignore
├── README.md
└── dist/
    └── PrivacyScope.exe     # Standalone executable
```
