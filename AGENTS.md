# Vortex Torrent - App Memory

Windows desktop BitTorrent downloader built with Python 3.13.9 (64-bit) / 3.12 (32-bit) + libtorrent 2.1.1 + customtkinter 6.0.0.

## App Details
- **Name**: Vortex Torrent
- **Version**: 1.8.0 (mod 9)
- **Entry point**: `main.py` (runs `ui.main_window.main`)
- **Python**: 64-bit build uses 3.13.9 (venv `.venv`); 32-bit build uses 3.12 (venv `.venv32`) - libtorrent has no cp314 wheels, do NOT move to Python 3.14
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
- Build outputs: x64 goes to `build/`/`dist/`, x86 goes to `build32/`/`dist32/`, installer to `installer/` (all gitignored).
- Combined installer (mod 9): `installer.iss` uses `ArchitecturesAllowed=x86compatible x64compatible` + `ArchitecturesInstallIn64BitMode=x64compatible`; `[Files]` installs `dist\VortexTorrent\*` when `Is64BitInstallMode` and `dist32\VortexTorrent\*` otherwise. Single `VortexTorrent-Setup.exe` asset, so updater logic is unchanged.
- x64 and x86 builds share the same `%APPDATA%\VortexTorrent` config/resume data.

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
- **mod 6 (1.5.0)**: New logo - `media/generate_media.py` rewritten to render a clean anti-aliased vortex (4x supersample, log-spiral arm, tapered stroke, gaussian glow, cyan->blue->purple->magenta gradient matching logo.jpeg, bright white-cyan core, transparent bg). Regenerated `media/logo.png` (512px) + `media/icon.ico` (multi-size). Header/bump: APP_VERSION and installer version -> 1.5.0.
- **mod 7 (1.6.0)**: 3D logo - renderer now models the spiral arm in 3D as a tilted galaxy disk: 16-deg pitch rotation, perspective projection (0.85-1.21x), depth-sorted occlusion, depth fog (near 1.0 -> far 0.45), near-side brightening, specular highlight stripe (up-left light), drop shadow, glowing core. Regenerated `media/logo.png` + `media/icon.ico`. APP_VERSION and installer version -> 1.6.0.
- **mod 8 (1.7.0)**: Custom logo - `media/generate_media.py` repurposed: the procedural 3D renderer is removed; it now only builds multi-size `media/icon.ico` (16-256px, LANCZOS) from the user-supplied `media/logo.png` (2048px RGBA vortex, added as the header logo + window/app icon) and NEVER overwrites logo.png. APP_VERSION and installer version -> 1.7.0.
- **mod 9 (1.8.0)**: 32-bit Windows support - new `.venv32` (Python 3.12-32, same `requirements.txt`; libtorrent 2.1.1 has cp312 `win32` wheels). `build.bat` now builds BOTH: x64 PyInstaller -> `dist\VortexTorrent`, x86 PyInstaller -> `dist32\VortexTorrent`. `installer.iss` is a combined dual-arch installer (`ArchitecturesAllowed=x86compatible x64compatible`, `ArchitecturesInstallIn64BitMode=x64compatible`) that installs `dist\*` when `Is64BitInstallMode` else `dist32\*`, still outputting a single `VortexTorrent-Setup.exe` so the Update feature is unchanged. APP_VERSION and installer version -> 1.8.0.

## Build Commands
- Dev run: `.venv\Scripts\python.exe main.py`
- Build: `build.bat` (both venvs check -> deps -> media -> x64 PyInstaller -> x86 PyInstaller -> ISCC combined installer)

## Rules to Remember
- Windows app -> always produce exe + installer (Inno Setup via ISCC.exe).
- Create/regenerate `medial_support.txt` after every modification.
- Update version + mod number here after every change.
- GitHub repo must contain only app files (build/, build32/, dist/, dist32/, installer/, .venv/, .venv32/ gitignored).
