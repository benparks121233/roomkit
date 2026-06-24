# Shared rate limiter instance.
# In-memory storage: accurate for single-worker deploys.
# Multi-worker (6F) needs Redis backend — each worker counts independently,
# so N workers = Nx the intended limit without shared state.

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    enabled=os.environ.get("TESTING") != "1",
)
