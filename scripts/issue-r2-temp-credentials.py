#!/usr/bin/env python3
"""R2 の一時キーを、親の鍵でローカルに署名して作る（標準ライブラリーだけ。通信しない）。

親の JSON（access_key_id と secret_access_key）を標準入力から読み、一時キーの JSON を標準出力へ出す。
値は引数にもファイルにも置かない。標準エラーには種類・期限・バケット・prefix だけを出す。
操作は種類（write / read）で固定し、引数では広げられない。

形式は Cloudflare の公式文書（Temporary access credentials）による。実 R2 での動作は未確認。
"""
import argparse
import base64
import hashlib
import hmac
import json
import re
import sys
import time
from datetime import datetime, timezone

KINDS = {
    "write": ["PutObject", "HeadObject"],
    "read": ["GetObject", "HeadObject"],
}
TTL_MIN, TTL_MAX = 900, 1800  # 15〜30 分


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def issue(parent, kind, account_id, bucket, prefix, ttl, now=None):
    if kind not in KINDS:
        raise ValueError("kind must be write or read")
    if not re.fullmatch(r"[0-9a-f]{32}", account_id):
        raise ValueError("account id must be 32 hex characters")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket):
        raise ValueError("invalid bucket name")
    if not re.fullmatch(r"[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*/", prefix) or ".." in prefix:
        raise ValueError("prefix must be a relative path ending with /")
    if not TTL_MIN <= ttl <= TTL_MAX:
        raise ValueError(f"ttl must be between {TTL_MIN} and {TTL_MAX} seconds")
    access_key_id = parent.get("access_key_id")
    secret_access_key = parent.get("secret_access_key")
    if not isinstance(access_key_id, str) or not access_key_id:
        raise ValueError("parent access_key_id is missing")
    if not isinstance(secret_access_key, str) or not secret_access_key:
        raise ValueError("parent secret_access_key is missing")

    iat = int(now if now is not None else time.time())
    exp = iat + ttl
    header = {"alg": "HS256", "typ": "JWT"}
    claims = {
        "bucket": bucket,
        "actions": KINDS[kind],
        "paths": {"prefixPaths": [prefix]},
        "sub": account_id,
        "iss": access_key_id,
        "aud": f"{account_id}.r2.cloudflarestorage.com",
        "iat": iat,
        "exp": exp,
    }
    signing_input = ".".join(
        b64url(json.dumps(part, separators=(",", ":")).encode("utf-8")) for part in (header, claims)
    )
    signature = hmac.new(secret_access_key.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    jwt = f"{signing_input}.{b64url(signature)}"
    return {
        "access_key_id": access_key_id,
        "secret_access_key": hashlib.sha256(jwt.encode("ascii")).hexdigest(),
        "session_token": base64.b64encode(f"jwt/{jwt}".encode("ascii")).decode("ascii"),
        "expires_at": datetime.fromtimestamp(exp, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main(argv=None, stdin=None, stdout=None, stderr=None):
    stdin, stdout, stderr = stdin or sys.stdin, stdout or sys.stdout, stderr or sys.stderr
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kind", required=True, choices=sorted(KINDS))
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--ttl", type=int, default=1200)
    args = parser.parse_args(argv)
    try:
        parent = json.loads(stdin.read())
        if not isinstance(parent, dict):
            raise ValueError("parent JSON must be an object")
        result = issue(parent, args.kind, args.account_id, args.bucket, args.prefix, args.ttl)
    except json.JSONDecodeError:  # ValueError の子なので先に捕まえる。親の値を文に入れない
        print("error: parent is not valid JSON", file=stderr)
        return 1
    except ValueError as error:  # issue() が自分で決めた文だけを投げる
        print(f"error: {error}", file=stderr)
        return 1
    stdout.write(json.dumps(result))
    print(
        f"issued kind={args.kind} actions={','.join(KINDS[args.kind])} bucket={args.bucket} "
        f"prefix={args.prefix} expires_at={result['expires_at']}",
        file=stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
