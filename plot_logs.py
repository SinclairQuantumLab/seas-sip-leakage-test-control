# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # SIP POWER CSV plots
# Run from the project directory. Set `csv_path` to a file, or keep `None`
# to select the latest log. Re-run the loading and plotting cells to refresh.
# This notebook reads files only; it never connects to the controller.

# %%
import io
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import display

csv_path = None  # Or Path("results/20260918_193000_123456Z.csv")

# %%
if csv_path is None:
    paths = sorted(Path("results").glob("*.csv"))
    if not paths:
        raise FileNotFoundError("No measurement CSV files in results/ yet.")
    selected_path = paths[-1]
else:
    selected_path = Path(csv_path)

# Take one snapshot; omit any last line still being written.
snapshot = selected_path.read_bytes()
snapshot = snapshot[: snapshot.rfind(b"\n") + 1]
log = pd.read_csv(io.BytesIO(snapshot))
# Also accept logs written before CSV unit symbols were capitalized.
log = log.rename(
    columns={
        "output_voltage_v": "output_voltage_V",
        "output_voltage_setpoint_v": "output_voltage_setpoint_V",
        "output_current_na": "output_current_nA",
    }
)
log["timestamp"] = pd.to_datetime(log["timestamp"], utc=True)
observations = log.loc[log["event"] == "observation"].copy()
actions = log.loc[log["event"] == "set_voltage"].copy()
print(f"{selected_path}: {len(observations)} observations, {len(actions)} actions")
display(observations.tail())

# %%
fig, axes = plt.subplots(2, 1, sharex=True, figsize=(11, 6), layout="constrained")
axes[0].plot(
    observations["timestamp"],
    observations["output_voltage_V"] / 1000,
    label="Measured voltage",
)
axes[0].plot(
    observations["timestamp"],
    observations["output_voltage_setpoint_V"] / 1000,
    linestyle="--",
    label="Read-back setpoint",
)
axes[0].set_ylabel("Voltage (kV)")
axes[0].legend()
axes[1].plot(observations["timestamp"], observations["output_current_nA"] / 1000)
axes[1].set_ylabel("Current (µA)")
axes[1].set_xlabel("Time (UTC)")
axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
for ax in axes:
    for timestamp in actions["timestamp"]:
        ax.axvline(timestamp, color="gray", alpha=0.25, linestyle=":")
    ax.grid(alpha=0.2)
fig.suptitle(selected_path.name)
plt.show()

# %% [markdown]
# All measured I–V samples, including transients; no settling selection or averaging.

# %%
fig, ax = plt.subplots(figsize=(7, 4), layout="constrained")
ax.scatter(
    observations["output_voltage_V"] / 1000,
    observations["output_current_nA"] / 1000,
    s=8,
    alpha=0.5,
)
ax.set_xlabel("Measured voltage (kV)")
ax.set_ylabel("Current (µA)")
ax.set_title("All observations (including transients)")
ax.grid(alpha=0.2)
plt.show()
