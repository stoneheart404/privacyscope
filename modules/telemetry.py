import winreg
import subprocess
import os


def _run_cmd(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, shell=True)
        return r.stdout.strip() or r.stderr.strip()
    except Exception:
        return ""


def _run_ps(cmd):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                           capture_output=True, text=True, timeout=15)
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


TELEMETRY_LEVELS = {0: "Security (0)", 1: "Basic (1)", 2: "Enhanced (2)", 3: "Full (3)"}
DO_MODES = {0: "Off", 1: "LAN only", 2: "Group", 3: "Internet", 99: "Simple download mode", 100: "Bypass mode"}


def check_telemetry_level():
    for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
        for path in [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection",
            r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
        ]:
            val = _reg_read(path, "AllowTelemetry", hive)
            if val is not None:
                return TELEMETRY_LEVELS.get(val, f"Unknown ({val})"), path
    return "Not configured", ""


def check_advertising_id():
    val = _reg_read(
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\AdvertisingInfo",
        "Enabled",
        winreg.HKEY_CURRENT_USER
    )
    if val is not None:
        return bool(val)
    return None


def check_ms_account():
    using_msa = False
    try:
        output = _run_cmd("whoami /upn")
        if "@" in output and not output.endswith("\\"):
            using_msa = True
    except Exception:
        pass
    return using_msa


def check_cortana_web_search():
    cortana = _reg_read(
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Search",
        "CortanaEnabled",
        winreg.HKEY_CURRENT_USER
    )
    web_search = _reg_read(
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Search",
        "BingSearchEnabled",
        winreg.HKEY_CURRENT_USER
    )
    return cortana, web_search


def check_location_services():
    val = _reg_read(
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location",
        "Value",
        winreg.HKEY_LOCAL_MACHINE
    )
    if val is not None:
        return val.lower() == "allow"
    return None


def check_onedrive():
    running = False
    try:
        output = _run_cmd("tasklist /FI \"IMAGENAME eq OneDrive.exe\"")
        running = "OneDrive.exe" in output
    except Exception:
        pass

    configured = False
    one_drive_path = os.path.expandvars(r"%USERPROFILE%\OneDrive")
    if os.path.exists(one_drive_path):
        configured = True

    # Check sync settings
    kfm_enabled = _reg_read(
        r"SOFTWARE\Microsoft\OneDrive\Accounts\Personal",
        "KFMEnabled",
        winreg.HKEY_CURRENT_USER
    )

    return running, configured, kfm_enabled


def check_delivery_optimization():
    mode = _reg_read(
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\DeliveryOptimization\Config",
        "DODownloadMode",
        winreg.HKEY_LOCAL_MACHINE
    )
    if mode is not None:
        return DO_MODES.get(mode, f"Unknown ({mode})")
    return None


def check_diagnostic_viewer():
    viewer_installed = False
    try:
        output = _run_ps("Get-AppxPackage Microsoft.DiagnosticDataViewer")
        if "DiagnosticDataViewer" in output:
            viewer_installed = True
    except Exception:
        pass
    return viewer_installed


def check_tailored_experiences():
    val = _reg_read(
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Privacy",
        "TailoredExperiencesWithDiagnosticDataEnabled",
        winreg.HKEY_CURRENT_USER
    )
    if val is not None:
        return bool(val)
    return None


def check_activity_history():
    val = _reg_read(
        r"SOFTWARE\Policies\Microsoft\Windows\System",
        "EnableActivityFeed",
        winreg.HKEY_LOCAL_MACHINE
    )
    if val is None:
        val = _reg_read(
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\SettingSync",
            "SyncPolicy",
            winreg.HKEY_LOCAL_MACHINE
        )
    return val


def scan():
    items = []

    # Telemetry level
    telemetry_level, telemetry_path = check_telemetry_level()
    if "Full" in telemetry_level or "Enhanced" in telemetry_level:
        sev = "high"
    elif "Basic" in telemetry_level:
        sev = "medium"
    else:
        sev = "low"
    items.append({"label": "Telemetry Level", "value": telemetry_level, "detail": f"Registry: {telemetry_path}\nMicrosoft collects diagnostic & usage data based on this level.", "severity": sev,
        "action": {"label": "Set to Basic", "cmd": 'reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection" /v AllowTelemetry /t REG_DWORD /d 1 /f', "admin": True}})

    # Advertising ID
    ad_id = check_advertising_id()
    if ad_id is not None:
        if ad_id:
            items.append({"label": "Advertising ID", "value": "Enabled", "detail": "Apps can use your advertising ID to show targeted ads", "severity": "high",
                "action": {"label": "Disable", "cmd": 'reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\AdvertisingInfo" /v Enabled /t REG_DWORD /d 0 /f'}})
        else:
            items.append({"label": "Advertising ID", "value": "Disabled", "detail": "Apps cannot use your advertising ID", "severity": "low",
                "action": {"label": "Enable", "cmd": 'reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\AdvertisingInfo" /v Enabled /t REG_DWORD /d 1 /f'}})
    else:
        items.append({"label": "Advertising ID", "value": "Unknown", "detail": "Could not read registry setting", "severity": "medium"})

    # Microsoft account
    using_msa = check_ms_account()
    if using_msa:
        items.append({"label": "Microsoft Account", "value": "Linked", "detail": "Your account syncs settings, browsing data, passwords to Microsoft cloud", "severity": "high"})
    else:
        items.append({"label": "Microsoft Account", "value": "Local account", "detail": "You are using a local Windows account", "severity": "low"})

    # Cortana / web search
    cortana, web_search = check_cortana_web_search()
    if cortana is not None:
        if cortana:
            items.append({"label": "Cortana", "value": "Enabled", "detail": "Voice assistant that sends queries to Microsoft", "severity": "medium",
                "action": {"label": "Disable", "cmd": 'reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Search" /v CortanaEnabled /t REG_DWORD /d 0 /f'}})
        else:
            items.append({"label": "Cortana", "value": "Disabled", "detail": "", "severity": "low",
                "action": {"label": "Enable", "cmd": 'reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Search" /v CortanaEnabled /t REG_DWORD /d 1 /f'}})
    if web_search is not None:
        if web_search:
            items.append({"label": "Web Search in Start Menu", "value": "Enabled", "detail": "Local file searches are sent to Bing", "severity": "medium",
                "action": {"label": "Disable", "cmd": 'reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Search" /v BingSearchEnabled /t REG_DWORD /d 0 /f'}})
        else:
            items.append({"label": "Web Search in Start Menu", "value": "Disabled", "detail": "", "severity": "low",
                "action": {"label": "Enable", "cmd": 'reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Search" /v BingSearchEnabled /t REG_DWORD /d 1 /f'}})

    # Location
    location_enabled = check_location_services()
    if location_enabled is not None:
        if location_enabled:
            items.append({"label": "Location Services", "value": "Enabled", "detail": "Apps and Microsoft can access your device location", "severity": "high",
                "action": {"label": "Disable", "cmd": 'reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\CapabilityAccessManager\\ConsentStore\\location" /v Value /t REG_SZ /d Deny /f'}})
        else:
            items.append({"label": "Location Services", "value": "Disabled", "detail": "Location access is blocked", "severity": "low",
                "action": {"label": "Enable", "cmd": 'reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\CapabilityAccessManager\\ConsentStore\\location" /v Value /t REG_SZ /d Allow /f'}})

    # OneDrive
    od_running, od_configured, od_kfm = check_onedrive()
    if od_configured:
        detail = "OneDrive is configured and syncing files to Microsoft cloud."
        if od_kfm is not None and od_kfm:
            detail += "\nKnown Folder Move is ON — Desktop, Documents, Pictures are synced."
        items.append({"label": "OneDrive Sync", "value": "Active" if od_running else "Configured (not running)", "detail": detail, "severity": "high"})
    else:
        items.append({"label": "OneDrive Sync", "value": "Not configured", "detail": "OneDrive is not set up", "severity": "low"})

    # Windows Update P2P
    do_mode = check_delivery_optimization()
    if do_mode:
        sev = "low" if do_mode.startswith("Off") or do_mode.startswith("LAN") else "high"
        do_action = {"label": "Turn Off", "cmd": 'reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\DeliveryOptimization\\Config" /v DODownloadMode /t REG_DWORD /d 0 /f'}
        items.append({"label": "Windows Update P2P Sharing", "value": do_mode, "detail": "Windows shares updates with other PCs. Internet mode shares outside your network.", "severity": sev, "action": do_action})

    # Diagnostic data viewer
    viewer = check_diagnostic_viewer()
    if viewer:
        items.append({"label": "Diagnostic Data Viewer", "value": "Installed", "detail": "You can inspect what diagnostic data Microsoft collects", "severity": "low"})
    else:
        items.append({"label": "Diagnostic Data Viewer", "value": "Not installed", "detail": "Install from Microsoft Store to see what data Microsoft has about you", "severity": "medium"})

    # Tailored experiences
    tailored = check_tailored_experiences()
    if tailored is not None:
        items.append({"label": "Tailored Experiences", "value": "Enabled" if tailored else "Disabled", "detail": "Microsoft uses diagnostic data to personalize tips, ads, and recommendations", "severity": "high" if tailored else "low",
            "action": {"label": "Disable" if tailored else "Enable", "cmd": f'reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Privacy" /v TailoredExperiencesWithDiagnosticDataEnabled /t REG_DWORD /d {0 if tailored else 1} /f'}})

    # Activity history
    activity = check_activity_history()
    if activity is not None:
        items.append({"label": "Activity History (Sync)", "value": "Enabled" if activity else "Disabled", "detail": "Your activity timeline and app history sync across devices via Microsoft", "severity": "medium" if activity else "low",
            "action": {"label": "Disable" if activity else "Enable", "cmd": f'reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\System" /v EnableActivityFeed /t REG_DWORD /d {0 if activity else 1} /f'}})

    return items
