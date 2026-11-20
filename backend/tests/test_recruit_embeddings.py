"""埋め込み（意味の近さ）の差し込み口（app/recruit_embeddings.py）と、関連する求人・おすすめの得点への足し込み（app/recruit_events.py）。

ベクトルは、人工の短いもの（実 API は使わない）。求人の条件と ID は、test_recruit_events.py の冒頭の表のとおり。
求人 10 を基準にしたとき、埋め込みが無ければ関連は [2, 1, 4, 5, 9, 3, 6, 7, 8, 11]（条件の一致の多い順）。
"""

import math
import random

import psycopg
import pytest
from psycopg.rows import dict_row

from app.recruit_embeddings import Embedding, cosine, load_embeddings, set_embedding, similarity_sums
from tests.conftest import TEST_URL
from tests.recsupport import (  # noqa: F401（clean_rec_state は自動で使われる）
    add_events,
    clean_rec_state,
    db_url,
    ids,
    make_user,
    oracle_recommendations,
    oracle_related,
    snapshot,
)
from tests.test_garden import db_exec
from tests.test_recruit_events import HIDDEN, TARGET, recommendations, related, sql_log  # noqa: F401（sql_log は fixture）

pytestmark = pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL が未設定です")

MODEL = "test-model"
BASELINE_RELATED = [2, 1, 4, 5, 9, 3, 6, 7, 8, 11]  # 求人 10 の関連（閲覧も埋め込みも無いとき）
BASELINE_RECOMMENDED = [2, 1, 4, 5, 9]  # 求人 10 だけを見た人のおすすめ（閲覧も埋め込みも無いとき）


def put(recruit_id: int, vector, model: str = MODEL) -> None:
    with psycopg.connect(db_url(), autocommit=True, row_factory=dict_row) as conn:
        set_embedding(conn, recruit_id, model, vector)


def put_all(vectors: dict[int, list[float]], model: str = MODEL) -> None:
    for recruit_id, vector in vectors.items():
        put(recruit_id, vector, model)


# ===== 近さ（コサイン類似度）=====


def test_cosine_is_between_0_and_1_and_zero_when_not_comparable():
    a = Embedding(MODEL, (1.0, 0.0))
    assert cosine(a, a) == pytest.approx(1.0)
    assert cosine(a, Embedding(MODEL, (2.0, 0.0))) == pytest.approx(1.0)  # 向きだけを見る
    assert cosine(a, Embedding(MODEL, (1.0, 1.0))) == pytest.approx(math.sqrt(0.5))
    assert cosine(a, Embedding(MODEL, (0.0, 1.0))) == 0.0
    assert cosine(a, Embedding(MODEL, (-1.0, 0.0))) == 0.0  # 負（反対向き）は 0 に切る
    assert cosine(a, Embedding(MODEL, (1.0, 0.0, 0.0))) == 0.0  # 次元が違う
    assert cosine(a, Embedding("other-model", (1.0, 0.0))) == 0.0  # モデルが違う
    assert cosine(a, Embedding(MODEL, (0.0, 0.0))) == 0.0  # 長さが 0


# ===== 値を入れる関数 =====


def test_set_embedding_inserts_then_replaces():
    put(3, [1, 2, 3])  # 整数でもよい（float で入る）
    first = db_exec("SELECT model, vector, updated_at FROM recruit_embeddings WHERE recruit_id = 3")
    assert first[0][:2] == (MODEL, [1.0, 2.0, 3.0])
    put(3, [0.5, 0.25], model="next-model")
    second = db_exec("SELECT model, vector, updated_at FROM recruit_embeddings WHERE recruit_id = 3")
    assert len(second) == 1 and second[0][:2] == ("next-model", [0.5, 0.25]) and second[0][2] >= first[0][2]
    assert db_exec("SELECT count(*) FROM recruit_embeddings") == [(1,)]


@pytest.mark.parametrize(
    "model, vector",
    [(MODEL, []), (MODEL, [float("nan")]), (MODEL, [1.0, float("inf")]), (MODEL, [True]), (MODEL, ["1"]), ("", [1.0]), ("x" * 201, [1.0])],
)
def test_set_embedding_rejects_bad_values_and_saves_nothing(model, vector):
    with psycopg.connect(db_url(), autocommit=True, row_factory=dict_row) as conn:
        with pytest.raises(ValueError):
            set_embedding(conn, 3, model, vector)
    assert db_exec("SELECT count(*) FROM recruit_embeddings") == [(0,)]


def test_embeddings_belong_to_an_existing_recruit_and_go_with_it():
    with psycopg.connect(db_url(), autocommit=True, row_factory=dict_row) as conn:
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            set_embedding(conn, 99999, MODEL, [1.0])
    db_exec("INSERT INTO recruits (category, corporate, is_displayed) VALUES ('消す求人', '消す法人', true)")
    gone = db_exec("SELECT id FROM recruits WHERE category = '消す求人'")[0][0]
    put(gone, [1.0, 0.0])
    put(3, [1.0, 0.0])
    db_exec("DELETE FROM recruits WHERE id = %s", (gone,))
    assert db_exec("SELECT recruit_id FROM recruit_embeddings") == [(3,)]  # 求人を消すと、その埋め込みも消える
    with pytest.raises(psycopg.errors.CheckViolation):
        db_exec("INSERT INTO recruit_embeddings (recruit_id, model, vector) VALUES (4, 'm', '{}')")  # 空のベクトルは、DB でも拒む


def test_loading_does_not_need_a_query_when_there_is_nothing_to_load(sql_log):
    with psycopg.connect(db_url(), row_factory=dict_row) as conn:
        assert load_embeddings(conn, []) == {} and similarity_sums(conn, [], [1, 2]) == {}
        assert not sql_log


# ===== 関連する求人 =====


def test_related_is_unchanged_while_there_are_no_embeddings(client):
    assert ids(related(client, TARGET, limit=12)) == BASELINE_RELATED
    put_all({3: [1.0, 0.0], 8: [1.0, 1.0]})  # 基準（10）にベクトルが無ければ、候補にあっても何も変わらない
    assert ids(related(client, TARGET, limit=12)) == BASELINE_RELATED
    db_exec("DELETE FROM recruit_embeddings")
    put(TARGET, [1.0, 0.0])  # 基準にあっても、候補のどれにも無ければ変わらない
    assert ids(related(client, TARGET, limit=12)) == BASELINE_RELATED


def test_related_reorders_by_similarity_when_both_have_vectors(client):
    put_all({TARGET: [1.0, 0.0], 3: [1.0, 0.0], 8: [1.0, 1.0], 6: [0.0, 1.0], 11: [-1.0, 0.0], HIDDEN: [1.0, 0.0]})
    # 3: 類似度 1 → +5、8: 約 0.71 → +3.5。2: 条件 2。1・4・5・9: 条件 1。6・11 は直交・反対向きで 0 のまま。非表示の 12 は出ない
    assert ids(related(client, TARGET, limit=12)) == [3, 8, 2, 1, 4, 5, 9, 6, 7, 11]
    assert ids(related(client, TARGET, limit=12)) == oracle_related(TARGET, 12, vectors=vectors_in_db())


def test_related_co_viewed_recruits_still_come_before_similar_ones(client, make_user):
    a, _ = make_user(1)
    add_events([(a, TARGET), (a, 11)])
    put_all({TARGET: [1.0, 0.0], 3: [1.0, 0.0], 8: [1.0, 1.0], 11: [-1.0, 0.0]})
    assert ids(related(client, TARGET, limit=12)) == [11, 3, 8, 2, 1, 4, 5, 9, 6, 7]  # 11 は共起で先頭（類似度は 0）


def test_related_treats_different_dimension_or_model_as_zero(client):
    put(TARGET, [1.0, 0.0])
    put(3, [1.0, 0.0, 0.0])  # 次元が違う
    put(8, [1.0, 0.0], model="other-model")  # モデルが違う
    put(6, [1.0, 0.0])
    put(11, [1.0, 0.0])
    assert ids(related(client, TARGET, limit=12)) == [6, 11, 2, 1, 4, 5, 9, 3, 7, 8]  # 近いのは 6 と 11 だけ。3・8 は、ベクトルが無いのと同じ並び


def test_related_sql_does_not_grow_with_the_number_of_recruits_even_with_embeddings(client, sql_log):
    put_all({TARGET: [1.0, 0.0], 3: [1.0, 0.0], 8: [1.0, 1.0], 6: [0.0, 1.0], 11: [1.0, 0.0]})
    counts = {}
    for limit in (1, 12):
        sql_log.clear()
        assert len(related(client, TARGET, limit=limit)) == (1 if limit == 1 else 10)
        counts[limit] = len(sql_log)
    assert counts[1] == counts[12] and counts[12] <= 8  # 基準の埋め込みと候補の埋め込みで、それぞれ 1 回。求人の数には比例しない


# ===== おすすめ =====


def test_recommendations_are_unchanged_while_the_viewed_recruit_has_no_embedding(client, make_user):
    me_id, headers = make_user(1)
    add_events([(me_id, TARGET)])
    assert ids(recommendations(client, headers, limit=12)) == BASELINE_RECOMMENDED
    put_all({3: [1.0, 0.0], 8: [1.0, 1.0]})  # 見た求人（10）にベクトルが無い
    assert ids(recommendations(client, headers, limit=12)) == BASELINE_RECOMMENDED


def test_recommendations_add_similarity_and_can_surface_a_zero_condition_recruit(client, make_user):
    me_id, headers = make_user(1)
    add_events([(me_id, TARGET)])
    put_all({TARGET: [1.0, 0.0], 3: [1.0, 0.0], 8: [1.0, 1.0], 6: [0.0, 1.0], 7: [1.0, 0.0, 0.0], 11: [-1.0, 0.0], HIDDEN: [1.0, 0.0]})
    # 3（条件 0・共起 0）が、類似度だけで首位に入る。8 は約 3.5 点。6（直交）・7（次元違い）・11（反対向き）は 0 点のままで出ない。非表示の 12 は出ない
    assert ids(recommendations(client, headers, limit=12)) == [3, 8, 2, 1, 4, 5, 9]
    assert ids(recommendations(client, headers, limit=2)) == [3, 8]


def test_recommendations_sum_similarity_over_every_viewed_recruit(client, make_user):
    me_id, headers = make_user(1)
    add_events([(me_id, TARGET), (me_id, 1)])
    put_all({TARGET: [1.0, 0.0], 1: [0.0, 1.0], 3: [1.0, 1.0], 8: [1.0, 0.0]})
    # 3: 0.71 + 0.71 = 1.41 → +7.07。8: 1 + 0 → +5。2: 条件 2 + 1 = 3。4・5・9: 条件 1 + 1 = 2
    assert ids(recommendations(client, headers, limit=12)) == [3, 8, 2, 4, 5, 9]
    assert oracle_recommendations(me_id, 12, vectors=vectors_in_db()) == [3, 8, 2, 4, 5, 9]


def vectors_in_db() -> dict[int, tuple[str, list[float]]]:
    return {r[0]: (r[1], r[2]) for r in db_exec("SELECT recruit_id, model, vector FROM recruit_embeddings")}


@pytest.mark.parametrize("seed", [1, 2])  # 1 回が 10 秒ほどかかる（DB の JIT。test_recruit_events.py の同じテストの注を参照）
def test_random_histories_and_vectors_match_an_independent_implementation(client, make_user, seed):
    rng = random.Random(seed)
    users = [make_user(n) for n in range(1, 5)]
    for user_id, _ in users:
        picked = rng.sample(range(1, 13), rng.randint(1, 5))
        add_events([(user_id, recruit_id) for recruit_id in picked], minutes_ago=rng.choice([0, 100]))
    for recruit_id in rng.sample(range(1, 13), 8):  # 8 件にベクトル（次元 2 か 3、モデル 2 種類のどちらか）
        put(recruit_id, [rng.uniform(-1, 1) for _ in range(rng.choice([2, 2, 3]))], model=rng.choice(["m1", "m1", "m2"]))
    vectors, snap = vectors_in_db(), snapshot()
    for recruit_id in range(1, 12):
        assert ids(related(client, recruit_id, limit=12)) == oracle_related(recruit_id, 12, vectors=vectors, snap=snap), f"related {recruit_id}"
    for user_id, headers in users:
        assert ids(recommendations(client, headers, limit=12)) == oracle_recommendations(user_id, 12, vectors=vectors, snap=snap), f"user {user_id}"
