# Vortex Torrent - Build Plan (v1.9.0, mod 10)

## Goal
Delete the hidden `.parts` part-files libtorrent leaves behind in download
folders after (selective) downloads finish, and fix hybrid-torrent priority
misalignment caused by BEP 52 pad files.

## Research
- libtorrent stores skipped-file portions of shared pieces in
  `<save_path>\.<info-hash-hex>.parts` (`part_file_dir=''` default) and never
  deletes them when redundant (upstream issues #1967/#7603).
- Python bindings 2.1.1 expose NO `delete_part_file()` / remove-flag, so the
  app must delete the file itself.
- Instrumented probes proved: the partfile is written LAZILY and libtorrent
  RECREATES it from its write-back cache after external deletion (post-pause
  flush lands ~0.4s after `torrent_finished_alert`), so one-shot deletion
  always fails -> cleanup must be retry-based.
- BEP 52 hybrids insert pad files into `file_storage`, shifting user file
  priorities onto wrong files; pads must be filtered for display and given
  priority 0 during expansion.

## Policy Decisions (user-approved)
- Always delete `.parts` once a torrent completes - even if some files were
  skipped; re-selecting later simply re-downloads.
- Full release cycle: version bump + docs + marketing + build.bat.

## Tasks

### 1. Cleanup helpers (`core/partfile.py`)
- [x] Hash hexes via `info_hashes().v1/.v2/.get_best()`.
- [x] `ready_for_cleanup`: complete AND paused/finished/seeding.
- [x] Retry queue: `queue_cleanup` + `drain_orphans` (200 tries x 50ms);
      items are NEVER dropped early (recreation race).

### 2. Pad-file mapping (`core/filemap.py`)
- [x] `visible_files` filters pads via `file_flags(i) & flag_pad_file`.
- [x] `expand_priorities` inserts priority 0 for pads.

### 3. Engine wiring (`core/engine.py`)
- [x] Queue candidate paths on save_resume_data / cache_flushed alerts and on
      remove(keep data); `_alert_loop` drains every tick; `stop()` drains
      synchronously up to 5s.
- [x] Finished torrents: pause + `save_resume_data(flush_disk_cache)`.

### 4. Test (`tests/test_partfile_cleanup.py`)
- [x] e2e vs localhost seeder: v1 selective/full + hybrid selective;
      16 checks - all pass (two consecutive runs).

### 5. Release
- [x] APP_VERSION + installer.iss -> 1.9.0.
- [x] AGENTS.md mod 10 entry.
- [x] Regenerate medial_support.txt.
- [x] build.bat (x64 + x86 exe + combined installer).
- [ ] Git commit + tag release (pending user go-ahead).

## Status
- COMPLETE - e2e test passes (2 consecutive runs); artifacts verified:
  dist\VortexTorrent.exe (x64), dist32\VortexTorrent.exe (x86),
  installer\VortexTorrent-Setup.exe (29.6 MB combined).
