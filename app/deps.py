# app/deps.py
# Shared FastAPI dependencies: DB session, settings, future auth.
# Stage 1: stub — dependencies will be wired in Stage 2+.


def get_settings():
    # Stage 2: load from pydantic-settings / .env
    raise NotImplementedError


def get_db():
    # Stage 2: yield a Supabase client scoped to the request
    raise NotImplementedError
