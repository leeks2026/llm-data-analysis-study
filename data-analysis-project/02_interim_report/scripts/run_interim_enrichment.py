#!/usr/bin/env python3
"""Additional *daily-record* exploratory analysis for the interim report.

Uses only the saved stage-two daily and subway-hour aggregates.  It does not
read hourly weather observations or run the later matched/model analyses.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DAILY = ROOT / "results/interim/tables/daily_joined.csv"
HOURLY = ROOT / "results/tables/hourly_subway.csv"
OUT = ROOT / "results/interim/enriched_eda"

SEASONS = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
           6: "summer", 7: "summer", 8: "summer", 9: "autumn", 10: "autumn", 11: "autumn"}
PERIODS = {"07-08": "morning", "08-09": "morning", "12-13": "midday", "13-14": "midday",
           "17-18": "evening", "18-19": "evening"}
HOURS = [f"{h:02d}-{h+1:02d}" for h in range(6, 24)]


def assign_daily_groups(frame: pd.DataFrame) -> pd.DataFrame:
    """Preserve blanks/0.0; never infer that an unconfirmed candidate is dry."""
    result = frame.copy()
    rain = pd.to_numeric(result["rain_mm"], errors="coerce")
    candidate = result["dry_candidate_unconfirmed"].eq(True)  # noqa: E712
    if (candidate & rain.notna()).any():
        raise ValueError("A dry candidate must have a blank daily rain value")
    result["group"] = "other_or_unresolved"
    result.loc[candidate, "group"] = "candidate_unconfirmed"
    result.loc[rain.ge(0.1), "group"] = "rain_at_least_0.1"
    result.loc[rain.eq(0), "group"] = "recorded_0.0"
    result["rain_band"] = "other_or_unresolved"
    result.loc[candidate, "rain_band"] = "candidate_unconfirmed"
    result.loc[rain.eq(0), "rain_band"] = "recorded_0.0"
    result.loc[rain.ge(0.1) & rain.lt(5), "rain_band"] = "0.1_to_lt5"
    result.loc[rain.ge(5) & rain.lt(20), "rain_band"] = "5_to_lt20"
    result.loc[rain.ge(20), "rain_band"] = "at_least_20"
    return result


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    daily = pd.read_csv(DAILY, parse_dates=["date"])
    daily = daily.loc[daily["population"].eq("common")].copy()
    if daily["date"].duplicated().any() or len(daily) != 1096:
        raise ValueError("Expected exactly one common-population row for each of 1,096 dates")
    expected_dates = pd.date_range("2023-01-01", "2025-12-31", freq="D")
    if not pd.DatetimeIndex(daily["date"].sort_values()).equals(expected_dates):
        raise ValueError("Date range has missing or unexpected dates")
    daily = assign_daily_groups(daily)
    daily["day_type"] = np.where(daily["date"].dt.day_of_week.lt(5), "weekday", "weekend")
    daily["season"] = daily["date"].dt.month.map(SEASONS)
    daily["year"] = daily["date"].dt.year

    hourly = pd.read_csv(HOURLY, parse_dates=["date"])
    hourly = hourly.loc[hourly["population"].eq("common") & hourly["direction"].eq("승차") &
                        hourly["time_band"].isin(HOURS)].copy()
    if hourly.duplicated(["date", "time_band"]).any() or len(hourly) != 1096 * 18:
        raise ValueError("Expected 18 unique hourly subway intervals for each date")
    day_sums = hourly.groupby("date", observed=True)["passengers"].sum()
    daily_values = daily.set_index("date")["boardings_06_24"].sort_index()
    if not day_sums.sort_index().equals(daily_values):
        raise AssertionError("Subway hourly totals do not match the archived daily totals")
    return daily, hourly


def seasonal_summary(daily: pd.DataFrame, dimension: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    subset = daily[daily["group"].isin(["candidate_unconfirmed", "rain_at_least_0.1"])].copy()
    grouped = (subset.groupby([dimension, "day_type", "group"], observed=True)
               .agg(days=("date", "nunique"), mean=("boardings_06_24", "mean"),
                    median=("boardings_06_24", "median")).reset_index())
    comparison = (grouped.pivot(index=[dimension, "day_type"], columns="group", values=["days", "mean", "median"]))
    comparison.columns = [f"{metric}_{group}" for metric, group in comparison.columns]
    comparison = comparison.reset_index()
    comparison["rain_minus_candidate_pct"] = 100 * (
        comparison["mean_rain_at_least_0.1"] / comparison["mean_candidate_unconfirmed"] - 1)
    return grouped, comparison


def period_data(daily: pd.DataFrame, hourly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    selected = hourly[hourly["time_band"].isin(PERIODS)].copy()
    selected["period"] = selected["time_band"].map(PERIODS)
    counts = selected.groupby(["date", "period"], observed=True)["time_band"].nunique()
    if len(counts) != 1096 * 3 or not counts.eq(2).all():
        raise AssertionError("Each date and period must contain its two distinct subway hours")
    period = (selected.groupby(["date", "period"], observed=True)
              .agg(boardings=("passengers", "sum")).reset_index())
    period = period.merge(daily[["date", "day_type", "season", "year", "group", "rain_band"]],
                          on="date", how="left", validate="many_to_one")
    subset = period[(period["day_type"].eq("weekday")) & period["rain_band"].isin(
        ["candidate_unconfirmed", "0.1_to_lt5", "5_to_lt20", "at_least_20"])].copy()
    summary = (subset.groupby(["period", "rain_band"], observed=True)
               .agg(days=("date", "nunique"), mean=("boardings", "mean"),
                    median=("boardings", "median"), q25=("boardings", lambda s: s.quantile(.25)),
                    q75=("boardings", lambda s: s.quantile(.75))).reset_index())
    refs = summary[summary["rain_band"].eq("candidate_unconfirmed")][["period", "mean"]].rename(
        columns={"mean": "candidate_mean"})
    summary = summary.merge(refs, on="period", validate="many_to_one")
    summary["difference_pct"] = 100 * (summary["mean"] / summary["candidate_mean"] - 1)
    return period, subset, summary


def distribution_data(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    subset = daily[daily["group"].isin(["candidate_unconfirmed", "rain_at_least_0.1"])].copy()
    rows, tails = [], []
    for (day_type, group), part in subset.groupby(["day_type", "group"], observed=True):
        values = part["boardings_06_24"]
        q25, q75 = values.quantile(.25), values.quantile(.75)
        lower = q25 - 1.5 * (q75 - q25)
        upper = q75 + 1.5 * (q75 - q25)
        rows.append({"day_type": day_type, "group": group, "days": part.date.nunique(),
                     "mean": values.mean(), "median": values.median(), "q25": q25, "q75": q75,
                     "minimum": values.min(), "maximum": values.max(),
                     "lower_iqr_bound": lower, "upper_iqr_bound": upper,
                     "below_iqr_count": int(values.lt(lower).sum()),
                     "above_iqr_count": int(values.gt(upper).sum())})
        for row in part.nsmallest(3, "boardings_06_24").itertuples():
            tails.append({"date": row.date.strftime("%Y-%m-%d"), "day_type": day_type, "group": group,
                          "boardings_06_24": int(row.boardings_06_24), "daily_rain_mm": row.rain_mm,
                          "season": row.season})
    return pd.DataFrame(rows), pd.DataFrame(tails)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_csv(frame: pd.DataFrame, name: str) -> None:
    frame.to_csv(OUT / name, index=False, encoding="utf-8-sig", float_format="%.6f")


def main() -> None:
    daily, hourly = load_inputs()
    season, season_compare = seasonal_summary(daily, "season")
    year, year_compare = seasonal_summary(daily, "year")
    period, _, period_summary = period_data(daily, hourly)
    distribution, tails = distribution_data(daily)
    OUT.mkdir(parents=True, exist_ok=True)
    for frame, name in [(season, "seasonal_daily_groups.csv"), (season_compare, "seasonal_daily_comparison.csv"),
                        (year, "yearly_daily_groups.csv"), (year_compare, "yearly_daily_comparison.csv"),
                        (period, "daily_period_observations.csv"), (period_summary, "weekday_period_by_daily_rain.csv"),
                        (distribution, "daily_distribution.csv"), (tails, "low_tail_candidates.csv")]:
        save_csv(frame, name)
    group_counts = {str(k): int(v) for k, v in daily["group"].value_counts().items()}
    assert group_counts == {"candidate_unconfirmed": 625, "rain_at_least_0.1": 336,
                            "recorded_0.0": 132, "other_or_unresolved": 3}
    audit = {"run_time_kst": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec="seconds"),
             "input_sha256": {"daily_joined.csv": digest(DAILY), "hourly_subway.csv": digest(HOURLY)},
             "daily_dates": len(daily), "hourly_common_boarding_rows": len(hourly),
             "period_date_rows": len(period), "group_counts": group_counts,
             "hourly_sums_equal_daily": True,
             "scope": "Stage-two daily rainfall exploratory summaries; hourly weather not used; holidays remain in weekdays."}
    (OUT / "analysis_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["=== Interim additional daily-record analysis ===", f"Run time (KST): {audit['run_time_kst']}",
             f"Dates: {len(daily):,}; common boarding-hour rows: {len(hourly):,}; 2-hour period rows: {len(period):,}",
             f"Daily group counts: {group_counts}", "Each date's 18-hour sum matches the daily total: True",
             "Created: seasonal/yearly comparisons, three-period summaries, distributions, low-tail candidates",
             "Comparison: daily rain record; candidate is unconfirmed; weekdays include holidays.",
             "No hourly rainfall exposure, causal estimate, or final-stage model is calculated."]
    (OUT / "execution_log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def show(kind: str) -> None:
    audit = json.loads((OUT / "analysis_audit.json").read_text(encoding="utf-8"))
    print("=== Interim daily-record results ===")
    print("Actual analysis run (KST):", audit["run_time_kst"])
    print("Note: dry candidate is unconfirmed; weekdays include holidays.")
    if kind == "season":
        data = pd.read_csv(OUT / "seasonal_daily_comparison.csv")
        data = data[data.day_type.eq("weekday")].set_index("season").loc[["spring", "summer", "autumn", "winter"]]
        print("Season  | candidate days | rainy days | candidate mean | rainy mean | difference")
        for season, row in data.iterrows():
            print(f"{season:7} | {int(row['days_candidate_unconfirmed']):14d} | "
                  f"{int(row['days_rain_at_least_0.1']):10d} | {row['mean_candidate_unconfirmed']:14,.0f} | "
                  f"{row['mean_rain_at_least_0.1']:10,.0f} | {row['rain_minus_candidate_pct']:+6.2f}%")
    elif kind == "period":
        data = pd.read_csv(OUT / "weekday_period_by_daily_rain.csv")
        print("Period | daily-rain group | dates | mean boardings | diff vs candidate")
        for row in data.itertuples(index=False):
            print(f"{row.period:7} | {row.rain_band:21} | {row.days:5d} | {row.mean:14,.0f} | {row.difference_pct:+7.2f}%")
    else:
        data = pd.read_csv(OUT / "daily_distribution.csv")
        print("Day type | group | dates | Q1 | median | Q3 | below 1.5 IQR")
        for row in data.itertuples(index=False):
            print(f"{row.day_type:7} | {row.group:21} | {row.days:3d} | {row.q25:,.0f} | {row.median:,.0f} | {row.q75:,.0f} | {row.below_iqr_count}")
    print("Descriptive only: daily rainfall does not identify rain during a specific subway hour.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", choices=["season", "period", "distribution"])
    args = parser.parse_args()
    show(args.show) if args.show else main()
