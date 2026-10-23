"""Unit tests with synthetic numerical fixtures, NOT experimental measurements."""

import unittest
from fractions import Fraction

from fairness import cell, jain_index, service_ratio, summarize, validate_budget_error


def fixture(demanded, granted, role="honest", requests=3, rejected=0):
    return dict(demanded=demanded, granted=granted, role=role, requests=requests,
                accepted_requests=requests - rejected, budget_rejected_requests=rejected)


class MetricUnitTests(unittest.TestCase):
    def test_service_ratio(self):
        self.assertEqual(service_ratio(30, 20), Fraction(2, 3))

    def test_zero_demand_is_undefined(self):
        self.assertIsNone(service_ratio(0, 0))

    def test_jain_equal_service(self):
        self.assertEqual(jain_index([100, 30, 30], [50, 15, 15]), 1)

    def test_jain_one_agent_served(self):
        self.assertEqual(jain_index([100, 30, 30], [100, 0, 0]), Fraction(1, 3))

    def test_jain_uses_service_ratios_not_grants(self):
        self.assertEqual(jain_index([100, 30, 30], [40, 30, 30]), Fraction(8, 9))

    def test_jain_excludes_idle_delegates(self):
        self.assertEqual(jain_index([20, 0, 40], [10, 0, 20]), 1)

    def test_jain_all_zero_grants_is_undefined(self):
        self.assertIsNone(jain_index([20, 40], [0, 0]))
        self.assertIsNone(jain_index([], []))
        self.assertIsNone(jain_index([0], [0]))

    def test_utilization_stranding_and_request_denominators(self):
        agents = [fixture(100, 60, "aggressive", 10, 4), fixture(30, 20, rejected=1),
                  fixture(30, 10, rejected=2)]
        m = summarize(agents, 100, adversarial=True)
        self.assertEqual(m["utilization"], Fraction(9, 10))
        self.assertEqual(m["stranded_capacity"], 10)
        self.assertEqual(m["budget_rejection_rate"], Fraction(7, 16))
        self.assertEqual(m["starvation_rate"], Fraction(3, 6))
        self.assertEqual(m["honest_requests"], 6)

    def test_stranding_undefined_when_demand_below_budget(self):
        m = summarize([fixture(20, 20)], 100, True)
        self.assertIsNone(m["stranded_capacity"])
        self.assertEqual(m["utilization"], Fraction(1, 5))

    def test_interleaved_starvation_not_applicable(self):
        m = summarize([fixture(30, 20, rejected=1)], 100, False)
        self.assertIsNone(m["starvation_rate"])
        self.assertEqual(m["honest_budget_rejection_rate"], Fraction(1, 3))

    def test_no_honest_requests_is_undefined(self):
        m = summarize([fixture(10, 10, "aggressive", 1)], 100, True)
        self.assertIsNone(m["starvation_rate"])
        m = summarize([], 100, True)
        self.assertIsNone(m["budget_rejection_rate"])

    def test_invalid_inputs_fail_visibly(self):
        for demanded, granted in ((-1, 0), (10, -1), (10, 11), (0, 1)):
            with self.assertRaises(ValueError):
                service_ratio(demanded, granted)
        with self.assertRaises(ValueError):
            jain_index([1], [])
        with self.assertRaises(ValueError):
            summarize([fixture(200, 110)], 100, True)
        with self.assertRaises(ValueError):
            summarize([], 0, True)

    def test_export_undefined_and_fraction(self):
        self.assertEqual(cell(None), "N/A")
        self.assertEqual(cell(Fraction(1, 3)), "0.333333333333")

    def test_budget_error_selector_and_arguments(self):
        # Synthetic ABI fixture: need 7 from surplus, only 2 available.
        args = (7).to_bytes(32, "big").hex() + (2).to_bytes(32, "big").hex()
        validate_budget_error("0xd5490551" + args, 10, 3, 2)
        for data in ("0xdeadbeef" + args, "0xd5490551" + args[:-2], "0x"):
            with self.assertRaises(ValueError):
                validate_budget_error(data, 10, 3, 2)
        with self.assertRaises(ValueError):
            validate_budget_error("0xd5490551" + args, 10, 3, 1)


if __name__ == "__main__":
    unittest.main()
