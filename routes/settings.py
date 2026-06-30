from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from core import templates, CONFIG_PATH
from config import load_config, save_config

router = APIRouter()


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    cfg = load_config(CONFIG_PATH)
    return templates.TemplateResponse(request, "settings.html", {"cfg": cfg})


@router.post("/settings")
def settings_save(auto_backup: str = Form(default="")):
    cfg = load_config(CONFIG_PATH)
    cfg["auto_backup"] = (auto_backup == "on")
    save_config(CONFIG_PATH, cfg)
    return RedirectResponse("/settings", status_code=303)
