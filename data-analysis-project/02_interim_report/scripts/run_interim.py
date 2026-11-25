#!/usr/bin/env python3
"""Run only the second-stage data checks and descriptive analysis.

This deliberately writes to results/interim and does not run the later
matched comparison, regression models or sensitivity analyses.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.subway import HOURS, RAW, aggregate, load_and_audit
from src.weather import read_weather

OUT = ROOT / "results" / "interim"
TABLES = OUT / "tables"
FIGURES = OUT / "figures"
WEATHER = ROOT / "data" / "raw" / "weather" / "asos_seoul_2023_2025.csv"


def csv(frame: pd.DataFrame, name: str) -> None:
    frame.to_csv(TABLES / name, index=False, encoding="utf-8-sig")


def chart(name: str) -> None:
    plt.tight_layout()
    plt.savefig(FIGURES / name, dpi=170, bbox_inches="tight")
    plt.close()


def join_weather(daily, hourly, weather):
    weather_fields = ["date", "rain_mm", "temp_c", "rain_duration_hr", "weather_article",
                      "rain_category", "dry_candidate_unconfirmed"]
    weather_one_per_day = weather[weather_fields]
    daily_join = daily.merge(weather_one_per_day, on="date", how="left", validate="many_to_one", indicator=True)
    hourly_join = hourly.merge(weather_one_per_day, on="date", how="left", validate="many_to_one", indicator=True)
    unmatched = daily_join.loc[daily_join._merge.eq("left_only"), "date"].nunique()
    unmatched_hourly = hourly_join.loc[hourly_join._merge.eq("left_only"), "date"].nunique()
    if unmatched or unmatched_hourly:
        raise ValueError("Weather observations missing for at least one subway date")
    if len(hourly_join) != len(hourly) or len(daily_join) != len(daily):
        raise AssertionError("Weather join changed the number of subway rows")
    if int(hourly_join.passengers.sum()) != int(hourly.passengers.sum()):
        raise AssertionError("Weather join changed the passenger total")
    return daily_join, hourly_join, unmatched


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    for key in ("text.color", "axes.labelcolor", "xtick.color", "ytick.color"):
        plt.rcParams[key] = "black"
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

    data, source_audit, coverage = load_and_audit()
    daily, hourly, reshape = aggregate(data, coverage)
    csv(source_audit, "subway_source_audit.csv")
    csv(coverage, "station_coverage.csv")
    csv(reshape, "reshape_validation.csv")

    # Direct check of one original row against the normalized source row.
    columns = ["수송일자", "호선", "역번호", "역명", "승하차구분", "06-07시간대"]
    raw = pd.read_csv(RAW / "subway_2023.csv", encoding="cp949", dtype="string", usecols=columns)
    select = ((raw["수송일자"] == "2023-01-01") & (raw["호선"] == "1호선") &
              (raw["역번호"] == "150") & (raw["승하차구분"] == "승차"))
    original = raw.loc[select]
    normalized = data.loc[(data.date == pd.Timestamp("2023-01-01")) & (data.line == "1호선") &
                          (data.station_code == "150") & (data.direction == "승차")]
    if len(original) != 1 or len(normalized) != 1:
        raise AssertionError("The selected source check does not identify exactly one row")
    raw_count = int(original.iloc[0]["06-07시간대"])
    normalized_count = int(normalized.iloc[0]["06-07"])
    if raw_count != normalized_count:
        raise AssertionError("Original and normalized source values differ")
    crosscheck = pd.DataFrame([{"date": "2023-01-01", "line": "1호선", "station_code": "150",
                                "station_name": "서울역", "direction": "승차", "time_band": "06-07",
                                "raw_count": raw_count, "normalized_count": normalized_count,
                                "equal": raw_count == normalized_count}])
    csv(crosscheck, "source_direct_comparison.csv")

    weather, audit = read_weather(WEATHER)
    daily_join, hourly_join, unmatched = join_weather(daily, hourly, weather)
    audit.update({"unmatched_subway_dates": int(unmatched), "hourly_rows_before_merge": len(hourly),
                  "hourly_rows_after_merge": len(hourly_join),
                  "hourly_passenger_sum_before_merge": int(hourly.passengers.sum()),
                  "hourly_passenger_sum_after_merge": int(hourly_join.passengers.sum()),
                  "scope_note": "Hourly rows contain both the common and all-station aggregates."})
    (OUT / "weather_merge_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    csv(weather, "weather_quality.csv")
    csv(daily_join, "daily_joined.csv")

    common = daily_join[daily_join.population.eq("common")].copy()
    common["analysis_group"] = np.select(
        [common.rain_category.eq("at_least_0.1mm"), common.rain_category.eq("recorded_0.0mm"),
         common.dry_candidate_unconfirmed.eq(True)],
        ["Rain >=0.1 mm", "Recorded 0.0 mm", "Blank: dry candidate (unconfirmed)"],
        default="Other / unresolved")
    group = (common.groupby(["analysis_group", "weekend"], observed=True)
             .agg(days=("date", "nunique"), mean_boardings=("boardings_06_24", "mean"),
                  median_boardings=("boardings_06_24", "median"),
                  q25=("boardings_06_24", lambda s: s.quantile(.25)),
                  q75=("boardings_06_24", lambda s: s.quantile(.75))).reset_index())
    csv(group, "precip_weekend_descriptive.csv")
    duration = pd.crosstab(common.rain_category, common.rain_duration_hr.notna(), dropna=False)
    duration.to_csv(TABLES / "rain_vs_duration_crosscheck.csv", encoding="utf-8-sig")
    year_weekday = (common.groupby(["year", "weekday"], observed=True)
                    .agg(days=("date", "nunique"), mean_boardings=("boardings_06_24", "mean"))
                    .reset_index())
    csv(year_weekday, "weekday_boardings.csv")
    year_rain = (common.groupby(["year", "rain_category"], observed=True)
                 .agg(days=("date", "nunique"), mean_boardings=("boardings_06_24", "mean"),
                      median_boardings=("boardings_06_24", "median")).reset_index())
    csv(year_rain, "rain_categories_by_year.csv")
    amount = pd.to_numeric(common.rain_mm, errors="coerce")
    common["intensity"] = np.select(
        [common.dry_candidate_unconfirmed.eq(True), common.rain_category.eq("recorded_0.0mm"),
         (amount.ge(.1) & amount.lt(5)).fillna(False).to_numpy(dtype=bool),
         (amount.ge(5) & amount.lt(20)).fillna(False).to_numpy(dtype=bool),
         amount.ge(20).fillna(False).to_numpy(dtype=bool)],
        ["Blank: dry candidate (unconfirmed)", "Recorded 0.0 mm", "0.1 to <5 mm", "5 to <20 mm", ">=20 mm"],
        default="Other / unresolved")
    intensity = (common.groupby(["intensity", "weekend"], observed=True)
                 .agg(days=("date", "nunique"), mean_boardings=("boardings_06_24", "mean"),
                      median_boardings=("boardings_06_24", "median")).reset_index())
    csv(intensity, "rain_intensity_by_weekend.csv")

    board = data.loc[data.direction.eq("승차"), ["date", "line", "station_code", *HOURS]].copy()
    board["boardings_06_24"] = board[HOURS].sum(axis=1)
    sizes = (board.groupby(["line", "station_code"], observed=True)
             .agg(observed_days=("date", "nunique"), mean_boardings_06_24=("boardings_06_24", "mean"))
             .reset_index().merge(coverage[["line", "station_code", "names", "common_station"]],
                                  on=["line", "station_code"], validate="one_to_one"))
    csv(sizes, "station_boarding_scale.csv")

    plt.figure(figsize=(8, 3.7))
    styles = {2023: ("-", "o"), 2024: ("--", "s"), 2025: (":", "^")}
    for year, (line, marker) in styles.items():
        part = year_weekday[year_weekday.year.eq(year)].sort_values("weekday")
        plt.plot(part.weekday, part.mean_boardings, color="black", linestyle=line, marker=marker,
                 markersize=4, label=str(year))
    plt.xticks(range(7), ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    plt.ylabel("Average daily boardings (06:00–24:00)")
    plt.title("Daily boardings by weekday and year")
    plt.grid(axis="y", color="0.88"); plt.legend(frameon=False, ncol=3)
    chart("01_weekday_boardings.png")

    labels = ["Rain >=0.1 mm", "Recorded 0.0 mm", "Blank"]
    values = [int(audit["rain_category_counts"].get(k, 0)) for k in
              ("at_least_0.1mm", "recorded_0.0mm", "blank_unresolved")]
    plt.figure(figsize=(7.4, 3.4))
    bars = plt.bar(labels, values, color=["0.3", "0.6", "0.86"], edgecolor="black")
    for bar, value in zip(bars, values):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height()+6, str(value), ha="center", color="black")
    plt.ylabel("Number of dates"); plt.ylim(0, max(values)*1.15)
    plt.title("Daily precipitation records, 2023–2025")
    chart("02_precipitation_records.png")

    hours = hourly_join[(hourly_join.population == "common") & (hourly_join.direction == "승차") &
                        hourly_join.time_band.isin(HOURS)].copy()
    hours["weekend"] = hours.date.dt.day_of_week.ge(5)
    hours["analysis_group"] = np.select(
        [hours.rain_category.eq("at_least_0.1mm"), hours.rain_category.eq("recorded_0.0mm"),
         hours.dry_candidate_unconfirmed.eq(True)],
        ["Rain >=0.1 mm", "Recorded 0.0 mm", "Blank: dry candidate (unconfirmed)"], default="Other / unresolved")
    profile = (hours[hours.analysis_group.ne("Other / unresolved")]
               .groupby(["time_band", "analysis_group", "weekend"], observed=True)
               .agg(mean_boardings=("passengers", "mean"), dates=("date", "nunique")).reset_index())
    csv(profile, "hourly_profile.csv")
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    style = {"Rain >=0.1 mm": ("-", "Rain >=0.1 mm"),
             "Recorded 0.0 mm": ("--", "Recorded 0.0 mm"),
             "Blank: dry candidate (unconfirmed)": (":", "Blank candidate*")}
    for ax, is_weekend in zip(axes, (False, True)):
        for label, (linestyle, display) in style.items():
            part = profile[profile.weekend.eq(is_weekend) & profile.analysis_group.eq(label)].set_index("time_band")
            hour_values = part.reindex(HOURS).mean_boardings
            ax.plot(range(len(HOURS)), hour_values, color="black", linestyle=linestyle, linewidth=1.4, label=display)
        ax.set_xticks(range(0, len(HOURS), 3), [HOURS[i] for i in range(0, len(HOURS), 3)], rotation=35)
        ax.set_title("Weekend" if is_weekend else "Weekday")
        ax.set_xlabel("Subway time band"); ax.grid(axis="y", color="0.88")
    axes[0].set_ylabel("Average boardings per day")
    axes[1].legend(frameon=False, fontsize=8)
    fig.suptitle("Hourly pattern grouped by daily precipitation record")
    chart("03_hourly_by_daily_precipitation.png")

    kst = dt.timezone(dt.timedelta(hours=9))
    print("=== 2nd-stage data verification and descriptive analysis ===")
    print("Run time (KST):", dt.datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S"))
    print("Analysis period: 2023-01-01 to 2025-12-31; daily weather records:", audit["rows"])
    print("Common station/line/code pairs:", int(coverage.common_station.sum()))
    print("Source audit: year | valid rows | fully blank rows | duplicate keys")
    for row in source_audit.itertuples():
        print(f"  {row.year} | {row.valid_rows:,} | {row.fully_empty_rows:,} | {row.candidate_key_duplicate_rows:,}")
    print("Direct raw/normalized sample: Seoul Station line 1, 2023-01-01 06-07, boarding:", raw_count, "=", normalized_count)
    print("Reshape totals preserved (common and all; board and alight):", bool(reshape.equal.all()))
    print("Weather unmatched dates:", audit["unmatched_subway_dates"])
    print("Hourly aggregate rows before/after join:", len(hourly), "/", len(hourly_join))
    print("Join passenger totals preserved:", audit["hourly_passenger_sum_before_merge"] == audit["hourly_passenger_sum_after_merge"])
    print("Precipitation records: >=0.1 mm =", values[0], "; 0.0 mm =", values[1], "; blank =", values[2])
    print("Recorded 0.0 mm with rain-duration entry:", int(duration.loc["recorded_0.0mm", True]))
    print("Unconfirmed dry candidates among blanks:", audit["dry_candidates_unconfirmed"])
    print("Output folder:", OUT)
    print("Stage scope: source checks, join checks and descriptive analysis only.")


if __name__ == "__main__":
    main()
