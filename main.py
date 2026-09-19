"""Apply a fixed voltage sequence and append device observations to CSV."""

import argparse
import csv
import math
import sys
import time
import tomllib
from collections.abc import Callable
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from seas_sip_client import (
    AccessModeEnum,
    ConnectionSettings,
    ConnectionTypeEnum,
    DeviceStatus,
    SAESSIPPower,
    SAESSIPPowerError,
)


@dataclass(frozen=True)
class Measurement:
    """Voltage sequence and fixed timing, in V and seconds."""

    start_voltage_v: int
    step_voltage_v: int
    stop_voltage_v: int
    hold_time_s: float
    initial_voltage_soak_time_s: float
    sample_interval_s: float = 1.0

    def __post_init__(self) -> None:
        for name in ("start_voltage_v", "step_voltage_v", "stop_voltage_v"):
            if type(getattr(self, name)) is not int:
                raise ValueError(f"{name} must be an integer")
        for name in ("start_voltage_v", "stop_voltage_v"):
            if not 1000 <= getattr(self, name) <= 6000:
                raise ValueError(f"{name} must be between 1000 and 6000 V")
        if self.step_voltage_v == 0:
            raise ValueError("step_voltage_v must not be zero")
        if (self.stop_voltage_v - self.start_voltage_v) * self.step_voltage_v < 0:
            raise ValueError("step_voltage_v must point from start toward stop")
        for name in (
            "hold_time_s",
            "sample_interval_s",
            "initial_voltage_soak_time_s",
        ):
            value = getattr(self, name)
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} must be positive and finite")

    def voltages(self) -> range:
        """Include stop when it lies on the step grid; never step past it."""
        end = self.stop_voltage_v + (1 if self.step_voltage_v > 0 else -1)
        return range(self.start_voltage_v, end, self.step_voltage_v)


@dataclass(frozen=True)
class CommandRetrySettings:
    """Retry policy for device communication commands."""

    count: int = 3
    interval_s: float = 1.0

    def __post_init__(self) -> None:
        if type(self.count) is not int or self.count <= 0:
            raise ValueError("command_retry_count must be a positive integer")
        if (
            type(self.interval_s) not in (int, float)
            or not math.isfinite(self.interval_s)
            or self.interval_s <= 0
        ):
            raise ValueError("command_retry_interval_s must be positive and finite")


def load_config(
    path: Path,
) -> tuple[ConnectionSettings, Measurement, CommandRetrySettings]:
    """Read connection settings and measurement timing from TOML."""
    with path.open("rb") as stream:
        config = tomllib.load(stream)
    connection = dict(config["connection"])
    transport = ConnectionTypeEnum(connection.pop("transport", "udp"))
    command_retry = CommandRetrySettings(
        count=connection.pop("command_retry_count", 3),
        interval_s=connection.pop("command_retry_interval_s", 1.0),
    )
    return (
        ConnectionSettings(connection_type=transport, **connection),
        Measurement(**config["measurement"]),
        command_retry,
    )


def utc_timestamp(value: datetime) -> str:
    """Format a host timestamp as ISO 8601 UTC."""
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def csv_column(name: str) -> str:
    """Preserve unit-symbol case in CSV headers without changing the device API."""
    units = {"v": "V", "na": "nA", "k": "K", "w": "W", "a": "A", "torr": "Torr"}
    return "_".join(units.get(part, part) for part in name.split("_"))


PRIMARY_FIELDS = [
    "output_voltage_setpoint_v",
    "output_voltage_v",
    "output_current_na",
]
CSV_FIELDS = [
    "timestamp",
    "event",
    "requested_voltage_V",
    "requested_ramp_interval_ms",
    *(csv_column(name) for name in PRIMARY_FIELDS),
    *(
        csv_column(field.name)
        for field in fields(DeviceStatus)
        if field.name not in {"observed_at", *PRIMARY_FIELDS}
    ),
]
CHANGED_SETTING_FIELDS = (
    "output_voltage_setpoint_v",
    "output_voltage_ramp_interval_ms",
)
MEASUREMENT_RAMP_INTERVAL_MS = 1000
COMMAND_GAP_S = 0.1


def capture_original_settings(status: DeviceStatus) -> dict[str, int]:
    """Copy the original values of the two settings changed by this app."""
    return {name: getattr(status, name) for name in CHANGED_SETTING_FIELDS}


def write_settings_snapshot(
    path: Path,
    status: DeviceStatus,
    settings: dict[str, int],
    csv_name: str,
) -> None:
    """Persist original values before either setting is changed."""
    lines = [
        "# Original device settings captured before the measurement procedure.",
        "# These are the previous values of settings temporarily changed by this app.",
        "# The app reapplies these values when the procedure ends.",
        "# A restore_pending filename means readback has not confirmed restoration.",
        "# A restore_confirmed filename means readback matched these values.",
        "[snapshot]",
        f'captured_at = "{utc_timestamp(status.observed_at)}"',
        f'csv_file = "{csv_name}"',
        "",
        "[original_settings]",
    ]
    lines.extend(f"{name} = {settings[name]}" for name in CHANGED_SETTING_FIELDS)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def settings_match(status: DeviceStatus, settings: dict[str, int]) -> bool:
    """Return whether readback matches both settings saved for restoration."""
    return all(getattr(status, name) == value for name, value in settings.items())


class CsvLog:
    """Write each action or observation immediately to a shared CSV stream."""

    def __init__(self, stream: TextIO) -> None:
        self.stream = stream
        self.writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        self.writer.writeheader()
        self.stream.flush()

    def settings_action(
        self,
        event: str,
        *,
        voltage_v: int | None = None,
        ramp_interval_ms: int | None = None,
    ) -> str:
        """Record intent before calling the device; this is not an ACK."""
        timestamp = utc_timestamp(datetime.now(UTC))
        self.writer.writerow(
            {
                "timestamp": timestamp,
                "event": event,
                "requested_voltage_V": voltage_v,
                "requested_ramp_interval_ms": ramp_interval_ms,
            }
        )
        self.stream.flush()
        return timestamp

    def set_voltage(
        self, voltage_v: int, ramp_interval_ms: int | None = None
    ) -> str:
        """Record a measurement-step voltage request."""
        return self.settings_action(
            "set_voltage",
            voltage_v=voltage_v,
            ramp_interval_ms=ramp_interval_ms,
        )

    def restore_settings(self, voltage_v: int, ramp_interval_ms: int) -> str:
        """Record restoration of the two original settings."""
        return self.settings_action(
            "restore_settings",
            voltage_v=voltage_v,
            ramp_interval_ms=ramp_interval_ms,
        )

    def observation(self, status: DeviceStatus) -> None:
        """Keep observed values, including unknowns, separate from targets."""
        row = {csv_column(name): value for name, value in asdict(status).items()}
        row["timestamp"] = utc_timestamp(row.pop("observed_at"))
        row["event"] = "observation"
        self.writer.writerow(row)
        self.stream.flush()

class DeviceCommandFailed(RuntimeError):
    """Report that a device command exhausted all configured attempts."""


def run_device_command[CommandResult](
    command: str,
    operation: Callable[[], CommandResult],
    command_retry: CommandRetrySettings,
) -> CommandResult:
    """Run one device command and retry failures at the configured interval."""
    max_attempts = command_retry.count
    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except Exception as exc:
            if attempt < max_attempts:
                suffix = f"retrying in {command_retry.interval_s:g} s"
            else:
                suffix = "command failed"
            print(
                f"Command error: {command} attempt "
                f"{attempt}/{max_attempts}: {exc}; {suffix}",
                file=sys.stderr,
                flush=True,
            )
            if attempt == max_attempts:
                time.sleep(COMMAND_GAP_S)
                raise DeviceCommandFailed(
                    f"{command} failed after {max_attempts} attempts: {exc}"
                ) from exc
            time.sleep(command_retry.interval_s)
    raise AssertionError("unreachable")


def run_measurement(
    connection: ConnectionSettings,
    measurement: Measurement,
    output_dir: Path = Path("results"),
    command_retry: CommandRetrySettings = CommandRetrySettings(),
) -> Path:
    """Request each voltage and log samples during each recording hold."""
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{datetime.now(UTC):%Y%m%d_%H%M%S_%fZ}"
    path = output_dir / f"{stem}.csv"
    pending_settings_path = output_dir / f"{stem}.settings.restore_pending.toml"
    restored_settings_path = output_dir / f"{stem}.settings.restore_confirmed.toml"
    device = SAESSIPPower(connection, access_mode=AccessModeEnum.READ_WRITE)

    with path.open("x", encoding="utf-8", newline="") as stream:
        log = CsvLog(stream)
        print(f"CSV: {path.resolve()}", flush=True)
        original_settings = None
        last_requested_voltage = None
        last_status = None
        settings_were_requested = False
        procedure_aborted = False

        def sample_until(deadline: float, *, record: bool) -> None:
            """Poll on schedule until a deadline and optionally write samples."""
            nonlocal last_status
            next_sample = time.monotonic()
            while (now := time.monotonic()) < deadline:
                if now < next_sample:
                    time.sleep(min(next_sample, deadline) - now)
                    continue
                try:
                    last_status = run_device_command(
                        "read_sample", device.read_sample, command_retry
                    )
                except DeviceCommandFailed:
                    print(
                        "Scheduled read failed; skipping this sample and continuing.",
                        file=sys.stderr,
                        flush=True,
                    )
                else:
                    time.sleep(COMMAND_GAP_S)
                    if record:
                        log.observation(last_status)
                next_sample += measurement.sample_interval_s
                # Skip missed ticks instead of issuing a burst of reads.
                now = time.monotonic()
                if next_sample < now:
                    missed = (
                        math.floor(
                            (now - next_sample) / measurement.sample_interval_s
                        )
                        + 1
                    )
                    next_sample += missed * measurement.sample_interval_s

        try:
            run_device_command("connect", device.connect, command_retry)
            time.sleep(COMMAND_GAP_S)
            last_status = run_device_command(
                "read_initial_status", device.read_sample, command_retry
            )
            time.sleep(COMMAND_GAP_S)
            original_settings = capture_original_settings(last_status)
            write_settings_snapshot(
                pending_settings_path, last_status, original_settings, path.name
            )
            print(f"Settings backup: {pending_settings_path.resolve()}", flush=True)
            previous_voltage = last_status.output_voltage_setpoint_v
            original_ramp = last_status.output_voltage_ramp_interval_ms

            for step_index, voltage in enumerate(measurement.voltages()):
                ramp_interval = (
                    MEASUREMENT_RAMP_INTERVAL_MS if step_index == 0 else None
                )
                timestamp = log.set_voltage(voltage, ramp_interval)
                last_requested_voltage = voltage
                settings_were_requested = True
                requested_settings = {"output_voltage_setpoint_v": voltage}
                if ramp_interval is not None:
                    requested_settings["output_voltage_ramp_interval_ms"] = (
                        ramp_interval
                    )
                run_device_command(
                    "set_working_parameters",
                    lambda: device.set_working_parameters(**requested_settings),
                    command_retry,
                )
                setting_completed = time.monotonic()
                time.sleep(COMMAND_GAP_S)
                delta = voltage - previous_voltage
                change = f"{previous_voltage} -> {voltage} V ({delta:+d} V)"
                current = f"last current {last_status.output_current_na} nA"
                ramp_change = (
                    f"; ramp interval {original_ramp} -> {ramp_interval} ms"
                    if ramp_interval is not None
                    else ""
                )
                print(
                    f"{timestamp} set_voltage: {change}{ramp_change}; {current}; "
                    + (
                        f"soak {measurement.initial_voltage_soak_time_s:g} s, "
                        f"then record {measurement.hold_time_s:g} s"
                        if step_index == 0
                        else f"record {measurement.hold_time_s:g} s"
                    ),
                    flush=True,
                )
                previous_voltage = voltage

                if step_index == 0:
                    sample_until(
                        setting_completed + measurement.initial_voltage_soak_time_s,
                        record=False,
                    )
                recording_started = time.monotonic()
                sample_until(
                    recording_started + measurement.hold_time_s,
                    record=True,
                )
        except KeyboardInterrupt as exc:
            procedure_aborted = True
            setattr(exc, "_sip_error_reported", True)
            print(
                "Interrupted. Rows already written remain in the CSV.",
                file=sys.stderr,
                flush=True,
            )
            raise
        except Exception as exc:
            procedure_aborted = True
            setattr(exc, "_sip_error_reported", True)
            print(f"Error: {exc}", file=sys.stderr, flush=True)
            raise
        finally:
            try:
                if original_settings is not None and settings_were_requested:
                    outcome = "aborted" if procedure_aborted else "completed"
                    print(
                        f"Procedure {outcome}; restoring original settings.",
                        file=sys.stderr if procedure_aborted else sys.stdout,
                        flush=True,
                    )
                    original_voltage = original_settings["output_voltage_setpoint_v"]
                    original_ramp = original_settings[
                        "output_voltage_ramp_interval_ms"
                    ]
                    timestamp = log.restore_settings(
                        original_voltage, original_ramp
                    )
                    run_device_command(
                        "restore_settings",
                        lambda: device.set_working_parameters(**original_settings),
                        command_retry,
                    )
                    time.sleep(1.0)
                    restored_status = run_device_command(
                        "read_restored_settings",
                        device.read_sample,
                        command_retry,
                    )
                    time.sleep(COMMAND_GAP_S)
                    if not settings_match(restored_status, original_settings):
                        raise RuntimeError(
                            "restored settings did not match the saved "
                            f"settings; use {pending_settings_path} for recovery"
                        )
                    pending_settings_path.rename(restored_settings_path)
                    delta = original_voltage - last_requested_voltage
                    print(
                        f"{timestamp} restore_settings: {last_requested_voltage} "
                        f"-> {original_voltage} V ({delta:+d} V); "
                        f"ramp interval {MEASUREMENT_RAMP_INTERVAL_MS} -> "
                        f"{original_ramp} ms; "
                        f"last current {last_status.output_current_na} nA",
                        flush=True,
                    )
                    print(
                        f"Settings restore confirmed: "
                        f"{restored_settings_path.resolve()}",
                        flush=True,
                    )
            finally:
                run_device_command("close", device.close, command_retry)
    return path


def main() -> None:
    """Run a TOML-configured measurement from the command line."""
    parser = argparse.ArgumentParser(
        description="Step the SIP POWER voltage and log actions/observations to CSV."
    )
    parser.add_argument(
        "settings_file",
        nargs="?",
        type=Path,
        help="TOML settings path (default: settings.toml)",
    )
    parser.add_argument(
        "--settings",
        "--config",
        dest="settings_option",
        type=Path,
        help="TOML settings path (default: settings.toml)",
    )
    args = parser.parse_args()
    if args.settings_file is not None and args.settings_option is not None:
        parser.error(
            "Specify the settings path either positionally or with --settings."
        )
    settings_path = args.settings_option or args.settings_file or Path("settings.toml")
    try:
        connection, measurement, command_retry = load_config(settings_path)
        path = run_measurement(
            connection, measurement, command_retry=command_retry
        )
    except KeyboardInterrupt as exc:
        message = (
            None
            if getattr(exc, "_sip_error_reported", False)
            else "Interrupted. Rows already written remain in the CSV.\n"
        )
        parser.exit(130, message)
    except (
        OSError,
        RuntimeError,
        ValueError,
        TypeError,
        KeyError,
        SAESSIPPowerError,
    ) as exc:
        message = (
            None
            if getattr(exc, "_sip_error_reported", False)
            else f"Error: {exc}\n"
        )
        parser.exit(1, message)
    print(f"Completed: {path}")


if __name__ == "__main__":
    main()
