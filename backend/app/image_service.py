"""画像の検証・登録・取り下げ・削除・点検（API・CLI・seed が同じものを使う）。

登録（register_image）: 検証（process_image）→ DB に uploading で記録 → 保存 → approved（公開中）。承認の段階は無く、登録が済んだ画像はそのまま公開される。
  （status の値は DB の制約に合わせて残してある。approved は「公開中」の意味。旧い値の pending / publishing は、今は作られない。）
取り下げ（reject_image。運営だけ）: DB を rejected にして、実体を消す。公開後の安全弁で、承認ではない。
削除（unlink_if_unused）: 求人などから外れて、どこからも使われなくなった画像は、その場で deleted にして実体を消す（猶予は無い）。
点検（reconcile）: DB と保存先の食い違いを報告するだけで、何も変えない。
どの途中で止まっても、DB とストレージが食い違ったままにならないための設計:
- 先に DB へ意図（uploading）を書き、そのあとストレージを触る。削除は、先に DB を deleted / rejected にして確定し、そのあとで実体を消す。
- ストレージの操作は何度やっても同じ結果になる。実体の削除に失敗しても、DB が先に確定しているので、公開 API には出ない。残った実体は reconcile が報告する。
- 画像の更新は、同じキーに上書きせず、新しい画像（新しい uuid のキー）として登録する。
- 参照されている画像（recruit_images / garden_images）は消さない。DB も RESTRICT で守る。
関数は dict_row の psycopg 接続を受け取る。各段階は conn.commit() で確定する（自動コミットの接続でもそのまま動く）。
"""

import hashlib
import io
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from PIL import Image, ImageOps, UnidentifiedImageError

from app.storage import Storage, StorageError

log = logging.getLogger("app.images")

FORMATS = {"JPEG": ("image/jpeg", "jpg"), "PNG": ("image/png", "png"), "WEBP": ("image/webp", "webp")}
MIN_SIDE = 200  # 入力の短辺の下限（px）
MAX_PIXELS = 40_000_000  # 入力の総画素の上限（展開して膨らむ画像への備え）
OUT_MAX_EDGE = 2400  # 配信用に縮める長辺の上限（px）
MAX_IMAGES_PER_RECRUIT = 10
Image.MAX_IMAGE_PIXELS = MAX_PIXELS * 2


class ImageRejected(ValueError):
    """受け付けられない画像。メッセージは、そのまま利用者に見せてよい固定の説明。"""


class ImageConflict(RuntimeError):
    """状態が合わず、操作できない（取り下げられた画像をヒーローにする、など）。メッセージは固定の説明。"""


@dataclass(frozen=True)
class Processed:
    data: bytes
    mime_type: str
    ext: str
    width: int
    height: int
    sha256: str


def process_image(raw: bytes, *, max_bytes: int) -> Processed:
    """実データを検証し、メタデータ（EXIF・ICC・テキスト）を除いて再エンコードした配信用のバイト列を返す。"""
    if len(raw) == 0:
        raise ImageRejected("画像が空です")
    if len(raw) > max_bytes:
        raise ImageRejected(f"画像は {max_bytes // (1024 * 1024)}MB 以下にしてください")
    try:
        probe = Image.open(io.BytesIO(raw), formats=list(FORMATS))
        fmt = probe.format
        if fmt not in FORMATS:
            raise ImageRejected("JPEG・PNG・WebP の画像だけ登録できます")
        if getattr(probe, "n_frames", 1) > 1:
            raise ImageRejected("アニメーションの画像は登録できません")
        if probe.width * probe.height > MAX_PIXELS:
            raise ImageRejected("画像の画素数が大きすぎます")
        if min(probe.size) < MIN_SIDE:
            raise ImageRejected(f"画像は短辺 {MIN_SIDE}px 以上にしてください")
        probe.verify()
        img = Image.open(io.BytesIO(raw), formats=list(FORMATS))
        img.load()
    except ImageRejected:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise ImageRejected("画像として読み込めません（形式が違うか、壊れています）") from None

    img = ImageOps.exif_transpose(img)  # 向きは画素に反映してから、メタデータを捨てる
    img.thumbnail((OUT_MAX_EDGE, OUT_MAX_EDGE), Image.Resampling.LANCZOS)
    mime, ext = FORMATS[fmt]
    if fmt == "JPEG":
        img = img.convert("RGB" if img.mode not in ("RGB", "L") else img.mode)
    elif img.mode not in ("RGB", "RGBA", "L"):
        img = img.convert("RGBA" if "A" in img.getbands() or "transparency" in img.info else "RGB")
    clean = Image.new(img.mode, img.size)  # 情報（info）を持たない新しい画像へ、画素だけ写す
    clean.paste(img)
    out = io.BytesIO()
    if fmt == "JPEG":
        clean.save(out, "JPEG", quality=88, optimize=True, progressive=True)
    elif fmt == "PNG":
        clean.save(out, "PNG", optimize=True)
    else:
        clean.save(out, "WEBP", quality=88, method=4)
    data = out.getvalue()
    return Processed(data, mime, ext, clean.width, clean.height, hashlib.sha256(data).hexdigest())


def _rollback_quietly(conn) -> None:
    try:
        conn.rollback()
    except Exception:  # noqa: BLE001
        pass


def register_image(
    conn, storage: Storage, processed: Processed, *, alt: str, origin: str, owner_garden_id: int | None = None, demo_key: str | None = None
) -> uuid.UUID:
    """検証済みの画像を保存して、公開中（approved）で登録する。失敗したら、作りかけの行と実体を消して例外を返す。"""
    alt = alt.strip()
    if not 1 <= len(alt) <= 300:
        raise ImageRejected("代替テキストは 1〜300 文字で入れてください")
    image_id = uuid.uuid4()
    key = f"images/{image_id}.{processed.ext}"
    conn.execute(
        "INSERT INTO images (id, storage_key, mime_type, byte_size, width, height, sha256, alt, origin, owner_garden_account_id, demo_key, status) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'uploading')",
        (image_id, key, processed.mime_type, len(processed.data), processed.width, processed.height, processed.sha256, alt, origin, owner_garden_id, demo_key),
    )
    conn.commit()
    try:
        storage.put(key, processed.data, processed.mime_type)
        conn.execute("UPDATE images SET status = 'approved', approved_at = now(), status_changed_at = now() WHERE id = %s AND status = 'uploading'", (image_id,))
        conn.commit()
    except Exception:
        _rollback_quietly(conn)
        try:  # 補償: 作りかけの行と実体を消す。消せなければ uploading のまま残り、reconcile が報告する
            storage.delete(key)
            conn.execute("DELETE FROM images WHERE id = %s AND status = 'uploading'", (image_id,))
            conn.commit()
        except Exception:  # noqa: BLE001
            _rollback_quietly(conn)
            log.warning("登録の途中で失敗し、片付けも失敗しました。reconcile が報告します image_id=%s", image_id)
        raise
    return image_id


def complete_upload(conn, storage: Storage, image_id: uuid.UUID) -> str:
    """登録の途中で止まった画像（uploading）を片付ける。実体があり sha256 が一致すれば公開中にし、無ければ（または違えば）deleted にして実体を消す。
    戻り値は新しい状態（approved / deleted）。uploading でなければ何もせず、今の状態を返す。"""
    row = conn.execute("SELECT status, storage_key, sha256 FROM images WHERE id = %s", (image_id,)).fetchone()
    if row is None:
        raise ImageConflict("画像が見つかりません")
    if row["status"] != "uploading":
        return row["status"]
    try:
        ok = storage.exists(row["storage_key"]) and hashlib.sha256(storage.get(row["storage_key"])).hexdigest() == row["sha256"]
    except StorageError:
        ok = False
    if ok:
        conn.execute("UPDATE images SET status = 'approved', approved_at = now(), status_changed_at = now() WHERE id = %s AND status = 'uploading'", (image_id,))
        conn.commit()
        return "approved"
    # demo_key は空けて、同じキーでやり直せるようにする
    conn.execute("UPDATE images SET status = 'deleted', status_changed_at = now(), deleted_at = now(), demo_key = NULL WHERE id = %s AND status = 'uploading'", (image_id,))
    conn.commit()
    delete_object(storage, row["storage_key"])
    return "deleted"


def reject_image(conn, storage: Storage, image_id: uuid.UUID) -> None:
    """運営の取り下げ（公開後の安全弁）。DB を先に rejected にし（ヒーローの印も外れる）、実体を消す。"""
    row = conn.execute(
        "UPDATE images SET status = 'rejected', status_changed_at = now() WHERE id = %s AND status IN ('pending', 'publishing', 'approved') RETURNING storage_key",
        (image_id,),
    ).fetchone()
    conn.commit()
    if row is None:
        raise ImageConflict("取り下げできる状態の画像ではありません")
    storage.delete(row["storage_key"])  # 失敗しても、DB は rejected で公開されない。残った実体は reconcile が報告する


def unlink_if_unused(conn, image_id: uuid.UUID) -> str | None:
    """どこからも参照されなくなった画像を deleted にして、消す実体の保存キーを返す（参照が残っていれば None）。
    コミットはしない。呼び出し側が、求人から外す操作と一緒に commit したあとで、delete_object で実体を消す。"""
    row = conn.execute(
        "UPDATE images SET status = 'deleted', status_changed_at = now(), deleted_at = now(), deletion_requested_at = now() "
        "WHERE id = %s AND status <> 'deleted' "
        "AND NOT EXISTS (SELECT 1 FROM recruit_images WHERE image_id = %s) AND NOT EXISTS (SELECT 1 FROM garden_images WHERE image_id = %s) RETURNING storage_key",
        (image_id, image_id, image_id),
    ).fetchone()
    return row["storage_key"] if row else None


def delete_object(storage: Storage, key: str | None) -> None:
    """DB の確定のあとで実体を消す。失敗しても例外にしない（利用者の操作は成功しており、残った実体は reconcile が報告する）。"""
    if key is None:
        return
    try:
        storage.delete(key)
    except StorageError:
        log.warning("画像の実体を消せませんでした。reconcile が報告します key=%s", key)


UNREFERENCED = "NOT EXISTS (SELECT 1 FROM recruit_images ri WHERE ri.image_id = i.id) AND NOT EXISTS (SELECT 1 FROM garden_images gi WHERE gi.image_id = i.id)"


def reconcile(conn, storage: Storage, *, stuck_hours: int = 1, out=print) -> dict[str, int]:
    """DB とストレージの食い違いを探して報告する。何も変えない（削除も、状態の変更もしない）。
    検出するもの: stuck_uploading（登録が途中で止まっている）、orphan_objects（DB に行のない実体）、stray_objects（取り下げ・削除済みなのに残っている実体）、
    unreferenced（どこからも使われていない公開中の画像）。登録・公開の最中かもしれないので、新しいもの（10 分以内、unreferenced と stuck は stuck_hours 以内）は数えない。"""
    now = datetime.now(UTC)
    stuck_before = now - timedelta(hours=stuck_hours)
    counts = {"stuck_uploading": 0, "orphan_objects": 0, "stray_objects": 0, "unreferenced": 0}

    for row in conn.execute("SELECT id FROM images WHERE status = 'uploading' AND status_changed_at < %s", (stuck_before,)).fetchall():
        counts["stuck_uploading"] += 1
        out(f"検出: 登録が途中で止まっている画像 {row['id']}")

    known = {r["storage_key"]: r["status"] for r in conn.execute("SELECT storage_key, status FROM images").fetchall()}
    for key, modified in storage.list_keys("images/"):
        if modified > now - timedelta(minutes=10):
            continue  # 登録の最中かもしれない
        status = known.get(key)
        if status is None:
            counts["orphan_objects"] += 1
            out(f"検出: DB に行のない実体 {key}")
        elif status not in ("approved", "uploading"):
            counts["stray_objects"] += 1
            out(f"検出: 公開されないはずの実体が残っています {key}（状態 {status}）")

    for row in conn.execute(
        f"SELECT i.id FROM images i WHERE i.status = 'approved' AND {UNREFERENCED} AND i.created_at < %s",  # noqa: S608
        (stuck_before,),
    ).fetchall():
        counts["unreferenced"] += 1
        out(f"検出: どこからも使われていない公開中の画像 {row['id']}")
    return counts
