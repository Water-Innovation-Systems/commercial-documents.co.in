import http.client
import http.cookiejar
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

import auth_server


class AuthenticationServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_directory = tempfile.TemporaryDirectory()
        cls.database_path = Path(cls.temp_directory.name) / "accounts.sqlite3"
        auth_server.initialize_database(cls.database_path)
        handler = partial(
            auth_server.PortalRequestHandler,
            database_path=cls.database_path,
        )
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.server_thread = threading.Thread(
            target=cls.server.serve_forever,
            daemon=True,
        )
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=5)
        cls.temp_directory.cleanup()

    def setUp(self):
        with auth_server.database_connection(self.database_path) as connection:
            connection.execute("DELETE FROM sessions")
            connection.execute("DELETE FROM accounts")
        with auth_server.PortalRequestHandler.auth_rate_lock:
            auth_server.PortalRequestHandler.auth_rate_limit.clear()

        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor(self.cookies),
        )

    def request(self, path, payload=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Origin": self.base_url}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            headers=headers,
        )
        try:
            response = self.opener.open(request, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        return response.status, response.headers, json.loads(response.read())

    @staticmethod
    def signup_payload(email="person@example.com"):
        return {
            "name": "Test Person",
            "company": "Example Works",
            "email": email,
            "password": "CorrectHorse9!",
            "acceptTerms": True,
        }

    def test_signup_saves_a_hash_and_starts_a_session(self):
        status, headers, response = self.request(
            "/api/auth/signup",
            self.signup_payload(),
        )

        self.assertEqual(status, 201)
        self.assertEqual(response, {"created": True, "authenticated": True})
        set_cookie = headers["Set-Cookie"]
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=Lax", set_cookie)
        self.assertNotIn("CorrectHorse9!", set_cookie)

        with auth_server.database_connection(self.database_path) as connection:
            account = connection.execute(
                "SELECT email, password_hash FROM accounts"
            ).fetchone()
            session = connection.execute(
                "SELECT token_hash FROM sessions"
            ).fetchone()

        self.assertEqual(account[0], "person@example.com")
        self.assertNotIn("CorrectHorse9!", account[1])
        self.assertTrue(auth_server.verify_password("CorrectHorse9!", account[1]))
        self.assertIsNotNone(session)

        status, _, session_response = self.request("/api/auth/session")
        self.assertEqual(status, 200)
        self.assertTrue(session_response["authenticated"])
        self.assertEqual(session_response["account"]["email"], "person@example.com")

    def test_login_redirects_authenticated_users_to_the_document_portal(self):
        self.request("/api/auth/signup", self.signup_payload())
        self.cookies.clear()

        status, headers, response = self.request(
            "/api/auth/login",
            {
                "email": "PERSON@example.com",
                "password": "CorrectHorse9!",
                "remember": False,
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(response, {"authenticated": True})
        self.assertIn("HttpOnly", headers["Set-Cookie"])

        request = urllib.request.Request(self.base_url + "/Mainpage.html")
        with self.opener.open(request, timeout=10) as dashboard:
            self.assertEqual(dashboard.status, 200)
            self.assertIn("no-store", dashboard.headers["Cache-Control"])
            self.assertIn("Your documents workspace", dashboard.read().decode("utf-8"))

    def test_login_rejects_an_incorrect_password(self):
        self.request("/api/auth/signup", self.signup_payload())
        self.cookies.clear()

        status, _, response = self.request(
            "/api/auth/login",
            {"email": "person@example.com", "password": "WrongPassword9!"},
        )

        self.assertEqual(status, 401)
        self.assertEqual(response, {"error": "invalid_credentials"})

    def test_duplicate_email_is_case_insensitive(self):
        self.request("/api/auth/signup", self.signup_payload())

        status, _, response = self.request(
            "/api/auth/signup",
            self.signup_payload("PERSON@example.com"),
        )

        self.assertEqual(status, 409)
        self.assertEqual(response, {"error": "account_exists"})

    def test_signup_requires_explicit_terms_acceptance(self):
        payload = self.signup_payload()
        payload["acceptTerms"] = False

        status, _, response = self.request("/api/auth/signup", payload)

        self.assertEqual(status, 400)
        self.assertEqual(response, {"error": "invalid_request"})
        with auth_server.database_connection(self.database_path) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM accounts").fetchone()[0],
                0,
            )

    def test_documents_redirect_when_there_is_no_authenticated_session(self):
        request = urllib.request.Request(
            self.base_url + "/Mainpage.html",
            headers={"Accept": "text/html"},
        )

        with self.opener.open(request, timeout=10) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(
                urllib.parse.urlsplit(response.geturl()).path,
                "/index.html",
            )
            self.assertEqual(
                urllib.parse.urlsplit(response.geturl()).query,
                "next=Mainpage.html",
            )

    def test_head_requests_cannot_bypass_document_session_checks(self):
        connection = http.client.HTTPConnection(
            "127.0.0.1",
            self.server.server_port,
            timeout=10,
        )
        try:
            connection.request("HEAD", "/Mainpage.html")
            response = connection.getresponse()
            self.assertEqual(response.status, 303)
            self.assertEqual(
                response.getheader("Location"),
                "/index.html?next=Mainpage.html",
            )
        finally:
            connection.close()


    def test_cross_origin_authentication_request_is_rejected(self):
        request = urllib.request.Request(
            self.base_url + "/api/auth/signup",
            data=json.dumps(self.signup_payload()).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Origin": "https://untrusted.example",
            },
        )
        try:
            response = self.opener.open(request, timeout=10)
        except urllib.error.HTTPError as error:
            response = error

        try:
            self.assertEqual(response.status, 403)
            self.assertEqual(json.loads(response.read()), {"error": "invalid_request"})
        finally:
            response.close()

    def test_password_reset_explains_that_email_delivery_is_not_configured(self):
        status, _, response = self.request(
            "/api/auth/password-reset",
            {"email": "person@example.com"},
        )

        self.assertEqual(status, 503)
        self.assertEqual(response, {"error": "password_reset_not_configured"})


if __name__ == "__main__":
    unittest.main()
