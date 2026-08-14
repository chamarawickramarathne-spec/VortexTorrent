import tkinter as tk
from tkinter import ttk, filedialog


class MagnetDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Add Magnet Link")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result = None

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Magnet link:").grid(row=0, column=0, sticky="w")
        self.magnet = tk.Text(frame, width=60, height=5, wrap="word")
        self.magnet.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 8))

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=2, column=0, columnspan=2, sticky="e")
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Add", command=self._ok).pack(side="left")

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.magnet.focus_set()

    def _ok(self):
        self.result = self.magnet.get("1.0", "end").strip()
        if self.result:
            self.destroy()


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.title("Settings")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.settings = dict(settings)
        self.result = None

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Download folder:").grid(row=0, column=0, sticky="w", pady=4)
        self.dir_var = tk.StringVar(value=self.settings["download_dir"])
        entry = ttk.Entry(frame, textvariable=self.dir_var, width=45)
        entry.grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(frame, text="Browse...", command=self._browse).grid(row=0, column=2)

        ttk.Label(frame, text="Download limit (KB/s, 0 = unlimited):").grid(
            row=1, column=0, sticky="w", pady=4
        )
        self.down_var = tk.StringVar(value=str(self.settings["download_rate"] // 1024))
        ttk.Entry(frame, textvariable=self.down_var, width=15).grid(row=1, column=1, sticky="w", padx=4)

        ttk.Label(frame, text="Upload limit (KB/s, 0 = unlimited):").grid(
            row=2, column=0, sticky="w", pady=4
        )
        self.up_var = tk.StringVar(value=str(self.settings["upload_rate"] // 1024))
        ttk.Entry(frame, textvariable=self.up_var, width=15).grid(row=2, column=1, sticky="w", padx=4)

        ttk.Label(frame, text="Listen port:").grid(row=3, column=0, sticky="w", pady=4)
        self.port_var = tk.StringVar(value=str(self.settings["port"]))
        ttk.Entry(frame, textvariable=self.port_var, width=15).grid(row=3, column=1, sticky="w", padx=4)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Save", command=self._save).pack(side="left")

    def _browse(self):
        path = filedialog.askdirectory(parent=self, title="Choose download folder")
        if path:
            self.dir_var.set(path)

    def _save(self):
        try:
            self.settings["download_dir"] = self.dir_var.get().strip()
            self.settings["download_rate"] = int(self.down_var.get()) * 1024
            self.settings["upload_rate"] = int(self.up_var.get()) * 1024
            self.settings["port"] = int(self.port_var.get())
        except ValueError:
            tk.messagebox.showerror("Invalid input", "Limits and port must be numbers.", parent=self)
            return
        self.result = self.settings
        self.destroy()
