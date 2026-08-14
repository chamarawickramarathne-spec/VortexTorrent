# Vortex Torrent - App Memory

Windows desktop BitTorrent downloader built with Python 3.13.9 + libtorrent 2.1.1 + customtkinter 6.0.0.

## App Details
- **Name**: Vortex Torrent
- **Version**: 1.1.0 (mod 2)
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
- `ui/main_window.py` - main window (CTk): header, toolbar, torrent rows w/ progress bars, context menu, keyboard shortcuts, Help menu, update prompts
- `ui/dialogs.py` - CTk magnet/settings/about dialogs
- `ui/theme.py` - shared dark color palette + font helpers
- `updater.py` - GitHub release check/download
- `media/` - logo.png, icon.ico, generate_media.py
- `requirements.txt` - libtorrent==2.1.1, customtkinter==6.0.0, Pillow>=10.0

## Key Decisions
- libtorrent 2.x API: `lt.add_torrent_params()`, `session.add_torrent()`, `lt.add_magnet_uri()`. PEX/LSD are per-torrent flags, NOT session settings (`enable_pex` throws KeyError).
- Resume data: `save_resume_data_alert.resume_data` is a **dict** in 2.1.1 -> serialize with `lt.bencode()`. Loading uses `lt.read_resume_data(bytes)` which returns an `add_torrent_params` (do NOT assign bytes to `params.resume_data`).
- No database needed; config is JSON. No `sql/` folder.
- Resume data saved to `%APPDATA%\VortexTorrent\resume\*.fastresume` on pause/remove/exit.
- Build outputs go to `build/`, `dist/`, `installer/` (gitignored).

## UI/UX Notes (mod 2)
- Dark theme colors in `ui/theme.py` (BG #12141c, PANEL #1c2030, ACCENT #7c5cff, CYAN #22d3ee).
- Torrents are widget rows in a `CTkScrollableFrame` (NOT ttk.Treeview). Row model: name/size/%/status/down/up/seeds/ETA + full-width `CTkProgressBar`.
- Selection tracked via `self._selected_id`; action buttons disabled until a row is selected.
- Controls: toolbar buttons, right-click context menu, Ctrl+O/Ctrl+M/Del/Space, double-click opens folder.
- Menus are native `tk.Menu` attached to the CTk window (File + Help). Help -> Check for Updates / About.
- `_selected_ids()` must NOT call `tree.set(item, "#0")` (raises TclError on hidden #0 column).

## Modification History
- **mod 1 (1.0.0)**: Initial release - engine, UI (ttk), updater, media, installer (PyInstaller + Inno Setup).
- **mod 2 (1.1.0)**: Fixed pause/resume/remove/delete bug (`_selected_ids`), new modern dark customtkinter UI, torrent rows w/ progress bars, context menu, keyboard shortcuts, visible update feature (Help menu + About), resume-data bencode fix, `save_path` in snapshot.

## Build Commands
- Dev run: `.venv\Scripts\python.exe main.py`
- Build: `build.bat` (venv check -> deps -> PyInstaller -> ISCC installer)

## Rules to Remember
- Windows app -> always produce exe + installer (Inno Setup via ISCC.exe).
- Create/regenerate `medial_support.txt` after every modification.
- Update version + mod number here after every change.
- GitHub repo must contain only app files (build/, dist/, installer/, .venv/ gitignored).
