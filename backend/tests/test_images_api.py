import io

import psycopg
import pytest
from PIL import Image

from app import image_service as svc
from app.storage import get_storage
from tests.conftest import TEST_URL
from tests.imagefiles import make_animated_png, make_image, make_noise_png
from tests.test_garden import GARDEN, GARDEN2, USER, bearer, db_exec, garden_login

pytestmark = pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL が未設定です")

# 園 1（hoshiniwa-garden）の求人は ID 1・2（12 は非表示）、園 2 の求人は ID 3・4
MINE, OTHERS = 1, 3


@pytest.fixture(autouse=True)
def clean_images(client):
    for table in ("recruit_images", "garden_images", "images"):
        db_exec(f"DELETE FROM {table}")  # noqa: S608
    yield


@pytest.fixture
def tok1(client):
    return garden_login(client, GARDEN)


@pytest.fixture
def tok2(client):
    return garden_login(client, GARDEN2)


def upload(client, token, recruit_id=MINE, *, data=None, ctype="image/jpeg", alt="テスト画像"):
    return client.post(
        f"/api/garden/recruits/{recruit_id}/images", params={"alt": alt}, content=data if data is not None else make_image(), headers={**bearer(token), "Content-Type": ctype}
    )


def approve(image_id):
    """運営の承認（CLI と同じ関数）。園の API からは呼べない。"""
    from psycopg.rows import dict_row

    from app.settings import database_url

    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        svc.approve_image(conn, get_storage(), image_id)


def listing(client, token, recruit_id=MINE):
    res = client.get(f"/api/garden/recruits/{recruit_id}/images", headers=bearer(token))
    assert res.status_code == 200
    return res.json()["images"]


def test_upload_then_pending_is_private_then_approved_is_public(client, tok1):
    res = upload(client, tok1)
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "pending" and body["url"] is None and body["position"] == 0 and body["is_hero"] is False
    # 承認前: 公開の求人詳細にも、/media にも出ない
    detail = client.get(f"/api/recruits/{MINE}").json()
    assert detail["hero_image"] is None and detail["images"] == []
    assert client.get(f"/media/images/{body['id']}.jpg").status_code == 404
    # 園には、認証付きのプレビューで見える
    pre = client.get(body["preview_path"], headers=bearer(tok1))
    assert pre.status_code == 200 and pre.headers["content-type"] == "image/jpeg" and pre.headers["cache-control"] == "private, no-store"
    Image.open(io.BytesIO(pre.content)).verify()
    # 承認（運営）
    approve(body["id"])
    detail = client.get(f"/api/recruits/{MINE}").json()
    assert detail["hero_image"]["id"] == body["id"] and detail["images"][0]["url"] == f"/media/images/{body['id']}.jpg"  # ヒーロー未指定なら先頭
    assert detail["hero_image"]["alt"] == "テスト画像" and detail["hero_image"]["width"] == 640
    media = client.get(detail["hero_image"]["url"])
    assert media.status_code == 200 and media.headers["content-type"] == "image/jpeg" and "immutable" in media.headers["cache-control"]


def test_authentication_is_required_everywhere(client, tok1):
    r = upload(client, tok1).json()
    user_token = client.post("/api/auth/login", json=USER).json()["token"]
    calls = [
        ("get", f"/api/garden/recruits/{MINE}/images"),
        ("post", f"/api/garden/recruits/{MINE}/images?alt=x"),
        ("put", f"/api/garden/recruits/{MINE}/images/order"),
        ("put", f"/api/garden/recruits/{MINE}/images/hero"),
        ("delete", f"/api/garden/recruits/{MINE}/images/{r['id']}"),
        ("get", r["preview_path"]),
        ("get", "/api/garden/recruits"),
        ("get", "/api/garden/profile-images"),
    ]
    for method, path in calls:
        assert getattr(client, method)(path).status_code == 401, (method, path)
        assert getattr(client, method)(path, headers=bearer(user_token)).status_code == 401, (method, path)  # 利用者のトークンでは入れない


def test_other_garden_cannot_see_or_change_my_recruit_images(client, tok1, tok2):
    mine = upload(client, tok1).json()
    approve(mine["id"])
    assert client.get(f"/api/garden/recruits/{MINE}/images", headers=bearer(tok2)).status_code == 404
    assert upload(client, tok2, MINE).status_code == 404
    assert client.put(f"/api/garden/recruits/{MINE}/images/order", json={"image_ids": [mine["id"]]}, headers=bearer(tok2)).status_code == 404
    assert client.put(f"/api/garden/recruits/{MINE}/images/hero", json={"image_id": mine["id"]}, headers=bearer(tok2)).status_code == 404
    assert client.delete(f"/api/garden/recruits/{MINE}/images/{mine['id']}", headers=bearer(tok2)).status_code == 404
    assert client.get(mine["preview_path"], headers=bearer(tok2)).status_code == 404  # 承認済みでも、他の園のプレビューは通らない
    # 自分の求人の URL のまま、他の園の画像 ID を指しても効かない
    theirs = upload(client, tok2, OTHERS).json()
    assert client.delete(f"/api/garden/recruits/{OTHERS}/images/{mine['id']}", headers=bearer(tok2)).status_code == 404
    assert client.put(f"/api/garden/recruits/{OTHERS}/images/hero", json={"image_id": mine["id"]}, headers=bearer(tok2)).status_code == 404
    assert client.put(f"/api/garden/recruits/{OTHERS}/images/order", json={"image_ids": [mine["id"], theirs["id"]]}, headers=bearer(tok2)).status_code == 422
    assert len(listing(client, tok1)) == 1  # 何も変わっていない


def test_upload_rejects_bad_input(client, tok1):
    assert upload(client, tok1, data=b"not an image").status_code == 422
    assert upload(client, tok1, data=make_image("PNG"), ctype="image/jpeg").status_code == 422  # 宣言と実データが違う
    assert upload(client, tok1, data=make_image("JPEG"), ctype="image/gif").status_code == 415
    assert upload(client, tok1, data=b"<svg/>", ctype="image/svg+xml").status_code == 415
    assert upload(client, tok1, data=make_animated_png(), ctype="image/png").status_code == 422
    assert upload(client, tok1, data=make_image("JPEG", (100, 100))).status_code == 422
    assert upload(client, tok1, alt="").status_code == 422
    assert upload(client, tok1, alt="あ" * 301).status_code == 422
    assert client.post(f"/api/garden/recruits/{MINE}/images", content=make_image(), headers={**bearer(tok1), "Content-Type": "image/jpeg"}).status_code == 422  # alt なし
    assert listing(client, tok1) == []  # 拒否したものは残らない
    assert db_exec("SELECT count(*) FROM images")[0][0] == 0


def test_upload_over_limit_is_rejected_by_header_and_by_stream(client, tok1, monkeypatch):
    monkeypatch.setenv("IMAGE_MAX_UPLOAD_BYTES", "20000")
    big = make_noise_png()
    assert len(big) > 20000
    assert upload(client, tok1, data=big, ctype="image/png").status_code == 413
    # Content-Length を偽った（小さく申告した）本文も、読みながら止める
    res = client.post(
        f"/api/garden/recruits/{MINE}/images",
        params={"alt": "x"},
        content=iter([big[:15000], big[15000:]]),  # チャンク転送（Content-Length なし）
        headers={**bearer(tok1), "Content-Type": "image/png"},
    )
    assert res.status_code == 413
    assert db_exec("SELECT count(*) FROM images")[0][0] == 0


def test_multiple_images_order_hero_and_delete(client, tok1):
    ids = [upload(client, tok1, data=make_image(seed=i), alt=f"画像{i}").json()["id"] for i in range(1, 4)]
    assert [i["position"] for i in listing(client, tok1)] == [0, 1, 2]
    for i in ids:
        approve(i)
    # 並べ替え
    res = client.put(f"/api/garden/recruits/{MINE}/images/order", json={"image_ids": [ids[2], ids[0], ids[1]]}, headers=bearer(tok1))
    assert res.status_code == 200 and [i["id"] for i in res.json()["images"]] == [ids[2], ids[0], ids[1]]
    public = client.get(f"/api/recruits/{MINE}").json()
    assert [i["id"] for i in public["images"]] == [ids[2], ids[0], ids[1]] and public["hero_image"]["id"] == ids[2]
    # 一覧と一致しない並べ替えは拒否
    for bad in ([ids[0]], [ids[0], ids[0], ids[1]], ids + [ids[0]], ["not-a-uuid"]):
        assert client.put(f"/api/garden/recruits/{MINE}/images/order", json={"image_ids": bad}, headers=bearer(tok1)).status_code == 422
    # ヒーローを変える
    res = client.put(f"/api/garden/recruits/{MINE}/images/hero", json={"image_id": ids[1]}, headers=bearer(tok1))
    assert res.status_code == 200 and [i["is_hero"] for i in res.json()["images"]] == [False, False, True]
    assert client.get(f"/api/recruits/{MINE}").json()["hero_image"]["id"] == ids[1]
    # 削除要求: 求人から外れ、画像の実体はすぐには消えない
    assert client.delete(f"/api/garden/recruits/{MINE}/images/{ids[1]}", headers=bearer(tok1)).status_code == 204
    after = listing(client, tok1)
    assert [i["id"] for i in after] == [ids[2], ids[0]] and [i["position"] for i in after] == [0, 1]
    assert client.get(f"/api/recruits/{MINE}").json()["hero_image"]["id"] == ids[2]  # ヒーローが無くなったら先頭へ
    row = db_exec("SELECT status, deletion_requested_at IS NOT NULL FROM images WHERE id = %s", (ids[1],))[0]
    assert row == ("approved", True)
    assert get_storage().exists(f"images/{ids[1]}.jpg", public=True)  # 即時に物理削除しない
    assert client.delete(f"/api/garden/recruits/{MINE}/images/{ids[1]}", headers=bearer(tok1)).status_code == 404


def test_hero_must_be_approved_and_linked(client, tok1):
    pending = upload(client, tok1).json()["id"]
    res = client.put(f"/api/garden/recruits/{MINE}/images/hero", json={"image_id": pending}, headers=bearer(tok1))
    assert res.status_code == 409
    assert client.put(f"/api/garden/recruits/{MINE}/images/hero", json={"image_id": "00000000-0000-0000-0000-000000000000"}, headers=bearer(tok1)).status_code == 404
    other = upload(client, tok1, 2).json()["id"]  # 同じ園の別の求人の画像は、この求人のヒーローにできない
    approve(other)
    assert client.put(f"/api/garden/recruits/{MINE}/images/hero", json={"image_id": other}, headers=bearer(tok1)).status_code == 404


def test_rejected_image_is_not_public_and_cannot_be_hero(client, tok1):
    from psycopg.rows import dict_row

    from app.settings import database_url

    image = upload(client, tok1).json()["id"]
    approve(image)
    assert client.put(f"/api/garden/recruits/{MINE}/images/hero", json={"image_id": image}, headers=bearer(tok1)).status_code == 200
    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        svc.reject_image(conn, get_storage(), image)
    public = client.get(f"/api/recruits/{MINE}").json()
    assert public["hero_image"] is None and public["images"] == []
    assert client.get(f"/media/images/{image}.jpg").status_code == 404
    assert listing(client, tok1)[0]["status"] == "rejected" and listing(client, tok1)[0]["is_hero"] is False


def test_hidden_recruit_images_are_not_public(client, tok1):
    image = upload(client, tok1, 12).json()["id"]  # ID 12 は非表示の求人
    approve(image)
    assert client.get("/api/recruits/12").status_code == 404


def test_image_count_limit(client, tok1):
    for i in range(svc.MAX_IMAGES_PER_RECRUIT):
        assert upload(client, tok1, data=make_image(seed=100 + i)).status_code == 201
    assert upload(client, tok1).status_code == 409
    assert len(listing(client, tok1)) == svc.MAX_IMAGES_PER_RECRUIT


def test_my_recruits_lists_only_my_recruits_with_counts(client, tok1, tok2):
    approve(upload(client, tok1).json()["id"])
    upload(client, tok1, data=make_image(seed=9))
    items = {i["id"]: i for i in client.get("/api/garden/recruits", headers=bearer(tok1)).json()}
    assert set(items) == {1, 2, 12} and items[1]["image_count"] == 2 and items[1]["approved_count"] == 1
    assert set(i["id"] for i in client.get("/api/garden/recruits", headers=bearer(tok2)).json()) == {3, 4}


def test_profile_images_share_the_same_foundation(client, tok1, tok2):
    res = client.post("/api/garden/profile-images", params={"alt": "ロゴ", "role": "logo"}, content=make_image(), headers={**bearer(tok1), "Content-Type": "image/jpeg"})
    assert res.status_code == 201 and res.json()["role"] == "logo" and res.json()["status"] == "pending"
    assert len(client.get("/api/garden/profile-images", headers=bearer(tok1)).json()) == 1
    assert client.get("/api/garden/profile-images", headers=bearer(tok2)).json() == []
    assert client.get(res.json()["preview_path"], headers=bearer(tok2)).status_code == 404
    assert client.post("/api/garden/profile-images", params={"alt": "x", "role": "evil"}, content=make_image(), headers={**bearer(tok1), "Content-Type": "image/jpeg"}).status_code == 422
    assert client.delete(f"/api/garden/profile-images/{res.json()['id']}", headers=bearer(tok2)).status_code == 404
    assert client.delete(f"/api/garden/profile-images/{res.json()['id']}", headers=bearer(tok1)).status_code == 204
    assert db_exec("SELECT deletion_requested_at IS NOT NULL FROM images")[0][0] is True


def test_media_route_serves_only_existing_public_objects_and_blocks_traversal(client, tok1):
    image = upload(client, tok1).json()["id"]
    assert client.get(f"/media/images/{image}.jpg").status_code == 404  # 非公開のまま
    for bad in ("../private/x.jpg", "images/../../etc/passwd", "images/x.svg", "images/x"):
        assert client.get(f"/media/{bad}").status_code == 404


def test_error_bodies_contain_no_paths_or_keys(client, tok1):
    res = upload(client, tok1, data=b"x" * 100)
    assert res.status_code == 422 and "/tmp" not in res.text and "Traceback" not in res.text
