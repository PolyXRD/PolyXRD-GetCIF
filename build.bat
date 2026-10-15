@echo off
chcp 65001 >nul
REM -- UTF-8 全局：中文不乱码
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title PolyXRD GetCIF v1.0.0 单文件 EXE 构建器

echo ========================================
echo   PolyXRD GetCIF v1.0.0
echo   打包为单文件 EXE (onefile)
echo ========================================
echo.

cd /d "%~dp0"

set APPVER=1.0.0

REM ── Python 定位：优先 PolyXRD 的 venv（PySide6/matplotlib/PyInstaller 齐备）──
set PYTHON=..\PolyXRD\venv\Scripts\python.exe
if not exist "%PYTHON%" set PYTHON=venv\Scripts\python.exe
if not exist "%PYTHON%" set PYTHON=python

echo [信息] 使用 Python: %PYTHON%
"%PYTHON%" -c "import sys;print('      版本:',sys.version.split()[0])"
echo.

REM ── 步骤 1：构建前自检（离屏冒烟）──
echo [步骤 1/3] 冒烟自检...
set QT_QPA_PLATFORM=offscreen
set PYTHONPATH=src
"%PYTHON%" -m getcif.gui --smoke --no-splash
if errorlevel 1 (
    echo [错误] 冒烟自检失败，中止构建。
    exit /b 1
)
set PYTHONPATH=
set QT_QPA_PLATFORM=
echo.

REM ── 步骤 2：PyInstaller 打包 ──
echo [步骤 2/3] PyInstaller 打包（onefile）...
set GETCIF_VERSION=%APPVER%
"%PYTHON%" -m PyInstaller PolyXRD-GetCIF.spec --noconfirm --clean
if errorlevel 1 (
    echo [错误] 打包失败。
    exit /b 1
)
echo.

REM ── 步骤 3：产物自检 ──
echo [步骤 3/3] 产物自检...
if not exist "dist\PolyXRD-GetCIF.exe" (
    echo [错误] 未找到 dist\PolyXRD-GetCIF.exe
    exit /b 1
)
for %%A in ("dist\PolyXRD-GetCIF.exe") do echo [产物] dist\PolyXRD-GetCIF.exe  大小: %%~zA 字节

echo.
echo ========================================
echo   构建完成: dist\PolyXRD-GetCIF.exe
echo ========================================
