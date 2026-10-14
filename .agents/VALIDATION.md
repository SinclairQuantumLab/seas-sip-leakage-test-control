# Validation evidence

## User feedback and publication request, 2026-10-13

- The user reported that the changes work and requested commit and push.
  No device-operation details or measurement evidence were supplied with that
  report; the agent has performed only the offline checks recorded below.
- No further runtime changes were made for publication, so the passing checks
  below were not repeated. Local settings, CSVs, and notebooks remain ignored.

## After-test voltage terminology, 2026-10-13

- Renamed configuration comments, CLI messages, documentation, and the CSV
  intent event to after-test voltage (`after_test_voltage`). Plot loading still
  accepts older `cool_voltage` rows. Transition behavior is unchanged.
- Preserved the user's fully commented after-test section in `settings.toml`.
  Offline loading confirms `enabled = false`. Omitting only the enabled field
  also selects false. Documented that commenting only the TOML section header
  while leaving its keys active assigns them to the preceding section.
- `uv run --no-sync pytest -q -k 'after_test or transition'`: 19 passed,
  23 deselected in 0.34 s. No new tests or hardware operations were added.
- Inspected and backed up the existing local plotting notebook, then updated
  it with Jupytext without execution. No render or cell-equivalence checks.

## Optional after-test cool voltage, 2026-10-13

- Replaced automatic voltage restoration with default-disabled `[after_test]`
  cooling. The user selected a linear software setpoint transition rather than
  using the device's 0-to-setpoint ramp interval as the transition duration.
- Existing offline cases now verify ramp-only cleanup and blank requested
  voltage on `restore_ramp_interval`. Added coverage for previous/fixed cool
  targets, upward/downward transitions, CSV flush before every cooling write,
  deadline timing, short transitions, missed ticks, option validation,
  configuration loading, procedure errors/Ctrl+C, and cooling failures.
- `uv sync --locked --inexact --group notebook` completed without changing
  the lockfile. `uv run --no-sync pytest -q`: 42 passed in 0.48 s.
  `uv run --no-sync ruff check main.py .agents plot_logs.py`: passed.
- Inspected the three existing local notebooks' input selections and saved
  output counts before generating `plot_logs.ipynb` with
  `uv run --group notebook jupytext --to ipynb --update plot_logs.py`. Existing
  comparison and per-log notebooks were untouched. No notebook execution,
  render checks, or cell-equivalence checks were performed.
- Added the fully commented optional section to the tracked template and an
  active default-disabled section to the current ignored settings file,
  preserving its existing connection and measurement configuration.
- Loaded both settings files offline: each resolves to disabled cooling with
  previous voltage and a 10-second transition. The current measurement inputs
  remain 1000/200/5000 V, 10-second soak/hold, and 1-second sampling.
- Library source, measurement data, and HV state were not changed. All tests
  used fakes; no live device I/O or hardware qualification occurred.

## Editable import repair, 2026-10-13

- Before repair, `uv run --no-sync python` reported the project's current
  `.venv/Scripts/python.exe` and installed distribution version 0.1.0, but
  `importlib.util.find_spec('seas_sip_client')` returned `None`. The generated
  editable finder pointed into the former OneDrive/ASUS checkout; that module
  path did not exist.
- Ran `uv sync --locked --inexact --reinstall-package py-seas-sip-power`:
  rebuilt and reinstalled only the local editable library, keeping the lockfile
  and extra installed packages.
- `uv run --no-sync python -c "import seas_sip_client; print(seas_sip_client.__file__)"`
  resolved to the current workspace's library source.
- `uv run --no-sync main.py --help` passed without loading settings or opening
  a device connection. `uv run --no-sync pytest -q`: 23 passed in 0.29 s.
- No application/library source or notebook changes, notebook execution, or
  live device I/O occurred. Ruff was not rerun for this environment-only repair.

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

## Initial voltage soak, 2026-09-18

- Added the required `initial_voltage_soak_time_s` setting for the starting
  voltage; later voltage steps continue to use `hold_time_s`.
- Ran the single directly affected scheduling check: 1 passed in 0.08 s. No
  live device I/O was performed.

## Device command spacing and error ordering, 2026-09-18

- Added a minimum 0.1-second gap after successful device commands; restoration
  retains its longer one-second set-to-read gap. The gap is included in soak and
  hold timing.
- Procedure errors are now printed before the cleanup/restoration announcement.
- Ran the single directly affected scheduling check: 1 passed in 0.07 s. No
  additional live device I/O was performed.

## Recording window and command retries, 2026-09-18

- Starting-voltage soak reads are excluded from CSV, followed by a full
  recording hold. Initial status and restoration readback are also excluded.
- Retry count and interval are parsed from `[connection]`; the count is the total
  attempts per command. Failures remain terminal-only, and an exhausted
  scheduled read skips one sample without stopping the voltage sequence.
- Ran the existing offline suite once: 23 passed in 0.24 s. Ruff passed for the
  changed app and test files. No live device I/O was performed.
