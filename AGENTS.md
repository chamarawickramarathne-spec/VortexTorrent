# Vortex Torrent - App Memory

Windows desktop BitTorrent downloader built with Python 3.13.9 (64-bit) / 3.12 (32-bit) + libtorrent 2.1.1 + customtkinter 6.0.0.

## App Details
- **Name**: Vortex Torrent
- **Version**: 1.11.0 (mod 12)
- **Entry point**: `main.py` (runs `MainWindow.mainloop()` directly)
- **Python**: 64-bit build uses 3.13.9 (venv `.venv`); 32-bit build uses 3.12 (venv `.venv32`) - libtorrent has no cp314 wheels, do NOT move to Python 3.14
- **GUI**: customtkinter 6.0.0 (dark theme) over tkinter
- **Engine**: libtorrent 2.1.1 via `core/engine.py`
- **Update source**: GitHub releases (owner `chamarawickramarathne-spec`, repo `VortexTorrent`)

## Structure
- `main.py` - entry point (creates MainWindow, runs mainloop)
- `core/engine.py` - libtorrent session wrapper (threaded alert loop, DHT, PEX, trackers, speed limits, torrent lifecycle)
- `core/queue.py` - active-download queue management (count_active, slot_available, promote_next, STATE_NAMES)
- `core/torrent_ops.py` - snapshot building, resume-data persistence, ETA calculation (extracted from engine.py)
- `core/models.py` - TorrentEntry model
- `core/partfile.py` - `.parts` part-file cleanup helpers (hash hexes, readiness checks, retry queue)
- `core/filemap.py` - pad-file-aware file listing + priority expansion (BEP 52 hybrids)
- `core/config.py` - settings load/save (JSON in `%APPDATA%\VortexTorrent\settings.json`), default download dir, validated/clamped load + corrupt-file backup, UNC path rejection
- `ui/main_window.py` - main window (CTk): header, toolbar, torrent table, statusbar, delegates row/update logic
- `ui/torrent_rows.py` - TorrentRowManager: row creation, selection, context menu, folder open, format helpers
- `ui/update_flow.py` - UpdateFlow: background update check, manual check, offer dialog, download+install
- `ui/dialogs.py` - CTk magnet/settings/about dialogs + FileSelectDialog (checkbox list, Select All/None, returns 1/0 priorities). MagnetDialog auto-pastes a `magnet:` link from the clipboard on open.
- `ui/theme.py` - shared dark color palette + font helpers
- `updater.py` - GitHub release check/download with SHA-256 checksum verification (published `.sha256` asset) + Authenticode signature policy (a PRESENT signature must be valid + publisher match; unsigned allowed so unsigned releases stay installable; present-but-invalid refused) + newer-only guard (never downgrades), cached-installer reuse with re-verification, stale installer cleanup, hardened PowerShell escaping
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
- **mod 10 (1.9.0)**: `.parts` leftover cleanup - libtorrent stores skipped-file portions of shared pieces in `<save_path>\.<info-hash-hex>.parts` and NEVER deletes them. New `core/partfile.py` (hash hexes via `info_hashes().v1/.v2/.get_best()`, completeness/settled checks) + `core/filemap.py`. CRITICAL lesson verified by instrumentation: the partfile is written LAZILY and libtorrent RECREATES it from its write-back cache after external deletion (post-pause flush lands ~0.4s later), so ONE-SHOT deletion always fails; cleanup is therefore RETRY-BASED - engine queues candidate paths on save_resume_data/cache_flushed alerts and on remove(keep data), and `_alert_loop` drains the queue every tick (`MAX_ORPHAN_TRIES=200` x 50ms); `stop()` drains synchronously up to 5s. Cleanup only fires when complete AND paused/finished/seeding - partial downloads keep their .parts (needed for resume); Vortex never lets users re-select files on completed torrents so deletion cannot corrupt anything. Fixed pre-existing pad-file bug: BEP 52 hybrids insert pad files into file_storage shifting user priorities onto wrong files; `filemap.visible_files` filters pads (`file_flags(i) & flag_pad_file`) for display and `expand_priorities` inserts priority 0 for pads before `file_priorities`/`prioritize_files`. New e2e test `tests/test_partfile_cleanup.py` (3 torrents vs localhost seeder: v1 selective/full + hybrid selective; 16 checks, all pass). APP_VERSION and installer version -> 1.9.0.
- **mod 11 (1.10.0)**: Max-active-downloads queue + security hardening. (a) Active-downloads setting: `max_active_downloads` (0 = unlimited) added to settings/UI; `engine.start`/`set_max_active_downloads` enforce a queue - new `.torrent` adds are paused+`queued` when full, `_promote_next` resumes the first queued once a slot frees (on pause/remove/finish/promote-tick), `activate()` re-queues a magnet after file selection when full, manual resume/pause/resume_all always win (may exceed the limit). Snapshot reports "Queued". (b) `_count_active` now EXCLUDES torrents with `awaiting_files=True` (a magnet paused awaiting selection performs no download and no longer occupies a slot). (c) Update channel hardening in `updater.py`: `UpdateChecker.check(current)` returns only NEWER tags (never downgrades); `download_installer` verifies SHA-256 against a published `.sha256` companion asset when present AND applies the Authenticode signature policy - a signature that IS present must pass WinVerifyTrust (chain vs trusted root store) + signing-cert publisher match (`EXPECTED_PUBLISHER`), while an UNSIGNED installer is still allowed only when its bytes match the published checksum (projects without a code-signing certificate must stay installable; present-but-invalid/tampered signatures are always refused); reuses a fresh cached installer with full re-verification; `cleanup_stale` removes old `VortexTorrent-Setup-*.exe` copies. (d) Settings hardening in `core/config.py`: `load_settings` now validates/coerces every key, clamps `port` to 1024-65535 and `download_rate`/`max_active_downloads` to >=0, and backs up a corrupt `settings.json` to `settings.json.bak` instead of silently discarding; `SettingsDialog._save` clamps port range + non-negative rate + non-empty folder. New e2e test `tests/test_active_limit.py` (max_active=1: add->paused-queued, pause promotes, magnet re-queued when full, manual resume override, remove promotes). APP_VERSION, installer version, VERSION -> 1.10.0.
- **mod 12 (1.11.0)**: Security audit + code quality refactors. (a) Security: hardened PowerShell escaping in `updater.py._signature_status()` - new `_ps_escape()` function escapes single quotes AND backticks to prevent command injection via installer paths. Added UNC path rejection in `core/config.py._coerce()` and `ui/dialogs.py._save()` - download directories are normalized via `os.path.realpath()` and UNC paths (`\\server\share`) are rejected. Added `settings.json.bak` to `.gitignore`. (b) Bug fixes: simplified redundant `and not entry.awaiting_files` condition in `_count_active` (line 279 already handles this case); added docstring to `cleanup_stale` explaining it's a backward-compatibility helper; fixed refactor regression where `self.update_flow` was instantiated AFTER `_build_header()` referenced it (crash on startup "can't invoke update_flow", caught by frozen-exe smoke test, fixed by creating UpdateFlow right after `app_data_dir`). (c) Code quality: split `core/engine.py` (was 403 lines) into 3 modules - `core/engine.py` (299 lines, session lifecycle + alert loop + torrent ops), `core/queue.py` (63 lines, count_active/slot_available/promote_next/STATE_NAMES), `core/torrent_ops.py` (88 lines, snapshot/eta/persist_resume/save_all_resume_data). Split `ui/main_window.py` (was 478 lines) into 3 modules - `ui/main_window.py` (298 lines, window frame + layout + refresh loop), `ui/torrent_rows.py` (148 lines, TorrentRowManager + format helpers), `ui/update_flow.py` (67 lines, UpdateFlow class). Moved `main()` from `ui/main_window.py` to `main.py`. All source files now under 300 lines. Both e2e tests pass (test_active_limit.py + test_partfile_cleanup.py); both frozen exes smoke-tested (x64 and x86 both launch and stay running). APP_VERSION, installer version, VERSION -> 1.11.0.

## Build Commands
- Dev run: `.venv\Scripts\python.exe main.py`
- Build: `build.bat` (both venvs check -> deps -> media -> x64 PyInstaller -> x86 PyInstaller -> ISCC combined installer)

## Rules to Remember
- Windows app -> always produce exe + installer (Inno Setup via ISCC.exe).
- Create/regenerate `medial_support.txt` after every modification.
- Update version + mod number here after every change.
- GitHub repo must contain only app files (build/, build32/, dist/, dist32/, installer/, .venv/, .venv32/ gitignored).
