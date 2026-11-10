"""偽の S3（R2）と偽の genai で確かめる。実 API・実 R2・ネットワークは使わない。"""
import hashlib
import json
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from botocore.awsrequest import AWSResponse
from botocore.exceptions import ClientError

import main

PNG = b"\x89PNG\r\n\x1a\n" + b"fake-image-body"
JPEG = b"\xff\xd8\xff\xe0" + b"fake-jpeg-body"
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 "
ACCOUNT_ID = "0123456789abcdef0123456789abcdef"
SECRET = "SECRET-ACCESS-KEY-VALUE"
TOKEN = "SESSION-TOKEN-VALUE"
BUCKET = "test-bucket"


def make_plan(items=None, **extra):
    items = items if items is not None else [
        {"document_id": "42", "prompt": "A calm abstract hero image.", "aspect_ratio": "16:9"}
    ]
    plan_json = json.dumps({"items": items, **extra})
    return plan_json, hashlib.sha256(plan_json.encode("utf-8")).hexdigest()


def make_credentials(expires_in=1200, **overrides):
    expires_at = datetime.fromtimestamp(time.time() + expires_in, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    credentials = {"access_key_id": "AKID", "secret_access_key": SECRET, "session_token": TOKEN, "expires_at": expires_at}
    credentials.update(overrides)
    return json.dumps(credentials)


def make_env(plan_json=None, plan_sha256=None, **overrides):
    if plan_json is None:
        plan_json, plan_sha256 = make_plan()
    env = {
        "PLAN_JSON": plan_json,
        "PLAN_SHA256": plan_sha256,
        "R2_BUCKET": BUCKET,
        "R2_ACCOUNT_ID": ACCOUNT_ID,
        "R2_TEMP_CREDENTIALS": make_credentials(),
    }
    env.update(overrides)
    return env


def client_error(code, status):
    return ClientError({"Error": {"Code": code, "Message": "x"}, "ResponseMetadata": {"HTTPStatusCode": status}}, "Op")


class FakeS3:
    """head_object と put_object だけを持つ。delete など他の操作は AttributeError になる。"""

    def __init__(self, head_error=None, put_error=None, existing=False):
        self.head_error = head_error
        self.put_error = put_error
        self.existing = existing
        self.heads = []
        self.puts = []

    def head_object(self, **kwargs):
        self.heads.append(kwargs)
        if self.head_error:
            raise self.head_error
        if not self.existing:
            raise client_error("404", 404)
        return {}

    def put_object(self, **kwargs):
        self.puts.append(kwargs)
        if self.put_error:
            raise self.put_error
        return {}


class FakeGenai:
    def __init__(self, data=PNG):
        self.calls = []
        self.models = self
        self._data = data

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self._data is None:
            return SimpleNamespace(candidates=[])
        part = SimpleNamespace(inline_data=SimpleNamespace(data=self._data))
        return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))])


def test_saves_png_with_create_once_condition(capsys):
    plan_json, sha = make_plan()
    s3, genai = FakeS3(), FakeGenai(PNG)
    main.run(make_env(plan_json, sha), s3=s3, client=genai)

    key = f"docunavi-hero/42/{sha[:16]}.png"
    assert s3.heads == [{"Bucket": BUCKET, "Key": key}]
    assert s3.puts == [{"Bucket": BUCKET, "Key": key, "Body": PNG, "ContentType": "image/png", "IfNoneMatch": "*"}]
    assert genai.calls[0]["model"] == main.MODEL
    assert genai.calls[0]["config"].image_config.aspect_ratio == "16:9"
    out = capsys.readouterr()
    assert f"Saved {len(PNG)} bytes to {key}" in out.out


@pytest.mark.parametrize("data,content_type", [(JPEG, "image/jpeg"), (WEBP, "image/webp")])
def test_extension_stays_png_and_content_type_follows_the_bytes(data, content_type):
    s3 = FakeS3()
    main.run(make_env(), s3=s3, client=FakeGenai(data))
    assert s3.puts[0]["Key"].endswith(".png")
    assert s3.puts[0]["ContentType"] == content_type


def test_unknown_bytes_are_not_saved():
    s3 = FakeS3()
    with pytest.raises(SystemExit):
        main.run(make_env(), s3=s3, client=FakeGenai(b"<html>not an image</html>"))
    assert s3.puts == []


def test_no_image_returned_is_an_error():
    s3 = FakeS3()
    with pytest.raises(SystemExit):
        main.run(make_env(), s3=s3, client=FakeGenai(None))
    assert s3.puts == []


def test_existing_object_skips_generation_and_write(capsys):
    s3, genai = FakeS3(existing=True), FakeGenai()
    main.run(make_env(), s3=s3, client=genai)
    assert genai.calls == []
    assert s3.puts == []
    assert "Already saved, skipped generation: docunavi-hero/42/" in capsys.readouterr().out


def test_head_error_other_than_missing_stops_before_generation():
    s3, genai = FakeS3(head_error=client_error("403", 403)), FakeGenai()
    with pytest.raises(SystemExit):
        main.run(make_env(), s3=s3, client=genai)
    assert genai.calls == []
    assert s3.puts == []


def test_precondition_failed_keeps_the_existing_object(capsys):
    s3 = FakeS3(put_error=client_error("PreconditionFailed", 412))
    main.run(make_env(), s3=s3, client=FakeGenai())
    assert len(s3.puts) == 1  # 上書きの再試行はしない
    assert "Already saved, not overwritten" in capsys.readouterr().out


def test_other_put_errors_fail():
    s3 = FakeS3(put_error=client_error("AccessDenied", 403))
    with pytest.raises(SystemExit):
        main.run(make_env(), s3=s3, client=FakeGenai())
    assert len(s3.puts) == 1


def test_plan_hash_mismatch_stops_before_any_call():
    plan_json, _ = make_plan()
    s3, genai = FakeS3(), FakeGenai()
    with pytest.raises(SystemExit):
        main.run(make_env(plan_json, "0" * 64), s3=s3, client=genai)
    assert s3.heads == [] and genai.calls == []


def test_plan_sha_must_be_hex():
    plan_json, _ = make_plan()
    with pytest.raises(SystemExit):
        main.run(make_env(plan_json, "../" + "a" * 61), s3=FakeS3(), client=FakeGenai())


@pytest.mark.parametrize("name", ["PLAN_JSON", "PLAN_SHA256", "R2_BUCKET"])
def test_missing_required_env(name):
    env = make_env()
    del env[name]
    with pytest.raises(SystemExit):
        main.run(env, s3=FakeS3(), client=FakeGenai())


@pytest.mark.parametrize(
    "items,extra",
    [
        ([], {}),
        ([{"document_id": "1", "prompt": "p"}] * 2, {"max_images": 1}),
        ([{"document_id": "../1", "prompt": "p"}], {}),
        ([{"document_id": "1", "prompt": "x" * 1001}], {}),
        ([{"document_id": "1", "prompt": "p", "aspect_ratio": "9:16"}], {}),
    ],
)
def test_invalid_plans_stop_before_any_call(items, extra):
    plan_json, sha = make_plan(items, **extra)
    s3, genai = FakeS3(), FakeGenai()
    with pytest.raises(SystemExit):
        main.run(make_env(plan_json, sha), s3=s3, client=genai)
    assert s3.heads == [] and genai.calls == []


def test_task_index_outside_the_plan():
    with pytest.raises(SystemExit):
        main.run(make_env(CLOUD_RUN_TASK_INDEX="1"), s3=FakeS3(), client=FakeGenai())


def test_logs_never_contain_credentials(capsys):
    main.run(make_env(), s3=FakeS3(), client=FakeGenai())
    out = capsys.readouterr()
    assert SECRET not in out.out + out.err and TOKEN not in out.out + out.err


def test_missing_credentials_stop_before_generation():
    env = make_env()
    del env["R2_TEMP_CREDENTIALS"]
    genai = FakeGenai()
    with pytest.raises(SystemExit):
        main.run(env, client=genai)
    assert genai.calls == []


@pytest.mark.parametrize(
    "credentials",
    [
        "not json " + SECRET,
        "[]",
        json.dumps({"access_key_id": "AKID"}),
        make_credentials(expires_in=60),  # 残りが 5 分未満
        make_credentials(expires_in=-10),  # 期限切れ
        make_credentials(expires_at="tomorrow"),
        make_credentials(session_token=""),
    ],
)
def test_bad_or_expiring_credentials_stop_before_generation(credentials, capsys):
    genai = FakeGenai()
    with pytest.raises(SystemExit):
        main.run(make_env(R2_TEMP_CREDENTIALS=credentials), client=genai)
    assert genai.calls == []
    out = capsys.readouterr()
    assert SECRET not in out.out + out.err and TOKEN not in out.out + out.err


def test_account_id_must_be_32_hex():
    with pytest.raises(SystemExit):
        main.make_s3(make_env(R2_ACCOUNT_ID="evil.example.com/x"))


class _Raw:
    def stream(self, *args, **kwargs):
        yield b""


def test_real_boto3_client_builds_the_expected_r2_request():
    """boto3 の本物のクライアントを作り、送信直前に止めて、ヘッダーを確かめる（通信しない）。"""
    s3 = main.make_s3(make_env())
    captured = []

    def before_send(request, **kwargs):
        captured.append(request)
        return AWSResponse(request.url, 200, {}, _Raw())

    s3.meta.events.register("before-send.s3.*", before_send)

    assert s3.meta.endpoint_url == f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"
    assert s3.meta.region_name == "auto"

    key = "docunavi-hero/42/abcdef0123456789.png"
    s3.put_object(Bucket=BUCKET, Key=key, Body=PNG, ContentType="image/png", IfNoneMatch="*")
    s3.head_object(Bucket=BUCKET, Key=key)

    put, head = captured
    assert put.method == "PUT" and head.method == "HEAD"
    assert put.url == f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com/{BUCKET}/{key}"
    headers = {name.lower(): value.decode() if isinstance(value, bytes) else value for name, value in put.headers.items()}
    assert headers["if-none-match"] == "*"
    assert headers["content-type"] == "image/png"
    assert headers["x-amz-security-token"] == TOKEN
    assert "/auto/s3/aws4_request" in headers["authorization"]
    assert not any(name.startswith("x-amz-checksum") or name == "x-amz-trailer" for name in headers)
    body = put.body.read() if hasattr(put.body, "read") else put.body
    assert body == PNG
