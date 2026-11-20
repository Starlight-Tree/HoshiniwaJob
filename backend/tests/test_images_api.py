import io

import psycopg
import pytest
from PIL import Image

from app import image_service as svc
from app.storage import get_storage
from tests.conftest import TEST_URL
from tests.imagefiles import make_animated_png, make_image, make_noise_png
from tests.jwt_tokens import make_token
from tests.test_garden import GARDEN, GARDEN2, bearer, db_exec, garden_login

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


def take_down(image_id):
    """運営の取り下げ（CLI と同じ関数）。園の API からは呼べない。"""
    from psycopg.rows import dict_row

    from app.settings import database_url

    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        svc.reject_image(conn, get_storage(), image_id)


def listing(client, token, recruit_id=MINE):
    res = client.get(f"/api/garden/recruits/{recruit_id}/images", headers=bearer(token))
    assert res.status_code == 200
    return res.json()["images"]


def test_upload_is_public_immediately_without_any_approval(client, tok1):
    res = upload(client, tok1)
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "approved" and body["url"] == f"/media/images/{body['id']}.jpg" and body["position"] == 0 and body["is_hero"] is False
    assert "preview_path" not in body
    # 保存した時点で、公開の求人詳細にも、/media にも出る
    detail = client.get(f"/api/recruits/{MINE}").json()
    assert detail["hero_image"]["id"] == body["id"] and detail["images"][0]["url"] == body["url"]  # ヒーロー未指定なら先頭
    assert detail["hero_image"]["alt"] == "テスト画像" and detail["hero_image"]["width"] == 640
    media = client.get(body["url"])
    assert media.status_code == 200 and media.headers["content-type"] == "image/jpeg" and "immutable" in media.headers["cache-control"]
    Image.open(io.BytesIO(media.content)).verify()
    # 承認前のプレビュー用の道は、もう無い
    assert client.get(f"/api/garden/images/{body['id']}/preview", headers=bearer(tok1)).status_code in (404, 405)


def test_authentication_is_required_everywhere(auth_env, client, tok1):
    r = upload(client, tok1).json()
    user_token = make_token()  # 求職者の JWT（Better Auth が発行したもの）
    calls = [
        ("get", f"/api/garden/recruits/{MINE}/images"),
        ("post", f"/api/garden/recruits/{MINE}/images?alt=x"),
        ("put", f"/api/garden/recruits/{MINE}/images/order"),
        ("put", f"/api/garden/recruits/{MINE}/images/hero"),
        ("delete", f"/api/garden/recruits/{MINE}/images/{r['id']}"),
        ("get", "/api/garden/recruits"),
        ("get", "/api/garden/profile-images"),
    ]
    for method, path in calls:
        assert getattr(client, method)(path).status_code == 401, (method, path)
        assert getattr(client, method)(path, headers=bearer(user_token)).status_code == 401, (method, path)  # 利用者のトークンでは入れない


def test_other_garden_cannot_see_or_change_my_recruit_images(client, tok1, tok2):
    mine = upload(client, tok1).json()
    assert client.get(f"/api/garden/recruits/{MINE}/images", headers=bearer(tok2)).status_code == 404
    assert upload(client, tok2, MINE).status_code == 404
    assert client.put(f"/api/garden/recruits/{MINE}/images/order", json={"image_ids": [mine["id"]]}, headers=bearer(tok2)).status_code == 404
    assert client.put(f"/api/garden/recruits/{MINE}/images/hero", json={"image_id": mine["id"]}, headers=bearer(tok2)).status_code == 404
    assert client.delete(f"/api/garden/recruits/{MINE}/images/{mine['id']}", headers=bearer(tok2)).status_code == 404
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
    # 並べ替え
    res = client.put(f"/api/garden/recruits/{MINE}/images/order", json={"image_ids": [ids[2], ids[0], ids[1]]}, headers=bearer(tok1))
    assert res.status_code == 200 and [i["id"] for i in res.json()["images"]] == [ids[2], ids[0], ids[1]]
    public = client.get(f"/api/recruits/{MINE}").json()
    assert [i["id"] for i in public["images"]] == [ids[2], ids[0], ids[1]] and public["hero_image"]["id"] == ids[2]
    # 一覧と一致しない並べ替えは拒否
    for bad in ([ids[0]], [ids[0], ids[0], ids[1]], ids + [ids[0]], ["not-a-uuid"]):
        assert client.put(f"/api/garden/recruits/{MINE}/images/order", json={"image_ids": bad}, headers=bearer(tok1)).status_code == 422
    # ヒーローを変える（アップロードした直後の画像にできる）
    res = client.put(f"/api/garden/recruits/{MINE}/images/hero", json={"image_id": ids[1]}, headers=bearer(tok1))
    assert res.status_code == 200 and [i["is_hero"] for i in res.json()["images"]] == [False, False, True]
    assert client.get(f"/api/recruits/{MINE}").json()["hero_image"]["id"] == ids[1]
    # 削除: 求人から外れ、画像はその場で消える（猶予はない）
    key = f"images/{ids[1]}.jpg"
    assert get_storage().exists(key)
    assert client.delete(f"/api/garden/recruits/{MINE}/images/{ids[1]}", headers=bearer(tok1)).status_code == 204
    after = listing(client, tok1)
    assert [i["id"] for i in after] == [ids[2], ids[0]] and [i["position"] for i in after] == [0, 1]
    assert client.get(f"/api/recruits/{MINE}").json()["hero_image"]["id"] == ids[2]  # ヒーローが無くなったら先頭へ
    row = db_exec("SELECT status, deleted_at IS NOT NULL FROM images WHERE id = %s", (ids[1],))[0]
    assert row == ("deleted", True)
    assert not get_storage().exists(key)  # 実体もその場で消える
    assert client.get(f"/media/{key}").status_code == 404
    assert client.delete(f"/api/garden/recruits/{MINE}/images/{ids[1]}", headers=bearer(tok1)).status_code == 404
    # 残りの画像は無事
    assert all(get_storage().exists(f"images/{i}.jpg") for i in (ids[0], ids[2]))


def test_replacing_an_image_uses_a_new_key_and_never_touches_the_old_one(client, tok1):
    old = upload(client, tok1, data=make_image(seed=1)).json()
    new = upload(client, tok1, data=make_image(seed=1)).json()  # 同じ内容でも、別の画像として登録される
    assert new["id"] != old["id"] and new["url"] != old["url"]
    assert client.delete(f"/api/garden/recruits/{MINE}/images/{old['id']}", headers=bearer(tok1)).status_code == 204
    assert client.get(old["url"]).status_code == 404 and client.get(new["url"]).status_code == 200
    assert [i["id"] for i in listing(client, tok1)] == [new["id"]]


def test_a_failed_storage_delete_does_not_fail_the_user_and_is_left_for_reconcile(client, tok1, monkeypatch):
    image = upload(client, tok1).json()
    from app.storage import StorageError

    def broken(self, key):
        raise StorageError("down")

    monkeypatch.setattr(type(get_storage()), "delete", broken)
    assert client.delete(f"/api/garden/recruits/{MINE}/images/{image['id']}", headers=bearer(tok1)).status_code == 204
    monkeypatch.undo()
    assert db_exec("SELECT status FROM images WHERE id = %s", (image["id"],))[0][0] == "deleted"
    assert listing(client, tok1) == [] and client.get(f"/api/recruits/{MINE}").json()["images"] == []  # DB が先に確定しているので、公開には出ない


def test_hero_must_be_my_linked_published_image(client, tok1):
    mine = upload(client, tok1).json()["id"]
    assert client.put(f"/api/garden/recruits/{MINE}/images/hero", json={"image_id": mine}, headers=bearer(tok1)).status_code == 200  # 承認を待たずに指定できる
    assert client.put(f"/api/garden/recruits/{MINE}/images/hero", json={"image_id": "00000000-0000-0000-0000-000000000000"}, headers=bearer(tok1)).status_code == 404
    other = upload(client, tok1, 2).json()["id"]  # 同じ園の別の求人の画像は、この求人のヒーローにできない
    assert client.put(f"/api/garden/recruits/{MINE}/images/hero", json={"image_id": other}, headers=bearer(tok1)).status_code == 404


def test_taken_down_image_is_gone_from_public_and_cannot_be_hero(client, tok1):
    image = upload(client, tok1).json()
    other = upload(client, tok1, data=make_image(seed=2)).json()
    assert client.put(f"/api/garden/recruits/{MINE}/images/hero", json={"image_id": image["id"]}, headers=bearer(tok1)).status_code == 200
    take_down(image["id"])
    public = client.get(f"/api/recruits/{MINE}").json()
    assert [i["id"] for i in public["images"]] == [other["id"]] and public["hero_image"]["id"] == other["id"]
    assert client.get(image["url"]).status_code == 404  # 実体も消えている
    mine = {i["id"]: i for i in listing(client, tok1)}
    assert mine[image["id"]]["status"] == "rejected" and mine[image["id"]]["url"] is None and mine[image["id"]]["is_hero"] is False
    assert client.put(f"/api/garden/recruits/{MINE}/images/hero", json={"image_id": image["id"]}, headers=bearer(tok1)).status_code == 409
    # 園は、取り下げられた画像を、自分の一覧から消せる
    assert client.delete(f"/api/garden/recruits/{MINE}/images/{image['id']}", headers=bearer(tok1)).status_code == 204
    assert [i["id"] for i in listing(client, tok1)] == [other["id"]]


def test_hidden_recruit_images_are_not_public(client, tok1):
    upload(client, tok1, 12)  # ID 12 は非表示の求人
    assert client.get("/api/recruits/12").status_code == 404


def list_items(client):
    """公開の求人一覧（1 ページに全件）を、求人 ID で引ける形で返す。"""
    res = client.get("/api/recruits", params={"per_page": 50})
    assert res.status_code == 200
    return {i["id"]: i for i in res.json()["items"]}


def detail_hero(client, recruit_id):
    return client.get(f"/api/recruits/{recruit_id}").json()["hero_image"]


@pytest.fixture
def image_sql(monkeypatch):
    """recruit_images を読む SQL が流れるたびに、その文を残す（接続のクエリ回数を数えるため）。"""
    seen: list[str] = []
    original = psycopg.Cursor.execute

    def counting(self, query, *args, **kwargs):
        if isinstance(query, str) and "recruit_images" in query:
            seen.append(query)
        return original(self, query, *args, **kwargs)

    monkeypatch.setattr(psycopg.Cursor, "execute", counting)
    return seen


def test_list_hero_image_is_null_when_there_are_no_images(client):
    items = list_items(client)
    assert len(items) == 11  # 非表示の 1 件は出ない
    assert all("hero_image" in i and i["hero_image"] is None for i in items.values())


def test_list_hero_image_is_the_same_as_the_detail_one(client, tok1):
    image = upload(client, tok1).json()
    items = list_items(client)
    hero = items[MINE]["hero_image"]
    assert hero == detail_hero(client, MINE)  # 一覧と詳細で、同じ画像・同じ形
    assert hero == {"id": image["id"], "url": image["url"], "alt": "テスト画像", "width": 640, "height": 360, "mime_type": "image/jpeg"}
    assert all(i["hero_image"] is None for rid, i in items.items() if rid != MINE)  # 画像を足していない求人は null のまま


def test_list_hero_images_belong_to_their_own_recruits(client, tok1, tok2):
    a = upload(client, tok1, 1, data=make_image(seed=1), alt="一").json()
    b = upload(client, tok1, 2, data=make_image(seed=2), alt="二").json()
    c = upload(client, tok2, OTHERS, data=make_image(seed=3), alt="三").json()
    items = list_items(client)
    assert [items[r]["hero_image"]["id"] for r in (1, 2, OTHERS)] == [a["id"], b["id"], c["id"]]
    assert items[4]["hero_image"] is None
    for recruit_id in (1, 2, OTHERS, 4):
        assert items[recruit_id]["hero_image"] == detail_hero(client, recruit_id)


def test_list_hero_image_prefers_the_designated_hero_over_the_first(client, tok1):
    ids = [upload(client, tok1, data=make_image(seed=i), alt=f"画像{i}").json()["id"] for i in range(1, 4)]
    assert list_items(client)[MINE]["hero_image"]["id"] == ids[0]  # ヒーロー未指定なら、表示順の先頭
    client.put(f"/api/garden/recruits/{MINE}/images/order", json={"image_ids": [ids[2], ids[0], ids[1]]}, headers=bearer(tok1))
    assert list_items(client)[MINE]["hero_image"]["id"] == ids[2]  # 並べ替えると、先頭が変わる
    assert client.put(f"/api/garden/recruits/{MINE}/images/hero", json={"image_id": ids[1]}, headers=bearer(tok1)).status_code == 200
    hero = list_items(client)[MINE]["hero_image"]
    assert hero["id"] == ids[1] and hero["alt"] == "画像2"  # 指定したヒーローは、先頭でなくても選ばれる
    assert hero == detail_hero(client, MINE)


def test_list_hero_image_skips_taken_down_images(client, tok1):
    image = upload(client, tok1).json()
    other = upload(client, tok1, data=make_image(seed=2)).json()
    assert client.put(f"/api/garden/recruits/{MINE}/images/hero", json={"image_id": image["id"]}, headers=bearer(tok1)).status_code == 200
    assert list_items(client)[MINE]["hero_image"]["id"] == image["id"]
    take_down(image["id"])  # 取り下げると、ヒーローでも一覧には出ない
    hero = list_items(client)[MINE]["hero_image"]
    assert hero["id"] == other["id"] and hero == detail_hero(client, MINE)
    take_down(other["id"])  # 公開中の画像が 1 枚も無くなったら null
    items = list_items(client)
    assert items[MINE]["hero_image"] is None and detail_hero(client, MINE) is None
    assert image["id"] not in str(items) and other["id"] not in str(items)


def test_list_loads_hero_images_in_one_query_however_many_items(client, tok1, tok2, image_sql):
    for token, recruit_id in ((tok1, 1), (tok1, 2), (tok2, 3), (tok2, 4)):
        upload(client, token, recruit_id, data=make_image(seed=recruit_id))
    image_sql.clear()  # 数えるのは、ここからの一覧の呼び出しだけ
    one = client.get("/api/recruits", params={"per_page": 1}).json()["items"]
    assert len(one) == 1 and len(image_sql) == 1
    image_sql.clear()
    ten = client.get("/api/recruits", params={"per_page": 10}).json()["items"]
    assert len(ten) == 10 and len(image_sql) == 1  # 件数が 10 倍でも、画像の SQL は 1 回
    assert [i["hero_image"] is not None for i in ten] == [True] * 4 + [False] * 6
    image_sql.clear()
    assert client.get("/api/recruits", params={"page": 99}).json()["items"] == [] and image_sql == []  # 求人が 0 件なら、画像の SQL は流さない


def test_image_count_limit(client, tok1):
    for i in range(svc.MAX_IMAGES_PER_RECRUIT):
        assert upload(client, tok1, data=make_image(seed=100 + i)).status_code == 201
    assert upload(client, tok1).status_code == 409
    assert len(listing(client, tok1)) == svc.MAX_IMAGES_PER_RECRUIT


def test_my_recruits_lists_only_my_recruits_with_counts(client, tok1, tok2):
    upload(client, tok1)
    taken = upload(client, tok1, data=make_image(seed=9)).json()["id"]
    take_down(taken)
    items = {i["id"]: i for i in client.get("/api/garden/recruits", headers=bearer(tok1)).json()}
    assert set(items) == {1, 2, 12} and items[1]["image_count"] == 2 and items[1]["published_count"] == 1
    assert set(i["id"] for i in client.get("/api/garden/recruits", headers=bearer(tok2)).json()) == {3, 4}


def test_profile_images_share_the_same_foundation(client, tok1, tok2):
    res = client.post("/api/garden/profile-images", params={"alt": "ロゴ", "role": "logo"}, content=make_image(), headers={**bearer(tok1), "Content-Type": "image/jpeg"})
    assert res.status_code == 201 and res.json()["role"] == "logo" and res.json()["status"] == "approved"
    image = res.json()
    assert client.get(image["url"]).status_code == 200
    assert len(client.get("/api/garden/profile-images", headers=bearer(tok1)).json()) == 1
    assert client.get("/api/garden/profile-images", headers=bearer(tok2)).json() == []
    assert client.post("/api/garden/profile-images", params={"alt": "x", "role": "evil"}, content=make_image(), headers={**bearer(tok1), "Content-Type": "image/jpeg"}).status_code == 422
    assert client.delete(f"/api/garden/profile-images/{image['id']}", headers=bearer(tok2)).status_code == 404  # 他の園は消せない
    assert get_storage().exists(f"images/{image['id']}.jpg")
    assert client.delete(f"/api/garden/profile-images/{image['id']}", headers=bearer(tok1)).status_code == 204
    assert db_exec("SELECT status FROM images")[0][0] == "deleted" and client.get(image["url"]).status_code == 404  # その場で消える


def test_media_route_serves_only_existing_objects_and_blocks_traversal(client, tok1):
    image = upload(client, tok1).json()
    assert client.get(f"/media/images/{image['id']}.jpg").status_code == 200
    assert client.get(f"/media/images/{'0' * 8}-0000-0000-0000-{'0' * 12}.jpg").status_code == 404  # 無い画像
    for bad in ("../private/x.jpg", "images/../../etc/passwd", "images/x.svg", "images/x"):
        assert client.get(f"/media/{bad}").status_code == 404


def test_the_api_has_no_approval_or_preview_route(client):
    paths = set(client.get("/openapi.json").json()["paths"])
    assert not [p for p in paths if "preview" in p or "approve" in p]


def test_error_bodies_contain_no_paths_or_keys(client, tok1):
    res = upload(client, tok1, data=b"x" * 100)
    assert res.status_code == 422 and "/tmp" not in res.text and "Traceback" not in res.text
