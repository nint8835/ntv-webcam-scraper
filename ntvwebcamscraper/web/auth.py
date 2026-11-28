import asyncio
import time
from typing import Annotated, Any

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from ntvwebcamscraper.config import config

# Only asymmetric algorithms; never trust a token to pick HS* or "none".
ALLOWED_ALGORITHMS = frozenset(
    {
        "RS256",
        "RS384",
        "RS512",
        "PS256",
        "PS384",
        "PS512",
        "ES256",
        "ES384",
        "ES512",
        "EdDSA",
    }
)
# Minimum time between forced JWKS refreshes triggered by an unknown key ID.
MIN_REFRESH_INTERVAL = 60.0


class Principal(BaseModel):
    issuer: str
    subject: str
    claims: dict[str, Any]


class _IssuerKeys:
    def __init__(self) -> None:
        self.keys: dict[str, dict[str, Any]] = {}
        self.fetched_at: float = 0.0
        self.lock = asyncio.Lock()


class OIDCVerifier:
    def __init__(
        self, issuers: dict[str, list[str]], audience: str, cache_ttl: float
    ) -> None:
        self.subjects = {
            issuer: frozenset(subjects) for issuer, subjects in issuers.items()
        }
        self.audience = audience
        self.cache_ttl = cache_ttl
        self._keys = {issuer: _IssuerKeys() for issuer in issuers}
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _fetch_keys(self, issuer: str) -> dict[str, dict[str, Any]]:
        discovery_url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
        discovery = (await self.client.get(discovery_url)).raise_for_status().json()
        if discovery.get("issuer") != issuer:
            raise ValueError(f"Discovery document issuer mismatch for {issuer}")
        jwks = (await self.client.get(discovery["jwks_uri"])).raise_for_status().json()

        return {
            jwk["kid"]: jwk
            for jwk in jwks.get("keys", [])
            if isinstance(jwk.get("kid"), str) and jwk.get("use", "sig") == "sig"
        }

    async def _get_key(self, issuer: str, kid: str) -> dict[str, Any] | None:
        cache = self._keys[issuer]
        now = time.monotonic()
        if kid in cache.keys and now - cache.fetched_at < self.cache_ttl:
            return cache.keys[kid]

        async with cache.lock:
            now = time.monotonic()
            stale = now - cache.fetched_at >= self.cache_ttl
            # Refresh on expiry, or on an unknown kid (key rotation) at most once per interval.
            if stale or (
                kid not in cache.keys and now - cache.fetched_at >= MIN_REFRESH_INTERVAL
            ):
                cache.keys = await self._fetch_keys(issuer)
                cache.fetched_at = now
            return cache.keys.get(kid)

    async def verify(self, token: str) -> Principal:
        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as e:
            raise _unauthorized("Malformed token") from e

        issuer = unverified.get("iss")
        # Check the issuer against the allowlist before making any network requests.
        if not isinstance(issuer, str) or issuer not in self.subjects:
            raise _unauthorized("Untrusted issuer")

        kid = header.get("kid")
        if not isinstance(kid, str):
            raise _unauthorized("Token is missing a key ID")

        algorithm = header.get("alg")
        if algorithm not in ALLOWED_ALGORITHMS:
            raise _unauthorized("Unsupported signing algorithm")

        try:
            jwk = await self._get_key(issuer, kid)
        except (httpx.HTTPError, ValueError, KeyError) as e:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Unable to fetch issuer signing keys",
            ) from e
        if jwk is None:
            raise _unauthorized("Unknown signing key")
        if jwk.get("alg", algorithm) != algorithm:
            raise _unauthorized("Signing algorithm does not match key")
        try:
            key = jwt.PyJWK(jwk, algorithm=algorithm)
        except jwt.PyJWKError as e:
            raise _unauthorized("Signing key is incompatible with algorithm") from e

        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=[algorithm],
                issuer=issuer,
                audience=self.audience,
                options={"require": ["iss", "sub", "aud", "exp", "iat"]},
                leeway=30,
            )
        except jwt.InvalidTokenError as e:
            raise _unauthorized("Invalid token") from e

        subject = claims["sub"]
        if subject not in self.subjects[issuer]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Subject is not permitted")

        return Principal(issuer=issuer, subject=subject, claims=claims)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"}
    )


verifier = OIDCVerifier(
    config.oidc_subjects,
    config.oidc_audience,
    config.oidc_jwks_cache_ttl.total_seconds(),
)

_bearer = HTTPBearer(auto_error=False)


async def require_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    """Require a valid OIDC token from a configured issuer / subject."""
    if credentials is None:
        raise _unauthorized("Missing bearer token")
    return await verifier.verify(credentials.credentials)


type Auth = Annotated[Principal, Depends(require_auth)]
