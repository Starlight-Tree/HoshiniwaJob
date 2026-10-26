"""求職者の会員登録・ログイン・ログアウト。

ログインの印（セッション）は、推測できない乱数のトークンを発行し、DB にはそのハッシュだけを置く。
トークンを Cookie に入れるのは画面側（Next.js のサーバー）の仕事で、ブラウザーは API を直接呼ばない。
画面のサーバーは、`Authorization: Bearer <トークン>` を付けて API を呼ぶ。
エラーの本文は固定の文にする（例外の文字列は返さない）。
"""

import hashlib
import secrets
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from psycopg import errors

from app.db import connection
from app.schemas import LoginRequest, RegisterRequest, Session, User

router = APIRouter(prefix="/api/auth")

SESSION_DAYS = 14

_hasher = PasswordHasher()
# メールが無いときも同じだけ時間をかけ、応答の速さから登録の有無を読まれないようにする
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")

_BAD_LOGIN = HTTPException(status_code=401, detail="メールアドレスまたはパスワードが違います")
_NOT_LOGGED_IN = HTTPException(status_code=401, detail="ログインしてください")


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _issue_session(conn, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute("DELETE FROM user_sessions WHERE expires_at < now()")  # 期限切れの掃除（呼ばれたときについでに）
    conn.execute(
        "INSERT INTO user_sessions (token_hash, user_id, expires_at) VALUES (%s, %s, now() + make_interval(days => %s))",
        (_digest(token), user_id, SESSION_DAYS),
    )
    return token


def _bearer(authorization: str | None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _NOT_LOGGED_IN
    return token


def current_user(authorization: Annotated[str | None, Header()] = None) -> User:
    """ログイン中の利用者。トークンが無い・違う・期限切れなら 401。"""
    token = _bearer(authorization)
    with connection() as conn:
        row = conn.execute(
            "SELECT u.id, u.email, u.last_name, u.first_name FROM user_sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = %s AND s.expires_at > now()",
            (_digest(token),),
        ).fetchone()
    if row is None:
        raise _NOT_LOGGED_IN
    return User(**row)


@router.post("/register", response_model=Session, status_code=201)
def register(body: RegisterRequest) -> Session:
    password_hash = _hasher.hash(body.password)
    with connection() as conn:
        try:
            row = conn.execute(
                "INSERT INTO users (last_name, first_name, email, password_hash, last_login_at) "
                "VALUES (%s, %s, %s, %s, now()) RETURNING id, email, last_name, first_name",
                (body.last_name, body.first_name, body.email, password_hash),
            ).fetchone()
        except errors.UniqueViolation:
            raise HTTPException(status_code=409, detail="このメールアドレスは登録できません") from None
        token = _issue_session(conn, row["id"])
    return Session(token=token, user=User(**row))


@router.post("/login", response_model=Session)
def login(body: LoginRequest) -> Session:
    with connection() as conn:
        row = conn.execute(
            "SELECT id, email, last_name, first_name, password_hash FROM users WHERE lower(email) = %s", (body.email,)
        ).fetchone()
        stored = row["password_hash"] if row else _DUMMY_HASH
        try:
            _hasher.verify(stored, body.password)
            verified = row is not None
        except (VerificationError, InvalidHashError):
            verified = False
        if not verified:
            raise _BAD_LOGIN
        if _hasher.check_needs_rehash(stored):  # 設定を強めたとき、次のログインで新しいハッシュに更新する
            conn.execute("UPDATE users SET password_hash = %s WHERE id = %s", (_hasher.hash(body.password), row["id"]))
        conn.execute("UPDATE users SET last_login_at = now() WHERE id = %s", (row["id"],))
        token = _issue_session(conn, row["id"])
    return Session(token=token, user=User(id=row["id"], email=row["email"], last_name=row["last_name"], first_name=row["first_name"]))


@router.get("/me", response_model=User)
def me(user: Annotated[User, Depends(current_user)]) -> User:
    return user


@router.post("/logout", status_code=204)
def logout(authorization: Annotated[str | None, Header()] = None) -> Response:
    """送られたトークンが、すでに無効でも 204 を返す（ログアウトは何度呼んでも同じ結果）。ヘッダーが無いときは 401。"""
    token = _bearer(authorization)
    with connection() as conn:
        conn.execute("DELETE FROM user_sessions WHERE token_hash = %s", (_digest(token),))
    return Response(status_code=204)
