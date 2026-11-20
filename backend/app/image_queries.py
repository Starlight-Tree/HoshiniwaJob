"""画像の読み取り（公開 API 用と、園の管理 API 用）。DB の行から、公開 URL などを組み立てる。"""

from app.schemas import ImageBody, ImageInfo
from app.storage import Storage


def _image_info(row: dict, storage: Storage) -> ImageInfo:
    return ImageInfo(
        id=str(row["id"]),
        url=storage.public_url(row["storage_key"]),
        alt=row["alt"],
        width=row["width"],
        height=row["height"],
        mime_type=row["mime_type"],
    )


def public_images(conn, recruit_id: int, storage: Storage) -> list[tuple[ImageInfo, bool]]:
    """求人の、公開してよい（approved の）画像。表示順。(画像, ヒーローか) の並び。"""
    rows = conn.execute(
        "SELECT i.id, i.storage_key, i.alt, i.width, i.height, i.mime_type, ri.is_hero FROM recruit_images ri "
        "JOIN images i ON i.id = ri.image_id WHERE ri.recruit_id = %s AND i.status = 'approved' ORDER BY ri.position",
        (recruit_id,),
    ).fetchall()
    return [(_image_info(r, storage), r["is_hero"]) for r in rows]


def hero_images(conn, recruit_ids: list[int], storage: Storage) -> dict[int, ImageInfo]:
    """求人ごとの代表画像（一覧のサムネ用）。1 回の SQL で、渡した求人の分を引く。

    選び方は詳細 API と同じ: 公開してよい（approved の）画像のうち、ヒーローに指定されたもの。無ければ表示順（position）で先頭。
    公開中の画像が 1 枚も無い求人は、結果に入らない。recruit_ids が空なら、SQL は流さない。
    """
    if not recruit_ids:
        return {}
    rows = conn.execute(
        "SELECT DISTINCT ON (ri.recruit_id) ri.recruit_id, i.id, i.storage_key, i.alt, i.width, i.height, i.mime_type "
        "FROM recruit_images ri JOIN images i ON i.id = ri.image_id "
        "WHERE ri.recruit_id = ANY(%s::int[]) AND i.status = 'approved' "
        "ORDER BY ri.recruit_id, ri.is_hero DESC, ri.position, ri.image_id",  # 同じ順位でも結果が変わらないよう、最後は image_id で決める
        (list(recruit_ids),),
    ).fetchall()
    return {r["recruit_id"]: _image_info(r, storage) for r in rows}


def body_of(row: dict, storage: Storage) -> ImageBody:
    return ImageBody(
        id=str(row["id"]),
        alt=row["alt"],
        width=row["width"],
        height=row["height"],
        mime_type=row["mime_type"],
        origin=row["origin"],
        status=row["status"],
        position=row["position"],
        is_hero=row.get("is_hero", False),
        role=row.get("role"),
        url=storage.public_url(row["storage_key"]) if row["status"] == "approved" else None,
    )


def recruit_images_for_garden(conn, recruit_id: int, storage: Storage) -> list[ImageBody]:
    """園が見る、求人の画像（取り下げられたものを含む。削除済みは除く）。"""
    rows = conn.execute(
        "SELECT i.id, i.storage_key, i.alt, i.width, i.height, i.mime_type, i.origin, i.status, ri.position, ri.is_hero FROM recruit_images ri "
        "JOIN images i ON i.id = ri.image_id WHERE ri.recruit_id = %s AND i.status <> 'deleted' ORDER BY ri.position",
        (recruit_id,),
    ).fetchall()
    return [body_of(r, storage) for r in rows]
