import json
import unittest
from dataclasses import replace
from import_dataset import read_dataset
from matching import ROOT, Request, load_profiles, catalog_options, recommend, parse_date, format_card


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profiles = load_profiles()
        cls.request = Request("Алматы", "2026-10-10", "свадьба", "Фотограф", 600000)

    def test_all_source_data_and_flags_preserved(self):
        self.assertEqual(self.profiles, read_dataset(ROOT / 'data/contractors.csv'))
        self.assertEqual(len(self.profiles), 66)
        self.assertEqual(len(catalog_options(self.profiles)['categories']), 17)
        self.assertEqual(sum(p['synthetic'] for p in self.profiles), 13)
        self.assertEqual(sum(p['price_imputed'] for p in self.profiles), 18)
        self.assertEqual(sum(p['max_hours'] is None for p in self.profiles), 9)
        script = (ROOT / 'catalog-data.js').read_text(encoding='utf-8')
        self.assertEqual(json.loads(script.removeprefix('window.HACKALEM_DATA = ').rstrip(';\n'))['profiles'], self.profiles)

    def test_known_recommendations_and_constraints(self):
        result = recommend(self.request, self.profiles)
        self.assertEqual([p['id'] for p in result.profiles], ['HK-53108', 'HK-30583', 'HK-16628'])
        self.assertEqual(recommend(replace(self.request, budget_kzt=1), self.profiles).total, 0)
        for p in result.profiles:
            self.assertNotIn(self.request.event_date, p['busy_dates'])
            self.assertLessEqual(p['price_kzt'], self.request.budget_kzt)
        filtered = recommend(replace(self.request, duration_hours=10, language='английский'), self.profiles)
        self.assertEqual([p['id'] for p in filtered.profiles], ['HK-16628'])

    def test_multiple_categories_and_not_applicable_hours(self):
        p = next(p for p in self.profiles if len(p['categories']) > 1)
        d = next('2026-10-%02d'%n for n in range(1,32) if '2026-10-%02d'%n not in p['busy_dates'])
        req = Request(p['city'], d, p['formats'][0], p['categories'][-1], p['price_kzt'])
        self.assertEqual(recommend(req, [p]).profiles, [p])
        p = next(p for p in self.profiles if p['max_hours'] is None)
        p = {**p, 'busy_dates': []}
        req = Request(p['city'], '2026-10-10', p['formats'][0], p['categories'][0], p['price_kzt'], 12)
        self.assertEqual(recommend(req, [p]).profiles, [p])
        self.assertIn('не применим', format_card(p))

    def test_calendar_boundaries_and_bad_input(self):
        self.assertEqual(parse_date('10.10.2026'), '2026-10-10')
        for valid in ('2026-09-23','2026-12-31'):
            self.assertEqual(parse_date(valid), valid)
        for invalid in ('2026-09-22','2027-01-01','2026-02-30','abc'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_date(invalid)


if __name__ == '__main__':
    unittest.main()
