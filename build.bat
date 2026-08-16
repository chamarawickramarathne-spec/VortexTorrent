@echo off
setlocal
cd /d "%~dp0"

set PYTHON=.venv\Scripts\python.exe
set PYTHON32=.venv32\Scripts\python.exe
set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe

if exist "%PYTHON%" goto :venv_ok
echo [ERROR] venv not found. Run: py -3.13 -m venv .venv
exit /b 1
:venv_ok

if exist "%PYTHON32%" goto :venv32_ok
echo [ERROR] 32-bit venv not found. Run: py -3.12-32 -m venv .venv32
exit /b 1
:venv32_ok

echo [1/5] Checking dependencies (64-bit + 32-bit)...
"%PYTHON%" -m pip install --quiet --upgrade pip
"%PYTHON%" -m pip install --quiet -r requirements.txt
"%PYTHON%" -m pip install --quiet pyinstaller
"%PYTHON32%" -m pip install --quiet --upgrade pip
"%PYTHON32%" -m pip install --quiet -r requirements.txt
"%PYTHON32%" -m pip install --quiet pyinstaller

echo [2/5] Generating media assets...
"%PYTHON%" media\generate_media.py

echo [3/5] Building 64-bit exe with PyInstaller...
if exist build\VortexTorrent rmdir /s /q build\VortexTorrent
if exist dist\VortexTorrent rmdir /s /q dist\VortexTorrent
"%PYTHON%" -m PyInstaller --noconfirm --clean --windowed --icon media\icon.ico --name VortexTorrent --hidden-import libtorrent main.py
if not errorlevel 1 goto :build64_ok
echo [ERROR] PyInstaller 64-bit build failed.
exit /b 1
:build64_ok

echo [4/5] Building 32-bit exe with PyInstaller...
if exist build32\VortexTorrent rmdir /s /q build32\VortexTorrent
if exist dist32\VortexTorrent rmdir /s /q dist32\VortexTorrent
"%PYTHON32%" -m PyInstaller --noconfirm --clean --windowed --icon media\icon.ico --name VortexTorrent --hidden-import libtorrent --distpath dist32 --workpath build32 main.py
if not errorlevel 1 goto :build32_ok
echo [ERROR] PyInstaller 32-bit build failed.
exit /b 1
:build32_ok

echo [5/5] Building installer with Inno Setup...
if not exist "%ISCC%" goto :noiscc
"%ISCC%" installer.iss
if errorlevel 1 goto :iscc_failed
goto :done

:iscc_failed
echo [ERROR] Inno Setup failed.
exit /b 1

:noiscc
echo [WARN] ISCC.exe not found at %ISCC% - skipping installer.

:done
echo.
echo Build complete.
echo exe 64-bit:  dist\VortexTorrent\VortexTorrent.exe
echo exe 32-bit:  dist32\VortexTorrent\VortexTorrent.exe
echo installer:   installer\VortexTorrent-Setup.exe (combined x86 + x64)
endlocal
