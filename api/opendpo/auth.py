"""Authentication: verify Keycloak access tokens and resolve memberships.

Identity comes from Keycloak; roles come from OpenDPO's own membership
records, because roles live on tenant memberships, not on users (PLT-04).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings
from .db import global_tx

_bearer = HTTPBearer(auto_error=False)
_jwks: jwt.PyJWKClient | None = None


def jwks_client() -> jwt.PyJWKClient:
    global _jwks
    if _jwks is None:
        _jwks = jwt.PyJWKClient(settings.oidc_jwks_url, cache_keys=True, lifespan=300)
    return _jwks


@dataclass
class Principal:
    user_id: UUID
    username: str
    display_name: str
    memberships: list[dict] = field(default_factory=list)       # tenant_id, tenant_name, role
    workspace_roles: list[dict] = field(default_factory=list)   # workspace_id, role

    def tenant_roles(self, tenant_id: UUID) -> list[str]:
        return sorted({m["role"] for m in self.memberships if m["tenant_id"] == tenant_id})


def decode_token(token: str) -> dict:
    key = jwks_client().get_signing_key_from_jwt(token).key
    return jwt.decode(token, key, algorithms=["RS256"], audience=settings.oidc_audience,
                      issuer=settings.oidc_issuer, options={"require": ["exp", "iat", "sub"]})


def current_principal(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Principal:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sign in required",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = decode_token(creds.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {exc}",
                            headers={"WWW-Authenticate": "Bearer"}) from exc
    user_id = UUID(claims["sub"])
    with global_tx() as conn:
        user = conn.execute("SELECT * FROM app_user WHERE id = %s", (user_id,)).fetchone()
        if user is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "this account has no OpenDPO memberships")
        memberships = conn.execute("SELECT * FROM my_memberships(%s)", (user_id,)).fetchall()
        ws_roles = conn.execute(
            "SELECT workspace_id, role FROM workspace_membership WHERE user_id = %s", (user_id,)).fetchall()
    return Principal(user_id, user["username"], user["display_name"], memberships, ws_roles)
