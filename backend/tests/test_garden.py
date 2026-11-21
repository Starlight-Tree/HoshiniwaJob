import hashlib
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest

from app import garden
from app.security import DUMMY_HASH
from tests.conftest import TEST_URL
from tests.jwt_tokens import make_token

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


def test_user_token_cannot_open_garden_api(auth_env, client):
    # 求職者の JWT（Better Auth が発行したもの）は、園の API を開けない
    user_token = make_token()
    assert client.get("/api/garden/auth/me", headers=bearer(user_token)).status_code == 401
    assert client.get("/api/garden/summary", headers=bearer(user_token)).status_code == 401


def test_garden_token_cannot_open_user_api(auth_env, client):
    token = garden_login(client)
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401
    assert client.get("/api/garden/auth/me", headers=bearer(token)).status_code == 200  # 園のセッションは、そのまま


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


# ---- ログインの試行の制限（メールごと。0007 の garden_login_attempts。上限・窓の既定は 5 回・15 分） ----

BAD = {"detail": "メールアドレスまたはパスワードが違います"}
LOCKED = {"detail": "ログインの試行が多すぎます。しばらくしてからもう一度お試しください"}
WRONG = "wrong-password-1"
UNKNOWN = {"email": "nobody-at-all@example.com", "password": "star-garden-demo"}


@pytest.fixture
def fresh_attempts():
    """試行の表を空にして始め、終わりにも空にする（ほかのテストのログインに、数えが残らないように）。"""
    db_exec("DELETE FROM garden_login_attempts")
    yield
    db_exec("DELETE FROM garden_login_attempts")


def attempt(client, email: str, password: str):
    return client.post("/api/garden/auth/login", json={"email": email, "password": password})


def attempt_row(email: str):
    """(失敗の数, 窓の始まりからの経過秒) か、行が無ければ None。"""
    rows = db_exec(
        "SELECT failures, extract(epoch FROM now() - window_start) FROM garden_login_attempts WHERE email_hash = %s",
        (hashlib.sha256(email.strip().lower().encode()).hexdigest(),),
    )
    return rows[0] if rows else None


def set_window_age(email: str, interval: str) -> None:
    db_exec(
        "UPDATE garden_login_attempts SET window_start = now() - %s::interval WHERE email_hash = %s",
        (interval, hashlib.sha256(email.encode()).hexdigest()),
    )


def count_sessions() -> int:
    return db_exec("SELECT count(*) FROM garden_sessions")[0][0]


@pytest.mark.usefixtures("fresh_attempts")
def test_login_is_rejected_at_the_limit_even_with_the_right_password(client):
    for _ in range(5):
        res = attempt(client, GARDEN["email"], WRONG)
        assert (res.status_code, res.json()) == (401, BAD)
    sessions = count_sessions()
    for password in (WRONG, GARDEN["password"]):  # 上限のあとは、正しいパスワードでも同じ
        res = attempt(client, GARDEN["email"], password)
        assert (res.status_code, res.json()) == (429, LOCKED)
    assert count_sessions() == sessions  # セッションは発行されない
    assert attempt_row(GARDEN["email"])[0] == 6  # 数えは上限 + 1 で頭打ち（上限を超えても増え続けない）
    assert attempt(client, GARDEN["email"], WRONG).status_code == 429
    assert attempt_row(GARDEN["email"])[0] == 6


@pytest.mark.usefixtures("fresh_attempts")
def test_the_last_allowed_attempt_can_still_succeed(client):
    for _ in range(4):
        assert attempt(client, GARDEN["email"], WRONG).status_code == 401
    assert attempt(client, GARDEN["email"], GARDEN["password"]).status_code == 200  # 5 回目は上限の内


@pytest.mark.usefixtures("fresh_attempts")
def test_locked_login_returns_after_the_window(client):
    for _ in range(5):
        attempt(client, GARDEN["email"], WRONG)
    assert attempt(client, GARDEN["email"], GARDEN["password"]).status_code == 429
    set_window_age(GARDEN["email"], "14 minutes")  # 窓（15 分）の中: まだ拒否
    assert attempt(client, GARDEN["email"], GARDEN["password"]).status_code == 429
    set_window_age(GARDEN["email"], "15 minutes 1 second")  # 窓を過ぎた: 戻る
    res = attempt(client, GARDEN["email"], GARDEN["password"])
    assert res.status_code == 200 and res.json()["garden"]["email"] == GARDEN["email"]
    assert attempt_row(GARDEN["email"]) is None


@pytest.mark.usefixtures("fresh_attempts")
def test_a_wrong_password_after_the_window_starts_a_new_count(client):
    for _ in range(5):
        attempt(client, GARDEN["email"], WRONG)
    set_window_age(GARDEN["email"], "16 minutes")
    assert attempt(client, GARDEN["email"], WRONG).status_code == 401
    failures, age = attempt_row(GARDEN["email"])
    assert failures == 1 and age < 60  # 数え直し。窓の始まりも新しい
    for _ in range(4):
        assert attempt(client, GARDEN["email"], WRONG).status_code == 401  # 数え直した 5 回までは、また通る
    assert attempt(client, GARDEN["email"], WRONG).status_code == 429


@pytest.mark.usefixtures("fresh_attempts")
def test_success_clears_the_failures(client):
    for _ in range(4):
        assert attempt(client, GARDEN["email"], WRONG).status_code == 401
    assert attempt_row(GARDEN["email"])[0] == 4
    assert attempt(client, GARDEN["email"], GARDEN["password"]).status_code == 200
    assert attempt_row(GARDEN["email"]) is None
    for _ in range(4):  # 成功で数え直しになったので、また 4 回失敗しても、拒否されない
        assert attempt(client, GARDEN["email"], WRONG).status_code == 401
    assert attempt_row(GARDEN["email"])[0] == 4


@pytest.mark.usefixtures("fresh_attempts")
def test_another_email_is_not_affected(client):
    for _ in range(6):
        attempt(client, GARDEN["email"], WRONG)
    assert attempt(client, GARDEN["email"], GARDEN["password"]).status_code == 429
    assert attempt(client, GARDEN2["email"], GARDEN2["password"]).status_code == 200  # 別の園は、そのまま入れる
    res = attempt(client, UNKNOWN["email"], UNKNOWN["password"])
    assert (res.status_code, res.json()) == (401, BAD)  # 登録の無いメールも、ふつうの失敗（上限の拒否にはならない）
    assert attempt_row(GARDEN2["email"]) is None and attempt_row(UNKNOWN["email"])[0] == 1


@pytest.mark.usefixtures("fresh_attempts")
def test_emails_are_counted_by_their_normalized_hash_and_never_stored_in_plain_text(client):
    variants = [GARDEN["email"], " Hoshiniwa-Garden@Example.com", "HOSHINIWA-GARDEN@EXAMPLE.COM "]
    for email in variants:
        assert attempt(client, email, WRONG).status_code == 401
    assert attempt_row(GARDEN["email"])[0] == 3  # 大文字小文字・前後の空白が違っても、同じ 1 行に数える
    rows = db_exec("SELECT email_hash FROM garden_login_attempts")
    assert [r[0] for r in rows] == [hashlib.sha256(GARDEN["email"].encode()).hexdigest()]
    whole_table = " ".join(r[0] for r in db_exec("SELECT a::text FROM garden_login_attempts a"))
    assert "hoshiniwa" not in whole_table.lower() and "example.com" not in whole_table.lower() and "@" not in whole_table
    # 登録の無いメールも、同じ形（ハッシュだけ）で数える
    attempt(client, UNKNOWN["email"], WRONG)
    assert "nobody" not in " ".join(r[0] for r in db_exec("SELECT a::text FROM garden_login_attempts a"))


@pytest.mark.usefixtures("fresh_attempts")
def test_an_unknown_email_gets_the_same_responses_as_a_registered_one(client, monkeypatch):
    checked: list[str] = []
    real_verify = garden.verify_password

    def spy(stored_hash: str, password: str) -> bool:
        checked.append(stored_hash)
        return real_verify(stored_hash, password)

    monkeypatch.setattr(garden, "verify_password", spy)
    outcomes = {}
    for label, email in (("registered", GARDEN["email"]), ("unknown", UNKNOWN["email"])):
        before = len(checked)
        responses = [attempt(client, email, WRONG) for _ in range(5)]
        assert len(checked) - before == 5  # 上限の内は、登録の有無にかかわらず、パスワードの検証を通る（無いときは DUMMY_HASH）
        locked = [attempt(client, email, WRONG), attempt(client, email, GARDEN["password"])]
        assert len(checked) - before == 5  # 上限のあとは、どちらも検証せずに拒否する
        outcomes[label] = [(r.status_code, r.json()) for r in responses + locked]
    assert outcomes["registered"] == outcomes["unknown"] == [(401, BAD)] * 5 + [(429, LOCKED)] * 2
    assert DUMMY_HASH in checked and DUMMY_HASH not in checked[:5]


@pytest.mark.usefixtures("fresh_attempts")
def test_old_rows_are_swept_at_login(client):
    old, middle, recent = ("old@example.com", "middle@example.com", "recent@example.com")
    for email, failures in ((old, 5), (middle, 5), (recent, 2)):
        db_exec(
            "INSERT INTO garden_login_attempts (email_hash, failures) VALUES (%s, %s)",
            (hashlib.sha256(email.encode()).hexdigest(), failures),
        )
    set_window_age(old, "31 minutes")  # 窓（15 分）の 2 倍（30 分）より古い: 掃除される
    set_window_age(middle, "20 minutes")  # 窓は過ぎたが 2 倍より新しい: 残る（そのメールが次に来たとき、数え直される）
    set_window_age(recent, "1 minute")
    assert attempt(client, UNKNOWN["email"], WRONG).status_code == 401
    assert attempt_row(old) is None
    assert attempt_row(middle) is not None and attempt_row(recent) is not None


@pytest.mark.usefixtures("fresh_attempts")
def test_limit_and_window_come_from_settings(client, monkeypatch):
    monkeypatch.setenv("GARDEN_LOGIN_MAX_FAILURES", "2")
    monkeypatch.setenv("GARDEN_LOGIN_WINDOW_MINUTES", "1")
    for _ in range(2):
        assert attempt(client, GARDEN["email"], WRONG).status_code == 401
    assert attempt(client, GARDEN["email"], GARDEN["password"]).status_code == 429
    set_window_age(GARDEN["email"], "61 seconds")  # 窓は 1 分
    assert attempt(client, GARDEN["email"], GARDEN["password"]).status_code == 200


@pytest.mark.usefixtures("fresh_attempts")
def test_parallel_attempts_do_not_exceed_the_limit(client, monkeypatch):
    checked: list[str] = []
    real_verify = garden.verify_password

    def spy(stored_hash: str, password: str) -> bool:
        checked.append(stored_hash)
        return real_verify(stored_hash, password)

    monkeypatch.setattr(garden, "verify_password", spy)
    with ThreadPoolExecutor(max_workers=12) as pool:
        codes = sorted(pool.map(lambda _: attempt(client, GARDEN["email"], WRONG).status_code, range(12)))
    assert codes == [401] * 5 + [429] * 7  # 同時に送っても、パスワードを確かめるのは上限の回数まで
    assert len(checked) == 5
