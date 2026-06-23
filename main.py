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

BG          = "#080808"
BG_SURFACE  = "#0f0f0f"
BORDER      = "#1c1c1c"
BORDER_HI   = "#333333"
FG          = "#f0f0f0"
FG_SEC      = "#9e9e9e"
FG_MUTE     = "#525252"
ACCENT      = "#f0f0f0"

SEV_FG      = {"low": "#22c55e", "medium": "#eab308", "high": "#ef4444"}
SEV_BG      = {"low": "#05220c", "medium": "#281c04", "high": "#2a0606"}
SEV_LABEL   = {"low": "LOW", "medium": "MED", "high": "HIGH"}

FONT        = ("Consolas", 9)
FONT_SM     = ("Consolas", 8)
FONT_BOLD   = ("Consolas", 9, "bold")
FONT_TITLE  = ("Consolas", 11, "bold")
FONT_HERO   = ("Consolas", 28, "bold")

MODULES = [
    ("Microsoft", telemetry, "microsoft"),
    ("WiFi / ISP", network, "wifi"),
    ("Websites", browser, "browser"),
    ("Nearby", broadcasts, "broadcasts"),
    ("Firewall", firewall, "firewall"),
    ("Terminal", monitor, "terminal"),
]

TABS = [
    ("dashboard", "Dashboard"),
    ("microsoft", "Microsoft"),
    ("wifi", "WiFi / ISP"),
    ("browser", "Websites"),
    ("broadcasts", "Nearby"),
    ("firewall", "Firewall"),
    ("terminal", "Terminal"),
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
    def __init__(self, parent, text, command, width=72, height=28, icon=""):
        super().__init__(parent, width=width, height=height,
                         bg=BG, highlightthickness=0, cursor="hand2")
        self.command = command
        self._text = icon + " " + text if icon else text
        self._hover = False
        self._draw()
        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _draw(self):
        self.delete("all")
        bg = "#2a2a2a" if self._hover else BG
        fg = FG if self._hover else FG_SEC
        self.create_rectangle(0, 0, self.winfo_reqwidth(), self.winfo_reqheight(),
                              fill=bg, outline="", width=0)
        self.create_text(self.winfo_reqwidth() / 2, self.winfo_reqheight() / 2,
                         text=self._text, fill=fg, font=FONT)

    def _on_enter(self, e):
        self._hover = True
        self._draw()

    def _on_leave(self, e):
        self._hover = False
        self._draw()


class PrivacyScopeApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("privacyscope")
        self.root.geometry("940x700")
        self.root.minsize(800, 550)
        self.root.configure(bg=BG)

        # global dark scrollbar style
        style = ttk.Style()
        style.configure("TScrollbar", background=BG, troughcolor=BG,
                       arrowcolor=FG_MUTE, bordercolor=BG)
        style.map("TScrollbar", background=[("active", BORDER)])
        style.configure("Vertical.TScrollbar", background=BG, troughcolor=BG)

        self.data = {}
        self.scanning = False
        self._active_tab = "dashboard"
        self._mw_handler = None
        self._scan_done = 0
        self._scan_total = len([m for m in MODULES if m[2] != "terminal"])
        self._scan_status = {key: "pending" for _, _, key in MODULES if key != "terminal"}

        self._build_toolbar()
        self._build_tab_bar()

        self.content = tk.Frame(self.root, bg=BG)
        self.content.pack(fill=tk.BOTH, expand=True)

        self.tab_frames = {}
        for key in ["dashboard", "microsoft", "wifi", "browser", "broadcasts", "firewall", "terminal"]:
            self.tab_frames[key] = tk.Frame(self.content, bg=BG)

        self._build_statusbar()
        self._show_tab("dashboard")

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(300, self.refresh_all)
        self.root.after(100, lambda: self.root.lift())
        self.root.after(200, lambda: self.root.focus_force())
        self.root.mainloop()

    # ── toolbar ─────────────────────────────────────────────────────
    def _build_toolbar(self):
        bar = tk.Frame(self.root, bg=BG, height=36)
        bar.pack(fill=tk.X, side=tk.TOP)

        border = tk.Frame(bar, bg=BORDER, height=1)
        border.pack(side=tk.BOTTOM, fill=tk.X)
        border.pack_propagate(False)

        inner = tk.Frame(bar, bg=BG)
        inner.pack(fill=tk.X, padx=8, pady=4)

        # app icon + name (left)
        brand = tk.Frame(inner, bg=BG)
        brand.pack(side=tk.LEFT)
        tk.Label(brand, text="\u25c9", bg=BG, fg="#22c55e",
                font=("Consolas", 10)).pack(side=tk.LEFT, padx=(2, 4))
        tk.Label(brand, text="PRIVACYSCOPE", bg=BG, fg=FG_SEC,
                font=("Consolas", 8, "bold")).pack(side=tk.LEFT, padx=(0, 12))

        DarkButton(inner, "Scan All", self.refresh_all, 80).pack(side=tk.LEFT, padx=(0, 2))
        DarkButton(inner, "Export", self.export_report, 62).pack(side=tk.LEFT, padx=2)
        DarkButton(inner, "Copy", lambda: self._copy_module(self._active_tab),
                  52).pack(side=tk.LEFT, padx=2)

        # right side
        rside = tk.Frame(inner, bg=BG)
        rside.pack(side=tk.RIGHT)

        self.auto_var = tk.BooleanVar(value=False)
        cb = tk.Checkbutton(rside, text="auto-refresh", variable=self.auto_var,
                            command=self._toggle_auto,
                            bg=BG, fg=FG_MUTE, selectcolor=BG,
                            font=FONT_SM, activebackground=BG,
                            activeforeground=FG_SEC, relief=tk.FLAT,
                            cursor="hand2")
        cb.pack(side=tk.RIGHT, padx=(0, 0))

    # ── tab bar ─────────────────────────────────────────────────────
    def _build_tab_bar(self):
        self.tab_bar = tk.Frame(self.root, bg=BG, height=32)
        self.tab_bar.pack(fill=tk.X, side=tk.TOP)

        border = tk.Frame(self.tab_bar, bg=BORDER, height=1)
        border.pack(fill=tk.X, side=tk.BOTTOM)
        border.pack_propagate(False)

        inner = tk.Frame(self.tab_bar, bg=BG)
        inner.pack(fill=tk.BOTH, padx=6)

        self.tab_labels = {}
        self.tab_indicators = {}

        for key, label in TABS:
            tab = tk.Frame(inner, bg=BG, cursor="hand2")
            tab.pack(side=tk.LEFT)

            # subtle separator between tabs
            if key != TABS[0][0]:
                sep = tk.Frame(inner, bg=BORDER, width=1)
                sep.pack(side=tk.LEFT, fill=tk.Y, padx=0)

            lbl = tk.Label(tab, text=f" {label} ", bg=BG, fg=FG_SEC,
                          font=FONT, padx=10, pady=7)
            lbl.pack()

            tab.bind("<Button-1>", lambda e, k=key: self._show_tab(k))
            lbl.bind("<Button-1>", lambda e, k=key: self._show_tab(k))
            lbl.bind("<Enter>", lambda e, l=lbl: l.configure(
                fg=FG, bg="#1a1a1a"))
            lbl.bind("<Leave>", lambda e, l=lbl, k=key:
                     l.configure(fg=FG if self._active_tab == k else FG_SEC,
                                bg="#1a1a1a" if self._active_tab == k else BG))
            lbl._name = key

            indicator = tk.Frame(tab, bg=BG, height=2)
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
        bar = tk.Frame(self.root, bg="#0d1117", height=24)
        bar.pack(fill=tk.X, side=tk.BOTTOM)

        top_line = tk.Frame(bar, bg=BORDER, height=1)
        top_line.pack(side=tk.TOP, fill=tk.X)
        top_line.pack_propagate(False)

        left = tk.Frame(bar, bg="#0d1117")
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.status_var = tk.StringVar(value="")
        tk.Label(left, textvariable=self.status_var, bg="#0d1117", fg=FG_SEC,
                font=FONT_SM, anchor=tk.W, padx=10).pack(side=tk.LEFT, pady=2)

        right = tk.Frame(bar, bg="#0d1117")
        right.pack(side=tk.RIGHT)

        self._time_var = tk.StringVar(value="")
        tk.Label(right, textvariable=self._time_var, bg="#0d1117", fg=FG_MUTE,
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
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL)
        scroll_frame = tk.Frame(canvas, bg=BG)
        win_id = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

        def _resize(event):
            w = event.width
            canvas.itemconfig(win_id, width=w)
            canvas._content_width = w

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
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: self.root.bind_all("<MouseWheel>", mw))
        canvas.bind("<Leave>", lambda e: self.root.unbind_all("<MouseWheel>"))

        build_inner(scroll_frame)

    # ── module page ─────────────────────────────────────────────────
    def _build_module_page(self, parent, mod_data, module_key):
        def build(scroll_frame):
            inner = tk.Frame(scroll_frame, bg=BG)
            inner.pack(fill=tk.BOTH, expand=True, padx=16, pady=(12, 8))

            header = tk.Frame(inner, bg=BG)
            header.pack(fill=tk.X, pady=(0, 14))

            tk.Label(header, text=f"$ {mod_data['label'].lower()}", bg=BG, fg=FG,
                    font=FONT_TITLE, anchor=tk.W).pack(side=tk.LEFT)

            counts = [sum(1 for i in mod_data["items"] if i.get("severity") == s)
                      for s in ["high", "medium", "low"]]
            parts = []
            for c, s, l in zip(counts, ["high", "med", "low"], SEV_FG.keys()):
                if c > 0:
                    lbl = tk.Label(header, text=f"{c} {s}  ", bg=BG,
                                  fg=SEV_FG[l], font=FONT_SM)
                    lbl.pack(side=tk.RIGHT)

            copy_btn = DarkButton(inner, "Copy",
                                  lambda: self._copy_module(module_key), 48)
            copy_btn.pack(anchor="e", pady=(0, 8))

            for item in mod_data["items"]:
                self._add_item_card(inner, item)

        self._make_scrollable(parent, build)

    def _add_item_card(self, parent, item):
        sev = item.get("severity", "low")
        sev_fg = SEV_FG[sev]
        wl = self._get_wraplength(parent)

        card = tk.Frame(parent, bg=BG_SURFACE, highlightbackground=BORDER,
                       highlightthickness=1)
        card.pack(fill=tk.X, pady=2)

        header = tk.Frame(card, bg=BG_SURFACE)
        header.pack(fill=tk.X, padx=10, pady=(8, 2))

        tk.Label(header, text="■", bg=BG_SURFACE, fg=sev_fg, font=("Consolas", 7)).pack(side=tk.LEFT)
        tk.Label(header, text=f" {SEV_LABEL[sev]}", bg=BG_SURFACE, fg=sev_fg,
                font=("Consolas", 7, "bold")).pack(side=tk.LEFT, padx=(0, 8))
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
            act_btn.pack(side=tk.RIGHT, padx=(4, 0))

        detail = item.get("detail", "")
        if detail:
            detail_frame = tk.Frame(card, bg=BG_SURFACE)
            detail_frame.pack(fill=tk.X, padx=18, pady=(0, 8))
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

        # main progress bar
        bar_outer = tk.Frame(inner, bg=BORDER, height=4)
        bar_outer.pack(fill=tk.X, pady=(0, 20))
        bar_outer.pack_propagate(False)
        pct = self._scan_done / self._scan_total
        bar_fill = tk.Frame(bar_outer, bg=FG_SEC)
        bar_fill.place(relx=0, rely=0, relwidth=pct, relheight=1)

        # module indicators
        names = {
            "microsoft": "Microsoft", "wifi": "WiFi / ISP",
            "browser": "Websites", "broadcasts": "Nearby", "firewall": "Firewall",
        }
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
            inner.pack(fill=tk.X, padx=16, pady=(12, 8))
            wl = self._get_wraplength(inner)

            # ── score + stats row ────────────────────────────────────
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
            hero_row.pack(fill=tk.X, pady=(0, 12))

            # ── gauge (left) ──
            gauge_size = 120
            gauge = tk.Canvas(hero_row, bg=BG, width=gauge_size, height=gauge_size,
                             highlightthickness=0)
            gauge.pack(side=tk.LEFT, padx=(0, 12))

            cx = gauge_size // 2
            cy = gauge_size - 10
            r = gauge_size // 2 - 10
            extent = max(5, int(180 * score / 100))

            gauge.create_arc(cx - r, cy - r, cx + r, cy + r,
                           start=180, extent=180, style=tk.ARC,
                           outline=BORDER, width=8)
            gauge.create_arc(cx - r, cy - r, cx + r, cy + r,
                           start=180, extent=extent, style=tk.ARC,
                           outline=sc, width=8)
            gauge.create_text(cx, cy - 12, text=str(score),
                            fill=sc, font=("Consolas", 22, "bold"))
            gauge.create_text(cx, cy + 18, text="exposure",
                            fill=FG_MUTE, font=FONT_SM)

            # ── stats (right) ──
            stats_frame = tk.Frame(hero_row, bg=BG)
            stats_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=(10, 0))

            desc = ("Well locked down" if score < 25
                    else "Moderate exposure" if score < 50
                    else "High exposure — review items below")
            tk.Label(stats_frame, text=desc, bg=BG, fg=FG,
                    font=FONT_TITLE, anchor=tk.W).pack(fill=tk.X)

            ss = tk.Frame(stats_frame, bg=BG)
            ss.pack(fill=tk.X, pady=(8, 0))

            for label, count, color in [("High", total_high, "#ef4444"),
                                         ("Medium", total_med, "#eab308"),
                                         ("Low", total_low, "#22c55e")]:
                sf = tk.Frame(ss, bg=BG)
                sf.pack(side=tk.LEFT, padx=(0, 16))
                tk.Label(sf, text=f"● {count}", bg=BG, fg=color,
                        font=("Consolas", 11, "bold")).pack(side=tk.LEFT)
                tk.Label(sf, text=f" {label}", bg=BG, fg=FG_SEC,
                        font=FONT_SM).pack(side=tk.LEFT)

            # ── category cards (2-column grid) ──────────────────────
            grid = tk.Frame(inner, bg=BG)
            grid.pack(fill=tk.X)

            keys_ordered = ["microsoft", "wifi", "browser", "broadcasts", "firewall"]
            for i, key in enumerate(keys_ordered):
                if key not in self.data:
                    continue
                cat_data = self.data[key]
                items = cat_data["items"]
                h = sum(1 for it in items if it.get("severity") == "high")
                m = sum(1 for it in items if it.get("severity") == "medium")
                lo = sum(1 for it in items if it.get("severity") == "low")
                total = h + m + lo or 1

                col = i % 2 if i < 4 else (i % 2)
                row = i // 2
                if i >= 4:
                    col = 0
                    row = 2

                card = tk.Frame(grid, bg=BG_SURFACE, highlightbackground=BORDER,
                              highlightthickness=1, cursor="hand2")
                card.bind("<Button-1>", lambda e, k=key: self._show_tab(k))
                card.bind("<Enter>", lambda e, c=card: c.configure(
                    highlightbackground=BORDER_HI))
                card.bind("<Leave>", lambda e, c=card: c.configure(
                    highlightbackground=BORDER))

                if i < 4:
                    card.grid(row=row, column=col, padx=(0, 6) if col == 0 else (6, 0),
                             pady=4, sticky="nsew")
                else:
                    card.grid(row=2, column=0, columnspan=2, pady=4, sticky="nsew")

                hdr = tk.Frame(card, bg=BG_SURFACE)
                hdr.pack(fill=tk.X, padx=14, pady=(10, 4))
                tk.Label(hdr, text=WHO[key], bg=BG_SURFACE, fg=FG,
                        font=("Consolas", 10, "bold")).pack(side=tk.LEFT)

                # severity bar chart
                bar_row = tk.Frame(card, bg=BG_SURFACE)
                bar_row.pack(fill=tk.X, padx=14, pady=(0, 10))
                bar_bg = tk.Frame(bar_row, bg=BORDER, height=8)
                bar_bg.pack(fill=tk.X)
                bar_bg.pack_propagate(False)

                cum = 0.0
                for s, cnt, c in [("high", h, "#ef4444"), ("medium", m, "#eab308"),
                                    ("low", lo, "#22c55e")]:
                    if cnt > 0:
                        w = cnt / total
                        seg = tk.Frame(bar_bg, bg=c, width=int(w * 200))
                        seg.place(relx=cum, rely=0, relwidth=w, relheight=1)
                        cum += w

                # top items
                for item in items[:3]:
                    s = item.get("severity", "low")
                    ir = tk.Frame(card, bg=BG_SURFACE)
                    ir.pack(fill=tk.X, padx=14, pady=(0, 2))
                    tk.Label(ir, text="  ●", bg=BG_SURFACE, fg=SEV_FG[s],
                            font=("Consolas", 6)).pack(side=tk.LEFT)
                    val = str(item.get("value", ""))[:30]
                    tk.Label(ir, text=f" {item['label']}", bg=BG_SURFACE,
                            fg=FG_SEC, font=FONT_SM).pack(side=tk.LEFT)
                    if val:
                        tk.Label(ir, text=f" {val}", bg=BG_SURFACE,
                                fg=FG_MUTE, font=FONT_SM).pack(side=tk.LEFT)

                rem = len(items) - 3
                if rem > 0:
                    more = tk.Frame(card, bg=BG_SURFACE, cursor="hand2")
                    more.pack(fill=tk.X, padx=14, pady=(4, 10))
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
            term_sec.pack(fill=tk.X, pady=(10, 10))

            term_hdr = tk.Frame(term_sec, bg=BG_SURFACE, cursor="hand2")
            term_hdr.pack(fill=tk.X)
            term_hdr.bind("<Button-1>", lambda e: self._show_tab("terminal"))
            tk.Label(term_hdr, text="  $ terminal", bg=BG_SURFACE, fg=FG,
                    font=FONT_TITLE, padx=14, pady=8).pack(side=tk.LEFT)
            term_hdr.bind("<Enter>", lambda e, h=term_hdr: h.configure(bg="#141414"))
            term_hdr.bind("<Leave>", lambda e, h=term_hdr: h.configure(bg=BG_SURFACE))

            term_body = tk.Frame(term_sec, bg="#0a0a0a")
            term_body.pack(fill=tk.X, padx=2, pady=(0, 2))
            term_txt = tk.Text(term_body, bg="#0a0a0a", fg="#33aa55",
                              font=("Consolas", 8), wrap=tk.WORD,
                              borderwidth=0, padx=14, pady=10, height=7,
                              state=tk.NORMAL)
            term_txt.insert("1.0", preview)
            term_txt.configure(state=tk.DISABLED)
            term_txt.pack(fill=tk.X)

        self._make_scrollable(parent, build)

    # ── copy / export ───────────────────────────────────────────────
    def _copy_module(self, key):
        if not self.data:
            return

        lines = ["privacyscope\n"]
        if key == "dashboard":
            for k, cd in self.data.items():
                lines.append(f"\n## {cd['label']}")
                for item in cd["items"]:
                    sev = item.get("severity", "low")
                    lines.append(
                        f"  [{SEV_LABEL[sev]}] {item['label']}: {item.get('value','')}")
                    if item.get("detail"):
                        lines.append(f"       {item['detail']}")
        elif key in self.data:
            cd = self.data[key]
            lines.append(f"## {cd['label']}\n")
            for item in cd["items"]:
                sev = item.get("severity", "low")
                lines.append(
                    f"  [{SEV_LABEL[sev]}] {item['label']}: {item.get('value','')}")
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
                export = {}
                for k, cd in self.data.items():
                    export[k] = {"category": cd["label"], "items": cd["items"]}
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

    # ── actions ─────────────────────────────────────────────────────
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
                                   capture_output=True, text=True, timeout=30)
            else:
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=20, shell=True)
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
                retry = messagebox.askyesno(
                    "Admin Required",
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
                      lambda: self._build_terminal_page(), 58, 24).pack(side=tk.RIGHT)

            # terminal output area
            term_frame = tk.Frame(inner, bg="#0a0a0a", highlightbackground=BORDER,
                                 highlightthickness=1)
            term_frame.pack(fill=tk.BOTH, expand=True)

            term_text = tk.Text(term_frame, bg="#0a0a0a", fg="#00ff66",
                               font=("Consolas", 9), wrap=tk.WORD,
                               insertbackground="#00ff66",
                               selectbackground="#1a3a1a",
                               borderwidth=0, padx=14, pady=12,
                               state=tk.NORMAL)
            term_text.insert("1.0", lines)
            term_text.configure(state=tk.DISABLED)
            term_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            scrollbar = tk.Scrollbar(term_frame, bg=BG, troughcolor=BG)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            term_text.configure(yscrollcommand=scrollbar.set)
            scrollbar.configure(command=term_text.yview)

        self._make_scrollable(parent, build)

    # ── helpers ─────────────────────────────────────────────────────
    def _get_wraplength(self, widget):
        while widget:
            if hasattr(widget, '_wraplength') and callable(widget._wraplength):
                return widget._wraplength()
            widget = widget.master
        return 600

    def _clear_frame(self, frame):
        for w in frame.winfo_children():
            w.destroy()
        frame.configure(bg=BG)

    def _on_close(self):
        self.auto_var.set(False)
        self.root.destroy()


if __name__ == "__main__":
    PrivacyScopeApp()
