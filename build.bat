@echo off
echo ========================================================
echo   Building KCSM Print Service Desktop Suite & Installer
echo ========================================================

cd /d "%~dp0"

echo [1/3] Checking dependencies...
python -m pip install -r requirements.txt
python -m pip install pyinstaller

echo [2/3] Building main Desktop Agent (ErpGoPrintService.exe)...
pyinstaller --noconsole ^
            --onefile ^
            --name "ErpGoPrintService" ^
            --hidden-import "win32print" ^
            --hidden-import "win32api" ^
            --hidden-import "websockets" ^
            --hidden-import "PyQt6" ^
            --hidden-import "PyQt6.QtCore" ^
            --hidden-import "PyQt6.QtGui" ^
            --hidden-import "PyQt6.QtWidgets" ^
            --hidden-import "PyQt6.QtNetwork" ^
            --collect-all PyQt6 ^
            --collect-all websockets ^
            main.py

echo [3/3] Building Standalone Graphical Installer (KCSM_PrintService_Setup.exe)...
pyinstaller --noconsole ^
            --onefile ^
            --name "KCSM_PrintService_Setup" ^
            --add-data "dist\ErpGoPrintService.exe;dist" ^
            --add-data "config.example.json;." ^
            --hidden-import "PyQt6" ^
            --hidden-import "PyQt6.QtWidgets" ^
            --hidden-import "PyQt6.QtCore" ^
            --hidden-import "PyQt6.QtGui" ^
            --collect-all PyQt6 ^
            installer_wizard.py

echo.
if exist "dist\ErpGoPrintService.exe" (
    echo ========================================================
    echo   BUILD SUCCESSFUL!
    echo   Main Executable: dist\ErpGoPrintService.exe
    if exist "dist\KCSM_PrintService_Setup.exe" (
        echo   Installer Wizard: dist\KCSM_PrintService_Setup.exe
    )
    echo   1-Click Batch Installer: install.bat
    echo ========================================================
) else (
    echo ========================================================
    echo   BUILD FAILED. Please check errors above.
    echo ========================================================
)
