# app/main.py
# FastAPI application entry point.
# Owns: app init, middleware, router registration, health check.
# Stage 1: stub — no middleware or startup logic yet.

from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(title="RoomKit", version="0.1.0")

app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
