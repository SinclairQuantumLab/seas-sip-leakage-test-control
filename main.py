"""Apply a fixed voltage sequence and append device observations to CSV."""

import argparse
import csv
import math
import time
import tomllib
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
        for name in ("hold_time_s", "sample_interval_s"):
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


def load_config(path: Path) -> tuple[ConnectionSettings, Measurement]:
    """Read connection settings and measurement timing from TOML."""
    with path.open("rb") as stream:
        config = tomllib.load(stream)
    connection = dict(config["connection"])
    transport = ConnectionTypeEnum(connection.pop("transport", "udp"))
    return (
        ConnectionSettings(connection_type=transport, **connection),
        Measurement(**config["measurement"]),
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
    *(csv_column(name) for name in PRIMARY_FIELDS),
    *(
        csv_column(field.name)
        for field in fields(DeviceStatus)
        if field.name not in {"observed_at", *PRIMARY_FIELDS}
    ),
]


class CsvLog:
    """Write each action or observation immediately to a shared CSV stream."""

    def __init__(self, stream: TextIO) -> None:
        self.stream = stream
        self.writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        self.writer.writeheader()
        self.stream.flush()

    def set_voltage(self, voltage_v: int) -> str:
        """Record intent before calling the device; this is not an ACK."""
        timestamp = utc_timestamp(datetime.now(UTC))
        self.writer.writerow(
            {
                "timestamp": timestamp,
                "event": "set_voltage",
                "requested_voltage_V": voltage_v,
            }
        )
        self.stream.flush()
        return timestamp

    def observation(self, status: DeviceStatus) -> None:
        """Keep observed values, including unknowns, separate from targets."""
        row = {csv_column(name): value for name, value in asdict(status).items()}
        row["timestamp"] = utc_timestamp(row.pop("observed_at"))
        row["event"] = "observation"
        self.writer.writerow(row)
        self.stream.flush()


def run_measurement(
    connection: ConnectionSettings,
    measurement: Measurement,
    output_dir: Path = Path("results"),
) -> Path:
    """Set each voltage once and log samples for the configured hold time."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{datetime.now(UTC):%Y%m%d_%H%M%S_%fZ}.csv"
    device = SAESSIPPower(connection, access_mode=AccessModeEnum.READ_WRITE)

    with path.open("x", encoding="utf-8", newline="") as stream:
        log = CsvLog(stream)
        print(f"CSV: {path.resolve()}", flush=True)
        try:
            device.connect()
            previous_voltage = None
            last_status = None
            for voltage in measurement.voltages():
                timestamp = log.set_voltage(voltage)
                device.set_working_parameters(output_voltage_setpoint_v=voltage)
                if previous_voltage is None:
                    change = f"target {voltage} V (first step)"
                else:
                    delta = voltage - previous_voltage
                    change = f"{previous_voltage} -> {voltage} V ({delta:+d} V)"
                current = (
                    "current unavailable"
                    if last_status is None
                    else f"last current {last_status.output_current_na} nA"
                )
                print(
                    f"{timestamp} set_voltage: {change}; {current}; "
                    f"hold {measurement.hold_time_s:g} s",
                    flush=True,
                )
                previous_voltage = voltage

                next_sample = time.monotonic()
                deadline = next_sample + measurement.hold_time_s
                while (now := time.monotonic()) < deadline:
                    if now < next_sample:
                        time.sleep(min(next_sample, deadline) - now)
                        continue
                    last_status = device.read_sample()
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
        finally:
            device.close()
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
        connection, measurement = load_config(settings_path)
        path = run_measurement(connection, measurement)
    except KeyboardInterrupt:
        parser.exit(130, "Interrupted. Rows already written remain in the CSV.\n")
    except (OSError, ValueError, TypeError, KeyError, SAESSIPPowerError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    print(f"Completed: {path}")


if __name__ == "__main__":
    main()
