import io
import os
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
    st.put("images/a.jpg", b"one", "image/jpeg")
    st.put("images/a.jpg", b"one", "image/jpeg")  # 同じ内容の再試行は成功
    with pytest.raises(StorageError):
        st.put("images/a.jpg", b"two", "image/jpeg")
    assert st.get("images/a.jpg") == b"one"
    for bad in ("../x.jpg", "images/../../x.jpg", "/etc/passwd", "images//a.jpg", "a" * 300):
        with pytest.raises(StorageError):
            st.put(bad, b"x", "image/jpeg")
    assert st.exists("images/a.jpg") and [k for k, _ in st.list_keys("images/")] == ["images/a.jpg"]
    st.delete("images/a.jpg")
    st.delete("images/a.jpg")  # 無いキーの削除も成功
    assert not st.exists("images/a.jpg")
    assert not (tmp_path / "private").exists()  # 非公開側は作らない


def test_s3_storage_uses_one_bucket():
    import boto3
    from moto import mock_aws

    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="x")
        client.create_bucket(Bucket="images")
        st = S3Storage(endpoint_url="", bucket="images", access_key_id="x", secret_access_key="x", public_base_url="https://img.example.test/", client=client)
        st.put("images/a.jpg", b"one", "image/jpeg")
        assert st.exists("images/a.jpg") and st.get("images/a.jpg") == b"one"
        st.put("images/a.jpg", b"one", "image/jpeg")  # 同じ内容の再試行は成功
        with pytest.raises(StorageError):
            st.put("images/a.jpg", b"two", "image/jpeg")
        head = client.head_object(Bucket="images", Key="images/a.jpg")
        assert "immutable" in head["CacheControl"] and head["ContentType"] == "image/jpeg"
        assert [k for k, _ in st.list_keys("images/")] == ["images/a.jpg"] and list(st.list_keys("other/")) == []
        st.delete("images/a.jpg")
        st.delete("images/a.jpg")  # 無いキーの削除も成功
        assert not st.exists("images/a.jpg")
        with pytest.raises(StorageError, match="見つかりません"):
            st.get("images/a.jpg")
        assert st.public_url("images/a.jpg") == "https://img.example.test/images/a.jpg"
        with pytest.raises(StorageError):
            st.put("../x.jpg", b"x", "image/jpeg")


def test_s3_errors_never_leak_credentials():
    class Boom:
        def head_object(self, **_):
            raise RuntimeError("AKIAEXAMPLEKEY secret-value https://signed.example/?X-Amz-Signature=abc")

    st = S3Storage(endpoint_url="", bucket="b", access_key_id="x", secret_access_key="x", public_base_url="https://x", client=Boom())
    with pytest.raises(StorageError) as e:
        st.exists("images/a.jpg")
    assert "AKIA" not in str(e.value) and "Signature" not in str(e.value) and e.value.__cause__ is None


def test_make_storage_s3_needs_one_bucket_and_never_falls_back_to_local(monkeypatch, tmp_path):
    from app import storage

    for name in ("STORAGE_S3_ENDPOINT_URL", "STORAGE_S3_BUCKET", "STORAGE_S3_ACCESS_KEY_ID", "STORAGE_S3_SECRET_ACCESS_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("IMAGE_PUBLIC_BASE_URL", "https://img.example.test")
    with pytest.raises(RuntimeError, match="STORAGE_S3_ENDPOINT_URL"):
        storage.make_storage()
    monkeypatch.setenv("STORAGE_S3_ENDPOINT_URL", "https://example.invalid")
    with pytest.raises(RuntimeError, match="STORAGE_S3_BUCKET"):  # 旧い 2 バケットの名前では通らない
        monkeypatch.setenv("STORAGE_S3_PUBLIC_BUCKET", "old-public")
        monkeypatch.setenv("STORAGE_S3_PRIVATE_BUCKET", "old-private")
        storage.make_storage()
    monkeypatch.setenv("STORAGE_S3_BUCKET", "images")
    monkeypatch.setenv("STORAGE_S3_ACCESS_KEY_ID", "x")
    monkeypatch.setenv("STORAGE_S3_SECRET_ACCESS_KEY", "x")
    made = storage.make_storage()
    assert isinstance(made, S3Storage) and made.bucket == "images" and made.public_url("images/a.jpg") == "https://img.example.test/images/a.jpg"


# ---- 登録・取り下げ・削除・点検（DB が要る）----

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


def first_recruit(conn) -> int:
    return conn.execute("SELECT id FROM recruits ORDER BY id LIMIT 1").fetchone()["id"]


def age(storage, key, *, minutes=60):
    old = (datetime.now(UTC) - timedelta(minutes=minutes)).timestamp()
    os.utime(storage.root / "public" / key, (old, old))


@needs_db
def test_register_publishes_immediately(env):
    conn, storage = env
    p, image_id = prepared(conn, storage)
    row = conn.execute("SELECT * FROM images WHERE id = %s", (image_id,)).fetchone()
    assert row["status"] == "approved" and row["approved_at"] is not None  # 承認の段階は無い
    assert row["storage_key"] == f"images/{image_id}.jpg" and row["byte_size"] == len(p.data) and row["sha256"] == p.sha256
    assert storage.get(row["storage_key"]) == p.data  # そのまま公開 URL で読める場所にある
    assert not hasattr(svc, "approve_image")


@needs_db
def test_every_registration_gets_a_new_key(env):
    conn, storage = env
    _, a = prepared(conn, storage, seed=1)
    _, b = prepared(conn, storage, seed=1)  # 同じ内容でも、別の画像として登録する（既存のキーは再利用しない）
    keys = [r["storage_key"] for r in conn.execute("SELECT storage_key FROM images").fetchall()]
    assert a != b and len(set(keys)) == 2


@needs_db
def test_registration_failure_in_storage_leaves_no_row_and_no_object(env):
    conn, storage = env

    class FailingPut(LocalStorage):
        def put(self, *a, **k):
            raise StorageError("down")

    p = svc.process_image(make_image(), max_bytes=MAX)
    with pytest.raises(StorageError):
        svc.register_image(conn, FailingPut(storage.root), p, alt="x", origin="uploaded")
    assert conn.execute("SELECT count(*) AS n FROM images").fetchone()["n"] == 0
    assert list(storage.list_keys("images/")) == []


@needs_db
def test_failure_after_saving_removes_the_object_too(env):
    conn, storage = env
    p = svc.process_image(make_image(), max_bytes=MAX)

    class DbDiesAfterPut:
        """保存のあとの DB 更新が失敗した状況（接続が切れた、など）。"""

        def __init__(self, inner):
            self.inner = inner
            self.calls = 0

        def execute(self, sql, params=None):
            if sql.startswith("UPDATE images SET status = 'approved'"):
                raise psycopg.OperationalError("lost")
            return self.inner.execute(sql, params)

        def commit(self):
            return self.inner.commit()

        def rollback(self):
            return self.inner.rollback()

    with pytest.raises(psycopg.OperationalError):
        svc.register_image(DbDiesAfterPut(conn), storage, p, alt="x", origin="uploaded")
    assert conn.execute("SELECT count(*) AS n FROM images").fetchone()["n"] == 0
    assert list(storage.list_keys("images/")) == []


@needs_db
def test_complete_upload_publishes_a_whole_object_and_removes_a_lost_one(env):
    conn, storage = env
    p = svc.process_image(make_image(seed=5), max_bytes=MAX)
    ok, lost = uuid.uuid4(), uuid.uuid4()
    for image_id, sha, demo in ((ok, p.sha256, "k-ok"), (lost, "0" * 64, "k-lost")):
        conn.execute(
            "INSERT INTO images (id, storage_key, mime_type, byte_size, width, height, sha256, alt, origin, status, demo_key) "
            "VALUES (%s, %s, 'image/jpeg', %s, %s, %s, %s, 'x', 'generated', 'uploading', %s)",
            (image_id, f"images/{image_id}.jpg", len(p.data), p.width, p.height, sha, demo),
        )
    conn.commit()
    storage.put(f"images/{ok}.jpg", p.data, "image/jpeg")
    assert svc.complete_upload(conn, storage, ok) == "approved"
    assert svc.complete_upload(conn, storage, ok) == "approved"  # 2 回目は何もしない
    assert svc.complete_upload(conn, storage, lost) == "deleted"
    assert conn.execute("SELECT demo_key FROM images WHERE id = %s", (lost,)).fetchone()["demo_key"] is None  # 同じキーでやり直せる
    with pytest.raises(svc.ImageConflict):
        svc.complete_upload(conn, storage, uuid.uuid4())


@needs_db
def test_reject_is_a_takedown_that_removes_the_object_and_clears_hero(env):
    conn, storage = env
    _, image_id = prepared(conn, storage)
    recruit = first_recruit(conn)
    conn.execute("INSERT INTO recruit_images (recruit_id, image_id, position, is_hero) VALUES (%s, %s, 0, true)", (recruit, image_id))
    conn.commit()
    svc.reject_image(conn, storage, image_id)
    key = f"images/{image_id}.jpg"
    assert not storage.exists(key)
    assert conn.execute("SELECT status FROM images WHERE id = %s", (image_id,)).fetchone()["status"] == "rejected"
    assert conn.execute("SELECT is_hero FROM recruit_images WHERE image_id = %s", (image_id,)).fetchone()["is_hero"] is False
    with pytest.raises(svc.ImageConflict):
        svc.reject_image(conn, storage, image_id)  # 取り下げ済みを、もう一度は取り下げられない


@needs_db
def test_reject_stays_rejected_even_if_the_object_cannot_be_removed(env):
    conn, storage = env
    _, image_id = prepared(conn, storage)

    class StuckDelete(LocalStorage):
        def delete(self, key):
            raise StorageError("down")

    with pytest.raises(StorageError):
        svc.reject_image(conn, StuckDelete(storage.root), image_id)
    assert conn.execute("SELECT status FROM images WHERE id = %s", (image_id,)).fetchone()["status"] == "rejected"  # 公開 API には出ない
    assert svc.reconcile(conn, storage, out=lambda *_: None)["stray_objects"] == 0  # 10 分以内の実体は数えない
    age(storage, f"images/{image_id}.jpg")
    assert svc.reconcile(conn, storage, out=lambda *_: None)["stray_objects"] == 1  # 残った実体は、点検が報告する


@needs_db
def test_unlink_if_unused_deletes_in_place_only_when_nothing_refers_to_the_image(env):
    conn, storage = env
    _, used = prepared(conn, storage, seed=1)
    _, unused = prepared(conn, storage, seed=2)
    recruit = first_recruit(conn)
    conn.execute("INSERT INTO recruit_images (recruit_id, image_id, position) VALUES (%s, %s, 0)", (recruit, used))
    conn.commit()
    assert svc.unlink_if_unused(conn, used) is None  # 参照中は残す
    key = svc.unlink_if_unused(conn, unused)
    conn.commit()
    assert key == f"images/{unused}.jpg"
    row = conn.execute("SELECT status, deleted_at IS NOT NULL AS gone FROM images WHERE id = %s", (unused,)).fetchone()
    assert row == {"status": "deleted", "gone": True}
    assert storage.exists(key)  # 呼び出し側が commit したあとで実体を消す
    svc.delete_object(storage, key)
    assert not storage.exists(key) and storage.exists(f"images/{used}.jpg")
    assert svc.unlink_if_unused(conn, unused) is None  # もう一度呼んでも何も起きない

    class StuckDelete(LocalStorage):
        def delete(self, key):
            raise StorageError("down")

    svc.delete_object(StuckDelete(storage.root), f"images/{used}.jpg")  # 失敗しても例外にしない
    svc.delete_object(storage, None)


@needs_db
def test_db_refuses_hero_for_an_image_that_is_not_published_and_a_second_hero_and_delete_of_referenced(env):
    conn, storage = env
    _, a = prepared(conn, storage, seed=1)
    _, b = prepared(conn, storage, seed=2)
    _, taken_down = prepared(conn, storage, seed=3)
    svc.reject_image(conn, storage, taken_down)
    recruit = first_recruit(conn)
    conn.execute("INSERT INTO recruit_images (recruit_id, image_id, position, is_hero) VALUES (%s, %s, 0, true)", (recruit, a))
    conn.commit()
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("INSERT INTO recruit_images (recruit_id, image_id, position, is_hero) VALUES (%s, %s, 1, true)", (recruit, taken_down))
    conn.rollback()
    with pytest.raises(psycopg.errors.UniqueViolation):  # ヒーローは 1 枚だけ
        conn.execute("INSERT INTO recruit_images (recruit_id, image_id, position, is_hero) VALUES (%s, %s, 1, true)", (recruit, b))
    conn.rollback()
    with pytest.raises(psycopg.errors.ForeignKeyViolation):  # 参照中の画像の行は消せない
        conn.execute("DELETE FROM images WHERE id = %s", (a,))
    conn.rollback()


@needs_db
def test_reconcile_only_reports_and_never_changes_anything(env):
    conn, storage = env
    recruit = first_recruit(conn)
    _, used = prepared(conn, storage, seed=1)
    conn.execute("INSERT INTO recruit_images (recruit_id, image_id, position) VALUES (%s, %s, 0)", (recruit, used))
    _, unreferenced = prepared(conn, storage, seed=2)  # どこからも使われていない公開中の画像
    _, taken_down = prepared(conn, storage, seed=3)
    conn.execute("UPDATE images SET status = 'rejected' WHERE id = %s", (taken_down,))  # 取り下げ済みだが、実体が残った
    # 登録が途中で止まった行（実体あり）
    stuck = uuid.uuid4()
    p = svc.process_image(make_image(seed=5), max_bytes=MAX)
    conn.execute(
        "INSERT INTO images (id, storage_key, mime_type, byte_size, width, height, sha256, alt, origin, status, status_changed_at) "
        "VALUES (%s, %s, 'image/jpeg', %s, %s, %s, %s, 'x', 'uploaded', 'uploading', now() - interval '3 hours')",
        (stuck, f"images/{stuck}.jpg", len(p.data), p.width, p.height, p.sha256),
    )
    conn.execute("UPDATE images SET created_at = now() - interval '3 hours'")
    conn.commit()
    # DB に行のない実体
    orphan = f"images/{uuid.uuid4()}.jpg"
    storage.put(orphan, b"orphan", "image/jpeg")
    for key, _ in list(storage.list_keys("images/")):
        age(storage, key)

    def snapshot():
        rows = sorted((str(r["id"]), r["status"], r["demo_key"], r["deleted_at"]) for r in conn.execute("SELECT id, status, demo_key, deleted_at FROM images").fetchall())
        return rows, sorted(k for k, _ in storage.list_keys("images/"))

    before = snapshot()
    lines: list[str] = []
    counts = svc.reconcile(conn, storage, out=lines.append)
    assert counts == {"stuck_uploading": 1, "orphan_objects": 1, "stray_objects": 1, "unreferenced": 1}
    assert len(lines) == 4 and all(line.startswith("検出") for line in lines)
    assert snapshot() == before  # 何も変えない（DB も、保存先も）
    with pytest.raises(TypeError):
        svc.reconcile(conn, storage, apply=True)  # 実行（削除）の指定は、もう無い


@needs_db
def test_reconcile_skips_objects_and_rows_that_are_still_being_written(env):
    conn, storage = env
    storage.put(f"images/{uuid.uuid4()}.jpg", b"fresh", "image/jpeg")  # 作ったばかりの実体
    _, fresh = prepared(conn, storage, seed=9)  # 作ったばかりの公開中の画像（まだ求人に結べていない最中かもしれない）
    assert svc.reconcile(conn, storage, out=lambda *_: None) == {"stuck_uploading": 0, "orphan_objects": 0, "stray_objects": 0, "unreferenced": 0}
    assert fresh
