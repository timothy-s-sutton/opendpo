"""Test setup. Needs a PostgreSQL database migrated with the demo seed and an
OPA server loaded with ../policy. Tokens are signed with a local test key in
place of Keycloak's."""
import os
import time
import uuid

import jwt
import psycopg
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

ISSUER = "http://localhost:8080/realms/opendpo"
os.environ.setdefault("OPENDPO_OIDC_ISSUER", ISSUER)

from opendpo import auth  # noqa: E402
from opendpo.main import app  # noqa: E402

NS = uuid.UUID("5f2b7c1e-0d4a-4b8e-9a51-0b0e0d0f0001")
HARBOR = uuid.uuid5(NS, "tenant:harbor")


def user_id(username: str) -> uuid.UUID:
    return uuid.uuid5(NS, f"user:{username}")


_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _FakeJWKS:
    def get_signing_key_from_jwt(self, token):
        return type("K", (), {"key": _key.public_key()})()


@pytest.fixture(autouse=True)
def fake_keycloak(monkeypatch):
    monkeypatch.setattr(auth, "jwks_client", lambda: _FakeJWKS())


def token_for(username: str, **overrides) -> str:
    now = int(time.time())
    claims = {"sub": str(user_id(username)), "iss": ISSUER, "aud": "opendpo-api",
              "iat": now, "exp": now + 300, "preferred_username": username, **overrides}
    return jwt.encode(claims, _key, algorithm="RS256")


@pytest.fixture
def client():
    return TestClient(app)


def as_user(username: str) -> dict:
    return {"Authorization": f"Bearer {token_for(username)}"}


@pytest.fixture
def superuser():
    dsn = os.environ.get("OPENDPO_TEST_SUPERUSER_DSN", "postgresql://postgres@localhost:5433/opendpo")
    with psycopg.connect(dsn, autocommit=True) as conn:
        yield conn
