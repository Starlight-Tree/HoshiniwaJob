"""求職者のログイン状態の確認と、プロフィール（表示名）。

ログイン（Google との通信・セッション・JWT の発行）は、画面のサーバー（Next.js）の中の Better Auth の仕事で、この API は扱わない（frontend/src/lib/auth.ts）。
画面のサーバーは、ログイン中の人の JWT（15 分）を `Authorization: Bearer <JWT>` で送ってくる。ここでは、JWKS の公開鍵で検証し（jwt_auth.py）、
JWT の `sub` を `users.auth_user_id` に結んで、求職者のプロフィール（users の行）を返す。ブラウザーは API を直接呼ばない。
はじめての人は、最初のリクエストで行を作る。確認済みのメールが同じ既存の行があれば、新しい行は作らず、その行に結ぶ。
エラーの本文は固定の文にする（例外の文字列は返さない）。
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from psycopg import errors

from app import jwt_auth
from app.db import connection
from app.schemas import UpdateNameRequest, User
from app.security import NOT_LOGGED_IN, bearer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth")

# パスワードを持たない利用者（Google だけでログインする人）の password_hash。argon2 として読めない印なので、検証は必ず失敗する（パスワードでは入れない）。
NO_PASSWORD = "!"
USER_COLUMNS = "id, email, display_name, avatar_url"

CONFLICT = HTTPException(status_code=409, detail="このメールアドレスは、別の Google アカウントで使われています")
NOT_CONFIGURED = HTTPException(status_code=503, detail="Google でのログインは、まだ設定されていません")
UNAVAILABLE = HTTPException(status_code=503, detail="ログインを確認できませんでした。しばらくしてから、もう一度お試しください")


def _profile_for(conn, ident: jwt_auth.Identity) -> dict:
    """JWT の持ち主の users の行。結ばれていれば、その行。なければ、確認済みのメールが同じ既存の行に結ぶ。それも無ければ作る。"""
    row = conn.execute(f"SELECT {USER_COLUMNS} FROM users WHERE auth_user_id = %s", (ident.sub,)).fetchone()
    if row is not None:
        # 毎回のリクエストでは書かない。画像が変わったときと、最後のログインが 1 時間以上前のときだけ
        if row["avatar_url"] != ident.picture:
            conn.execute("UPDATE users SET avatar_url = %s WHERE id = %s", (ident.picture, row["id"]))
            row["avatar_url"] = ident.picture
        conn.execute(
            "UPDATE users SET last_login_at = now() WHERE id = %s AND (last_login_at IS NULL OR last_login_at < now() - interval '1 hour')",
            (row["id"],),
        )
        return row
    row = conn.execute(f"SELECT {USER_COLUMNS}, auth_user_id FROM users WHERE lower(email) = %s", (ident.email,)).fetchone()
    if row is not None and row["auth_user_id"] not in (None, ident.sub):
        # 同じメールの人が、すでに別の Google アカウントと結ばれている。乗っ取りを防ぐため、結び直さない
        raise CONFLICT
    if row is None:
        return conn.execute(
            "INSERT INTO users (display_name, email, password_hash, auth_user_id, avatar_url, last_login_at) "
            f"VALUES (%s, %s, %s, %s, %s, now()) RETURNING {USER_COLUMNS}",
            (ident.name, ident.email, NO_PASSWORD, ident.sub, ident.picture),
        ).fetchone()
    # 既存の人: 結ぶ。表示名は、まだ空のときだけ Google の名前で埋める（本人が決めた名前を上書きしない）
    return conn.execute(
        "UPDATE users SET auth_user_id = %s, avatar_url = %s, display_name = coalesce(display_name, %s), "
        f"last_login_at = now() WHERE id = %s RETURNING {USER_COLUMNS}",
        (ident.sub, ident.picture, ident.name, row["id"]),
    ).fetchone()


def current_user(authorization: Annotated[str | None, Header()] = None) -> User:
    """ログイン中の利用者。トークンが無い・違う・期限切れなら 401。認証の設定が無ければ 503。"""
    token = bearer(authorization)
    try:
        ident = jwt_auth.verify_token(token)
    except jwt_auth.InvalidToken as e:
        logger.info("認証に失敗しました (reason=%s)", e)  # 失敗の種類だけ。トークンの中身は出さない
        raise NOT_LOGGED_IN from None
    except jwt_auth.AuthNotConfigured:
        raise NOT_CONFIGURED from None
    except jwt_auth.AuthUnavailable:
        raise UNAVAILABLE from None
    try:
        with connection() as conn:
            row = _profile_for(conn, ident)
    except errors.UniqueViolation:
        # はじめてのリクエストが同時に 2 つ来た（同じ人）。もう一方が作った行を読む。見つからなければ、メールの競合
        with connection() as conn:
            row = conn.execute(f"SELECT {USER_COLUMNS} FROM users WHERE auth_user_id = %s", (ident.sub,)).fetchone()
        if row is None:
            raise CONFLICT from None
    return User(**row)


@router.get("/me", response_model=User)
def me(user: Annotated[User, Depends(current_user)]) -> User:
    return user


@router.patch("/me", response_model=User)
def update_name(body: UpdateNameRequest, user: Annotated[User, Depends(current_user)]) -> User:
    """表示名（ニックネーム）の変更。変えられるのはログイン中の本人のものだけ（id は、JWT の持ち主から決まる）。"""
    with connection() as conn:
        row = conn.execute(
            f"UPDATE users SET display_name = %s WHERE id = %s RETURNING {USER_COLUMNS}",
            (body.display_name, user.id),
        ).fetchone()
    return User(**row)
