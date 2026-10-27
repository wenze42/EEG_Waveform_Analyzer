@echo off
setlocal
chcp 65001 >nul
title Phone Folder Cleaner
cd /d "%~dp0"

set "PYC="

python -c "import sys" >nul 2>nul
if not errorlevel 1 set PYC=python
if defined PYC goto run

py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 set PYC=py -3
if defined PYC goto run

for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" set PYC="%%D\python.exe"
if defined PYC goto run

for /d %%D in ("C:\Python3*") do if exist "%%D\python.exe" set PYC="%%D\python.exe"
if defined PYC goto run

goto nopython

:run
call %PYC% "%~dp0phone_cleaner.py"
echo.
pause
exit /b 0

:nopython
echo.
echo [!] Python not found on this computer.
echo.
echo Option 1 - one command in PowerShell:
echo     winget install -e --id Python.Python.3.12
echo.
echo Option 2 - download installer:
echo     https://www.python.org/downloads/
echo     IMPORTANT: tick "Add python.exe to PATH" on the first screen.
echo.
echo After installing, close this window and double-click this file again.
echo.
pause
exit /b 1
