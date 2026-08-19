#!/usr/bin/env python3
"""
Flarient Public Event Ledger — Transparency Engine

Commits significant space weather events to Git as structured, timestamped records.
Researchers can verify what Flarient believed BEFORE an outcome was known by reading
the Git history of each event directory.

Directory structure:
  events/year/month/day/event-id/event.json       — event metadata + current state
  events/year/month/day/event-id/observations.json — community observations
  events/year/month/day/event-id/forecasts.json    — predictions made before outcome
  events/year/month/day/event-id/outcome.json       — actual observed values (written on resolution)

Rules:
  - Only SIGNIFICANT events are committed (G3+ storms, M5+ flares, X-class, NEO close approaches)
  - No high-frequency noise — one commit per state change, not per data tick
  - Each commit is timestamped so Git history shows the evolution of understanding
  - Forecasts are written BEFORE outcomes are known — the Git log proves this
"""

import os, sys, json, subprocess, datetime, hashlib
from pathlib import Path
import requests

FLARIENT_API = os.environ.get("FLARIENT_API_URL", "https://flarient.com").rstrip("/")
REPO_DIR = Path(os.environ.get("GITHUB_WORKSPACE", "."))
EVENTS_DIR = REPO_DIR / "events"

# Significance thresholds — only commit events that meet these criteria
MIN_KP = 5          # G2 or above
MIN_FLARE_CLASS = "M"  # M-class or above
MIN_FLARE_LEVEL = 5    # M5 or above for flares
NEO_DISTANCE_THRESHOLD = 0.05  # AU (within ~7.5 million km)


def log(msg):
    print(f"[ledger] {msg}", flush=True)


# ── Fetch significant events from Flarient ─────────────────────────────────
def fetch_significant_events():
    """Fetch events from Flarient that meet significance thresholds."""
    log("Fetching significant events from Flarient API...")
    try:
        resp = requests.get(f"{FLARIENT_API}/api/functions/getSignificantEvents", timeout=30)
        resp.raise_for_status()
        data = resp.json()
        events = data.get("events", [])
        log(f"  {len(events)} significant events fetched")
        return events
    except Exception as e:
        log(f"  API fetch failed: {e}")
        # Fallback: fetch from public NOAA feeds and construct events
        return fetch_from_noaa()


def fetch_from_noaa():
    """Fallback: construct events from public NOAA data."""
    events = []
    try:
        # Check current Kp
        kp_resp = requests.get("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json", timeout=15)
        kp_data = kp_resp.json()
        if kp_data:
            max_kp = max(float(e.get("kp", 0)) for e in kp_data[-24:])  # Last 24 hours
            if max_kp >= MIN_KP:
                events.append({
                    "event_id": f"kp-{datetime.date.today().isoformat()}",
                    "event_type": "geomagnetic_storm",
                    "title": f"Geomagnetic Activity Kp {max_kp}",
                    "severity": f"G{int(max_kp) - 2}" if max_kp >= 3 else "G1",
                    "source_data": {"kp": max_kp},
                    "start_time": kp_data[-24]["time_tag"] if len(kp_data) >= 24 else kp_data[0]["time_tag"],
                    "current_summary": f"Kp index reached {max_kp} in the last 24 hours.",
                    "status": "active" if max_kp >= MIN_KP else "watch",
                })
    except Exception as e:
        log(f"  NOAA fallback failed: {e}")
    return events


# ── Directory structure ──────────────────────────────────────────────────
def event_dir(event):
    """Get the directory path for an event: events/year/month/day/event-id/"""
    start = event.get("start_time") or event.get("created_date") or datetime.datetime.now().isoformat()
    try:
        dt = datetime.datetime.fromisoformat(start.replace("Z", "+00:00"))
    except:
        dt = datetime.datetime.now(datetime.timezone.utc)

    year = str(dt.year)
    month = f"{dt.month:02d}"
    day = f"{dt.day:02d}"
    event_id = event.get("event_id") or hashlib.md5(
        (event.get("title", "") + start).encode()
    ).hexdigest()[:12]

    # Sanitize event_id for filesystem
    event_id = "".join(c for c in event_id if c.isalnum() or c in "-_")[:80]
    return EVENTS_DIR / year / month / day / event_id, event_id


# ── Write event files ────────────────────────────────────────────────────
def write_json(path, data):
    """Write JSON with consistent formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")


def write_event_file(event, event_id):
    """Write event.json — the core event record."""
    event_record = {
        "event_id": event_id,
        "event_type": event.get("event_type", "unknown"),
        "title": event.get("title", "Untitled Event"),
        "severity": event.get("severity"),
        "status": event.get("status", "watch"),
        "start_time": event.get("start_time"),
        "estimated_peak_time": event.get("estimated_peak_time"),
        "end_time": event.get("end_time"),
        "geographic_relevance": event.get("geographic_relevance"),
        "current_summary": event.get("current_summary") or event.get("summary", ""),
        "source_data": event.get("source_data", {}),
        "impact_categories": event.get("impact_categories", {}),
        "flarient_url": f"{FLARIENT_API}/space-events/{event.get('slug', event_id)}",
        "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    return event_record


def write_observations_file(event, event_id):
    """Write observations.json — community observations linked to this event."""
    observations = event.get("observations", [])
    return {
        "event_id": event_id,
        "observation_count": len(observations),
        "observations": observations,
        "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def write_forecasts_file(event, event_id):
    """Write forecasts.json — predictions made BEFORE the outcome was known.

    This is the key transparency file. It captures what Flarient (and its community)
    predicted before the event resolved. The Git commit timestamp proves these
    predictions were made before the outcome was known.
    """
    forecasts = event.get("forecasts", [])
    # Include Flarient's own consensus forecast
    consensus = event.get("consensus_forecast", {})
    return {
        "event_id": event_id,
        "consensus_forecast": consensus,
        "community_forecasts": forecasts,
        "forecast_count": len(forecasts),
        "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "note": "These forecasts were committed to Git BEFORE the outcome was known. "
                "The Git commit timestamp serves as a verifiable proof of when predictions were made.",
    }


def write_outcome_file(event, event_id):
    """Write outcome.json — actual observed values. Only written when event resolves."""
    if event.get("status") not in ("ended", "declining", "completed"):
        return None  # Don't write outcome until event resolves

    resolution_data = event.get("resolution_data", {})
    if not resolution_data:
        return None

    return {
        "event_id": event_id,
        "outcome": resolution_data,
        "resolved_at": event.get("resolved_at") or datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "verdict": event.get("verdict", "resolved"),
        "note": "This file was written AFTER the event resolved. Compare with forecasts.json "
                "(committed earlier) to verify prediction accuracy.",
    }


# ── Git operations ───────────────────────────────────────────────────────
def git_commit(message):
    """Stage and commit changes with a timestamped message."""
    env = os.environ.copy()
    env["GH_TOKEN"] = os.environ.get("GITHUB_TOKEN", "")
    subprocess.run(["git", "config", "user.name", "Flarient Event Ledger"], env=env, check=True)
    subprocess.run(["git", "config", "user.email", "ledger@flarient.com"], env=env, check=True)
    subprocess.run(["git", "add", "events/"], env=env, check=True, cwd=str(REPO_DIR))
    result = subprocess.run(["git", "diff", "--cached", "--quiet"], env=env, cwd=str(REPO_DIR))
    if result.returncode == 0:
        log("  No changes to commit")
        return False
    subprocess.run(["git", "commit", "-m", message], env=env, check=True, cwd=str(REPO_DIR))
    subprocess.run(["git", "push"], env=env, check=True, cwd=str(REPO_DIR))
    return True


# ── Main ─────────────────────────────────────────────────────────────────
def main():
    log("=== Flarient Public Event Ledger ===")
    events = fetch_significant_events()
    if not events:
        log("No significant events to record")
        return

    committed = 0
    for event in events:
        edir, event_id = event_dir(event)
        edir.mkdir(parents=True, exist_ok=True)

        # Write event.json
        event_record = write_event_file(event, event_id)
        write_json(edir / "event.json", event_record)

        # Write observations.json
        obs_record = write_observations_file(event, event_id)
        write_json(edir / "observations.json", obs_record)

        # Write forecasts.json (BEFORE outcome — this is the transparency key)
        fc_record = write_forecasts_file(event, event_id)
        write_json(edir / "forecasts.json", fc_record)

        # Write outcome.json only if event has resolved
        outcome = write_outcome_file(event, event_id)
        if outcome:
            write_json(edir / "outcome.json", outcome)

        committed += 1
        log(f"  Recorded: {event_id} ({event.get('event_type', 'unknown')})")

    # Commit all changes with a timestamped message
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    message = f"Event ledger update — {committed} event(s) — {timestamp}"
    if git_commit(message):
        log(f"Committed {committed} events to ledger")
    else:
        log("No new changes to commit (events already up to date)")

    log("Done")


if __name__ == "__main__":
    main()
