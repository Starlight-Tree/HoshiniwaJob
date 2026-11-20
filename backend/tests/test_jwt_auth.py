"""JWT の検証（app/jwt_auth.py）。DB は使わない。Better Auth の代わりに、テスト用の鍵と JWKS を使う（conftest の auth_env）。"""

import base64
import hashlib
import hmac
import json
import time

import jwt
import pytest

from app import jwt_auth
from tests import jwt_tokens
from tests.jwt_tokens import make_token


def verify(token: str) -> jwt_auth.Identity:
    return jwt_auth.verify_token(token)


def test_valid_token_gives_identity(auth_env):
    ident = verify(make_token(email="Hikari@Example.com", last_name=" 苔野 "))
    assert ident == jwt_auth.Identity(
        sub="ba_user_0000000001",
        email="hikari@example.com",  # 小文字にそろえる
        last_name="苔野",
        first_name="ひかり",
        picture="https://lh3.googleusercontent.com/a/test",
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "http://evil.example"},
        {"aud": "docunavi"},
        {"exp": int(time.time()) - 3600},
        {"exp": None},
        {"sub": None},
        {"sub": "short"},
        {"sub": "has space in it!"},
        {"email": None},
        {"email": "not-an-email"},
        {"email_verified": False},
        {"email_verified": "true"},  # 文字列の "true" は確認済みとは見なさない
    ],
)
def test_bad_claims_are_rejected(auth_env, overrides):
    with pytest.raises(jwt_auth.InvalidToken):
        verify(make_token(**overrides))


def test_picture_other_than_https_is_dropped(auth_env):
    assert verify(make_token(picture="http://example.com/a.png")).picture is None
    assert verify(make_token(picture="javascript:alert(1)")).picture is None
    assert verify(make_token(picture=None)).picture is None


def test_signature_from_another_key_is_rejected(auth_env):
    with pytest.raises(jwt_auth.InvalidToken):
        verify(make_token(key=jwt_tokens.OTHER_PRIVATE_KEY))  # kid は同じでも、署名が JWKS の鍵と違う


def test_alg_none_is_rejected(auth_env):
    def b64(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    token = f"{b64({'alg': 'none', 'kid': jwt_tokens.KID, 'typ': 'JWT'})}.{b64(jwt_tokens.claims())}."
    with pytest.raises(jwt_auth.InvalidToken, match="algorithm"):
        verify(token)


def test_hs256_signed_with_the_public_key_is_rejected(auth_env):
    # 公開鍵（JWKS で誰でも読める）を共有秘密にして HS256 で署名する攻撃。PyJWT は、この署名を作ること自体を拒むので、手で作る
    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    secret = json.dumps(jwt_tokens.jwks_document()["keys"][0]).encode()
    signing_input = f"{b64(json.dumps({'alg': 'HS256', 'kid': jwt_tokens.KID, 'typ': 'JWT'}).encode())}.{b64(json.dumps(jwt_tokens.claims()).encode())}"
    token = f"{signing_input}.{b64(hmac.new(secret, signing_input.encode(), hashlib.sha256).digest())}"
    with pytest.raises(jwt_auth.InvalidToken, match="algorithm"):
        verify(token)


@pytest.mark.parametrize("token", ["", "abc", "a.b.c", "Bearer x"])
def test_malformed_tokens_are_rejected(auth_env, token):
    with pytest.raises(jwt_auth.InvalidToken):
        verify(token)


def test_token_without_kid_is_rejected(auth_env):
    with pytest.raises(jwt_auth.InvalidToken, match="kid"):
        verify(make_token(kid=None))


def test_unknown_kid_is_rejected_and_jwks_is_not_hammered(auth_env, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(jwt_auth, "_now", lambda: clock[0])
    with pytest.raises(jwt_auth.InvalidToken, match="unknown_key"):
        verify(make_token(kid="nope-1"))
    assert len(auth_env) == 1
    # でたらめな kid を続けても、最小間隔（60 秒）のあいだは、JWKS を取り直さない
    for i in range(5):
        clock[0] += 5
        with pytest.raises(jwt_auth.InvalidToken):
            verify(make_token(kid=f"nope-{i}"))
    assert len(auth_env) == 1
    # 間隔が過ぎれば、新しい鍵（ローテーション）を取りに行ける
    clock[0] += 120
    with pytest.raises(jwt_auth.InvalidToken):
        verify(make_token(kid="nope-after"))
    assert len(auth_env) == 2


def test_keys_are_cached_and_refreshed_after_ttl(auth_env, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(jwt_auth, "_now", lambda: clock[0])
    verify(make_token())
    verify(make_token())
    assert len(auth_env) == 1
    clock[0] += jwt_auth._KEYS_TTL_SECONDS + 1
    verify(make_token())
    assert len(auth_env) == 2


def test_jwks_failure_keeps_using_previous_keys(auth_env, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(jwt_auth, "_now", lambda: clock[0])
    verify(make_token())  # 鍵を取る

    def down(url: str):
        raise OSError("connection refused: http://secret-host/")

    monkeypatch.setattr(jwt_auth, "fetch_jwks_document", down)
    clock[0] += jwt_auth._KEYS_TTL_SECONDS + 1
    assert verify(make_token()).sub  # 前の鍵で続ける


def test_no_keys_and_jwks_down_means_unavailable(auth_env, monkeypatch):
    def down(url: str):
        raise OSError("connection refused")

    monkeypatch.setattr(jwt_auth, "fetch_jwks_document", down)
    with pytest.raises(jwt_auth.AuthUnavailable):
        verify(make_token())


def test_not_configured_when_env_is_missing(monkeypatch):
    for name in ("AUTH_BASE_URL", "AUTH_JWKS_URL"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(jwt_auth.AuthNotConfigured):
        verify(make_token())


def test_parse_keys_keeps_only_usable_keys():
    good = jwt_tokens.jwks_document()["keys"][0]
    document = {
        "keys": [
            good,
            {**good, "kid": ""},  # kid が空
            {k: v for k, v in good.items() if k != "kid"},  # kid なし
            {"kty": "oct", "kid": "sym", "k": "c2VjcmV0"},  # 共有秘密の鍵は使わない
            "not-a-dict",
        ]
    }
    assert list(jwt_auth._parse_keys(document)) == [jwt_tokens.KID]
    assert jwt_auth._parse_keys({"keys": "x"}) == {}
    assert jwt_auth._parse_keys({}) == {}
