# Vortex Torrent - App Memory

Windows desktop BitTorrent downloader built with Python 3.13.9 + libtorrent 2.1.1 + customtkinter 6.0.0.

## App Details
- **Name**: Vortex Torrent
- **Version**: 1.4.0 (mod 5)
- **Entry point**: `main.py` (runs `ui.main_window.main`)
- **Python**: 3.13.9 64-bit (venv `.venv`) - libtorrent has no cp314 wheels, do NOT move to Python 3.14
- **GUI**: customtkinter 6.0.0 (dark theme) over tkinter
- **Engine**: libtorrent 2.1.1 via `core/engine.py`
- **Update source**: GitHub releases (owner `chamarawickramarathne-spec`, repo `VortexTorrent`)

## Structure
- `main.py` - entry point
- `core/engine.py` - libtorrent session wrapper (threaded alert loop, DHT, PEX, trackers, speed limits, resume data)
- `core/models.py` - TorrentEntry model
- `core/config.py` - settings load/save (JSON in `%APPDATA%\VortexTorrent\settings.json`), default download dir
- `ui/main_window.py` - main window (CTk): header (title + version + Update button), toolbar, torrent rows w/ progress bars, context menu, keyboard shortcuts, update prompts
- `ui/dialogs.py` - CTk magnet/settings/about dialogs + FileSelectDialog (checkbox list, Select All/None, returns 1/0 priorities). MagnetDialog auto-pastes a `magnet:` link from the clipboard on open.
- `ui/theme.py` - shared dark color palette + font helpers
- `updater.py` - GitHub release check/download
- `media/` - logo.png, icon.ico, generate_media.py
- `requirements.txt` - libtorrent==2.1.1, customtkinter==6.0.0, Pillow>=10.0

## Download-Only Mode (mod 3)- App NEVER uploads: session settings force `unchoke_slots_limit=0`, `num_optimistic_unchoke_slots=0`, `active_seeds=0`. Do NOT raise these.
- Torrents are added with `auto_managed` cleared (default flags include `paused`, so `paused` must be cleared too for non-paused adds — otherwise torrent never starts).
- On `torrent_finished_alert` the torrent is paused (no seeding).
- `snapshot()` reports `upload_rate` from `st.upload_payload_rate` (plain `st.upload_rate` reports spurious non-payload bytes in 2.1.1).
- Settings dialog has NO upload limit; `apply_speed_limits(download_rate)` only.

## File Selection (mod 5)
- `.torrent` add: file list read via `engine.file_list_from_file(path)` BEFORE adding; FileSelectDialog shown (skipped for single-file); priorities applied at add time via `params.file_priorities` so skipped files never download. Cancel = do not add. Priorities ALSO resynced after add via `set_file_priorities` (idempotent safety net).
- Magnet add: torrent added immediately (must stay unpaused or metadata is never fetched). On `metadata_received_alert` the engine appends the id to a thread-safe `_files_ready` queue AND calls `alert.handle.pause()` immediately, so NOTHING downloads until the user confirms selection. UI drains the queue in `_refresh` (main thread), opens FileSelectDialog, then applies priorities via `handle.prioritize_files()` and resumes the torrent. Cancel = keep all files (still resumes). Single-file magnet = skip dialog but resume.
- `engine.file_list(torrent_id)` returns `None` until metadata arrives; uses `handle.torrent_file().files()`.
- `params.file_priorities` and `handle.prioritize_files` both verified working in libtorrent 2.1.1. `handle.file_priorities()`/`prioritize_files` are deprecated warnings but functional.
- Do NOT touch Tk from the engine alert thread; UI polls `take_files_ready()` instead of a callback.

## Key Decisions
- libtorrent 2.x API: `lt.add_torrent_params()`, `session.add_torrent()`, `lt.add_magnet_uri()`. PEX/LSD are per-torrent flags, NOT session settings (`enable_pex` throws KeyError).
- Resume data: `save_resume_data_alert.resume_data` is a **dict** in 2.1.1 -> serialize with `lt.bencode()`. Loading uses `lt.read_resume_data(bytes)` which returns an `add_torrent_params` (do NOT assign bytes to `params.resume_data`).
- No database needed; config is JSON. No `sql/` folder.
- Resume data saved to `%APPDATA%\VortexTorrent\resume\*.fastresume` on pause/remove/exit.
- Build outputs go to `build/`, `dist/`, `installer/` (gitignored).

## UI/UX Notes
- Dark theme colors in `ui/theme.py` (BG #12141c, PANEL #1c2030, ACCENT #7c5cff, CYAN #22d3ee).
- Torrents are widget rows in a `CTkScrollableFrame` (NOT ttk.Treeview). Row model: name/size/%/status/down/seeds/ETA + full-width `CTkProgressBar`. No "Up" column (download-only).
- Selection tracked via `self._selected_id`; action buttons disabled until a row is selected.
- Controls: toolbar buttons, right-click context menu, Ctrl+O/Ctrl+M/Del/Space, double-click opens folder.
- NO menu bar (mod 3): header shows title + clickable version (opens About) + Update button on the right.
- `_selected_ids()` must NOT call `tree.set(item, "#0")` (raises TclError on hidden #0 column).

## Modification History
- **mod 1 (1.0.0)**: Initial release - engine, UI (ttk), updater, media, installer (PyInstaller + Inno Setup).
- **mod 2 (1.1.0)**: Fixed pause/resume/remove/delete bug (`_selected_ids`), new modern dark customtkinter UI, torrent rows w/ progress bars, context menu, keyboard shortcuts, visible update feature (Help menu + About), resume-data bencode fix, `save_path` in snapshot.
- **mod 3 (1.2.0)**: Removed menu bar; header now shows version next to title (clickable -> About) + Update button; forced download-only mode (no upload/seeding: unchoke_slots_limit=0, num_optimistic_unchoke_slots=0, active_seeds=0, pause on finish); removed Up column + status bar upload; removed upload limit from Settings; snapshot upload_rate uses upload_payload_rate.
- **mod 4 (1.3.0)**: MagnetDialog auto-pastes a `magnet:` link from clipboard on open; added file selection - `.torrent` shows FileSelectDialog before add (priorities via `params.file_priorities`), magnet shows FileSelectDialog automatically when metadata arrives (priorities via `handle.prioritize_files`); single-file torrents skip the dialog; engine gains `file_list_from_file`, `file_list`, `set_file_priorities`, `take_files_ready`.
- **mod 5 (1.4.0)**: Guarantee only selected files download - engine pauses the handle on `metadata_received_alert` so NOTHING downloads until the user confirms; UI resumes the magnet after applying priorities (and on Cancel/single-file magnet); `.torrent` add resyncs priorities after add as a safety net. New "Completed" status: snapshot shows "Completed" (green) instead of "Paused" when selected bytes finish; Space-toggle ignores Completed torrents.

## Build Commands
- Dev run: `.venv\Scripts\python.exe main.py`
- Build: `build.bat` (venv check -> deps -> PyInstaller -> ISCC installer)

## Rules to Remember
- Windows app -> always produce exe + installer (Inno Setup via ISCC.exe).
- Create/regenerate `medial_support.txt` after every modification.
- Update version + mod number here after every change.
- GitHub repo must contain only app files (build/, dist/, installer/, .venv/ gitignored).
