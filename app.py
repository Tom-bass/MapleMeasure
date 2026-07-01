import threading
import webbrowser
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles

from core import DB_PATH, STATIC_DIR, UPLOADS_DIR, templates
from database import init_db
from routes import api, sessions, settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(DB_PATH)
    yield


app = FastAPI(lifespan=lifespan)

app.mount("/static",  StaticFiles(directory=STATIC_DIR),  name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

app.include_router(api.router)
app.include_router(sessions.router)
app.include_router(settings.router)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse(
        request,
        "error.html",
        {"message": "Page not found."},
        status_code=404,
    )


def main():
    t = threading.Timer(1.5, lambda: webbrowser.open("http://localhost:8000"))
    t.daemon = True
    t.start()
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
