import hashlib

import psycopg
import pytest

from tests.conftest import TEST_URL

NEW = {"last_name": "試験", "first_name": "花子", "email": "hanako@example.com", "password": "correct-horse-1"}


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def db_rows(sql: str, params: tuple = ()):
    with psycopg.connect(TEST_URL.rsplit("/", 1)[0] + "/hj_test") as conn:
        return conn.execute(sql, params).fetchall()


def test_register_then_me_then_logout(client):
    res = client.post("/api/auth/register", json=NEW)
    assert res.status_code == 201
    body = res.json()
    assert body["user"]["email"] == "hanako@example.com"
    assert "password" not in str(body)
    token = body["token"]

    assert client.get("/api/auth/me", headers=bearer(token)).json()["first_name"] == "花子"
    assert client.post("/api/auth/logout", headers=bearer(token)).status_code == 204
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401
    # 2 回目のログアウトも 204（何度呼んでも同じ）
    assert client.post("/api/auth/logout", headers=bearer(token)).status_code == 204


def test_passwords_and_tokens_are_not_stored_in_plain_text(client):
    token = client.post(
        "/api/auth/register", json={**NEW, "email": "plain-check@example.com", "password": "plain-check-pw"}
    ).json()["token"]
    stored = db_rows("SELECT password_hash FROM users WHERE email = 'plain-check@example.com'")[0][0]
    assert stored.startswith("$argon2id$") and "plain-check-pw" not in stored
    hashes = [r[0] for r in db_rows("SELECT token_hash FROM user_sessions")]
    assert token not in hashes
    assert hashlib.sha256(token.encode()).hexdigest() in hashes


def test_register_rejects_duplicate_email_case_insensitively(client):
    first = {**NEW, "email": "dup@example.com"}
    assert client.post("/api/auth/register", json=first).status_code == 201
    again = client.post("/api/auth/register", json={**first, "email": "  DUP@Example.com "})
    assert again.status_code == 409
    assert again.json()["detail"] == "このメールアドレスは登録できません"


@pytest.mark.parametrize(
    "patch",
    [{"password": "short"}, {"email": "not-an-email"}, {"last_name": ""}, {"first_name": "x" * 51}, {"password": "x" * 129}],
)
def test_register_validates_input(client, patch):
    assert client.post("/api/auth/register", json={**NEW, "email": "v@example.com", **patch}).status_code == 422


def test_login_with_demo_user_and_normalized_email(client):
    res = client.post("/api/auth/login", json={"email": " Hoshiniwa-User@Example.com", "password": "star-garden-demo"})
    assert res.status_code == 200
    assert res.json()["user"]["last_name"] == "苔野"
    assert client.get("/api/auth/me", headers=bearer(res.json()["token"])).status_code == 200


def test_login_failures_share_one_message(client):
    wrong_pw = client.post("/api/auth/login", json={"email": "hoshiniwa-user@example.com", "password": "nope-nope"})
    no_user = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "star-garden-demo"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json() == {"detail": "メールアドレスまたはパスワードが違います"}


def test_me_requires_a_valid_token(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Basic abc"}).status_code == 401
    assert client.get("/api/auth/me", headers=bearer("not-a-real-token")).status_code == 401


def test_expired_session_is_rejected(client):
    token = client.post("/api/auth/login", json={"email": "hoshiniwa-user@example.com", "password": "star-garden-demo"}).json()["token"]
    digest = hashlib.sha256(token.encode()).hexdigest()
    with psycopg.connect(TEST_URL.rsplit("/", 1)[0] + "/hj_test", autocommit=True) as conn:
        conn.execute("UPDATE user_sessions SET expires_at = now() - interval '1 second' WHERE token_hash = %s", (digest,))
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401


def test_garden_account_cannot_log_in_as_user(client):
    res = client.post("/api/auth/login", json={"email": "hoshiniwa-garden@example.com", "password": "star-garden-demo"})
    assert res.status_code == 401


def test_update_name_changes_only_the_logged_in_users_name(client):
    mine = client.post("/api/auth/register", json={**NEW, "email": "rename-me@example.com"}).json()
    other = client.post("/api/auth/register", json={**NEW, "email": "rename-other@example.com"}).json()
    res = client.patch("/api/auth/me", headers=bearer(mine["token"]), json={"last_name": "新姓", "first_name": "新名"})
    assert res.status_code == 200
    assert (res.json()["last_name"], res.json()["first_name"]) == ("新姓", "新名")
    assert client.get("/api/auth/me", headers=bearer(mine["token"])).json()["first_name"] == "新名"
    assert client.get("/api/auth/me", headers=bearer(other["token"])).json()["first_name"] == "花子"


def test_update_name_requires_login_and_validates_input(client):
    assert client.patch("/api/auth/me", json={"last_name": "a", "first_name": "b"}).status_code == 401
    token = client.post("/api/auth/register", json={**NEW, "email": "rename-v@example.com"}).json()["token"]
    for patch in ({"last_name": ""}, {"first_name": "x" * 51}, {"last_name": None}):
        res = client.patch("/api/auth/me", headers=bearer(token), json={"last_name": "姓", "first_name": "名", **patch})
        assert res.status_code == 422
    assert client.patch("/api/auth/me", headers=bearer(token), json={"last_name": "姓"}).status_code == 422
