# Deploy: Railway

## Three services

Defined in `railway.json`:

| Service | Role | Start command |
|---|---|---|
| `web` | FastAPI API server | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| `worker` | Async sourcing + render jobs | `python -m services.refresh_worker` |
| `cron` | Locked price/link refresh | `python -m services.refresh_worker` on schedule `0 */6 * * *` |

## Environment variables

All required env vars are documented in `.env.example`. Set these in the Railway
service environment settings — never in `railway.json`.

Key vars:
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` — DB
- `ANTHROPIC_API_KEY` — LLM calls (style, composition, selection)
- `AMAZON_AFFILIATE_TAG` — injected into all Amazon buy URLs
- `PORT` — set automatically by Railway for the web service

## Deployment

Push to `main` on GitHub triggers Railway deploy (configure via Railway GitHub integration).

The `web` service deploys the FastAPI app. The `cron` service runs the refresh worker
on the freshness schedule from `context/freshness_policies.yaml`.

## Refresh worker lock

The refresh worker (`services/refresh_worker.py`) must run under a Supabase advisory
lock to prevent double-run when Railway cron fires. See Stage 11 for implementation.
The lock pattern mirrors the advisory-lock work from the furniture price engine.
