"""Display saved results from the actual second-stage execution for review."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "interim"
TABLES = OUT / "tables"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("part", choices=("source", "join", "precip", "eda"))
    args = parser.parse_args()
    kst = dt.timezone(dt.timedelta(hours=9))
    print("2차 중간 분석 실행 결과 |", dt.datetime.now(kst).strftime("%Y-%m-%d %H:%M KST"))
    print("실행 경로:", ROOT)
    if args.part == "source":
        audit = pd.read_csv(TABLES / "subway_source_audit.csv")
        print("\n[원자료] 연도별 파일 검사 (유효 행, 완전 빈 행, 고유키 중복)")
        print(audit[["year", "valid_rows", "fully_empty_rows", "candidate_key_duplicate_rows", "observed_dates"]].to_string(index=False))
        print("\n[원본 직접 대조] 서울역 1호선 2023-01-01 06-07 승차")
        print(pd.read_csv(TABLES / "source_direct_comparison.csv")[["raw_count", "normalized_count", "equal"]].to_string(index=False))
    elif args.part == "join":
        with (OUT / "weather_merge_audit.json").open(encoding="utf-8") as f:
            audit = json.load(f)
        print("\n[시간대 변환 전후] 승차·하차 합계 보존")
        print(pd.read_csv(TABLES / "reshape_validation.csv").to_string(index=False))
        print("\n[날짜 결합] 기상 미매칭 날짜:", audit["unmatched_subway_dates"])
        print("시간대 집계 행 수 before / after:", audit["hourly_rows_before_merge"], "/", audit["hourly_rows_after_merge"])
        print("승하차 합계 보존:", audit["hourly_passenger_sum_before_merge"] == audit["hourly_passenger_sum_after_merge"])
        print("※ 행 수는 공통 역과 전체 역 두 집계를 함께 포함")
    elif args.part == "precip":
        with (OUT / "weather_merge_audit.json").open(encoding="utf-8") as f:
            audit = json.load(f)
        print("\n[기상자료] 고유 관측일:", audit["rows"])
        for key in ("at_least_0.1mm", "recorded_0.0mm", "blank_unresolved"):
            print(key, "=", audit["rain_category_counts"].get(key, 0))
        print("\n[교차 확인] 강수 계속시간 기록 여부")
        print(pd.read_csv(TABLES / "rain_vs_duration_crosscheck.csv").to_string(index=False))
        print("빈칸 중 미확인 무강수 후보:", audit["dry_candidates_unconfirmed"], "일")
        print("※ 빈칸 후보는 무강수로 확정된 자료가 아님")
    else:
        desc = pd.read_csv(TABLES / "precip_weekend_descriptive.csv")
        selected = desc[desc.analysis_group.isin(["Rain >=0.1 mm", "Blank: dry candidate (unconfirmed)"])]
        print("\n[기초 집계] 공통 역, 일별 06~24시 승차")
        print(selected[["analysis_group", "weekend", "days", "mean_boardings", "median_boardings"]].round(0).to_string(index=False))
        print("※ 후보군과 강수 기록일의 기술통계, 인과 효과 아님")


if __name__ == "__main__":
    main()
