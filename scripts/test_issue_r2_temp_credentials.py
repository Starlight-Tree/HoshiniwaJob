"""issue-r2-temp-credentials.py を、偽の鍵で確かめる。通信しない。"""
import base64
import hashlib
import importlib.util
import io
import json
import shutil
import subprocess
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("issuer", Path(__file__).with_name("issue-r2-temp-credentials.py"))
issuer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(issuer)

ACCOUNT_ID = "0123456789abcdef0123456789abcdef"
PARENT = {"access_key_id": "PARENT-KEY-ID", "secret_access_key": "PARENT-SECRET-VALUE"}
ARGS = dict(account_id=ACCOUNT_ID, bucket="test-bucket", prefix="docunavi-hero/", ttl=1200, now=1_800_000_000)


def unb64url(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def split_jwt(result):
    decoded = base64.b64decode(result["session_token"]).decode("ascii")
    assert decoded.startswith("jwt/")
    return decoded[4:]


@pytest.mark.parametrize("kind,actions", [("write", ["PutObject", "HeadObject"]), ("read", ["GetObject", "HeadObject"])])
def test_claims_and_header(kind, actions):
    jwt = split_jwt(issuer.issue(PARENT, kind, **ARGS))
    header, claims, _ = jwt.split(".")
    assert json.loads(unb64url(header)) == {"alg": "HS256", "typ": "JWT"}
    assert json.loads(unb64url(claims)) == {
        "bucket": "test-bucket",
        "actions": actions,
        "paths": {"prefixPaths": ["docunavi-hero/"]},
        "sub": ACCOUNT_ID,
        "iss": "PARENT-KEY-ID",
        "aud": f"{ACCOUNT_ID}.r2.cloudflarestorage.com",
        "iat": 1_800_000_000,
        "exp": 1_800_001_200,
    }


def test_no_delete_or_list_and_no_scope_claim():
    for kind in ("write", "read"):
        claims = json.loads(unb64url(split_jwt(issuer.issue(PARENT, kind, **ARGS)).split(".")[1]))
        assert "scope" not in claims
        assert not {"DeleteObject", "DeleteObjects", "CopyObject", "ListObjectsV2"} & set(claims["actions"])


def test_signature_secret_and_session_token_are_derived_as_documented():
    result = issuer.issue(PARENT, "write", **ARGS)
    jwt = split_jwt(result)
    signing_input, signature = jwt.rsplit(".", 1)
    import hmac

    expected = hmac.new(b"PARENT-SECRET-VALUE", signing_input.encode(), hashlib.sha256).digest()
    assert unb64url(signature) == expected
    assert result["secret_access_key"] == hashlib.sha256(jwt.encode()).hexdigest()
    assert result["access_key_id"] == "PARENT-KEY-ID"
    assert result["expires_at"] == "2027-01-15T08:20:00Z"


@pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl is not installed")
def test_signature_matches_openssl():
    jwt = split_jwt(issuer.issue(PARENT, "read", **ARGS))
    signing_input, signature = jwt.rsplit(".", 1)
    out = subprocess.run(
        ["openssl", "dgst", "-sha256", "-hmac", "PARENT-SECRET-VALUE", "-binary"],
        input=signing_input.encode(),
        capture_output=True,
        check=True,
    ).stdout
    assert unb64url(signature) == out


@pytest.mark.parametrize("ttl", [899, 1801, 0, -1])
def test_ttl_outside_15_to_30_minutes_is_rejected(ttl):
    with pytest.raises(ValueError):
        issuer.issue(PARENT, "write", **{**ARGS, "ttl": ttl})


@pytest.mark.parametrize("ttl", [900, 1800])
def test_ttl_bounds_are_allowed(ttl):
    issuer.issue(PARENT, "write", **{**ARGS, "ttl": ttl})


@pytest.mark.parametrize(
    "override",
    [
        {"account_id": "evil.example.com"},
        {"bucket": "../x"},
        {"prefix": ""},
        {"prefix": "docunavi-hero"},
        {"prefix": "/docunavi-hero/"},
        {"prefix": "a/../b/"},
    ],
)
def test_invalid_inputs_are_rejected(override):
    with pytest.raises(ValueError):
        issuer.issue(PARENT, "write", **{**ARGS, **override})


@pytest.mark.parametrize("parent", [{}, {"access_key_id": "x"}, {"secret_access_key": "x"}, {"access_key_id": "", "secret_access_key": "x"}])
def test_incomplete_parent_is_rejected(parent):
    with pytest.raises(ValueError):
        issuer.issue(parent, "write", **ARGS)


def run_main(stdin_text, *extra):
    out, err = io.StringIO(), io.StringIO()
    code = issuer.main(
        ["--kind", "write", "--account-id", ACCOUNT_ID, "--bucket", "test-bucket", "--prefix", "docunavi-hero/", *extra],
        stdin=io.StringIO(stdin_text),
        stdout=out,
        stderr=err,
    )
    return code, out.getvalue(), err.getvalue()


def test_main_prints_values_only_to_stdout_never_to_stderr():
    code, out, err = run_main(json.dumps(PARENT))
    assert code == 0
    result = json.loads(out)
    assert set(result) == {"access_key_id", "secret_access_key", "session_token", "expires_at"}
    for secret in ("PARENT-SECRET-VALUE", result["secret_access_key"], result["session_token"]):
        assert secret not in err
    assert "kind=write" in err and "actions=PutObject,HeadObject" in err and "prefix=docunavi-hero/" in err


@pytest.mark.parametrize("stdin_text", ["not json PARENT-SECRET-VALUE", "[]", json.dumps({"access_key_id": "a"})])
def test_main_failures_print_no_values_and_no_output(stdin_text):
    code, out, err = run_main(stdin_text)
    assert code == 1 and out == ""
    assert "PARENT-SECRET-VALUE" not in err


def test_main_rejects_bad_ttl_without_output():
    code, out, err = run_main(json.dumps(PARENT), "--ttl", "60")
    assert code == 1 and out == "" and "ttl" in err
