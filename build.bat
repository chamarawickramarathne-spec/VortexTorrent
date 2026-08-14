@echo off
setlocal
cd /d "%~dp0"

set PYTHON=.venv\Scripts\python.exe
set PYINSTALLER=.venv\Scripts\pyinstaller.exe
set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe

if not exist "%PYTHON%" (
    echo [ERROR] venv not found. Run: py -3.13 -m venv .venv
    exit /b 1
)

echo [1/4] Checking dependencies...
"%PYTHON%" -m pip install --quiet --upgrade pip
"%PYTHON%" -m pip install --quiet -r requirements.txt
"%PYTHON%" -m pip install --quiet pyinstaller

echo [2/4] Generating media assets...
"%PYTHON%" media\generate_media.py

echo [3/4] Building exe with PyInstaller...
if exist build\VortexTorrent rmdir /s /q build\VortexTorrent
if exist dist\VortexTorrent rmdir /s /q dist\VortexTorrent
"%PYINSTALLER%" --noconfirm --clean --windowed --icon media\icon.ico --name VortexTorrent --hidden-import libtorrent main.py
if errorlevel 1 (
    echo [ERROR] PyInstaller failed.
    exit /b 1
)

echo [4/4] Building installer with Inno Setup...
if not exist "%ISCC%" goto :noiscc
"%ISCC%" installer.iss
if errorlevel 1 (
    echo [ERROR] Inno Setup failed.
    exit /b 1
)
goto :done

:noiscc
echo [WARN] ISCC.exe not found at %ISCC% - skipping installer.

:done
echo.
echo Build complete.
echo exe:       dist\VortexTorrent\VortexTorrent.exe
echo installer: installer\VortexTorrent-Setup-1.1.0.exe
endlocal
