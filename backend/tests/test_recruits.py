def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_master_has_codes_and_grouped_occupations(client):
    body = client.get("/api/master").json()
    assert len(body["areas"]) == 14
    assert len(body["stations"]) == 11
    assert len(body["employments"]) == 4
    assert body["occupations"][0]["category"] == "栽培"
    assert sum(len(g["items"]) for g in body["occupations"]) == 35


def test_search_without_filters_shows_only_displayed(client):
    body = client.get("/api/recruits").json()
    assert body["total"] == 11  # 非表示の 1 件は出ない
    assert all(item["corporate"] != "非表示のテスト求人" for item in body["items"])


def test_search_or_within_kind_and_between_kinds(client):
    # 地域 3(第一環) か 4(第二環) の求人
    two = client.get("/api/recruits", params={"area": [3, 4]}).json()
    assert {i["corporate"] for i in two["items"]} == {"環軌道植物公社", "星庭財団"}
    # さらに雇用形態が 1(常勤) に限る（AND）
    narrowed = client.get("/api/recruits", params={"area": [3, 4], "employment": 1}).json()
    assert narrowed["total"] == 3
    assert all("常勤" in i["employments"] for i in narrowed["items"])


def test_paging(client):
    first = client.get("/api/recruits", params={"per_page": 5}).json()
    assert (first["total"], first["last_page"], len(first["items"])) == (11, 3, 5)
    last = client.get("/api/recruits", params={"per_page": 5, "page": 3}).json()
    assert len(last["items"]) == 1


def test_detail_and_hidden_404(client):
    first = client.get("/api/recruits").json()["items"][0]
    detail = client.get(f"/api/recruits/{first['id']}").json()
    assert detail["start_time"] == "09:00" and detail["areas"]
    assert client.get("/api/recruits/12").status_code == 404  # 非表示
    assert client.get("/api/recruits/9999").status_code == 404


def test_invalid_page_is_rejected(client):
    assert client.get("/api/recruits", params={"page": 0}).status_code == 422
    assert client.get("/api/recruits", params={"per_page": 999}).status_code == 422


def _counts(rows):
    return {r["code"]: r["count"] for r in rows}


def test_facets_without_filters_count_displayed_only(client):
    body = client.get("/api/facets").json()
    assert body["total"] == 11
    assert _counts(body["employments"]) == {1: 5, 2: 3, 3: 2, 4: 1}  # 非表示の常勤 1 件は数えない
    assert _counts(body["areas"])[3] == 2


def test_facets_ignore_own_kind_but_apply_other_kinds(client):
    # 常勤だけに絞ると、地域の件数は「常勤の求人」から数える
    areas = _counts(client.get("/api/facets", params={"employment": 1}).json()["areas"])
    assert areas == {3: 1, 4: 2, 9: 1, 10: 1, 12: 1}
    # 雇用形態の件数は、自分の種類（雇用形態）の選択に影響されない。他の種類（地域 3,4）は効く
    both = client.get("/api/facets", params={"area": [3, 4], "employment": 1}).json()
    assert both["total"] == 3
    assert _counts(both["employments"]) == {1: 3, 3: 1}


def test_summary_has_salary_kind(client):
    items = client.get("/api/recruits").json()["items"]
    assert items[0]["salary"] == 2 and items[0]["pay_min"] == 180000  # 月給制
    assert items[2]["salary"] == 4 and items[2]["pay_min"] == 1100  # 時給制


def test_every_summary_has_a_hero_image_key(client):
    items = client.get("/api/recruits", params={"per_page": 50}).json()["items"]
    assert len(items) == 11
    for item in items:
        assert "hero_image" in item  # 画像が無い求人でも、キーは必ずある（値は null）
        assert item["hero_image"] is None or set(item["hero_image"]) == {"id", "url", "alt", "width", "height", "mime_type"}
