# Cost Estimation Engine

A Streamlit application backed by Snowflake, sharing its foundation with the
[`data-quality-app`](../data-quality-app): the same Snowflake client, env-driven
settings, `mock`/`snowflake` data-source switch, global theme, session/router
plumbing, and test + CI harness.

> **Status:** scaffold. The reusable foundation is in place and
> `streamlit run app.py` works (placeholder home screen). The Cost Estimation
> Engine domain logic (data model, workflow steps, computations) is added on
> top of this base once the specification is wired in.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env          # fill in Snowflake creds for snowflake mode
streamlit run app.py          # or: make run
```

By default `DATA_SOURCE=mock`, so the app and tests run with no Snowflake
connection.

## Run the tests / lint

```bash
DATA_SOURCE=mock pytest -q    # or: make test
ruff check .
```

CI ([.github/workflows/tests.yml](.github/workflows/tests.yml)) runs
`ruff check` then `pytest` with `DATA_SOURCE=mock`.

## Layout

```
app.py                  # Streamlit router (current_step -> renderer)
config/
  settings.py           # env-driven Settings dataclass (DATA_SOURCE + Snowflake)
src/
  snowflake_client.py   # thin connector wrapper (fetch_table / fetch_query + shared client)
  mock_data.py          # deterministic synthetic data (RNG reseed contract)
ui/
  _theme.py             # one global stylesheet (status colours via sentinels)
  step_home.py          # placeholder landing step
utils/
  colors.py             # STATUS_GREEN/YELLOW/RED - single source for status hexes
  session_state.py      # slim re-export shim over utils/session/*
  session/
    state.py            # STEPS, init_state
    sidebar.py          # sidebar CSS / brand / sample-mode toggle / footer
tests/
  conftest.py           # autouse: pin DATA_SOURCE=mock
```

## Relationship to data-quality-app

This project deliberately reuses the proven patterns from the Data Quality app:

- **`mock` / `snowflake` data sources** via `DATA_SOURCE` and one `Settings`
  dataclass.
- **One shared Snowflake client** per process (`get_shared_client`) with an
  Arrow fast path (`fetch_table`) and a schema-resilient rows path
  (`fetch_query`).
- **One global stylesheet**; status colours live only in `utils/colors.py`.
- **Deterministic mock data** via `_reseed_rng_for` (stable `crc32` seed).
- **Same test/CI harness**: pytest with a mock-pinning autouse fixture, ruff,
  pre-commit, GitHub Actions.
