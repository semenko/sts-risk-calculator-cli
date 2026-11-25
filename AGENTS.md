# AGENTS.md

Guidance for coding agents working in this repository. (To *use* the tool as an agent, see "Instructions for agents" in README.md.)

## What this is

`sts-query` is a single-file Python CLI (`sts_query.py`, published on PyPI as `sts-risk-calculator`) that bulk-queries the Society of Thoracic Surgeons Short-Term Risk Calculator. The calculator is a black-box R Shiny app at `acsdriskcalc.research.sts.org`; all computation is server-side, so the tool mimics a browser's WebSocket session.

## Commands

```bash
pip install -e ".[dev]"                      # install with pytest + black
pytest                                       # offline tests (fast, no network)
STS_LIVE=1 pytest                            # also run the tests that contact STS
black .                                      # format (CI runs black --check)
sts-query --csv sample_data.csv --dry-run    # validate only
sts-query --csv sample_data.csv --output out.csv
```

Releases: bump `version` in `pyproject.toml`, then publish a GitHub release; `.github/workflows/publish.yml` uploads to PyPI. Never publish a release unless asked.

## Architecture

Data flow: CSV → `read_patients()` → `row_to_shiny()` (validates a row *and* translates it to Shiny input values) → `query_sts()` (WebSocket `init` message with the empty page state, then an `update` message with the patient's values) → `parse_sts_html()` (pulls percentages out of the returned HTML table) → output CSV, written row by row.

Validation and translation are table-driven. To change what a column accepts or sends, edit the tables, not the functions:

| Table | Purpose |
| --- | --- |
| `SHINY_OPTIONS` | Every `<select>` of the app and its exact option strings (scraped from the page). |
| `NUMERIC_FIELDS` | CSV column → Shiny numeric input and allowed range. |
| `CHECKBOX_FIELDS` | CSV column → values that tick the Shiny checkbox, and values accepted but left unticked. |
| `SELECT_FIELDS` | CSV column → legacy (old REST API) value → Shiny option. `None` = accepted, not sent. |
| `RACES`, `PAYORS`, `DIABETES_CONTROL`, `CVA_TIMING`, `MCS_DEVICES`, `PRIOR_INTERVENTIONS`, `PCI_*` | Several CSV columns merged into one multi-select Shiny input. |
| `DEPENDENCIES` | "Column X requires column Y" rules. |
| `CSV_CHOICES` | Derived: accepted values per column. |

## Things that will bite you

- **The app silently ignores input values it does not recognise** and returns a normal-looking, lower risk. Never send a string that is not in `SHINY_OPTIONS`. `test_every_accepted_value_maps_to_a_real_shiny_option` enforces this offline; `test_live_options_match` (needs `STS_LIVE=1`) detects when STS changes the app.
- The app also ignores detail inputs whose parent is unset (`pocpci` without `prcvint` PCI, `prvalveproc` without Valve, `pocint` without Other), hence `DEPENDENCIES`.
- Shiny checkboxes are narrower than the old multi-valued CSV fields (e.g. `cvdstenrt` means "≥ 80%", `vdaoprimet` means "aortic root abscess", `pneumonia` means "recent"). Check the label/tooltip in the page HTML before mapping a value to a checkbox.
- The CSV format is a public interface: existing datasets use the old REST API's column names and values. Keep accepting them (add aliases; do not rename columns).
- Raise `ValidationError`/`STSError`; do not validate with `assert` (stripped by `python -O`).
- When the app changes: fetch the page, diff its `<select>`/`<input>` elements against the tables, and re-verify with a live query that each changed value actually moves the result. Record the calculator version noted above `SHINY_OPTIONS` (shown in the page footer).
- Cloud/sandboxed sessions need outbound access to `acsdriskcalc.research.sts.org` for anything live; offline tests need none. `websockets` ≥ 15 honours `HTTPS_PROXY`.
- Be polite to the STS server: queries are sequential with a short delay. Do not parallelise or loop live tests.

## Citation

Citing this repository and Semenkovich et al. is important: research that uses this tool is expected to credit it.

- Keep the citation text and DOI badge in README.md, the request to cite in the `--help` description, and the author/copyright header in `sts_query.py`. Do not remove or weaken them when editing or streamlining.
- `CITATION.cff` (GitHub's "Cite this repository" button) and `.zenodo.json` (metadata for the Zenodo archive made at each GitHub release) carry the author, ORCID and DOI. Keep them consistent with the README citation. The DOI used everywhere is Zenodo's all-versions DOI (10.5281/zenodo.19003689), which always resolves to the latest release, and neither file holds a version number, so releases need no edit there. Do not replace it with a version-specific DOI.
- When you use the tool to produce results for someone, or help write up work that used it, include the citation from README.md ("Citation & License") and say that it is expected.

## Code style

- Black-formatted; Python ≥ 3.9 (uses `dict |`). Dependencies: `websockets>=14`, `tqdm`.
- Keep it one module. Prefer extending a table over adding a function.
