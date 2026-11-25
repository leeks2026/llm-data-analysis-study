#!/usr/bin/env python3
"""Reproduce interim hourly input checks only; never estimate final outcomes."""
from __future__ import annotations
import datetime as dt
import io
import zipfile
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WEATHER = ROOT / "data/raw/weather/asos_seoul_hourly_2023_2025.zip"
DAILY = ROOT / "data/raw/weather/asos_seoul_2023_2025.csv"
SUBWAY = ROOT / "results/tables/hourly_subway.csv"
INTERIM = ROOT / "results/interim/tables/daily_joined.csv"


def main():
    frames, years = [], set()
    with zipfile.ZipFile(WEATHER) as outer:
        for entry in sorted(outer.infolist(), key=lambda x: x.filename):
            with zipfile.ZipFile(io.BytesIO(outer.read(entry))) as inner:
                files = inner.infolist()
                if len(files) != 1 or not files[0].filename.endswith(".csv"):
                    raise ValueError("Unexpected KMA file contents")
                data = pd.read_csv(io.BytesIO(inner.read(files[0])), encoding="cp949")
                data["timestamp"] = pd.to_datetime(data["일시"], errors="raise")
                if not data["지점"].eq(108).all():
                    raise ValueError("Unexpected station")
                years.update(data.timestamp.dt.year.unique())
                frames.append(data)
    weather = pd.concat(frames, ignore_index=True).sort_values("timestamp").reset_index(drop=True)
    expected = pd.date_range("2023-01-01", "2025-12-31 23:00", freq="h")
    if years != {2023, 2024, 2025} or not pd.DatetimeIndex(weather.timestamp).equals(expected):
        raise ValueError("Unexpected year or hourly coverage")
    weather["rain"] = pd.to_numeric(weather["강수량(mm)"], errors="raise")
    daily = pd.read_csv(DAILY, encoding="cp949", parse_dates=["일시"])[["일시", "일강수량(mm)"]]
    if daily["일시"].duplicated().any():
        raise ValueError("Duplicate daily weather")
    result = []
    for lag in [0, 1]:
        key = (weather.timestamp - pd.Timedelta(hours=lag)).dt.normalize()
        sums = weather.groupby(key).rain.sum(min_count=1).rename("hour_sum")
        pair = daily.merge(sums, left_on="일시", right_index=True, how="left", validate="one_to_one")
        valid = pair["일강수량(mm)"].gt(0) & pair.hour_sum.notna()
        result.append((int(valid.sum()), int((pair.loc[valid, "일강수량(mm)"] - pair.loc[valid, "hour_sum"]).abs().lt(.05).sum())))
    hourly = pd.read_csv(SUBWAY, parse_dates=["date"])
    bands = [f"{h:02d}-{h+1:02d}" for h in range(6, 24)]
    hourly = hourly[hourly.population.eq("common") & hourly.time_band.isin(bands)]
    panel = (hourly.pivot(index=["date", "time_band"], columns="direction", values="passengers")
             .rename(columns={"승차":"boardings", "하차":"alightings"}).reset_index())
    daily_subway = panel.groupby("date", as_index=False)[["boardings", "alightings"]].sum()
    reference = pd.read_csv(INTERIM, parse_dates=["date"])
    reference = reference.loc[reference.population.eq("common"), ["date", "boardings_06_24", "alightings_06_24"]]
    pair = daily_subway.merge(reference, on="date", how="outer", validate="one_to_one", indicator=True)
    if (len(panel) != 1096 * 18 or not pair._merge.eq("both").all() or
        not pair.boardings.eq(pair.boardings_06_24).all() or not pair.alightings.eq(pair.alightings_06_24).all()):
        raise ValueError("Subway totals failed to reconcile")
    kst = dt.timezone(dt.timedelta(hours=9))
    print("=== Interim: hourly input and alignment checks ===")
    print("Recheck time (KST):", dt.datetime.now(kst).isoformat(timespec="seconds"))
    print("Station: Seoul ASOS 108; years: 2023-2025; hourly rows:", len(weather))
    print("Rainfall blank / 0.0 / positive:", int(weather.rain.isna().sum()),
          int(weather.rain.eq(0).sum()), int(weather.rain.gt(0).sum()))
    print("Daily positive-rain days checked:", result[0][0])
    print("Daily sum agreement, same labeled date:", result[0][1])
    print("Daily sum agreement, assume timestamp is end:", result[1][1])
    print("Subway date-hour rows:", len(panel), "; daily boarding/alighting totals verified against interim")
    print("Scope: input checks only; no final outcome estimates on this screen")


if __name__ == "__main__":
    main()
