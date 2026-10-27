"""Host session tokens: mint, verify, reject (MP-06)."""

import base64
import json

import pytest

from molchat_agent.server.auth import (
    AuthError,
    Session,
    mint,
    parse_bearer,
    standalone_secret,
    verify,
)

SECRET = b"test-secret-32-bytes-long-value!!"
NOW = 1_800_000_000


def test_roundtrip_keeps_identity_scopes_and_expiry():
    token = mint(SECRET, "cuenta-1", {"read", "chat"}, 3600, now=NOW)
    session = verify(SECRET, token, now=NOW)
    assert isinstance(session, Session)
    assert session.sub == "cuenta-1"
    assert session.scopes == frozenset({"read", "chat"})
    assert session.exp == NOW + 3600
    assert session.allows("read", "chat")
    assert not session.allows("approve")


def test_tampered_payload_rejected():
    token = mint(SECRET, "cuenta-1", {"read"}, 60, now=NOW)
    head, payload, sig = token.split(".")
    other = base64.urlsafe_b64encode(json.dumps(
        {"sub": "otra", "scopes": ["read"], "exp": NOW + 60,
         "jti": "x", "aud": "molchat"}).encode()).decode()
    with pytest.raises(AuthError, match="firma"):
        verify(SECRET, f"{head}.{other}.{sig}", now=NOW)


def test_wrong_secret_rejected():
    token = mint(SECRET, "cuenta-1", {"read"}, 60, now=NOW)
    with pytest.raises(AuthError, match="firma"):
        verify(b"other-secret-32-bytes-long-value!", token, now=NOW)


def test_expired_rejected_at_boundary():
    token = mint(SECRET, "cuenta-1", {"read"}, 60, now=NOW)
    verify(SECRET, token, now=NOW + 59)
    with pytest.raises(AuthError, match="caducada"):
        verify(SECRET, token, now=NOW + 60)


@pytest.mark.parametrize("token", ["", "nope", "mh1.solo", "mh1.a.b.c",
                                   "otro.aGVsbG8=.c2ln", "mh1..c2ln",
                                   "mh1.aGVsbG8=."])
def test_malformed_rejected(token):
    with pytest.raises(AuthError):
        verify(SECRET, token, now=NOW)


def test_wrong_audience_rejected():
    import hashlib
    import hmac

    raw = base64.urlsafe_b64encode(json.dumps(
        {"sub": "cuenta-1", "scopes": ["read"], "exp": NOW + 60,
         "jti": "x", "aud": "otro"}).encode()).decode()
    body = f"mh1.{raw}"
    sig = base64.urlsafe_b64encode(
        hmac.new(SECRET, body.encode(), hashlib.sha256).digest()).decode()
    with pytest.raises(AuthError, match="audiencia"):
        verify(SECRET, f"{body}.{sig}", now=NOW)


@pytest.mark.parametrize("scopes", [{"root"}, {"read", "todo"}, set(), []])
def test_unknown_or_empty_scopes_never_mint(scopes):
    with pytest.raises(AuthError):
        mint(SECRET, "cuenta-1", scopes, 60, now=NOW)


@pytest.mark.parametrize("kwargs", [{"sub": ""}, {"sub": "  "}, {"ttl_s": 0},
                                    {"ttl_s": -5}])
def test_bad_inputs_never_mint(kwargs):
    args = {"sub": "cuenta-1", "ttl_s": 60}
    args.update(kwargs)
    with pytest.raises(AuthError):
        mint(SECRET, args["sub"], {"read"}, args["ttl_s"], now=NOW)
    with pytest.raises(AuthError):
        mint(b"", "cuenta-1", {"read"}, 60, now=NOW)


def test_standalone_secret_is_fresh_32_bytes():
    assert standalone_secret() != standalone_secret()
    assert len(standalone_secret()) == 32


@pytest.mark.parametrize("header,expected", [
    (None, None),
    ("", None),
    ("Basic abc", None),
    ("Bearer", None),
    ("Bearer test-token-1", "test-token-1"),
    ("bearer test-token-2", "test-token-2"),
])
def test_parse_bearer(header, expected):
    assert parse_bearer(header) == expected
