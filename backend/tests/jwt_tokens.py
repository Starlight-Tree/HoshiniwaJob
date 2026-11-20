"""テスト用の JWT。EC P-256 の鍵を 1 つ作り、API が読む JWKS をその公開鍵に差し替える（Better Auth の代わり）。"""

import json
import time

import jwt
from cryptography.hazmat.primitives.asymmetric import ec

ISSUER = "http://localhost:3200"
JWKS_URL = "http://auth.test/api/auth/jwks"
AUDIENCE = "hoshiniwajob"
KID = "test-key-1"
DEFAULT_SUB = "ba_user_0000000001"

PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())  # JWKS に載せない鍵（偽造の想定）


def jwks_document(private_key=PRIVATE_KEY, kid: str = KID) -> dict:
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private_key.public_key()))
    jwk.update(kid=kid, alg="ES256", use="sig")
    return {"keys": [jwk]}


def claims(**overrides) -> dict:
    """検証に通る既定の claims（Better Auth の definePayload と同じ形）。None を渡した項目は外す。"""
    base = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": DEFAULT_SUB,
        "iat": int(time.time()),
        "exp": int(time.time()) + 900,
        "email": "new.user@example.com",
        "email_verified": True,
        "name": "苔野 ひかり",
        "picture": "https://lh3.googleusercontent.com/a/test",
    }
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


def make_token(*, key=PRIVATE_KEY, kid: str | None = KID, alg: str = "ES256", **overrides) -> str:
    headers = {"kid": kid} if kid else {}
    return jwt.encode(claims(**overrides), key, algorithm=alg, headers=headers)
