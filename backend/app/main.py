from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.auth import router as auth_router
from app.garden import router as garden_router
from app.images_api import media_router
from app.images_api import router as images_router
from app.recruit_events import router as recruit_events_router
from app.recruits import router as recruits_router
from app.settings import cors_origins, storage_backend


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.open_pool()
    try:
        yield
    finally:
        db.close_pool()


app = FastAPI(title="JobNavi API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=cors_origins(), allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["*"])
app.include_router(recruits_router)
app.include_router(recruit_events_router)
app.include_router(auth_router)
app.include_router(garden_router)
app.include_router(images_router)
if storage_backend() == "local":  # S3 / R2 では、公開画像は CDN が配る
    app.include_router(media_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
