"""Google でのログイン。Google へは接続しない（コードの交換は差し替え、ID トークンはテスト用に作る。署名は検証しない設計）。"""

import time

import jwt
import psycopg
import pytest

from app import google_login
from tests.conftest import TEST_URL

CLIENT_ID = "test-client-id.apps.googleusercontent.com"
REDIRECT = "http://localhost:3200/auth/google/callback"
NONCE = "n" * 24
BODY = {"code": "auth-code", "code_verifier": "v" * 50, "nonce": NONCE, "redirect_uri": REDIRECT}
PICTURE = "https://lh3.googleusercontent.com/a/example=s96-c"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def db_rows(sql: str, params: tuple = ()):
    with psycopg.connect(TEST_URL.rsplit("/", 1)[0] + "/hj_test") as conn:
        return conn.execute(sql, params).fetchall()


def claims(**over):
    base = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "exp": int(time.time()) + 600,
        "nonce": NONCE,
        "sub": "google-sub-1",
        "email": "Taro.Google@Example.com",
        "email_verified": True,
        "given_name": "太郎",
        "family_name": "山田",
        "picture": PICTURE,
    }
    base.update(over)
    return base


@pytest.fixture
def google(monkeypatch):
    """Google の設定を入れ、コードの交換を、渡した claims の ID トークンを返すものに差し替える。"""
    monkeypatch.setenv("GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", REDIRECT)
    state = {"claims": claims(), "calls": []}

    def fake_exchange(code, verifier, client_id, client_secret, redirect_uri):
        state["calls"].append((code, verifier, client_id, client_secret, redirect_uri))
        return {"id_token": jwt.encode(state["claims"], "unused-test-key-" * 4, algorithm="HS256")}

    monkeypatch.setattr(google_login, "exchange_code", fake_exchange)
    return state


def test_not_configured_returns_503_with_a_fixed_message(client, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    res = client.post("/api/auth/google", json=BODY)
    assert res.status_code == 503
    assert res.json()["detail"] == "Google でのログインは、まだ設定されていません"


def test_first_login_creates_a_user_with_profile_and_no_usable_password(client, google):
    res = client.post("/api/auth/google", json=BODY)
    assert res.status_code == 200
    body = res.json()
    assert body["user"]["email"] == "taro.google@example.com"
    assert (body["user"]["last_name"], body["user"]["first_name"]) == ("山田", "太郎")
    assert body["user"]["avatar_url"] == PICTURE
    # コードの交換には、画面から受け取った code・verifier と、API の持つ設定だけを渡す
    assert google["calls"] == [("auth-code", "v" * 50, CLIENT_ID, "test-secret", REDIRECT)]
    me = client.get("/api/auth/me", headers=bearer(body["token"])).json()
    assert me["avatar_url"] == PICTURE and me["id"] == body["user"]["id"]
    stored = db_rows("SELECT password_hash, google_sub FROM users WHERE email = 'taro.google@example.com'")[0]
    assert stored == ("!", "google-sub-1")


def test_google_only_user_cannot_log_in_with_a_password(client, google):
    client.post("/api/auth/google", json=BODY)
    for password in ("!", "any-password-1", "x" * 20):
        res = client.post("/api/auth/login", json={"email": "taro.google@example.com", "password": password})
        assert res.status_code == 401


def test_second_login_with_the_same_google_id_reuses_the_user_and_updates_the_picture(client, google):
    first = client.post("/api/auth/google", json=BODY).json()
    google["claims"] = claims(picture="https://lh3.googleusercontent.com/a/new=s96-c")
    second = client.post("/api/auth/google", json=BODY).json()
    assert second["user"]["id"] == first["user"]["id"]
    assert second["user"]["avatar_url"].endswith("new=s96-c")
    assert db_rows("SELECT count(*) FROM users WHERE google_sub = 'google-sub-1'")[0][0] == 1


def test_google_login_links_an_existing_password_user_by_verified_email(client, google):
    reg = client.post(
        "/api/auth/register",
        json={"last_name": "既存", "first_name": "花子", "email": "link@example.com", "password": "correct-horse-1"},
    ).json()
    google["claims"] = claims(sub="google-sub-link", email="LINK@example.com", given_name="別名", family_name="別姓")
    res = client.post("/api/auth/google", json=BODY).json()
    assert res["user"]["id"] == reg["user"]["id"]
    # 本人が付けた名前は上書きしない。パスワードでのログインも、そのまま使える
    assert (res["user"]["last_name"], res["user"]["first_name"]) == ("既存", "花子")
    assert client.post("/api/auth/login", json={"email": "link@example.com", "password": "correct-horse-1"}).status_code == 200
    assert db_rows("SELECT google_sub FROM users WHERE email = 'link@example.com'")[0][0] == "google-sub-link"


def test_same_email_already_linked_to_another_google_account_is_refused(client, google):
    google["claims"] = claims(sub="google-sub-A", email="shared@example.com")
    assert client.post("/api/auth/google", json=BODY).status_code == 200
    google["claims"] = claims(sub="google-sub-B", email="shared@example.com")
    res = client.post("/api/auth/google", json=BODY)
    assert res.status_code == 409
    assert res.json()["detail"] == "このメールアドレスは、別の Google アカウントで使われています"
    assert db_rows("SELECT google_sub FROM users WHERE email = 'shared@example.com'")[0][0] == "google-sub-A"


@pytest.mark.parametrize(
    "over",
    [
        {"iss": "https://evil.example.com"},
        {"aud": "another-client-id"},
        {"aud": ["x", "y"]},
        {"exp": 1},
        {"nonce": "w" * 24},
        {"sub": ""},
        {"email": ""},
    ],
    ids=["issuer", "audience", "audience-list", "expired", "nonce", "no-sub", "no-email"],
)
def test_invalid_id_tokens_are_refused_and_nothing_is_created(client, google, over):
    before = db_rows("SELECT count(*) FROM users")[0][0]
    google["claims"] = claims(**{"sub": "google-sub-bad", "email": "bad@example.com", **over})
    res = client.post("/api/auth/google", json=BODY)
    assert res.status_code == 400
    assert res.json()["detail"] == "Google でのログインに失敗しました。もう一度お試しください"
    assert db_rows("SELECT count(*) FROM users")[0][0] == before


def test_unverified_email_is_refused(client, google):
    google["claims"] = claims(sub="google-sub-unv", email="unverified@example.com", email_verified=False)
    res = client.post("/api/auth/google", json=BODY)
    assert res.status_code == 400
    assert "確認が済んでいない" in res.json()["detail"]
    assert db_rows("SELECT count(*) FROM users WHERE email = 'unverified@example.com'")[0][0] == 0


def test_the_audience_may_be_a_list_that_contains_our_client_id(client, google):
    google["claims"] = claims(sub="google-sub-list", email="list@example.com", aud=["other", CLIENT_ID])
    assert client.post("/api/auth/google", json=BODY).status_code == 200


def test_an_empty_redirect_uri_setting_falls_back_to_the_default(monkeypatch):
    from app import settings

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "")  # Compose の ${GOOGLE_REDIRECT_URI:-} が、未設定のとき空文字を渡す
    assert settings.google_oauth() == ("cid", "secret", "http://localhost:3200/auth/google/callback")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", " ")
    assert settings.google_oauth() is None


def test_redirect_uri_must_match_the_configured_one(client, google):
    res = client.post("/api/auth/google", json={**BODY, "redirect_uri": "https://evil.example.com/cb"})
    assert res.status_code == 400
    assert google["calls"] == []  # Google へは、渡さない


def test_a_picture_that_is_not_https_is_not_stored(client, google):
    google["claims"] = claims(sub="google-sub-http", email="http@example.com", picture="http://example.com/a.png")
    res = client.post("/api/auth/google", json=BODY).json()
    assert res["user"]["avatar_url"] is None


def test_exchange_failures_return_a_fixed_message_without_details(client, google, monkeypatch):
    def broken(*args, **kwargs):
        raise google_login.GoogleLoginError("Google でのログインに失敗しました。もう一度お試しください")

    monkeypatch.setattr(google_login, "exchange_code", broken)
    res = client.post("/api/auth/google", json=BODY)
    assert res.status_code == 400
    assert res.json() == {"detail": "Google でのログインに失敗しました。もう一度お試しください"}


@pytest.mark.parametrize("patch", [{"code": ""}, {"code_verifier": "short"}, {"nonce": "short"}, {"redirect_uri": ""}])
def test_request_validation(client, google, patch):
    assert client.post("/api/auth/google", json={**BODY, **patch}).status_code == 422


def test_exchange_code_hides_google_errors(monkeypatch):
    """実際の exchange_code は、通信の失敗の詳細（URL・本文・例外の文字列）を外へ出さない。"""
    import urllib.error

    def boom(*args, **kwargs):
        raise urllib.error.URLError("secret-host-detail")

    monkeypatch.setattr(google_login.urllib.request, "urlopen", boom)
    with pytest.raises(google_login.GoogleLoginError) as info:
        google_login.exchange_code("c", "v" * 50, "id", "secret", REDIRECT)
    assert "secret-host-detail" not in str(info.value) and info.value.__cause__ is None
