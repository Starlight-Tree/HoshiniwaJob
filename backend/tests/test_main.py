"""アプリの組み立て（app/main.py）。CORS の設定。DB には触れない（lifespan を動かさない）。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.settings import cors_origins


@pytest.fixture
def preflight():
    """ブラウザーが本リクエストの前に送る事前確認（OPTIONS）を送る関数。"""
    client = TestClient(app)  # with を使わない = lifespan（DB の接続プール）を動かさない
    origin = cors_origins()[0]

    def send(method: str, origin_header: str | None = None):
        return client.options(
            "/api/auth/me",
            headers={"Origin": origin_header or origin, "Access-Control-Request-Method": method, "Access-Control-Request-Headers": "authorization,content-type"},
        )

    return send


def test_cors_allows_patch(preflight):
    res = preflight("PATCH")  # PATCH /api/auth/me（表示名の変更）のため
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == cors_origins()[0]
    assert "PATCH" in {m.strip() for m in res.headers["access-control-allow-methods"].split(",")}


def test_cors_allowed_methods_are_exactly_the_ones_the_api_uses(preflight):
    res = preflight("GET")
    assert {m.strip() for m in res.headers["access-control-allow-methods"].split(",")} == {"GET", "POST", "PUT", "PATCH", "DELETE"}
    assert preflight("TRACE").status_code == 400  # 許していない方法は、事前確認で止まる


def test_cors_rejects_an_origin_that_is_not_listed(preflight):
    res = preflight("PATCH", "https://evil.example.com")
    assert res.status_code == 400 and "access-control-allow-origin" not in res.headers
