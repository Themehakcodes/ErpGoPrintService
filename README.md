# KCSM Print Service — Windows Desktop Agent

A robust, hardware-agnostic Windows desktop background application that bridges **KCSM ERP Cloud** to physical receipt, barcode sticker, and thermal printers via secure WebSockets.

---

## Key Features

1. **Clean Front View Dashboard**
   - **Front View**: Live Print Jobs Queue and real-time KPI metrics take 100% of the screen.
   - **The Other Side (Settings Tab)**: Cloud server connection, device pairing, printer selection, and Windows startup preferences are organized cleanly in the Settings tab.
   - Header badge shows active device identity, connected printer, and an instant `⚙️ Settings` shortcut.

2. **Startup Printer Selection Dialog**
   - On application startup, a modern prompt asks the operator to confirm or select their active thermal printer and template.
   - Includes a quick **Test Print Alignment** button to verify before starting cashier operations.
   - Remembers choices and can be toggled on/off.

3. **Automatic Windows Startup**
   - Integrates with the Windows Registry (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`).
   - Automatically boots with Windows in the background tray without requiring manual launch.

4. **1-Click Installer & Uninstaller**
   - **`install.bat`**: 1-click batch installer that copies files to `%LOCALAPPDATA%\Programs\KCSM Print Service`, creates Desktop & Start Menu shortcuts, registers Windows auto-start, and launches the app.
   - **`KCSM_PrintService_Setup.exe`**: Standalone graphical setup wizard.
   - **`uninstall.bat`**: Clean uninstaller that removes shortcuts, registry keys, and files.

5. **Power-Cut & Crash Protection (`ledger.json`)**
   - Automatically maintains a persistent local ledger of every print job received.
   - If an electrical outage or crash occurs while printing, startup reconciliation marks the interrupted job as `INTERRUPTED` and advances the queue.
   - Prevents endless reprint loops of failed or interrupted jobs.

6. **Exact TSPL Retail Barcode Templates**
   - **TSPL 1x4 (4-Up 101.6mm x 25mm)**: Matches the exact download template used in KCSM ERP Products view.
   - **TSPL Bala (74.10mm x 25mm)**: Single label tag with rounded MRP and Code128 barcodes.
   - **ESC/POS & RAW**: Supports thermal receipt printers and vendor PRN files.

---

## Installation Options

### Option A: 1-Click Installer (Recommended for Stores)
Double click:
```cmd
install.bat
```
This automatically installs the app, creates Desktop shortcuts, and configures Windows boot auto-start.

### Option B: Run Standalone Executable
```cmd
dist\ErpGoPrintService.exe
```

### Option C: Run from Python Source
```cmd
pip install -r requirements.txt
python main.py
```
*(Or double click `run.bat`)*

---

## Configuration (`config.json`)

Copy `config.example.json` to `config.json` (ignored by `.gitignore` so local device keys and tokens are never pushed):

```json
{
    "server_url": "wss://erp.kcsmtraders.com/ws/print-service",
    "device_code": "DEV-0002",
    "secret_key": "",
    "selected_printer": "SNBC TVSE LP 46 NEO BPLE",
    "printer_mode": "TSPL",
    "auto_connect": true,
    "minimize_to_tray": true,
    "sound_alerts": true,
    "autostart_with_windows": true,
    "prompt_printer_on_startup": false,
    "auto_check_updates": true,
    "github_repo": "Themehakcodes/ErpGoPrintService",
    "github_token": ""
}
```

---

## Publishing Auto-Updates via GitHub Releases

Every store PC automatically checks `https://api.github.com/repos/<github_repo>/releases/latest` 5 seconds after startup (or manually via **Settings → Check for Updates**).

To roll out a new version to all store PCs:
1. Bump `APP_VERSION` in `core/version.py` (e.g. `"1.2.0"`).
2. Run `build.bat` to generate `dist\KCSM_PrintService_Setup.exe`.
3. Push your code to GitHub and create a new **GitHub Release** with tag `v1.2.0`.
4. Attach `dist\KCSM_PrintService_Setup.exe` as a release asset and publish.
5. All store PCs will display a **🚀 Update Available: v1.2.0** banner with 1-click **Download & Install**.
   - *(For private repositories, enter a fine-grained read-only GitHub PAT with `Contents: Read` permission in Settings → Access Token.)*
