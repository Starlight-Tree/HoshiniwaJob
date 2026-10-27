"""画像の読み取り（公開 API 用と、園の管理 API 用）。DB の行から、公開 URL などを組み立てる。"""

from app.schemas import ImageBody, ImageInfo
from app.storage import Storage


def public_images(conn, recruit_id: int, storage: Storage) -> list[tuple[ImageInfo, bool]]:
    """求人の、公開してよい（approved の）画像。表示順。(画像, ヒーローか) の並び。"""
    rows = conn.execute(
        "SELECT i.id, i.storage_key, i.alt, i.width, i.height, i.mime_type, ri.is_hero FROM recruit_images ri "
        "JOIN images i ON i.id = ri.image_id WHERE ri.recruit_id = %s AND i.status = 'approved' ORDER BY ri.position",
        (recruit_id,),
    ).fetchall()
    return [
        (ImageInfo(id=str(r["id"]), url=storage.public_url(r["storage_key"]), alt=r["alt"], width=r["width"], height=r["height"], mime_type=r["mime_type"]), r["is_hero"])
        for r in rows
    ]


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
