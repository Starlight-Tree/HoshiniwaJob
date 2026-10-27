import os
import shutil
import tempfile

import pytest

# DATABASE_URL が無ければ、Postgres が要るテストは飛ばす（TEST_DATABASE_URL があるときだけ動かす）
TEST_URL = os.environ.get("TEST_DATABASE_URL")
MEDIA_DIR = tempfile.mkdtemp(prefix="hj-test-media-")
HERE = os.path.dirname(__file__)
DB_ROOT = os.path.join(HERE, "..", "..", "db")


def new_database(name: str) -> str:
    """空の DB を作り直して、その URL を返す（schema.sql と seed_codes.sql は流さない）。"""
    import psycopg

    admin = psycopg.connect(TEST_URL, autocommit=True)
    admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
    admin.execute(f'CREATE DATABASE "{name}"')
    admin.close()
    return TEST_URL.rsplit("/", 1)[0] + "/" + name


def load_initial_schema(url: str) -> None:
    """Postgres の初回起動で流れる初期スキーマ（db/schema.sql と db/seed_codes.sql）。"""
    import psycopg

    with psycopg.connect(url, autocommit=True) as conn:
        for name in ("schema.sql", "seed_codes.sql"):
            conn.execute(open(os.path.join(DB_ROOT, name), encoding="utf-8").read())


@pytest.fixture(scope="session")
def client():
    if not TEST_URL:
        pytest.skip("TEST_DATABASE_URL が未設定です")
    from fastapi.testclient import TestClient

    test_url = new_database("hj_test")
    load_initial_schema(test_url)
    os.environ["DATABASE_URL"] = test_url
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["STORAGE_LOCAL_DIR"] = MEDIA_DIR
    os.environ["IMAGE_PUBLIC_BASE_URL"] = "/media"
    from app import migrate, seed_demo
    from app.storage import get_storage

    get_storage.cache_clear()
    assert migrate.apply(test_url, out=lambda *_: None) == 0
    seed_demo.main(reset=True)
    from app.main import app

    with TestClient(app) as c:
        yield c
    shutil.rmtree(MEDIA_DIR, ignore_errors=True)
