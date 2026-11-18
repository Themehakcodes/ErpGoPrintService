@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo   KCSM Print Service — 1-Click Windows Setup
echo ========================================================
echo.

set "TARGET_DIR=%LOCALAPPDATA%\Programs\KCSM Print Service"
set "SOURCE_DIR=%~dp0"

echo [1/4] Preparing installation directory...
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"

echo [2/4] Copying application files to:
echo       %TARGET_DIR%

copy /Y "%SOURCE_DIR%dist\ErpGoPrintService.exe" "%TARGET_DIR%\ErpGoPrintService.exe" >nul
if not exist "%TARGET_DIR%\config.json" (
    if exist "%SOURCE_DIR%config.json" (
        copy /Y "%SOURCE_DIR%config.json" "%TARGET_DIR%\config.json" >nul
    )
)

echo [3/4] Creating Desktop and Start Menu Shortcuts...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$WshShell = New-Object -ComObject WScript.Shell; " ^
    "$DesktopPath = [System.Environment]::GetFolderPath('Desktop'); " ^
    "$DesktopShortcut = $WshShell.CreateShortcut(\"$DesktopPath\KCSM Print Service.lnk\"); " ^
    "$DesktopShortcut.TargetPath = \"%TARGET_DIR%\ErpGoPrintService.exe\"; " ^
    "$DesktopShortcut.WorkingDirectory = \"%TARGET_DIR%\"; " ^
    "$DesktopShortcut.IconLocation = \"%TARGET_DIR%\ErpGoPrintService.exe,0\"; " ^
    "$DesktopShortcut.Description = \"KCSM Print Service Desktop Agent\"; " ^
    "$DesktopShortcut.Save(); " ^
    "$StartMenu = [System.Environment]::GetFolderPath('StartMenu') + '\Programs'; " ^
    "$MenuShortcut = $WshShell.CreateShortcut(\"$StartMenu\KCSM Print Service.lnk\"); " ^
    "$MenuShortcut.TargetPath = \"%TARGET_DIR%\ErpGoPrintService.exe\"; " ^
    "$MenuShortcut.WorkingDirectory = \"%TARGET_DIR%\"; " ^
    "$MenuShortcut.IconLocation = \"%TARGET_DIR%\ErpGoPrintService.exe,0\"; " ^
    "$MenuShortcut.Description = \"KCSM Print Service Desktop Agent\"; " ^
    "$MenuShortcut.Save(); "

echo [4/4] Registering Windows Auto-Start upon Boot...
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "KCSMPrintService" /t REG_SZ /d "\"%TARGET_DIR%\ErpGoPrintService.exe\"" /f >nul

echo.
echo ========================================================
echo   INSTALLATION COMPLETED SUCCESSFULLY!
echo ========================================================
echo   - Installed to: %TARGET_DIR%
echo   - Desktop Shortcut: Created
echo   - Windows Auto-Start: Enabled (Launches automatically on PC boot)
echo.
echo Launching KCSM Print Service...
start "" "%TARGET_DIR%\ErpGoPrintService.exe"

echo Done.
pause
