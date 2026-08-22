# Flarient Public Event Ledger

A transparent, versioned record of significant space weather events. Uses **Git history** as a transparency layer — researchers can verify what Flarient believed **before** an outcome was known by reading the commit log.

## Why this exists

Forecasting is only credible if predictions are timestamped before outcomes are known. This repository commits Flarient's event records, community observations, and forecasts to Git, creating a permanent, verifiable audit trail.

## Directory Structure

\`\`\`
events/
  year/
    month/
      day/
        event-id/
          event.json          — event metadata + current state
          observations.json   — community observations
          forecasts.json      — predictions made BEFORE outcome (key transparency file)
          outcome.json         — actual observed values (written on resolution)
\`\`\`

### Example

\`\`\`
events/2026/08/12/g4-geomagnetic-storm/
  event.json          — "G4 Geomagnetic Storm — Kp reached 8.0"
  forecasts.json      — committed 2026-08-12T14:00Z (before storm peaked)
  observations.json   — community aurora sightings
  outcome.json         — committed 2026-08-13T06:00Z (after storm resolved)
\`\`\`

The Git log shows that `forecasts.json` was committed **before** `outcome.json`, proving the predictions were made without knowledge of the result.

## What gets recorded

Only **significant** events are committed — no high-frequency noise:
- Geomagnetic storms G3 or above (Kp ≥ 6)
- M5+ solar flares (M-class and above)
- X-class solar flares
- Near-Earth object close approaches (< 0.05 AU)
- Major astronomical events (eclipses, meteor showers)

## How it works

1. A GitHub Action runs every 3 hours
2. Fetches significant events from the Flarient API
3. Creates structured JSON files in the event directory
4. Commits to Git with a timestamped message
5. When events resolve, `outcome.json` is added in a separate commit

## Transparency guarantees

- **Forecasts are committed before outcomes** — Git timestamps prove this
- **No retroactive edits** — corrections are new commits, not rewrites (Git history preserves the original)
- **Public repository** — anyone can audit the full history
- **Structured data** — JSON files are machine-readable for research

## Using the ledger for research

\`\`\`bash
# Clone the full history
git clone https://github.com/flarientglobal/flarient-event-ledger.git

# See what Flarient predicted before a specific storm resolved
git log --before="2026-08-13T06:00:00Z" -- events/2026/08/12/g4-geomagnetic-storm/forecasts.json

# Compare with the actual outcome
cat events/2026/08/12/g4-geomagnetic-storm/outcome.json
\`\`\`

## Cost

**Free** — runs on GitHub Actions, data from public APIs.

## About

Built by [Flarient](https://flarient.com) — the space weather intelligence platform. Part of the [Flarient Constellation](https://github.com/flarientglobal/flarient-constellation).

## License

MIT — the event ledger data is open for research and verification.
