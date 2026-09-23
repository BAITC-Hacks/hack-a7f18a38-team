import unittest
from dataclasses import replace
from matching import Request, load_profiles, recommend, format_result


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.profiles = load_profiles()
        self.request = Request("Алматы", "2026-10-10", "свадьба", "Фотограф", 600000)

    def test_top_three_sorted_and_available(self):
        result = recommend(self.request, self.profiles)
        self.assertEqual([p["id"] for p in result.profiles], ["photo-2", "photo-3", "photo-4"])
        self.assertEqual(result.rejection_counts["busy"], 1)
        self.assertIn("ДЕМО", format_result(result, self.request))

    def test_constraints(self):
        result = recommend(replace(self.request, language="казахский", duration_hours=10), self.profiles)
        self.assertEqual([p["id"] for p in result.profiles], ["photo-3"])
        for changes in ({"budget_kzt":0}, {"city":"Нет города"}, {"duration_hours":20}, {"language":"Нет языка"}, {"event_format":"Нет формата"}, {"category":"Нет категории"}):
            with self.subTest(changes=changes):
                self.assertEqual(recommend(replace(self.request, **changes), self.profiles).status, "no_matches")

    def test_invalid_date(self):
        with self.assertRaises(ValueError):
            recommend(replace(self.request, event_date="2026-02-30"), self.profiles)


if __name__ == "__main__":
    unittest.main()
