import json
import shutil
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
    assert first == {"registered": 11, "approved": 11, "linked": 11, "kept": 0, "no_recruit": 0}
    rows = conn.execute(
        "SELECT ri.recruit_id, ri.is_hero, i.status, i.storage_key, i.alt, i.origin FROM recruit_images ri JOIN images i ON i.id = ri.image_id ORDER BY ri.recruit_id"
    ).fetchall()
    assert [r["recruit_id"] for r in rows] == list(range(1, 12))  # 12（非表示のテスト求人）には結ばない
    for r in rows:
        assert r["is_hero"] and r["status"] == "approved" and r["origin"] == "generated" and r["alt"].endswith("（職種名からの演出）")
        expected = svc.process_image((SOURCE / FILE_OF_RECRUIT_ID[r["recruit_id"]]).read_bytes(), max_bytes=20 * 1024 * 1024)
        assert storage.get(r["storage_key"], public=True) == expected.data  # 公開側の実体が、その求人用の元画像から作られている
    assert len({r["storage_key"] for r in rows}) == 11
    # 園が並びやヒーローを変えたあとに再実行しても、変えず、増やさない
    conn.execute("UPDATE recruit_images SET is_hero = false WHERE recruit_id = 1")
    conn.commit()
    second = seed_images.seed(conn, storage, source_dir=SOURCE, source_url=None, out=lambda *_: None)
    assert second == {"registered": 0, "approved": 0, "linked": 0, "kept": 11, "no_recruit": 0}
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

    class DiesOnPublicCopyOfThird(LocalStorage):
        def put(self, key, data, content_type, *, public):
            if public and self.root.joinpath("boom").exists():
                raise OSError("disk full")
            super().put(key, data, content_type, public=public)

    flaky = DiesOnPublicCopyOfThird(storage.root)
    flaky.root.joinpath("boom").parent.mkdir(parents=True, exist_ok=True)
    flaky.root.joinpath("boom").write_text("x")
    with pytest.raises(OSError):
        seed_images.seed(conn, flaky, source_dir=SOURCE, source_url=None, out=lambda *_: None)
    conn.rollback()
    assert conn.execute("SELECT status FROM images").fetchone()["status"] == "pending"  # 補償で pending に戻っている
    assert not list((flaky.root / "public").rglob("*.jpg")) if (flaky.root / "public").exists() else True
    flaky.root.joinpath("boom").unlink()
    again = seed_images.seed(conn, flaky, source_dir=SOURCE, source_url=None, out=lambda *_: None)
    assert again["linked"] == 11 and conn.execute("SELECT count(*) AS n FROM images").fetchone()["n"] == 11


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


def test_cli_register_approve_reject_list_and_reconcile(fresh, tmp_path):
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
    assert code == 0 and "承認待ち" in text
    image_id = conn.execute("SELECT id FROM images").fetchone()["id"]
    assert conn.execute("SELECT is_hero FROM recruit_images").fetchone()["is_hero"] is False
    code, text = run("register", str(img), "--alt", "手動", "--recruit-id", "999")
    assert code == 1 and "求人が見つかりません" in text
    assert run("approve", str(image_id))[0] == 0
    assert run("list", "--status", "approved")[1].endswith("1 件")
    assert run("reconcile")[1].startswith("dry-run")
    assert run("reject", str(image_id))[0] == 0
    with pytest.raises(svc.ImageConflict):
        run("reject", str(image_id))
    code, text = run("formfile")
    assert code == 0 and "0 件" in text


def test_cli_register_with_hero_requires_approve(fresh, tmp_path):
    conn, storage, _ = fresh
    img = tmp_path / "a.jpg"
    img.write_bytes(make_image())
    out: list[str] = []
    images_cli.run(images_cli._parser().parse_args(["register", str(img), "--alt", "x", "--recruit-id", "1", "--hero"]), conn, storage, out=out.append)
    assert any("--approve" in line for line in out)
    assert conn.execute("SELECT is_hero FROM recruit_images").fetchone()["is_hero"] is False
