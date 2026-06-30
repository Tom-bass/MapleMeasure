import os
from fastapi import APIRouter
from core import ASSETS_DIR

router = APIRouter(prefix="/api")

_AUDIO_EXTS = {".mp3", ".ogg", ".wav", ".flac", ".m4a"}


@router.get("/tracks")
def list_tracks():
    if not os.path.isdir(ASSETS_DIR):
        return {"tracks": []}
    tracks = sorted(
        f for f in os.listdir(ASSETS_DIR)
        if os.path.splitext(f)[1].lower() in _AUDIO_EXTS
    )
    return {"tracks": tracks}
