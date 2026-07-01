import csv
import io
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse

from core import templates, DB_PATH, UPLOADS_DIR, CONFIG_PATH
from config import load_config
from database import (
    get_dashboard_data,
    insert_session,
    list_sessions,
    get_session,
    delete_session,
    update_session,
    get_sessions_analytics,
    export_sessions_rows,
    import_sessions,
)

router = APIRouter()

_VALID_SORTS    = frozenset({"created_at", "session_date", "auto_battle_minutes", "kills", "solo_frags"})
_SESSIONS_PER_PAGE = 20
_MAX_UPLOAD_BYTES  = 20 * 1024 * 1024  # 20 MB


def _fi(value: str) -> Optional[int]:
    v = value.strip()
    try:
        return int(float(v)) if v else None
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    import json
    data = get_dashboard_data(DB_PATH)
    cfg  = load_config(CONFIG_PATH)

    chart_rows   = data["chart_rows"]
    chart_labels = [r["session_date"] for r in chart_rows]
    chart_kills  = [r["total_kills"] or 0 for r in chart_rows]
    chart_frags  = [r["total_frags"] or 0 for r in chart_rows]

    return templates.TemplateResponse(request, "index.html", {
        "total_sessions": data["total_sessions"],
        "total_hours":    data["total_hours"],
        "total_kills":    f"{data['total_kills']:,}",
        "total_frags":    f"{data['total_frags']:,}",
        "recent":         data["recent"],
        "chart_labels":   json.dumps(chart_labels),
        "chart_kills":    json.dumps(chart_kills),
        "chart_frags":    json.dumps(chart_frags),
        "auto_backup":    cfg.get("auto_backup", False),
        "backup_folder":  cfg.get("backup_folder", ""),
    })


# ---------------------------------------------------------------------------
# New session form
# ---------------------------------------------------------------------------

@router.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request):
    today = datetime.now().strftime("%Y-%m-%d")
    return templates.TemplateResponse(request, "upload.html", {
        "today": today,
        "error": None,
    })


@router.post("/sessions/create")
async def create_session(
    request: Request,
    session_date: str        = Form(...),
    auto_battle_minutes: str = Form(...),
    kills: str               = Form(...),
    solo_frags: str          = Form(...),
    file: Optional[UploadFile] = File(None),
):
    image_filename = None
    if file and file.filename:
        content = await file.read()
        if len(content) > _MAX_UPLOAD_BYTES:
            today = datetime.now().strftime("%Y-%m-%d")
            return templates.TemplateResponse(request, "upload.html", {
                "today": today,
                "error": "Screenshot too large — maximum is 20 MB.",
            })
        if content:
            ext = os.path.splitext(file.filename)[1] or ".png"
            image_filename = f"{uuid.uuid4().hex}{ext}"
            with open(os.path.join(UPLOADS_DIR, image_filename), "wb") as fh:
                fh.write(content)

    session_data = {
        "created_at":          datetime.utcnow().isoformat(),
        "session_date":        session_date.strip() or None,
        "auto_battle_minutes": _fi(auto_battle_minutes),
        "kills":               _fi(kills),
        "solo_frags":          _fi(solo_frags),
        "image_filename":      image_filename,
    }

    session_id = insert_session(DB_PATH, session_data)
    return RedirectResponse(f"/sessions/{session_id}", status_code=303)


# ---------------------------------------------------------------------------
# Session list
# ---------------------------------------------------------------------------

@router.get("/sessions", response_class=HTMLResponse)
def sessions_list(
    request: Request,
    page:  int = 1,
    sort:  str = "created_at",
    order: str = "desc",
):
    import json
    if sort not in _VALID_SORTS:
        sort = "created_at"
    if order not in {"asc", "desc"}:
        order = "desc"

    rows, total = list_sessions(DB_PATH, sort, order, page, _SESSIONS_PER_PAGE)
    total_pages = max(1, (total + _SESSIONS_PER_PAGE - 1) // _SESSIONS_PER_PAGE)
    analytics   = get_sessions_analytics(DB_PATH)

    # Build per-session chart labels: date + counter when same date appears multiple times
    date_counts: dict = {}
    chart_labels = []
    for r in analytics["chart_rows"]:
        d = r["session_date"] or f"#{r['id']}"
        date_counts[d] = date_counts.get(d, 0) + 1
        chart_labels.append(d)

    # Re-pass if any date is duplicated, append occurrence index
    date_seen: dict = {}
    final_labels = []
    needs_suffix = {d for d, n in date_counts.items() if n > 1}
    for r in analytics["chart_rows"]:
        d = r["session_date"] or f"#{r['id']}"
        if d in needs_suffix:
            date_seen[d] = date_seen.get(d, 0) + 1
            final_labels.append(f"{d} #{date_seen[d]}")
        else:
            final_labels.append(d)

    return templates.TemplateResponse(request, "sessions.html", {
        "sessions":       rows,
        "page":           page,
        "total_pages":    total_pages,
        "total":          total,
        "sort":           sort,
        "order":          order,
        "analytics":      analytics,
        "chart_labels":   json.dumps(final_labels),
        "chart_minutes":  json.dumps([r["auto_battle_minutes"] or 0 for r in analytics["chart_rows"]]),
        "chart_kills":    json.dumps([r["kills"] or 0 for r in analytics["chart_rows"]]),
        "chart_frags":    json.dumps([r["solo_frags"] or 0 for r in analytics["chart_rows"]]),
    })


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

@router.get("/sessions/export")
def export_csv():
    rows = export_sessions_rows(DB_PATH)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["session_date", "auto_battle_minutes", "kills", "solo_frags"])
    for r in rows:
        writer.writerow([r["session_date"], r["auto_battle_minutes"], r["kills"], r["solo_frags"]])
    buf.seek(0)
    filename = f"maplemeasure_{datetime.now().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Session detail
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}", response_class=HTMLResponse)
def session_detail(request: Request, session_id: int):
    session = get_session(DB_PATH, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return templates.TemplateResponse(request, "session_detail.html", {
        "session": session,
    })


# ---------------------------------------------------------------------------
# Edit session
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/edit", response_class=HTMLResponse)
def edit_session_page(request: Request, session_id: int):
    session = get_session(DB_PATH, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return templates.TemplateResponse(request, "session_edit.html", {
        "session": session,
        "error":   None,
    })


@router.post("/sessions/{session_id}/edit")
async def edit_session_submit(
    request: Request,
    session_id: int,
    session_date: str        = Form(...),
    auto_battle_minutes: str = Form(...),
    kills: str               = Form(...),
    solo_frags: str          = Form(...),
    file: Optional[UploadFile] = File(None),
):
    session = get_session(DB_PATH, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    image_filename = session["image_filename"]
    if file and file.filename:
        content = await file.read()
        if len(content) > _MAX_UPLOAD_BYTES:
            return templates.TemplateResponse(request, "session_edit.html", {
                "session": session,
                "error":   "Screenshot too large — maximum is 20 MB.",
            })
        if content:
            ext = os.path.splitext(file.filename)[1] or ".png"
            new_filename = f"{uuid.uuid4().hex}{ext}"
            with open(os.path.join(UPLOADS_DIR, new_filename), "wb") as fh:
                fh.write(content)
            image_filename = new_filename

    session_data = {
        "session_date":        session_date.strip() or None,
        "auto_battle_minutes": _fi(auto_battle_minutes),
        "kills":               _fi(kills),
        "solo_frags":          _fi(solo_frags),
        "image_filename":      image_filename,
    }

    update_session(DB_PATH, session_id, session_data)
    return RedirectResponse(f"/sessions/{session_id}", status_code=303)


# ---------------------------------------------------------------------------
# Delete session
# ---------------------------------------------------------------------------

@router.post("/sessions/{session_id}/delete")
def delete_session_route(session_id: int):
    delete_session(DB_PATH, session_id)
    return RedirectResponse("/sessions", status_code=303)


# ---------------------------------------------------------------------------
# CSV import
# ---------------------------------------------------------------------------

_REQUIRED_COLS = {"session_date", "auto_battle_minutes", "kills", "solo_frags"}


@router.get("/import", response_class=HTMLResponse)
def import_page(request: Request):
    return templates.TemplateResponse(request, "import.html", {"result": None})


@router.post("/import", response_class=HTMLResponse)
async def import_post(request: Request, file: UploadFile = File(...)):
    raw = await file.read()
    if not raw:
        return templates.TemplateResponse(request, "import.html", {
            "result": {"error": "The uploaded file is empty."}
        })

    try:
        text = raw.decode("utf-8-sig")  # strip BOM if present (Excel exports)
    except UnicodeDecodeError:
        return templates.TemplateResponse(request, "import.html", {
            "result": {"error": "File must be UTF-8 encoded."}
        })

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return templates.TemplateResponse(request, "import.html", {
            "result": {"error": "Could not read CSV headers — is the file valid CSV?"}
        })

    missing = _REQUIRED_COLS - {f.strip().lower() for f in reader.fieldnames}
    if missing:
        return templates.TemplateResponse(request, "import.html", {
            "result": {"error": f"Missing required columns: {', '.join(sorted(missing))}"}
        })

    now = datetime.utcnow().isoformat()
    valid_rows, row_errors = [], []

    for i, row in enumerate(reader, start=2):  # row 1 is the header
        mins_raw  = (row.get("auto_battle_minutes") or "").strip()
        kills_raw = (row.get("kills") or "").strip()
        frags_raw = (row.get("solo_frags") or "").strip()
        date_raw  = (row.get("session_date") or "").strip()

        errors = []
        try:
            mins = int(float(mins_raw)) if mins_raw else None
            if mins is None or mins < 1:
                errors.append("auto_battle_minutes must be a positive integer")
        except ValueError:
            errors.append(f"auto_battle_minutes '{mins_raw}' is not a number")

        try:
            kills = int(float(kills_raw)) if kills_raw else None
            if kills is None or kills < 0:
                errors.append("kills must be a non-negative integer")
        except ValueError:
            errors.append(f"kills '{kills_raw}' is not a number")

        try:
            frags = int(float(frags_raw)) if frags_raw else None
            if frags is None or frags < 0:
                errors.append("solo_frags must be a non-negative integer")
        except ValueError:
            errors.append(f"solo_frags '{frags_raw}' is not a number")

        if errors:
            row_errors.append({"row": i, "messages": errors})
            continue

        valid_rows.append({
            "created_at":          now,
            "session_date":        date_raw or None,
            "auto_battle_minutes": mins,
            "kills":               kills,
            "solo_frags":          frags,
        })

    imported = 0
    if valid_rows:
        imported = import_sessions(DB_PATH, valid_rows)

    return templates.TemplateResponse(request, "import.html", {
        "result": {
            "imported":   imported,
            "skipped":    len(row_errors),
            "row_errors": row_errors,
        }
    })
