"""Torrent row widgets: creation, selection, context menu, and folder open.

Extracted from main_window.py to keep individual modules under 300 lines.
"""

import os
import tkinter as tk

import customtkinter as ctk

from ui import theme


class TorrentRowManager:
    """Owns the scrollable row widgets for the torrent list."""

    def __init__(self, rows_frame, window):
        self.rows = rows_frame
        self.window = window
        self._row_widgets = {}
        self._selected_id = None

    def create(self, torrent_id, snap=None):
        if torrent_id in self._row_widgets:
            return
        snap = snap or {}
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
            widget.bind("<Button-1>", lambda e, tid=torrent_id: self.select(tid, e))
        row.bind("<Button-3>", lambda e, tid=torrent_id: self.show_context_menu(tid, e))
        row.bind("<Double-Button-1>", lambda e, tid=torrent_id: self.open_folder(tid))

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

    def select(self, torrent_id, event=None):
        self._selected_id = torrent_id
        for tid, w in self._row_widgets.items():
            bg = theme.ROW_SELECTED if tid == torrent_id else theme.BG
            w["row"].configure(fg_color=bg)
        self.window._update_action_buttons()

    def show_context_menu(self, torrent_id, event):
        self.select(torrent_id)
        ctx = tk.Menu(self.window, tearoff=0)
        ctx.add_command(label="Pause", command=self.window._pause_selected)
        ctx.add_command(label="Resume", command=self.window._resume_selected)
        ctx.add_separator()
        ctx.add_command(label="Remove", command=lambda: self.window._remove_selected(delete=False))
        ctx.add_command(label="Delete Files", command=lambda: self.window._remove_selected(delete=True))
        ctx.add_separator()
        ctx.add_command(label="Open Folder", command=lambda: self.open_folder(torrent_id))
        try:
            ctx.tk_popup(event.x_root, event.y_root)
        finally:
            ctx.grab_release()

    def open_folder(self, torrent_id):
        snap = self.window._last_snapshot.get(torrent_id)
        if not snap:
            return
        path = snap.get("save_path")
        if path and os.path.isdir(path):
            os.startfile(path)

    def remove(self, torrent_id):
        if torrent_id in self._row_widgets:
            self._row_widgets.pop(torrent_id)["row"].destroy()

    def clear_selection(self):
        self._selected_id = None

    def selected_ids(self):
        if not self._selected_id:
            return []
        return [self._selected_id]

    def widgets(self):
        return self._row_widgets

    def update(self, torrent_id, snap):
        w = self._row_widgets[torrent_id]
        w["name"].configure(text=snap["name"])
        w["size"].configure(text=format_size(snap["size"]))
        pct = snap["progress"] * 100
        w["pct"].configure(text="%.1f%%" % pct, text_color=theme.state_color(snap["state"]))
        w["state"].configure(text=snap["state"], text_color=theme.state_color(snap["state"]))
        w["down"].configure(text=format_rate(snap["download_rate"]))
        w["peers"].configure(text="%d/%d" % (snap["seeds"], snap["peers"]))
        w["eta"].configure(text=format_eta(snap["eta"]))
        w["progress"].set(min(1.0, snap["progress"]))


def format_size(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return "%.1f %s" % (n, unit)
        n /= 1024


def format_rate(n):
    return format_size(n) + "/s"


def format_eta(secs):
    secs = int(secs or 0)
    if secs <= 0:
        return "--:--"
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    if h:
        return "%d:%02d:%02d" % (h, m, s)
    return "%02d:%02d" % (m, s)