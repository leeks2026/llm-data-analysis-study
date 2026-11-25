#!/usr/bin/env python3
"""Regenerate the audited station-group hourly subway input from raw CSVs."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.subway import aggregate, load_and_audit

if __name__ == "__main__":
    source, source_audit, coverage = load_and_audit()
    _, hourly, reshape = aggregate(source, coverage)
    if not reshape["equal"].all():
        raise ValueError("Subway reshape changed passenger totals")
    out = ROOT / "results/tables/hourly_subway.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    hourly.to_csv(out, index=False, encoding="utf-8-sig")
    print("Saved audited hourly subway input:", out)
    print("Rows:", len(hourly), "; common station/line pairs:", int(coverage.common_station.sum()))
