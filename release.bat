@echo off
if "%~1"=="" (
    echo Usage: release.bat ^<version^> [release notes]
    echo Example: release.bat 1.1.0 "Added Printed By column and auto-updater"
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0release.ps1" -Version "%~1" -Notes "%~2"
