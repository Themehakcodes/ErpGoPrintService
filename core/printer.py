"""
Windows Print Spooler Integration & Label Format Generators.
Communicates directly with win32print to send RAW commands to any printer.
"""

import math
import time
import win32print

class WindowsPrinter:
    @staticmethod
    def get_installed_printers() -> list[str]:
        """Lists all local and network printers installed on this Windows PC."""
        try:
            printers = [p[2] for p in win32print.EnumPrinters(
                win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            )]
            return printers
        except Exception as e:
            print(f"[Printer] Failed to enumerate printers: {e}")
            return []

    @staticmethod
    def get_default_printer() -> str:
        """Returns the Windows default printer name."""
        try:
            return win32print.GetDefaultPrinter()
        except Exception:
            return ""

    @staticmethod
    def get_spooler_status(printer_name: str) -> dict:
        """
        Queries the Windows Print Spooler for real-time queue and printer state.
        Returns: {"busy": bool, "active_jobs": int, "status_text": str, "current_doc": str}
        """
        if not printer_name or "No Windows Printers" in printer_name:
            return {"busy": False, "active_jobs": 0, "status_text": "No printer selected", "current_doc": ""}

        try:
            handle = win32print.OpenPrinter(printer_name)
            try:
                p_info = win32print.GetPrinter(handle, 2)
                status_flags = p_info.get("Status", 0)
                jobs = win32print.EnumJobs(handle, 0, 50, 1) or []
            finally:
                win32print.ClosePrinter(handle)

            active_jobs = len(jobs)
            current_doc = jobs[0].get("pDocument", "") if jobs else ""

            # Common win32print status flags
            PRINTER_STATUS_PAUSED = 0x00000001
            PRINTER_STATUS_ERROR = 0x00000002
            PRINTER_STATUS_PAPER_JAM = 0x00000008
            PRINTER_STATUS_PAPER_OUT = 0x00000010
            PRINTER_STATUS_OFFLINE = 0x00000080
            PRINTER_STATUS_BUSY = 0x00000200
            PRINTER_STATUS_PRINTING = 0x00000400
            PRINTER_STATUS_DOOR_OPEN = 0x00400000

            is_busy = active_jobs > 0 or bool(status_flags & (PRINTER_STATUS_PRINTING | PRINTER_STATUS_BUSY))

            if status_flags & PRINTER_STATUS_PAPER_OUT:
                status_text = "Paper / Label Roll Out"
            elif status_flags & PRINTER_STATUS_PAPER_JAM:
                status_text = "Paper Jam Detected"
            elif status_flags & PRINTER_STATUS_DOOR_OPEN:
                status_text = "Printer Cover Open"
            elif status_flags & PRINTER_STATUS_OFFLINE:
                status_text = "Printer Offline"
            elif status_flags & PRINTER_STATUS_PAUSED:
                status_text = "Printer Paused in Windows"
            elif status_flags & PRINTER_STATUS_ERROR:
                status_text = "Printer Hardware Error"
            elif is_busy:
                status_text = f"Spooling / Printing ({active_jobs} in queue)" if active_jobs > 0 else "Printer Busy..."
            else:
                status_text = "Printer Ready — Idle"

            return {
                "busy": is_busy,
                "active_jobs": active_jobs,
                "status_text": status_text,
                "current_doc": current_doc,
            }
        except Exception:
            return {"busy": False, "active_jobs": 0, "status_text": "Printer Ready — Idle", "current_doc": ""}

    @staticmethod
    def send_raw_bytes(printer_name: str, data: bytes, doc_name: str = "KCSM_Print_Job") -> tuple[bool, str]:
        """Sends raw bytes directly to the Windows Spooler for instant output."""
        if not printer_name:
            return False, "No printer specified"

        try:
            handle = win32print.OpenPrinter(printer_name)
            try:
                win32print.StartDocPrinter(handle, 1, (doc_name, None, "RAW"))
                win32print.StartPagePrinter(handle)
                win32print.WritePrinter(handle, data)
                win32print.EndPagePrinter(handle)
                win32print.EndDocPrinter(handle)
            finally:
                win32print.ClosePrinter(handle)
            return True, "Printed successfully"
        except Exception as e:
            return False, f"Windows Spooler Error: {e}"

    # ─── TSPL Generator (4-up Barcode Label 101.6mm x 25mm, e.g. TVS LP-46 / TSC) ───

    @staticmethod
    def generate_tspl_4up(product_name: str, mrp: float, sale_rate: float, barcode: str, quantity: int = 1) -> bytes:
        """
        Generates TSPL 4-sticker-across code (101.6mm x 25mm / 4" x 1").
        Matches the EXACT download template used in ProductStocksView (1x4):
        SIZE 101.6 mm, 25 mm, GAP 3 mm, 0 mm, 4 columns across.
        """
        bc = barcode.strip()
        if "NOT FOR SALE" in bc:
            import re
            m = re.search(r"\d{8,14}", bc)
            if m:
                bc = m.group(0)
        if len(bc) > 16:
            bc = bc[:16]

        clean_short_name = product_name.replace('"', '').strip()[:15].upper()
        mrp_str = f"{mrp:.2f}"
        rate_str = f"{sale_rate:.2f}"
        rows_to_print = max(1, math.ceil(quantity / 4))

        tspl = [
            "SIZE 101.6 mm, 25 mm",
            "GAP 3 mm, 0 mm",
            "DIRECTION 0,0",
            "REFERENCE 0,0",
            "OFFSET 0 mm",
            "SET PEEL OFF",
            "SET CUTTER OFF",
            "SET PARTIAL_CUTTER OFF",
            "SET TEAR ON",
            "ON",
            "CLS",
            "CODEPAGE 1252",
            # Column 1
            f'TEXT 795,189,"0",180,9,7," {clean_short_name}"',
            f'TEXT 801,160,"ROMAN.TTF",180,1,9,"MRP:    {mrp_str}"',
            f'TEXT 800,121,"ROMAN.TTF",180,1,9,"RATE:    {rate_str}"',
            f'BARCODE 782,83,"128M",38,0,180,1,2,"{bc}"',
            f'TEXT 782,43,"ROMAN.TTF",180,1,8,"{bc}"',
            # Column 2
            f'TEXT 592,189,"0",180,9,7," {clean_short_name}"',
            f'TEXT 598,160,"ROMAN.TTF",180,1,9,"MRP:    {mrp_str}"',
            f'TEXT 597,121,"ROMAN.TTF",180,1,9,"RATE:    {rate_str}"',
            f'BARCODE 579,83,"128M",38,0,180,1,2,"{bc}"',
            f'TEXT 579,43,"ROMAN.TTF",180,1,8,"{bc}"',
            # Column 3
            f'TEXT 389,189,"0",180,9,7," {clean_short_name}"',
            f'TEXT 395,160,"ROMAN.TTF",180,1,9,"MRP:    {mrp_str}"',
            f'TEXT 394,121,"ROMAN.TTF",180,1,9,"RATE:    {rate_str}"',
            f'BARCODE 376,83,"128M",38,0,180,1,2,"{bc}"',
            f'TEXT 376,43,"ROMAN.TTF",180,1,8,"{bc}"',
            # Column 4
            f'TEXT 186,189,"0",180,9,7," {clean_short_name}"',
            f'TEXT 192,160,"ROMAN.TTF",180,1,9,"MRP:    {mrp_str}"',
            f'TEXT 191,121,"ROMAN.TTF",180,1,9,"RATE:    {rate_str}"',
            f'BARCODE 173,83,"128M",38,0,180,1,2,"{bc}"',
            f'TEXT 173,43,"ROMAN.TTF",180,1,8,"{bc}"',
            f"PRINT {rows_to_print},1\n"
        ]
        return "\n".join(tspl).encode("latin-1", errors="replace")

    # ─── TSPL Generator (Bala Single Label 74.10mm x 25mm) ─────────────────────

    @staticmethod
    def generate_tspl_bala(product_name: str, mrp: float, sale_rate: float, barcode: str, quantity: int = 1) -> bytes:
        """
        Generates TSPL Bala Single Label (74.10mm x 25mm).
        Matches the EXACT download template used in ProductStocksView (bala).
        """
        bc = barcode.strip()
        if "NOT FOR SALE" in bc:
            import re
            m = re.search(r"\d{8,14}", bc)
            if m:
                bc = m.group(0)
        if len(bc) > 16:
            bc = bc[:16]

        clean_short_name = product_name.replace('"', '').strip()[:15].upper()
        rounded_mrp = round(mrp)
        title_text = f"{clean_short_name} {rounded_mrp}/-     "
        mrp_str = f"{mrp:.2f}"
        rate_str = f"{sale_rate:.2f}"
        total_labels = max(1, quantity)

        tspl = [
            "SIZE 74.10 mm, 25 mm",
            "GAP 3 mm, 0 mm",
            "DIRECTION 0,0",
            "REFERENCE 0,0",
            "OFFSET 0 mm",
            "SET PEEL OFF",
            "SET CUTTER OFF",
            "SET PARTIAL_CUTTER OFF",
            "SET TEAR ON",
            "ON",
            "CLS",
            "CODEPAGE 1252",
            f'TEXT 415,108,"0",180,9,9,"{title_text}"',
            f'BARCODE 590,100,"128M",44,0,180,1,4,"{bc}     "',
            f'TEXT 550,50,"ROMAN.TTF",180,1,10,"{bc}          "',
            f'TEXT 415,75,"0",180,9,9,"MRP :  {mrp_str}"',
            f'TEXT 415,40,"0",180,9,9,"RATE :   {rate_str}"',
            f"PRINT {total_labels},1\n"
        ]
        return "\n".join(tspl).encode("latin-1", errors="replace")

    # ─── TSPL Generator (1-up Barcode Label 50mm x 25mm / 2" x 1") ─────────────

    @staticmethod
    def generate_tspl_1up(product_name: str, mrp: float, sale_rate: float, barcode: str, quantity: int = 1) -> bytes:
        """Generates standard 1-up barcode label (50mm x 25mm)."""
        display_name = product_name[:24].upper()
        bc_str = barcode.strip()

        tspl = [
            "SIZE 50 mm, 25 mm",
            "GAP 3 mm, 0 mm",
            "DIRECTION 1,0",
            "CLS",
            f'TEXT 20,20,"0",0,1,1,"{display_name}"',
            f'TEXT 20,45,"0",0,1,1,"MRP: Rs.{mrp:.2f}  RATE: Rs.{sale_rate:.2f}"',
            f'BARCODE 20,80,"128",55,1,0,2,2,"{bc_str}"',
            f'TEXT 20,145,"0",0,1,1,"* {bc_str} *"',
            f"PRINT {max(1, quantity)},1\n"
        ]
        return "\n".join(tspl).encode("latin-1", errors="replace")

    # ─── ESC/POS Generator (Thermal Receipt 58mm / 80mm) ────────────────────────

    @staticmethod
    def generate_escpos_tag(product_name: str, mrp: float, sale_rate: float, barcode: str, quantity: int = 1, store_name: str = "KCSM Store") -> bytes:
        """Generates ESC/POS thermal receipt sticker or tag with barcode."""
        ESC = b"\x1b"
        GS = b"\x1d"

        out = bytearray()
        for _ in range(max(1, quantity)):
            out.extend(ESC + b"@")                     # Initialize
            out.extend(ESC + b"a" + b"\x01")           # Align Center
            out.extend(ESC + b"E" + b"\x01")           # Bold ON
            out.extend(f"{store_name}\n".encode("ascii", errors="replace"))
            out.extend(ESC + b"E" + b"\x00")           # Bold OFF
            out.extend(f"{product_name}\n".encode("ascii", errors="replace"))
            out.extend(b"--------------------------------\n")
            out.extend(f"MRP: Rs.{mrp:.2f}  SALE: Rs.{sale_rate:.2f}\n".encode("ascii"))
            out.extend(b"\n")
            # Barcode CODE128
            out.extend(GS + b"h" + b"\x40")            # Height 64 dots
            out.extend(GS + b"w" + b"\x02")            # Width 2
            out.extend(GS + b"H" + b"\x02")            # Text below barcode
            bc_bytes = barcode.encode("ascii", errors="replace")
            out.extend(GS + b"k" + b"\x49" + bytes([len(bc_bytes)]) + bc_bytes)
            out.extend(b"\n\n\n")
            out.extend(GS + b"V" + b"\x41" + b"\x00")  # Partial cut

        return bytes(out)

    # ─── Test Print Generator ───────────────────────────────────────────────────

    @classmethod
    def generate_test_print(cls, mode: str = "TSPL", printer_name: str = "") -> bytes:
        """Generates test calibration label."""
        if mode == "ESCPOS":
            return cls.generate_escpos_tag(
                product_name="** KCSM TEST PRINT **",
                mrp=999.00,
                sale_rate=888.00,
                barcode="TEST890123",
                quantity=1,
                store_name="KCSM PRINT SERVICE TEST"
            )
        elif mode == "TSPL_BALA":
            return cls.generate_tspl_bala(
                product_name="KCSM CALIB TEST",
                mrp=99.00,
                sale_rate=85.00,
                barcode="TEST-12345",
                quantity=1
            )
        elif mode == "TSPL_1UP":
            return cls.generate_tspl_1up(
                product_name="KCSM CALIBRATION TEST",
                mrp=99.00,
                sale_rate=85.00,
                barcode="TEST-12345",
                quantity=1
            )
        else:
            # Default TSPL 4-up
            return cls.generate_tspl_4up(
                product_name="KCSM TEST TAG",
                mrp=100.00,
                sale_rate=90.00,
                barcode="TEST890123",
                quantity=4
            )
