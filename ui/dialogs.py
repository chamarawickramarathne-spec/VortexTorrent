import tkinter as tk

import customtkinter as ctk
from tkinter import filedialog

from ui import theme


def _fmt_bytes(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return "%.1f %s" % (n, unit)
        n /= 1024


class MagnetDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Add Magnet Link")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result = None

        frame = ctk.CTkFrame(self, fg_color=theme.PANEL, corner_radius=12)
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(frame, text="Paste a magnet link below", font=theme.font(15, "bold")).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(frame, text="Magnet link:", font=theme.font(12)).pack(anchor="w")

        self.magnet = ctk.CTkTextbox(frame, width=440, height=100, wrap="word", fg_color=theme.BG, border_color=theme.BORDER, border_width=1)
        self.magnet.pack(fill="x", pady=(4, 12))

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(anchor="e")
        ctk.CTkButton(btn_frame, text="Cancel", fg_color=theme.PANEL_HOVER, hover_color=theme.BORDER, command=self.destroy, width=90).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="Add", fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, command=self._ok, width=90).pack(side="left")

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.magnet.focus_set()

        try:
            clip = self.clipboard_get().strip()
            if "magnet:" in clip:
                self.magnet.insert("1.0", clip)
        except tk.TclError:
            pass

    def _ok(self):
        self.result = self.magnet.get("1.0", "end").strip()
        if self.result:
            self.destroy()


class FileSelectDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, files):
        super().__init__(parent)
        self.title(title)
        self.geometry("560x480")
        self.minsize(480, 320)
        self.transient(parent)
        self.grab_set()
        self.result = None
        self._files = list(files)
        self._vars = []

        frame = ctk.CTkFrame(self, fg_color=theme.PANEL, corner_radius=12)
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        head = ctk.CTkFrame(frame, fg_color="transparent")
        head.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(head, text="Select files to download", font=theme.font(15, "bold")).pack(side="left")
        ctk.CTkLabel(head, text="%d files · %s" % (len(files), _fmt_bytes(sum(f[1] for f in files))), font=theme.font(11), text_color=theme.TEXT_DIM).pack(side="right")

        self.box = ctk.CTkScrollableFrame(frame, fg_color=theme.BG, corner_radius=8)
        self.box.pack(fill="both", expand=True)
        self.box.grid_columnconfigure(0, weight=1)

        for name, size in self._files:
            var = tk.BooleanVar(value=True)
            self._vars.append(var)
            row = ctk.CTkFrame(self.box, fg_color="transparent")
            row.grid(sticky="ew", pady=1)
            ctk.CTkCheckBox(row, text=name, variable=var, font=theme.font(12), checkbox_width=20, checkbox_height=20, fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER).pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(row, text=_fmt_bytes(size), font=theme.font(11), text_color=theme.TEXT_DIM).pack(side="right", padx=(8, 8))

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(12, 0))
        ctk.CTkButton(btn_frame, text="Select All", fg_color=theme.PANEL_HOVER, hover_color=theme.BORDER, command=lambda: self._set_all(True), width=92).pack(side="left")
        ctk.CTkButton(btn_frame, text="Select None", fg_color=theme.PANEL_HOVER, hover_color=theme.BORDER, command=lambda: self._set_all(False), width=92).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="Cancel", fg_color=theme.PANEL_HOVER, hover_color=theme.BORDER, command=self.destroy, width=90).pack(side="right", padx=6)
        ctk.CTkButton(btn_frame, text="OK", fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, command=self._ok, width=90).pack(side="right")

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())

    def _set_all(self, value):
        for var in self._vars:
            var.set(value)

    def _ok(self):
        self.result = [1 if var.get() else 0 for var in self._vars]
        self.destroy()


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.title("Settings")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.settings = dict(settings)
        self.result = None

        frame = ctk.CTkFrame(self, fg_color=theme.PANEL, corner_radius=12)
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(frame, text="Settings", font=theme.font(16, "bold")).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(frame, text="Download folder", font=theme.font(12)).pack(anchor="w")
        folder_row = ctk.CTkFrame(frame, fg_color="transparent")
        folder_row.pack(fill="x", pady=(4, 8))
        self.dir_var = ctk.StringVar(value=self.settings["download_dir"])
        ctk.CTkEntry(folder_row, textvariable=self.dir_var, fg_color=theme.BG, border_color=theme.BORDER).pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(folder_row, text="Browse...", fg_color=theme.PANEL_HOVER, hover_color=theme.BORDER, command=self._browse, width=90).pack(side="left")

        limits_row = ctk.CTkFrame(frame, fg_color="transparent")
        limits_row.pack(fill="x", pady=(4, 4))
        ctk.CTkLabel(limits_row, text="Download limit (KB/s)", font=theme.font(12)).pack(side="left")
        self.down_var = ctk.StringVar(value=str(self.settings["download_rate"] // 1024))
        ctk.CTkEntry(limits_row, textvariable=self.down_var, width=90, fg_color=theme.BG, border_color=theme.BORDER).pack(side="right")
        ctk.CTkLabel(limits_row, text="0 = unlimited").pack(side="right", padx=(0, 10))

        port_row = ctk.CTkFrame(frame, fg_color="transparent")
        port_row.pack(fill="x", pady=(8, 4))
        ctk.CTkLabel(port_row, text="Listen port", font=theme.font(12)).pack(side="left")
        self.port_var = ctk.StringVar(value=str(self.settings["port"]))
        ctk.CTkEntry(port_row, textvariable=self.port_var, width=120, fg_color=theme.BG, border_color=theme.BORDER).pack(side="right")

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(anchor="e", pady=(14, 0))
        ctk.CTkButton(btn_frame, text="Cancel", fg_color=theme.PANEL_HOVER, hover_color=theme.BORDER, command=self.destroy, width=90).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="Save", fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, command=self._save, width=90).pack(side="left")

    def _browse(self):
        path = filedialog.askdirectory(parent=self, title="Choose download folder")
        if path:
            self.dir_var.set(path)

    def _save(self):
        try:
            self.settings["download_dir"] = self.dir_var.get().strip()
            self.settings["download_rate"] = int(self.down_var.get()) * 1024
            self.settings["port"] = int(self.port_var.get())
        except ValueError:
            import tkinter as tk
            tk.messagebox.showerror("Invalid input", "Limits and port must be numbers.", parent=self)
            return
        self.result = self.settings
        self.destroy()


class AboutDialog(ctk.CTkToplevel):
    def __init__(self, parent, version):
        super().__init__(parent)
        self.title("About Vortex Torrent")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        frame = ctk.CTkFrame(self, fg_color=theme.PANEL, corner_radius=12)
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(frame, text="Vortex Torrent", font=theme.font(20, "bold"), text_color=theme.CYAN).pack(pady=(6, 0))
        ctk.CTkLabel(frame, text="Version %s" % version, font=theme.font(13), text_color=theme.TEXT_DIM).pack()
        ctk.CTkLabel(frame, text="Fast, free desktop BitTorrent downloader.\nBuilt with libtorrent + customtkinter.", font=theme.font(12), text_color=theme.TEXT).pack(pady=(10, 4))
        ctk.CTkLabel(frame, text="github.com/chamarawickramarathne-spec/VortexTorrent", font=theme.font(11), text_color=theme.ACCENT).pack(pady=(4, 10))
        ctk.CTkButton(frame, text="Close", fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, command=self.destroy, width=120).pack(pady=(6, 4))
