# Handoff

Updated 2026-10-13, America/Chicago.

## Environment repair, 2026-10-13

- Diagnosed `ModuleNotFoundError: No module named 'seas_sip_client'`: the
  installed editable finder still pointed to the former OneDrive/ASUS checkout,
  although the library source existed in the current workspace.
- Reinstalled only the library with
  `uv sync --locked --inexact --reinstall-package py-seas-sip-power`.
  Import now resolves to this workspace's `py-seas-sip-power/seas_sip_client.py`.
- Import, CLI help, and all 23 existing offline tests passed. No device I/O
  occurred. Application code, configuration, and library source were unchanged.
- After relocating a checkout, reinstall the editable library if its generated
  import finder retains an old absolute path; ordinary sync may consider the
  existing installation current.

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
  plus intended after-test settings in an `after_test_pending` TOML file. The
  first voltage command requests the minimum supported 1000 ms ramp interval.
  Default cleanup keeps the voltage setpoint and restores only the original
  ramp interval. Matching requested-settings readback renames the snapshot to
  `after_test_confirmed`; this does not confirm physical voltage arrival.
- Optional `[after_test]` defaults to `enabled = false`, `voltage_v = "previous"`,
  and `transition_time_s = 10`. The voltage can be the initial setpoint or a
  fixed integer from 1000 to 6000 V. An enabled transition uses a fresh setpoint read
  and a linear software schedule with approximately one-second updates, missed
  ticks skipped, and a final target request at or after the deadline. Actual
  output arrival is not guaranteed. Errors/Ctrl+C also run the enabled transition
  after a settings request. Ramp restoration is attempted even if it fails.
- The template includes the optional section as a commented example. The
  current ignored `settings.toml` has its entire `[after_test]` section
  commented out by the user. Existing local connection/measurement values were
  preserved; after-test transition remains disabled.
- Procedure errors are printed before cleanup is announced. Normal completion
  is also announced before after-test commands.
- Each settings command is preceded by a flushed action CSV row. Successful
  samples from recording holds become flushed `observation` rows with all status
  fields. Initial, soak, and restoration reads are not measurement rows.
- Every device command gets the total attempt count and retry interval configured
  under `[connection]`. Failures are terminal-only. An exhausted scheduled read
  skips one sample while the voltage sequence continues; initial-read and
  control/after-test failures abort.
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
  holds begin after the gap. Ramp restoration retains its one-second readback delay.
- `plot_logs.py` is the tracked notebook source; `plot_logs.ipynb` has been
  generated locally. It reloads a chosen/latest CSV on cell execution and plots
  V(t), I(t), action timestamps, and raw I-V samples.
- Plot loading accepts `after_test_voltage` and `restore_ramp_interval` actions as
  well as historical `restore_settings` and `cool_voltage`. A local `plot_logs.ipynb` was generated
  without execution; existing per-log notebooks and their outputs were preserved.
- `compare_magnet_logs.py` is a separate tracked Jupytext source comparing
  `20260919_025053_048080Z.csv` as `Magnet` with
  `20260919_030322_046377Z.csv` as `No magnet`. Its final plot overlays faint
  raw observations and connected median-current points with IQR error bars.
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
- The user requested local commits of the existing work on 2026-10-13, split by
  editing scope: single-log plots and dependencies, magnet comparison, notebook
  maintenance policy, and environment repair records. Those four commits were
  created. The user subsequently reported that the after-test changes work and
  requested committing and pushing the current work, including those commits.
  Recheck Git status and remote synchronization before continuing.
- The requested optional after-test voltage is implemented. Offline validation
  and the user's reported success are recorded in VALIDATION.md. Preserve
  settings, measurements, and notebook work during edits.
