"""求職者の会員登録・ログイン・ログアウト。

ログインの印（セッション）は、推測できない乱数のトークンを発行し、DB にはそのハッシュだけを置く。
トークンを Cookie に入れるのは画面側（Next.js のサーバー）の仕事で、ブラウザーは API を直接呼ばない。
画面のサーバーは、`Authorization: Bearer <トークン>` を付けて API を呼ぶ。
エラーの本文は固定の文にする（例外の文字列は返さない）。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from psycopg import errors

from app.db import connection
from app.schemas import LoginRequest, RegisterRequest, Session, User
from app.security import BAD_LOGIN, DUMMY_HASH, NOT_LOGGED_IN, SESSION_DAYS, bearer, digest, hasher, new_token, verify_password

router = APIRouter(prefix="/api/auth")


def _issue_session(conn, user_id: int) -> str:
    token = new_token()
    conn.execute("DELETE FROM user_sessions WHERE expires_at < now()")  # 期限切れの掃除（呼ばれたときについでに）
    conn.execute(
        "INSERT INTO user_sessions (token_hash, user_id, expires_at) VALUES (%s, %s, now() + make_interval(days => %s))",
        (digest(token), user_id, SESSION_DAYS),
    )
    return token


def current_user(authorization: Annotated[str | None, Header()] = None) -> User:
    """ログイン中の利用者。トークンが無い・違う・期限切れなら 401。"""
    token = bearer(authorization)
    with connection() as conn:
        row = conn.execute(
            "SELECT u.id, u.email, u.last_name, u.first_name FROM user_sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = %s AND s.expires_at > now()",
            (digest(token),),
        ).fetchone()
    if row is None:
        raise NOT_LOGGED_IN
    return User(**row)


@router.post("/register", response_model=Session, status_code=201)
def register(body: RegisterRequest) -> Session:
    password_hash = hasher.hash(body.password)
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
        stored = row["password_hash"] if row else DUMMY_HASH
        verified = verify_password(stored, body.password) and row is not None
        if not verified:
            raise BAD_LOGIN
        if hasher.check_needs_rehash(stored):  # 設定を強めたとき、次のログインで新しいハッシュに更新する
            conn.execute("UPDATE users SET password_hash = %s WHERE id = %s", (hasher.hash(body.password), row["id"]))
        conn.execute("UPDATE users SET last_login_at = now() WHERE id = %s", (row["id"],))
        token = _issue_session(conn, row["id"])
    return Session(token=token, user=User(id=row["id"], email=row["email"], last_name=row["last_name"], first_name=row["first_name"]))


@router.get("/me", response_model=User)
def me(user: Annotated[User, Depends(current_user)]) -> User:
    return user


@router.post("/logout", status_code=204)
def logout(authorization: Annotated[str | None, Header()] = None) -> Response:
    """送られたトークンが、すでに無効でも 204 を返す（ログアウトは何度呼んでも同じ結果）。ヘッダーが無いときは 401。"""
    token = bearer(authorization)
    with connection() as conn:
        conn.execute("DELETE FROM user_sessions WHERE token_hash = %s", (digest(token),))
    return Response(status_code=204)
