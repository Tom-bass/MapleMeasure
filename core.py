"""
Shared singletons and path constants.

Imported by app.py and every route module.  Keeping path resolution in one
place means the PyInstaller frozen-path logic is written exactly once.
"""

import sys
import os

from fastapi.templating import Jinja2Templates

# ---------------------------------------------------------------------------
# Path resolution — source vs. frozen (PyInstaller) contexts
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    BASE_DIR    = os.path.dirname(sys.executable)
    _BUNDLE_DIR = sys._MEIPASS          # unpacked bundle temp dir
else:
    BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
    _BUNDLE_DIR = BASE_DIR

DB_PATH      = os.path.join(BASE_DIR,    "mapletracker.db")
UPLOADS_DIR  = os.path.join(BASE_DIR,    "uploads")
CONFIG_PATH  = os.path.join(BASE_DIR,    "config.json")
TEMPLATE_DIR = os.path.join(_BUNDLE_DIR, "templates")
STATIC_DIR   = os.path.join(_BUNDLE_DIR, "static")
ASSETS_DIR   = os.path.join(_BUNDLE_DIR, "assets")   # read-only bundle content

os.makedirs(UPLOADS_DIR, exist_ok=True)
# assets/ is read-only when frozen (extracted from bundle); only create in dev
if not getattr(sys, "frozen", False):
    os.makedirs(ASSETS_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Jinja2 template engine — one instance shared across all route modules
# ---------------------------------------------------------------------------
templates = Jinja2Templates(directory=TEMPLATE_DIR)
