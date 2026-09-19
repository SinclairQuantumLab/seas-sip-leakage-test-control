"""Agent-owned offline checks for logging and scheduling without device I/O."""

import csv
from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from typing import get_type_hints
from unittest.mock import Mock

import pytest
from seas_sip_client import (
    AccessModeEnum,
    ConnectionSettings,
    ConnectionTypeEnum,
    DeviceStatus,
    SAESSIPPowerCommunicationError,
)

import main as app


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        assert seconds > 0
        self.now += seconds


def sample_at(seconds):
    hints = get_type_hints(DeviceStatus)
    defaults = {int: 0, float: 0.0, bool: False, str: ""}
    values = {
        field.name: defaults.get(hints[field.name]) for field in fields(DeviceStatus)
    }
    values.update(
        observed_at=datetime(2026, 9, 18, tzinfo=UTC) + timedelta(seconds=seconds),
        output_voltage_setpoint_v=2900,
        output_voltage_v=2898,
        output_current_na=43,
        global_alarm=True,  # An observation, not an automatic stop condition.
        serial_number=123,
        software_version="2.0",
    )
    return DeviceStatus(**values)


class Device:
    """Only expose the three operations this app is meant to use, plus close."""

    def __init__(self, clock):
        self.clock = clock
        self.calls = []
        self.read_delay = 0.0
        self.write_delay = 0.0
        self.read_error = None
        self.write_error = None
        self.before_write = lambda: None
        self.before_read = lambda: None

    def connect(self):
        self.calls.append(("connect", self.clock.now))

    def close(self):
        self.calls.append(("close", self.clock.now))

    def set_working_parameters(self, **kwargs):
        self.before_write()
        self.calls.append(("set", self.clock.now, kwargs))
        if self.write_error:
            raise self.write_error
        self.clock.now += self.write_delay

    def read_sample(self):
        self.before_read()
        self.calls.append(("read", self.clock.now))
        if self.read_error:
            raise self.read_error
        self.clock.now += self.read_delay
        return sample_at(self.clock.now)


@pytest.fixture
def rig(monkeypatch):
    clock = Clock()
    device = Device(clock)
    factory = Mock(return_value=device)
    monkeypatch.setattr(app, "SAESSIPPower", factory)
    monkeypatch.setattr(app.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(app.time, "sleep", clock.sleep)
    return clock, device, factory


def read_rows(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def test_fixed_steps_flush_and_observations_stay_distinct(rig, tmp_path, capsys):
    clock, device, factory = rig
    visible_observations = []

    def check_action_is_already_on_disk():
        rows = read_rows(next(tmp_path.glob("*.csv")))
        assert rows[-1]["event"] == "set_voltage"
        assert rows[-1]["output_current_nA"] == ""

    def check_previous_observations_are_already_on_disk():
        rows = read_rows(next(tmp_path.glob("*.csv")))
        visible_observations.append(sum(row["event"] == "observation" for row in rows))

    device.before_write = check_action_is_already_on_disk
    device.before_read = check_previous_observations_are_already_on_disk
    connection = ConnectionSettings("example.invalid")
    path = app.run_measurement(
        connection, app.Measurement(3000, 200, 3200, 2.5), tmp_path
    )
    factory.assert_called_once_with(connection, access_mode=AccessModeEnum.READ_WRITE)

    rows = read_rows(path)
    assert [row["event"] for row in rows] == [
        "set_voltage",
        "observation",
        "observation",
        "observation",
        "set_voltage",
        "observation",
        "observation",
        "observation",
    ]
    assert visible_observations == list(range(6))
    assert [call[1] for call in device.calls if call[0] == "set"] == [0, 2.5]
    assert [call[2] for call in device.calls if call[0] == "set"] == [
        {"output_voltage_setpoint_v": 3000},
        {"output_voltage_setpoint_v": 3200},
    ]
    assert [call[1] for call in device.calls if call[0] == "read"] == [
        0,
        1,
        2,
        2.5,
        3.5,
        4.5,
    ]
    assert device.calls[-1] == ("close", 5)
    assert clock.now == 5  # The final hold completes too.
    assert rows[4]["requested_voltage_V"] == "3200"
    assert rows[1]["requested_voltage_V"] == ""
    assert rows[1]["output_voltage_setpoint_V"] == "2900"  # Not the requested 3000.
    assert rows[1]["output_voltage_V"] == "2898"
    assert rows[1]["enabled"] == "False"
    assert rows[1]["global_alarm"] == "True"
    assert rows[1]["arcing_events"] == "0"
    assert rows[1]["pressure_Torr"] == ""
    assert rows[1]["timestamp"] == "2026-09-18T00:00:00.000000Z"
    assert all(row["timestamp"].endswith("Z") for row in rows)
    assert "observed_at" not in rows[0]
    stdout = capsys.readouterr().out
    assert stdout.count(" set_voltage: ") == 2
    assert "target 3000 V (first step); current unavailable" in stdout
    assert "3000 -> 3200 V (+200 V); last current 43 nA" in stdout


def test_hold_starts_after_write_and_short_hold_has_one_sample(rig, tmp_path):
    clock, device, _ = rig
    device.write_delay = 2
    path = app.run_measurement(
        ConnectionSettings("example.invalid"),
        app.Measurement(3000, 200, 3000, 0.5),
        tmp_path,
    )
    assert [call[1] for call in device.calls if call[0] == "read"] == [2]
    assert clock.now == 2.5
    assert len(read_rows(path)) == 2


def test_slow_reads_skip_missed_ticks_without_catchup_bursts(rig, tmp_path):
    _, device, _ = rig
    device.read_delay = 1.4
    app.run_measurement(
        ConnectionSettings("example.invalid"),
        app.Measurement(3000, 200, 3000, 3),
        tmp_path,
    )
    assert [call[1] for call in device.calls if call[0] == "read"] == [0, 2]
    assert device.calls[-1] == ("close", 3.4)


@pytest.mark.parametrize(
    "failure", [SAESSIPPowerCommunicationError("timeout"), KeyboardInterrupt()]
)
@pytest.mark.parametrize("operation", ["read", "write"])
def test_failure_keeps_intent_and_closes_without_retry(
    rig, tmp_path, operation, failure
):
    _, device, _ = rig
    setattr(device, f"{operation}_error", failure)
    with pytest.raises(type(failure)):
        app.run_measurement(
            ConnectionSettings("example.invalid"),
            app.Measurement(3000, 200, 3400, 2),
            tmp_path,
        )
    rows = read_rows(next(tmp_path.glob("*.csv")))
    assert len(rows) == 1
    assert rows[0]["event"] == "set_voltage"
    assert rows[0]["requested_voltage_V"] == "3000"
    assert [call[0] for call in device.calls].count("set") == 1
    assert device.calls[-1][0] == "close"


def test_csv_failure_prevents_the_voltage_command(rig, tmp_path, monkeypatch):
    _, device, _ = rig
    monkeypatch.setattr(
        app.CsvLog, "set_voltage", Mock(side_effect=OSError("disk full"))
    )
    with pytest.raises(OSError, match="disk full"):
        app.run_measurement(
            ConnectionSettings("example.invalid"),
            app.Measurement(3000, 200, 3400, 2),
            tmp_path,
        )
    assert [call[0] for call in device.calls] == ["connect", "close"]


def test_voltage_grid():
    assert list(app.Measurement(3000, 200, 3400, 1).voltages()) == [3000, 3200, 3400]
    assert list(app.Measurement(3400, -200, 3000, 1).voltages()) == [3400, 3200, 3000]
    assert list(app.Measurement(3000, 200, 3300, 1).voltages()) == [3000, 3200]
    assert list(app.Measurement(3300, -200, 3000, 1).voltages()) == [3300, 3100]
    assert list(app.Measurement(3000, 200, 3000, 1).voltages()) == [3000]


@pytest.mark.parametrize(
    "changes",
    [
        {"step_voltage_v": 0},
        {"step_voltage_v": -200},
        {"start_voltage_v": 500},
        {"stop_voltage_v": 7000},
        {"start_voltage_v": 3000.5},
        {"hold_time_s": 0},
        {"hold_time_s": float("inf")},
        {"sample_interval_s": float("nan")},
        {"sample_interval_s": -1},
    ],
)
def test_invalid_sequences_fail_before_io(changes):
    with pytest.raises(ValueError):
        replace(app.Measurement(3000, 200, 5000, 2), **changes)


@pytest.mark.parametrize("transport", ["udp", "modbus_tcp", "modbus_rtu"])
def test_config_maps_transport_once(tmp_path, transport):
    path = tmp_path / "settings.toml"
    path.write_text(
        f'[connection]\naddress = "example.invalid"\ntransport = "{transport}"\n'
        "[measurement]\nstart_voltage_v = 3000\nstep_voltage_v = 200\n"
        "stop_voltage_v = 5000\nhold_time_s = 300\n",
        encoding="utf-8",
    )
    connection, measurement = app.load_config(path)
    assert connection.connection_type is ConnectionTypeEnum(transport)
    assert measurement.sample_interval_s == 1
