"""Admin password and session helpers."""

from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import ipaddress
import hmac
import json
import secrets
import time


def _urlsafe_b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _urlsafe_b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def hash_password(password: str, *, iterations: int = 600_000) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return (
        f"pbkdf2_sha256${iterations}$"
        f"{_urlsafe_b64encode(salt)}$"
        f"{_urlsafe_b64encode(digest)}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, raw_iterations, raw_salt, raw_digest = stored_hash.split("$", 3)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    try:
        iterations = int(raw_iterations)
        salt = _urlsafe_b64decode(raw_salt)
        expected = _urlsafe_b64decode(raw_digest)
    except Exception:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


@dataclass(frozen=True)
class SessionClaims:
    issued_at: int
    expires_at: int


class AdminSessionManager:
    """Stateless HMAC-signed admin session tokens."""

    def __init__(self, *, secret: str, ttl_seconds: int, cookie_name: str = "rrls_admin") -> None:
        self._secret = secret.encode("utf-8")
        self.ttl_seconds = ttl_seconds
        self.cookie_name = cookie_name

    def issue(self) -> str:
        now = int(time.time())
        payload = {
            "iat": now,
            "exp": now + self.ttl_seconds,
            "nonce": secrets.token_urlsafe(16),
        }
        raw_payload = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        signature = hmac.new(self._secret, raw_payload, hashlib.sha256).digest()
        return f"{_urlsafe_b64encode(raw_payload)}.{_urlsafe_b64encode(signature)}"

    def verify(self, token: str | None) -> SessionClaims | None:
        if not token or "." not in token:
            return None
        raw_payload, raw_sig = token.split(".", 1)
        try:
            payload_bytes = _urlsafe_b64decode(raw_payload)
            signature = _urlsafe_b64decode(raw_sig)
        except Exception:
            return None
        expected = hmac.new(self._secret, payload_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            return None
        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except Exception:
            return None
        issued_at = int(payload.get("iat"))
        expires_at = int(payload.get("exp"))
        now = int(time.time())
        if expires_at <= now or issued_at > now:
            return None
        return SessionClaims(issued_at=issued_at, expires_at=expires_at)


TRUSTED_NETWORKS_ENV = "ROBOROCK_SERVER_ADMIN_TRUSTED_NETWORKS"

def parse_trusted_networks(raw: str) -> tuple[list[ipaddress.IPv4Network | ipaddress.IPv6Network], list[str]]:
    """Comma or space separated CIDR ranges (a bare address means one host). Returns (networks, rejected entries)."""
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    rejected: list[str] = []
    for entry in raw.replace(",", " ").split():
        try:
            network = ipaddress.ip_network(entry, strict=False)
        except ValueError:
            rejected.append(entry)
            continue
        if network.prefixlen == 0:
            # 0.0.0.0/0 or ::/0 would trust the whole Internet.
            rejected.append(entry)
            continue
        networks.append(network)
    return networks, rejected


def address_in_networks(
    address: str | None, networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network]
) -> bool:
    if not address or not networks:
        return False
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(ip in network for network in networks if network.version == ip.version)
