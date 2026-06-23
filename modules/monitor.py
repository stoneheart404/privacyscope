import socket
import subprocess
import time

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def _run_ps(cmd):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                           capture_output=True, text=True, timeout=6)
        return r.stdout.strip() or r.stderr.strip()
    except Exception:
        return ""


_cache = {"data": [], "time": 0}


def get_active_connections():
    lines = []
    lines.append(f"[{time.strftime('%H:%M:%S')}]  network connections")

    if HAS_PSUTIL:
        conns = psutil.net_connections(kind="inet")
        established = [c for c in conns if c.status == "ESTABLISHED"]
        listening = [c for c in conns if c.status == "LISTEN"]
        lines.append(f"  established: {len(established)} | listening: {len(listening)}")

        for c in established[:20]:
            remote = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "*"
            pid_name = ""
            if c.pid:
                try:
                    pid_name = psutil.Process(c.pid).name()
                except Exception:
                    pid_name = str(c.pid)
            lines.append(f"  -> {remote:60s}  [{pid_name}]")
    else:
        lines.append("  psutil not available")

    return lines


def get_dns_cache():
    lines = []
    lines.append(f"\n[{time.strftime('%H:%M:%S')}]  dns cache (last 15 entries)")

    try:
        output = _run_ps("Get-DnsClientCache | Select-Object -First 15 Entry, Data, Type | ConvertTo-Csv -NoTypeInformation")
        if output:
            for i, line in enumerate(output.split("\n")[1:], 1):
                if line.strip():
                    parts = line.replace('"', '').split(",")
                    if len(parts) >= 2:
                        domain = parts[0].strip()
                        ip = parts[1].strip()
                        lines.append(f"  {domain:50s} -> {ip}")
    except Exception:
        lines.append("  could not read DNS cache")

    return lines


def get_broadcast_info():
    lines = []
    lines.append(f"\n[{time.strftime('%H:%M:%S')}]  local broadcasts")

    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "unknown"
    lines.append(f"  hostname: {hostname}")
    lines.append(f"  local IP: {local_ip}")

    return lines


def scan():
    t = time.time()
    if _cache["data"] and (t - _cache["time"]) < 5:
        return _cache["data"]

    lines = []
    lines.append("  privacyscope terminal v1.0")
    lines.append("  monitoring active data exposure...\n")

    lines.extend(get_active_connections())
    lines.extend(get_dns_cache())
    lines.extend(get_broadcast_info())

    lines.append(f"\n[{time.strftime('%H:%M:%S')}]  done — refresh to update")

    _cache["data"] = lines
    _cache["time"] = t
    return lines
