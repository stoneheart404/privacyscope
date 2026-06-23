import socket
import subprocess
import re
import winreg
import json

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def _run_ps(cmd):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                           capture_output=True, text=True, timeout=15)
        return r.stdout.strip() or r.stderr.strip()
    except Exception:
        return ""


def _run_cmd(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, shell=True)
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


def get_mac_addresses():
    macs = []
    randomization_enabled = False

    if HAS_PSUTIL:
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == psutil.AF_LINK and addr.address:
                    macs.append({"interface": iface, "mac": addr.address})

    # Check MAC randomization (Windows 10+)
    rand_val = _reg_read(
        r"SOFTWARE\Microsoft\WcmSvc\wifinetworkmanager\features",
        "WiFiRandomizationEnabled"
    )
    if rand_val is not None:
        randomization_enabled = bool(rand_val)

    return macs, randomization_enabled


def get_network_info():
    hostname = socket.gethostname()
    netbios_name = ""

    # Try NetBIOS name
    try:
        netbios_output = _run_cmd("nbtstat -n")
        match = re.search(r"^\s*(\S+)\s+<00>\s+UNIQUE", netbios_output, re.MULTILINE)
        if match:
            netbios_name = match.group(1)
    except Exception:
        pass

    local_ips = []
    gateway = ""
    dhcp_server = ""
    dns_servers = []

    try:
        ipconfig = _run_cmd("ipconfig /all")
        current_interface = ""
        for line in ipconfig.split("\n"):
            line = line.strip()
            if "adapter" in line.lower() and ":" in line:
                current_interface = line.split(":")[-1].strip().rstrip(":")
            if "IPv4 Address" in line:
                ip_match = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
                if ip_match:
                    local_ips.append({"interface": current_interface, "ip": ip_match.group(1)})
            if "Default Gateway" in line:
                gw_match = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
                if gw_match and not gateway:
                    gateway = gw_match.group(1)
            if "DHCP Server" in line:
                dhcp_match = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
                if dhcp_match and not dhcp_server:
                    dhcp_server = dhcp_match.group(1)
            if "DNS Servers" in line:
                dns_match = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
                if dns_match and dns_match.group(1) not in dns_servers:
                    dns_servers.append(dns_match.group(1))
    except Exception:
        pass

    # Also try psutil for addresses
    if HAS_PSUTIL:
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    entry = {"interface": iface, "ip": addr.address}
                    if not any(e["ip"] == addr.address for e in local_ips):
                        local_ips.append(entry)

    return hostname, netbios_name, local_ips, gateway, dhcp_server, dns_servers


def get_open_ports():
    ports = []

    if HAS_PSUTIL:
        conns = psutil.net_connections(kind="inet")
        seen = set()
        for conn in conns:
            if conn.status == "LISTEN" and conn.laddr:
                key = (conn.laddr.ip, conn.laddr.port, conn.type)
                if key not in seen:
                    seen.add(key)
                    proto = "TCP" if conn.type == socket.SOCK_STREAM else "UDP"
                    ports.append({
                        "address": f"{conn.laddr.ip}:{conn.laddr.port}",
                        "protocol": proto,
                        "pid": conn.pid
                    })

    return ports


def get_saved_wifi_networks():
    profiles = []
    try:
        output = _run_cmd("netsh wlan show profiles")
        # Try parsing these patterns: "User Profile" or "    All User Profile     :"
        for line in output.split("\n"):
            for keyword in ["User Profile", "All User Profile"]:
                if keyword in line and ":" in line:
                    ssid = line.split(":")[-1].strip()
                    if ssid:
                        profiles.append(ssid)
                        break
    except Exception:
        pass
    return list(set(profiles))


def get_vpn_status():
    vpns = []
    try:
        output = _run_ps("Get-VpnConnection | Select-Object Name, ServerAddress, ConnectionStatus | ConvertTo-Json")
        if output:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            for vpn in data:
                vpns.append({
                    "name": vpn.get("Name", "Unknown"),
                    "server": vpn.get("ServerAddress", ""),
                    "status": vpn.get("ConnectionStatus", "Unknown"),
                })
    except Exception:
        pass
    return vpns


def get_network_profile():
    profiles = []
    try:
        output = _run_ps("Get-NetConnectionProfile | Select-Object Name, NetworkCategory | ConvertTo-Json")
        if output:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            for p in data:
                profiles.append({
                    "name": p.get("Name", ""),
                    "category": p.get("NetworkCategory", "Unknown"),
                })
    except Exception:
        pass
    return profiles


def check_doh_status():
    doh_configured = False
    try:
        output = _run_ps("Get-DnsClientDohServerAddress")
        if output and "ServerAddress" in output:
            doh_configured = True
    except Exception:
        pass
    return doh_configured


def scan():
    items = []

    # Hostname
    hostname, netbios_name, local_ips, gateway, dhcp_server, dns_servers = get_network_info()
    items.append({"label": "Hostname", "value": hostname, "detail": "Visible in DHCP requests, NetBIOS broadcasts, mDNS", "severity": "medium"})

    if netbios_name:
        items.append({"label": "NetBIOS Name", "value": netbios_name, "detail": "Broadcast to local network (port 137-139)", "severity": "high"})

    # MAC addresses
    macs, mac_randomization = get_mac_addresses()
    for m in macs:
        sev = "medium" if mac_randomization else "high"
        detail = "Visible to WiFi routers and local network devices"
        if not mac_randomization:
            detail += " — randomization NOT enabled"
        items.append({"label": f"MAC Address ({m['interface']})", "value": m['mac'], "detail": detail, "severity": sev})

    if mac_randomization:
        items.append({"label": "MAC Randomization", "value": "Enabled", "detail": "Windows randomizes MAC when probing networks", "severity": "low"})
    else:
        items.append({"label": "MAC Randomization", "value": "Disabled", "detail": "Your real MAC is always visible to WiFi routers", "severity": "high"})

    # IP addresses
    for ip in local_ips:
        items.append({"label": f"Local IP ({ip['interface']})", "value": ip['ip'], "detail": "Visible to your router, ISP, and any server you connect to", "severity": "medium"})

    if gateway:
        items.append({"label": "Gateway (Router)", "value": gateway, "detail": "Your router — sees all unencrypted traffic and DNS queries", "severity": "medium"})

    if dhcp_server:
        items.append({"label": "DHCP Server", "value": dhcp_server, "detail": "Assigns your IP; sees hostname and MAC address", "severity": "low"})

    # DNS servers
    if dns_servers:
        items.append({"label": "DNS Servers", "value": ", ".join(dns_servers), "detail": "These servers see every domain you visit (unless using DoH/DoT)", "severity": "high"})

    doh = check_doh_status()
    if doh:
        items.append({"label": "DNS over HTTPS", "value": "Enabled", "detail": "DNS queries are encrypted — ISP cannot see them", "severity": "low"})
    else:
        items.append({"label": "DNS Encryption", "value": "Not detected", "detail": "DNS queries are sent in plaintext — ISP/router can see all domains", "severity": "high",
            "action": {"label": "Open DNS Settings", "cmd": "start ms-settings:network-advancedsettings", "type": "cmd"}})

    # Open ports
    ports = get_open_ports()
    if ports:
        port_list = ", ".join(f"{p['protocol']}:{p['address']}" for p in ports[:15])
        items.append({"label": f"Open Ports ({len(ports)})", "value": port_list, "detail": "Listening services visible to anyone on the same network", "severity": "high"})
    else:
        items.append({"label": "Open Ports", "value": "None detected", "detail": "No listening services found", "severity": "low"})

    # Saved WiFi
    wifi_profiles = get_saved_wifi_networks()
    if wifi_profiles:
        items.append({"label": f"Saved WiFi Networks ({len(wifi_profiles)})", "value": ", ".join(sorted(wifi_profiles)), "detail": "Your device broadcasts probe requests for these networks — visible to nearby WiFi", "severity": "high"})
    else:
        items.append({"label": "Saved WiFi Networks", "value": "None found", "detail": "", "severity": "low"})

    # VPN
    vpns = get_vpn_status()
    if vpns:
        for v in vpns:
            sev = "low" if v['status'] == "Connected" else "medium"
            items.append({"label": f"VPN: {v['name']}", "value": v['status'], "detail": f"Server: {v['server']}" if v['server'] else "", "severity": sev})
    else:
        items.append({"label": "VPN Connections", "value": "None", "detail": "No VPN configured — all traffic visible to ISP", "severity": "high"})

    # Network profile
    profiles = get_network_profile()
    for p in profiles:
        if p['category'] == "Public":
            sev = "low"
            detail = f"{p['name']}: Public profile — device is hidden from local network browsing"
        else:
            sev = "medium"
            detail = f"{p['name']}: Private profile — device is visible to other PCs on this network"
        items.append({"label": f"Network: {p['name']}", "value": p['category'], "detail": detail, "severity": sev})

    # SNI explanation
    items.append({"label": "SNI Exposure", "value": "TLS SNI leaks domain names", "detail": "Even with HTTPS, the domain name is visible to ISP/router. Encrypted Client Hello (ECH) is not yet widely deployed.", "severity": "high"})

    return items
