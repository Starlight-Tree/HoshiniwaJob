import hashlib

import psycopg

from app import garden
from app.security import DUMMY_HASH
from tests.conftest import TEST_URL

GARDEN = {"email": "hoshiniwa-garden@example.com", "password": "star-garden-demo"}
GARDEN2 = {"email": "hoshiniwa-garden2@example.com", "password": "star-garden-demo"}
USER = {"email": "hoshiniwa-user@example.com", "password": "star-garden-demo"}


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def garden_login(client, creds=GARDEN) -> str:
    res = client.post("/api/garden/auth/login", json=creds)
    assert res.status_code == 200
    return res.json()["token"]


def db_exec(sql: str, params: tuple = ()):
    with psycopg.connect(TEST_URL.rsplit("/", 1)[0] + "/hj_test", autocommit=True) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else None


def test_login_then_me_then_logout(client):
    res = client.post("/api/garden/auth/login", json={"email": " Hoshiniwa-Garden@Example.com", "password": "star-garden-demo"})
    assert res.status_code == 200
    body = res.json()
    assert body["garden"]["corporate"] == "環軌道植物公社"
    assert "password" not in str(body)
    token = body["token"]

    assert client.get("/api/garden/auth/me", headers=bearer(token)).json()["email"] == "hoshiniwa-garden@example.com"
    assert client.post("/api/garden/auth/logout", headers=bearer(token)).status_code == 204
    assert client.get("/api/garden/auth/me", headers=bearer(token)).status_code == 401
    assert client.get("/api/garden/summary", headers=bearer(token)).status_code == 401
    # 2 回目のログアウトも 204（何度呼んでも同じ）
    assert client.post("/api/garden/auth/logout", headers=bearer(token)).status_code == 204


def test_login_failures_share_one_message(client):
    wrong_pw = client.post("/api/garden/auth/login", json={**GARDEN, "password": "nope-nope"})
    no_garden = client.post("/api/garden/auth/login", json={"email": "nobody@example.com", "password": "star-garden-demo"})
    # 利用者のアカウントでは、園にはログインできない
    user_account = client.post("/api/garden/auth/login", json=USER)
    assert wrong_pw.status_code == no_garden.status_code == user_account.status_code == 401
    assert wrong_pw.json() == no_garden.json() == user_account.json() == {"detail": "メールアドレスまたはパスワードが違います"}


def test_unknown_email_still_spends_the_hashing_time(client, monkeypatch):
    checked = []

    def spy(stored_hash: str, password: str) -> bool:
        checked.append(stored_hash)
        return False

    monkeypatch.setattr(garden, "verify_password", spy)
    client.post("/api/garden/auth/login", json={"email": "nobody@example.com", "password": "whatever-1"})
    assert checked == [DUMMY_HASH]


def test_tokens_are_not_stored_in_plain_text(client):
    token = garden_login(client)
    hashes = [r[0] for r in db_exec("SELECT token_hash FROM garden_sessions")]
    assert token not in hashes
    assert hashlib.sha256(token.encode()).hexdigest() in hashes
    stored = db_exec("SELECT password_hash FROM garden_accounts WHERE email = %s", (GARDEN["email"],))[0][0]
    assert stored.startswith("$argon2id$") and GARDEN["password"] not in stored


def test_me_requires_a_valid_token(client):
    assert client.get("/api/garden/auth/me").status_code == 401
    assert client.get("/api/garden/auth/me", headers={"Authorization": "Basic abc"}).status_code == 401
    assert client.get("/api/garden/auth/me", headers=bearer("not-a-real-token")).status_code == 401
    assert client.get("/api/garden/summary").status_code == 401


def test_expired_session_is_rejected(client):
    token = garden_login(client)
    db_exec(
        "UPDATE garden_sessions SET expires_at = now() - interval '1 second' WHERE token_hash = %s",
        (hashlib.sha256(token.encode()).hexdigest(),),
    )
    assert client.get("/api/garden/auth/me", headers=bearer(token)).status_code == 401
    assert client.get("/api/garden/summary", headers=bearer(token)).status_code == 401


def test_user_token_cannot_open_garden_api(client):
    user_token = client.post("/api/auth/login", json=USER).json()["token"]
    assert client.get("/api/garden/auth/me", headers=bearer(user_token)).status_code == 401
    assert client.get("/api/garden/summary", headers=bearer(user_token)).status_code == 401


def test_garden_token_cannot_open_user_api(client):
    token = garden_login(client)
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401
    # 園のトークンでの利用者のログアウトは、園のセッションを消さない
    assert client.post("/api/auth/logout", headers=bearer(token)).status_code == 204
    assert client.get("/api/garden/auth/me", headers=bearer(token)).status_code == 200


def test_summary_counts_only_own_recruits(client):
    first = client.get("/api/garden/summary", headers=bearer(garden_login(client))).json()
    second = client.get("/api/garden/summary", headers=bearer(garden_login(client, GARDEN2))).json()
    assert first == {"corporate": "環軌道植物公社", "email": "hoshiniwa-garden@example.com", "displayed": 2, "hidden": 1}
    assert second == {"corporate": "ミルフェン月面植物園", "email": "hoshiniwa-garden2@example.com", "displayed": 2, "hidden": 0}

    # どの園にも紐づかない求人は、どちらの件数にも入らない
    total = db_exec("SELECT count(*) FROM recruits")[0][0]
    owned = db_exec("SELECT count(*) FROM recruits WHERE garden_account_id IS NOT NULL")[0][0]
    assert owned == first["displayed"] + first["hidden"] + second["displayed"] + second["hidden"] < total


def test_no_garden_registration_endpoint(client):
    body = {"corporate": "試験法人", "email": "new-garden@example.com", "password": "correct-horse-1"}
    assert client.post("/api/garden/auth/register", json=body).status_code in (404, 405)
