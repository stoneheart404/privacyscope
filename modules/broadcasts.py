import subprocess
import winreg
import json
import sys


def _run_cmd(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, shell=True,
                           creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        return r.stdout.strip() or r.stderr.strip()
    except Exception:
        return ""


def _run_ps(cmd):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                           capture_output=True, text=True, timeout=15,
                           creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        return r.stdout.strip() or r.stderr.strip()
    except Exception:
        return ""


def _reg_read(key_path, value_name, hive=winreg.HKEY_LOCAL_MACHINE):
    try:
        with winreg.OpenKey(hive, key_path) as key:
            val, _ = winreg.QueryValueEx(key, value_name)
            return val
    except Exception:
        return None


def check_bluetooth():
    adapter_present = False
    discoverable = False
    connected_devices = []

    try:
        output = _run_ps("Get-PnpDevice -Class Bluetooth | Where-Object { $_.Status -eq 'OK' } | Select-Object -First 3")
        if output and "OK" in output:
            adapter_present = True
    except Exception:
        pass

    if adapter_present:
        try:
            output = _run_ps("Get-BluetoothDevice | Select-Object Name, Connected | ConvertTo-Json")
            if output:
                data = json.loads(output)
                if isinstance(data, dict):
                    data = [data]
                for d in data:
                    connected_devices.append({
                        "name": d.get("Name", "Unknown"),
                        "connected": d.get("Connected", False),
                    })
        except Exception:
            pass

    # Check Bluetooth discoverability via registry
    try:
        disc_val = _reg_read(
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Bluetooth",
            "DiscoverabilityMode"
        )
        if disc_val is not None:
            discoverable = disc_val != 0
    except Exception:
        pass

    return adapter_present, discoverable, connected_devices


def check_wifi_probe():
    probe_randomization = False
    try:
        rand_val = _reg_read(
            r"SOFTWARE\Microsoft\WcmSvc\wifinetworkmanager\features",
            "WiFiRandomizationEnabled"
        )
        if rand_val is not None:
            probe_randomization = bool(rand_val)
    except Exception:
        pass
    return probe_randomization


def check_netbios():
    enabled = False
    base_path = r"SYSTEM\CurrentControlSet\Services\NetBT\Parameters\Interfaces"

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_path) as base_key:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(base_key, i)
                    subkey_path = f"{base_path}\\{subkey_name}"
                    val = _reg_read(subkey_path, "NetbiosOptions")
                    if val is not None:
                        if val in [0, 1]:
                            enabled = True
                            break
                        if val == 2:
                            pass
                    i += 1
                except OSError:
                    break
    except Exception:
        pass
    return enabled


def check_network_discovery():
    private_enabled = False
    public_enabled = False

    try:
        # Private profile
        output = _run_cmd('netsh advfirewall firewall show rule name="Network Discovery (NB-Name-In)" dir=in')
        if output and ("Allow" in output or "Yes" in output):
            private_enabled = True
    except Exception:
        pass

    try:
        # Check file/printer sharing
        output = _run_ps("Get-NetFirewallRule -DisplayGroup 'File and Printer Sharing' | Where-Object Enabled -eq True | Select-Object -First 1")
        if output and "File" in output:
            public_enabled = True
    except Exception:
        pass

    return private_enabled, public_enabled


def check_mdns():
    running = False
    try:
        output = _run_ps("Get-Service 'Dnscache' | Select-Object Status | ConvertTo-Json")
        if output and "Running" in output:
            running = True
    except Exception:
        pass

    mdns_svc = False
    try:
        output = _run_ps("Get-Service -Name '*mDNS*' -ErrorAction SilentlyContinue | Select-Object Name, Status | ConvertTo-Json")
        if output and "Running" in output:
            mdns_svc = True
    except Exception:
        pass

    return running, mdns_svc


def check_ssdp():
    running = False
    try:
        output = _run_ps("Get-Service 'SSDPSRV' | Select-Object Status | ConvertTo-Json")
        if output and "Running" in output:
            running = True
    except Exception:
        pass
    return running


def check_llmnr():
    enabled = False
    try:
        val = _reg_read(
            r"SOFTWARE\Policies\Microsoft\Windows NT\DNSClient",
            "EnableMulticast"
        )
        if val is not None:
            enabled = bool(val)
    except Exception:
        pass

    if not enabled:
        try:
            output = _run_cmd('reg query "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows NT\\DNSClient" /v EnableMulticast 2>nul')
            if "EnableMulticast" not in output:
                enabled = True  # Default is enabled when not configured
        except Exception:
            enabled = True

    return enabled


def check_nearby_share():
    enabled = False
    try:
        val = _reg_read(
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\CDP\Settings\NearShare",
            "NearShareEnabled",
            winreg.HKEY_CURRENT_USER
        )
        if val is not None:
            enabled = bool(val)
    except Exception:
        pass
    return enabled


def check_smb_shares():
    shares = []
    try:
        output = _run_ps("Get-SmbShare | Where-Object Special -eq $false | Select-Object Name, Path | ConvertTo-Json")
        if output:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            for s in data:
                shares.append({"name": s.get("Name", ""), "path": s.get("Path", "")})
    except Exception:
        pass
    return shares


def scan():
    items = []

    # Bluetooth
    bt_present, bt_discoverable, bt_devices = check_bluetooth()
    if bt_present:
        if bt_discoverable:
            items.append({"label": "Bluetooth Discoverability", "value": "Discoverable", "detail": "Nearby devices can see your PC's Bluetooth name and connect to it", "severity": "high",
                "action": {"label": "Hide", "cmd": 'reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Bluetooth" /v DiscoverabilityMode /t REG_DWORD /d 0 /f'}})
        else:
            items.append({"label": "Bluetooth Discoverability", "value": "Hidden", "detail": "Your PC is not discoverable by new devices", "severity": "low"})

        if bt_devices:
            connected_list = [d['name'] for d in bt_devices if d['connected']]
            if connected_list:
                items.append({"label": "Connected Bluetooth Devices", "value": ", ".join(connected_list), "detail": "These devices are actively paired and connected", "severity": "medium"})
            else:
                items.append({"label": "Connected Bluetooth Devices", "value": "None", "detail": "No actively connected Bluetooth devices", "severity": "low"})
    else:
        items.append({"label": "Bluetooth", "value": "No adapter detected", "detail": "No Bluetooth radio found on this system", "severity": "low"})

    # WiFi probe requests
    probe_rand = check_wifi_probe()
    if probe_rand:
        items.append({"label": "WiFi Probe Randomization", "value": "Enabled", "detail": "Windows randomizes MAC in probe requests for unknown networks", "severity": "low"})
    else:
        items.append({"label": "WiFi Probe Randomization", "value": "Not detected", "detail": "Your MAC may be broadcast in probe requests for saved networks", "severity": "high"})

    # NetBIOS
    netbios_enabled = check_netbios()
    if netbios_enabled:
        items.append({"label": "NetBIOS over TCP/IP", "value": "Enabled", "detail": "Broadcasts your computer name and domain to the local network (port 137-139)", "severity": "high",
            "action": {"label": "Disable", "cmd": 'powershell -NoProfile -Command "Set-ItemProperty -Path \'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\NetBT\\Parameters\\Interfaces\\Tcpip_*\' -Name NetbiosOptions -Value 2"', "type": "ps"}})
    else:
        items.append({"label": "NetBIOS over TCP/IP", "value": "Disabled", "detail": "Your computer name is not broadcast via NetBIOS", "severity": "low"})

    # LLMNR
    llmnr_enabled = check_llmnr()
    if llmnr_enabled:
        items.append({"label": "LLMNR (Link-Local Multicast Name Resolution)", "value": "Enabled", "detail": "Responds to name queries on the local network — can be exploited for credential harvesting", "severity": "high",
            "action": {"label": "Disable", "cmd": 'reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows NT\\DNSClient" /v EnableMulticast /t REG_DWORD /d 0 /f'}})
    else:
        items.append({"label": "LLMNR", "value": "Disabled", "detail": "Not responding to multicast name queries", "severity": "low"})

    # Network discovery
    nd_private, nd_public = check_network_discovery()
    if nd_private:
        items.append({"label": "Network Discovery (Private)", "value": "Enabled", "detail": "Your PC is visible to other devices on private networks", "severity": "medium",
            "action": {"label": "Disable", "cmd": 'netsh advfirewall firewall set rule group="Network Discovery" new enable=No', "type": "cmd"}})
    if nd_public:
        items.append({"label": "File & Printer Sharing", "value": "Enabled on some profiles", "detail": "Shared folders and printers are accessible from the network", "severity": "high",
            "action": {"label": "Disable", "cmd": 'netsh advfirewall firewall set rule group="File and Printer Sharing" new enable=No', "type": "cmd"}})
    if not nd_private and not nd_public:
        items.append({"label": "Network Discovery", "value": "Disabled", "detail": "Your PC is hidden from network browsing", "severity": "low"})

    # mDNS
    mdns_running, mdns_svc = check_mdns()
    items.append({"label": "mDNS (Bonjour/Multicast DNS)", "value": "Active" if mdns_svc else "Not detected", "detail": "mDNS broadcasts device names and services to the local network (used by AirDrop, Chromecast, printers). DNS cache " + ("is" if mdns_running else "is not") + " running.", "severity": "high" if mdns_svc else "medium"})

    # SSDP/UPnP
    ssdp_running = check_ssdp()
    if ssdp_running:
        items.append({"label": "SSDP / UPnP Discovery", "value": "Active", "detail": "Discovers and announces UPnP devices on the local network (smart TVs, media servers, IoT)", "severity": "high",
            "action": {"label": "Stop Service", "cmd": "sc stop SSDPSRV & sc config SSDPSRV start=disabled", "type": "cmd"}})
    else:
        items.append({"label": "SSDP / UPnP Discovery", "value": "Not running", "detail": "UPnP/SSDP service is stopped", "severity": "low"})

    # Nearby Share
    nearby = check_nearby_share()
    if nearby:
        items.append({"label": "Nearby Share", "value": "Enabled", "detail": "Your PC is visible to nearby Windows devices for file sharing", "severity": "high",
            "action": {"label": "Disable", "cmd": 'reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\CDP\\Settings\\NearShare" /v NearShareEnabled /t REG_DWORD /d 0 /f'}})
    else:
        items.append({"label": "Nearby Share", "value": "Disabled", "detail": "File sharing via Nearby Share is off", "severity": "low"})

    # SMB shares
    shares = check_smb_shares()
    if shares:
        share_list = ", ".join(s['name'] for s in shares)
        items.append({"label": "SMB File Shares", "value": share_list, "detail": "These folders are shared on the network. Visible to anyone with network access.", "severity": "high"})
    else:
        items.append({"label": "SMB File Shares", "value": "None", "detail": "No folders are shared via SMB", "severity": "low"})

    return items
