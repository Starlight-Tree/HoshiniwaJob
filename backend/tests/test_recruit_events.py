"""閲覧の記録・関連する求人・おすすめ（app/recruit_events.py）。埋め込み（意味の近さ）を使う分は test_recruit_embeddings.py。

テスト用 DB のダミーの求人（seed_demo）を使う。ID 1〜11 は表示中、12 は非表示。条件（雇用形態・エリア・職種）は次のとおり:
  1: 常勤・第一環(3)・職 1     2: 常勤・第二環(4)・職 2     3: 短時間・北縁(8)・職 9     4: 常勤・中央(9,10)・職 11
  5: 常勤・砂丘(12)・職 6      6: 季節・砂丘(12)・職 12     7: 短時間・岩山(13)・遺跡前(14)・職 10   8: 派遣・遺跡前(14)・職 19
  9: 季節・第一環(3)・第二環(4)・職 17   10: 常勤・第二環(4)・職 16   11: 短時間・根元(6)・職 25   12（非表示）: 常勤・翠環(1)・職 7
求人 10 を基準にした条件の一致の数: 2 は 2（常勤・第二環）、1・4・5・9 は 1、3・6・7・8・11 は 0。
"""

import random
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
from psycopg.rows import dict_row

from app.schemas import RecruitSummary
from tests.conftest import TEST_URL
from tests.imagefiles import make_image
from tests.recsupport import (  # noqa: F401（clean_rec_state は自動で使われる）
    add_events,
    clean_rec_state,
    db_url,
    event_count,
    ids,
    make_user,
    oracle_recommendations,
    oracle_related,
    snapshot,
)
from tests.test_garden import GARDEN, GARDEN2, db_exec, garden_login
from tests.test_images_api import upload

pytestmark = pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL が未設定です")

NOT_LOGGED_IN = {"detail": "ログインしてください"}
NOT_FOUND = {"detail": "求人が見つかりません"}
HIDDEN = 12
TARGET = 10  # 関連・おすすめの基準にする求人（上の表）


def view(client, recruit_id, headers=None):
    return client.post(f"/api/recruits/{recruit_id}/view", headers=headers)


def related(client, recruit_id, **params):
    res = client.get(f"/api/recruits/{recruit_id}/related", params=params)
    assert res.status_code == 200
    return res.json()


def recommendations(client, headers, **params):
    res = client.get("/api/recommendations", params=params, headers=headers)
    assert res.status_code == 200
    return res.json()


@pytest.fixture
def sql_log(monkeypatch):
    """流れた SQL の文を、すべて残す（求人の件数に比例して SQL が増えないことの確認）。"""
    seen: list[str] = []
    original = psycopg.Cursor.execute

    def counting(self, query, *args, **kwargs):
        if isinstance(query, str):
            seen.append(query)
        return original(self, query, *args, **kwargs)

    monkeypatch.setattr(psycopg.Cursor, "execute", counting)
    return seen


# ===== 閲覧の記録 =====


def test_view_requires_login_before_anything_else(client, make_user):
    for headers in (None, {"Authorization": "Bearer"}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer not-a-jwt"}):
        res = view(client, 1, headers)
        assert res.status_code == 401 and res.json() == NOT_LOGGED_IN
    assert view(client, 9999).status_code == 401  # 存在しない求人でも、先に 401（求人の有無を、ログインしていない人に教えない）
    assert event_count() == 0


def test_view_of_missing_or_hidden_recruit_is_404_and_records_nothing(client, make_user):
    _, headers = make_user(1)
    for recruit_id in (9999, 99999999999, HIDDEN):
        res = view(client, recruit_id, headers)
        assert res.status_code == 404 and res.json() == NOT_FOUND
    assert event_count() == 0


def test_view_records_one_event_for_the_logged_in_user_and_returns_204(client, make_user):
    user_id, headers = make_user(1)
    res = view(client, 3, headers)
    assert res.status_code == 204 and res.content == b""
    rows = db_exec("SELECT user_id, recruit_id, event_type, created_at IS NOT NULL FROM recruit_events")
    assert rows == [(user_id, 3, "view", True)]


def test_view_within_30_minutes_is_not_added_again_but_still_204(client, make_user):
    user_id, headers = make_user(1)
    assert view(client, 3, headers).status_code == 204
    assert view(client, 3, headers).status_code == 204
    assert event_count(user_id, 3) == 1
    db_exec("UPDATE recruit_events SET created_at = now() - interval '29 minutes'")  # まだ 30 分以内
    assert view(client, 3, headers).status_code == 204
    assert event_count(user_id, 3) == 1


def test_view_after_30_minutes_is_added_again(client, make_user):
    user_id, headers = make_user(1)
    view(client, 3, headers)
    db_exec("UPDATE recruit_events SET created_at = now() - interval '31 minutes'")
    assert view(client, 3, headers).status_code == 204
    assert event_count(user_id, 3) == 2
    assert view(client, 3, headers).status_code == 204  # 直前に足したので、また重複
    assert event_count(user_id, 3) == 2


def test_dedup_is_per_user_and_per_recruit(client, make_user):
    a, ha = make_user(1)
    b, hb = make_user(2)
    for headers, recruit_id in ((ha, 3), (hb, 3), (ha, 4)):
        assert view(client, recruit_id, headers).status_code == 204
    assert event_count(a, 3) == event_count(b, 3) == event_count(a, 4) == 1 and event_count() == 3


def test_simultaneous_views_of_the_same_recruit_record_one_event(client, make_user):
    user_id, headers = make_user(1)
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda _: view(client, 2, headers).status_code, range(8)))
    assert codes == [204] * 8
    assert event_count(user_id, 2) == 1


def test_events_are_removed_with_their_user_or_recruit_and_only_view_is_allowed(client, make_user):
    a, _ = make_user(1)
    b, _ = make_user(2)
    db_exec("INSERT INTO recruits (category, corporate, is_displayed) VALUES ('消す求人', '消す法人', true)")
    gone = db_exec("SELECT id FROM recruits WHERE category = '消す求人'")[0][0]
    add_events([(a, 1), (b, 1), (a, gone), (b, gone)])
    db_exec("DELETE FROM users WHERE id = %s", (a,))
    assert event_count(a) == 0 and event_count(b) == 2  # 利用者を消すと、その人の記録だけが消える
    db_exec("DELETE FROM recruits WHERE id = %s", (gone,))
    assert event_count(b, gone) == 0 and event_count(b, 1) == 1  # 求人を消すと、その求人の記録だけが消える
    with pytest.raises(psycopg.errors.CheckViolation):
        db_exec("INSERT INTO recruit_events (user_id, recruit_id, event_type) VALUES (%s, 1, 'click')", (b,))


# ===== 関連する求人 =====

# 利用者 1・2 が 10 と 11 を、利用者 3 が 10 と 7 を見た（1 は 10 と 11 を 2 回ずつ、3 は 10 と 7 を 3 回ずつ）。非表示の 12 は、10 と一緒に 3 人が見た。7 と 3 は、10 を見ていない利用者 4 も見た
def scenario_related(make_user):
    u = {n: make_user(n)[0] for n in (1, 2, 3, 4)}
    add_events([(u[1], 10), (u[1], 11), (u[2], 10), (u[2], 11), (u[3], 10), (u[3], 7), (u[4], 7), (u[4], 3)] + [(u[n], HIDDEN) for n in (1, 2, 3)])
    add_events([(u[1], 10), (u[1], 11)], minutes_ago=120)  # 1 は 2 時間前にも見た（利用者の数で数えるので、共起は増えない）
    add_events([(u[3], 10), (u[3], 7)], minutes_ago=180)  # 3 は 7 を何度も見た: 閲覧の組の回数なら 7 のほうが多く（9）、利用者の数なら 11（2 人）のほうが多い
    add_events([(u[3], 10), (u[3], 7)], minutes_ago=240)
    return u


def test_related_puts_co_viewed_recruits_before_condition_matches(client, make_user):
    scenario_related(make_user)
    # 共起: 11（2 人）→ 7（1 人）。条件が 1 つも合わない 11・7 が、条件が 2 つ合う 2 より前に来る。以降は条件の一致が多い順（2 → 1・4・5・9 → 0 のもの）、同じなら ID 順
    assert ids(related(client, TARGET, limit=12)) == [11, 7, 2, 1, 4, 5, 9, 3, 6, 8]


def test_related_never_includes_itself_or_hidden_recruits(client, make_user):
    scenario_related(make_user)
    everything = ids(related(client, TARGET, limit=12))
    assert TARGET not in everything and HIDDEN not in everything  # 非表示の 12 は、10 と 3 人が一緒に見ていても出ない
    assert len(everything) == 10  # 表示中 11 件から自分を除いた分。共起も条件の一致も 0 のものも、後ろに入る
    assert 1 not in ids(related(client, 1, limit=12))


def test_related_limit(client, make_user):
    scenario_related(make_user)
    assert ids(related(client, TARGET)) == [11, 7, 2, 1]  # 既定は 4
    assert ids(related(client, TARGET, limit=1)) == [11]
    assert ids(related(client, TARGET, limit=12)) == [11, 7, 2, 1, 4, 5, 9, 3, 6, 8]
    for bad in (0, 13, -1):
        assert client.get(f"/api/recruits/{TARGET}/related", params={"limit": bad}).status_code == 422


def test_related_without_any_views_is_ordered_by_condition_matches_then_id(client):
    assert ids(related(client, TARGET, limit=12)) == [2, 1, 4, 5, 9, 3, 6, 7, 8, 11]


def test_related_is_public_and_missing_or_hidden_recruit_is_404(client):
    assert client.get(f"/api/recruits/{TARGET}/related").status_code == 200  # 認証なし
    for recruit_id in (9999, HIDDEN):
        res = client.get(f"/api/recruits/{recruit_id}/related")
        assert res.status_code == 404 and res.json() == NOT_FOUND


def test_related_has_the_same_shape_as_the_list_and_carries_hero_images(client, make_user):
    scenario_related(make_user)
    upload(client, garden_login(client, GARDEN), 2, data=make_image(seed=2), alt="二")
    upload(client, garden_login(client, GARDEN2), 4, data=make_image(seed=4), alt="四")
    listing = {i["id"]: i for i in client.get("/api/recruits", params={"per_page": 50}).json()["items"]}
    items = related(client, TARGET, limit=12)
    for item in items:
        assert item == listing[item["id"]]  # 一覧と同じ形・同じ値（hero_image 込み）
    heroes = {i["id"]: i["hero_image"] for i in items}
    assert heroes[2]["alt"] == "二" and heroes[4]["alt"] == "四"
    assert heroes[2] == client.get("/api/recruits/2").json()["hero_image"]
    assert [k for k, v in heroes.items() if v is None] == [11, 7, 1, 5, 9, 3, 6, 8]  # 画像を足していない求人は null


def test_related_sql_does_not_grow_with_the_number_of_recruits(client, make_user, sql_log):
    scenario_related(make_user)
    upload(client, garden_login(client, GARDEN), 2, data=make_image(seed=2))
    counts = {}
    for limit in (1, 4, 12):
        sql_log.clear()
        assert len(related(client, TARGET, limit=limit)) == min(limit, 10)
        counts[limit] = (len(sql_log), sum("recruit_images" in q for q in sql_log))
    assert counts[1] == counts[4] == counts[12]
    total, image_queries = counts[12]
    assert image_queries == 1 and total <= 6  # 画像は 1 回でまとめて引く。全体も、求人 10 件に対して 10 回以上にはならない


def test_ranking_functions_expose_the_numbers_behind_the_order(client, make_user):
    """順位の理由（共起の数・条件の一致の数・得点）を、関数の戻り値で確かめる。同じ人の繰り返しの閲覧は、共起を増やさない。"""
    from app.recruit_events import rank_recommendations, rank_related

    u = scenario_related(make_user)
    with psycopg.connect(db_url(), row_factory=dict_row) as conn:
        rel = rank_related(conn, TARGET, 12)
        recs = rank_recommendations(conn, u[3], 12)
    # 関連（基準は 10）: (共起, 条件の一致, 類似度)。11 は利用者 1・2 の 2 人。7 は利用者 3 の 1 人（3 回ずつ見ていても 1）
    assert {r.recruit_id: (r.cooc, r.matches, r.similarity) for r in rel} == {
        11: (2, 0, 0.0), 7: (1, 0, 0.0), 2: (0, 2, 0.0), 1: (0, 1, 0.0), 4: (0, 1, 0.0), 5: (0, 1, 0.0), 9: (0, 1, 0.0), 3: (0, 0, 0.0), 6: (0, 0, 0.0), 8: (0, 0, 0.0),
    }
    # おすすめ（利用者 3 は 10・7・12 を見た。12 は今は非表示でも、見た求人には数える）: (共起の合計, 条件の一致の合計, 得点 = 共起 × 3 + 一致)
    # 11: 共起は 10 と 2 人 + 12 と 2 人 = 4、一致は 7 と短時間勤務で 1 → 13。3: 共起は 7 と利用者 4 の 1 人、一致は 7 と短時間勤務で 1 → 4。6 は 0 点で出ない
    assert {r.recruit_id: (r.cooc, r.matches, r.score) for r in recs} == {
        11: (4, 1, 13.0), 3: (1, 1, 4.0), 2: (0, 3, 3.0), 1: (0, 2, 2.0), 4: (0, 2, 2.0), 5: (0, 2, 2.0), 8: (0, 1, 1.0), 9: (0, 1, 1.0),
    }
    assert [r.recruit_id for r in recs] == [11, 3, 2, 1, 4, 5, 8, 9]


# ===== おすすめ =====


def test_recommendations_require_login(auth_env, client):
    for headers in (None, {"Authorization": "Bearer"}, {"Authorization": "Bearer not-a-jwt"}):
        res = client.get("/api/recommendations", headers=headers)
        assert res.status_code == 401 and res.json() == NOT_LOGGED_IN


def test_recommendations_are_empty_without_history(client, make_user):
    _, headers = make_user(1)
    assert recommendations(client, headers) == []
    other, _ = make_user(2)
    add_events([(other, TARGET), (other, 7)])  # ほかの人の履歴があっても、履歴の無い人には出さない
    assert recommendations(client, headers) == []


# 利用者 1 が 10 だけを見た。利用者 2 は 10 と 7 を、利用者 3・4・5 は 10 と非表示の 12 を見た
def scenario_recommendations(make_user):
    u = {n: make_user(n) for n in (1, 2, 3, 4, 5)}
    add_events([(u[1][0], 10), (u[2][0], 10), (u[2][0], 7)] + [(u[n][0], pair) for n in (3, 4, 5) for pair in (10, HIDDEN)])
    add_events([(u[2][0], 10), (u[2][0], 7)], minutes_ago=120)  # 利用者 2 は、10 と 7 を 3 回ずつ見た（共起は、人数で 1 のまま）
    add_events([(u[2][0], 10), (u[2][0], 7)], minutes_ago=240)
    return u


def test_recommendations_follow_the_score_formula(client, make_user):
    u = scenario_recommendations(make_user)
    # 7: 共起 1 × 3 = 3。2: 条件 2（常勤・第二環）。1・4・5・9: 条件 1。3・6・8・11: 0 で出ない。
    # 重みが 3 倍なので、条件が 2 つ合う 2 より、共起が 1 つの 7 が上（重みが 1 なら、2 が上になる）
    assert ids(recommendations(client, u[1][1])) == [7, 2, 1, 4, 5, 9]


def test_recommendations_exclude_seen_hidden_and_zero_score(client, make_user):
    u = scenario_recommendations(make_user)
    shown = ids(recommendations(client, u[1][1], limit=12))
    assert TARGET not in shown  # 見た求人（自分に当てはまる条件が 3 つで、除かなければ首位に近い）
    assert HIDDEN not in shown  # 非表示（10 と 3 人が一緒に見ていて、除かなければ首位）
    assert not {3, 6, 8, 11} & set(shown)  # 得点 0
    add_events([(u[1][0], 7)])  # 7 を見たら、おすすめから消える
    assert 7 not in ids(recommendations(client, u[1][1], limit=12))


def test_recommendations_limit(client, make_user):
    u = scenario_recommendations(make_user)
    assert ids(recommendations(client, u[1][1], limit=2)) == [7, 2]
    assert ids(recommendations(client, u[1][1], limit=12)) == [7, 2, 1, 4, 5, 9]  # 得点のある分だけ
    for bad in (0, 13):
        assert client.get("/api/recommendations", params={"limit": bad}, headers=u[1][1]).status_code == 422


def test_recommendations_sum_over_every_viewed_recruit(client, make_user):
    # 10 と 1 を見た人。2 は 10 と 2 点、1 と 1 点（常勤）。共起: 利用者 2 が (10, 2) を、利用者 3 が (1, 2) と (10, 2) を見た
    me_id, me_headers = make_user(1)
    other_a, _ = make_user(2)
    other_b, _ = make_user(3)
    add_events([(me_id, 10), (me_id, 1), (other_a, 10), (other_a, 2), (other_b, 1), (other_b, 2), (other_b, 10)])
    # 2 の共起: 10 とは 2 人（利用者 2・3）、1 とは 1 人（利用者 3）→ 3 × 3 = 9。条件: 10 と 2、1 と 1 → 3。得点 12
    # 4: 条件 10 と 1、1 と 1 → 2（共起なし）。5: 同じく 2。9: 10 と 1（第二環）、1 と 1（第一環）→ 2。3・6・7・8・11 は 0
    assert ids(recommendations(client, me_headers, limit=12)) == [2, 4, 5, 9]
    assert oracle_recommendations(me_id, 12) == [2, 4, 5, 9]


@pytest.mark.parametrize("seed", [1, 2])  # 1 回が 10 秒ほどかかる（DB の JIT で、一覧と同じ種類の SQL が 1 回 0.2 秒前後）。増やすなら、ここ
def test_random_histories_match_an_independent_implementation(client, make_user, seed):
    rng = random.Random(seed)
    users = [make_user(n) for n in range(1, 7)]
    for user_id, _ in users:
        picked = rng.sample(range(1, 13), rng.randint(0, 6))  # 非表示の 12 も含む（直接足す）
        for recruit_id in picked:
            add_events([(user_id, recruit_id)], minutes_ago=rng.choice([0, 0, 45, 300]))
        add_events([(user_id, recruit_id) for recruit_id in picked if rng.random() < 0.3], minutes_ago=600)  # 30 分以上空けた再閲覧（利用者の数は増えない）
    snap = snapshot()
    for recruit_id in range(1, 12):
        assert ids(related(client, recruit_id, limit=12)) == oracle_related(recruit_id, 12, snap=snap), f"related {recruit_id}"
    assert ids(related(client, TARGET, limit=3)) == oracle_related(TARGET, 3, snap=snap)
    for user_id, headers in users:
        assert ids(recommendations(client, headers, limit=12)) == oracle_recommendations(user_id, 12, snap=snap), f"user {user_id}"
    assert ids(recommendations(client, users[0][1], limit=2)) == oracle_recommendations(users[0][0], 2, snap=snap)


def test_recommendations_sql_does_not_grow_with_the_number_of_recruits(client, make_user, sql_log):
    u = scenario_recommendations(make_user)
    upload(client, garden_login(client, GARDEN), 2, data=make_image(seed=2))
    counts = {}
    for limit in (1, 12):
        sql_log.clear()
        assert len(recommendations(client, u[1][1], limit=limit)) == (1 if limit == 1 else 6)
        counts[limit] = (len(sql_log), sum("recruit_images" in q for q in sql_log))
    assert counts[1] == counts[12] and counts[12][1] == 1 and counts[12][0] <= 12  # 認証の分を含む。求人 6 件に対して 6 回以上は増えない


def test_recommendations_carry_hero_images(client, make_user):
    u = scenario_recommendations(make_user)
    upload(client, garden_login(client, GARDEN), 2, data=make_image(seed=2), alt="二")
    items = recommendations(client, u[1][1])
    assert items[1]["id"] == 2 and items[1]["hero_image"]["alt"] == "二" and items[0]["hero_image"] is None
    assert set(items[0]) == set(RecruitSummary.model_fields)
