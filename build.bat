@echo off
chcp 65001 >nul
REM -- UTF-8 global: keep console output sane (messages below are ASCII-only;
REM -- full-width chars in batch lines can desync cmd's parser under cp65001)
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title PolyXRD GetCIF v1.2.0 multi-edition EXE + Setup builder

echo ==========================================
echo   PolyXRD GetCIF v1.2.0 build all
echo   [1] Standard  PolyXRD-GetCIF.exe         (onefile, no 3D, trimmed Qt)
echo   [2] Plus      PolyXRD-GetCIF-Plus.exe    (onefile, 3D preview, full Qt)
echo   [3] Internal  PolyXRD-GetCIF-Internal.exe (onefile, Plus-based, NO registration)
echo   [4] Dir       dist\PolyXRD-GetCIF\       (onedir, for Setup)
echo   [5] Dir       dist\PolyXRD-GetCIF-Plus\  (onedir, for Setup)
echo   [6] Setup     PolyXRD-GetCIF-Setup.exe / -Plus-Setup.exe (Inno Setup)
echo ==========================================
echo.

cd /d "%~dp0"

set APPVER=1.3.0

REM -- Python: prefer PolyXRD venv (PySide6/matplotlib/PyInstaller ready)
set PYTHON=..\PolyXRD\venv\Scripts\python.exe
if not exist "%PYTHON%" set PYTHON=venv\Scripts\python.exe
if not exist "%PYTHON%" set PYTHON=python

echo [info] Python: %PYTHON%
"%PYTHON%" -c "import sys;print('       version:',sys.version.split()[0])"
echo.

REM -- Inno Setup compiler (optional: skip setup steps when absent)
set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=C:\Program Files\Inno Setup 6\ISCC.exe
if exist "%ISCC%" goto :iscc_ok
echo [warn] Inno Setup 6 (ISCC.exe) not found -- Setup packages will be SKIPPED.
set ISCC=
:iscc_ok

REM -- Step 1: pre-build checks (offscreen smoke + functional checks)
echo [step 1/6] smoke + functional checks...
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

REM -- Steps 2-5: PyInstaller builds
set GETCIF_VERSION=%APPVER%

echo [step 2/6] Standard build (onefile, no 3D, trimmed Qt)...
"%PYTHON%" -m PyInstaller PolyXRD-GetCIF.spec --noconfirm --clean
if errorlevel 1 (
    echo [error] Standard build failed.
    exit /b 1
)
echo.

echo [step 3/6] Plus build (onefile, 3D, full Qt)...
"%PYTHON%" -m PyInstaller PolyXRD-GetCIF-Plus.spec --noconfirm --clean
if errorlevel 1 (
    echo [error] Plus build failed.
    exit /b 1
)
echo.

echo [step 4/6] Internal build (onefile, Plus-based, no registration)...
"%PYTHON%" -m PyInstaller PolyXRD-GetCIF-Internal.spec --noconfirm --clean
if errorlevel 1 (
    echo [error] Internal build failed.
    exit /b 1
)
echo.

echo [step 5/6] onedir builds (for Setup packages)...
"%PYTHON%" -m PyInstaller PolyXRD-GetCIF-Dir.spec --noconfirm --clean
if errorlevel 1 (
    echo [error] Standard onedir build failed.
    exit /b 1
)
"%PYTHON%" -m PyInstaller PolyXRD-GetCIF-Plus-Dir.spec --noconfirm --clean
if errorlevel 1 (
    echo [error] Plus onedir build failed.
    exit /b 1
)
echo.

REM -- Step 6: Inno Setup packages
if "%ISCC%"=="" goto :skip_iscc
echo [step 6/6] Inno Setup packages...
"%ISCC%" /DAppVersion=%APPVER% /DAppFlavor= installer\getcif-setup.iss
if errorlevel 1 (
    echo [error] Standard setup build failed.
    exit /b 1
)
"%ISCC%" /DAppVersion=%APPVER% /DAppFlavor="-Plus" installer\getcif-setup.iss
if errorlevel 1 (
    echo [error] Plus setup build failed.
    exit /b 1
)
echo.
goto :artifact_check

:skip_iscc
echo [step 6/6] SKIPPED (Inno Setup not found).
echo.

:artifact_check
echo [artifact check]...
if not exist "dist\PolyXRD-GetCIF.exe" (
    echo [error] missing dist\PolyXRD-GetCIF.exe
    exit /b 1
)
if not exist "dist\PolyXRD-GetCIF-Plus.exe" (
    echo [error] missing dist\PolyXRD-GetCIF-Plus.exe
    exit /b 1
)
if not exist "dist\PolyXRD-GetCIF-Internal.exe" (
    echo [error] missing dist\PolyXRD-GetCIF-Internal.exe
    exit /b 1
)
if not exist "dist\PolyXRD-GetCIF\PolyXRD-GetCIF.exe" (
    echo [error] missing dist\PolyXRD-GetCIF\PolyXRD-GetCIF.exe
    exit /b 1
)
if not exist "dist\PolyXRD-GetCIF-Plus\PolyXRD-GetCIF-Plus.exe" (
    echo [error] missing dist\PolyXRD-GetCIF-Plus\PolyXRD-GetCIF-Plus.exe
    exit /b 1
)
for %%A in ("dist\PolyXRD-GetCIF.exe") do echo [onefile ] dist\PolyXRD-GetCIF.exe          size: %%~zA
for %%A in ("dist\PolyXRD-GetCIF-Plus.exe") do echo [onefile ] dist\PolyXRD-GetCIF-Plus.exe      size: %%~zA
for %%A in ("dist\PolyXRD-GetCIF-Internal.exe") do echo [onefile ] dist\PolyXRD-GetCIF-Internal.exe  size: %%~zA
if not "%ISCC%"=="" (
    if not exist "installer\Output\PolyXRD-GetCIF-Setup.exe" (
        echo [error] missing installer\Output\PolyXRD-GetCIF-Setup.exe
        exit /b 1
    )
    if not exist "installer\Output\PolyXRD-GetCIF-Plus-Setup.exe" (
        echo [error] missing installer\Output\PolyXRD-GetCIF-Plus-Setup.exe
        exit /b 1
    )
    for %%A in ("installer\Output\PolyXRD-GetCIF-Setup.exe") do echo [setup   ] PolyXRD-GetCIF-Setup.exe        size: %%~zA
    for %%A in ("installer\Output\PolyXRD-GetCIF-Plus-Setup.exe") do echo [setup   ] PolyXRD-GetCIF-Plus-Setup.exe    size: %%~zA
)

echo.
echo ==========================================
echo   Build complete:
echo     dist\PolyXRD-GetCIF.exe            [Standard onefile]
echo     dist\PolyXRD-GetCIF-Plus.exe       [Plus onefile]
echo     dist\PolyXRD-GetCIF-Internal.exe   [Internal onefile, no registration]
echo     dist\PolyXRD-GetCIF\               [Standard onedir]
echo     dist\PolyXRD-GetCIF-Plus\          [Plus onedir]
if not "%ISCC%"=="" echo     installer\Output\PolyXRD-GetCIF-Setup.exe       [Standard Setup]
if not "%ISCC%"=="" echo     installer\Output\PolyXRD-GetCIF-Plus-Setup.exe  [Plus Setup]
echo ==========================================
