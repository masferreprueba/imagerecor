import shutil
import threading
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.auth import router as auth_router
from .api.jobs import router as jobs_router
from .config import get_settings
from .database import init_db

settings = get_settings()
cleanup_stop = threading.Event()


def cleanup_expired() -> None:
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    threshold = datetime.now(timezone.utc) - timedelta(hours=settings.temp_ttl_hours)
    for directory in settings.storage_root.iterdir():
        if directory.is_dir() and datetime.fromtimestamp(directory.stat().st_mtime, timezone.utc) < threshold:
            shutil.rmtree(directory, ignore_errors=True)


def cleanup_loop() -> None:
    while not cleanup_stop.wait(3600):
        cleanup_expired()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db(); cleanup_expired()
    cleaner = threading.Thread(target=cleanup_loop, name="temp-cleaner", daemon=True)
    cleaner.start()
    yield
    cleanup_stop.set()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["*"])
app.include_router(auth_router)
app.include_router(jobs_router)


@app.get("/health")
def health():
    return {"status": "ok", "provider": settings.image_api_provider}
