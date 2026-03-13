# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python CLI tool (`sts-query`) that bulk-queries the Society of Thoracic Surgeons (STS) Short-Term Risk Calculator via WebSocket. It reads patient data from CSV, validates fields against STS parameter constraints, sends each patient record to the STS Shiny app at `acsdriskcalc.research.sts.org`, and writes mortality/complication predictions to an output CSV.

## Commands

```bash
# Install from source
pip install .

# Run the tool
sts-query --csv sample_data.csv --output results.csv

# Dry run (validate only, no API calls)
sts-query --csv sample_data.csv --dry-run

# Override parameters for all patients
sts-query --csv sample_data.csv --output results.csv --override age=50 dialysis=Yes
```

There are no tests or linting configured.

## Architecture

This is a single-file Python project (`sts_query.py`) published as `sts-risk-calculator` on PyPI.

**Data flow:** CSV input → `validate_and_return_csv_data()` → `translate_csv_to_shiny()` (backward-compat value mapping) → `prepare_websocket_messages()` (builds Shiny protocol JSON) → `query_sts_api_async()` (WebSocket send/receive) → `parse_sts_html_response()` (regex extraction from HTML table) → CSV output.

**Key design details:**
- The STS calculator is a black-box Shiny app — all computation is server-side. The tool mimics a browser WebSocket client.
- `translate_csv_to_shiny()` maps old REST API parameter values to current Shiny app values, maintaining backward compatibility with existing CSV datasets.
- Several CSV fields get merged into single Shiny fields (e.g., `diabetes`+`diabctrl` → `diabetes`, `cvd`+`cva`+`cvawhen`+`cvdtia` → `cvd` array, `iabpwhen`+`cathbasassistwhen`+`ecmowhen` → `mcs` array). These use `_`-prefixed intermediate keys.
- The WebSocket protocol requires an `init` message (full state with defaults) followed by an `update` message (only patient-specific values).
- Validation uses assertions extensively — invalid data causes immediate failure with descriptive messages.

## Code Style

- Formatted with Black
- Requires Python ≥ 3.9 (uses `dict |` merge operator)
- Dependencies: `websockets`, `tqdm`
