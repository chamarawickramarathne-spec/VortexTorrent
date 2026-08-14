# Vortex Torrent - Build Plan (v1.4.0, mod 5)

## Goal
Ensure a torrent downloads ONLY the inner files selected in the file-selection
dialog, into the configured download folder, and show "Completed" (not "Paused")
when the selected files finish downloading.

## Tasks

### 1. Magnet race fix - nothing downloads until selection confirmed
- [x] `core/engine.py`: on `metadata_received_alert`, pause the handle immediately.
- [x] `ui/main_window.py`: after dialog OK -> apply priorities + resume; on Cancel -> resume.
- [x] `ui/main_window.py`: single-file magnet -> skip dialog but resume.
- [x] `ui/main_window.py`: .torrent add -> resync priorities via `set_file_priorities` after add.

### 2. "Completed" status
- [x] `core/engine.py` `snapshot()`: show "Completed" when selected bytes fully downloaded.
- [x] `ui/theme.py`: add "Completed" color (SUCCESS).
- [x] `ui/main_window.py` `_toggle_selected()`: ignore Space on "Completed".

### 3. Versioning / build
- [x] Bump APP_VERSION to 1.4.0.
- [x] Update AGENTS.md (mod 5).
- [x] Regenerate medial_support.txt.
- [x] Build exe + installer (build.bat + ISCC). Installer renamed to version-free `VortexTorrent-Setup.exe`; old installers removed.
- [ ] Git commit + tag release (pending user go-ahead).

## Status
- [x] All code changes done
- [x] Build verified (exe + installer produced)
