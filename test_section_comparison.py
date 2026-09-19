import unittest

from section_comparison import percentage_variation, relative_capacity


class PercentageTests(unittest.TestCase):
    def test_equal_values(self):
        self.assertEqual(percentage_variation(100, 100), 0)

    def test_area_ninety_percent(self):
        self.assertEqual(percentage_variation(100, 90), -10)

    def test_zx_eighty_percent(self):
        self.assertEqual(percentage_variation(100, 80), -20)

    def test_zx_seventy_percent(self):
        self.assertEqual(percentage_variation(100, 70), -30)

    def test_zx_increase(self):
        self.assertAlmostEqual(relative_capacity(100, 110), 110)
        self.assertAlmostEqual(percentage_variation(100, 110), 10)


if __name__ == "__main__":
    unittest.main()
