"""求職者の API（app/auth.py）。ログインは Better Auth の仕事で、ここでは、JWT を受けて利用者の行に結ぶところと、お名前の変更を確かめる。"""

import psycopg
import pytest

from tests.conftest import TEST_URL
from tests.jwt_tokens import DEFAULT_SUB, OTHER_PRIVATE_KEY, make_token


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def db_rows(sql: str, params: tuple = ()):
    with psycopg.connect(TEST_URL.rsplit("/", 1)[0] + "/hj_test") as conn:
        return conn.execute(sql, params).fetchall()


def ensure_auth_user(sub: str) -> None:
    """Better Auth が作る「だれか」（auth_user）の行。実際には、JWT が出る前に、Better Auth（画面のサーバー）が作っている（users.auth_user_id の外部キー）。"""
    with psycopg.connect(TEST_URL.rsplit("/", 1)[0] + "/hj_test") as conn:
        conn.execute(
            'INSERT INTO auth_user ("id", "name", "email", "emailVerified") VALUES (%s, %s, %s, true) ON CONFLICT ("id") DO NOTHING',
            (sub, sub, f"{sub}@auth.test"),
        )


def me(client, **overrides):
    ensure_auth_user(overrides.get("sub", DEFAULT_SUB))
    return client.get("/api/auth/me", headers=bearer(make_token(**overrides)))


def test_first_request_creates_the_profile_from_the_token(auth_env, client):
    res = me(client, sub="ba_user_first00001", email="first.user@example.com", last_name="初", first_name="回")
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == "first.user@example.com"
    assert (body["last_name"], body["first_name"]) == ("初", "回")
    assert body["avatar_url"] == "https://lh3.googleusercontent.com/a/test"
    assert "password" not in str(body)
    (row,) = db_rows("SELECT auth_user_id, password_hash FROM users WHERE id = %s", (body["id"],))
    assert row[0] == "ba_user_first00001"
    assert row[1] == "!"  # パスワードでは入れない印（argon2 として読めない）


def test_second_request_uses_the_same_profile(auth_env, client):
    first = me(client, sub="ba_user_again0001", email="again.user@example.com").json()
    second = me(client, sub="ba_user_again0001", email="again.user@example.com").json()
    assert first["id"] == second["id"]
    assert db_rows("SELECT count(*) FROM users WHERE auth_user_id = %s", ("ba_user_again0001",)) == [(1,)]


def test_existing_user_with_the_same_verified_email_is_linked_not_duplicated(auth_env, client):
    # ダミーの求職者（seed）と同じメール。名前は、本人が決めたもの（空でないとき）を上書きしない
    before = db_rows("SELECT id, last_name, first_name FROM users WHERE lower(email) = 'hoshiniwa-user@example.com'")
    assert len(before) == 1
    uid, last, first = before[0]
    res = me(client, sub="ba_user_linked0001", email="Hoshiniwa-User@Example.com", last_name="別の姓", first_name="別の名")
    assert res.status_code == 200
    assert res.json()["id"] == uid
    assert (res.json()["last_name"], res.json()["first_name"]) == (last, first)
    assert db_rows("SELECT auth_user_id FROM users WHERE id = %s", (uid,)) == [("ba_user_linked0001",)]
    assert db_rows("SELECT count(*) FROM users WHERE lower(email) = 'hoshiniwa-user@example.com'") == [(1,)]


def test_same_email_already_linked_to_another_account_is_a_conflict(auth_env, client):
    # 上のテストで結ばれたメールへ、別の Google アカウント（別の sub）が来た。乗っ取りを防ぐため、結び直さない
    me(client, sub="ba_user_linked0001", email="hoshiniwa-user@example.com")
    res = me(client, sub="ba_user_intruder01", email="hoshiniwa-user@example.com")
    assert res.status_code == 409
    assert res.json()["detail"] == "このメールアドレスは、別の Google アカウントで使われています"
    assert db_rows("SELECT count(*) FROM users WHERE auth_user_id = %s", ("ba_user_intruder01",)) == [(0,)]


def test_picture_follows_the_token(auth_env, client):
    sub = "ba_user_picture001"
    me(client, sub=sub, email="picture.user@example.com", picture="https://lh3.googleusercontent.com/a/old")
    new = me(client, sub=sub, email="picture.user@example.com", picture="https://lh3.googleusercontent.com/a/new").json()
    assert new["avatar_url"] == "https://lh3.googleusercontent.com/a/new"
    # https 以外の画像は持たない
    plain = me(client, sub=sub, email="picture.user@example.com", picture="http://example.com/a.png").json()
    assert plain["avatar_url"] is None


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer"}, {"Authorization": "Bearer not-a-jwt"}],
)
def test_missing_or_malformed_authorization_is_401(auth_env, client, headers):
    res = client.get("/api/auth/me", headers=headers)
    assert res.status_code == 401
    assert res.json()["detail"] == "ログインしてください"


def test_bad_tokens_are_401_with_a_fixed_message(auth_env, client):
    for token in (
        make_token(exp=1),
        make_token(aud="docunavi"),
        make_token(iss="http://evil.example"),
        make_token(key=OTHER_PRIVATE_KEY),
        make_token(email_verified=False),
    ):
        res = client.get("/api/auth/me", headers=bearer(token))
        assert res.status_code == 401
        assert res.json() == {"detail": "ログインしてください"}


def test_a_garden_session_token_is_not_a_user_token(auth_env, client):
    garden = client.post("/api/garden/auth/login", json={"email": "hoshiniwa-garden@example.com", "password": "star-garden-demo"}).json()["token"]
    assert client.get("/api/auth/me", headers=bearer(garden)).status_code == 401


def test_not_configured_is_503(client, monkeypatch):
    for name in ("AUTH_BASE_URL", "AUTH_JWKS_URL"):
        monkeypatch.delenv(name, raising=False)
    res = client.get("/api/auth/me", headers=bearer(make_token()))
    assert res.status_code == 503
    assert "まだ設定されていません" in res.json()["detail"]


def test_jwks_unreachable_is_503_without_leaking_details(auth_env, client, monkeypatch):
    from app import jwt_auth

    def down(url: str):
        raise OSError("connect ECONNREFUSED 10.0.0.5:3000")

    monkeypatch.setattr(jwt_auth, "fetch_jwks_document", down)
    res = client.get("/api/auth/me", headers=bearer(make_token()))
    assert res.status_code == 503
    assert "ECONNREFUSED" not in res.text and "10.0.0.5" not in res.text


def test_password_login_and_registration_are_gone(auth_env, client):
    for path in ("/api/auth/register", "/api/auth/login", "/api/auth/google", "/api/auth/logout"):
        assert client.post(path, json={}).status_code in (404, 405), path


def test_update_name_changes_only_my_row(auth_env, client):
    mine = me(client, sub="ba_user_rename0001", email="rename.me@example.com").json()
    other = me(client, sub="ba_user_rename0002", email="rename.other@example.com").json()
    res = client.patch(
        "/api/auth/me",
        headers=bearer(make_token(sub="ba_user_rename0001", email="rename.me@example.com")),
        json={"last_name": "新姓", "first_name": "新名"},
    )
    assert res.status_code == 200
    assert (res.json()["last_name"], res.json()["first_name"]) == ("新姓", "新名")
    rows = dict(db_rows("SELECT id, last_name FROM users WHERE id IN (%s, %s)", (mine["id"], other["id"])))
    assert rows[mine["id"]] == "新姓"
    assert rows[other["id"]] == other["last_name"]
    # 名前は、本人が決めたものが、次のログインの Google の値より優先される
    again = me(client, sub="ba_user_rename0001", email="rename.me@example.com", last_name="Google の姓").json()
    assert again["last_name"] == "新姓"


@pytest.mark.parametrize("body", [{}, {"last_name": "", "first_name": "名"}, {"last_name": "姓", "first_name": "あ" * 51}, {"last_name": "姓"}])
def test_update_name_validates_input(auth_env, client, body):
    ensure_auth_user("ba_user_validate01")
    res = client.patch("/api/auth/me", headers=bearer(make_token(sub="ba_user_validate01", email="validate.user@example.com")), json=body)
    assert res.status_code == 422


def test_update_name_requires_login(auth_env, client):
    assert client.patch("/api/auth/me", json={"last_name": "姓", "first_name": "名"}).status_code == 401
