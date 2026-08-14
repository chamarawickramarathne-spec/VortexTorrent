# Vortex Torrent - Build Plan

## Goal
Full-featured Windows desktop BitTorrent downloader, v1.0.0.

## Plan (from planning phase)
1. Install Python 3.13.9 (64-bit) - libtorrent has no cp314 wheels.
2. Scaffold project (venv, folders, requirements, AGENTS files, gitignore).
3. Engine: `core/engine.py` (session, DHT, trackers, speed limits, resume data), `core/models.py`.
4. UI: `ui/main_window.py` + `ui/dialogs.py` (tkinter), `main.py`.
5. Updater: `updater.py` - GitHub releases check/download.
6. Media: `media/` logo.png + icon.ico (Pillow generation).
7. Docs: `medial_support.txt`, `AGENTS.md`, `AGENTS_PLAN.md`.
8. Build: `build.bat` -> PyInstaller exe + Inno Setup installer.
9. Git: init repo, GitHub repo `VortexTorrent`, push, v1.0.0 release.

## Progress
- [x] Python 3.13.9 64-bit installed; libtorrent 2.1.1 verified (real download test: ~12 MB/s, 59 peers).
- [x] Scaffold created (venv, folders, requirements, VERSION, .gitignore).
- [x] Engine + models written and tested end-to-end with Ubuntu 24.04 torrent.
- [x] UI + dialogs + main entry written (imports verified).
- [x] updater.py written.
- [x] media logo.png (512x512) + icon.ico (256x256) generated.
- [x] medial_support.txt, AGENTS.md, AGENTS_PLAN.md written.
- [x] Build exe + installer (build.bat + installer.iss).
- [x] Git init + GitHub repo + v1.0.0 release.
- [x] Final verification: launch app, add legal magnet, watch download.
- [x] Packaged exe verified: launches and stays running.
- [x] Updater verified against GitHub release (v1.0.0 found, installer asset resolved).

## Decisions locked
- Stack: Python 3.13.9 + libtorrent 2.1.1 + customtkinter 6.0.0 (mod 2).
- App name / repo: Vortex Torrent / VortexTorrent.
- No database (JSON settings), no sql/ folder.
- Update via GitHub releases.

## Mod 2 (v1.1.0) - Bug fix + UI redesign
- [x] Fixed `_selected_ids()` (was calling `tree.set(item, "#0")` -> TclError, broke pause/remove/delete).
- [x] Rewrote UI with customtkinter dark theme (ui/theme.py palette, header, toolbar, row cards + progress bars, context menu, keyboard shortcuts, status bar, empty state).
- [x] Added visible update feature: Help menu -> Check for Updates + About (version + repo link).
- [x] Fixed resume-data save/load (lt.bencode on alert dict; lt.read_resume_data on load).
- [x] Added save_path to snapshot() for Open Folder.
- [x] Bumped VERSION/APP_VERSION/installer.iss to 1.1.0; requirements + Pillow.
- [x] Smoke tested add/select/pause/remove/delete + real download via UI.
- [x] Rebuilt exe + installer, released v1.1.0 (updater verified).

## Mod 3 (v1.2.0) - Menu bar removed, header update button, download-only
- [x] Removed native File/Help menu bar (toolbar + shortcuts cover add/settings/exit).
- [x] Header shows version next to title; version clickable -> About dialog.
- [x] Update button added to header right (runs manual update check).
- [x] Engine forced download-only: unchoke_slots_limit=0, num_optimistic_unchoke_slots=0, active_seeds=0; pause on torrent_finished_alert; auto_managed cleared + paused cleared for non-paused adds (default flags include paused -> torrent would otherwise never start).
- [x] snapshot upload_rate uses st.upload_payload_rate (st.upload_rate reports spurious bytes in 2.1.1).
- [x] Removed Up column, status bar upload, and upload limit setting (config + dialogs + apply_speed_limits(download only)).
- [x] Bumped VERSION/APP_VERSION/installer.iss to 1.2.0.
- [x] Engine verified: real Ubuntu torrent downloads (down>0) with 0 B/s upload.
- [ ] Rebuild exe + installer, release v1.2.0.

Last updated: 2026-08-15
