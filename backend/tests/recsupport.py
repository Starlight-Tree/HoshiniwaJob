"""閲覧の記録・関連する求人・おすすめ（recruit_events.py）と、埋め込み（recruit_embeddings.py）のテストの共通部品。

ここにある oracle_* は、アプリの SQL とは別の書き方（Python の集合）で、同じ規則の「正しい答え」を出す。
重み（3 と 5）は、アプリの定数を使わず、数をそのまま書く（アプリの定数を変えたときに、テストが一緒に動かないように）。
"""

import math

import psycopg
import pytest

from tests.conftest import TEST_URL
from tests.jwt_tokens import make_token
from tests.test_garden import db_exec


def db_url() -> str:
    return TEST_URL.rsplit("/", 1)[0] + "/hj_test"


@pytest.fixture(autouse=True)
def clean_rec_state(client):
    """このテストが足した閲覧・埋め込み・利用者・画像を、前後で消す（共有のテスト用 DB を、ほかのテストに残さない）。"""
    wipe()
    yield
    wipe()


def wipe() -> None:
    for sql in (
        "DELETE FROM recruits WHERE corporate = '消す法人'",  # test_recruit_events の、消えることの確認用
        "DELETE FROM recruit_embeddings",
        "DELETE FROM recruit_events",
        "DELETE FROM users WHERE auth_user_id LIKE 'ba_rec_%%'",
        "DELETE FROM auth_user WHERE id LIKE 'ba_rec_%%'",
        "DELETE FROM recruit_images",
        "DELETE FROM garden_images",
        "DELETE FROM images",
    ):
        db_exec(sql)


@pytest.fixture
def make_user(auth_env, client):
    """番号 n の求職者を作り、(users.id, Authorization ヘッダー) を返す。Better Auth の代わりに、テスト用の鍵で JWT を作る。"""

    def make(n: int) -> tuple[int, dict[str, str]]:
        sub = f"ba_rec_u{n:03d}"
        db_exec(
            'INSERT INTO auth_user ("id", "name", "email", "emailVerified") VALUES (%s, %s, %s, true) ON CONFLICT ("id") DO NOTHING',
            (sub, sub, f"{sub}@auth.test"),
        )
        headers = {"Authorization": "Bearer " + make_token(sub=sub, email=f"{sub}@rec.test", name=f"記録{n}")}
        res = client.get("/api/auth/me", headers=headers)
        assert res.status_code == 200
        return res.json()["id"], headers

    return make


def add_events(rows: list[tuple[int, int]], minutes_ago: int = 0) -> None:
    """(利用者 ID, 求人 ID) の閲覧を、直接 DB に足す（API は、非表示の求人や過去の時刻を受けないため）。"""
    with psycopg.connect(db_url(), autocommit=True) as conn:
        conn.cursor().executemany(
            "INSERT INTO recruit_events (user_id, recruit_id, event_type, created_at) VALUES (%s, %s, 'view', now() - make_interval(mins => %s))",
            [(user_id, recruit_id, minutes_ago) for user_id, recruit_id in rows],
        )


def event_count(user_id: int | None = None, recruit_id: int | None = None) -> int:
    return db_exec(
        "SELECT count(*) FROM recruit_events WHERE (%(u)s::int IS NULL OR user_id = %(u)s) AND (%(r)s::int IS NULL OR recruit_id = %(r)s)",
        {"u": user_id, "r": recruit_id},
    )[0][0]


def ids(items: list[dict]) -> list[int]:
    return [i["id"] for i in items]


# ===== oracle（正しい答え）=====


def _catalog() -> dict[int, dict]:
    rows = db_exec("SELECT id, is_displayed, employment_codes, area_codes, occupation_codes FROM recruit_search")
    return {r[0]: {"shown": r[1], "kinds": (set(r[2]), set(r[3]), set(r[4]))} for r in rows}


def _viewers() -> dict[int, set[int]]:
    who: dict[int, set[int]] = {}
    for recruit_id, user_id in db_exec("SELECT DISTINCT recruit_id, user_id FROM recruit_events WHERE event_type = 'view'"):
        who.setdefault(recruit_id, set()).add(user_id)
    return who


def _matches(catalog: dict[int, dict], a: int, b: int) -> int:
    return sum(len(x & y) for x, y in zip(catalog[a]["kinds"], catalog[b]["kinds"], strict=True))


def _cosine(a: tuple[str, list[float]], b: tuple[str, list[float]]) -> float:
    (model_a, va), (model_b, vb) = a, b
    if model_a != model_b or len(va) != len(vb):
        return 0.0
    na, nb = math.sqrt(sum(x * x for x in va)), math.sqrt(sum(x * x for x in vb))
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, sum(x * y for x, y in zip(va, vb, strict=True)) / (na * nb))


def _similarity(vectors: dict, a: int, b: int) -> float:
    return _cosine(vectors[a], vectors[b]) if a in vectors and b in vectors else 0.0


def snapshot() -> tuple[dict[int, dict], dict[int, set[int]]]:
    """求人の条件と、求人ごとの閲覧者の集合（oracle に渡して、何度も DB を読まないため）。"""
    return _catalog(), _viewers()


def oracle_related(recruit_id: int, limit: int, vectors: dict | None = None, snap=None) -> list[int]:
    """共起（両方を見た利用者の数）の多い順 → 条件の一致（+ 類似度 × 5）の多い順 → ID 昇順。表示中の、自分以外の求人。"""
    vectors = vectors or {}
    catalog, who = snap or snapshot()
    keyed = []
    for c, info in catalog.items():
        if c == recruit_id or not info["shown"]:
            continue
        cooc = len(who.get(recruit_id, set()) & who.get(c, set()))
        cond = _matches(catalog, recruit_id, c) + 5 * _similarity(vectors, recruit_id, c)
        keyed.append((-cooc, -round(cond, 9), c))
    return [c for _, _, c in sorted(keyed)[:limit]]


def oracle_recommendations(user_id: int, limit: int, vectors: dict | None = None, snap=None) -> list[int]:
    """得点 = 見た求人との共起の合計 × 3 + 条件の一致の合計（+ 類似度の合計 × 5）。見ていない・表示中だけ。得点 0 は出さない。同点は ID 昇順。"""
    vectors = vectors or {}
    catalog, who = snap or snapshot()
    seen = {r for r, users in who.items() if user_id in users}
    scored = []
    for c, info in catalog.items():
        if c in seen or not info["shown"]:
            continue
        cooc = sum(len(who[v] & who.get(c, set())) for v in seen)
        cond = sum(_matches(catalog, v, c) + 5 * _similarity(vectors, v, c) for v in seen)
        score = round(cooc * 3 + cond, 9)
        if score > 0:
            scored.append((-score, c))
    return [c for _, c in sorted(scored)[:limit]]
