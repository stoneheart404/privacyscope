<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-%230078D4?style=flat&logo=windows" alt="Windows" />
  <img src="https://img.shields.io/badge/python-3.8%2B-blue?style=flat&logo=python" alt="Python" />
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat" alt="License" />
  <img src="https://img.shields.io/badge/build-exe%20available-brightgreen?style=flat" alt="Build" />
</p>

# PrivacyScope

**See what your system exposes. Fix it with one click.**

A desktop tool that scans your Windows machine and shows exactly what Microsoft, your ISP, websites, and nearby devices can see about you — then lets you disable the leaks instantly.

---

## Quick install

```powershell
git clone https://github.com/stoneheart404/privacyscope.git
cd privacyscope
pip install -r requirements.txt
python main.py
```

Or grab the pre-built `.exe` from [Releases](https://github.com/stoneheart404/privacyscope/releases).

---

## What it scans

| Module | What's exposed | Who sees it | Fixable |
|--------|---------------|-------------|:-------:|
| **Microsoft** | Telemetry level, advertising ID, MS account, Cortana, OneDrive, location, activity history, tailored experiences | Microsoft | ✓ |
| **WiFi / ISP** | MAC address, hostname, IP, DNS servers, open ports, saved WiFi SSIDs, VPN status, network profile | Router admin, ISP, network admins | ✓ |
| **Websites** | User-Agent, screen resolution, fonts, WebGL GPU fingerprint, timezone, locale, Do Not Track, cookies | Every site you visit | ✓ |
| **Nearby** | Bluetooth discoverability, NetBIOS, LLMNR, mDNS, SSDP/UPnP, SMB shares, Nearby Share | Devices on your local network | ✓ |
| **Firewall** | Service status, 3 profiles (Domain/Private/Public), rule counts, risky inbound rules, logging | Port scanners, attackers | ✓ |
| **Terminal** | Live TCP connections, DNS cache, ARP table, hostname broadcast | Real-time network visibility | — |

---

## Features

- **Zero telemetry** — all scanning is local, nothing leaves your machine
- **One-click remediation** — 25+ action buttons: disable telemetry, hide Bluetooth, block cookies, enable firewall, stop UPnP, and more
- **Admin elevation** — detects "access denied" and offers to re-run with elevated privileges
- **Live progress** — status bar shows `[3/5] Websites ok` as modules complete
- **Smooth auto-refresh** — background rescans never flash or clear the screen
- **Responsive** — text reflows from 800×550 up to any resolution
- **VS Code-dark UI** — monospace terminal aesthetic, green-on-black terminal tab
- **Export** — save full report as `.txt` or `.json`
- **Standalone `.exe`** — build with `pyinstaller --onefile --windowed main.py`

---

## Actions you can take

| Category | Action |
|----------|--------|
| **Microsoft** | Set telemetry to Basic, disable advertising ID, disable Cortana, disable web search, disable location, turn off P2P updates, disable tailored experiences, disable activity history |
| **Network** | Open DNS-over-HTTPS settings |
| **Broadcasts** | Hide Bluetooth, disable NetBIOS, disable LLMNR, disable network discovery, disable file sharing, stop SSDP/UPnP, disable Nearby Share |
| **Browser** | Enable Do Not Track header, block all cookies |
| **Firewall** | Start firewall service, enable per-profile firewall, open Windows Firewall to review risky rules |

---

## Requirements

- **Windows 10 or 11**
- **Python 3.8+** (for source run only)
- **`psutil`** — installed automatically via `requirements.txt`

---

## Build from source

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name PrivacyScope main.py
# .exe will be in dist/
```

---

## Project layout

```
privacyscope/
├── main.py              # Tkinter GUI — VS Code-dark theme, 7 tabs
├── modules/
│   ├── telemetry.py     # Microsoft diagnostic data & account checks
│   ├── network.py       # MAC, DNS, ports, WiFi, VPN inspection
│   ├── browser.py       # User-Agent, fonts, WebGL fingerprinting
│   ├── broadcasts.py    # Bluetooth, NetBIOS, mDNS, SSDP/UPnP
│   ├── firewall.py      # Windows Firewall profiles, rules, logging
│   └── monitor.py       # Live connection terminal
├── launch.bat           # One-click Windows launcher
├── requirements.txt     # psutil
├── .gitignore
└── README.md
```
