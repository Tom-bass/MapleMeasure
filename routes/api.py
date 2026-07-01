import csv
import os
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from core import DB_PATH, CONFIG_PATH
from config import load_config
from database import export_sessions_rows

router = APIRouter(prefix="/api")


@router.get("/browse-folder")
def browse_folder():
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return JSONResponse({"path": None, "error": "tkinter not available"})

    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", True)
    folder = filedialog.askdirectory(parent=root, title="Select backup folder")
    root.destroy()
    return {"path": folder or None}


@router.get("/backup")
def run_backup():
    cfg = load_config(CONFIG_PATH)
    folder = cfg.get("backup_folder", "")
    if not folder or not os.path.isdir(folder):
        return JSONResponse({"ok": False, "error": "Backup folder not set or does not exist"}, status_code=400)

    filename = f"MapleMeasure_{datetime.now().strftime('%Y-%m-%d')}.csv"
    filepath = os.path.join(folder, filename)

    rows = export_sessions_rows(DB_PATH)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["session_date", "auto_battle_minutes", "kills", "solo_frags"])
        for r in rows:
            writer.writerow([r["session_date"], r["auto_battle_minutes"], r["kills"], r["solo_frags"]])

    return {"ok": True, "path": filepath}
