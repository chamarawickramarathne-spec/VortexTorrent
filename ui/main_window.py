import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.config import app_data_dir, load_settings, save_settings
from core.engine import TorrentEngine
from ui.dialogs import MagnetDialog, SettingsDialog
from updater import UpdateChecker

APP_VERSION = "1.0.0"


def fmt_bytes(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return "%.1f %s" % (n, unit)
        n /= 1024


def fmt_rate(n):
    return fmt_bytes(n) + "/s"


def fmt_eta(secs):
    secs = int(secs or 0)
    if secs <= 0:
        return "—"
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    if h:
        return "%d:%02d:%02d" % (h, m, s)
    return "%d:%02d" % (m, s)


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Vortex Torrent")
        self.geometry("900x520")
        self.minsize(760, 420)

        self.settings = load_settings()
        self.config_dir = app_data_dir()

        icon = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media", "icon.ico")
        if os.path.exists(icon):
            try:
                self.iconbitmap(icon)
            except tk.TclError:
                pass

        self.engine = TorrentEngine(self.config_dir)
        self._build_toolbar()
        self._build_table()
        self._build_statusbar()
        self._last_snapshot = {}

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.engine.start(
            port=self.settings["port"],
            download_rate=self.settings["download_rate"],
            upload_rate=self.settings["upload_rate"],
        )
        threading.Thread(target=self._check_update_bg, daemon=True).start()
        self._refresh_after_id = None
        self.after(500, self._refresh)

    def _build_toolbar(self):
        bar = ttk.Frame(self, padding=(6, 6))
        bar.pack(fill="x")

        ttk.Button(bar, text="Add .torrent", command=self._add_torrent_file).pack(side="left", padx=3)
        ttk.Button(bar, text="Add Magnet", command=self._add_magnet).pack(side="left", padx=3)
        ttk.Button(bar, text="Pause", command=self._pause_selected).pack(side="left", padx=3)
        ttk.Button(bar, text="Resume", command=self._resume_selected).pack(side="left", padx=3)
        ttk.Button(bar, text="Remove", command=self._remove_selected).pack(side="left", padx=3)
        ttk.Button(bar, text="Delete Files", command=self._delete_selected).pack(side="left", padx=3)
        ttk.Button(bar, text="Settings", command=self._open_settings).pack(side="left", padx=3)

    def _build_table(self):
        self.columns = ("name", "size", "progress", "state", "down", "up", "peers", "eta")
        self.tree = ttk.Treeview(self, columns=self.columns, show="headings", selectmode="extended")
        headings = {
            "name": ("Name", 300),
            "size": ("Size", 90),
            "progress": ("Progress", 120),
            "state": ("State", 110),
            "down": ("Down", 90),
            "up": ("Up", 90),
            "peers": ("Peers", 70),
            "eta": ("ETA", 70),
        }
        for col, (text, width) in headings.items():
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w" if col == "name" else "e")

        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(fill="both", expand=True, padx=6)
        vsb.pack(side="right", fill="y")

    def _build_statusbar(self):
        self.status = ttk.Label(self, text="Ready", relief="sunken", anchor="w", padding=(6, 2))
        self.status.pack(fill="x", side="bottom")

    def _selected_ids(self):
        return [self.tree.set(item, "#0") for item in self.tree.selection()]

    def _add_torrent_file(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("Torrent files", "*.torrent"), ("All files", "*.*")])
        if not path:
            return
        os.makedirs(self.settings["download_dir"], exist_ok=True)
        try:
            entry = self.engine.add_torrent_file(path, self.settings["download_dir"])
        except Exception as exc:
            messagebox.showerror("Add failed", str(exc), parent=self)
            return
        self.tree.insert("", "end", iid=entry.id, values=self._row(entry.id))

    def _add_magnet(self):
        dialog = MagnetDialog(self)
        self.wait_window(dialog)
        if not dialog.result:
            return
        os.makedirs(self.settings["download_dir"], exist_ok=True)
        try:
            entry = self.engine.add_magnet(dialog.result, self.settings["download_dir"])
        except Exception as exc:
            messagebox.showerror("Add failed", str(exc), parent=self)
            return
        self.tree.insert("", "end", iid=entry.id, values=self._row(entry.id))

    def _row(self, torrent_id):
        snap = self._last_snapshot.get(torrent_id)
        if not snap:
            return ("...", "", "", "", "", "", "", "")
        return (
            snap["name"],
            fmt_bytes(snap["size"]),
            "%.1f%%" % (snap["progress"] * 100),
            snap["state"],
            fmt_rate(snap["download_rate"]),
            fmt_rate(snap["upload_rate"]),
            "%d/%d" % (snap["seeds"], snap["peers"]),
            fmt_eta(snap["eta"]),
        )

    def _refresh(self):
        snapshots = self.engine.snapshot()
        self._last_snapshot = {s["id"]: s for s in snapshots}
        current = set(self.tree.get_children())
        active = set(self._last_snapshot.keys())
        for removed in current - active:
            self.tree.delete(removed)
        for torrent_id, snap in self._last_snapshot.items():
            values = self._row(torrent_id)
            if torrent_id in current:
                self.tree.item(torrent_id, values=values)
            else:
                self.tree.insert("", "end", iid=torrent_id, values=values)

        total_down = sum(s["download_rate"] for s in snapshots)
        total_up = sum(s["upload_rate"] for s in snapshots)
        active_count = sum(1 for s in snapshots if s["state"] in ("Downloading", "Seeding"))
        self.status.configure(
            text="Active: %d   Down: %s   Up: %s" % (active_count, fmt_rate(total_down), fmt_rate(total_up))
        )
        self._refresh_after_id = self.after(500, self._refresh)

    def _pause_selected(self):
        for tid in self._selected_ids():
            self.engine.pause(tid)

    def _resume_selected(self):
        for tid in self._selected_ids():
            self.engine.resume(tid)

    def _remove_selected(self, delete=False):
        for tid in self._selected_ids():
            self.engine.remove(tid, delete_files=delete)
            self.tree.delete(tid)

    def _delete_selected(self):
        if not self.tree.selection():
            return
        if messagebox.askyesno("Delete files", "Delete downloaded files too?", parent=self):
            self._remove_selected(delete=True)
        else:
            self._remove_selected()

    def _open_settings(self):
        dialog = SettingsDialog(self, self.settings)
        self.wait_window(dialog)
        if not dialog.result:
            return
        self.settings = dialog.result
        save_settings(self.settings)
        os.makedirs(self.settings["download_dir"], exist_ok=True)
        self.engine.apply_speed_limits(self.settings["download_rate"], self.settings["upload_rate"])
        self.engine.apply_port(self.settings["port"])

    def _check_update_bg(self):
        try:
            checker = UpdateChecker()
            latest = checker.check()
        except Exception:
            latest = None
        if latest and latest != APP_VERSION:
            self.after(2000, lambda: self._offer_update(latest))

    def _offer_update(self, version):
        if messagebox.askyesno(
            "Update available",
            "Vortex Torrent %s is available (you have %s).\n\nDownload and install now?" % (version, APP_VERSION),
            parent=self,
        ):
            try:
                self._download_and_install(version)
            except Exception as exc:
                messagebox.showerror("Update failed", str(exc), parent=self)

    def _download_and_install(self, version):
        installer = os.path.join(self.config_dir, "VortexTorrent-Setup-%s.exe" % version)
        UpdateChecker().download_installer(version, installer)
        self.engine.stop()
        self.destroy()
        subprocess.Popen([installer])

    def _on_close(self):
        if getattr(self, "_refresh_after_id", None):
            try:
                self.after_cancel(self._refresh_after_id)
            except tk.TclError:
                pass
            self._refresh_after_id = None
        self.engine.stop()
        self.destroy()


def main():
    try:
        app = MainWindow()
        app.mainloop()
    except Exception as exc:
        messagebox.showerror("Vortex Torrent", "Failed to start:\n%s" % exc)
        sys.exit(1)
