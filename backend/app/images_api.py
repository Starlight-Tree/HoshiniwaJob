"""園が自分の求人・法人の画像を扱う API と、ローカル保存のときの公開画像の配信（/media）。

権限: 園は、自分に紐づく求人（recruits.garden_account_id）と、自分の画像だけを扱える。確認は、画面ではなくここ（API）で、毎回 SQL の条件で行う。
他の園の求人・画像は、存在しないのと同じ 404 を返す。
園ができるのは「登録（保存した時点で公開）・並べ替え・ヒーローの指定・外す（その場で削除）」まで。
承認の段階は無い。公開後に問題があれば、運営だけが取り下げられる（app/images_cli.py の reject）。
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool

from app.db import connection
from app.garden import current_garden
from app.image_queries import body_of, recruit_images_for_garden
from app.image_service import FORMATS, MAX_IMAGES_PER_RECRUIT, ImageRejected, Processed, delete_object, process_image, register_image, unlink_if_unused
from app.schemas import Garden, GardenRecruitImages, GardenRecruitItem, HeroChoice, ImageBody, ImageOrder
from app.settings import max_upload_bytes
from app.storage import StorageError, get_storage

router = APIRouter(prefix="/api/garden")
media_router = APIRouter()

MAX_PROFILE_IMAGES = 5
_ALLOWED_TYPES = {mime for mime, _ in FORMATS.values()}
_EXT_TYPES = {ext: mime for mime, ext in FORMATS.values()}
NOT_FOUND_RECRUIT = HTTPException(status_code=404, detail="求人が見つかりません")
NOT_FOUND_IMAGE = HTTPException(status_code=404, detail="画像が見つかりません")


def _own_recruit(conn, recruit_id: int, garden_id: int, *, lock: bool = False) -> dict:
    row = conn.execute(
        "SELECT id, category, is_displayed FROM recruits WHERE id = %s AND garden_account_id = %s" + (" FOR UPDATE" if lock else ""),
        (recruit_id, garden_id),
    ).fetchone()
    if row is None:
        raise NOT_FOUND_RECRUIT
    return row


async def _read_upload(request: Request, alt: str) -> tuple[Processed, str]:
    """本文を上限まで読み、検証して（メタデータを除いた）配信用のバイト列にする。"""
    alt = alt.strip()
    if not 1 <= len(alt) <= 300:
        raise HTTPException(status_code=422, detail="代替テキストは 1〜300 文字で入れてください")
    declared = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if declared not in _ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="JPEG・PNG・WebP の画像だけ登録できます")
    limit = max_upload_bytes()
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > limit:
        raise HTTPException(status_code=413, detail=f"画像は {limit // (1024 * 1024)}MB 以下にしてください")
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise HTTPException(status_code=413, detail=f"画像は {limit // (1024 * 1024)}MB 以下にしてください")
        chunks.append(chunk)
    try:
        processed = await run_in_threadpool(process_image, b"".join(chunks), max_bytes=limit)
    except ImageRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    if processed.mime_type != declared:
        raise HTTPException(status_code=422, detail="画像の種類が、指定と一致しません")
    return processed, alt


def _register(conn, garden: Garden, processed: Processed, alt: str):
    try:
        return register_image(conn, get_storage(), processed, alt=alt, origin="uploaded", owner_garden_id=garden.id)
    except StorageError:
        raise HTTPException(status_code=503, detail="画像を保存できませんでした。しばらくしてから、もう一度お試しください") from None


@router.get("/recruits", response_model=list[GardenRecruitItem])
def my_recruits(garden: Annotated[Garden, Depends(current_garden)]) -> list[GardenRecruitItem]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT r.id, r.category, r.is_displayed, "
            "count(i.id) FILTER (WHERE i.status <> 'deleted') AS image_count, count(i.id) FILTER (WHERE i.status = 'approved') AS published_count "
            "FROM recruits r LEFT JOIN recruit_images ri ON ri.recruit_id = r.id LEFT JOIN images i ON i.id = ri.image_id "
            "WHERE r.garden_account_id = %s GROUP BY r.id ORDER BY r.id",
            (garden.id,),
        ).fetchall()
    return [GardenRecruitItem(**r) for r in rows]


@router.get("/recruits/{recruit_id}/images", response_model=GardenRecruitImages)
def list_recruit_images(recruit_id: int, garden: Annotated[Garden, Depends(current_garden)]) -> GardenRecruitImages:
    with connection() as conn:
        recruit = _own_recruit(conn, recruit_id, garden.id)
        images = recruit_images_for_garden(conn, recruit_id, get_storage())
    return GardenRecruitImages(recruit_id=recruit_id, category=recruit["category"], is_displayed=recruit["is_displayed"], max_images=MAX_IMAGES_PER_RECRUIT, images=images)


@router.post("/recruits/{recruit_id}/images", response_model=ImageBody, status_code=201)
async def upload_recruit_image(recruit_id: int, request: Request, garden: Annotated[Garden, Depends(current_garden)], alt: Annotated[str, Query()]) -> ImageBody:
    """本文は画像そのもの（Content-Type は image/jpeg・image/png・image/webp）。検証に通れば、保存した時点で公開される。"""

    def check() -> None:
        with connection() as conn:
            _own_recruit(conn, recruit_id, garden.id)
            count = conn.execute("SELECT count(*) AS n FROM recruit_images WHERE recruit_id = %s", (recruit_id,)).fetchone()["n"]
            if count >= MAX_IMAGES_PER_RECRUIT:
                raise HTTPException(status_code=409, detail=f"1 つの求人に登録できる画像は {MAX_IMAGES_PER_RECRUIT} 枚までです")

    await run_in_threadpool(check)  # 所有権と枚数を、重い処理の前に確かめる
    processed, text = await _read_upload(request, alt)

    def store() -> ImageBody:
        with connection() as conn:
            _own_recruit(conn, recruit_id, garden.id)
            image_id = _register(conn, garden, processed, text)
            _own_recruit(conn, recruit_id, garden.id, lock=True)  # 同じ求人への同時の登録で、表示順が重ならないように
            count = conn.execute("SELECT count(*) AS n FROM recruit_images WHERE recruit_id = %s", (recruit_id,)).fetchone()["n"]
            if count >= MAX_IMAGES_PER_RECRUIT:
                key = unlink_if_unused(conn, image_id)  # 補償: 結べなかった画像を、その場で消す
                conn.commit()
                delete_object(get_storage(), key)
                raise HTTPException(status_code=409, detail=f"1 つの求人に登録できる画像は {MAX_IMAGES_PER_RECRUIT} 枚までです")
            conn.execute(
                "INSERT INTO recruit_images (recruit_id, image_id, position) SELECT %s, %s, COALESCE(MAX(position) + 1, 0) FROM recruit_images WHERE recruit_id = %s",
                (recruit_id, image_id, recruit_id),
            )
            conn.commit()
            return next(b for b in recruit_images_for_garden(conn, recruit_id, get_storage()) if b.id == str(image_id))

    return await run_in_threadpool(store)


@router.put("/recruits/{recruit_id}/images/order", response_model=GardenRecruitImages)
def reorder_recruit_images(recruit_id: int, body: ImageOrder, garden: Annotated[Garden, Depends(current_garden)]) -> GardenRecruitImages:
    try:
        wanted = [uuid.UUID(i) for i in body.image_ids]
    except ValueError:
        raise HTTPException(status_code=422, detail="画像の指定が正しくありません") from None
    with connection() as conn:
        recruit = _own_recruit(conn, recruit_id, garden.id, lock=True)
        current = {r["image_id"] for r in conn.execute("SELECT image_id FROM recruit_images WHERE recruit_id = %s", (recruit_id,)).fetchall()}
        if len(wanted) != len(set(wanted)) or set(wanted) != current:
            raise HTTPException(status_code=422, detail="並べ替える画像が、今の画像の一覧と一致しません")
        for position, image_id in enumerate(wanted):
            conn.execute("UPDATE recruit_images SET position = %s WHERE recruit_id = %s AND image_id = %s", (position, recruit_id, image_id))
        conn.commit()
        images = recruit_images_for_garden(conn, recruit_id, get_storage())
    return GardenRecruitImages(recruit_id=recruit_id, category=recruit["category"], is_displayed=recruit["is_displayed"], max_images=MAX_IMAGES_PER_RECRUIT, images=images)


@router.put("/recruits/{recruit_id}/images/hero", response_model=GardenRecruitImages)
def set_hero_image(recruit_id: int, body: HeroChoice, garden: Annotated[Garden, Depends(current_garden)]) -> GardenRecruitImages:
    try:
        image_id = uuid.UUID(body.image_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="画像の指定が正しくありません") from None
    with connection() as conn:
        recruit = _own_recruit(conn, recruit_id, garden.id, lock=True)
        row = conn.execute(
            "SELECT i.status FROM recruit_images ri JOIN images i ON i.id = ri.image_id WHERE ri.recruit_id = %s AND ri.image_id = %s",
            (recruit_id, image_id),
        ).fetchone()
        if row is None:
            raise NOT_FOUND_IMAGE
        if row["status"] != "approved":
            raise HTTPException(status_code=409, detail="公開されていない（取り下げられた）画像は、ヒーローにできません")
        conn.execute("UPDATE recruit_images SET is_hero = false WHERE recruit_id = %s AND is_hero", (recruit_id,))
        conn.execute("UPDATE recruit_images SET is_hero = true WHERE recruit_id = %s AND image_id = %s", (recruit_id, image_id))
        conn.commit()
        images = recruit_images_for_garden(conn, recruit_id, get_storage())
    return GardenRecruitImages(recruit_id=recruit_id, category=recruit["category"], is_displayed=recruit["is_displayed"], max_images=MAX_IMAGES_PER_RECRUIT, images=images)


@router.delete("/recruits/{recruit_id}/images/{image_id}", status_code=204)
def remove_recruit_image(recruit_id: int, image_id: uuid.UUID, garden: Annotated[Garden, Depends(current_garden)]) -> Response:
    """削除。求人から外し、どこからも使われなければ、その場で画像を消す（元に戻せない）。"""
    with connection() as conn:
        _own_recruit(conn, recruit_id, garden.id, lock=True)
        gone = conn.execute("DELETE FROM recruit_images WHERE recruit_id = %s AND image_id = %s", (recruit_id, image_id))
        if gone.rowcount == 0:
            raise NOT_FOUND_IMAGE
        key = unlink_if_unused(conn, image_id)
        conn.execute(
            "UPDATE recruit_images r SET position = s.rn - 1 FROM (SELECT image_id, row_number() OVER (ORDER BY position) AS rn FROM recruit_images WHERE recruit_id = %s) s "
            "WHERE r.recruit_id = %s AND r.image_id = s.image_id",
            (recruit_id, recruit_id),
        )
        conn.commit()
        delete_object(get_storage(), key)  # DB の確定のあとで実体を消す。失敗しても、画像は DB の上で消えている
    return Response(status_code=204)


# ---- 法人の画像（ロゴ・バナー）。同じ画像の基盤を使う。公開ページでの表示は、法人の紹介ページができてから ----


@router.get("/profile-images", response_model=list[ImageBody])
def list_profile_images(garden: Annotated[Garden, Depends(current_garden)]) -> list[ImageBody]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT i.id, i.storage_key, i.alt, i.width, i.height, i.mime_type, i.origin, i.status, gi.position, gi.role FROM garden_images gi "
            "JOIN images i ON i.id = gi.image_id WHERE gi.garden_account_id = %s AND i.status <> 'deleted' ORDER BY gi.role, gi.position",
            (garden.id,),
        ).fetchall()
    return [body_of(r, get_storage()) for r in rows]


@router.post("/profile-images", response_model=ImageBody, status_code=201)
async def upload_profile_image(
    request: Request, garden: Annotated[Garden, Depends(current_garden)], alt: Annotated[str, Query()], role: Annotated[str, Query(pattern="^(logo|banner)$")]
) -> ImageBody:
    processed, text = await _read_upload(request, alt)

    def store() -> ImageBody:
        with connection() as conn:
            conn.execute("SELECT id FROM garden_accounts WHERE id = %s FOR UPDATE", (garden.id,))
            count = conn.execute("SELECT count(*) AS n FROM garden_images WHERE garden_account_id = %s AND role = %s", (garden.id, role)).fetchone()["n"]
            if count >= MAX_PROFILE_IMAGES:
                raise HTTPException(status_code=409, detail=f"登録できる画像は、種類ごとに {MAX_PROFILE_IMAGES} 枚までです")
            image_id = _register(conn, garden, processed, text)
            conn.execute("SELECT id FROM garden_accounts WHERE id = %s FOR UPDATE", (garden.id,))
            conn.execute(
                "INSERT INTO garden_images (garden_account_id, image_id, role, position) SELECT %s, %s, %s, COALESCE(MAX(position) + 1, 0) FROM garden_images "
                "WHERE garden_account_id = %s AND role = %s",
                (garden.id, image_id, role, garden.id, role),
            )
            conn.commit()
            row = conn.execute(
                "SELECT i.id, i.storage_key, i.alt, i.width, i.height, i.mime_type, i.origin, i.status, gi.position, gi.role FROM garden_images gi "
                "JOIN images i ON i.id = gi.image_id WHERE gi.image_id = %s",
                (image_id,),
            ).fetchone()
            return body_of(row, get_storage())

    return await run_in_threadpool(store)


@router.delete("/profile-images/{image_id}", status_code=204)
def remove_profile_image(image_id: uuid.UUID, garden: Annotated[Garden, Depends(current_garden)]) -> Response:
    with connection() as conn:
        gone = conn.execute("DELETE FROM garden_images WHERE garden_account_id = %s AND image_id = %s", (garden.id, image_id))
        if gone.rowcount == 0:
            raise NOT_FOUND_IMAGE
        key = unlink_if_unused(conn, image_id)
        conn.commit()
        delete_object(get_storage(), key)
    return Response(status_code=204)


# ---- ローカル保存のときだけ、画像を配る（S3 / R2 では、公開 URL の配信元が配る） ----


@media_router.get("/media/{key:path}", include_in_schema=False)
def media(key: str) -> Response:
    ext = key.rsplit(".", 1)[-1] if "." in key else ""
    if ext not in _EXT_TYPES:
        raise NOT_FOUND_IMAGE
    try:
        data = get_storage().get(key)
    except StorageError:
        raise NOT_FOUND_IMAGE from None
    return Response(
        content=data, media_type=_EXT_TYPES[ext], headers={"Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"}
    )
