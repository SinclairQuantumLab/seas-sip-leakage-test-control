# Validation evidence

## Initial implementation, 2026-09-18

- 21 offline pytest cases passed using a fake device and monotonic clock.
  Coverage includes CSV action/observation separation, immediate flush before
  writes and between reads, actual versus requested values, final hold duration,
  short holds, slow-read scheduling, errors/Ctrl+C, file-write failure, voltage
  sequences, input checks, and transport selection.
- Ruff passed for app, tests, and notebook source.
- `uv build` produced an sdist and wheel. Both the module and console entry
  point displayed their help successfully.
- `plot_logs.ipynb` cells matched `plot_logs.py` and had no saved execution
  outputs. A separate synthetic-data check executed the plot cells with a
  noninteractive backend: six observations and two actions loaded, a partial
  trailing row was excluded, and both plots rendered. A header-only CSV also
  loaded and plotted successfully.
- Imports resolved to this workspace's app and library checkouts. The library
  worktree was unchanged. No live device connection or control was performed.

## Agent-file organization and root script, 2026-09-18

- Moved the existing test module from `tests/test_app.py` to
  `.agents/test_app.py`; changed pytest discovery and documented lint commands.
- Added root `AGENTS.md`, handoff, decisions, and this evidence record.
- Moved runtime code to root `main.py` and adjusted test imports. Removed the
  app's package/build configuration and console entry point at the user's request.
- The build evidence above is historical, not a required workflow. Do not create
  further distributions for this project.
- `uv sync --group notebook` updated the environment and lockfile for the
  non-package project, removing the previous editable app installation.
- Ran the existing suite once after the move: `uv run --locked pytest -q`,
  21 passed in 0.20 s. The environment's `python main.py --help` also passed.
- Removed the generated `dist/` files and the old `src/` and `tests/` directories.
  No new tests, distribution build, notebook execution, or device I/O was added.

## Artifact language correction, 2026-09-18

- Translated README to English and recorded the user's English-only artifact
  rule in global/project instructions and project decisions.
- Documentation-only change; no runtime tests or builds were rerun.

## Settings arguments and CSV unit symbols, 2026-09-18

- Updated positional/`--settings` input, retained `--config`, and corrected CSV
  unit-symbol case. Updated existing CSV assertions and plotting columns.
- Existing tests passed once: 21 passed in 0.20 s. Mocked CLI checks covered
  default, positional (including spaces), `--settings`, and `--config` paths.
- Verified unit headers and synchronized notebook cell inputs without executing
  the notebook or connecting to a device. Prior notebook inputs matched the
  source and contained no saved outputs before regeneration.

## Control-action stdout, 2026-09-18

- Added one stdout line per voltage-control action; samples remain CSV-only.
- Ran the single affected test (1 passed) and Ruff on the changed Python files.
  No device I/O or broader test run was performed.

## Ramp and settings restoration, 2026-09-18

- Confirmed in the vendor manual that `Vout Ramp Intv` is limited to 1–60
  seconds. The app therefore requests the supported minimum of 1000 ms on the
  first voltage step; the library's lower bound was not changed.
- Added a pending TOML backup containing only the original voltage setpoint and
  ramp interval. Cleanup reapplies both once, logs the intent, records a
  readback, and renames the backup to `restore_confirmed` only when both values
  match.
- Ran the two directly affected offline test groups: 5 passed, 16 deselected.
  Ruff passed for `main.py`, `.agents/test_app.py`, and `plot_logs.py`. No live
  device I/O was performed.
- Updated the local notebook without execution. The changed loading cell's old
  outputs were cleared by Jupytext; the matching plot-cell output and notebook
  input were preserved.
