from __future__ import annotations

import unittest

from vendorverdict.cli import run_health_check


class HealthCheckTests(unittest.TestCase):
    def test_health_check_passes_without_live_evidence(self):
        self.assertEqual(run_health_check(use_live_evidence=False), 0)


if __name__ == "__main__":
    unittest.main()
