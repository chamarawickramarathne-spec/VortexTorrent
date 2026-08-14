# Vortex Torrent - App Memory

Windows desktop BitTorrent downloader built with Python 3.13.9 + libtorrent 2.1.1 + tkinter.

## App Details
- **Name**: Vortex Torrent
- **Version**: 1.0.0 (mod 1)
- **Entry point**: `main.py` (runs `ui.main_window.main`)
- **Python**: 3.13.9 64-bit (venv `.venv`) - libtorrent has no cp314 wheels, do NOT move to Python 3.14
- **GUI**: tkinter / ttk
- **Engine**: libtorrent 2.1.1 via `core/engine.py`
- **Update source**: GitHub releases (owner `chamarawickramarathne-spec`, repo `VortexTorrent`)

## Structure
- `main.py` - entry point
- `core/engine.py` - libtorrent session wrapper (threaded alert loop, DHT, PEX, trackers, speed limits, resume data)
- `core/models.py` - TorrentEntry model
- `core/config.py` - settings load/save (JSON in `%APPDATA%\VortexTorrent\settings.json`), default download dir
- `ui/main_window.py` - main window, torrent table, toolbar, status bar, update prompt
- `ui/dialogs.py` - magnet add + settings dialogs
- `updater.py` - GitHub release check/download
- `media/` - logo.png, icon.ico, generate_media.py
- `requirements.txt` - libtorrent==2.1.1 (+ Pillow for media generation only)

## Key Decisions
- libtorrent 2.x API: `lt.add_torrent_params()`, `session.add_torrent()`, `lt.add_magnet_uri()`. PEX/LSD are per-torrent flags, NOT session settings (`enable_pex` throws KeyError).
- No database needed in v1.0.0; config is JSON. No `sql/` folder.
- Resume data saved to `%APPDATA%\VortexTorrent\resume\*.fastresume` on pause/remove/exit.
- Build outputs go to `build/` and `dist/` (gitignored).

## Modification History
- **mod 1 (1.0.0)**: Initial release - engine, UI, updater, media, installer (PyInstaller + Inno Setup).

## Build Commands
- Dev run: `.venv\Scripts\python.exe main.py`
- Build: `build.bat` (venv check -> deps -> PyInstaller -> ISCC installer)

## Rules to Remember
- Windows app -> always produce exe + installer (Inno Setup via ISCC.exe).
- Create/regenerate `medial_support.txt` after every modification.
- Update version + mod number here after every change.
- GitHub repo must contain only app files (build/, dist/, .venv/ gitignored).
