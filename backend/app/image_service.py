"""画像の検証・登録・承認・掃除（API・CLI・seed が同じものを使う）。

登録（register）: 検証（process_image）→ DB に uploading で記録 → 非公開側へ保存 → pending。
承認（approve。運営だけ）: publishing → 公開側へ複製して確認 → approved。途中で失敗したら、公開側の複製を消して pending へ戻す。
どの途中で止まっても、状態は reconcile（掃除。既定は dry-run）が整える。DB とストレージが食い違ったままにならないための設計:
- 先に DB へ意図（uploading / publishing）を書き、そのあとストレージを触る。ストレージの操作は何度やっても同じ結果になる。
- 公開側にあるのは approved（または公開の途中の publishing）の画像だけ。それ以外の公開側の実体は reconcile が消す。
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
    """状態が合わず、操作できない（承認済みでないものをヒーローにする、など）。メッセージは固定の説明。"""


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
    """検証済みの画像を、非公開側に pending で登録する（公開はしない）。失敗したら、作りかけの行を消して例外を返す。"""
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
        storage.put(key, processed.data, processed.mime_type, public=False)
        conn.execute("UPDATE images SET status = 'pending', status_changed_at = now() WHERE id = %s AND status = 'uploading'", (image_id,))
        conn.commit()
    except Exception:
        _rollback_quietly(conn)
        try:  # 補償: 作りかけの行と実体を消す。消せなければ uploading のまま残り、reconcile が拾う
            storage.delete(key, public=False)
            conn.execute("DELETE FROM images WHERE id = %s AND status = 'uploading'", (image_id,))
            conn.commit()
        except Exception:  # noqa: BLE001
            _rollback_quietly(conn)
            log.warning("登録の途中で失敗し、片付けも失敗しました。reconcile が整えます image_id=%s", image_id)
        raise
    return image_id


def approve_image(conn, storage: Storage, image_id: uuid.UUID) -> None:
    """運営の承認。非公開側の実体を検査して公開側へ複製し、approved にする。やり直しても同じ結果になる。"""
    row = conn.execute(
        "UPDATE images SET status = 'publishing', status_changed_at = now() WHERE id = %s AND status IN ('pending', 'publishing') "
        "RETURNING storage_key, mime_type, sha256",
        (image_id,),
    ).fetchone()
    conn.commit()
    if row is None:
        raise ImageConflict("承認できる状態の画像ではありません")
    try:
        data = storage.get(row["storage_key"], public=False)
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ImageConflict("保存された画像が、登録時の内容と一致しません")
        storage.put(row["storage_key"], data, row["mime_type"], public=True)
        if not storage.exists(row["storage_key"], public=True):
            raise StorageError("公開側への複製を確認できません")
        done = conn.execute(
            "UPDATE images SET status = 'approved', approved_at = now(), status_changed_at = now() WHERE id = %s AND status = 'publishing'",
            (image_id,),
        )
        conn.commit()
        if done.rowcount == 0:
            raise ImageConflict("承認の途中で状態が変わりました")
    except Exception:
        _rollback_quietly(conn)
        try:  # 補償: 公開側の複製を消して pending へ戻す。戻せなければ publishing のまま残り、reconcile が拾う
            storage.delete(row["storage_key"], public=True)
            conn.execute("UPDATE images SET status = 'pending', status_changed_at = now() WHERE id = %s AND status = 'publishing'", (image_id,))
            conn.commit()
        except Exception:  # noqa: BLE001
            _rollback_quietly(conn)
            log.warning("承認の途中で失敗し、戻す処理も失敗しました。reconcile が整えます image_id=%s", image_id)
        raise


def reject_image(conn, storage: Storage, image_id: uuid.UUID) -> None:
    """運営の却下・公開の取り消し。DB を先に rejected にし（ヒーローの印も外れる）、公開側の実体を消す。"""
    row = conn.execute(
        "UPDATE images SET status = 'rejected', status_changed_at = now() WHERE id = %s AND status IN ('pending', 'publishing', 'approved') "
        "RETURNING storage_key",
        (image_id,),
    ).fetchone()
    conn.commit()
    if row is None:
        raise ImageConflict("却下できる状態の画像ではありません")
    storage.delete(row["storage_key"], public=True)  # 失敗しても、DB は rejected。残った公開側の実体は reconcile が消す


def unlink_if_unused(conn, image_id: uuid.UUID) -> None:
    """どこからも参照されなくなった画像に、削除要求の時刻を付ける（物理削除は猶予のあとの reconcile）。"""
    conn.execute(
        "UPDATE images SET deletion_requested_at = now() WHERE id = %s AND deletion_requested_at IS NULL "
        "AND NOT EXISTS (SELECT 1 FROM recruit_images WHERE image_id = %s) AND NOT EXISTS (SELECT 1 FROM garden_images WHERE image_id = %s)",
        (image_id, image_id, image_id),
    )


UNREFERENCED = "NOT EXISTS (SELECT 1 FROM recruit_images ri WHERE ri.image_id = i.id) AND NOT EXISTS (SELECT 1 FROM garden_images gi WHERE gi.image_id = i.id)"


def reconcile(conn, storage: Storage, *, apply: bool, grace_days: int = 30, stuck_hours: int = 1, out=print) -> dict[str, int]:
    """DB とストレージの食い違い・未参照の画像・未完了の登録を探す。apply=False（既定）は、何も変えずに一覧だけ出す。
    猶予: 未参照や削除要求の画像は grace_days 日、登録・公開の途中は stuck_hours 時間たってから対象にする。参照されている画像は対象にしない。"""
    now = datetime.now(UTC)
    stuck_before = now - timedelta(hours=stuck_hours)
    grace_before = now - timedelta(days=grace_days)
    counts = {"stuck_uploading": 0, "stuck_publishing": 0, "stray_public": 0, "orphan_objects": 0, "deletable": 0}
    verb = "処理" if apply else "対象（dry-run）"

    for row in conn.execute("SELECT id, storage_key, sha256 FROM images WHERE status = 'uploading' AND status_changed_at < %s", (stuck_before,)).fetchall():
        counts["stuck_uploading"] += 1
        out(f"{verb}: 登録が途中で止まっている画像 {row['id']}")
        if apply:
            ok = False
            try:
                ok = storage.exists(row["storage_key"], public=False) and hashlib.sha256(storage.get(row["storage_key"], public=False)).hexdigest() == row["sha256"]
            except StorageError:
                ok = False
            conn.execute(
                "UPDATE images SET status = %s, status_changed_at = now(), deleted_at = CASE WHEN %s THEN NULL ELSE now() END WHERE id = %s AND status = 'uploading'",
                ("pending" if ok else "deleted", ok, row["id"]),
            )
            if not ok:
                storage.delete(row["storage_key"], public=False)
            conn.commit()

    for row in conn.execute("SELECT id FROM images WHERE status = 'publishing' AND status_changed_at < %s", (stuck_before,)).fetchall():
        counts["stuck_publishing"] += 1
        out(f"{verb}: 公開の途中で止まっている画像 {row['id']}（承認をやり直します）")
        if apply:
            try:
                approve_image(conn, storage, row["id"])
            except (ImageConflict, StorageError):
                out(f"  やり直せませんでした: {row['id']}（pending へ戻しました）")

    known = {r["storage_key"]: r["status"] for r in conn.execute("SELECT storage_key, status FROM images").fetchall()}
    for public in (True, False):
        for key, modified in storage.list_keys("images/", public=public):
            status = known.get(key)
            if modified > now - timedelta(minutes=10):
                continue  # 登録・公開の最中かもしれない
            if status is None:
                counts["orphan_objects"] += 1
                out(f"{verb}: DB に行のない{'公開' if public else '非公開'}側の実体 {key}")
                if apply and modified < grace_before:
                    storage.delete(key, public=public)
            elif public and status not in ("approved", "publishing"):
                counts["stray_public"] += 1
                out(f"{verb}: 公開側に残っている未承認の実体 {key}（状態 {status}）")
                if apply:
                    storage.delete(key, public=True)

    candidates = conn.execute(
        f"SELECT i.id, i.storage_key, i.status FROM images i WHERE i.status IN ('pending', 'approved', 'rejected') AND {UNREFERENCED} "  # noqa: S608
        "AND COALESCE(i.deletion_requested_at, i.created_at) < %s",
        (grace_before,),
    ).fetchall()
    for row in candidates:
        counts["deletable"] += 1
        out(f"{verb}: 未参照で猶予を過ぎた画像 {row['id']}（状態 {row['status']}）")
        if apply:
            # 削除の直前にもう一度、参照されていないことを確かめる（その間に結ばれていたら消さない）
            claimed = conn.execute(
                f"UPDATE images i SET status = 'deleted', status_changed_at = now(), deleted_at = now() WHERE i.id = %s AND {UNREFERENCED} "  # noqa: S608
                "AND i.status IN ('pending', 'approved', 'rejected')",
                (row["id"],),
            )
            conn.commit()
            if claimed.rowcount:
                storage.delete(row["storage_key"], public=True)
                storage.delete(row["storage_key"], public=False)
    return counts
