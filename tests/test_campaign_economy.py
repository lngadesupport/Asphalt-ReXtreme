import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from rextreme_economy import campaign_price, repeat_reward_multiplier


class CampaignEconomyTests(unittest.TestCase):
    def test_80_percent_discount(self):
        self.assertEqual(campaign_price(100000), 20000)
        self.assertEqual(campaign_price(50000), 10000)
        self.assertEqual(campaign_price(125000), 25000)

    def test_repeat_grace(self):
        self.assertEqual(repeat_reward_multiplier(1), 1.0)
        self.assertEqual(repeat_reward_multiplier(10), 1.0)

    def test_repeat_decay_and_floor(self):
        self.assertAlmostEqual(repeat_reward_multiplier(11), 0.998)
        self.assertAlmostEqual(repeat_reward_multiplier(12), 0.996)
        self.assertAlmostEqual(repeat_reward_multiplier(15), 0.990)
        self.assertAlmostEqual(repeat_reward_multiplier(20), 0.980)
        self.assertAlmostEqual(repeat_reward_multiplier(50), 0.980)
        self.assertAlmostEqual(repeat_reward_multiplier(500), 0.980)


if __name__ == "__main__":
    unittest.main()
