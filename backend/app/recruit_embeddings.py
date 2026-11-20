"""求人の埋め込み（文章の意味を数の並びにしたもの）の差し込み口。今は空のままで、値は入れていない。

- 表は recruit_embeddings（マイグレーション 0006）。pgvector は使わず、double precision[] に入れる（拡張を足さない）。
- 値を入れるのは set_embedding だけ（upsert）。これを呼ぶ CLI・API は作っていない。埋め込みを作るには実 API（求人の文章の埋め込み）が要る。
  このモジュールは、その API を呼ぶコードを持たない。入れるときは、回数と費用を示して承認を得てから、別の道具で行う。
- 近さは、コサイン類似度。「両方にベクトルがあるとき」だけ値を持ち、無いとき・次元が違うとき・モデルが違うときは 0。負の値も 0 に切る（遠いからといって、条件の得点を引かない）。
  使われ方は recruit_events.py（関連する求人・おすすめの得点に、類似度 × EMBEDDING_WEIGHT を足す）。
"""

import math
from collections.abc import Sequence
from typing import NamedTuple


class Embedding(NamedTuple):
    model: str
    vector: tuple[float, ...]


def set_embedding(conn, recruit_id: int, model: str, vector: Sequence[float]) -> None:
    """求人の埋め込みを入れる（あれば置き換える）。トランザクションは呼ぶ側が決める（commit しない）。

    vector は、1 つ以上の有限の数。model は、1〜200 文字のモデルの名前（モデルが違うベクトルどうしは比べない）。
    求人が無ければ、外部キーのエラーになる。
    """
    if not isinstance(model, str) or not 1 <= len(model) <= 200:
        raise ValueError("model は 1〜200 文字の文字列にしてください")
    values = list(vector)
    if not values or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in values):
        raise ValueError("vector は、1 つ以上の有限の数の並びにしてください")
    conn.execute(
        "INSERT INTO recruit_embeddings (recruit_id, model, vector) VALUES (%s, %s, %s::float8[]) "
        "ON CONFLICT (recruit_id) DO UPDATE SET model = EXCLUDED.model, vector = EXCLUDED.vector, updated_at = now()",
        (recruit_id, model, [float(x) for x in values]),
    )


def load_embeddings(conn, recruit_ids: Sequence[int]) -> dict[int, Embedding]:
    """渡した求人のうち、埋め込みがあるものを 1 回の SQL で引く。recruit_ids が空なら SQL は流さない。"""
    if not recruit_ids:
        return {}
    rows = conn.execute(
        "SELECT recruit_id, model, vector FROM recruit_embeddings WHERE recruit_id = ANY(%s::int[])", (list(recruit_ids),)
    ).fetchall()
    return {r["recruit_id"]: Embedding(r["model"], tuple(r["vector"])) for r in rows}


def cosine(a: Embedding, b: Embedding) -> float:
    """コサイン類似度（0〜1）。モデルか次元が違う・長さが 0 のベクトルがある・負になるときは 0。"""
    if a.model != b.model or len(a.vector) != len(b.vector):
        return 0.0
    norm_a = math.sqrt(sum(x * x for x in a.vector))
    norm_b = math.sqrt(sum(x * x for x in b.vector))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    value = sum(x * y for x, y in zip(a.vector, b.vector, strict=True)) / (norm_a * norm_b)
    return min(1.0, max(0.0, value)) if math.isfinite(value) else 0.0


def similarity_sums(conn, pivot_ids: Sequence[int], candidate_ids: Sequence[int]) -> dict[int, float]:
    """候補ごとに、基準の求人（pivot_ids）との類似度の合計。基準にも候補にも埋め込みがあるものだけが、結果に入る（入らない候補は 0）。

    基準に埋め込みが 1 つも無ければ、候補の分は引かない（SQL は 1 回。ある場合は 2 回。求人の件数に比例しない）。
    """
    pivots = load_embeddings(conn, pivot_ids)
    if not pivots:
        return {}
    candidates = load_embeddings(conn, candidate_ids)
    sums: dict[int, float] = {}
    for candidate_id, embedding in candidates.items():
        total = sum(cosine(pivot, embedding) for pivot in pivots.values())
        if total > 0:
            sums[candidate_id] = total
    return sums
