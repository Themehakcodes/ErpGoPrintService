@echo off
echo ========================================================
echo   KCSM Print Service — Uninstaller
echo ========================================================
echo.

set "TARGET_DIR=%LOCALAPPDATA%\Programs\KCSM Print Service"

echo Stopping running print service processes...
taskkill /F /IM ErpGoPrintService.exe 2>nul

echo Removing Windows Auto-Start registry key...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "KCSMPrintService" /f 2>nul

echo Removing shortcuts...
del "%USERPROFILE%\Desktop\KCSM Print Service.lnk" 2>nul
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\KCSM Print Service.lnk" 2>nul

echo Removing application directory...
rmdir /S /Q "%TARGET_DIR%" 2>nul

echo.
echo ========================================================
echo   UNINSTALLATION COMPLETED.
echo ========================================================
pause
