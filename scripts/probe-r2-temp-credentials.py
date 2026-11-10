#!/usr/bin/env python3
"""発行した一時キー（write / read）が、R2 で意図どおりの権限になっているかを確かめる小さなプローブ。

環境変数 W_JSON / R_JSON（issue-r2-temp-credentials.py の出力）と、R2_ACCOUNT_ID・R2_BUCKET を読む。
書き込むのは docunavi-hero/test/ の下の小さな PNG 1 つだけ（削除はしない）。
画面に出すのは、確認の名前・期待・実際のステータス・結果だけ。キーの値・トークンは出さない。
boto3 の設定は jobs/image-gen/main.py の make_s3 と同じ。
"""
import json
import os
import sys
import time

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

PREFIX = "docunavi-hero/"
PNG = b"\x89PNG\r\n\x1a\n" + b"probe"


def client(account_id, credentials):
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        region_name="auto",
        aws_access_key_id=credentials["access_key_id"],
        aws_secret_access_key=credentials["secret_access_key"],
        aws_session_token=credentials["session_token"],
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
            retries={"mode": "standard", "max_attempts": 1},
        ),
    )


def status_of(call):
    try:
        call()
    except ClientError as error:
        return error.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
    return 200


def main():
    account_id, bucket = os.environ["R2_ACCOUNT_ID"], os.environ["R2_BUCKET"]
    write = client(account_id, json.loads(os.environ["W_JSON"]))
    read = client(account_id, json.loads(os.environ["R_JSON"]))
    key = f"{PREFIX}test/{int(time.time())}-probe.png"
    missing = f"{PREFIX}test/{int(time.time())}-never-written.png"
    outside = "docunavi-probe-outside/never-written.png"

    checks = [
        ("write: HeadObject 未保存キー", 404, lambda: write.head_object(Bucket=bucket, Key=missing)),
        ("write: PutObject (If-None-Match)", 200, lambda: write.put_object(Bucket=bucket, Key=key, Body=PNG, ContentType="image/png", IfNoneMatch="*")),
        ("write: PutObject 2 回目は上書きしない", 412, lambda: write.put_object(Bucket=bucket, Key=key, Body=PNG, ContentType="image/png", IfNoneMatch="*")),
        ("write: HeadObject 保存済みキー", 200, lambda: write.head_object(Bucket=bucket, Key=key)),
        ("write: GetObject は許可されない", 403, lambda: write.get_object(Bucket=bucket, Key=key)),
        ("write: prefix 外の HeadObject は許可されない", 403, lambda: write.head_object(Bucket=bucket, Key=outside)),
        ("read: HeadObject 未保存キー", 404, lambda: read.head_object(Bucket=bucket, Key=missing)),
        ("read: HeadObject 保存済みキー", 200, lambda: read.head_object(Bucket=bucket, Key=key)),
        ("read: GetObject 保存済みキー", 200, lambda: read.get_object(Bucket=bucket, Key=key)["Body"].read()),
        ("read: PutObject は許可されない", 403, lambda: read.put_object(Bucket=bucket, Key=f"{PREFIX}test/read-must-fail.png", Body=PNG, IfNoneMatch="*")),
        ("read: prefix 外の HeadObject は許可されない", 403, lambda: read.head_object(Bucket=bucket, Key=outside)),
    ]
    failed = 0
    for name, expected, call in checks:
        actual = status_of(call)
        ok = actual == expected
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name}  期待={expected} 実際={actual}")
    print(f"probe key: {key}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
