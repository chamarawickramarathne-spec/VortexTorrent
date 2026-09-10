# Vortex Torrent - Build Plan (v1.11.0, mod 12)

## Goal
Security audit of the entire application plus code-quality refactors to
bring every source file under 300 lines (mod 11 left `core/engine.py` at
403 lines and `ui/main_window.py` at 478 lines).

## Audit Findings (user-approved for full implementation)

| ID | Type | Finding | Fix |
|----|------|---------|-----|
| SECURITY-1 | Security | PowerShell command injection risk in `updater._signature_status` (only single-quote escaping) | New `_ps_escape()` escapes single quotes AND backticks |
| SECURITY-5 | Security | `settings.json.bak` not gitignored | Added to `.gitignore` |
| SECURITY-2 | Security | Download dir not normalized; UNC paths allowed | `realpath()` normalize + UNC rejection in `config._coerce` and `SettingsDialog._save` |
| BUG-1 | Bug | Redundant `and not entry.awaiting_files` in `_count_active` | Simplified to `if st.paused:` |
| BUG-2 | Bug | `cleanup_stale` undocumented dead code | Docstring clarifying backward-compat purpose |
| BLOCK-1 | Quality | `core/engine.py` 403 lines | Split into engine.py (299) + queue.py (63) + torrent_ops.py (88) |
| BLOCK-2 | Quality | `ui/main_window.py` 478 lines | Split into main_window.py (298) + torrent_rows.py (148) + update_flow.py (67) |

Skipped as already-mitigated/acceptable: settings integrity (validated on load),
resume-data verification (libtorrent rejects malformed), certificate pinning
(system trust store standard), 0.0.0.0 listener (standard for BT clients).

## Tasks

### 1. Security fixes (`updater.py`, `.gitignore`, `core/config.py`, `ui/dialogs.py`)
- [x] `_ps_escape()` in `updater.py` - escapes `'` and backtick as PowerShell
      single-quoted-literal safety.
- [x] `settings.json.bak` added to `.gitignore`.
- [x] `core/config.py._coerce()` normalizes with `os.path.realpath()` and
      rejects UNC paths (`\\server\share`).
- [x] `ui/dialogs.py SettingsDialog._save()` same UNC rejection at input point.

### 2. Bug fixes (`core/engine.py`, `updater.py`)
- [x] `_count_active` simplified (remove redundant `and not entry.awaiting_files`).
- [x] `cleanup_stale` docstring documents backward-compat role.

### 3. Refactors (line-count limits)
- [x] `core/engine.py` 403 -> 299 lines: session lifecycle + alert loop +
      torrent ops (+ remove/snapshot/resume delegated).
- [x] NEW `core/queue.py` (63 lines): `count_active`, `slot_available`,
      `promote_next`, `STATE_NAMES`.
- [x] NEW `core/torrent_ops.py` (88 lines): `snapshot`, `eta`,
      `persist_resume`, `save_all_resume_data`.
- [x] `ui/main_window.py` 478 -> 298 lines: window frame + layout + refresh loop.
- [x] NEW `ui/torrent_rows.py` (148 lines): `TorrentRowManager` + format helpers.
- [x] NEW `ui/update_flow.py` (67 lines): `UpdateFlow` (check/offer/download/install).
- [x] `main()` moved from `ui/main_window.py` to `main.py`.

### 4. Tests
- [x] `tests/test_active_limit.py` e2e - PASS (11/11).
- [x] `tests/test_partfile_cleanup.py` e2e - PASS (16/16).
- [x] All modules import + `py_compile` OK.

### 5. Release
- [x] APP_VERSION + installer.iss + VERSION -> 1.11.0.
- [x] AGENTS.md mod 12 entry.
- [x] Regenerate medial_support.txt.

## Status
- CODE COMPLETE - all audit items implemented, e2e tests pass.
- Remaining (uncommitted): build.bat (x64 + x86 exe + combined installer),
  Git commit + tag v1.11.0 + GitHub release with VortexTorrent-Setup.exe.