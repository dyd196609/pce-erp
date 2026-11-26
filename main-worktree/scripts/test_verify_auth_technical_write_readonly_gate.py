from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("verify_auth_technical_write_readonly_gate.py")
SPEC = importlib.util.spec_from_file_location("auth_gate", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class AuthenticationTechnicalWriteGateTests(unittest.TestCase):
    def test_exact_login_whitelist_is_approved(self):
        result = MODULE.classify_delta_map(
            {
                "user_system": [
                    {"change": "UPDATED", "rowId": 31, "fields": ["last_login"]}
                ],
                "django_session": [
                    {"change": "ADDED"},
                    {"change": "DELETED"},
                ],
            },
            31,
        )
        self.assertEqual(result["status"], "APPROVED")
        self.assertEqual(result["rejected"], [])

    def test_non_whitelist_business_table_is_rejected(self):
        result = MODULE.classify_delta_map(
            {"sales_order": [{"change": "UPDATED", "rowId": 3, "fields": ["status"]}]},
            31,
        )
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["rejected"][0]["reason"], "NON_WHITELIST_TABLE")

    def test_non_whitelist_user_field_is_rejected(self):
        result = MODULE.classify_delta_map(
            {"user_system": [{"change": "UPDATED", "rowId": 31, "fields": ["password"]}]},
            31,
        )
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(
            result["rejected"][0]["reason"],
            "USER_CHANGE_OUTSIDE_LAST_LOGIN_WHITELIST",
        )

    def test_post_login_sha_requires_all_three_values_to_match(self):
        self.assertTrue(MODULE.post_login_sha_stable("ABC", "abc", "ABC"))
        self.assertFalse(MODULE.post_login_sha_stable("ABC", "ABC", "DEF"))


if __name__ == "__main__":
    unittest.main()
