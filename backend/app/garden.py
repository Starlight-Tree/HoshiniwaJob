"""園・法人のログイン・ログアウトと、ダッシュボード用の件数。

仕組みは利用者（auth.py）と同じ（部品は security.py）。ただし、アカウントもセッションも別の表で、
利用者のトークンでは園の API を、園のトークンでは利用者の API を開けない。
園の会員登録の API は作らない（アカウントは運営が seed で作る）。
園が見られるのは、自分のアカウントと、自分に紐づく求人（recruits.garden_account_id）だけ。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response

from app.db import connection
from app.schemas import Garden, GardenSession, GardenSummary, LoginRequest
from app.security import BAD_LOGIN, DUMMY_HASH, NOT_LOGGED_IN, SESSION_DAYS, bearer, digest, hasher, new_token, verify_password

router = APIRouter(prefix="/api/garden")


def _issue_session(conn, garden_id: int) -> str:
    token = new_token()
    conn.execute("DELETE FROM garden_sessions WHERE expires_at < now()")  # 期限切れの掃除（呼ばれたときについでに）
    conn.execute(
        "INSERT INTO garden_sessions (token_hash, garden_account_id, expires_at) VALUES (%s, %s, now() + make_interval(days => %s))",
        (digest(token), garden_id, SESSION_DAYS),
    )
    return token


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
    with connection() as conn:
        row = conn.execute(
            "SELECT id, email, corporate, password_hash FROM garden_accounts WHERE lower(email) = %s", (body.email,)
        ).fetchone()
        stored = row["password_hash"] if row else DUMMY_HASH
        verified = verify_password(stored, body.password) and row is not None
        if not verified:
            raise BAD_LOGIN
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
