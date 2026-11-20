"""閲覧の記録と、それを使った「関連する求人」「あなたへのおすすめ」。機械学習は使わない（ルールと統計だけ。理由を説明できる順位づけ）。

- POST /api/recruits/{id}/view: 求職者の閲覧を記録する（認証は /api/auth/me と同じ Bearer。利用者は JWT の sub から決まる）。
- GET /api/recruits/{id}/related: 公開。その求人と一緒に見られた求人・条件の近い求人。
- GET /api/recommendations: 求職者だけ。見た求人から、まだ見ていない求人を選ぶ。
- 順位づけは、下の「順位づけ」の 2 つの関数（rank_related・rank_recommendations）に集めてある。中身（得点の式・埋め込み・学習）を入れ替えるときは、ここだけを直す。
  どちらも「求人の ID を、並べた順に」返すだけで、画面の形（RecruitSummary）を作る部分とは分けてある。
- 説明は docs/recommendation.md。個人情報（どの利用者が何を見たか）を保存する。利用者を消すと記録も消える。
"""

from typing import Annotated, NamedTuple

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.auth import current_user
from app.db import connection
from app.image_queries import hero_images
from app.recruit_embeddings import similarity_sums
from app.recruits import _NAMES, _SUMMARY_COLS  # 一覧・詳細と同じ列・名前の付け方（ここで作り直さない）
from app.schemas import RecruitSummary, User
from app.storage import get_storage

router = APIRouter(prefix="/api")

NOT_FOUND = HTTPException(status_code=404, detail="求人が見つかりません")

DEDUP_MINUTES = 30  # 同じ利用者・同じ求人の閲覧は、この分数のあいだ 1 件だけ記録する
COOCCURRENCE_WEIGHT = 3  # おすすめの得点: 共起の数 × 3
EMBEDDING_WEIGHT = 5  # 埋め込みの類似度（0〜1）× 5。埋め込みが無ければ 0 を足すだけ（recruit_embeddings.py）

# 条件の一致を数える種類（recruit_search の配列の列）。駅は数えない。マスタの名前は種類の中で重ならないので、コードの一致は名前の一致と同じ
_MATCH_COLUMNS = ("employment_codes", "area_codes", "occupation_codes")


# ===== 順位づけ =====


class Ranked(NamedTuple):
    """順位づけの 1 件。理由（数）つき。cooc: 共起の数、matches: 条件の一致の数、similarity: 埋め込みの類似度（合計。無ければ 0）。"""

    recruit_id: int
    cooc: int
    matches: int
    similarity: float
    score: float  # おすすめの得点（related では、共起の次の並び替えに使う「条件の得点」）


def _match_sql(candidate: str, pivot: str) -> str:
    """候補（別名 candidate）と基準（別名 pivot）の、条件の一致の数を出す SQL の式。別名と列名は、このモジュールの固定の文字列だけ。"""
    return " + ".join(
        f"(SELECT count(*) FROM unnest({candidate}.{col}) AS x WHERE x = ANY({pivot}.{col}))" for col in _MATCH_COLUMNS
    )


def _condition_score(matches: int, similarity: float) -> float:
    """条件の一致の数に、埋め込みの類似度 × EMBEDDING_WEIGHT を足したもの。類似度が 0 なら、一致の数のまま。"""
    return round(matches + EMBEDDING_WEIGHT * similarity, 9)  # 浮動小数点の端数で、同点の並びが ID 順にならないのを防ぐ


def rank_related(conn, recruit_id: int, limit: int) -> list[Ranked]:
    """求人 recruit_id に関連する、表示中の求人（自分は含めない）。

    並び: (1) 同じ利用者が両方を閲覧した、その利用者の数（共起）の多い順、(2) 条件（雇用形態・エリア・職種）の一致の数
    （埋め込みがあれば、その類似度 × EMBEDDING_WEIGHT を足したもの）の多い順、(3) ID の昇順。
    共起が 0 でも、条件が 1 つも合わなくても、表示中なら入る（上の並びで後ろになるだけ）。
    """
    rows = conn.execute(
        "WITH co AS ("
        "  SELECT o2.recruit_id, count(DISTINCT o1.user_id) AS n FROM recruit_events o1"
        "  JOIN recruit_events o2 ON o2.user_id = o1.user_id AND o2.event_type = 'view' AND o2.recruit_id <> o1.recruit_id"
        "  WHERE o1.recruit_id = %(rid)s AND o1.event_type = 'view' GROUP BY o2.recruit_id"
        ") "
        f"SELECT c.id AS recruit_id, COALESCE(co.n, 0)::int AS cooc, ({_match_sql('c', 't')})::int AS matches "
        "FROM recruit_search c JOIN recruit_search t ON t.id = %(rid)s LEFT JOIN co ON co.recruit_id = c.id "
        "WHERE c.is_displayed AND c.id <> %(rid)s",
        {"rid": recruit_id},
    ).fetchall()
    similarity = similarity_sums(conn, [recruit_id], [r["recruit_id"] for r in rows])
    ranked = []
    for r in rows:
        sim = similarity.get(r["recruit_id"], 0.0)
        ranked.append(Ranked(r["recruit_id"], r["cooc"], r["matches"], sim, _condition_score(r["matches"], sim)))
    ranked.sort(key=lambda x: (-x.cooc, -x.score, x.recruit_id))
    return ranked[:limit]


def rank_recommendations(conn, user_id: int, limit: int) -> list[Ranked]:
    """利用者へのおすすめ。その人がまだ見ていない・表示中の求人から選ぶ。閲覧の履歴が無ければ []。

    得点 = 見た求人との共起の数の合計 × COOCCURRENCE_WEIGHT + 見た求人との条件の一致の数の合計（+ 埋め込みの類似度の合計 × EMBEDDING_WEIGHT）。
    得点 0 の求人は出さない。同点は ID の昇順。
    共起の数 = 見た求人 v と候補 c を、どちらも見た「別の利用者」の数（利用者ごとに 1 と数える）。v ごとに数えて足す。
    """
    viewed = conn.execute(
        "SELECT DISTINCT recruit_id FROM recruit_events WHERE user_id = %s AND event_type = 'view' ORDER BY recruit_id", (user_id,)
    ).fetchall()
    seen = [r["recruit_id"] for r in viewed]
    if not seen:
        return []
    rows = conn.execute(
        "WITH co AS ("
        "  SELECT p.cand_id, count(*) AS n FROM ("
        "    SELECT DISTINCT s.v AS seen_id, o2.user_id, o2.recruit_id AS cand_id FROM unnest(%(seen)s::int[]) AS s(v)"
        "    JOIN recruit_events o1 ON o1.recruit_id = s.v AND o1.event_type = 'view'"
        "    JOIN recruit_events o2 ON o2.user_id = o1.user_id AND o2.event_type = 'view' AND o2.recruit_id <> s.v"
        "  ) p GROUP BY p.cand_id"
        ") "
        f"SELECT c.id AS recruit_id, COALESCE(co.n, 0)::int AS cooc, sum({_match_sql('c', 'v')})::int AS matches "
        "FROM recruit_search c JOIN recruit_search v ON v.id = ANY(%(seen)s::int[]) LEFT JOIN co ON co.cand_id = c.id "
        "WHERE c.is_displayed AND c.id <> ALL(%(seen)s::int[]) GROUP BY c.id, co.n",
        {"seen": seen},
    ).fetchall()
    similarity = similarity_sums(conn, seen, [r["recruit_id"] for r in rows])
    ranked = []
    for r in rows:
        sim = similarity.get(r["recruit_id"], 0.0)
        score = round(r["cooc"] * COOCCURRENCE_WEIGHT + _condition_score(r["matches"], sim), 9)
        if score > 0:
            ranked.append(Ranked(r["recruit_id"], r["cooc"], r["matches"], sim, score))
    ranked.sort(key=lambda x: (-x.score, x.recruit_id))
    return ranked[:limit]


# ===== 応答（RecruitSummary）の組み立て =====


def summaries(conn, recruit_ids: list[int]) -> list[RecruitSummary]:
    """求人の ID の並びのとおりに、一覧と同じ形（hero_image 込み）にする。SQL は、求人の件数によらず（空でなければ）2 回: 求人の本体と画像。"""
    if not recruit_ids:
        return []
    rows = conn.execute(
        f"SELECT {_SUMMARY_COLS}, {_NAMES} FROM recruit_search s WHERE s.id = ANY(%s::int[]) AND s.is_displayed",  # noqa: S608
        (recruit_ids,),
    ).fetchall()
    by_id = {row["id"]: row for row in rows}
    ordered = [by_id[i] for i in recruit_ids if i in by_id]  # 順位づけのあとで非表示になった求人は、落とす
    heroes = hero_images(conn, [row["id"] for row in ordered], get_storage())
    return [RecruitSummary(**row, hero_image=heroes.get(row["id"])) for row in ordered]


# ===== API =====


@router.post("/recruits/{recruit_id}/view", status_code=204, response_class=Response)
def record_view(recruit_id: int, user: Annotated[User, Depends(current_user)]) -> Response:
    """閲覧を記録する。同じ利用者・同じ求人は、直近 DEDUP_MINUTES 分に 1 件あれば足さない（それでも 204）。表示中でない・無い求人は 404。"""
    with connection() as conn:
        # 求人の行を共有ロックして確かめる（このトランザクションのあいだ、求人が消えない）。recruit_search は集約のビューなので、同じ is_displayed を持つ recruits を見る
        if conn.execute("SELECT 1 FROM recruits WHERE id = %s AND is_displayed FOR KEY SHARE", (recruit_id,)).fetchone() is None:
            raise NOT_FOUND
        # 同じ利用者・同じ求人の同時のリクエストが、どちらも「無い」と見て 2 件足さないよう、この組だけを直列にする（コミットまで）
        conn.execute("SELECT pg_advisory_xact_lock(%s::int, %s::int)", (user.id, recruit_id))
        conn.execute(
            "INSERT INTO recruit_events (user_id, recruit_id, event_type) SELECT %(u)s::int, %(r)s::int, 'view' "
            "WHERE NOT EXISTS (SELECT 1 FROM recruit_events WHERE user_id = %(u)s AND recruit_id = %(r)s AND event_type = 'view' "
            "AND created_at > now() - make_interval(mins => %(m)s))",
            {"u": user.id, "r": recruit_id, "m": DEDUP_MINUTES},
        )
    return Response(status_code=204)


@router.get("/recruits/{recruit_id}/related", response_model=list[RecruitSummary])
def related(recruit_id: int, limit: Annotated[int, Query(ge=1, le=12)] = 4) -> list[RecruitSummary]:
    with connection() as conn:
        if conn.execute("SELECT 1 FROM recruits WHERE id = %s AND is_displayed", (recruit_id,)).fetchone() is None:
            raise NOT_FOUND
        ranked = rank_related(conn, recruit_id, limit)
        return summaries(conn, [r.recruit_id for r in ranked])


@router.get("/recommendations", response_model=list[RecruitSummary])
def recommendations(user: Annotated[User, Depends(current_user)], limit: Annotated[int, Query(ge=1, le=12)] = 6) -> list[RecruitSummary]:
    with connection() as conn:
        ranked = rank_recommendations(conn, user.id, limit)
        return summaries(conn, [r.recruit_id for r in ranked])
