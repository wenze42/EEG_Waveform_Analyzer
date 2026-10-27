@echo off
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo 没有找到 Python。
    echo 请先安装：https://www.python.org/downloads/
    echo 安装时务必勾选 "Add python.exe to PATH"。
    echo.
    pause
    exit /b 1
)

if not exist "platform-tools\adb.exe" (
    if not exist "adb.exe" (
        echo.
        echo 没有找到 adb.exe。
        echo 请下载 https://dl.google.com/android/repository/platform-tools-latest-windows.zip
        echo 解压后把 platform-tools 文件夹放到本文件所在目录，再运行本脚本。
        echo.
        pause
        exit /b 1
    )
)

echo.
echo ============================================
echo   手机文件夹整理工具
echo ============================================
echo   1. 只导出并扫描（不改任何文件，推荐先做）
echo   2. 导出并按分类归档（跳过无用文件，原手机不动）
echo   3. 导出、归档，并把无用文件移入「待删除」
echo   4. 不连手机，直接扫描已有的「手机导出」目录
echo ============================================
set /p choice=请输入序号后回车（默认 1）：

if "%choice%"=="" set choice=1

if "%choice%"=="1" python phone_cleaner.py --adb
if "%choice%"=="2" python phone_cleaner.py --adb --apply --skip-junk
if "%choice%"=="3" python phone_cleaner.py --adb --apply --skip-junk --delete --yes --include-apk
if "%choice%"=="4" python phone_cleaner.py --src "手机导出"

echo.
echo 完成。报告在「清理报告」文件夹里。
pause
