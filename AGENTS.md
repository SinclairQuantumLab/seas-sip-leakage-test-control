# Agent instructions

## Official language

All authored artifacts must be in English, including code, comments, documentation,
configuration comments, notebooks, and agent records. Conversation may be in
Korean; this does not change the artifact language. This is the user's global
rule across projects and threads, also recorded in `~/.codex/AGENTS.md`.

## Scope and user intent

This project is a small CLI that changes the SAES SIP POWER voltage in fixed
steps, holds each step for a fixed time, and appends device observations to CSV.
Keep experimental decisions with the user. Do not expand the app into an
autonomous experiment manager: no stability-based progression, current-based
abort policies, experiment metadata forms, independent pressure acquisition,
automatic interpretation, or live plotting unless requested.

Read [.agents/HANDOFF.md](.agents/HANDOFF.md),
[.agents/DECISIONS.md](.agents/DECISIONS.md), and
[.agents/VALIDATION.md](.agents/VALIDATION.md) when continuing work. Inspect Git
status and existing changes before editing; preserve user edits and local data.
Update these records when behavior, decisions, or validation evidence changes.

## File ownership

- `main.py`: user-facing CLI, settings loading, fixed
  voltage sequence, sampling, and CSV writing.
- `settings.toml.template`: tracked configuration template. `settings.toml` is
  the default local file and is Git-ignored. Keep the library README GitHub link
  in the connection comments.
- `plot_logs.py`: user-facing Jupytext source. `plot_logs.ipynb` is the generated
  local notebook. It only reads CSV snapshots when cells are run.
- `README.md`: user installation, settings, execution, and CSV/notebook usage.
- `.agents/`: agent-created tests, validation helpers, development notes, and
  handoff records. Put new agent working files here unless they are explicitly
  intended for the user. Do not create a top-level `tests/` for agent checks.
- `.agents/local/`: ignored scratch files and backups; do not commit run data or
  notebook outputs. Durable tests and notes elsewhere in `.agents/` are tracked.
- `docs/`: user-provided references. Preserve the source email and attachments.
- `results/`: ignored measurement CSVs; preserve existing files.
- `py-seas-sip-power/`: separate library repository and editable uv workspace
  dependency. Read its `AGENTS.md` and `README.md` before changing or integrating
  its device API. Do not silently restructure it or edit its internals as part
  of ordinary consumer work.

## Implementation contract

- This is a clone-and-run script project. Use `uv sync`, then `uv run main.py`,
  or activate the environment and use `python main.py`. Keep scripts at the
  project root. Do not add a `src/` package, console entry points, build backend,
  or distribution artifacts. The library keeps its own packaging.
- Connection setup chooses UDP, Modbus TCP, or Modbus RTU once. Command retry
  count and interval are connection settings. Use the common `SAESSIPPower` API
  afterward; keep device protocol details in the library.
- The measurement inputs are start/step/stop voltage, initial-voltage soak time,
  recording hold time, and sampling interval. Basic input checks are separate
  from experimental decision-making.
- At the starting voltage, poll through the soak without recording observations,
  then record for a full hold. Record for a full hold at every later voltage.
  Leave at least 0.1 seconds after each successful device command before issuing
  the next one, poll on a monotonic schedule, and skip missed sampling ticks.
- The app changes the voltage setpoint and temporarily requests the device's
  minimum supported ramp interval of 1000 ms. Starting/stopping HV belongs to
  the user. Read the initial status once and save only the original setpoint and
  ramp interval in a `restore_pending` TOML file. Restore both once after a
  settings request, including on errors and Ctrl+C; rename the file to
  `restore_confirmed` only after matching readback. Do not wait for the physical
  voltage ramp to finish. Closing never sends Start, Stop, Reset, or Clear Alarm.
- Print a procedure error before cleanup starts. Then announce whether the
  procedure aborted or completed before requesting restoration, so terminal
  output reflects the actual event order.
- Keep one timestamp-named CSV per invocation. `set_voltage` and
  `restore_settings` rows are written and flushed before their calls and record
  intent, not successful application.
  `observation` rows contain successful recording-hold samples only. Initial,
  soak, and restoration readbacks are not measurement observations. Keep
  requested voltage, observed setpoint, and actual output voltage distinct.
- Preserve all returned status fields; rename `observed_at` to UTC `timestamp`.
  CSV headers use proper unit-symbol case (`V`, `nA`, `K`, `W`, `A`, `Torr`);
  settings keys and library API names keep their existing spelling.
  Unknown observations stay blank. Give each device command the configured total
  number of attempts and print failures only to the terminal. After all attempts,
  skip a failed scheduled sample and continue the voltage sequence; initial-read,
  settings-write, and restoration failures abort. Flush the header and every row.
- The notebook snapshots the CSV, excludes any incomplete trailing line, and
  plots observations and action timestamps. It never accesses the device.
- Use offline fakes for development. A request to implement or test software
  does not by itself request live device I/O. Follow explicit user instructions
  for any actual measurement.

## Validation and notebook maintenance

From the project root:

```powershell
uv sync
uv run pytest -q
uv run ruff check main.py .agents plot_logs.py
```

Pytest discovers `.agents/test_app.py`. Keep verification proportional to the
change: use existing relevant checks once, do not add tests for simple file moves
or documentation changes, and do not build distributions. Record actual results
in `.agents/VALIDATION.md`, distinguishing offline checks from hardware evidence.

When changing `plot_logs.py`, inspect and preserve any newer local notebook
inputs and outputs first. Update the local notebook without executing it:

```powershell
uv sync --group notebook
uv run --group notebook jupytext --to ipynb --update plot_logs.py
```

Keep a usable local notebook, verify its cells match the source, and preserve
matching outputs. The notebook is ignored by Git; that does not make it
disposable. Do not rerun device operations as part of notebook verification.
