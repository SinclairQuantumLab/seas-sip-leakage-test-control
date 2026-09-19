# Durable decisions

- 2026-09-18: Do not print individual samples to stdout. Print one concise line
  per voltage-control action with its UTC timestamp, voltage change and target,
  last observed current, and hold time. Read the initial status so the first
  step also has a current observation.

- 2026-09-18: Accept a positional settings path or `--settings`; keep `--config`
  as an alias and default to `settings.toml` when omitted. CSV unit symbols must
  retain their proper case. Settings keys and the library API remain unchanged.

- 2026-09-18: English is mandatory for every authored artifact across all
  projects and threads. Korean conversation does not imply Korean deliverables.
  The rule is recorded in global and project `AGENTS.md`; README is in English.

- 2026-09-18: The app is a fixed-step control and recording tool. Experimental
  conditions, strategy, stability assessment, and interpretation belong to the
  user. Do not add experiment/run IDs, magnet/pump/cable/valve metadata, expected
  serial-number checks, current-driven control policies, or external pressure
  collection unless requested.
- Measurement settings are start/step/stop voltage, a separate starting-voltage
  soak time, later-step hold time, and sampling interval. The soak setting is
  required. A negative step supports descending sequences; equal start and stop
  gives one soak. Stop is included if on the step grid, otherwise the sequence
  ends before crossing it.
- Runtime changes the voltage setpoint and requests a 1000 ms ramp interval on
  the first step. The manual specifies 1–60 seconds, so zero is not supported.
  HV start/stop remains manual. Before control, save only the original voltage
  setpoint and ramp interval in a `restore_pending` TOML file. Restore both once
  on normal completion, interruption, or error after a settings request and log
  `restore_settings`. Rename the backup to `restore_confirmed` only after a
  matching readback. Do not wait for the physical voltage ramp to finish.
- CLI + TOML + CSV are the user interface. Default file: `settings.toml`;
  template: `settings.toml.template`. Connection comments link to
  <https://github.com/SinclairQuantumLab/py-seas-sip-power#connections-and-access>.
- One CSV contains both `set_voltage` and `observation` events. Action intent is
  flushed before the command; observed values are never inferred from requests.
  UTC filenames are generated automatically. Every header/row is flushed.
- All `DeviceStatus` fields are preserved; `observed_at` becomes `timestamp`.
  The app performs no extra pressure calculation or measurement interpretation.
- Plotting is a separate user-facing notebook that reloads saved CSV data when
  cells execute. No live plotting service or device access in the notebook.
- 2026-09-18: Agent-created tests, validation scripts, scratch utilities, and
  working records belong in `.agents/` unless explicitly made for user use.
  The CLI, configuration template, and plotting notebook remain user-facing
  project files. Root `AGENTS.md` and `.agents/` notes must be maintained.
- 2026-09-18: Use root `main.py` with `uv sync` / `uv run main.py` or an activated
  environment's `python main.py`. Remove the application package layout, console
  entry point, build backend, and generated distributions. Do not add packaging
  or excessive validation to this simple script project.
