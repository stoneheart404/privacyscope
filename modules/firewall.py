import subprocess
import json


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


def check_firewall_profiles():
    profiles = []
    try:
        out = _run_ps("Get-NetFirewallProfile | Select-Object Name, Enabled, DefaultInboundAction, DefaultOutboundAction | ConvertTo-Json")
        if out:
            data = json.loads(out)
            if isinstance(data, dict):
                data = [data]
            for p in data:
                profiles.append({
                    "name": p.get("Name", "Unknown"),
                    "enabled": p.get("Enabled", False),
                    "inbound": p.get("DefaultInboundAction", "Unknown"),
                    "outbound": p.get("DefaultOutboundAction", "Unknown"),
                })
    except Exception:
        pass
    return profiles


def check_firewall_service():
    running = False
    try:
        out = _run_ps("Get-Service MpsSvc | Select-Object -ExpandProperty Status")
        running = "Running" in out
    except Exception:
        pass
    return running


def check_risky_rules():
    risky = []
    checks = [
        ("Remote Desktop (RDP)", "Remote Desktop"),
        ("File and Printer Sharing (SMB-In)", "File and Printer Sharing"),
        ("All Inbound Traffic", "Allow All Inbound"),
    ]
    for label, pattern in checks:
        try:
            out = _run_ps(
                f"Get-NetFirewallRule -DisplayName '*{pattern}*' | "
                f"Where-Object {{ $_.Enabled -and $_.Direction -eq 'Inbound' -and $_.Action -eq 'Allow' }} | "
                f"Select-Object -First 1 -ExpandProperty DisplayName"
            )
            if out and pattern.lower() in out.lower():
                risky.append(label)
        except Exception:
            pass
    return risky


def check_rule_counts():
    inbound = 0
    outbound = 0
    try:
        inp = _run_ps("Get-NetFirewallRule -Direction Inbound | Measure-Object | Select-Object -ExpandProperty Count")
        outb = _run_ps("Get-NetFirewallRule -Direction Outbound | Measure-Object | Select-Object -ExpandProperty Count")
        if inp:
            inbound = int(inp.strip())
        if outb:
            outbound = int(outb.strip())
    except Exception:
        pass
    return inbound, outbound


def check_logging():
    log_enabled = False
    log_path = ""
    try:
        out = _run_ps("Get-NetFirewallProfile -Name Domain | Select-Object -ExpandProperty LogAllowed")
        if out and "True" in out:
            log_enabled = True
        path = _run_ps("Get-NetFirewallProfile -Name Domain | Select-Object -ExpandProperty LogFileName")
        if path:
            log_path = path.strip()
    except Exception:
        pass
    return log_enabled, log_path


def check_notifications():
    notify = False
    try:
        out = _run_ps("Get-NetFirewallProfile -Name Public | Select-Object -ExpandProperty NotifyOnListen")
        if out and "True" in out:
            notify = True
    except Exception:
        pass
    return notify


def scan():
    items = []

    service = check_firewall_service()
    if service:
        items.append({"label": "Firewall Service", "value": "Running", "detail": "Windows Defender Firewall is active", "severity": "low"})
    else:
        items.append({"label": "Firewall Service", "value": "Stopped", "detail": "Windows Firewall service is not running — system is unprotected", "severity": "high",
            "action": {"label": "Start", "cmd": "sc start MpsSvc & sc config MpsSvc start=auto"}})

    profiles = check_firewall_profiles()
    for p in profiles:
        name = p["name"]
        if p["enabled"]:
            sev = "low"
            detail = f"{name} profile is active"
            if p["inbound"] == "Allow":
                sev = "high"
                detail += " — inbound connections allowed (dangerous)"
            elif p["inbound"] == "Block":
                detail += " — inbound blocked"
            items.append({"label": f"Firewall: {name} Profile", "value": f"On | inbound={p['inbound']}", "detail": detail, "severity": sev})
        else:
            items.append({"label": f"Firewall: {name} Profile", "value": "Off", "detail": f"{name} profile firewall is disabled — system exposed", "severity": "high",
                "action": {"label": "Enable", "cmd": f'powershell -NoProfile -Command "Set-NetFirewallProfile -Name {name} -Enabled True"'}})

    inbound, outbound = check_rule_counts()
    items.append({"label": "Firewall Rules", "value": f"{inbound} inbound / {outbound} outbound", "detail": "Active firewall rules controlling network traffic", "severity": "low"})

    risky = check_risky_rules()
    if risky:
        items.append({"label": "Risky Inbound Rules", "value": ", ".join(risky), "detail": "These rules allow inbound connections — potential attack surface", "severity": "high",
            "action": {"label": "Review", "cmd": "start wf.msc"}})
    else:
        items.append({"label": "Risky Inbound Rules", "value": "None detected", "detail": "No risky inbound allow rules found", "severity": "low"})

    log_enabled, log_path = check_logging()
    if log_enabled:
        items.append({"label": "Firewall Logging", "value": "Enabled", "detail": f"Log file: {log_path}" if log_path else "Logging active", "severity": "low"})
    else:
        items.append({"label": "Firewall Logging", "value": "Disabled", "detail": "Firewall logs not being recorded — harder to detect attacks", "severity": "medium"})

    notify = check_notifications()
    if notify:
        items.append({"label": "Firewall Notifications", "value": "Enabled", "detail": "Windows will notify when new apps are blocked", "severity": "low"})
    else:
        items.append({"label": "Firewall Notifications", "value": "Disabled", "detail": "You may not notice when apps are blocked", "severity": "medium"})

    return items
