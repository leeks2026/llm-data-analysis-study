#!/usr/bin/env python3
"""Make EDA figures from the archived stage-two descriptive results.

Run from any directory after installing 02_interim_report/requirements.txt.
This script reads result tables and writes figures; it does not re-run the EDA
or modify its execution logs and input tables.
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "02_interim_report" / "results" / "interim" / "enriched_eda"
FIGURES = HERE / "figures"


def read_csv(name: str) -> list[dict[str, str]]:
    with (RESULTS / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def annotate(ax, value: float, position: float) -> None:
    ax.text(value - 0.15 if value < 0 else value + 0.15, position,
            f"{value:+.1f}%", va="center", ha="right" if value < 0 else "left",
            fontsize=9.5, color="black")


def seasonal_chart() -> None:
    rows = read_csv("seasonal_daily_comparison.csv")
    lookup = {(r["day_type"], r["season"]): r for r in rows}
    seasons = [("spring", "Spring"), ("summer", "Summer"),
               ("autumn", "Autumn"), ("winter", "Winter")]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), sharex=True)
    fig.suptitle("Daily boardings: rainy dates versus unconfirmed candidate dates",
                 fontsize=14, fontweight="bold", y=0.97)
    for ax, (day_type, title) in zip(axes, [("weekday", "Weekdays (holidays included)"),
                                             ("weekend", "Weekends")]):
        labels, values = [], []
        for key, label in seasons:
            row = lookup[(day_type, key)]
            candidate = int(float(row["days_candidate_unconfirmed"]))
            rainy = int(float(row["days_rain_at_least_0.1"]))
            labels.append(f"{label}  ({candidate} / {rainy} days)")
            values.append(float(row["rain_minus_candidate_pct"]))
        positions = list(range(len(seasons)))
        ax.barh(positions, values, color="0.45", height=0.55, edgecolor="black")
        for pos, value in zip(positions, values):
            annotate(ax, value, pos)
        ax.set_yticks(positions, labels)
        ax.invert_yaxis()
        ax.set_xlim(-10.0, 8.5)
        ax.axvline(0, color="black", linewidth=0.8)
        ax.xaxis.grid(True, color="0.88", linewidth=0.7)
        ax.set_axisbelow(True)
        ax.set_title(title, fontsize=11, pad=10)
        ax.set_xlabel("Difference in group mean (%)")
        ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.5, 0.02, "Dates in parentheses: unconfirmed candidate / recorded rain >= 0.1 mm. "
             "Daily rainfall; descriptive comparison, 2023-2025.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.07, 1, 0.91))
    fig.savefig(FIGURES / "01_seasonal_difference.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def period_chart() -> None:
    rows = read_csv("weekday_period_by_daily_rain.csv")
    lookup = {(r["period"], r["rain_band"]): r for r in rows}
    periods = [("morning", "Morning 07-09"), ("midday", "Midday 12-14"),
               ("evening", "Evening 17-19")]
    bands = [("0.1_to_lt5", "0.1 to <5 mm (124 days)", "0.72"),
             ("5_to_lt20", "5 to <20 mm (54 days)", "0.48"),
             ("at_least_20", ">=20 mm (52 days)", "0.20")]
    fig, ax = plt.subplots(figsize=(10.8, 5.5))
    for idx, (band, label, color) in enumerate(bands):
        positions = [i + (idx - 1) * 0.23 for i in range(len(periods))]
        values = [float(lookup[(period, band)]["difference_pct"]) for period, _ in periods]
        ax.barh(positions, values, height=0.20, color=color, edgecolor="black", label=label)
        for pos, value in zip(positions, values):
            annotate(ax, value, pos)
    ax.set_yticks(range(len(periods)), [label for _, label in periods])
    ax.invert_yaxis()
    ax.set_xlim(-10.5, 0.5)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.xaxis.grid(True, color="0.88", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_xlabel("Difference in mean boardings versus candidate dates (%)")
    ax.set_title("Weekday boardings by daily rainfall amount", fontsize=14, fontweight="bold", pad=14)
    ax.legend(title="Daily rainfall", loc="lower left", ncol=3, fontsize=9, title_fontsize=9,
              bbox_to_anchor=(0.0, -0.32), frameon=False)
    fig.text(0.5, 0.015, "Candidate: 455 unconfirmed dates. Daily rain does not identify rain during the two-hour period. "
             "Holidays included.", ha="center", fontsize=8.5)
    fig.tight_layout(rect=(0, 0.11, 1, 1))
    fig.savefig(FIGURES / "02_weekday_period_difference.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    seasonal_chart()
    period_chart()
    print("Created figures from archived stage-two result tables:")
    for filename in ("01_seasonal_difference.png", "02_weekday_period_difference.png"):
        print(FIGURES / filename)


if __name__ == "__main__":
    main()
