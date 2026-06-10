# app/main.py
# FastAPI application entry point.
# Owns: app init, middleware, router registration, health check.

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from app.api.routes import router  # noqa: E402

app = FastAPI(title="RoomKit", version="0.1.0")

# CORS — allow the Next.js dev server (port 3000) to reach the API (port 8000).
# In production, tighten origins to the actual domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
