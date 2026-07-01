# MapleMeasure

A local desktop web app for MapleStory Mobile players. Log auto-battle sessions, track kill rates and SOL Frag drop rates over time, and visualise trends — all without sending data anywhere.

Double-click the `.exe`. Your browser opens. That's it.

---

## Features

- **Manual session logging** — enter Duration, Kills, and SOL Frags gathered; optional screenshot per session
- **Dashboard** — aggregate stat cards and per-date trend charts (kills/day, SOL frags/day) across all sessions
- **Session history** — sortable, paginated table with per-column bar charts and automatic average/total footer rows; includes computed Frags per Hour and SOL Frags per 1,000 Kills rates
- **CSV export & import** — full roundtrip: export all sessions, edit offline, re-import; row-level validation with per-row error reporting
- **Auto-backup** — optional setting that silently saves a CSV backup each time the app launches; choose a folder via the native Windows folder picker or fall back to the browser Downloads folder
- **100% local** — SQLite database, no account, no cloud, no telemetry

---

## Installation (Windows)

1. Download `MapleMeasure.exe` from the [latest release](../../releases/latest)
2. Place it in any folder — it creates `mapletracker.db`, `uploads/`, and `config.json` alongside itself on first run
3. Double-click — a terminal window opens and your browser launches automatically

Closing the terminal window stops the app. Run it again to restart.

---

## Running from source

```bash
git clone https://github.com/<your-username>/MapleMeasure.git
cd MapleMeasure
pip install -r requirements.txt
python app.py
```

The browser opens automatically. To stop, press `Ctrl+C` in the terminal.

---

## Building the EXE

GitHub Actions builds and attaches `MapleMeasure.exe` to a release automatically when a version tag is pushed:

```bash
git tag v1.0.0
git push origin v1.0.0
```

To build locally on Windows:

```bash
pip install -r requirements.txt
pyinstaller MapleTracker.spec
# output: dist/MapleMeasure.exe
```

---

## Architecture

```
app.py              Entrypoint — FastAPI app factory, lifespan hook, static mounts, router registration
core.py             All path constants with frozen/source dual-resolution + Jinja2 singleton
database.py         Every SQL query as a named function — no inline SQL anywhere in route handlers
config.py           Reads/writes config.json next to the .exe (persists user settings)

routes/
  sessions.py       Dashboard (/), new session (/upload), history (/sessions),
                    detail/edit/delete (/sessions/{id}), CSV export, CSV import
  settings.py       /settings — auto-backup toggle and backup folder config
  api.py            /api/browse-folder — native OS folder picker (tkinter)
                    /api/backup — server-side CSV write to configured folder

templates/          Jinja2 server-rendered HTML; no JS framework, no build step
static/
  style.css         Dark gaming theme (#0d1117 bg, #f0a500 amber, #1a6fb5 blue); CSS custom properties throughout
  main.js           Shared UI helpers

.github/workflows/
  build.yml         Lint + import-check on every push; Windows EXE build on v* tags → GitHub Release
MapleTracker.spec   PyInstaller spec — canonical, version-controlled build definition
```

**Session data flow:**

```
User submits form (/upload)
  → optional screenshot written to uploads/{uuid}.ext
  → session row inserted into SQLite (sessions table)
  → HTTP 303 redirect to /sessions/{id}
```

**PyInstaller path resolution** (`core.py`):

```python
# Read-only bundle content (templates, static) uses sys._MEIPASS when frozen
# User-writable files (DB, uploads, config) use sys.executable's directory
# This ensures data persists between exe runs rather than being unpacked to a temp dir
```

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI + uvicorn | Clean route definitions, async where needed, runs as a plain Python process |
| Templates | Jinja2 + vanilla JS | Zero build step; works inside a PyInstaller bundle without a node_modules tree |
| Charts | Chart.js (CDN) | Lightweight; per-date aggregation computed server-side, pushed as JSON to the template |
| Database | SQLite (`sqlite3` stdlib) | Zero setup; single portable file; no server process |
| Packaging | PyInstaller `--onefile` | Single `.exe` — no Python, no installer, no admin rights required on end-user machine |
| CI/CD | GitHub Actions | Lint on every push; release build triggered by version tag; EXE attached to GitHub Release automatically |

---

## Database schema

```sql
CREATE TABLE sessions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at          TEXT NOT NULL,       -- UTC ISO-8601
    session_date        TEXT,                -- YYYY-MM-DD
    auto_battle_minutes INTEGER,
    kills               INTEGER,
    solo_frags          INTEGER,
    image_filename      TEXT                 -- relative to uploads/, nullable
);
```

All queries live in `database.py` as named functions. Route handlers never construct SQL strings.

---

## Licence

[MIT](LICENSE)
