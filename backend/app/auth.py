"""求職者の会員登録・ログイン・ログアウト。

ログインの印（セッション）は、推測できない乱数のトークンを発行し、DB にはそのハッシュだけを置く。
トークンを Cookie に入れるのは画面側（Next.js のサーバー）の仕事で、ブラウザーは API を直接呼ばない。
画面のサーバーは、`Authorization: Bearer <トークン>` を付けて API を呼ぶ。
エラーの本文は固定の文にする（例外の文字列は返さない）。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from psycopg import errors

from app import google_login, settings
from app.db import connection
from app.schemas import GoogleLoginRequest, LoginRequest, RegisterRequest, Session, UpdateNameRequest, User
from app.security import BAD_LOGIN, DUMMY_HASH, NOT_LOGGED_IN, SESSION_DAYS, bearer, digest, hasher, new_token, verify_password

router = APIRouter(prefix="/api/auth")

# パスワードを持たない利用者（Google だけでログインする人）の password_hash。argon2 として読めない印なので、検証は必ず失敗する（パスワードでは入れない）。
NO_PASSWORD = "!"
USER_COLUMNS = "id, email, last_name, first_name, avatar_url"


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
            "SELECT u.id, u.email, u.last_name, u.first_name, u.avatar_url FROM user_sessions s JOIN users u ON u.id = s.user_id "
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
            f"SELECT {USER_COLUMNS}, password_hash FROM users WHERE lower(email) = %s", (body.email,)
        ).fetchone()
        stored = row["password_hash"] if row else DUMMY_HASH
        verified = verify_password(stored, body.password) and row is not None
        if not verified:
            raise BAD_LOGIN
        if hasher.check_needs_rehash(stored):  # 設定を強めたとき、次のログインで新しいハッシュに更新する
            conn.execute("UPDATE users SET password_hash = %s WHERE id = %s", (hasher.hash(body.password), row["id"]))
        conn.execute("UPDATE users SET last_login_at = now() WHERE id = %s", (row["id"],))
        token = _issue_session(conn, row["id"])
    return Session(token=token, user=User(**{k: row[k] for k in User.model_fields}))


@router.get("/me", response_model=User)
def me(user: Annotated[User, Depends(current_user)]) -> User:
    return user


@router.patch("/me", response_model=User)
def update_name(body: UpdateNameRequest, user: Annotated[User, Depends(current_user)]) -> User:
    """お名前（姓・名）の変更。変えられるのはログイン中の本人のものだけ（id は、トークンから決まる）。"""
    with connection() as conn:
        row = conn.execute(
            f"UPDATE users SET last_name = %s, first_name = %s WHERE id = %s RETURNING {USER_COLUMNS}",
            (body.last_name, body.first_name, user.id),
        ).fetchone()
    return User(**row)


GOOGLE_FAILED = "Google でのログインに失敗しました。もう一度お試しください"


def _google_user(conn, profile: google_login.GoogleProfile) -> dict:
    """Google の利用者を、DB の利用者に結ぶ。Google の ID で見つかればその人。なければ、確認済みのメールが同じ既存の人に紐づける。それも無ければ作る。"""
    row = conn.execute(f"SELECT {USER_COLUMNS}, google_sub FROM users WHERE google_sub = %s", (profile.sub,)).fetchone()
    if row is None:
        row = conn.execute(f"SELECT {USER_COLUMNS}, google_sub FROM users WHERE lower(email) = %s", (profile.email,)).fetchone()
        if row is not None and row["google_sub"] not in (None, profile.sub):
            # 同じメールの人が、すでに別の Google アカウントと結ばれている。乗っ取りを防ぐため、結び直さない
            raise HTTPException(status_code=409, detail="このメールアドレスは、別の Google アカウントで使われています")
    if row is None:
        return conn.execute(
            "INSERT INTO users (last_name, first_name, email, password_hash, google_sub, avatar_url, last_login_at) "
            f"VALUES (%s, %s, %s, %s, %s, %s, now()) RETURNING {USER_COLUMNS}",
            (profile.last_name, profile.first_name, profile.email, NO_PASSWORD, profile.sub, profile.avatar_url),
        ).fetchone()
    # 既存の人: Google の ID と画像を結ぶ。名前は、まだ空のときだけ Google の値で埋める（本人が変えた名前を上書きしない）
    return conn.execute(
        "UPDATE users SET google_sub = %s, avatar_url = %s, last_name = coalesce(last_name, %s), first_name = coalesce(first_name, %s), "
        f"last_login_at = now() WHERE id = %s RETURNING {USER_COLUMNS}",
        (profile.sub, profile.avatar_url, profile.last_name, profile.first_name, row["id"]),
    ).fetchone()


@router.post("/google", response_model=Session)
def google_login_endpoint(body: GoogleLoginRequest) -> Session:
    config = settings.google_oauth()
    if config is None:
        raise HTTPException(status_code=503, detail="Google でのログインは、まだ設定されていません")
    client_id, client_secret, redirect_uri = config
    if body.redirect_uri != redirect_uri:
        raise HTTPException(status_code=400, detail=GOOGLE_FAILED)
    try:
        tokens = google_login.exchange_code(body.code, body.code_verifier, client_id, client_secret, redirect_uri)
        profile = google_login.profile_from_id_token(tokens["id_token"], client_id, body.nonce)
    except google_login.GoogleLoginError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    with connection() as conn:
        try:
            row = _google_user(conn, profile)
        except errors.UniqueViolation:
            raise HTTPException(status_code=409, detail="このメールアドレスは、別の Google アカウントで使われています") from None
        token = _issue_session(conn, row["id"])
    return Session(token=token, user=User(**{k: row[k] for k in User.model_fields}))


@router.post("/logout", status_code=204)
def logout(authorization: Annotated[str | None, Header()] = None) -> Response:
    """送られたトークンが、すでに無効でも 204 を返す（ログアウトは何度呼んでも同じ結果）。ヘッダーが無いときは 401。"""
    token = bearer(authorization)
    with connection() as conn:
        conn.execute("DELETE FROM user_sessions WHERE token_hash = %s", (digest(token),))
    return Response(status_code=204)
