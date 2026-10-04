"""Tests for the tamper-evident audit hash chain."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.audit.chain import _hash_entry


class HashChainTests(unittest.TestCase):
    def test_deterministic(self):
        h1 = _hash_entry(1, __import__("datetime").datetime.fromisoformat("2025-01-01T00:00:00+00:00"),
                          "u1", "u@x.com", "x.create", "x", "1", {"k": "v"}, "0" * 64)
        h2 = _hash_entry(1, __import__("datetime").datetime.fromisoformat("2025-01-01T00:00:00+00:00"),
                          "u1", "u@x.com", "x.create", "x", "1", {"k": "v"}, "0" * 64)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_changes_on_tampering(self):
        h1 = _hash_entry(1, __import__("datetime").datetime.fromisoformat("2025-01-01T00:00:00+00:00"),
                          "u1", "u@x.com", "x.create", "x", "1", {"k": "v"}, "0" * 64)
        h2 = _hash_entry(1, __import__("datetime").datetime.fromisoformat("2025-01-01T00:00:00+00:00"),
                          "u1", "u@x.com", "x.create", "x", "1", {"k": "tampered"}, "0" * 64)
        self.assertNotEqual(h1, h2)


if __name__ == "__main__":
    unittest.main()
