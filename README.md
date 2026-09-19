# seas-sip-leakage-test-control

A small CLI that uses `py-seas-sip-power` to change voltage in fixed steps,
hold each voltage for a fixed time, and record device status in one CSV file.

## Usage

Use Python 3.14 and uv. `py-seas-sip-power/` is the local library checkout in
this workspace, so clone the repository with its submodule:

```bash
git clone --recursive https://github.com/SinclairQuantumLab/seas-sip-leakage-test-control.git
cd seas-sip-leakage-test-control
uv sync
cp settings.toml.template settings.toml
```

Edit the connection address and measurement settings in `settings.toml`, then run:

```powershell
uv run main.py
```

Alternatively, activate the virtual environment and run `python main.py`.
The settings path can be positional or passed with `--settings`. With no input,
the app loads `settings.toml`. The previous `--config` option remains an alias.

```powershell
uv run main.py settings.toml
uv run main.py --settings "settings_no magnet.toml"
```

The CSV is created under `results/` in the current working directory, named
with the UTC start time, for example `results/20260918_193000_123456Z.csv`.
The file path and each voltage-control or restoration action are printed to the
terminal. Individual samples are written only to CSV. A control line includes
the UTC timestamp, voltage change, new target, last observed current, and hold
time:

```text
2026-09-18T19:35:00.000000Z set_voltage: 3000 -> 3200 V (+200 V); last current 43 nA; hold 300 s
```

## Settings and behavior

```toml
[connection]
address = "192.168.50.34"
transport = "udp"

[measurement]
start_voltage_v = 3000
step_voltage_v = 200
stop_voltage_v = 5000
hold_time_s = 300
sample_interval_s = 1
```

- This example holds 3000, 3200, ..., 5000 V for 300 seconds each.
- Use a negative `step_voltage_v` for a descending sweep. Equal start and stop
  voltages produce one hold. The stop voltage is included when it lies on the
  step grid; otherwise the sequence ends before crossing it. For example,
  start 3000, step 500, stop 4200 produces 3000, 3500, 4000 V.
- `hold_time_s` starts when the voltage-setting call returns. The first sample
  is read immediately, without waiting for voltage or current to settle.
- The first voltage request also sets `output_voltage_ramp_interval_ms` to
  1000 ms, the fastest value allowed by the device manual. The permitted range
  is 1–60 seconds, so a zero ramp interval is not supported.
- Sampling uses a monotonic clock. Slow communication skips missed sampling
  ticks; an in-progress communication call can also delay the end of a hold.
- The app changes the voltage setpoint. The user starts and stops HV operation.
  Before the first step, it reads and records the current device status and
  saves the original voltage setpoint and ramp interval in a sibling
  `*.settings.restore_pending.toml` file. On completion, Ctrl+C, or an error
  after a settings request, it reapplies those two values once and records a
  `restore_settings` action. A successful readback renames the backup to
  `*.settings.restore_confirmed.toml`; a pending file remains available for
  recovery if restoration is not confirmed. Confirmation concerns the two
  settings, not completion of the physical voltage ramp.
  The backup stores the values under `[original_settings]` and explains the
  pending and confirmed filename states in its header comments.
- Alarms and current values are recorded as observed. Communication or file
  errors are printed to the terminal and end the run without automatic retries.
  Rows already flushed remain in the file.

Choose `udp`, `modbus_tcp`, or `modbus_rtu` for the transport. Optional connection
fields are `port`, `timeout_s`, `modbus_id`, and `baudrate`; defaults come from the
library. For RTU, use a serial address such as `address = "COM3"` and run
`uv run --extra serial main.py`.

## CSV

The first columns are shown below. The remaining `DeviceStatus` fields follow
with their values unchanged. `observed_at` is stored as `timestamp`, and unit
symbols in column names retain their proper case: `V`, `nA`, `K`, `W`, `A`, `Torr`.

```csv
timestamp,event,requested_voltage_V,requested_ramp_interval_ms,output_voltage_setpoint_V,output_voltage_V,output_current_nA
2026-09-18T19:29:59.900000Z,observation,,,2900,2898,43
2026-09-18T19:30:00.000000Z,set_voltage,3000,1000,,,
2026-09-18T19:30:00.100000Z,observation,,,3000,2998,43
2026-09-18T19:35:00.000000Z,restore_settings,2900,10000,,,
```

- `set_voltage`: records and flushes the requested voltage immediately before
  the command call. Its first row also records the 1000 ms ramp interval.
  Measurement columns are blank. This records intent, not successful
  transmission or confirmed device application.
- `restore_settings`: records the one-time request that restores the original
  voltage setpoint and ramp interval.
- `observation`: contains the result of a successful `read_sample()` call. The
  requested-voltage column is blank. Both the setpoint and actual output voltage
  are values read from the device.
- Timestamps use ISO 8601 UTC. Actions use the host time immediately before the
  call; observations use the library's `observed_at`.
- Units follow the library values, with corrected symbol case in CSV headers.
  For example, `conversion_rate_A_per_Torr` preserves both unit symbols.
  Settings keys and library API names retain their existing spelling.
  Unknown values (`None`) remain blank;
  observed `0` and `False` values are preserved. The app does no extra pressure
  calculation.
- The header and every row are flushed immediately so the CSV can be read
  while the measurement is running.

## Plotting in a notebook

```powershell
uv sync --group notebook
uv run --group notebook jupytext --to ipynb plot_logs.py
```

Open the generated `plot_logs.ipynb` and select the project's `.venv` kernel.
Choose a file in the first cell, or keep `csv_path = None` to select the latest
CSV. During a measurement, rerun the loading and plotting cells to view the
data saved so far. Loading takes one file snapshot and excludes any incomplete
trailing line that is still being written.

The V(t) and I(t) plots mark voltage-change requests with vertical lines.
A separate I-V scatter plot shows all observations, including transients.
The notebook reads CSV files only and never connects to the device.

`plot_logs.py` is the version-controlled Jupytext source. Generated notebooks
and measurement results are excluded from Git.

## Development checks

```powershell
uv run pytest -q
uv run ruff check main.py .agents plot_logs.py
```

Agent-owned tests live in `.agents/test_app.py`. They use a fake device and clock
to check CSV ordering, immediate flush, fixed hold times, and cleanup after
communication failures or Ctrl+C. They do not connect to hardware.
