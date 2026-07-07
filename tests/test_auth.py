from __future__ import annotations

import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from vendorverdict.api import app
from vendorverdict.auth import SESSION_COOKIE_NAME


class AuthenticationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_env = {key: os.environ.get(key) for key in AUTH_ENV_KEYS}
        os.environ["VENDORVERDICT_AUTH_ENABLED"] = "1"
        os.environ["VENDORVERDICT_AUTH_USERNAME"] = "admin"
        os.environ["VENDORVERDICT_AUTH_PASSWORD"] = "secret-password"
        os.environ["VENDORVERDICT_AUTH_SECRET"] = "test-auth-secret"
        os.environ["VENDORVERDICT_API_DB_PATH"] = os.path.join(self.tmp.name, "auth.sqlite3")
        os.environ["VENDORVERDICT_API_EXPORT_DIR"] = os.path.join(self.tmp.name, "reports")
        os.environ["VENDORVERDICT_API_LIVE_EVIDENCE"] = "0"
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.tmp.cleanup()
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_health_remains_public_when_auth_is_enabled(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_dashboard_redirects_to_login_without_session(self) -> None:
        response = self.client.get("/dashboard", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.headers["location"].startswith("/login"))

    def test_api_requires_authentication_without_basic_credentials(self) -> None:
        response = self.client.get("/reports")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Authentication required")

    def test_api_accepts_http_basic_credentials(self) -> None:
        response = self.client.get("/reports", auth=("admin", "secret-password"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_login_sets_session_cookie_and_logout_clears_it(self) -> None:
        login = self.client.post(
            "/login",
            data={"username": "admin", "password": "secret-password", "next": "/dashboard"},
            follow_redirects=False,
        )
        self.assertEqual(login.status_code, 303)
        self.assertEqual(login.headers["location"], "/dashboard")
        self.assertIn(SESSION_COOKIE_NAME, self.client.cookies)

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("VendorVerdict Dashboard", dashboard.text)
        self.assertIn("Logout", dashboard.text)

        logout = self.client.get("/logout", follow_redirects=False)
        self.assertEqual(logout.status_code, 303)
        self.assertEqual(logout.headers["location"], "/login")

    def test_login_rejects_invalid_password(self) -> None:
        response = self.client.post(
            "/login",
            data={"username": "admin", "password": "wrong", "next": "/dashboard"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Invalid username or password", response.text)


AUTH_ENV_KEYS = [
    "VENDORVERDICT_AUTH_ENABLED",
    "VENDORVERDICT_AUTH_USERNAME",
    "VENDORVERDICT_AUTH_PASSWORD",
    "VENDORVERDICT_AUTH_SECRET",
    "VENDORVERDICT_AUTH_SECURE_COOKIE",
    "VENDORVERDICT_AUTH_SESSION_SECONDS",
    "VENDORVERDICT_API_DB_PATH",
    "VENDORVERDICT_API_EXPORT_DIR",
    "VENDORVERDICT_API_LIVE_EVIDENCE",
]


if __name__ == "__main__":
    unittest.main()
