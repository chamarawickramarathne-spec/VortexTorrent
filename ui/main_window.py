import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from core.config import app_data_dir, load_settings, save_settings
from core.engine import TorrentEngine
from ui import theme
from ui.dialogs import AboutDialog, FileSelectDialog, MagnetDialog, SettingsDialog
from updater import UpdateChecker

APP_VERSION = "1.6.0"
GITHUB_URL = "https://github.com/chamarawickramarathne-spec/VortexTorrent"


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
        return "--:--"
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    if h:
        return "%d:%02d:%02d" % (h, m, s)
    return "%02d:%02d" % (m, s)


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Vortex Torrent")
        self.geometry("1000x600")
        self.minsize(820, 480)
        ctk.set_appearance_mode("dark")

        self.settings = load_settings()
        self.config_dir = app_data_dir()

        icon = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media", "icon.ico")
        if os.path.exists(icon):
            try:
                self.iconbitmap(icon)
            except tk.TclError:
                pass

        self.engine = TorrentEngine(self.config_dir)
        self._last_snapshot = {}
        self._row_widgets = {}
        self._selected_id = None
        self._file_dialog_shown = set()
        self._build_header()
        self._build_toolbar()
        self._build_table()
        self._build_statusbar()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.engine.start(
            port=self.settings["port"],
            download_rate=self.settings["download_rate"],
            upload_rate=0,
        )
        self.bind("<Control-o>", lambda e: self._add_torrent_file())
        self.bind("<Control-m>", lambda e: self._add_magnet())
        self.bind("<Delete>", lambda e: self._remove_selected(delete=False))
        self.bind("<space>", lambda e: self._toggle_selected())
        threading.Thread(target=self._check_update_bg, daemon=True).start()
        self._refresh_after_id = None
        self._closing = False
        self.after(300, self._refresh)

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=theme.PANEL, corner_radius=0, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        logo = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media", "logo.png")
        if os.path.exists(logo):
            img = ctk.CTkImage(light_image=Image.open(logo), dark_image=Image.open(logo), size=(40, 40))
            ctk.CTkLabel(header, image=img, text="").pack(side="left", padx=(16, 10), pady=12)

        title_block = ctk.CTkFrame(header, fg_color="transparent")
        title_block.pack(side="left")
        title_row = ctk.CTkFrame(title_block, fg_color="transparent")
        title_row.pack(anchor="w")
        ctk.CTkLabel(title_row, text="Vortex Torrent", font=theme.font(18, "bold"), text_color=theme.TEXT).pack(side="left")
        version_label = ctk.CTkLabel(title_row, text="v%s" % APP_VERSION, font=theme.font(11, "bold"), text_color=theme.CYAN, cursor="hand2")
        version_label.pack(side="left", padx=(8, 0), pady=(3, 0))
        version_label.bind("<Button-1>", lambda e: self._open_about())
        ctk.CTkLabel(title_block, text="Fast, free BitTorrent downloader", font=theme.font(11), text_color=theme.TEXT_DIM).pack(anchor="w")

        self.btn_update = ctk.CTkButton(header, text="Update", font=theme.font(12, "bold"), fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, command=self._manual_update_check, height=30, width=90)
        self.btn_update.pack(side="right", padx=16, pady=17)

    def _build_toolbar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(12, 6))

        add_frame = ctk.CTkFrame(bar, fg_color="transparent")
        add_frame.pack(side="left")
        self.btn_add_file = ctk.CTkButton(add_frame, text="+  Add Torrent", font=theme.font(13, "bold"), fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, command=self._add_torrent_file, height=34)
        self.btn_add_file.pack(side="left", padx=(0, 8))
        self.btn_add_magnet = ctk.CTkButton(add_frame, text="+  Add Magnet", font=theme.font(13, "bold"), fg_color=theme.CYAN, hover_color=theme.CYAN_HOVER, text_color="#04222b", command=self._add_magnet, height=34)
        self.btn_add_magnet.pack(side="left")

        action_frame = ctk.CTkFrame(bar, fg_color="transparent")
        action_frame.pack(side="right")
        self.btn_pause = ctk.CTkButton(action_frame, text="Pause", font=theme.font(12), fg_color=theme.PANEL_HOVER, hover_color=theme.BORDER, command=self._pause_selected, width=84, height=32)
        self.btn_pause.pack(side="left", padx=4)
        self.btn_resume = ctk.CTkButton(action_frame, text="Resume", font=theme.font(12), fg_color=theme.PANEL_HOVER, hover_color=theme.BORDER, command=self._resume_selected, width=84, height=32)
        self.btn_resume.pack(side="left", padx=4)
        self.btn_remove = ctk.CTkButton(action_frame, text="Remove", font=theme.font(12), fg_color=theme.DANGER, hover_color="#ff6580", command=self._remove_selected, width=90, height=32)
        self.btn_remove.pack(side="left", padx=4)
        self.btn_settings = ctk.CTkButton(action_frame, text="Settings", font=theme.font(12), fg_color=theme.PANEL_HOVER, hover_color=theme.BORDER, command=self._open_settings, width=90, height=32)
        self.btn_settings.pack(side="left", padx=4)

    def _build_table(self):
        container = ctk.CTkFrame(self, fg_color=theme.PANEL, corner_radius=12)
        container.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        header = ctk.CTkFrame(container, fg_color=theme.BG, corner_radius=0, height=34)
        header.pack(fill="x")
        header.pack_propagate(False)
        cols = [
            ("name", "Name", 1),
            ("size", "Size", 0),
            ("pct", "%", 0),
            ("state", "Status", 0),
            ("down", "Down", 0),
            ("peers", "Seeds/Peers", 0),
            ("eta", "ETA", 0),
        ]
        widths = {"size": 90, "pct": 60, "state": 90, "down": 90, "peers": 110, "eta": 70}
        for idx, (key, text, weight) in enumerate(cols):
            header.grid_columnconfigure(idx, weight=weight)
            anchor = "w" if idx == 0 else "center"
            kwargs = {}
            if idx != 0:
                kwargs["width"] = widths[key]
            ctk.CTkLabel(header, text=text, font=theme.font(11, "bold"), text_color=theme.TEXT_DIM, **kwargs).grid(row=0, column=idx, sticky="ew", padx=4)

        self.rows = ctk.CTkScrollableFrame(container, fg_color="transparent")
        self.rows.pack(fill="both", expand=True)
        self.rows.grid_columnconfigure(0, weight=1)

        self.empty = ctk.CTkFrame(self.rows, fg_color="transparent")
        self.empty.grid(row=0, column=0, sticky="nsew", pady=40)
        ctk.CTkLabel(self.empty, text="No downloads yet", font=theme.font(22, "bold"), text_color=theme.TEXT_DIM).pack(pady=(40, 6))
        ctk.CTkLabel(self.empty, text="Add a .torrent file or paste a magnet link to get started", font=theme.font(13), text_color=theme.TEXT_DIM).pack()
        ctk.CTkButton(self.empty, text="Add Torrent", font=theme.font(13, "bold"), fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, command=self._add_torrent_file, width=160, height=38).pack(pady=(18, 0))

        self._menu = tk.Menu(self, tearoff=0)

    def _build_statusbar(self):
        self.status = ctk.CTkFrame(self, fg_color=theme.PANEL, corner_radius=8, height=36)
        self.status.pack(fill="x", padx=12, pady=(0, 10))
        self.status.pack_propagate(False)
        self.status_left = ctk.CTkLabel(self.status, text="Ready", font=theme.font(12), text_color=theme.TEXT_DIM)
        self.status_left.pack(side="left", padx=12)
        self.status_right = ctk.CTkLabel(self.status, text="", font=theme.font(12, "bold"), text_color=theme.CYAN)
        self.status_right.pack(side="right", padx=12)

    def _selected_ids(self):
        if not self._selected_id:
            return []
        return [self._selected_id]

    def _add_torrent_file(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("Torrent files", "*.torrent"), ("All files", "*.*")])
        if not path:
            return
        os.makedirs(self.settings["download_dir"], exist_ok=True)
        try:
            files = self.engine.file_list_from_file(path)
        except Exception as exc:
            messagebox.showerror("Add failed", str(exc), parent=self)
            return
        priorities = None
        if len(files) > 1:
            dialog = FileSelectDialog(self, os.path.basename(path), files)
            self.wait_window(dialog)
            if dialog.result is None:
                return
            priorities = dialog.result
        try:
            entry = self.engine.add_torrent_file(path, self.settings["download_dir"], priorities=priorities)
        except Exception as exc:
            messagebox.showerror("Add failed", str(exc), parent=self)
            return
        if priorities is not None:
            try:
                self.engine.set_file_priorities(entry.id, priorities)
            except Exception:
                pass
        self._create_row(entry.id)

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
        self._create_row(entry.id)

    def _show_file_selection(self, torrent_id):
        if torrent_id in self._file_dialog_shown:
            return
        files = self.engine.file_list(torrent_id)
        if files is None:
            return
        self._file_dialog_shown.add(torrent_id)
        if len(files) <= 1:
            self.engine.resume(torrent_id)
            return
        snap = self._last_snapshot.get(torrent_id)
        title = (snap or {}).get("name") or "Select files"
        dialog = FileSelectDialog(self, title, files)
        self.wait_window(dialog)
        if dialog.result is not None:
            try:
                self.engine.set_file_priorities(torrent_id, dialog.result)
            except Exception as exc:
                messagebox.showerror("Selection failed", str(exc), parent=self)
        self.engine.resume(torrent_id)

    def _create_row(self, torrent_id):
        if torrent_id in self._row_widgets:
            return
        snap = self._last_snapshot.get(torrent_id) or {}
        name = snap.get("name", "...")

        row = ctk.CTkFrame(self.rows, fg_color=theme.BG, corner_radius=8, height=52)
        row.grid(row=len(self._row_widgets) + 1, column=0, sticky="ew", pady=2, padx=2)
        row.grid_columnconfigure(0, weight=1)
        row.grid_propagate(False)

        name_label = ctk.CTkLabel(row, text=name, font=theme.font(13), text_color=theme.TEXT, anchor="w", width=40)
        name_label.grid(row=0, column=0, sticky="ew", padx=(12, 8))
        size_label = ctk.CTkLabel(row, text="", font=theme.font(11), text_color=theme.TEXT_DIM, width=70)
        size_label.grid(row=0, column=1, padx=4)
        pct_label = ctk.CTkLabel(row, text="0%", font=theme.font(11, "bold"), text_color=theme.ACCENT, width=48)
        pct_label.grid(row=0, column=2, padx=4)
        state_label = ctk.CTkLabel(row, text="", font=theme.font(10, "bold"), text_color=theme.TEXT_DIM, width=60)
        state_label.grid(row=0, column=3, padx=4)
        down_label = ctk.CTkLabel(row, text="", font=theme.font(11), text_color=theme.SUCCESS, width=70)
        down_label.grid(row=0, column=4, padx=4)
        peers_label = ctk.CTkLabel(row, text="", font=theme.font(11), text_color=theme.TEXT_DIM, width=80)
        peers_label.grid(row=0, column=5, padx=4)
        eta_label = ctk.CTkLabel(row, text="", font=theme.font(11), text_color=theme.TEXT_DIM, width=60)
        eta_label.grid(row=0, column=6, padx=8)

        progress = ctk.CTkProgressBar(row, height=6, fg_color=theme.BORDER, progress_color=theme.ACCENT, corner_radius=3)
        progress.grid(row=1, column=0, columnspan=7, sticky="ew", padx=12, pady=(0, 8))
        progress.set(0)

        for widget in (row, name_label, size_label, pct_label, state_label, down_label, peers_label, eta_label, progress):
            widget.bind("<Button-1>", lambda e, tid=torrent_id: self._select_row(tid, e))
        row.bind("<Button-3>", lambda e, tid=torrent_id: self._show_context_menu(tid, e))
        row.bind("<Double-Button-1>", lambda e, tid=torrent_id: self._open_folder(tid))

        self._row_widgets[torrent_id] = {
            "row": row,
            "name": name_label,
            "size": size_label,
            "pct": pct_label,
            "state": state_label,
            "down": down_label,
            "peers": peers_label,
            "eta": eta_label,
            "progress": progress,
        }

    def _select_row(self, torrent_id, event=None):
        self._selected_id = torrent_id
        for tid, w in self._row_widgets.items():
            bg = theme.ROW_SELECTED if tid == torrent_id else theme.BG
            w["row"].configure(fg_color=bg)
        self._update_action_buttons()

    def _show_context_menu(self, torrent_id, event):
        self._select_row(torrent_id)
        ctx = tk.Menu(self, tearoff=0)
        ctx.add_command(label="Pause", command=self._pause_selected)
        ctx.add_command(label="Resume", command=self._resume_selected)
        ctx.add_separator()
        ctx.add_command(label="Remove", command=lambda: self._remove_selected(delete=False))
        ctx.add_command(label="Delete Files", command=lambda: self._remove_selected(delete=True))
        ctx.add_separator()
        ctx.add_command(label="Open Folder", command=lambda: self._open_folder(torrent_id))
        try:
            ctx.tk_popup(event.x_root, event.y_root)
        finally:
            ctx.grab_release()

    def _open_folder(self, torrent_id):
        snap = self._last_snapshot.get(torrent_id)
        if not snap:
            return
        path = snap.get("save_path")
        if path and os.path.isdir(path):
            os.startfile(path)

    def _refresh(self):
        snapshots = self.engine.snapshot()
        self._last_snapshot = {s["id"]: s for s in snapshots}
        for tid in self.engine.take_files_ready():
            if tid not in self._file_dialog_shown:
                self._show_file_selection(tid)
        active_ids = set(self._last_snapshot.keys())
        for tid in set(self._row_widgets.keys()) - active_ids:
            self._row_widgets.pop(tid)["row"].destroy()
        if self._selected_id and self._selected_id not in active_ids:
            self._selected_id = None

        for idx, (tid, snap) in enumerate(self._last_snapshot.items(), start=1):
            self._create_row(tid)
            w = self._row_widgets[tid]
            w["row"].grid(row=idx, column=0, sticky="ew", pady=2, padx=2)
            w["name"].configure(text=snap["name"])
            w["size"].configure(text=fmt_bytes(snap["size"]))
            pct = snap["progress"] * 100
            w["pct"].configure(text="%.1f%%" % pct, text_color=theme.state_color(snap["state"]))
            w["state"].configure(text=snap["state"], text_color=theme.state_color(snap["state"]))
            w["down"].configure(text=fmt_rate(snap["download_rate"]))
            w["peers"].configure(text="%d/%d" % (snap["seeds"], snap["peers"]))
            w["eta"].configure(text=fmt_eta(snap["eta"]))
            w["progress"].set(min(1.0, snap["progress"]))

        if snapshots:
            self.empty.grid_remove()
        else:
            self.empty.grid()

        total_down = sum(s["download_rate"] for s in snapshots)
        active_count = sum(1 for s in snapshots if s["state"] in ("Downloading", "Seeding"))
        self.status_left.configure(text="Active: %d  ·  Total: %d" % (active_count, len(snapshots)))
        self.status_right.configure(text="%s ↓" % fmt_rate(total_down))
        self._update_action_buttons()
        self._refresh_after_id = self.after(500, self._refresh)

    def _update_action_buttons(self):
        state = "normal"
        if not self._selected_id:
            state = "disabled"
        self.btn_pause.configure(state=state)
        self.btn_resume.configure(state=state)
        self.btn_remove.configure(state=state)

    def _pause_selected(self):
        for tid in self._selected_ids():
            self.engine.pause(tid)

    def _resume_selected(self):
        for tid in self._selected_ids():
            self.engine.resume(tid)

    def _toggle_selected(self):
        if not self._selected_id:
            return
        snap = self._last_snapshot.get(self._selected_id)
        if snap and snap["state"] == "Paused":
            self.engine.resume(self._selected_id)
        elif snap and snap["state"] == "Completed":
            return
        else:
            self.engine.pause(self._selected_id)

    def _remove_selected(self, delete=False):
        if not self._selected_id:
            return
        msg = "Remove this torrent from the list? Files will be kept." if not delete else "Delete this torrent AND its downloaded files?"
        if not messagebox.askyesno("Remove torrent", msg, parent=self):
            return
        tid = self._selected_id
        self.engine.remove(tid, delete_files=delete)
        self._selected_id = None

    def _open_settings(self):
        dialog = SettingsDialog(self, self.settings)
        self.wait_window(dialog)
        if not dialog.result:
            return
        self.settings = dialog.result
        save_settings(self.settings)
        os.makedirs(self.settings["download_dir"], exist_ok=True)
        self.engine.apply_speed_limits(self.settings["download_rate"])
        self.engine.apply_port(self.settings["port"])

    def _open_about(self):
        AboutDialog(self, APP_VERSION)

    def _manual_update_check(self):
        self.status_left.configure(text="Checking for updates...")
        self.after(0, lambda: threading.Thread(target=self._manual_update_worker, daemon=True).start())

    def _manual_update_worker(self):
        try:
            latest = UpdateChecker().check()
        except Exception:
            self.after(0, lambda: messagebox.showerror("Update check failed", "Could not reach GitHub. Check your connection.", parent=self))
            return
        if latest == APP_VERSION:
            self.after(0, lambda: messagebox.showinfo("Up to date", "You are running the latest version (%s)." % APP_VERSION, parent=self))
        else:
            self.after(0, lambda: self._offer_update(latest))

    def _check_update_bg(self):
        try:
            latest = UpdateChecker().check()
        except Exception:
            return
        if latest and latest != APP_VERSION:
            self.after(2000, lambda: self._offer_update(latest) if not self._closing else None)

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
        self._closing = True
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
