"""Checks for the extra stage-two daily-record analysis."""
from __future__ import annotations

import unittest
import pandas as pd

from scripts.run_interim_enrichment import (
    PERIODS, SEASONS, assign_daily_groups, distribution_data, load_inputs, period_data,
)


class InterimEnrichmentTests(unittest.TestCase):
    def test_blank_zero_and_rain_boundaries_remain_distinct(self):
        sample = pd.DataFrame({"rain_mm": [None, None, 0, .1, 4.999, 5, 19.999, 20],
                               "dry_candidate_unconfirmed": [True, False, False, False, False, False, False, False]})
        result = assign_daily_groups(sample)
        self.assertEqual(result.rain_band.tolist(), ["candidate_unconfirmed", "other_or_unresolved", "recorded_0.0",
                         "0.1_to_lt5", "0.1_to_lt5", "5_to_lt20", "5_to_lt20", "at_least_20"])
        self.assertEqual(result.group.tolist()[:3], ["candidate_unconfirmed", "other_or_unresolved", "recorded_0.0"])
        with self.assertRaises(ValueError):
            assign_daily_groups(pd.DataFrame({"rain_mm": [3.0], "dry_candidate_unconfirmed": [True]}))

    def test_seasons_and_periods_cover_the_intended_calendar_and_hours(self):
        self.assertEqual([SEASONS[m] for m in (12, 1, 2, 3, 6, 9)],
                         ["winter", "winter", "winter", "spring", "summer", "autumn"])
        self.assertEqual(PERIODS, {"07-08": "morning", "08-09": "morning", "12-13": "midday",
                                   "13-14": "midday", "17-18": "evening", "18-19": "evening"})

    @classmethod
    def setUpClass(cls):
        cls.daily, cls.hourly = load_inputs()

    def test_two_hour_period_matches_original_hour_values(self):
        periods, _, _ = period_data(self.daily, self.hourly)
        day = pd.Timestamp("2023-01-01")
        original = self.hourly.loc[self.hourly.date.eq(day) & self.hourly.time_band.isin(["07-08", "08-09"]),
                                   "passengers"]
        actual = periods.loc[periods.date.eq(day) & periods.period.eq("morning"), "boardings"]
        self.assertEqual(len(original), 2)
        self.assertEqual(len(actual), 1)
        self.assertEqual(int(actual.iloc[0]), int(original.sum()))

    def test_daily_group_distribution_matches_input_rows(self):
        distribution, _ = distribution_data(self.daily)
        subset = self.daily[(self.daily.day_type.eq("weekday")) &
                            (self.daily.group.eq("rain_at_least_0.1"))]
        reported = distribution[(distribution.day_type.eq("weekday")) &
                                (distribution.group.eq("rain_at_least_0.1"))].iloc[0]
        self.assertEqual(int(reported["days"]), subset.date.nunique())
        self.assertEqual(float(reported["median"]), float(subset.boardings_06_24.median()))
        self.assertEqual(float(reported["q25"]), float(subset.boardings_06_24.quantile(.25)))
        self.assertEqual(float(reported["q75"]), float(subset.boardings_06_24.quantile(.75)))


if __name__ == "__main__":
    unittest.main()
