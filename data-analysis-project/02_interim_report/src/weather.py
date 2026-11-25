"""Load KMA Seoul ASOS daily data while preserving ambiguous precipitation blanks."""
from __future__ import annotations

import hashlib
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def read_weather(path: Path) -> tuple[pd.DataFrame, dict]:
    raw = None
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            raw = pd.read_csv(path, encoding=enc, dtype="string")
            break
        except UnicodeDecodeError:
            continue
    if raw is None:
        raise ValueError(f"Cannot decode {path}")
    raw.columns = raw.columns.str.strip().str.lstrip("\ufeff")
    raw = raw.dropna(how="all").copy()

    def column(prefixes: tuple[str, ...], required: bool = True) -> str | None:
        matches = [c for c in raw.columns if any(c.startswith(p) for p in prefixes)]
        if not matches and required:
            raise ValueError(f"Required column {prefixes} not found: {list(raw.columns)}")
        return matches[0] if matches else None

    date_col = column(("일시", "시간", "날짜"))
    rain_col = column(("일강수량",))
    temp_col = column(("평균기온",))
    duration_col = column(("강수 계속시간", "강수계속시간"), False)
    article_col = column(("기사",), False)
    station_col = column(("지점",), False)
    result = pd.DataFrame(index=raw.index)
    result["date"] = pd.to_datetime(raw[date_col].str.strip(), errors="coerce")
    if result.date.isna().any():
        raise ValueError(f"Unparseable weather dates: {int(result.date.isna().sum())}")
    if station_col is not None:
        station = raw[station_col].str.strip()
        if not station.str.contains(r"108|서울", regex=True, na=False).all():
            raise ValueError("Weather file includes a station other than Seoul(108)")
    if result.date.duplicated().any():
        raise ValueError("Weather file has duplicate dates")
    result["rain_source_text"] = raw[rain_col].fillna("").str.strip()
    result["rain_mm"] = pd.to_numeric(result.rain_source_text.replace("", pd.NA), errors="coerce")
    unexpected = result.rain_source_text.ne("") & result.rain_mm.isna()
    if unexpected.any() or (result.rain_mm.dropna() < 0).any():
        raise ValueError("Unexpected or negative precipitation values require source review")
    result["temp_c"] = pd.to_numeric(raw[temp_col].str.strip(), errors="coerce")
    result["rain_duration_hr"] = (pd.to_numeric(raw[duration_col].str.strip(), errors="coerce")
                                  if duration_col else np.nan)
    result["weather_article"] = raw[article_col].fillna("").str.strip() if article_col else ""
    result["rain_category"] = np.select(
        [result.rain_mm.ge(0.1).fillna(False), result.rain_mm.eq(0).fillna(False),
         result.rain_mm.gt(0).fillna(False) & result.rain_mm.lt(0.1).fillna(False)],
        ["at_least_0.1mm", "recorded_0.0mm", "positive_below_0.1mm"], default="blank_unresolved")
    # A missing amount is never changed to zero. This is an explicitly tentative sensitivity group,
    # not proof that a precipitation sensor observed no rainfall on the day.
    precip_phenomena = r"비|눈|우박|진눈깨비|소나기|싸락|이슬비|서리|안개비"
    event_present = result.weather_article.str.contains(precip_phenomena, regex=True, na=False)
    result["dry_candidate_unconfirmed"] = (result.rain_mm.isna() & result.rain_duration_hr.isna() &
                                            result.temp_c.notna() & ~event_present &
                                            bool(duration_col) & bool(article_col))
    result = result.sort_values("date").reset_index(drop=True)
    expected = pd.date_range("2023-01-01", "2025-12-31")
    missing_days = sorted(set(expected) - set(result.date))
    extra_days = sorted(set(result.date) - set(expected))
    audit = {"source_file": path.name, "encoding": enc, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
             "rows": len(result), "date_first": result.date.min().strftime("%Y-%m-%d"),
             "date_last": result.date.max().strftime("%Y-%m-%d"), "missing_calendar_days": len(missing_days),
             "out_of_range_days": len(extra_days), "rain_blank_days": int(result.rain_mm.isna().sum()),
             "temp_missing_days": int(result.temp_c.isna().sum()),
             "dry_candidates_unconfirmed": int(result.dry_candidate_unconfirmed.sum()),
             "rain_category_counts": result.rain_category.value_counts().to_dict(),
             "rain_duration_available": duration_col is not None,
             "article_available": article_col is not None}
    return result, audit
