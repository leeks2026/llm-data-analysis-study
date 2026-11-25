"""Read, reconcile, and audit the official annual Seoul Metro CSV files."""
from __future__ import annotations

import re
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "subway"
TABLES = ROOT / "results" / "tables"
BEFORE = "before_06"
AFTER = "after_24"
HOURS = [f"{h:02d}-{h+1:02d}" for h in range(6, 24)]
ALL_BANDS = [BEFORE, *HOURS, AFTER]
KEY = ["date", "line", "station_code", "direction"]


def read_csv_any_encoding(path: Path) -> tuple[pd.DataFrame, str]:
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return pd.read_csv(path, encoding=enc, dtype="string"), enc
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode {path}")


def canonical_band(name: str) -> str | None:
    text = str(name).strip().replace(" ", "")
    if text in ("06시이전", "06시이전시간대"):
        return BEFORE
    if text in ("24시이후", "24시이후시간대"):
        return AFTER
    m = re.fullmatch(r"(\d{2})(?:시)?-(\d{2})(?:시|시간대)?", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return None


def load_year(path: Path, year: int) -> tuple[pd.DataFrame, dict]:
    raw, encoding = read_csv_any_encoding(path)
    original_rows = len(raw)
    empty_rows = int(raw.isna().all(axis=1).sum())
    raw = raw.dropna(how="all").copy()
    aliases = {"수송일자": "date", "날짜": "date", "호선": "line",
               "역번호": "station_code", "역명": "station_name",
               "승하차구분": "direction", "구분": "direction"}
    names = {c: aliases[c] for c in raw.columns if c in aliases}
    for c in raw.columns:
        band = canonical_band(c)
        if band:
            names[c] = band
    raw = raw.rename(columns=names)
    required = ["date", "line", "station_code", "station_name", "direction", *ALL_BANDS]
    if len(set(raw.columns)) != len(raw.columns):
        raise ValueError(f"Duplicate column after mapping {path.name}")
    if missing := set(required) - set(raw.columns):
        raise ValueError(f"Missing columns in {path.name}: {sorted(missing)}")
    df = raw[required].copy()
    for c in ["date", "line", "station_code", "station_name", "direction"]:
        df[c] = df[c].str.strip()
    if df[KEY].isna().any(axis=None):
        raise ValueError(f"Incomplete identifying columns in {path.name}")
    df["date"] = pd.to_datetime(df["date"], errors="raise")
    if not df.date.dt.year.eq(year).all():
        raise ValueError(f"Out-of-year dates in {path.name}")
    if set(df.direction.unique()) != {"승차", "하차"}:
        raise ValueError(f"Unexpected passenger directions in {path.name}")
    for c in ALL_BANDS:
        df[c] = pd.to_numeric(df[c].str.replace(",", "", regex=False), errors="coerce")
    if df[ALL_BANDS].isna().any(axis=None) or (df[ALL_BANDS] < 0).any(axis=None):
        raise ValueError(f"Missing, invalid, or negative passenger counts in {path.name}")
    df[ALL_BANDS] = df[ALL_BANDS].astype("int64")
    duplicates = int(df.duplicated(KEY, keep=False).sum())
    if duplicates:
        raise ValueError(f"{path.name}: {duplicates} duplicate key rows")
    all_days = pd.date_range(f"{year}-01-01", f"{year}-12-31")
    missing_days = sorted(set(all_days) - set(df.date.unique()))
    totals = df.groupby("direction", observed=True)[ALL_BANDS].sum().sum(axis=1)
    audit = {"year": year, "filename": path.name, "encoding": encoding,
             "raw_rows": original_rows, "fully_empty_rows": empty_rows,
             "valid_rows": len(df), "candidate_key_duplicate_rows": duplicates,
             "first_date": df.date.min().strftime("%Y-%m-%d"),
             "last_date": df.date.max().strftime("%Y-%m-%d"),
             "observed_dates": int(df.date.nunique()), "missing_dates": len(missing_days),
             "station_line_code_pairs": int(df[["line", "station_code"]].drop_duplicates().shape[0]),
             "boarding_all_bands": int(totals.get("승차", 0)),
             "alighting_all_bands": int(totals.get("하차", 0))}
    return df, audit


def load_and_audit() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    data, audits = [], []
    for year in (2023, 2024, 2025):
        path = RAW / f"subway_{year}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing {path}; run python scripts/collect_seoul.py")
        df, audit = load_year(path, year)
        data.append(df)
        audits.append(audit)
    data = pd.concat(data, ignore_index=True)
    if data.duplicated(KEY).any():
        raise ValueError("Overlapping annual files: duplicate natural keys")
    coverage = (data.groupby(["line", "station_code"], observed=True)
                .agg(rows=("date", "size"), dates=("date", "nunique"),
                     names=("station_name", lambda x: " | ".join(sorted(set(x.dropna())))))
                .reset_index())
    # Both directions on all 1,096 dates, with unique keys, imply a complete panel.
    coverage["common_station"] = coverage.dates.eq(1096) & coverage.rows.eq(2 * 1096)
    return data, pd.DataFrame(audits), coverage


def aggregate(data: pd.DataFrame, coverage: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    common = coverage.loc[coverage.common_station, ["line", "station_code"]]
    if common.empty:
        raise ValueError("No station with complete observations on every day")
    grouped_outputs = []
    check = []
    for label, frame in (("common", data.merge(common, on=["line", "station_code"], validate="many_to_one")),
                         ("all", data)):
        # Aggregate stations before melt to keep memory small; summation commutes with the reshape.
        wide = frame.groupby(["date", "direction"], observed=True)[ALL_BANDS].sum().reset_index()
        long = wide.melt(id_vars=["date", "direction"], value_vars=ALL_BANDS,
                         var_name="time_band", value_name="passengers")
        for direction in ("승차", "하차"):
            original = int(frame.loc[frame.direction == direction, ALL_BANDS].to_numpy().sum())
            transformed = int(long.loc[long.direction == direction, "passengers"].sum())
            if original != transformed:
                raise AssertionError(f"Passenger total changed for {label}/{direction}")
            check.append({"population": label, "direction": direction,
                          "before_reshape": original, "after_reshape": transformed,
                          "equal": original == transformed})
        long["population"] = label
        grouped_outputs.append(long)
    hourly = pd.concat(grouped_outputs, ignore_index=True)
    daytime = hourly[hourly.time_band.isin(HOURS)].copy()
    daily = (daytime.groupby(["population", "date", "direction"], observed=True)
             .passengers.sum().unstack("direction").rename(columns={"승차": "boardings_06_24", "하차": "alightings_06_24"})
             .reset_index())
    daily["weekday"] = daily.date.dt.dayofweek
    daily["weekend"] = daily.weekday >= 5
    daily["year"] = daily.date.dt.year
    daily["month"] = daily.date.dt.month
    return daily, hourly, pd.DataFrame(check)


def save_subway_outputs() -> dict:
    TABLES.mkdir(parents=True, exist_ok=True)
    data, audit, coverage = load_and_audit()
    daily, hourly, checks = aggregate(data, coverage)
    audit.to_csv(TABLES / "subway_source_audit.csv", index=False, encoding="utf-8-sig")
    coverage.to_csv(TABLES / "station_coverage.csv", index=False, encoding="utf-8-sig")
    checks.to_csv(TABLES / "reshape_validation.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(TABLES / "daily_subway.csv", index=False, encoding="utf-8-sig")
    hourly.to_csv(TABLES / "hourly_subway.csv", index=False, encoding="utf-8-sig")
    board = data.loc[data.direction.eq("승차"), ["date", "line", "station_code", *HOURS]].copy()
    board["boardings_06_24"] = board[HOURS].sum(axis=1)
    station_size = (board.groupby(["line", "station_code"], observed=True)
                    .agg(observed_days=("date", "nunique"), mean_boardings_06_24=("boardings_06_24", "mean"),
                         median_boardings_06_24=("boardings_06_24", "median")).reset_index())
    station_size = station_size.merge(coverage[["line", "station_code", "names", "common_station"]],
                                      on=["line", "station_code"], validate="one_to_one")
    station_size.to_csv(TABLES / "station_boarding_scale.csv", index=False, encoding="utf-8-sig")
    # Save a traceable, selected station/date example for a human source check.
    sample = data.loc[(data.date == pd.Timestamp("2023-01-01")) & (data.line == "1호선") &
                      (data.station_code == "150"), [*KEY, "station_name", *ALL_BANDS]]
    sample.to_csv(TABLES / "source_crosscheck_sample.csv", index=False, encoding="utf-8-sig")
    return {"source_audit": audit, "station_coverage": coverage, "station_size": station_size, "reshape_checks": checks,
            "daily": daily, "hourly": hourly}
