import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from core.config import app_data_dir, load_settings, save_settings
from core.engine import TorrentEngine
from ui import theme
from ui.dialogs import AboutDialog, FileSelectDialog, MagnetDialog, SettingsDialog
from ui.torrent_rows import TorrentRowManager, format_rate
from ui.update_flow import UpdateFlow

APP_VERSION = "1.11.0"


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Vortex Torrent")
        self.geometry("1000x600")
        self.minsize(820, 480)
        ctk.set_appearance_mode("dark")

        self.settings = load_settings()
        self.config_dir = app_data_dir()
        self.update_flow = UpdateFlow(self, APP_VERSION, self.config_dir)

        icon = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media", "icon.ico")
        if os.path.exists(icon):
            try:
                self.iconbitmap(icon)
            except tk.TclError:
                pass

        self.engine = TorrentEngine(self.config_dir)
        self._last_snapshot = {}
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
            max_active_downloads=self.settings["max_active_downloads"],
        )
        self.bind("<Control-o>", lambda e: self._add_torrent_file())
        self.bind("<Control-m>", lambda e: self._add_magnet())
        self.bind("<Delete>", lambda e: self._remove_selected(delete=False))
        self.bind("<space>", lambda e: self._toggle_selected())
        threading.Thread(target=self.update_flow.check_background, daemon=True).start()
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
        title_block.pack(side="left", padx=(4, 8), pady=8)
        title_row = ctk.CTkFrame(title_block, fg_color="transparent")
        title_row.pack(anchor="w")
        ctk.CTkLabel(title_row, text="Vortex Torrent", font=theme.font(18, "bold"), text_color=theme.TEXT).pack(side="left")
        version_label = ctk.CTkLabel(title_row, text="v%s" % APP_VERSION, font=theme.font(11, "bold"), text_color=theme.CYAN, cursor="hand2")
        version_label.pack(side="left", padx=(8, 0), pady=(3, 0))
        version_label.bind("<Button-1>", lambda e: self._open_about())
        ctk.CTkLabel(title_block, text="Fast, free BitTorrent downloader", font=theme.font(11), text_color=theme.TEXT_DIM).pack(anchor="w")

        self.btn_update = ctk.CTkButton(header, text="Update", font=theme.font(12, "bold"), fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, command=self.update_flow.manual_check, height=30, width=90)
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

        hdr = ctk.CTkFrame(container, fg_color=theme.BG, corner_radius=0, height=34)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        cols = [("Name", 1, "w"), ("Size", 90, "c"), ("%", 60, "c"), ("Status", 90, "c"),
                ("Down", 90, "c"), ("Seeds/Peers", 110, "c"), ("ETA", 70, "c")]
        for idx, (text, width, anchor) in enumerate(cols):
            hdr.grid_columnconfigure(idx, weight=1 if anchor == "w" else 0)
            w = {} if anchor == "w" else {"width": width}
            ctk.CTkLabel(hdr, text=text, font=theme.font(11, "bold"), text_color=theme.TEXT_DIM, **w).grid(row=0, column=idx, sticky="ew", padx=4)

        self.rows = ctk.CTkScrollableFrame(container, fg_color="transparent")
        self.rows.pack(fill="both", expand=True)
        self.rows.grid_columnconfigure(0, weight=1)

        self.rows_mgr = TorrentRowManager(self.rows, self)

        self.empty = ctk.CTkFrame(self.rows, fg_color="transparent")
        self.empty.grid(row=0, column=0, sticky="nsew", pady=40)
        ctk.CTkLabel(self.empty, text="No downloads yet", font=theme.font(22, "bold"), text_color=theme.TEXT_DIM).pack(pady=(40, 6))
        ctk.CTkLabel(self.empty, text="Add a .torrent file or paste a magnet link to get started", font=theme.font(13), text_color=theme.TEXT_DIM).pack()
        ctk.CTkButton(self.empty, text="Add Torrent", font=theme.font(13, "bold"), fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, command=self._add_torrent_file, width=160, height=38).pack(pady=(18, 0))

    def _build_statusbar(self):
        self.status = ctk.CTkFrame(self, fg_color=theme.PANEL, corner_radius=8, height=36)
        self.status.pack(fill="x", padx=12, pady=(0, 10))
        self.status.pack_propagate(False)
        self.status_left = ctk.CTkLabel(self.status, text="Ready", font=theme.font(12), text_color=theme.TEXT_DIM)
        self.status_left.pack(side="left", padx=12)
        self.status_right = ctk.CTkLabel(self.status, text="", font=theme.font(12, "bold"), text_color=theme.CYAN)
        self.status_right.pack(side="right", padx=12)

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
        self.rows_mgr.create(entry.id)

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
        self.rows_mgr.create(entry.id)

    def _show_file_selection(self, torrent_id):
        if torrent_id in self._file_dialog_shown:
            return
        files = self.engine.file_list(torrent_id)
        if files is None:
            return
        self._file_dialog_shown.add(torrent_id)
        if len(files) <= 1:
            self.engine.activate(torrent_id)
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
        self.engine.activate(torrent_id)

    def _refresh(self):
        snapshots = self.engine.snapshot()
        self._last_snapshot = {s["id"]: s for s in snapshots}
        for tid in self.engine.take_files_ready():
            if tid not in self._file_dialog_shown:
                self._show_file_selection(tid)
        active_ids = set(self._last_snapshot.keys())
        for tid in set(self.rows_mgr.widgets().keys()) - active_ids:
            self.rows_mgr.remove(tid)
        if self.rows_mgr._selected_id and self.rows_mgr._selected_id not in active_ids:
            self.rows_mgr.clear_selection()

        for idx, (tid, snap) in enumerate(self._last_snapshot.items(), start=1):
            self.rows_mgr.create(tid, snap)
            w = self.rows_mgr.widgets()[tid]
            w["row"].grid(row=idx, column=0, sticky="ew", pady=2, padx=2)
            self.rows_mgr.update(tid, snap)

        if snapshots:
            self.empty.grid_remove()
        else:
            self.empty.grid()

        total_down = sum(s["download_rate"] for s in snapshots)
        active_count = sum(1 for s in snapshots if s["state"] in ("Downloading", "Seeding"))
        self.status_left.configure(text="Active: %d  ·  Total: %d" % (active_count, len(snapshots)))
        self.status_right.configure(text="%s ↓" % format_rate(total_down))
        self._update_action_buttons()
        self._refresh_after_id = self.after(500, self._refresh)

    def _update_action_buttons(self):
        state = "normal"
        if not self.rows_mgr.selected_ids():
            state = "disabled"
        self.btn_pause.configure(state=state)
        self.btn_resume.configure(state=state)
        self.btn_remove.configure(state=state)

    def _pause_selected(self):
        for tid in self.rows_mgr.selected_ids():
            self.engine.pause(tid)

    def _resume_selected(self):
        for tid in self.rows_mgr.selected_ids():
            self.engine.resume(tid)

    def _toggle_selected(self):
        tid = self.rows_mgr._selected_id
        if not tid:
            return
        snap = self._last_snapshot.get(tid)
        if snap and snap["state"] == "Paused":
            self.engine.resume(tid)
        elif snap and snap["state"] == "Completed":
            return
        else:
            self.engine.pause(tid)

    def _remove_selected(self, delete=False):
        tid = self.rows_mgr._selected_id
        if not tid:
            return
        msg = "Remove this torrent from the list? Files will be kept." if not delete else "Delete this torrent AND its downloaded files?"
        if not messagebox.askyesno("Remove torrent", msg, parent=self):
            return
        self.engine.remove(tid, delete_files=delete)
        self.rows_mgr.clear_selection()

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
        self.engine.set_max_active_downloads(self.settings["max_active_downloads"])

    def _open_about(self):
        AboutDialog(self, APP_VERSION)

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