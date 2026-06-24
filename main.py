import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import threading
import subprocess
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modules import network, telemetry, browser, broadcasts, monitor, firewall

BG          = "#000000"
BG_SURFACE  = "#0a0a0a"
BG_HOVER    = "#141414"
BG_SIDEBAR  = "#050505"
BORDER      = "#1a1a1a"
BORDER_HI   = "#2a2a2a"
FG          = "#ededed"
FG_SEC      = "#888888"
FG_MUTE     = "#4a4a4a"
ACCENT      = "#ededed"
STATUS_BG   = "#0d1117"

SEV_FG      = {"low": "#22c55e", "medium": "#eab308", "high": "#ef4444"}
SEV_LABEL   = {"low": "LOW", "medium": "MED", "high": "HIGH"}

FONT        = ("Consolas", 9)
FONT_SM     = ("Consolas", 8)
FONT_BOLD   = ("Consolas", 9, "bold")
FONT_TITLE  = ("Consolas", 11, "bold")

MODULES = [
    ("Microsoft", telemetry, "microsoft"),
    ("WiFi / ISP", network, "wifi"),
    ("Websites", browser, "browser"),
    ("Nearby", broadcasts, "broadcasts"),
    ("Firewall", firewall, "firewall"),
    ("Terminal", monitor, "terminal"),
]

TABS = [
    ("dashboard", "Overview", "\u25c8"),       # ◈ diamond/gem — dashboard analytics
    ("microsoft", "Microsoft", "\u25a0"),      # ■ solid square — OS / system
    ("wifi", "WiFi / ISP", "\u26a1"),          # ⚡ lightning — network / signal
    ("browser", "Websites", "\u25c9"),         # ◎ fisheye — globe / web
    ("broadcasts", "Nearby", "\u25cb"),        # ○ circle — broadcast radius
    ("firewall", "Firewall", "\u25a8"),        # ▨ patterned square — shield
    ("terminal", "Terminal", "$"),
]

WHO = {
    "microsoft": "Microsoft",
    "wifi": "WiFi / ISP",
    "browser": "Websites",
    "broadcasts": "Nearby",
    "firewall": "Firewall",
    "terminal": "Terminal",
}


class DarkButton(tk.Canvas):
    def __init__(self, parent, text, command, width=72, height=28):
        super().__init__(parent, width=width, height=height,
                         bg=BG, highlightthickness=0, cursor="hand2")
        self.command = command
        self._text = text
        self._hover = False
        self._draw()
        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _draw(self):
        self.delete("all")
        bg = BG_HOVER if self._hover else BG
        fg = FG if self._hover else FG_SEC
        self.create_rectangle(0, 0, self.winfo_reqwidth(), self.winfo_reqheight(),
                              fill=bg, outline="", width=0)
        self.create_text(self.winfo_reqwidth() / 2, self.winfo_reqheight() / 2,
                         text=self._text, fill=fg, font=FONT_SM)

    def _on_enter(self, e):
        self._hover = True
        self._draw()

    def _on_leave(self, e):
        self._hover = False
        self._draw()


class PrivacyScopeApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.geometry("960x700+200+100")
        self.root.minsize(820, 550)
        self.root.configure(bg=BG)

        # taskbar icon
        try:
            ico = os.path.join(os.path.dirname(__file__), "icon.ico")
            self.root.iconbitmap(default=ico)
        except Exception:
            pass

        self._drag_x = 0
        self._drag_y = 0
        self._maximized = False
        self._restore_geom = ""

        style = ttk.Style()
        style.configure("TScrollbar", background=BG, troughcolor=BG,
                       arrowcolor=FG_MUTE, bordercolor=BG)
        style.map("TScrollbar", background=[("active", BORDER)])
        style.configure("Vertical.TScrollbar", background=BG, troughcolor=BG)

        self.data = {}
        self.scanning = False
        self._active_tab = "dashboard"
        self._scan_done = 0
        self._scan_total = len([m for m in MODULES if m[2] != "terminal"])
        self._scan_status = {key: "pending" for _, _, key in MODULES if key != "terminal"}

        self._build_titlebar()
        self._build_tab_bar()

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill=tk.BOTH, expand=True)

        self.content = tk.Frame(body, bg=BG)
        self.content.pack(fill=tk.BOTH, expand=True)

        self.tab_frames = {}
        for key in ["dashboard", "microsoft", "wifi", "browser", "broadcasts", "firewall", "terminal"]:
            self.tab_frames[key] = tk.Frame(self.content, bg=BG)

        self._build_statusbar()

        self._show_tab("dashboard")

        self.root.after(300, self.refresh_all)
        self.root.after(50, lambda: self.root.lift())
        self.root.after(100, lambda: self.root.focus_force())
        self.root.mainloop()

    # ── custom title bar ─────────────────────────────────────────────
    def _start_drag(self, event):
        if not self._maximized and event.x < self.root.winfo_width() - 140:
            self._drag_x = event.x
            self._drag_y = event.y

    def _do_drag(self, event):
        if not self._maximized:
            x = self.root.winfo_x() + event.x - self._drag_x
            y = self.root.winfo_y() + event.y - self._drag_y
            self.root.geometry(f"+{x}+{y}")

    def _minimize(self):
        self.root.iconify()

    def _toggle_maximize(self):
        if self._maximized:
            self.root.geometry(self._restore_geom)
            self._maximized = False
        else:
            self._restore_geom = self.root.geometry()
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            self.root.geometry(f"{sw}x{sh - 40}+0+0")
            self._maximized = True

    def _build_titlebar(self):
        bar = tk.Frame(self.root, bg=BG, height=38)
        bar.pack(fill=tk.X, side=tk.TOP)
        bar.pack_propagate(False)

        border = tk.Frame(bar, bg=BORDER, height=1)
        border.pack(side=tk.BOTTOM, fill=tk.X)
        border.pack_propagate(False)

        # drag target — whole bar
        bar.bind("<Button-1>", self._start_drag)
        bar.bind("<B1-Motion>", self._do_drag)

        # left side
        left = tk.Frame(bar, bg=BG)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(12, 0))

        tk.Label(left, text="\u25c9", bg=BG, fg="#22c55e",
                font=("Consolas", 11)).pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(left, text="privacyscope", bg=BG, fg=FG_SEC,
                font=("Consolas", 8)).pack(side=tk.LEFT, padx=(0, 16))

        DarkButton(left, "Scan All", self.refresh_all, 80, 26).pack(side=tk.LEFT, padx=(0, 6))
        DarkButton(left, "Export", self.export_report, 62, 26).pack(side=tk.LEFT, padx=(0, 6))
        DarkButton(left, "Copy", lambda: self._copy_module(self._active_tab), 52, 26).pack(side=tk.LEFT, padx=(0, 6))

        self.auto_var = tk.BooleanVar(value=False)
        cb = tk.Checkbutton(left, text="auto-refresh", variable=self.auto_var,
                            command=self._toggle_auto, bg=BG, fg=FG_MUTE,
                            selectcolor=BG, font=FONT_SM, activebackground=BG,
                            activeforeground=FG_SEC, relief=tk.FLAT, cursor="hand2")
        cb.pack(side=tk.LEFT, padx=(4, 0))

        # right side — window controls
        right = tk.Frame(bar, bg=BG)
        right.pack(side=tk.RIGHT, fill=tk.Y)

        for text, cmd in [("\u2500", self._minimize),
                          ("\u25a1", self._toggle_maximize),
                          ("\u2715", self._on_close)]:
            btn = tk.Label(right, text=text, bg=BG, fg=FG_SEC, font=("Consolas", 10),
                          padx=14, pady=0, cursor="hand2")
            btn.pack(side=tk.RIGHT, fill=tk.Y)
            btn.bind("<Enter>", lambda e, b=btn, t=text: b.configure(
                bg="#e81123" if t == "\u2715" else "#2a2a2a", fg="#fff"))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=BG, fg=FG_SEC))
            btn.bind("<Button-1>", lambda e, c=cmd: c())

    # ── tab bar ──────────────────────────────────────────────────────
    def _build_tab_bar(self):
        self.tab_bar = tk.Frame(self.root, bg=BG, height=34)
        self.tab_bar.pack(fill=tk.X, side=tk.TOP)

        border = tk.Frame(self.tab_bar, bg=BORDER, height=1)
        border.pack(fill=tk.X, side=tk.BOTTOM)
        border.pack_propagate(False)

        inner = tk.Frame(self.tab_bar, bg=BG)
        inner.pack(fill=tk.X, padx=12)

        self.tab_labels = {}
        self.tab_indicators = {}

        for key, label, icon in TABS:
            frame = tk.Frame(inner, bg=BG, cursor="hand2")
            frame.pack(side=tk.LEFT)

            if key != TABS[0][0]:
                sep = tk.Frame(inner, bg=BORDER, width=1)
                sep.pack(side=tk.LEFT, fill=tk.Y)

            lbl = tk.Label(frame, text=f" {label} ", bg=BG, fg=FG_SEC,
                          font=FONT, padx=12, pady=8)
            lbl.pack()
            lbl.bind("<Button-1>", lambda e, k=key: self._show_tab(k))
            frame.bind("<Button-1>", lambda e, k=key: self._show_tab(k))
            lbl.bind("<Enter>", lambda e, l=lbl: l.configure(fg=FG, bg="#1a1a1a"))
            lbl.bind("<Leave>", lambda e, l=lbl, k=key:
                     l.configure(fg=FG if self._active_tab == k else FG_SEC,
                                bg="#1a1a1a" if self._active_tab == k else BG))
            lbl._name = key

            indicator = tk.Frame(frame, bg=BG, height=2)
            indicator.pack(fill=tk.X)

            self.tab_labels[key] = lbl
            self.tab_indicators[key] = indicator

    def _show_tab(self, key):
        self.root.unbind_all("<MouseWheel>")
        self._active_tab = key

        for f in self.tab_frames.values():
            f.pack_forget()
        self.tab_frames[key].pack(fill=tk.BOTH, expand=True)

        for k, lbl in self.tab_labels.items():
            active = k == key
            lbl.configure(fg=FG if active else FG_SEC,
                         bg="#1a1a1a" if active else BG)
        for k, ind in self.tab_indicators.items():
            ind.configure(bg="#22c55e" if k == key else BG)

        if key == "dashboard":
            self._build_dashboard()
        elif key == "terminal":
            self._build_terminal_page()

    # ── status bar ──────────────────────────────────────────────────
    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=STATUS_BG, height=24)
        bar.pack(fill=tk.X, side=tk.BOTTOM)

        top_line = tk.Frame(bar, bg=BORDER, height=1)
        top_line.pack(side=tk.TOP, fill=tk.X)
        top_line.pack_propagate(False)

        left = tk.Frame(bar, bg=STATUS_BG)
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.status_var = tk.StringVar(value="")
        tk.Label(left, textvariable=self.status_var, bg=STATUS_BG, fg=FG_SEC,
                font=FONT_SM, anchor=tk.W, padx=10).pack(side=tk.LEFT, pady=2)

        right = tk.Frame(bar, bg=STATUS_BG)
        right.pack(side=tk.RIGHT)

        self._time_var = tk.StringVar(value="")
        tk.Label(right, textvariable=self._time_var, bg=STATUS_BG, fg=FG_MUTE,
                font=FONT_SM, anchor=tk.E, padx=10).pack(side=tk.RIGHT, pady=2)

    def _set_time_stamp(self):
        self._time_var.set(datetime.now().strftime("%H:%M:%S"))

    # ── scan logic ──────────────────────────────────────────────────
    def _toggle_auto(self):
        if self.auto_var.get():
            self._auto_refresh()

    def _auto_refresh(self):
        if self.auto_var.get():
            self.refresh_all()
            self.root.after(60000, self._auto_refresh)

    def refresh_all(self):
        if self.scanning:
            return
        self.scanning = True
        self._scan_done = 0
        self._scan_status = {key: "pending" for _, _, key in MODULES if key != "terminal"}
        self.status_var.set(f"> scanning [0/{self._scan_total}] ...")
        self._set_time_stamp()
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        results = {}
        done_count = 0
        for _, (label, mod, key) in enumerate(MODULES):
            if key == "terminal":
                continue
            self._scan_status[key] = "scanning"
            self.root.after(0, self._update_scan_progress, key, "scanning")
            try:
                items = mod.scan()
                results[key] = {"label": label, "items": items}
                self._scan_status[key] = "done"
            except Exception as e:
                results[key] = {"label": label, "items": [
                    {"label": "Error", "value": str(e), "severity": "high",
                     "detail": "Module failed to scan"}
                ]}
                self._scan_status[key] = "error"
            done_count += 1
            self._scan_done = done_count
            self.root.after(0, self._update_scan_progress, key, self._scan_status[key])
        self.data = results
        self.root.after(0, self._display_results)

    def _update_scan_progress(self, key, status):
        names = {"microsoft": "Microsoft", "wifi": "WiFi / ISP",
                 "browser": "Websites", "broadcasts": "Nearby", "firewall": "Firewall"}
        module_name = names.get(key, key)
        if status == "scanning":
            self.status_var.set(f"> scanning [{self._scan_done}/{self._scan_total}] {module_name}...")
        elif status == "done":
            self.status_var.set(f"> scanning [{self._scan_done}/{self._scan_total}] {module_name} ok")
        else:
            self.status_var.set(f"> scanning [{self._scan_done}/{self._scan_total}] {module_name} err")

    def _display_results(self):
        self.scanning = False
        for key, f in self.tab_frames.items():
            if key == "dashboard" or key == "terminal" or key not in self.data:
                continue
            self._clear_frame(f)
            self._build_module_page(f, self.data[key], key)
        self._build_dashboard()
        if self._active_tab == "terminal":
            self._build_terminal_page()
        self._set_time_stamp()
        total = sum(len(d["items"]) for d in self.data.values() if d["label"] != "Terminal")
        self.status_var.set(f"> {total} items exposed")

    # ── scroll helper ───────────────────────────────────────────────
    def _make_scrollable(self, parent, build_inner):
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, bg=BG, troughcolor=BG, activebackground=BORDER,
                                 borderwidth=0, highlightthickness=0)
        scroll_frame = tk.Frame(canvas, bg=BG)
        win_id = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

        def _resize(event):
            canvas.itemconfig(win_id, width=event.width)
            canvas._content_width = event.width

        scroll_frame.bind("<Configure>",
                          lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", _resize)
        canvas._content_width = 700
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.configure(command=canvas.yview)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _wraplength(c=canvas):
            return max(300, getattr(c, '_content_width', 600) - 50)
        canvas._wraplength = _wraplength

        def mw(event):
            # clamp scrolling to content bounds
            bbox = canvas.bbox("all")
            if not bbox:
                return
            canvas_height = canvas.winfo_height()
            content_height = bbox[3] - bbox[1]
            if content_height <= canvas_height:
                return
            delta = int(-1 * (event.delta / 120))
            current = canvas.canvasy(0)
            new_y = current + delta * 20
            if new_y < 0:
                new_y = 0
            elif new_y > content_height - canvas_height:
                new_y = content_height - canvas_height
            canvas.yview_moveto(new_y / content_height)
        canvas.bind("<Enter>", lambda e: self.root.bind_all("<MouseWheel>", mw))
        canvas.bind("<Leave>", lambda e: self.root.unbind_all("<MouseWheel>"))
        build_inner(scroll_frame)

    def _get_wraplength(self, widget):
        while widget:
            if hasattr(widget, '_wraplength') and callable(widget._wraplength):
                return widget._wraplength()
            widget = widget.master
        return 600

    # ── module page ─────────────────────────────────────────────────
    def _build_module_page(self, parent, mod_data, module_key):
        def build(scroll_frame):
            inner = tk.Frame(scroll_frame, bg=BG)
            inner.pack(fill=tk.BOTH, expand=True, padx=18, pady=(10, 8))

            header = tk.Frame(inner, bg=BG)
            header.pack(fill=tk.X, pady=(0, 16))

            tk.Label(header, text=f"$ {mod_data['label'].lower()}", bg=BG, fg=FG,
                    font=FONT_TITLE, anchor=tk.W).pack(side=tk.LEFT)

            counts = [sum(1 for i in mod_data["items"] if i.get("severity") == s)
                      for s in ["high", "medium", "low"]]
            for c, s, l in zip(counts, ["high", "med", "low"], SEV_FG.keys()):
                if c > 0:
                    lbl = tk.Label(header, text=f"{c} {s}  ", bg=BG,
                                  fg=SEV_FG[l], font=FONT_SM)
                    lbl.pack(side=tk.RIGHT)

            DarkButton(inner, "Copy",
                      lambda: self._copy_module(module_key), 48).pack(anchor="e", pady=(0, 10))

            for item in mod_data["items"]:
                self._add_item_card(inner, item)

        self._make_scrollable(parent, build)

    def _add_item_card(self, parent, item):
        sev = item.get("severity", "low")
        sev_fg = SEV_FG[sev]
        wl = self._get_wraplength(parent)

        card = tk.Frame(parent, bg=BG_SURFACE, highlightbackground=BORDER,
                       highlightthickness=1)
        card.pack(fill=tk.X, pady=3)

        header = tk.Frame(card, bg=BG_SURFACE)
        header.pack(fill=tk.X, padx=14, pady=(10, 4))

        tk.Label(header, text="\u25cf", bg=BG_SURFACE, fg=sev_fg,
                font=("Consolas", 7)).pack(side=tk.LEFT)
        tk.Label(header, text=f" {SEV_LABEL[sev]}", bg=BG_SURFACE, fg=sev_fg,
                font=("Consolas", 7, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(header, text=item["label"], bg=BG_SURFACE, fg=FG, font=FONT_BOLD,
                anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)

        val_text = str(item.get("value", ""))
        if len(val_text) > 60:
            val_text = val_text[:57] + "..."
        tk.Label(header, text=val_text, bg=BG_SURFACE, fg=FG_SEC, font=FONT,
                anchor=tk.E).pack(side=tk.RIGHT, padx=(4, 0))

        action = item.get("action", {})
        if action and action.get("label"):
            act_btn = DarkButton(header, action["label"],
                                lambda a=action: self._execute_action(a),
                                max(48, len(action["label"]) * 7 + 16))
            act_btn.pack(side=tk.RIGHT, padx=(6, 0))

        detail = item.get("detail", "")
        if detail:
            detail_frame = tk.Frame(card, bg=BG_SURFACE)
            detail_frame.pack(fill=tk.X, padx=24, pady=(0, 10))
            for part in detail.split("\n"):
                if part.strip():
                    tk.Label(detail_frame, text=part.strip(), bg=BG_SURFACE,
                            fg=FG_MUTE, font=FONT_SM, anchor=tk.W,
                            wraplength=wl, justify=tk.LEFT).pack(anchor=tk.W)

    # ── dashboard ───────────────────────────────────────────────────
    def _build_scan_progress(self, parent):
        self._clear_frame(parent)
        inner = tk.Frame(parent, bg=BG)
        inner.pack(expand=True, padx=60, pady=60)

        tk.Label(inner, text="$ scanning system ...", bg=BG, fg=FG_SEC,
                font=FONT_SM).pack(anchor=tk.W, pady=(0, 12))

        bar_outer = tk.Frame(inner, bg=BORDER, height=4)
        bar_outer.pack(fill=tk.X, pady=(0, 20))
        bar_outer.pack_propagate(False)
        pct = self._scan_done / self._scan_total
        bar_fill = tk.Frame(bar_outer, bg=FG_SEC)
        bar_fill.place(relx=0, rely=0, relwidth=pct, relheight=1)

        names = {"microsoft": "Microsoft", "wifi": "WiFi / ISP",
                 "browser": "Websites", "broadcasts": "Nearby", "firewall": "Firewall"}
        for _, _, key in MODULES:
            if key == "terminal":
                continue
            status = self._scan_status[key]
            row = tk.Frame(inner, bg=BG)
            row.pack(fill=tk.X, pady=1)
            if status == "done":
                icon, color, text = "  ok", "#22c55e", names[key]
            elif status == "error":
                icon, color, text = " err", "#ef4444", names[key]
            elif status == "scanning":
                icon, color, text = " ...", "#eab308", names[key]
            else:
                icon, color, text = "  --", FG_MUTE, names[key]
            tk.Label(row, text=icon, bg=BG, fg=color, font=FONT_SM,
                    width=5, anchor=tk.W).pack(side=tk.LEFT)
            tk.Label(row, text=text, bg=BG, fg=FG if status != "pending" else FG_MUTE,
                    font=FONT_SM, anchor=tk.W).pack(side=tk.LEFT)

        if self._scan_done == self._scan_total:
            tk.Label(inner, text="", bg=BG).pack()
            tk.Label(inner, text="  building dashboard ...", bg=BG, fg=FG_MUTE,
                    font=FONT_SM).pack(anchor=tk.W, pady=(12, 0))

    def _build_dashboard(self):
        self._clear_frame(self.tab_frames["dashboard"])
        parent = self.tab_frames["dashboard"]

        if not self.data:
            self._build_scan_progress(parent)
            return

        def build(scroll_frame):
            inner = tk.Frame(scroll_frame, bg=BG)
            inner.pack(fill=tk.X, padx=20, pady=(12, 10))

            # ── dashboard header ─────────────────────────────────────
            title_row = tk.Frame(inner, bg=BG)
            title_row.pack(fill=tk.X, pady=(0, 2))

            tk.Label(title_row, text="Dashboard", bg=BG, fg=FG,
                    font=("Consolas", 13, "bold")).pack(side=tk.LEFT)

            total = sum(len(d["items"]) for d in self.data.values())
            tk.Label(title_row, text=f"{total} items", bg=BG, fg=FG_MUTE,
                    font=FONT).pack(side=tk.LEFT, padx=(8, 0))

            # ── score row ───────────────────────────────────────────
            total_high = sum(1 for k in self.data for i in self.data[k]["items"]
                           if i.get("severity") == "high")
            total_med = sum(1 for k in self.data for i in self.data[k]["items"]
                          if i.get("severity") == "medium")
            total_low = sum(1 for k in self.data for i in self.data[k]["items"]
                          if i.get("severity") == "low")
            total_all = total_high + total_med + total_low or 1
            score = max(0, min(100, int(
                (total_high * 60 + total_med * 30 + total_low * 10) / total_all
            )))
            sc = "#22c55e" if score < 25 else "#eab308" if score < 50 else "#ef4444"

            hero_row = tk.Frame(inner, bg=BG)
            hero_row.pack(fill=tk.X, pady=(10, 18))

            gs = 100
            gauge = tk.Canvas(hero_row, bg=BG, width=gs, height=gs, highlightthickness=0)
            gauge.pack(side=tk.LEFT, padx=(0, 16))
            cx = gs // 2
            cy = gs - 4
            r = gs // 2 - 12
            extent = max(5, int(180 * score / 100))
            gauge.create_arc(cx - r, cy - r, cx + r, cy + r,
                           start=180, extent=180, style=tk.ARC, outline=BORDER, width=6)
            gauge.create_arc(cx - r, cy - r, cx + r, cy + r,
                           start=180, extent=extent, style=tk.ARC, outline=sc, width=6)
            gauge.create_text(cx, cy - 8, text=str(score),
                            fill=sc, font=("Consolas", 18, "bold"))
            gauge.create_text(cx, cy + 12, text="exposure",
                            fill=FG_MUTE, font=FONT_SM)

            sf = tk.Frame(hero_row, bg=BG)
            sf.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=(6, 0))

            desc = ("Well locked down" if score < 25
                    else "Moderate exposure" if score < 50
                    else "High exposure")
            tk.Label(sf, text=desc, bg=BG, fg=FG, font=FONT_TITLE).pack(anchor=tk.W)

            sr = tk.Frame(sf, bg=BG)
            sr.pack(fill=tk.X, pady=(6, 0))
            for label, count, color in [("High", total_high, "#ef4444"),
                                         ("Medium", total_med, "#eab308"),
                                         ("Low", total_low, "#22c55e")]:
                tk.Label(sr, text=f"\u25cf {count} ", bg=BG, fg=color,
                        font=("Consolas", 10, "bold")).pack(side=tk.LEFT)
                tk.Label(sr, text=f"{label}  ", bg=BG, fg=FG_SEC,
                        font=FONT_SM).pack(side=tk.LEFT, padx=(0, 14))

            # ── category cards — 2-column responsive grid ────────────
            keys_ordered = ["microsoft", "wifi", "browser", "broadcasts", "firewall"]
            grid = tk.Frame(inner, bg=BG)
            grid.pack(fill=tk.X)

            for i, key in enumerate(keys_ordered):
                if key not in self.data:
                    continue
                cat = self.data[key]
                items = cat["items"]
                h = sum(1 for it in items if it.get("severity") == "high")
                m = sum(1 for it in items if it.get("severity") == "medium")
                lo = sum(1 for it in items if it.get("severity") == "low")
                t = h + m + lo or 1

                col = i % 2
                row = i // 2
                is_last_odd = (i == len(keys_ordered) - 1 and col == 0)

                cs = 2 if is_last_odd else 1

                card = tk.Frame(grid, bg=BG_SURFACE, highlightbackground=BORDER,
                              highlightthickness=1, cursor="hand2")
                padx = (0, 6) if col == 0 else (6, 0)
                card.grid(row=row, column=col, columnspan=cs, padx=padx, pady=5,
                         sticky="nsew")
                card.bind("<Button-1>", lambda e, k=key: self._show_tab(k))
                card.bind("<Enter>", lambda e, c=card: c.configure(
                    highlightbackground=BORDER_HI))
                card.bind("<Leave>", lambda e, c=card: c.configure(
                    highlightbackground=BORDER))

                hdr = tk.Frame(card, bg=BG_SURFACE)
                hdr.pack(fill=tk.X, padx=16, pady=(14, 8))
                tk.Label(hdr, text=WHO[key], bg=BG_SURFACE, fg=FG,
                        font=("Consolas", 10, "bold")).pack(side=tk.LEFT)

                bar_row = tk.Frame(card, bg=BG_SURFACE)
                bar_row.pack(fill=tk.X, padx=16, pady=(0, 10))
                bar_bg = tk.Frame(bar_row, bg=BORDER, height=6)
                bar_bg.pack(fill=tk.X)
                bar_bg.pack_propagate(False)
                cum = 0.0
                for s, cnt, c in [("high", h, "#ef4444"), ("medium", m, "#eab308"),
                                    ("low", lo, "#22c55e")]:
                    if cnt > 0:
                        seg = tk.Frame(bar_bg, bg=c)
                        seg.place(relx=cum, rely=0, relwidth=cnt / t, relheight=1)
                        cum += cnt / t

                for item in items[:3]:
                    s = item.get("severity", "low")
                    ir = tk.Frame(card, bg=BG_SURFACE)
                    ir.pack(fill=tk.X, padx=16, pady=(0, 3))
                    tk.Label(ir, text="  \u25cf", bg=BG_SURFACE, fg=SEV_FG[s],
                            font=("Consolas", 6)).pack(side=tk.LEFT)
                    tk.Label(ir, text=f" {item['label']}", bg=BG_SURFACE,
                            fg=FG_SEC, font=FONT_SM).pack(side=tk.LEFT)
                    v = str(item.get("value", ""))[:25]
                    if v:
                        tk.Label(ir, text=f" {v}", bg=BG_SURFACE,
                                fg=FG_MUTE, font=FONT_SM).pack(side=tk.LEFT)

                rem = len(items) - 3
                if rem > 0:
                    more = tk.Frame(card, bg=BG_SURFACE, cursor="hand2")
                    more.pack(fill=tk.X, padx=16, pady=(6, 14))
                    more.bind("<Button-1>", lambda e, k=key: self._show_tab(k))
                    tk.Label(more, text=f"+ {rem} more \u2192", bg=BG_SURFACE,
                            fg=FG_MUTE, font=FONT_SM).pack(anchor=tk.W)

            grid.grid_columnconfigure(0, weight=1)
            grid.grid_columnconfigure(1, weight=1)

            # ── terminal preview ──────────────────────────────────
            try:
                tdata = monitor.scan()
                preview = "\n".join(tdata)[:800]
            except Exception:
                preview = "  terminal unavailable"

            term_sec = tk.Frame(inner, bg=BG_SURFACE, highlightbackground=BORDER,
                               highlightthickness=1)
            term_sec.pack(fill=tk.X, pady=(8, 10))

            th = tk.Frame(term_sec, bg=BG_SURFACE, cursor="hand2")
            th.pack(fill=tk.X)
            th.bind("<Button-1>", lambda e: self._show_tab("terminal"))
            tk.Label(th, text="  $ terminal", bg=BG_SURFACE, fg=FG,
                    font=FONT_TITLE, padx=16, pady=10).pack(side=tk.LEFT)
            th.bind("<Enter>", lambda e, h=th: h.configure(bg=BG_HOVER))
            th.bind("<Leave>", lambda e, h=th: h.configure(bg=BG_SURFACE))

            tb = tk.Frame(term_sec, bg="#050505")
            tb.pack(fill=tk.X, padx=2, pady=(0, 2))
            tt = tk.Text(tb, bg="#050505", fg="#33aa55", font=("Consolas", 8),
                        wrap=tk.WORD, borderwidth=0, padx=14, pady=10,
                        height=7, state=tk.NORMAL)
            tt.insert("1.0", preview)
            tt.configure(state=tk.DISABLED)
            tt.pack(fill=tk.X)

        self._make_scrollable(parent, build)

    # ── copy / export / actions ─────────────────────────────────────
    def _copy_module(self, key):
        if not self.data:
            return
        lines = ["privacyscope\n"]
        if key == "dashboard":
            for k, cd in self.data.items():
                lines.append(f"\n## {cd['label']}")
                for item in cd["items"]:
                    sev = item.get("severity", "low")
                    lines.append(f"  [{SEV_LABEL[sev]}] {item['label']}: {item.get('value','')}")
                    if item.get("detail"):
                        lines.append(f"       {item['detail']}")
        elif key in self.data:
            cd = self.data[key]
            lines.append(f"## {cd['label']}\n")
            for item in cd["items"]:
                sev = item.get("severity", "low")
                lines.append(f"  [{SEV_LABEL[sev]}] {item['label']}: {item.get('value','')}")
                if item.get("detail"):
                    lines.append(f"       {item['detail']}")
        else:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lines))
        self.status_var.set("> copied")

    def export_report(self):
        if not self.data:
            return
        fp = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("JSON", "*.json")],
            initialfile="privacyscope_report.txt",
            title="Export Report"
        )
        if not fp:
            return
        try:
            if fp.endswith(".json"):
                export = {k: {"category": cd["label"], "items": cd["items"]}
                         for k, cd in self.data.items()}
                with open(fp, "w", encoding="utf-8") as f:
                    json.dump(export, f, indent=2, ensure_ascii=False)
            else:
                lines = ["PRIVACYSCOPE EXPOSURE REPORT", "=" * 50, ""]
                for k, cd in self.data.items():
                    lines.append(f"## {cd['label']}")
                    lines.append("-" * 40)
                    for item in cd["items"]:
                        sev = item.get("severity", "low")
                        lines.append(f"  [{SEV_LABEL[sev]}] {item['label']}")
                        lines.append(f"       Value:  {item.get('value', 'N/A')}")
                        if item.get("detail"):
                            d = item["detail"].replace("\n", "\n       ")
                            lines.append(f"       Info:   {d}")
                        lines.append("")
                with open(fp, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
            messagebox.showinfo("Export", f"Saved to:\n{fp}")
            self.status_var.set(f"> exported {os.path.basename(fp)}")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))

    def _execute_action(self, action):
        if not action.get("cmd"):
            return
        label = action.get("label", "Fix")
        ok = messagebox.askyesno("Confirm Action",
                                 f"Run: {label}?\n\n{action['cmd'][:120]}...")
        if not ok:
            return

        def _run(cmd, elevated=False):
            if elevated:
                ps_cmd = f'''Start-Process cmd -Verb RunAs -Wait -ArgumentList '/c {cmd} & pause' '''
                r = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd],
                                   capture_output=True, text=True, timeout=30,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=20, shell=True,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
            return r

        try:
            cmd = action["cmd"]
            result = _run(cmd)
            out = result.stdout.strip()
            err = result.stderr.strip()
            if result.returncode == 0:
                if err and ("error" in err.lower() or "denied" in err.lower()):
                    messagebox.showerror("Action Failed", err)
                else:
                    self.status_var.set(f"> {label} — done. Rescanning...")
                    self.root.after(1200, self.refresh_all)
            elif "access is denied" in (err + out).lower():
                retry = messagebox.askyesno("Admin Required",
                    "This change needs administrator privileges.\n\nRetry as administrator?")
                if not retry:
                    return
                result = _run(cmd, elevated=True)
                out2 = result.stdout.strip()
                err2 = result.stderr.strip()
                if result.returncode == 0:
                    self.status_var.set(f"> {label} — done. Rescanning...")
                    self.root.after(1200, self.refresh_all)
                else:
                    messagebox.showerror("Action Failed", err2 or out2 or "Unknown error")
            else:
                messagebox.showerror("Action Failed", err or out or "Unknown error")
        except Exception as e:
            messagebox.showerror("Action Failed", str(e))

    # ── terminal page ───────────────────────────────────────────────
    def _build_terminal_page(self):
        parent = self.tab_frames["terminal"]
        tdata = monitor.scan()
        lines = "\n".join(tdata)
        self._clear_frame(parent)

        def build(scroll_frame):
            inner = tk.Frame(scroll_frame, bg=BG)
            inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 8))

            header = tk.Frame(inner, bg=BG)
            header.pack(fill=tk.X, pady=(0, 10))
            tk.Label(header, text="$ terminal", bg=BG, fg=FG,
                    font=FONT_TITLE, anchor=tk.W).pack(side=tk.LEFT)
            DarkButton(header, "Refresh",
                      lambda: self._build_terminal_page(), 58).pack(side=tk.RIGHT)

            term_frame = tk.Frame(inner, bg="#050505", highlightbackground=BORDER,
                                 highlightthickness=1)
            term_frame.pack(fill=tk.BOTH, expand=True)
            term_text = tk.Text(term_frame, bg="#050505", fg="#33aa55",
                               font=("Consolas", 9), wrap=tk.WORD,
                               insertbackground="#33aa55",
                               selectbackground="#0a2a0a",
                               borderwidth=0, padx=14, pady=12,
                               state=tk.NORMAL)
            term_text.insert("1.0", lines)
            term_text.configure(state=tk.DISABLED)
            term_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar = tk.Scrollbar(term_frame, bg="#050505", troughcolor="#050505")
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            term_text.configure(yscrollcommand=scrollbar.set)
            scrollbar.configure(command=term_text.yview)

        self._make_scrollable(parent, build)

    # ── helpers ─────────────────────────────────────────────────────
    def _clear_frame(self, frame):
        for w in frame.winfo_children():
            w.destroy()
        frame.configure(bg=BG)

    def _on_close(self):
        self.auto_var.set(False)
        self.root.destroy()


if __name__ == "__main__":
    PrivacyScopeApp()
