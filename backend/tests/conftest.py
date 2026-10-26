import os

import pytest

# DATABASE_URL が無ければ、Postgres が要るテストは飛ばす（TEST_DATABASE_URL があるときだけ動かす）
TEST_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def client():
    if not TEST_URL:
        pytest.skip("TEST_DATABASE_URL が未設定です")
    import psycopg
    from fastapi.testclient import TestClient

    here = os.path.dirname(__file__)
    root = os.path.join(here, "..", "..", "db")
    admin = psycopg.connect(TEST_URL, autocommit=True)
    admin.execute("DROP DATABASE IF EXISTS hj_test")
    admin.execute("CREATE DATABASE hj_test")
    admin.close()
    test_url = TEST_URL.rsplit("/", 1)[0] + "/hj_test"
    with psycopg.connect(test_url, autocommit=True) as conn:
        for name in ("schema.sql", "seed_codes.sql"):
            conn.execute(open(os.path.join(root, name), encoding="utf-8").read())
    os.environ["DATABASE_URL"] = test_url
    from app import seed_demo

    seed_demo.main(reset=True)
    from app.main import app

    with TestClient(app) as c:
        yield c
