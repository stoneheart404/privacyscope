import subprocess
import platform
import locale
import time
import os
import winreg
import sys

try:
    import tkinter as tk
    HAS_TK = True
except ImportError:
    HAS_TK = False


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


def _reg_read(key_path, value_name, hive=winreg.HKEY_CURRENT_USER):
    try:
        with winreg.OpenKey(hive, key_path) as key:
            val, _ = winreg.QueryValueEx(key, value_name)
            return val
    except Exception:
        return None


def get_screen_info():
    width, height = 1920, 1080
    if HAS_TK:
        try:
            root = tk.Tk()
            root.withdraw()
            width = root.winfo_screenwidth()
            height = root.winfo_screenheight()
            root.destroy()
        except Exception:
            pass
    return width, height


def get_user_agent_examples():
    py_ver = platform.python_version()
    win_ver = platform.win32_ver()[1] or platform.version()
    arch = platform.machine()

    examples = []
    examples.append({
        "browser": "Chrome (Windows)",
        "ua": f"Mozilla/5.0 (Windows NT 10.0; {arch}; rv:1.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    })
    examples.append({
        "browser": "Firefox (Windows)",
        "ua": f"Mozilla/5.0 (Windows NT 10.0; {arch}; rv:133.0) Gecko/20100101 Firefox/133.0"
    })
    examples.append({
        "browser": "Edge (Windows)",
        "ua": f"Mozilla/5.0 (Windows NT 10.0; {arch}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
    })
    examples.append({
        "browser": "Python requests",
        "ua": f"Python-urllib/{py_ver}"
    })
    return examples


def get_installed_browsers():
    browsers = []
    browser_keys = {
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe": "Google Chrome",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\firefox.exe": "Mozilla Firefox",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe": "Microsoft Edge",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\opera.exe": "Opera",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\brave.exe": "Brave",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\iexplore.exe": "Internet Explorer",
    }

    for path, name in browser_keys.items():
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
                exe_path, _ = winreg.QueryValueEx(key, "")
                if os.path.exists(exe_path):
                    browsers.append(name)
        except Exception:
            pass

    if not browsers:
        browsers.append("Microsoft Edge (built-in)")

    return browsers


def get_system_fonts():
    fonts = []
    try:
        output = _run_ps("Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Fonts' | Select-Object -ExpandProperty PSObject.Properties | Where-Object { $_.Name -notlike '* (TrueType)*' -and $_.Name -notlike '* (OpenType)*' } | ForEach-Object { $_.Name } | Select-Object -First 60")
        for line in output.split("\n"):
            line = line.strip()
            if line and not line.endswith("(TrueType)") and not line.endswith("(OpenType)"):
                fonts.append(line)
    except Exception:
        pass
    return fonts[:50]


def get_tracking_protection_status():
    tcp = _reg_read(
        r"SOFTWARE\Microsoft\Internet Explorer\Main",
        "TCP"
    )
    return tcp


def get_dnt_status():
    dnt = _reg_read(
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings",
        "DNTHeader"
    )
    if dnt is None:
        dnt = _reg_read(
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings\Zones\3",
            "DNTHeader"
        )
    return dnt


def get_cookie_settings():
    privacy_advanced = _reg_read(
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings\Zones\3",
        "1A10"
    )
    return privacy_advanced


def get_webgl_info():
    try:
        output = _run_ps("Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion | ConvertTo-Json")
        import json
        if output:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            if data:
                return data[0].get("Name", "Unknown"), data[0].get("DriverVersion", "Unknown")
    except Exception:
        pass
    return "Unknown", "Unknown"


def check_edge_sync():
    syncing = False
    try:
        output = _run_ps("Get-AppxPackage *MicrosoftEdge* | Select-Object Name | ConvertTo-Json")
        if "MicrosoftEdge" in output:
            ms_account = _reg_read(
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Authentication\LogonUI",
                "LastLoggedOnUser",
                winreg.HKEY_LOCAL_MACHINE
            )
            if ms_account and ("@" in ms_account):
                syncing = True
    except Exception:
        pass
    return syncing


def scan():
    items = []

    # User-Agent examples
    ua_examples = get_user_agent_examples()
    items.append({"label": "Browser User-Agent", "value": "See details", "detail": "Websites see your User-Agent string, revealing OS, browser, and version.", "severity": "medium"})
    for ua in ua_examples:
        items.append({"label": f"  {ua['browser']}", "value": ua['ua'], "detail": "Sent in every HTTP request", "severity": "medium"})

    # Screen resolution
    width, height = get_screen_info()
    items.append({"label": "Screen Resolution", "value": f"{width}x{height}", "detail": "Websites can detect screen size for fingerprinting (via JS)", "severity": "medium"})

    # Color depth (standard on modern Windows)
    items.append({"label": "Color Depth", "value": "24-bit (True Color)", "detail": "Detectable via screen.colorDepth JS property", "severity": "low"})

    # Timezone
    tz_name = time.tzname[0] if time.tzname else "Unknown"
    tz_offset = -(time.timezone / 3600) if time.timezone else 0
    items.append({"label": "Timezone", "value": f"{tz_name} (UTC{tz_offset:+})", "detail": "Websites can detect your timezone via Intl.DateTimeFormat", "severity": "medium"})

    # Locale
    try:
        loc = locale.getdefaultlocale()
        loc_str = f"{loc[0]}.{loc[1]}" if loc[0] else "Unknown"
    except Exception:
        loc_str = "Unknown"
    items.append({"label": "System Locale", "value": loc_str, "detail": "Detectable via navigator.language", "severity": "medium"})

    # Installed browsers
    browsers = get_installed_browsers()
    items.append({"label": "Installed Browsers", "value": ", ".join(browsers), "detail": "Software inventory can be detected via various fingerprinting methods", "severity": "medium"})

    # Windows version
    win_ver = platform.win32_ver()[1] or platform.version()
    items.append({"label": "Windows Version", "value": f"Windows {win_ver}", "detail": "Detectable via various JS APIs and HTTP headers", "severity": "low"})

    # Architecture
    items.append({"label": "CPU Architecture", "value": platform.machine(), "detail": "Detectable via navigator.platform or User-Agent", "severity": "low"})

    # WebGL
    gpu_name, gpu_driver = get_webgl_info()
    items.append({"label": "WebGL GPU (fingerprint)", "value": gpu_name, "detail": f"WebGL reveals your GPU renderer — highly identifiable. Driver: {gpu_driver}", "severity": "high"})

    # System fonts (summary)
    fonts = get_system_fonts()
    if fonts:
        items.append({"label": "System Fonts", "value": f"{len(fonts)} fonts detected", "detail": "Installed fonts are a strong fingerprinting vector. First 5: " + ", ".join(fonts[:5]), "severity": "high"})

    # Do Not Track
    dnt = get_dnt_status()
    if dnt is not None:
        if dnt:
            items.append({"label": "Do Not Track Header", "value": "Enabled", "detail": "When enabled, browser sends DNT: 1 header. Most sites ignore it.", "severity": "low"})
        else:
            items.append({"label": "Do Not Track Header", "value": "Disabled", "detail": "DNT is not set", "severity": "medium",
                "action": {"label": "Enable", "cmd": 'reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v DNTHeader /t REG_DWORD /d 1 /f'}})
    else:
        items.append({"label": "Do Not Track Header", "value": "Not configured", "detail": "DNT is not set in Internet Options", "severity": "medium",
            "action": {"label": "Enable", "cmd": 'reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v DNTHeader /t REG_DWORD /d 1 /f'}})

    # Cookie settings
    cookie_setting = get_cookie_settings()
    if cookie_setting is not None:
        cookie_desc = {0: "Accept all", 1: "Prompt", 3: "Block all"}.get(cookie_setting, f"Custom ({cookie_setting})")
        cook_act = {}
        if cookie_setting != 3:
            cook_act = {"label": "Block All", "cmd": 'reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings\\Zones\\3" /v 1A10 /t REG_DWORD /d 3 /f'}
        items.append({"label": "Cookie Policy (Internet Zone)", "value": cookie_desc, "detail": "Applies to Internet Explorer and some system web views", "severity": "low",
            "action": cook_act})

    # Edge sync
    edge_syncing = check_edge_sync()
    if edge_syncing:
        items.append({"label": "Edge Sync Status", "value": "Likely syncing", "detail": "Browsing history, passwords, and favorites may sync to Microsoft cloud", "severity": "high"})
    else:
        items.append({"label": "Edge Sync Status", "value": "Unknown", "detail": "Check Edge settings > Profiles > Sync for details", "severity": "medium"})

    return items
