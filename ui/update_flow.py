"""Update check / download / install flow.

Extracted from main_window.py to keep individual modules under 300 lines.
"""

import os
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox

from updater import UpdateChecker


class UpdateFlow:
    """Background update checking and installer launch for the main window."""

    def __init__(self, window, version, config_dir):
        self.window = window
        self.version = version
        self.config_dir = config_dir

    def check_background(self):
        try:
            latest = UpdateChecker().check(self.version)
        except Exception:
            return
        if latest:
            self.window.after(2000, lambda: self.offer(latest) if not self.window._closing else None)

    def manual_check(self):
        self.window.status_left.configure(text="Checking for updates...")
        self.window.after(0, lambda: threading.Thread(target=self._manual_worker, daemon=True).start())

    def _manual_worker(self):
        try:
            latest = UpdateChecker().check(self.version)
        except Exception:
            self.window.after(0, lambda: messagebox.showerror("Update check failed", "Could not reach GitHub. Check your connection.", parent=self.window))
            return
        if latest is None:
            self.window.after(0, lambda: messagebox.showinfo("Up to date", "You are running the latest version (%s)." % self.version, parent=self.window))
        else:
            self.window.after(0, lambda: self.offer(latest))

    def offer(self, version):
        if messagebox.askyesno(
            "Update available",
            "Vortex Torrent %s is available (you have %s).\n\nDownload and install now?" % (version, self.version),
            parent=self.window,
        ):
            try:
                self.download_and_install(version)
            except Exception as exc:
                messagebox.showerror("Update failed", str(exc), parent=self.window)

    def download_and_install(self, version):
        checker = UpdateChecker()
        installer = os.path.join(self.config_dir, "VortexTorrent-Setup.exe")
        try:
            checker.download_installer(installer)
            checker.cleanup_stale(self.config_dir, os.path.basename(installer))
        except Exception as exc:
            raise RuntimeError(str(exc))
        self.window.engine.stop()
        self.window.destroy()
        subprocess.Popen([installer])