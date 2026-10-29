#!/usr/bin/env python3
"""Serve the document portal and its same-origin, SQLite-backed auth API."""

from __future__ import annotations

import base64
import functools
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from http import HTTPStatus
from http.cookies import CookieError, SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent
COOKIE_NAME = "wisi_session"
PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
SESSION_HOURS = 12
REMEMBERED_SESSION_DAYS = 30
SESSION_PATHS = {
    "/mainpage.html",
    "/po.html",
    "/quotation.html",
    "/tax-invoice.html",
}
EMAIL_PATTERN = re.compile(r"^[^@\s]{1,64}@[^@\s.]+(?:\.[^@\s.]+)+$")
API_ERRORS = {
    "invalid_request",
    "invalid_credentials",
    "account_exists",
    "too_many_attempts",
    "password_reset_not_configured",
    "not_found",
    "method_not_allowed",
    "unsupported_media_type",
    "payload_too_large",
    "account_service_error",
}
ATTEMPT_LIMIT = 12
ATTEMPT_WINDOW_SECONDS = 15 * 60
MAX_REQUEST_BYTES = 16 * 1024
logger = logging.getLogger("water-innovation-auth")


@contextmanager
def database_connection(database_path: Path):
    connection = sqlite3.connect(database_path, timeout=10)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            yield connection
    finally:
        connection.close()


def default_database_path() -> Path:
    configured = os.environ.get("WIS_AUTH_DB")
    if configured:
        return Path(configured).expanduser().resolve()

    if os.name == "nt":
        data_directory = Path(
            os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        )
    else:
        data_directory = Path(
            os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
        )

    return data_directory / "WaterInnovationSystems" / "accounts.sqlite3"


def initialize_database(database_path: Path) -> None:
    database_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != "nt":
        database_path.parent.chmod(0o700)
    with database_connection(database_path) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                company TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS sessions_expiry_idx
                ON sessions(expires_at);
            """
        )
    if os.name != "nt":
        database_path.chmod(0o600)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    encoded_salt = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
    encoded_digest = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return (
        f"{PASSWORD_SCHEME}${PASSWORD_ITERATIONS}"
        f"${encoded_salt}${encoded_digest}"
    )


DUMMY_PASSWORD_HASH = hash_password("not-a-real-account-password")


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, iterations_value, encoded_salt, encoded_digest = stored_hash.split("$")
        iterations = int(iterations_value)
        if (
            scheme != PASSWORD_SCHEME
            or iterations < 100_000
            or iterations > 2_000_000
        ):
            return False
        salt = base64.urlsafe_b64decode(encoded_salt + "===")
        expected_digest = base64.urlsafe_b64decode(encoded_digest + "===")
    except (ValueError, TypeError):
        return False

    actual_digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(actual_digest, expected_digest)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


class PortalRequestHandler(SimpleHTTPRequestHandler):
    database_path: Path
    auth_rate_limit: dict[str, deque[float]] = defaultdict(deque)
    auth_rate_lock = threading.Lock()

    def __init__(self, *args: object, database_path: Path, **kwargs: object) -> None:
        self.database_path = database_path
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format_string: str, *args: object) -> None:
        logger.info("%s - %s", self.address_string(), format_string % args)

    def end_headers(self) -> None:
        if urlsplit(self.path).path.lower() in SESSION_PATHS:
            self.send_header("Cache-Control", "no-store, private")
        super().end_headers()

    def respond_json(
        self,
        status: HTTPStatus,
        payload: dict[str, object],
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        if headers:
            for name, value in headers.items():
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def respond_api_error(
        self, status: HTTPStatus, error: str
    ) -> None:
        if error not in API_ERRORS:
            error = "account_service_error"
        self.respond_json(status, {"error": error})

    def api_route(self) -> str | None:
        path = urlsplit(self.path).path
        if path.startswith("/api/"):
            return path
        return None

    def parse_json_body(self) -> dict[str, object] | None:
        content_type = self.headers.get("Content-Type", "")
        if content_type.partition(";")[0].strip().lower() != "application/json":
            self.respond_api_error(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "unsupported_media_type"
            )
            return None

        try:
            content_length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self.respond_api_error(HTTPStatus.BAD_REQUEST, "invalid_request")
            return None

        if content_length < 0:
            self.respond_api_error(HTTPStatus.BAD_REQUEST, "invalid_request")
            return None
        if content_length > MAX_REQUEST_BYTES:
            self.respond_api_error(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "payload_too_large"
            )
            return None

        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.respond_api_error(HTTPStatus.BAD_REQUEST, "invalid_request")
            return None

        if not isinstance(payload, dict):
            self.respond_api_error(HTTPStatus.BAD_REQUEST, "invalid_request")
            return None
        return payload

    def check_same_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True

        parsed_origin = urlsplit(origin)
        host = self.headers.get("Host", "").lower()
        if parsed_origin.scheme not in {"http", "https"} or not parsed_origin.netloc:
            return False
        return parsed_origin.netloc.lower() == host

    def cookie_value(self, cookie_name: str) -> str | None:
        cookie_header = self.headers.get("Cookie")
        if not cookie_header:
            return None

        cookies = SimpleCookie()
        try:
            cookies.load(cookie_header)
        except CookieError:
            return None
        morsel = cookies.get(cookie_name)
        return morsel.value if morsel is not None else None

    def current_account(self) -> sqlite3.Row | None:
        token = self.cookie_value(COOKIE_NAME)
        if not token or len(token) > 256:
            return None

        with database_connection(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            return connection.execute(
                """
                SELECT accounts.id, accounts.name, accounts.company, accounts.email
                FROM sessions
                JOIN accounts ON accounts.id = sessions.account_id
                WHERE sessions.token_hash = ? AND sessions.expires_at > ?
                """,
                (hash_session_token(token), int(time.time())),
            ).fetchone()

    def issue_session(self, account_id: int, remember: bool) -> str:
        lifetime = (
            REMEMBERED_SESSION_DAYS * 24 * 60 * 60
            if remember
            else SESSION_HOURS * 60 * 60
        )
        token = secrets.token_urlsafe(32)
        current_time = int(time.time())
        with database_connection(self.database_path) as connection:
            connection.execute(
                "INSERT INTO sessions (token_hash, account_id, expires_at, created_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    hash_session_token(token),
                    account_id,
                    current_time + lifetime,
                    current_time,
                ),
            )

        cookie = (
            f"{COOKIE_NAME}={token}; Path=/; HttpOnly; "
            "SameSite=Lax; Priority=High"
        )
        if os.environ.get("WIS_COOKIE_SECURE") == "1":
            cookie += "; Secure"
        if remember:
            cookie += f"; Max-Age={lifetime}"
        return cookie

    def enforce_rate_limit(self) -> bool:
        now = time.monotonic()
        address = self.client_address[0]
        with self.auth_rate_lock:
            attempts = self.auth_rate_limit[address]
            while attempts and attempts[0] <= now - ATTEMPT_WINDOW_SECONDS:
                attempts.popleft()
            if len(attempts) >= ATTEMPT_LIMIT:
                return False
            attempts.append(now)
        return True

    def clear_rate_limit(self) -> None:
        with self.auth_rate_lock:
            self.auth_rate_limit.pop(self.client_address[0], None)

    def do_GET(self) -> None:
        route = self.api_route()
        if route == "/api/auth/session":
            account = self.current_account()
            if account is None:
                self.respond_json(HTTPStatus.OK, {"authenticated": False})
            else:
                self.respond_json(
                    HTTPStatus.OK,
                    {
                        "authenticated": True,
                        "account": {
                            "name": account["name"],
                            "company": account["company"],
                            "email": account["email"],
                        },
                    },
                )
            return
        if route is not None:
            self.respond_api_error(HTTPStatus.NOT_FOUND, "not_found")
            return

        page_path = urlsplit(self.path).path
        if page_path.lower() in SESSION_PATHS and self.current_account() is None:
            next_page = urlsplit(self.path).path.lstrip("/")
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header(
                "Location",
                "/index.html?next=" + next_page,
            )
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return

        super().do_GET()

    def do_HEAD(self) -> None:
        page_path = urlsplit(self.path).path
        if page_path.lower() in SESSION_PATHS and self.current_account() is None:
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header(
                "Location",
                "/index.html?next=" + page_path.lstrip("/"),
            )
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return

        super().do_HEAD()

    def do_POST(self) -> None:
        route = self.api_route()
        if route is None:
            self.respond_api_error(HTTPStatus.NOT_FOUND, "not_found")
            return
        if route not in {
            "/api/auth/login",
            "/api/auth/signup",
            "/api/auth/password-reset",
            "/api/auth/logout",
        }:
            self.respond_api_error(HTTPStatus.NOT_FOUND, "not_found")
            return
        if not self.check_same_origin():
            self.respond_api_error(HTTPStatus.FORBIDDEN, "invalid_request")
            return

        payload = self.parse_json_body()
        if payload is None:
            return

        try:
            if route == "/api/auth/signup":
                self.handle_signup(payload)
            elif route == "/api/auth/login":
                self.handle_login(payload)
            elif route == "/api/auth/password-reset":
                self.respond_api_error(
                    HTTPStatus.SERVICE_UNAVAILABLE, "password_reset_not_configured"
                )
            else:
                self.handle_logout()
        except sqlite3.Error:
            logger.exception("An authentication database operation failed.")
            if not self.wfile.closed:
                self.respond_api_error(
                    HTTPStatus.INTERNAL_SERVER_ERROR, "account_service_error"
                )

    def handle_signup(self, payload: dict[str, object]) -> None:
        if not self.enforce_rate_limit():
            self.respond_api_error(HTTPStatus.TOO_MANY_REQUESTS, "too_many_attempts")
            return

        name = payload.get("name")
        company = payload.get("company")
        email_value = payload.get("email")
        password = payload.get("password")
        accepted_terms = payload.get("acceptTerms")

        if not all(
            isinstance(value, str) for value in (name, company, email_value, password)
        ) or accepted_terms is not True:
            self.respond_api_error(HTTPStatus.BAD_REQUEST, "invalid_request")
            return

        normalized_email = email_value.strip().lower()
        normalized_name = name.strip()
        normalized_company = company.strip()
        if (
            not normalized_name
            or len(normalized_name) > 120
            or not normalized_company
            or len(normalized_company) > 160
            or len(normalized_email) > 254
            or not EMAIL_PATTERN.fullmatch(normalized_email)
            or len(password) < PASSWORD_MIN_LENGTH
            or len(password) > PASSWORD_MAX_LENGTH
            or len(password.encode("utf-8")) > 1024
        ):
            self.respond_api_error(HTTPStatus.BAD_REQUEST, "invalid_request")
            return

        password_hash = hash_password(password)
        current_time = int(time.time())
        try:
            with database_connection(self.database_path) as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO accounts (name, company, email, password_hash, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        normalized_name,
                        normalized_company,
                        normalized_email,
                        password_hash,
                        current_time,
                    ),
                )
                account_id = cursor.lastrowid
                if account_id is None:
                    raise sqlite3.DatabaseError("Account creation returned no ID.")
        except sqlite3.IntegrityError:
            self.respond_api_error(HTTPStatus.CONFLICT, "account_exists")
            return

        session_cookie = self.issue_session(account_id, remember=False)
        self.clear_rate_limit()
        self.respond_json(
            HTTPStatus.CREATED,
            {"created": True, "authenticated": True},
            headers={"Set-Cookie": session_cookie},
        )

    def handle_login(self, payload: dict[str, object]) -> None:
        if not self.enforce_rate_limit():
            self.respond_api_error(HTTPStatus.TOO_MANY_REQUESTS, "too_many_attempts")
            return

        email_value = payload.get("email")
        password = payload.get("password")
        remember = payload.get("remember", False)
        if (
            not isinstance(email_value, str)
            or not isinstance(password, str)
            or not isinstance(remember, bool)
            or not EMAIL_PATTERN.fullmatch(email_value.strip().lower())
            or len(password) > PASSWORD_MAX_LENGTH
        ):
            self.respond_api_error(HTTPStatus.BAD_REQUEST, "invalid_request")
            return

        with database_connection(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            account = connection.execute(
                """
                SELECT id, password_hash FROM accounts
                WHERE email = ? COLLATE NOCASE
                """,
                (email_value.strip().lower(),),
            ).fetchone()

        stored_hash = (
            account["password_hash"] if account is not None else DUMMY_PASSWORD_HASH
        )
        password_matches = verify_password(password, stored_hash)
        valid_password = account is not None and password_matches
        if not valid_password:
            self.respond_api_error(HTTPStatus.UNAUTHORIZED, "invalid_credentials")
            return

        session_cookie = self.issue_session(account["id"], remember)
        self.clear_rate_limit()
        self.respond_json(
            HTTPStatus.OK,
            {"authenticated": True},
            headers={"Set-Cookie": session_cookie},
        )

    def handle_logout(self) -> None:
        token = self.cookie_value(COOKIE_NAME)
        if token:
            with database_connection(self.database_path) as connection:
                connection.execute(
                    "DELETE FROM sessions WHERE token_hash = ?",
                    (hash_session_token(token),),
                )

        expired_cookie = (
            f"{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Lax; "
            "Max-Age=0; Priority=High"
        )
        if os.environ.get("WIS_COOKIE_SECURE") == "1":
            expired_cookie += "; Secure"
        self.respond_json(
            HTTPStatus.OK,
            {"authenticated": False},
            headers={"Set-Cookie": expired_cookie},
        )

    def do_PUT(self) -> None:
        self.respond_api_error(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed")

    def do_PATCH(self) -> None:
        self.respond_api_error(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed")

    def do_DELETE(self) -> None:
        self.respond_api_error(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    database_path = default_database_path()
    try:
        initialize_database(database_path)
    except (OSError, sqlite3.Error):
        logger.exception("Could not initialize the authentication database.")
        raise SystemExit(1) from None

    host = os.environ.get("WIS_HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("WIS_PORT", "8000"))
        if not 0 <= port <= 65535:
            raise ValueError("Port is outside the valid range.")
    except ValueError as error:
        raise SystemExit(f"Invalid WIS_PORT: {error}") from None

    handler = functools.partial(
        PortalRequestHandler, database_path=database_path
    )
    try:
        server = ThreadingHTTPServer((host, port), handler)
    except OSError:
        logger.exception("Could not start the portal server at %s:%s.", host, port)
        raise SystemExit(1) from None

    logger.info("Portal running at http://%s:%s", host, server.server_port)
    logger.info("Account database: %s", database_path)
    if host not in {"127.0.0.1", "localhost", "::1"}:
        logger.warning(
            "Use HTTPS and set WIS_COOKIE_SECURE=1 before exposing this server to a network."
        )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down the portal server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
