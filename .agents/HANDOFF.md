# Handoff

Updated 2026-09-18, America/Chicago.

## Current state

- The requested fixed-step CLI and CSV-only plotting notebook are implemented.
- Runtime code is root `main.py`. Use `uv sync`, then `uv run main.py`, or
  activate the environment and run `python main.py`. A positional path or
  `--settings` selects another settings file; `--config` remains an alias.
  No input defaults to `settings.toml`. This project has no package build.
- The default local settings filename is `settings.toml`; copy from
  `settings.toml.template`. The template links to the library README for
  connection details. Local settings and timestamped `results/*.csv` are ignored.
- Before control, the app saves the original voltage setpoint and ramp interval
  in a `restore_pending` TOML file. The first voltage command also requests the
  device's minimum supported 1000 ms ramp interval. On cleanup it restores both
  settings; matching readback renames the file to `restore_confirmed`.
- Procedure errors are printed before cleanup announces restoration. Normal
  completion is also announced before the restore request.
- Each settings command is preceded by a flushed action CSV row. Successful
  samples from recording holds become flushed `observation` rows with all status
  fields. Initial, soak, and restoration reads are not measurement rows.
- Every device command gets the total attempt count and retry interval configured
  under `[connection]`. Failures are terminal-only. An exhausted scheduled read
  skips one sample while the voltage sequence continues; initial-read and
  control/restoration failures abort.
- CSV headers preserve unit-symbol case, such as `output_voltage_V` and
  `output_current_nA`. The plotting notebook also accepts older lowercase headers.
- Stdout prints the CSV path and one line per voltage-control action. Sampling
  remains CSV-only; action lines include time, voltage delta/target, last current,
  and soak or hold time.
- The starting voltage uses `initial_voltage_soak_time_s` without CSV recording,
  followed by a full `hold_time_s` recording period. Later voltages each use the
  same full recording hold. Both values are required.
- Successful device commands are separated from the next command by at least
  0.1 seconds. The first set-to-read gap is part of the soak; later recording
  holds begin after the gap. Restoration retains its one-second readback delay.
- `plot_logs.py` is the tracked notebook source; `plot_logs.ipynb` has been
  generated locally. It reloads a chosen/latest CSV on cell execution and plots
  V(t), I(t), action timestamps, and raw I-V samples.
- The user requested agent-owned tests and working files under `.agents/`.
  Tests now live in `.agents/test_app.py`; pytest discovery and README commands
  are updated. Root `AGENTS.md` records this rule for future work.

## Boundaries for continuation

- All authored artifacts must be in English. Conversation may be in Korean.
- The user's language rule is also recorded in `~/.codex/AGENTS.md`.
- Keep the app simple. The user rejected autonomous stability decisions,
  experiment metadata entry, pressure acquisition, and automatic interpretation.
- Runtime does not start or stop HV; the user operates it. No agent-run device
  connection or live measurement has occurred. Offline results are recorded in
  `VALIDATION.md`.
- The library is its own repository. This work has not modified its files.
- Keep work and validation small. The user explicitly rejected unnecessary
  packaging and excessive verification. Agent tests stay in `.agents/`.
- At the time of this handoff, the outer project files are untracked; no commit
  or push has been requested or performed. Recheck status rather than assuming
  this remains true.
- No pending feature request remains from the current implementation. Preserve
  the user's settings, measurements, and notebook work during future edits.
