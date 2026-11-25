"""Focused checks for second-stage input integrity and weather joining."""
import tempfile
import unittest
from pathlib import Path
import pandas as pd

from scripts.run_interim import join_weather
from src.subway import canonical_band, load_year
from src.weather import read_weather


class InterimIntegrityTests(unittest.TestCase):
    def test_yearly_time_band_spellings(self):
        self.assertEqual(canonical_band("06-07시간대"), "06-07")
        self.assertEqual(canonical_band("06시-07시"), "06-07")

    def test_duplicate_source_key_is_rejected(self):
        row = {"날짜": "2024-01-01", "호선": "1호선", "역번호": "150", "역명": "서울역", "구분": "승차"}
        row.update({"06시 이전": "1", "24시 이후": "1"})
        row.update({f"{h:02d}시-{h+1:02d}시": "1" for h in range(6, 24)})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.csv"
            other_direction = {**row, "구분": "하차"}
            pd.DataFrame([row, other_direction, row]).to_csv(path, index=False, encoding="utf-8-sig")
            with self.assertRaisesRegex(ValueError, "duplicate key"):
                load_year(path, 2024)

    def test_missing_weather_is_never_zero_filled(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weather.csv"
            pd.DataFrame({"지점": [108, 108, 108], "일시": ["2023-01-01", "2023-01-02", "2023-01-03"],
                          "평균기온(°C)": [1, 2, 3], "일강수량(mm)": [None, 0, 5],
                          "강수 계속시간(hr)": [None, .1, 2]}).to_csv(path, index=False, encoding="utf-8-sig")
            result, _ = read_weather(path)
            self.assertTrue(pd.isna(result.loc[0, "rain_mm"]))
            self.assertEqual(result.loc[0, "rain_category"], "blank_unresolved")
            self.assertEqual(result.loc[1, "rain_category"], "recorded_0.0mm")
            self.assertEqual(result.loc[2, "rain_category"], "at_least_0.1mm")

    def test_unmatched_weather_date_stops_analysis(self):
        dates = pd.to_datetime(["2023-01-01", "2023-01-02"])
        weather = pd.DataFrame({"date": [dates[0]], "rain_mm": [0.0], "temp_c": [1.0],
                                "rain_duration_hr": [0.0], "weather_article": [""],
                                "rain_category": ["recorded_0.0mm"], "dry_candidate_unconfirmed": [False]})
        daily = pd.DataFrame({"date": dates})
        hourly = pd.DataFrame({"date": dates, "passengers": [10, 20]})
        with self.assertRaisesRegex(ValueError, "Weather observations missing"):
            join_weather(daily, hourly, weather)


if __name__ == "__main__":
    unittest.main()
