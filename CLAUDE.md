# CLAUDE.md

Guidance for Claude Code (and other AI assistants) working in this repo.

## What this app is

The **Cost Estimation Engine** - a Streamlit app backed by Snowflake. It was
bootstrapped from the sibling [`data-quality-app`](../data-quality-app) and
deliberately reuses that project's foundation: the Snowflake client, env-driven
settings, `mock`/`snowflake` data-source switch, global theme, session/router
plumbing, and the test + CI harness.

> **Status:** scaffold. Only the shared foundation exists today. The domain
> logic (data model, workflow steps, cost computations) is added on top once
> the Cost Estimation Engine specification is provided.

## Foundation that already exists (carried over from data-quality-app)

- `config/settings.py` - frozen `Settings` dataclass driven by env vars
  (`DATA_SOURCE`, Snowflake creds, `MAX_ROWS_PER_TABLE`). `SETTINGS.is_mock`.
- `src/snowflake_client.py` - `SnowflakeClient` with `fetch_table` (Arrow fast
  path) and `fetch_query` (rows path, resilient to Arrow chunk-schema
  mismatch); a process-wide shared client (`get_shared_client` /
  `close_shared_client`). User literals go through `%s` params, never string
  concat (injection-safe). Per-domain database/schema resolution was stripped
  (no domain registry yet) - `_resolve_location()` reads `SETTINGS` directly;
  reintroduce the domain-preferring version if/when CEE grows domains.
- `src/mock_data.py` - the determinism contract: one shared stateful `RNG`,
  reseeded per builder via `_reseed_rng_for(name)` (stable `zlib.crc32`, NOT
  the salted built-in `hash`), "recent" dates anchored to `_MOCK_NOW` captured
  once at import. Builders are stubs awaiting the spec.
- `ui/_theme.py` - one global stylesheet; the three status hexes live ONLY in
  `utils/colors.py` and are injected via `__GREEN__`/`__YELLOW__`/`__RED__`
  sentinels. Don't reintroduce a per-step `<style>` block or a hardcoded hex.
- `app.py` - `current_step -> renderer` router; one sidebar build + one global
  CSS inject per render.
- `utils/session/` - `state.py` (STEPS, `init_state`) + `sidebar.py` (CSS,
  brand, sample-mode toggle, footer); `utils/session_state.py` is a slim
  re-export shim.

## Patterns to follow (inherited)

- **One global stylesheet; colours in one module.** Status hexes live only in
  `utils/colors.py`. A re-brand is one edit.
- **Slim re-exports preserve public API.** `utils/session_state.py` re-exports
  from `utils/session/*`. Add new symbols to BOTH the sub-module and `__all__`.
- **Tests always run against `mock`** - the autouse fixture in
  `tests/conftest.py` pins `SETTINGS.data_source = "mock"` regardless of the
  shell env, patching the instance on every module that imported it.
- **`from __future__ import annotations` everywhere** - missing `typing`
  imports won't fail at runtime but `ruff check` catches them (F821).
- **`.env.example` holds placeholders only** - real creds go in `.env`
  (gitignored).

## How to run things

```bash
pip install -r requirements.txt
streamlit run app.py            # also: make run
DATA_SOURCE=mock pytest -q      # also: make test
ruff check .                    # matches CI
```

CI ([.github/workflows/tests.yml](.github/workflows/tests.yml)) runs
`ruff check` then `pytest` with `DATA_SOURCE=mock` (`--cov-fail-under=90`).

## Adding the domain logic

When the Cost Estimation Engine spec lands, build domain modules under `src/`
and `config/`, add workflow steps as `ui/step_*.py` renderers wired into
`STEP_RENDERERS` in `app.py`, extend `STEPS`/`STEP_LABELS` in
`utils/session/state.py`, and add the navigation/sidebar progress plumbing
following the data-quality-app split (`utils/session/navigation.py`). Keep any
automation UI-free and unit-tested (the way `src/one_click.py` is in the
sibling app).
