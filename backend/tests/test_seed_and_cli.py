import json
import shutil
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

from app import image_service as svc
from app import images_cli, migrate, seed_demo, seed_images
from app.storage import LocalStorage
from tests.conftest import TEST_URL, load_initial_schema, new_database
from tests.imagefiles import make_image

pytestmark = pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL が未設定です")

SOURCE = Path(__file__).resolve().parents[2] / "frontend" / "public" / "images" / "generated" / "recruits"
FILE_OF_RECRUIT_ID = {1: "1.jpg", 2: "2.jpg", 3: "3.jpg", 4: "4.jpg", 5: "5.jpg", 6: "6.jpg", 7: "7-people.jpg", 8: "8.jpg", 9: "9.jpg", 10: "10.jpg", 11: "11.jpg"}
needs_sources = pytest.mark.skipif(not SOURCE.is_dir(), reason="画像のフォルダーがありません")


@pytest.fixture
def fresh(tmp_path, monkeypatch):
    """マイグレーション済みの空の DB に seed_demo を入れたもの（テストごとに作り直す）。"""
    url = new_database("hj_seed")
    load_initial_schema(url)
    assert migrate.apply(url, out=lambda *_: None) == 0
    monkeypatch.setenv("DATABASE_URL", url)
    seed_demo.main(reset=True)
    with psycopg.connect(url, row_factory=dict_row) as conn:
        yield conn, LocalStorage(tmp_path / "media"), url


def test_every_demo_recruit_has_a_unique_demo_key_matching_the_manifest(fresh):
    conn, _, _ = fresh
    keys = [r["demo_key"] for r in conn.execute("SELECT demo_key FROM recruits ORDER BY id").fetchall()]
    assert len(keys) == 12 and len(set(keys)) == 12 and None not in keys
    manifest = json.loads(seed_images.MANIFEST.read_text(encoding="utf-8"))["images"]
    assert {e["recruit_demo_key"] for e in manifest} <= set(keys)
    assert len({e["demo_key"] for e in manifest}) == len(manifest)


@needs_sources
def test_seed_images_maps_each_image_to_the_right_recruit_and_is_idempotent(fresh):
    conn, storage, _ = fresh
    first = seed_images.seed(conn, storage, source_dir=SOURCE, source_url=None, out=lambda *_: None)
    assert first == {"registered": 11, "linked": 11, "kept": 0, "no_recruit": 0}
    rows = conn.execute(
        "SELECT ri.recruit_id, ri.is_hero, i.status, i.storage_key, i.alt, i.origin FROM recruit_images ri JOIN images i ON i.id = ri.image_id ORDER BY ri.recruit_id"
    ).fetchall()
    assert [r["recruit_id"] for r in rows] == list(range(1, 12))  # 12（非表示のテスト求人）には結ばない
    for r in rows:
        assert r["is_hero"] and r["status"] == "approved" and r["origin"] == "generated" and r["alt"].endswith("（職種名からの演出）")
        expected = svc.process_image((SOURCE / FILE_OF_RECRUIT_ID[r["recruit_id"]]).read_bytes(), max_bytes=20 * 1024 * 1024)
        assert storage.get(r["storage_key"]) == expected.data  # 保存された実体が、その求人用の元画像から作られている
    assert len({r["storage_key"] for r in rows}) == 11
    # 園が並びやヒーローを変えたあとに再実行しても、変えず、増やさない
    conn.execute("UPDATE recruit_images SET is_hero = false WHERE recruit_id = 1")
    conn.commit()
    second = seed_images.seed(conn, storage, source_dir=SOURCE, source_url=None, out=lambda *_: None)
    assert second == {"registered": 0, "linked": 0, "kept": 11, "no_recruit": 0}
    assert conn.execute("SELECT count(*) AS n FROM images").fetchone()["n"] == 11
    assert conn.execute("SELECT count(*) AS n FROM recruit_images").fetchone()["n"] == 11
    assert conn.execute("SELECT is_hero FROM recruit_images WHERE recruit_id = 1").fetchone()["is_hero"] is False


@needs_sources
def test_seed_images_refuses_a_source_whose_checksum_differs(fresh, tmp_path):
    conn, storage, _ = fresh
    src = tmp_path / "src"
    shutil.copytree(SOURCE, src)
    (src / "3.jpg").write_bytes(make_image())  # 別の画像にすり替わっている
    with pytest.raises(SystemExit, match="sha256"):
        seed_images.seed(conn, storage, source_dir=src, source_url=None, out=lambda *_: None)
    conn.rollback()
    assert conn.execute("SELECT count(*) AS n FROM images WHERE demo_key = 'garden-storyteller-hero'").fetchone()["n"] == 0


@needs_sources
def test_seed_images_resumes_after_a_failure_in_the_middle(fresh):
    conn, storage, _ = fresh

    class DiesOnThird(LocalStorage):
        puts = 0

        def put(self, key, data, content_type):
            type(self).puts += 1
            if type(self).puts == 3:
                raise OSError("disk full")
            super().put(key, data, content_type)

    flaky = DiesOnThird(storage.root)
    with pytest.raises(OSError):
        seed_images.seed(conn, flaky, source_dir=SOURCE, source_url=None, out=lambda *_: None)
    conn.rollback()
    assert conn.execute("SELECT count(*) AS n FROM images").fetchone()["n"] == 2  # 3 枚目は、補償で行も実体も消えている
    assert len(list(flaky.list_keys("images/"))) == 2
    again = seed_images.seed(conn, flaky, source_dir=SOURCE, source_url=None, out=lambda *_: None)
    assert again == {"registered": 9, "linked": 9, "kept": 2, "no_recruit": 0}
    assert conn.execute("SELECT count(*) AS n FROM images").fetchone()["n"] == 11
    assert conn.execute("SELECT count(*) AS n FROM recruit_images").fetchone()["n"] == 11


@needs_sources
def test_seed_images_finishes_or_clears_a_registration_that_stopped_halfway(fresh):
    conn, storage, _ = fresh
    entry = next(e for e in json.loads(seed_images.MANIFEST.read_text(encoding="utf-8"))["images"] if e["demo_key"] == "garden-storyteller-hero")
    processed = svc.process_image((SOURCE / entry["file"]).read_bytes(), max_bytes=20 * 1024 * 1024)
    # 実体まで保存したのに、公開中にする更新の前で止まった行
    stuck = uuid.uuid4()
    conn.execute(
        "INSERT INTO images (id, storage_key, mime_type, byte_size, width, height, sha256, alt, origin, status, demo_key) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, 'x', 'generated', 'uploading', %s)",
        (stuck, f"images/{stuck}.jpg", processed.mime_type, len(processed.data), processed.width, processed.height, processed.sha256, entry["demo_key"]),
    )
    conn.commit()
    storage.put(f"images/{stuck}.jpg", processed.data, processed.mime_type)
    out: list[str] = []
    seed_images.seed(conn, storage, source_dir=SOURCE, source_url=None, out=out.append)
    assert conn.execute("SELECT status FROM images WHERE id = %s", (stuck,)).fetchone()["status"] == "approved"  # 新しい画像を作らず、その行を公開中にした
    assert conn.execute("SELECT count(*) AS n FROM images WHERE demo_key = %s", (entry["demo_key"],)).fetchone()["n"] == 1
    # 実体が無いまま止まった行は、片付けて、次の実行でやり直せる
    conn.execute("DELETE FROM recruit_images")
    conn.execute("DELETE FROM images")
    lost = uuid.uuid4()
    conn.execute(
        "INSERT INTO images (id, storage_key, mime_type, byte_size, width, height, sha256, alt, origin, status, demo_key) "
        "VALUES (%s, %s, 'image/jpeg', 10, 300, 300, %s, 'x', 'generated', 'uploading', %s)",
        (lost, f"images/{lost}.jpg", "0" * 64, entry["demo_key"]),
    )
    conn.commit()
    out.clear()
    seed_images.seed(conn, storage, source_dir=SOURCE, source_url=None, out=out.append)
    assert any("片付けました" in line for line in out)
    assert conn.execute("SELECT status FROM images WHERE id = %s", (lost,)).fetchone()["status"] == "deleted"
    again = seed_images.seed(conn, storage, source_dir=SOURCE, source_url=None, out=lambda *_: None)
    assert again["registered"] == 1  # 片付けた 1 枚だけを、改めて登録する（ほかの 10 枚は、最初の実行で登録済み）
    assert conn.execute("SELECT count(*) AS n FROM images WHERE status = 'approved'").fetchone()["n"] == 11


def test_backfill_demo_keys_links_only_rows_that_match_in_id_and_name(fresh):
    conn, _, _ = fresh
    conn.execute("UPDATE recruits SET demo_key = NULL")
    conn.execute("UPDATE recruits SET category = '別の職種' WHERE id = 5")  # 名前が違う行は結ばない
    conn.commit()
    assert seed_demo.backfill_demo_keys(conn) == 11
    conn.commit()
    assert conn.execute("SELECT demo_key FROM recruits WHERE id = 5").fetchone()["demo_key"] is None
    assert conn.execute("SELECT demo_key FROM recruits WHERE id = 7").fetchone()["demo_key"] == "ruins-storyteller"
    assert seed_demo.backfill_demo_keys(conn) == 0  # 再実行しても変わらない


def test_seed_demo_on_existing_data_does_not_reset(fresh):
    conn, _, url = fresh
    before = conn.execute("SELECT id, category FROM recruits ORDER BY id").fetchall()
    conn.execute("UPDATE recruits SET demo_key = NULL")
    conn.commit()
    seed_demo.main(reset=False)  # データがあるので入れ直さず、demo_key だけ結ぶ
    assert conn.execute("SELECT id, category FROM recruits ORDER BY id").fetchall() == before
    conn.rollback()
    assert conn.execute("SELECT count(demo_key) AS n FROM recruits").fetchone()["n"] == 12


def test_cli_register_publishes_and_reject_takes_down(fresh, tmp_path):
    conn, storage, _ = fresh
    img = tmp_path / "a.jpg"
    img.write_bytes(make_image())
    lines: list[str] = []
    cli = images_cli._parser()

    def run(*argv):
        lines.clear()
        code = images_cli.run(cli.parse_args(list(argv)), conn, storage, out=lines.append)
        return code, "\n".join(lines)

    code, text = run("register", str(img), "--alt", "手動", "--recruit-id", "2")
    assert code == 0 and "公開中" in text
    row = conn.execute("SELECT id, status, storage_key FROM images").fetchone()
    image_id = row["id"]
    assert row["status"] == "approved" and storage.exists(row["storage_key"])  # 承認の操作なしで公開されている
    assert conn.execute("SELECT is_hero FROM recruit_images").fetchone()["is_hero"] is False
    code, text = run("register", str(img), "--alt", "手動", "--recruit-id", "999")
    assert code == 1 and "求人が見つかりません" in text
    assert run("list", "--status", "approved")[1].endswith("1 件")
    code, text = run("reconcile")
    assert code == 0 and "報告だけ" in text and "orphan_objects=0" in text
    assert run("reject", str(image_id))[0] == 0
    assert not storage.exists(row["storage_key"]) and conn.execute("SELECT status FROM images").fetchone()["status"] == "rejected"
    with pytest.raises(svc.ImageConflict):
        run("reject", str(image_id))
    code, text = run("formfile")
    assert code == 0 and "0 件" in text


def test_cli_has_no_approve_or_apply():
    cli = images_cli._parser()
    for argv in (["approve", str(uuid.uuid4())], ["reconcile", "--apply"], ["reconcile", "--grace-days", "30"], ["register", "x.jpg", "--alt", "x", "--recruit-id", "1", "--approve"]):
        with pytest.raises(SystemExit):
            cli.parse_args(argv)


def test_cli_register_with_hero_sets_the_hero_at_once(fresh, tmp_path):
    conn, storage, _ = fresh
    img = tmp_path / "a.jpg"
    img.write_bytes(make_image())
    images_cli.run(images_cli._parser().parse_args(["register", str(img), "--alt", "x", "--recruit-id", "1", "--hero"]), conn, storage, out=lambda *_: None)
    assert conn.execute("SELECT is_hero FROM recruit_images").fetchone()["is_hero"] is True
