import io
import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from PIL import Image

from app import image_service as svc
from app.storage import LocalStorage, S3Storage, StorageError
from tests.conftest import TEST_URL
from tests.imagefiles import make_animated_png, make_image

MAX = 5 * 1024 * 1024


# ---- 検証・メタデータの除去（DB 不要）----


def test_jpeg_png_webp_are_accepted_and_reencoded():
    for fmt, mime in (("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")):
        p = svc.process_image(make_image(fmt), max_bytes=MAX)
        assert p.mime_type == mime and (p.width, p.height) == (640, 360) and len(p.sha256) == 64


def test_exif_gps_and_png_text_are_stripped():
    p = svc.process_image(make_image("JPEG", exif=True), max_bytes=MAX)
    assert not dict(Image.open(io.BytesIO(p.data)).getexif())
    assert b"SecretCamera" not in p.data
    q = svc.process_image(make_image("PNG", text_chunk=True), max_bytes=MAX)
    assert b"secret-author" not in q.data and not Image.open(io.BytesIO(q.data)).info.get("Author")


def test_exif_orientation_is_applied_before_stripping():
    img = Image.new("RGB", (400, 300), "white")
    e = Image.Exif()
    e[0x0112] = 6  # 90 度回転して表示
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=e)
    p = svc.process_image(buf.getvalue(), max_bytes=MAX)
    assert (p.width, p.height) == (300, 400)


def test_large_image_is_downscaled():
    p = svc.process_image(make_image("JPEG", (3600, 2400)), max_bytes=MAX * 10)
    assert max(p.width, p.height) == svc.OUT_MAX_EDGE


@pytest.mark.parametrize(
    "raw, reason",
    [
        (b"", "空"),
        (b"GIF89a" + b"\x00" * 100, "読み込めません"),
        (b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", "読み込めません"),
        (b"%PDF-1.4 fake", "読み込めません"),
        (make_image("JPEG")[:200], "読み込めません"),  # 途中で切れている
        (make_image("JPEG", (100, 100)), "短辺"),
        (make_animated_png(), "アニメーション"),
    ],
)
def test_invalid_images_are_rejected(raw, reason):
    with pytest.raises(svc.ImageRejected, match=reason):
        svc.process_image(raw, max_bytes=MAX)


def test_gif_is_rejected_even_when_it_is_a_real_gif():
    buf = io.BytesIO()
    Image.new("RGB", (300, 300), "red").save(buf, "GIF")
    with pytest.raises(svc.ImageRejected):
        svc.process_image(buf.getvalue(), max_bytes=MAX)


def test_oversize_is_rejected_by_bytes_and_by_pixels(monkeypatch):
    with pytest.raises(svc.ImageRejected, match="MB"):
        svc.process_image(make_image("JPEG", (1200, 800)), max_bytes=1000)
    monkeypatch.setattr(svc, "MAX_PIXELS", 100_000)
    with pytest.raises(svc.ImageRejected, match="画素数"):
        svc.process_image(make_image("JPEG", (640, 360)), max_bytes=MAX)


# ---- 保存部品 ----


def test_local_storage_never_overwrites_and_blocks_traversal(tmp_path):
    st = LocalStorage(tmp_path)
    st.put("images/a.jpg", b"one", "image/jpeg", public=False)
    st.put("images/a.jpg", b"one", "image/jpeg", public=False)  # 同じ内容の再試行は成功
    with pytest.raises(StorageError):
        st.put("images/a.jpg", b"two", "image/jpeg", public=False)
    assert st.get("images/a.jpg", public=False) == b"one"
    for bad in ("../x.jpg", "images/../../x.jpg", "/etc/passwd", "images//a.jpg", "a" * 300):
        with pytest.raises(StorageError):
            st.put(bad, b"x", "image/jpeg", public=True)
    assert not st.exists("images/a.jpg", public=True)  # 非公開に置いたものは、公開側に見えない


def test_s3_storage_behaves_like_local_with_two_buckets():
    import boto3
    from moto import mock_aws

    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="x")
        client.create_bucket(Bucket="pub")
        client.create_bucket(Bucket="priv")
        st = S3Storage(endpoint_url="", public_bucket="pub", private_bucket="priv", access_key_id="x", secret_access_key="x", public_base_url="https://img.example.test/", client=client)
        st.put("images/a.jpg", b"one", "image/jpeg", public=False)
        assert st.exists("images/a.jpg", public=False) and not st.exists("images/a.jpg", public=True)
        st.put("images/a.jpg", b"one", "image/jpeg", public=False)
        with pytest.raises(StorageError):
            st.put("images/a.jpg", b"two", "image/jpeg", public=False)
        st.put("images/a.jpg", b"one", "image/jpeg", public=True)
        head = client.head_object(Bucket="pub", Key="images/a.jpg")
        assert "immutable" in head["CacheControl"]
        assert [k for k, _ in st.list_keys("images/", public=True)] == ["images/a.jpg"]
        st.delete("images/a.jpg", public=True)
        st.delete("images/a.jpg", public=True)  # 無いキーの削除も成功
        assert not st.exists("images/a.jpg", public=True)
        assert st.public_url("images/a.jpg") == "https://img.example.test/images/a.jpg"
        with pytest.raises(StorageError):
            S3Storage(endpoint_url="", public_bucket="same", private_bucket="same", access_key_id="x", secret_access_key="x", public_base_url="https://x", client=client)


def test_s3_errors_never_leak_credentials():
    class Boom:
        def head_object(self, **_):
            raise RuntimeError("AKIAEXAMPLEKEY secret-value https://signed.example/?X-Amz-Signature=abc")

    st = S3Storage(endpoint_url="", public_bucket="a", private_bucket="b", access_key_id="x", secret_access_key="x", public_base_url="https://x", client=Boom())
    with pytest.raises(StorageError) as e:
        st.exists("images/a.jpg", public=True)
    assert "AKIA" not in str(e.value) and "Signature" not in str(e.value) and e.value.__cause__ is None


# ---- 登録・承認・補償・掃除（DB が要る）----

needs_db = pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL が未設定です")


@pytest.fixture
def env(client, tmp_path):
    """画像のテスト用: 空の保存先と、画像の表を空にした DB の接続。"""
    from psycopg.rows import dict_row

    from app.settings import database_url

    storage = LocalStorage(tmp_path)
    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        for table in ("recruit_images", "garden_images", "images"):
            conn.execute(f"DELETE FROM {table}")  # noqa: S608（テスト用 DB の固定の表名）
        conn.commit()
        yield conn, storage


def prepared(conn, storage, **kw):
    p = svc.process_image(make_image(seed=kw.pop("seed", 1)), max_bytes=MAX)
    return p, svc.register_image(conn, storage, p, alt=kw.pop("alt", "テスト"), origin="generated", **kw)


@needs_db
def test_register_is_private_until_approved_then_public(env):
    conn, storage = env
    p, image_id = prepared(conn, storage)
    row = conn.execute("SELECT * FROM images WHERE id = %s", (image_id,)).fetchone()
    assert row["status"] == "pending" and row["storage_key"] == f"images/{image_id}.jpg" and row["byte_size"] == len(p.data) and row["sha256"] == p.sha256
    assert storage.exists(row["storage_key"], public=False) and not storage.exists(row["storage_key"], public=True)
    svc.approve_image(conn, storage, image_id)
    assert conn.execute("SELECT status FROM images WHERE id = %s", (image_id,)).fetchone()["status"] == "approved"
    assert storage.exists(row["storage_key"], public=True)
    with pytest.raises(svc.ImageConflict):
        svc.approve_image(conn, storage, image_id)


@needs_db
def test_registration_failure_in_storage_leaves_no_row(env):
    conn, storage = env

    class FailingPut(LocalStorage):
        def put(self, *a, **k):
            raise StorageError("down")

    p = svc.process_image(make_image(), max_bytes=MAX)
    with pytest.raises(StorageError):
        svc.register_image(conn, FailingPut(storage.root), p, alt="x", origin="uploaded")
    assert conn.execute("SELECT count(*) AS n FROM images").fetchone()["n"] == 0


@needs_db
def test_approval_failure_compensates_and_retry_succeeds(env):
    conn, storage = env
    _, image_id = prepared(conn, storage)

    class FailOncePublic(LocalStorage):
        failed = False

        def exists(self, key, *, public):
            if public and not self.failed:
                self.failed = True
                return False  # 複製の確認に失敗したことにする
            return super().exists(key, public=public)

    flaky = FailOncePublic(storage.root)
    with pytest.raises(StorageError):
        svc.approve_image(conn, flaky, image_id)
    row = conn.execute("SELECT status, storage_key FROM images WHERE id = %s", (image_id,)).fetchone()
    assert row["status"] == "pending" and not storage.exists(row["storage_key"], public=True)  # 食い違いを残さない
    svc.approve_image(conn, flaky, image_id)  # 再試行
    assert conn.execute("SELECT status FROM images WHERE id = %s", (image_id,)).fetchone()["status"] == "approved"


@needs_db
def test_approval_detects_tampered_private_object(env):
    conn, storage = env
    _, image_id = prepared(conn, storage)
    key = conn.execute("SELECT storage_key FROM images WHERE id = %s", (image_id,)).fetchone()["storage_key"]
    (storage.root / "private" / key).write_bytes(b"tampered")
    with pytest.raises(svc.ImageConflict, match="一致しません"):
        svc.approve_image(conn, storage, image_id)
    assert conn.execute("SELECT status FROM images WHERE id = %s", (image_id,)).fetchone()["status"] == "pending"
    assert not storage.exists(key, public=True)


@needs_db
def test_reject_removes_public_copy_and_clears_hero(env):
    conn, storage = env
    _, image_id = prepared(conn, storage)
    svc.approve_image(conn, storage, image_id)
    recruit = conn.execute("SELECT id FROM recruits ORDER BY id LIMIT 1").fetchone()["id"]
    conn.execute("INSERT INTO recruit_images (recruit_id, image_id, position, is_hero) VALUES (%s, %s, 0, true)", (recruit, image_id))
    conn.commit()
    svc.reject_image(conn, storage, image_id)
    key = f"images/{image_id}.jpg"
    assert not storage.exists(key, public=True) and storage.exists(key, public=False)
    assert conn.execute("SELECT is_hero FROM recruit_images WHERE image_id = %s", (image_id,)).fetchone()["is_hero"] is False


@needs_db
def test_db_refuses_hero_for_unapproved_image_and_second_hero_and_delete_of_referenced(env):
    conn, storage = env
    _, a = prepared(conn, storage, seed=1)
    _, b = prepared(conn, storage, seed=2)
    svc.approve_image(conn, storage, a)
    svc.approve_image(conn, storage, b)
    _, pending = prepared(conn, storage, seed=3)
    recruit = conn.execute("SELECT id FROM recruits ORDER BY id LIMIT 1").fetchone()["id"]
    conn.execute("INSERT INTO recruit_images (recruit_id, image_id, position, is_hero) VALUES (%s, %s, 0, true)", (recruit, a))
    conn.commit()
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("INSERT INTO recruit_images (recruit_id, image_id, position, is_hero) VALUES (%s, %s, 1, true)", (recruit, pending))
    conn.rollback()
    with pytest.raises(psycopg.errors.UniqueViolation):  # ヒーローは 1 枚だけ
        conn.execute("INSERT INTO recruit_images (recruit_id, image_id, position, is_hero) VALUES (%s, %s, 1, true)", (recruit, b))
    conn.rollback()
    with pytest.raises(psycopg.errors.ForeignKeyViolation):  # 参照中の画像の行は消せない
        conn.execute("DELETE FROM images WHERE id = %s", (a,))
    conn.rollback()


@needs_db
def test_reconcile_dry_run_changes_nothing_and_apply_never_touches_referenced(env):
    conn, storage = env
    _, used = prepared(conn, storage, seed=1)
    _, unused = prepared(conn, storage, seed=2)
    _, requested = prepared(conn, storage, seed=3)
    svc.approve_image(conn, storage, requested)
    recruit = conn.execute("SELECT id FROM recruits ORDER BY id LIMIT 1").fetchone()["id"]
    conn.execute("INSERT INTO recruit_images (recruit_id, image_id, position) VALUES (%s, %s, 0)", (recruit, used))
    old = datetime.now(UTC) - timedelta(days=40)
    conn.execute("UPDATE images SET created_at = %s", (old,))
    conn.execute("UPDATE images SET deletion_requested_at = %s WHERE id = %s", (old, requested))
    conn.commit()

    def snapshot():
        return sorted((str(r["id"]), r["status"]) for r in conn.execute("SELECT id, status FROM images").fetchall()), sorted(
            k for k, _ in storage.list_keys("images/", public=False)
        ) + sorted(k for k, _ in storage.list_keys("images/", public=True))

    before = snapshot()
    counts = svc.reconcile(conn, storage, apply=False, out=lambda *_: None)
    assert counts["deletable"] == 2 and snapshot() == before  # dry-run は何も変えない

    # 猶予内なら、何もしない
    assert svc.reconcile(conn, storage, apply=True, grace_days=60, out=lambda *_: None)["deletable"] == 0
    svc.reconcile(conn, storage, apply=True, out=lambda *_: None)
    statuses = {str(r["id"]): r["status"] for r in conn.execute("SELECT id, status FROM images").fetchall()}
    assert statuses[str(used)] == "pending"  # 参照中は残る
    assert statuses[str(unused)] == statuses[str(requested)] == "deleted"
    for image_id in (unused, requested):
        assert not storage.exists(f"images/{image_id}.jpg", public=False) and not storage.exists(f"images/{image_id}.jpg", public=True)
    assert storage.exists(f"images/{used}.jpg", public=False)


@needs_db
def test_reconcile_fixes_stuck_states_and_stray_public_objects(env):
    conn, storage = env
    # 1) 登録が途中で止まった（実体はある）→ pending に進める
    p = svc.process_image(make_image(seed=5), max_bytes=MAX)
    stuck = uuid.uuid4()
    key = f"images/{stuck}.jpg"
    conn.execute(
        "INSERT INTO images (id, storage_key, mime_type, byte_size, width, height, sha256, alt, origin, status, status_changed_at) "
        "VALUES (%s, %s, 'image/jpeg', %s, %s, %s, %s, 'x', 'uploaded', 'uploading', now() - interval '3 hours')",
        (stuck, key, len(p.data), p.width, p.height, p.sha256),
    )
    conn.commit()
    storage.put(key, p.data, "image/jpeg", public=False)
    # 2) 実体のない uploading → deleted
    lost = uuid.uuid4()
    conn.execute(
        "INSERT INTO images (id, storage_key, mime_type, byte_size, width, height, sha256, alt, origin, status, status_changed_at) "
        "VALUES (%s, %s, 'image/jpeg', 10, 300, 300, %s, 'x', 'uploaded', 'uploading', now() - interval '3 hours')",
        (lost, f"images/{lost}.jpg", "0" * 64),
    )
    # 3) 公開の途中で止まった → 承認をやり直す
    _, publishing = prepared(conn, storage, seed=6)
    conn.execute("UPDATE images SET status = 'publishing', status_changed_at = now() - interval '3 hours' WHERE id = %s", (publishing,))
    # 4) 却下済みなのに公開側に実体が残っている → 消す
    _, rejected = prepared(conn, storage, seed=7)
    svc.approve_image(conn, storage, rejected)
    conn.execute("UPDATE images SET status = 'rejected' WHERE id = %s", (rejected,))
    conn.commit()
    old = datetime.now(UTC) - timedelta(hours=1)
    import os

    for pub_key in (f"images/{rejected}.jpg",):
        path = storage.root / "public" / pub_key
        os.utime(path, (old.timestamp(), old.timestamp()))
    svc.reconcile(conn, storage, apply=True, out=lambda *_: None)
    status = {str(r["id"]): r["status"] for r in conn.execute("SELECT id, status FROM images").fetchall()}
    assert status[str(stuck)] == "pending" and status[str(lost)] == "deleted" and status[str(publishing)] == "approved"
    assert not storage.exists(f"images/{rejected}.jpg", public=True)
