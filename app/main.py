# app/main.py
# FastAPI application entry point.
# Owns: app init, middleware, router registration, health check.

from dotenv import load_dotenv

load_dotenv()

from pathlib import Path  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from app.api.routes import router  # noqa: E402
from app.api.admin import router as admin_router  # noqa: E402

app = FastAPI(title="RoomKit", version="0.1.0")

# CORS — allow the Next.js frontend to reach the API.
# In production, set CORS_ORIGINS to the actual domain(s), comma-separated.
# Defaults to localhost dev servers only.
import os as _os  # noqa: E402
_cors_origins = _os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:3001",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(admin_router)

# Serve rendered room images as static files.
_renders_dir = Path(__file__).parent.parent / "data" / "renders"
_renders_dir.mkdir(parents=True, exist_ok=True)
app.mount("/renders", StaticFiles(directory=str(_renders_dir)), name="renders")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/health/supabase")
def supabase_health() -> dict:
    from services.supabase_client import health_check
    return health_check()
