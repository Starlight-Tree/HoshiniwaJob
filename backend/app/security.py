"""園（garden.py）のログインの部品と、Authorization ヘッダーの読み取り。

園のトークンは推測できない乱数で、DB にはそのハッシュ（sha256）だけを置く。パスワードは argon2。
求職者のログインは Better Auth の JWT（jwt_auth.py・auth.py）で、別の仕組み。ここから使うのは、bearer と NOT_LOGGED_IN だけ。
"""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import HTTPException

SESSION_DAYS = 14

hasher = PasswordHasher()
# メールが無いときも同じだけ時間をかけ、応答の速さから登録の有無を読まれないようにする
DUMMY_HASH = hasher.hash("dummy-password-for-timing")

BAD_LOGIN = HTTPException(status_code=401, detail="メールアドレスまたはパスワードが違います")
NOT_LOGGED_IN = HTTPException(status_code=401, detail="ログインしてください")


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def bearer(authorization: str | None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise NOT_LOGGED_IN
    return token


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False
