# Vortex Torrent - Build Plan (v1.10.0, mod 11)

## Goal
Add a max-active-downloads queue and harden the application's security
(update channel integrity, settings validation, active-slot accounting).

## Policy Decisions (user-approved via audit)
- Update channel: verify the SHA-256 checksum against the published `.sha256`
  asset (always) and apply the Authenticode policy - a PRESENT signature must
  be valid (WinVerifyTrust + publisher match), an UNSIGNED installer is
  allowed only when its bytes match the published checksum, present-but-invalid
  signatures are refused; only ever offer NEWER versions (never downgrade).
  (Policy revised from "must be signed" to "checksum required, signature
  validated when present" because releases are unsigned and strict enforcement
  would make the updater refuse the app's own releases.)
- Settings: validate/coerce all `settings.json` keys, clamp `port` to
  1024-65535 and `download_rate`/`max_active_downloads` to >= 0, back up a
  corrupt file to `settings.json.bak` instead of silent fallback.
- Queue accounting: a magnet paused while `awaiting_files=True` does NOT
  consume an active-download slot (it performs no download).

## Tasks

### 1. Max-active-downloads queue (`core/engine.py`, `core/models.py`, `core/config.py`, `ui/dialogs.py`, `ui/main_window.py`)
- [x] `max_active_downloads` setting (0 = unlimited) in defaults/UI/save.
- [x] `engine.start`/`set_max_active_downloads` enforce queue via
      `_slot_available`/`_count_active`/`_promote_next`.
- [x] `.torrent` adds pause+`queued` when full; promote on pause/remove/finish/tick.
- [x] Magnet `activate()` re-queues after file selection when full.
- [x] Manual resume/pause/resume_all always win (may exceed the limit).
- [x] `_count_active` EXCLUDES `awaiting_files` torrents.

### 2. Update channel hardening (`updater.py`, `ui/main_window.py`)
- [x] `UpdateChecker.check(current)` returns only tags NEWER than current.
- [x] `download_installer` verifies SHA-256 vs published `.sha256` asset when
      present, then applies the signature policy (signed = valid + publisher
      match; unsigned = allowed via checksum; present-but-invalid = refused).
- [x] Reuses a fresh cached installer with full re-verification.
- [x] `cleanup_stale` removes old `VortexTorrent-Setup-*.exe` copies.
- [x] UI offers only newer versions; runs the verified installer.

### 3. Settings hardening (`core/config.py`, `ui/dialogs.py`)
- [x] `load_settings` validates/coerces every key + clamps ranges.
- [x] Corrupt `settings.json` backed up to `.bak` (no silent discard).
- [x] `SettingsDialog._save` clamps port range + non-negative rate + non-empty folder.

### 4. Tests
- [x] `tests/test_active_limit.py` e2e (max_active=1 queue scenarios) - PASS.
- [x] `tests/test_partfile_cleanup.py` regression - PASS.

### 5. Release
- [x] APP_VERSION + installer.iss + VERSION -> 1.10.0.
- [x] AGENTS.md mod 11 entry.
- [x] Regenerate medial_support.txt.
- [x] build.bat (x64 + x86 exe + combined installer).
- [x] Git commit + tag v1.10.0 + GitHub release with VortexTorrent-Setup.exe.

## Status
- COMPLETE - e2e tests pass; artifacts verified: dist\VortexTorrent.exe (x64),
  dist32\VortexTorrent.exe (x86), installer\VortexTorrent-Setup.exe (combined).
