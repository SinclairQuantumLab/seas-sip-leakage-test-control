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
# # Magnet vs no-magnet I–V comparison
# This notebook reads the two saved CSV logs only. Raw observations are shown
# faintly, while each connected point is the median for one voltage setpoint.
# Error bars span the 25th to 75th percentiles of current at that setpoint.

# %%
import io
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

datasets = {
    "Magnet": Path("results/20260919_025053_048080Z.csv"),
    "No magnet": Path("results/20260919_030322_046377Z.csv"),
}
styles = {
    "Magnet": {
        "observation_color": "tab:cyan",
        "summary_color": "tab:blue",
        "observation_alpha": 0.3,
    },
    "No magnet": {
        "observation_color": "tab:orange",
        "summary_color": "tab:red",
        "observation_alpha": 0.03,
    },
}

# %%
def load_observations(path):
    """Load one complete CSV snapshot and return measurement observations."""
    snapshot = path.read_bytes()
    snapshot = snapshot[: snapshot.rfind(b"\n") + 1]
    log = pd.read_csv(io.BytesIO(snapshot))
    log = log.rename(
        columns={
            "output_voltage_v": "output_voltage_V",
            "output_voltage_setpoint_v": "output_voltage_setpoint_V",
            "output_current_na": "output_current_nA",
        }
    )
    return log.loc[log["event"] == "observation"].copy()


def summarize_iv(observations):
    """Summarize current by voltage setpoint using the median and IQR."""
    return (
        observations.groupby("output_voltage_setpoint_V", sort=True)
        .agg(
            voltage_median_V=("output_voltage_V", "median"),
            current_median_nA=("output_current_nA", "median"),
            current_q1_nA=(
                "output_current_nA",
                lambda values: values.quantile(0.25),
            ),
            current_q3_nA=(
                "output_current_nA",
                lambda values: values.quantile(0.75),
            ),
        )
        .dropna()
    )


observations_by_condition = {
    label: load_observations(path) for label, path in datasets.items()
}
summaries = {
    label: summarize_iv(observations)
    for label, observations in observations_by_condition.items()
}

# %%
fig, ax = plt.subplots(figsize=(7, 5), layout="constrained")

for label, observations in observations_by_condition.items():
    style = styles[label]
    summary = summaries[label]
    median_current_ua = summary["current_median_nA"] / 1000

    ax.scatter(
        observations["output_voltage_V"] / 1000,
        observations["output_current_nA"] / 1000,
        s=8,
        alpha=style["observation_alpha"],
        color=style["observation_color"],
        label=f"{label} observations",
    )
    ax.errorbar(
        summary["voltage_median_V"] / 1000,
        median_current_ua,
        yerr=[
            median_current_ua - summary["current_q1_nA"] / 1000,
            summary["current_q3_nA"] / 1000 - median_current_ua,
        ],
        fmt="o-",
        color=style["summary_color"],
        linewidth=1.5,
        markersize=5,
        capsize=4,
        label=f"{label} median & IQR",
        zorder=3,
    )

ax.set_xlabel("Measured voltage (kV)")
ax.set_ylabel("Current (µA)")
ax.set_title("Observations, medians, and interquartile ranges")
ax.set_xlim([2.8, 5.2])
ax.set_yscale("log")
ax.set_ylim([1e-2, 50])
ax.grid(alpha=0.2)
ax.legend(ncols=2)
plt.show()
