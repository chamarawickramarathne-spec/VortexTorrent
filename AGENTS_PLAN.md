# Vortex Torrent - Build Plan (v1.8.0, mod 9)

## Goal
Add 32-bit (x86) Windows support via a single combined installer while keeping
the existing Update feature unchanged.

## Research
- libtorrent 2.1.1 ships `cp312-cp312-win32` wheels, so a 32-bit build works with
  the already-installed Python 3.12-32 (`py -3.12-32`) - no new Python install needed.
- 32-bit executables must be built with a 32-bit Python (PyInstaller derives the
  arch from the interpreter), so a second venv `.venv32` is required.
- A combined installer (Inno Setup `Is64BitInstallMode` check) keeps a single
  `VortexTorrent-Setup.exe` asset -> `updater.py` and the Update button unchanged.

## Tasks

### 1. 32-bit venv
- [x] Create `.venv32` via `py -3.12-32 -m venv .venv32`.
- [x] Install `requirements.txt` + pyinstaller; verified `libtorrent 2.1.1` on 32-bit Python.

### 2. Dual-arch build
- [x] `build.bat`: check both venvs, install deps in both, x64 PyInstaller -> `dist\VortexTorrent`, x86 PyInstaller (`.venv32`) -> `dist32\VortexTorrent`, then ISCC.
- [x] `installer.iss`: `ArchitecturesAllowed=x86compatible x64compatible`, `ArchitecturesInstallIn64BitMode=x64compatible`, `[Files]` splits by `Is64BitInstallMode` (x64 -> `dist\*`, x86 -> `dist32\*`). Single `VortexTorrent-Setup.exe`, version -> 1.8.0.
- [x] `.gitignore`: add `.venv32/`, `build32/`, `dist32/`.

### 3. Versioning
- [x] Bump APP_VERSION to 1.8.0.
- [x] Update AGENTS.md (mod 9, dual-arch notes).
- [x] Regenerate medial_support.txt.
- [x] Build exe (x64 + x86) + combined installer (build.bat + ISCC).
- [x] Verify x86 exe PE machine type = 0x014c, x64 = 0x8664.
- [ ] Git commit + tag release (pending user go-ahead).

## Status
- [x] Code changes done
- [x] Build verified - x64 exe (dist\VortexTorrent, arch x64), x86 exe (dist32\VortexTorrent, arch x86), combined installer (installer\VortexTorrent-Setup.exe)
