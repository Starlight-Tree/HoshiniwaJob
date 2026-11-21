"""園・法人のログイン・ログアウトと、ダッシュボード用の件数。

仕組みは利用者（auth.py）と同じ（部品は security.py）。ただし、アカウントもセッションも別の表で、
利用者のトークンでは園の API を、園のトークンでは利用者の API を開けない。
園の会員登録の API は作らない（アカウントは運営が seed で作る）。
園が見られるのは、自分のアカウントと、自分に紐づく求人（recruits.garden_account_id）だけ。

ログインには、メールアドレスごとの試行の制限がある（garden_login_attempts。数え方は 0007 の SQL の冒頭）。
IP では数えない（API を呼ぶのは画面のサーバーで、どの利用者も同じ送信元に見えるため）。窓の間の試行が上限を超えたら、正しいパスワードでも 429。
登録済みかどうかで応答を分けない（上限の応答も、メールが無いときの処理も、登録済みのときと同じ）。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response

from app.db import connection
from app.schemas import Garden, GardenSession, GardenSummary, LoginRequest
from app.security import BAD_LOGIN, DUMMY_HASH, LOGIN_LOCKED, NOT_LOGGED_IN, SESSION_DAYS, bearer, digest, hasher, new_token, verify_password
from app.settings import garden_login_limits

router = APIRouter(prefix="/api/garden")


def _issue_session(conn, garden_id: int) -> str:
    token = new_token()
    conn.execute("DELETE FROM garden_sessions WHERE expires_at < now()")  # 期限切れの掃除（呼ばれたときについでに）
    conn.execute(
        "INSERT INTO garden_sessions (token_hash, garden_account_id, expires_at) VALUES (%s, %s, now() + make_interval(days => %s))",
        (digest(token), garden_id, SESSION_DAYS),
    )
    return token


def _login_key(email: str) -> str:
    """試行を数えるときの鍵。正規化（前後の空白を除き小文字）したメールの SHA-256。生のメールは表に置かない。"""
    return digest(email.strip().lower())


def _reserve_login_attempt(email_hash: str) -> bool:
    """このメールの試行を 1 つ数え、窓の中の上限の内なら True（上限を超えたら False）。パスワードを確かめる前に呼ぶ。

    数えるのは 1 文の INSERT ... ON CONFLICT なので、同時に大量に送られても、上限を超えて確かめない。
    ログインの失敗は例外（BAD_LOGIN）で終わり、その接続の変更は巻き戻る。数えた分が消えないよう、ログインの本体とは別の接続・別のトランザクションで確定する。
    窓は、そのメールの最初の試行から（窓の長さが過ぎたら数え直す）。窓の 2 倍より古い行は、ここでついでに消す。
    """
    max_failures, window_minutes = garden_login_limits()
    params = {"hash": email_hash, "max": max_failures, "window": window_minutes}
    with connection() as conn:
        conn.execute(
            "DELETE FROM garden_login_attempts WHERE window_start < now() - make_interval(mins => %(window)s * 2)", params
        )
        row = conn.execute(
            "INSERT INTO garden_login_attempts AS a (email_hash, failures, window_start) VALUES (%(hash)s, 1, now()) "
            "ON CONFLICT (email_hash) DO UPDATE SET "
            "failures = CASE WHEN a.window_start <= now() - make_interval(mins => %(window)s) THEN 1 ELSE LEAST(a.failures + 1, %(max)s + 1) END, "
            "window_start = CASE WHEN a.window_start <= now() - make_interval(mins => %(window)s) THEN now() ELSE a.window_start END "
            "RETURNING failures",
            params,
        ).fetchone()
    return row["failures"] <= max_failures


def current_garden(authorization: Annotated[str | None, Header()] = None) -> Garden:
    """ログイン中の園。トークンが無い・違う・期限切れなら 401。"""
    token = bearer(authorization)
    with connection() as conn:
        row = conn.execute(
            "SELECT g.id, g.email, g.corporate FROM garden_sessions s JOIN garden_accounts g ON g.id = s.garden_account_id "
            "WHERE s.token_hash = %s AND s.expires_at > now()",
            (digest(token),),
        ).fetchone()
    if row is None:
        raise NOT_LOGGED_IN
    return Garden(**row)


@router.post("/auth/login", response_model=GardenSession)
def login(body: LoginRequest) -> GardenSession:
    email_hash = _login_key(body.email)
    if not _reserve_login_attempt(email_hash):
        raise LOGIN_LOCKED  # 登録済みかどうか、パスワードが合っているかを調べない（正しくても拒否する）
    with connection() as conn:
        row = conn.execute(
            "SELECT id, email, corporate, password_hash FROM garden_accounts WHERE lower(email) = %s", (body.email,)
        ).fetchone()
        stored = row["password_hash"] if row else DUMMY_HASH
        verified = verify_password(stored, body.password) and row is not None
        if not verified:
            raise BAD_LOGIN  # 数えた試行は、そのまま残る
        conn.execute("DELETE FROM garden_login_attempts WHERE email_hash = %s", (email_hash,))  # 成功したら、そのメールの数えを消す
        if hasher.check_needs_rehash(stored):  # 設定を強めたとき、次のログインで新しいハッシュに更新する
            conn.execute("UPDATE garden_accounts SET password_hash = %s WHERE id = %s", (hasher.hash(body.password), row["id"]))
        token = _issue_session(conn, row["id"])
    return GardenSession(token=token, garden=Garden(id=row["id"], email=row["email"], corporate=row["corporate"]))


@router.get("/auth/me", response_model=Garden)
def me(garden: Annotated[Garden, Depends(current_garden)]) -> Garden:
    return garden


@router.post("/auth/logout", status_code=204)
def logout(authorization: Annotated[str | None, Header()] = None) -> Response:
    """送られたトークンが、すでに無効でも 204 を返す（ログアウトは何度呼んでも同じ結果）。ヘッダーが無いときは 401。"""
    token = bearer(authorization)
    with connection() as conn:
        conn.execute("DELETE FROM garden_sessions WHERE token_hash = %s", (digest(token),))
    return Response(status_code=204)


@router.get("/summary", response_model=GardenSummary)
def summary(garden: Annotated[Garden, Depends(current_garden)]) -> GardenSummary:
    with connection() as conn:
        row = conn.execute(
            "SELECT count(*) FILTER (WHERE is_displayed) AS displayed, count(*) FILTER (WHERE NOT is_displayed) AS hidden "
            "FROM recruits WHERE garden_account_id = %s",
            (garden.id,),
        ).fetchone()
    return GardenSummary(corporate=garden.corporate, email=garden.email, displayed=row["displayed"], hidden=row["hidden"])
