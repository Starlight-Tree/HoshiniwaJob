"""利用者（auth.py）と園（garden.py）のログインで共通の部品。

トークンは推測できない乱数で、DB にはそのハッシュ（sha256）だけを置く。パスワードは argon2。
利用者と園は、テーブルもセッションも別。ここに置くのは、同じ方式で動かす部分だけ。
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
