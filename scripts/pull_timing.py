#!/usr/bin/env python3
"""Pull decomposed timing from design_completed events in Supabase.

Uses the SERVICE-ROLE key (bypasses RLS) because the events table is
correctly not anon-readable. This script runs locally — the service-role
key must NEVER be committed, shipped in frontend code, or exposed
client-side.

Usage:
  python scripts/pull_timing.py [--last N]

Reads SUPABASE_URL and SUPABASE_SERVICE_KEY from .env (via dotenv)
or pass explicitly via --supabase-url and --service-key.
"""
import argparse
import json
import os
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--supabase-url", default=os.environ.get("SUPABASE_URL"))
    parser.add_argument("--service-key", default=os.environ.get("SUPABASE_SERVICE_KEY"))
    parser.add_argument("--schema", default=os.environ.get("SUPABASE_SCHEMA", "public"))
    parser.add_argument("--last", type=int, default=10, help="Last N design_completed events")
    args = parser.parse_args()

    if not args.supabase_url or not args.service_key:
        print("Need SUPABASE_URL and SUPABASE_SERVICE_KEY in .env (or pass --supabase-url / --service-key)")
        print(f"  SUPABASE_URL present: {'SUPABASE_URL' in os.environ}")
        print(f"  SUPABASE_SERVICE_KEY present: {'SUPABASE_SERVICE_KEY' in os.environ}")
        return

    key_prefix = args.service_key[:20]
    is_service_key = "service_role" in args.service_key or key_prefix.startswith("eyJ")
    print(f"Using schema: {args.schema}")
    print(f"Key prefix: {key_prefix}... ({'service-role' if is_service_key else 'CHECK — may be anon key'})")
    print()

    url = f"{args.supabase_url}/rest/v1/events"
    headers = {
        "apikey": args.service_key,
        "Authorization": f"Bearer {args.service_key}",
        "Accept-Profile": args.schema,
    }
    params = {
        "select": "run_id,event_type,data,created_at",
        "event_type": "eq.design_completed",
        "order": "created_at.desc",
        "limit": args.last,
    }

    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        print(f"Error {resp.status_code}: {resp.text[:300]}")
        return

    events = resp.json()
    if not events:
        print("No design_completed events found.")
        return

    print(f"{'run_id':>12s}  {'total':>8s}  {'sem_wait':>8s}  {'sel_llm':>8s}  "
          f"{'style':>8s}  {'comp':>8s}  {'source':>8s}  {'intake':>8s}  {'created_at':>20s}")
    print("-" * 110)

    for e in reversed(events):
        data = e.get("data") or {}
        if isinstance(data, str):
            data = json.loads(data)
        timing = data.get("timing", {})

        run_id = (e.get("run_id") or "?")[-12:]
        total = timing.get("total_ms", "?")
        sem = timing.get("semaphore_wait_ms", "—")
        sel_llm = timing.get("selection_llm_ms", "—")
        style = timing.get("style_ms", "?")
        comp = timing.get("composition_ms", "?")
        source = timing.get("sourcing_ms", "?")
        intake = timing.get("intake_ms", "?")
        created = (e.get("created_at") or "?")[:19]

        def fmt(v):
            if isinstance(v, (int, float)):
                return f"{v/1000:.1f}s"
            return str(v)

        print(f"{run_id:>12s}  {fmt(total):>8s}  {fmt(sem):>8s}  {fmt(sel_llm):>8s}  "
              f"{fmt(style):>8s}  {fmt(comp):>8s}  {fmt(source):>8s}  {fmt(intake):>8s}  {created:>20s}")

    # Summary
    print()
    def _get_timing(e):
        d = e.get("data") or {}
        if isinstance(d, str):
            d = json.loads(d)
        return d.get("timing", {})

    designs_with_timing = [
        e for e in events
        if "semaphore_wait_ms" in _get_timing(e)
    ]
    if designs_with_timing:
        waits = [_get_timing(e)["semaphore_wait_ms"] for e in designs_with_timing]
        llms = [_get_timing(e)["selection_llm_ms"] for e in designs_with_timing]
        print(f"Semaphore wait: min={min(waits)/1000:.1f}s  max={max(waits)/1000:.1f}s  avg={sum(waits)/len(waits)/1000:.1f}s")
        print(f"Selection LLM:  min={min(llms)/1000:.1f}s  max={max(llms)/1000:.1f}s  avg={sum(llms)/len(llms)/1000:.1f}s")
    else:
        print("No events with decomposed timing (semaphore_wait_ms) found yet.")
        print("Run Test B after the latest deploy to generate them.")


if __name__ == "__main__":
    main()
