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

import matplotlib.pyplot as plt
import pandas as pd
from brokenaxes import brokenaxes
from IPython.display import display
from matplotlib.ticker import MultipleLocator

csv_path = None  # Or Path("results/20260918_193000_123456Z.csv")
voltage_main_limits_kv = (2.75, 5.1)
voltage_drop_limits_kv = (-0.1, 0.25)
current_rolling_window = "5min"

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
actions = log.loc[
    log["event"].isin(
        [
            "set_voltage", "after_test_voltage", "restore_ramp_interval",
            "restore_settings", "cool_voltage",
        ]
    )
].copy()
time_origin = log["timestamp"].min()
observations["elapsed_time_h"] = (
    observations["timestamp"] - time_origin
).dt.total_seconds() / 3600
actions["elapsed_time_h"] = (
    actions["timestamp"] - time_origin
).dt.total_seconds() / 3600
print(f"{selected_path}: {len(observations)} observations, {len(actions)} actions")
display(observations.tail())

# %%
fig = plt.figure(figsize=(11, 7))
grid = fig.add_gridspec(1, 1, top=0.94)
voltage_ax = brokenaxes(
    ylims=(voltage_drop_limits_kv, voltage_main_limits_kv),
    d=0.01,
    tilt=15,
    despine=True,
    diag_color="tab:blue",
    subplot_spec=grid[0],
    fig=fig,
    hspace=0.04,
)
current_ax = voltage_ax.big_ax.twinx()

voltage_ax.plot(
    observations["elapsed_time_h"],
    observations["output_voltage_V"] / 1000,
    label="Measured voltage",
)
voltage_ax.plot(
    observations["elapsed_time_h"],
    observations["output_voltage_setpoint_V"] / 1000,
    linestyle="--",
    label="Read-back setpoint",
)
for ax in voltage_ax.axs[:-1]:
    ax.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
for ax in voltage_ax.axs:
    ax.tick_params(axis="y", colors="tab:blue")
    ax.spines["left"].set_color("tab:blue")
voltage_ax.axs[-1].set_xlabel("Time (h)")
voltage_ax.set_ylabel("Voltage (kV)", color="tab:blue")

current_line = current_ax.plot(
    observations["elapsed_time_h"],
    observations["output_current_nA"] / 1000,
    color="tab:green",
    linewidth=0.8,
    alpha=0.25,
    label="Current",
)[0]
current_rolling_mean_ua = (
    observations.set_index("timestamp")["output_current_nA"]
    .rolling(current_rolling_window, center=True, min_periods=1)
    .mean()
    / 1000
)
current_mean_line = current_ax.plot(
    observations["elapsed_time_h"],
    current_rolling_mean_ua,
    color="tab:green",
    linewidth=2,
    label=f"Current ({current_rolling_window} rolling mean)",
)[0]
current_ax.set_ylabel("Current (µA)", color=current_mean_line.get_color())
current_ax.tick_params(axis="y", colors=current_mean_line.get_color())
current_ax.spines["right"].set_color(current_mean_line.get_color())
current_ax.spines["left"].set_visible(False)
current_ax.spines["top"].set_visible(False)
current_ax.spines["bottom"].set_visible(False)
voltage_handles, voltage_labels = voltage_ax.axs[0].get_legend_handles_labels()
current_handles, current_labels = current_ax.get_legend_handles_labels()
current_ax.legend(
    voltage_handles + current_handles,
    voltage_labels + current_labels,
    loc="upper left",
    ncols=2,
)
for elapsed_time_h in actions["elapsed_time_h"]:
    current_ax.axvline(elapsed_time_h, color="gray", alpha=0.25, linestyle=":")
voltage_ax.grid(alpha=0.2)
current_ax.set_xlim(left=0)
for ax in voltage_ax.axs:
    ax.set_xlim(current_ax.get_xlim())
voltage_ax.axs[-1].xaxis.set_major_locator(MultipleLocator(2))
voltage_ax.axs[-1].set_yticks([0])
voltage_ax.axs[0].spines["top"].set_visible(True)
fig.suptitle(selected_path.name)
plt.show()

# %% [markdown]
# Raw I–V samples include transients with no settling selection. Step summaries
# show the median current and its interquartile range.

# %%
iv_summary = (
    observations.groupby("output_voltage_setpoint_V", sort=True)
    .agg(
        voltage_median_V=("output_voltage_V", "median"),
        current_median_nA=("output_current_nA", "median"),
        current_q1_nA=("output_current_nA", lambda values: values.quantile(0.25)),
        current_q3_nA=("output_current_nA", lambda values: values.quantile(0.75)),
    )
    .dropna()
)
median_current_ua = iv_summary["current_median_nA"] / 1000

fig, ax = plt.subplots(figsize=(6, 4), layout="constrained")
ax.scatter(
    observations["output_voltage_V"] / 1000,
    observations["output_current_nA"] / 1000,
    s=8,
    alpha=1e-2,
    # label="Observations",
)
ax.errorbar(
    iv_summary["voltage_median_V"] / 1000,
    median_current_ua,
    yerr=[
        median_current_ua - iv_summary["current_q1_nA"] / 1000,
        iv_summary["current_q3_nA"] / 1000 - median_current_ua,
    ],
    fmt="o-",
    color="tab:red",
    linewidth=1.5,
    markersize=5,
    capsize=4,
    label="Median & interquartile range",
    zorder=3,
)
ax.set_xlabel("Measured voltage (kV)")
ax.set_ylabel("Current (µA)")
ax.set_title(selected_path.name)
ax.grid(alpha=0.2)
ax.set_xlim([2.8, 5.2])
# ax.set_ylim([0, 35])
ax.set_yscale("log")
ax.set_ylim([1e-1, 50])
ax.legend()
plt.show()

# %%
