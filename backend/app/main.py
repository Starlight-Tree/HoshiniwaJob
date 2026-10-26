from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.auth import router as auth_router
from app.recruits import router as recruits_router
from app.settings import cors_origins


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.open_pool()
    try:
        yield
    finally:
        db.close_pool()


app = FastAPI(title="星庭ジョブ API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=cors_origins(), allow_methods=["GET", "POST"], allow_headers=["*"])
app.include_router(recruits_router)
app.include_router(auth_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
