@echo off
chcp 65001 >nul
REM -- UTF-8 global: keep console output sane (messages below are ASCII-only;
REM -- full-width chars in batch lines can desync cmd's parser under cp65001)
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title PolyXRD GetCIF v1.0.0 dual-edition EXE builder

echo ==========================================
echo   PolyXRD GetCIF v1.0.0 dual-edition build
echo   [1] Standard  PolyXRD-GetCIF.exe       (no 3D, trimmed Qt, lightweight)
echo   [2] Plus      PolyXRD-GetCIF-Plus.exe  (3D preview, full Qt)
echo ==========================================
echo.

cd /d "%~dp0"

set APPVER=1.0.0

REM -- Python: prefer PolyXRD venv (PySide6/matplotlib/PyInstaller ready)
set PYTHON=..\PolyXRD\venv\Scripts\python.exe
if not exist "%PYTHON%" set PYTHON=venv\Scripts\python.exe
if not exist "%PYTHON%" set PYTHON=python

echo [info] Python: %PYTHON%
"%PYTHON%" -c "import sys;print('       version:',sys.version.split()[0])"
echo.

REM -- Step 1: pre-build checks (offscreen smoke + functional checks)
echo [step 1/4] smoke + functional checks...
set QT_QPA_PLATFORM=offscreen
set PYTHONPATH=src
"%PYTHON%" -m getcif.gui --smoke --no-splash
if errorlevel 1 (
    echo [error] smoke check failed, abort.
    exit /b 1
)
"%PYTHON%" tests\run_checks.py
if errorlevel 1 (
    echo [error] functional check failed, abort.
    exit /b 1
)
set PYTHONPATH=
set QT_QPA_PLATFORM=
echo.

REM -- Step 2/3: PyInstaller builds
set GETCIF_VERSION=%APPVER%

echo [step 2/4] Standard build (no 3D, trimmed Qt)...
"%PYTHON%" -m PyInstaller PolyXRD-GetCIF.spec --noconfirm --clean
if errorlevel 1 (
    echo [error] Standard build failed.
    exit /b 1
)
echo.

echo [step 3/4] Plus build (3D, full Qt)...
"%PYTHON%" -m PyInstaller PolyXRD-GetCIF-Plus.spec --noconfirm --clean
if errorlevel 1 (
    echo [error] Plus build failed.
    exit /b 1
)
echo.

REM -- Step 4: artifact check
echo [step 4/4] artifact check...
if not exist "dist\PolyXRD-GetCIF.exe" (
    echo [error] missing dist\PolyXRD-GetCIF.exe
    exit /b 1
)
if not exist "dist\PolyXRD-GetCIF-Plus.exe" (
    echo [error] missing dist\PolyXRD-GetCIF-Plus.exe
    exit /b 1
)
for %%A in ("dist\PolyXRD-GetCIF.exe") do echo [Standard] dist\PolyXRD-GetCIF.exe       size: %%~zA bytes
for %%A in ("dist\PolyXRD-GetCIF-Plus.exe") do echo [Plus]     dist\PolyXRD-GetCIF-Plus.exe  size: %%~zA bytes

echo.
echo ==========================================
echo   Build complete:
echo     dist\PolyXRD-GetCIF.exe       [Standard]
echo     dist\PolyXRD-GetCIF-Plus.exe  [Plus]
echo ==========================================
