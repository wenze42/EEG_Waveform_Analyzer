@echo off
setlocal
chcp 65001 >nul
title Phone Folder Cleaner
cd /d "%~dp0"

python -c "import sys" >nul 2>nul
if errorlevel 1 goto nopython

python "%~dp0phone_cleaner.py"
echo.
pause
exit /b 0

:nopython
echo.
echo [!] Python not found.
echo     Install it from https://www.python.org/downloads/
echo     and check "Add python.exe to PATH" during installation.
echo.
pause
exit /b 1
