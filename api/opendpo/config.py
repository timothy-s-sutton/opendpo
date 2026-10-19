"""Settings, read from the environment (see .env.example at the repo root)."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_dsn: str = os.environ.get("OPENDPO_APP_DSN", "postgresql://opendpo_app@localhost/opendpo")
    owner_dsn: str = os.environ.get("OPENDPO_OWNER_DSN", "postgresql://opendpo_owner@localhost/opendpo")
    oidc_issuer: str = os.environ.get("OPENDPO_OIDC_ISSUER", "http://localhost:8080/realms/opendpo")
    # The API may reach Keycloak on an internal address that differs from the
    # issuer the browser sees; tokens are still checked against oidc_issuer.
    oidc_jwks_url: str = os.environ.get(
        "OPENDPO_OIDC_JWKS_URL", "http://localhost:8080/realms/opendpo/protocol/openid-connect/certs")
    oidc_audience: str = os.environ.get("OPENDPO_OIDC_AUDIENCE", "opendpo-api")
    opa_url: str = os.environ.get("OPENDPO_OPA_URL", "http://localhost:8181")
    seed_demo: bool = os.environ.get("OPENDPO_SEED_DEMO", "false").lower() == "true"
    cors_origins: tuple[str, ...] = tuple(
        o for o in os.environ.get("OPENDPO_CORS_ORIGINS", "http://localhost:5173").split(",") if o)


settings = Settings()
