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
- [ ] Build exe + installer (build.bat + installer.iss).
- [ ] Git init + GitHub repo + v1.0.0 release.
- [ ] Final verification: launch app, add legal magnet, watch download.

## Decisions locked
- Stack: Python 3.13.9 + libtorrent 2.1.1 + tkinter.
- App name / repo: Vortex Torrent / VortexTorrent.
- No database (JSON settings), no sql/ folder.
- Update via GitHub releases.

Last updated: 2026-08-15
