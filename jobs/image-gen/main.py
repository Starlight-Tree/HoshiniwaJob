import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from google import genai
from google.genai import types

MODEL = "gemini-3.1-flash-lite-image"  # Nano Banana 2 Lite
ASPECT_RATIOS = {"1:1", "16:9", "4:3", "3:2"}
MAX_IMAGES = 20  # 1 回の承認の上限。plan がこれを超えていたら動かない
MAX_PROMPT_CHARS = 1000
OUTPUT_PREFIX = "docunavi-hero/"  # 一時キーの許可範囲と同じ。環境変数にしない
MISSING_CODES = {"404", "NoSuchKey", "NotFound"}
EXISTS_CODES = {"412", "PreconditionFailed"}
MIN_REMAINING_SECONDS = 300  # 一時キーの残りがこれより短ければ、生成（課金）の前に止まる


def fail(message):
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def require_env(env, name):
    return env.get(name) or fail(f"{name} is required")


def load_plan(plan_json, expected_sha256):
    """承認された plan だけを読む。ハッシュが合わなければ、API を呼ぶ前に止まる。"""
    if hashlib.sha256(plan_json.encode("utf-8")).hexdigest() != expected_sha256:
        fail("PLAN_JSON does not match PLAN_SHA256 (it was changed after approval)")
    plan = json.loads(plan_json)
    items = plan.get("items")
    if not isinstance(items, list) or not items:
        fail("plan has no items")
    if len(items) > min(int(plan.get("max_images", MAX_IMAGES)), MAX_IMAGES):
        fail("plan has more items than max_images")
    return items


def pick_item(items, task_index):
    if not 0 <= task_index < len(items):
        fail(f"task index {task_index} is outside the plan ({len(items)} items)")
    item = items[task_index]
    document_id = str(item.get("document_id", ""))
    prompt = item.get("prompt")
    aspect_ratio = item.get("aspect_ratio", "1:1")
    if not re.fullmatch(r"[0-9]+", document_id):
        fail("document_id must be digits")
    if not isinstance(prompt, str) or not 0 < len(prompt) <= MAX_PROMPT_CHARS:
        fail("prompt is missing or too long")
    if aspect_ratio not in ASPECT_RATIOS:
        fail(f"aspect_ratio must be one of {sorted(ASPECT_RATIOS)}")
    return document_id, prompt, aspect_ratio


def sniff_content_type(data):
    """拡張子は .png 固定。Content-Type だけ、実際のバイト列で決める。"""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def load_temp_credentials(env, now=None):
    """R2_TEMP_CREDENTIALS（JSON）を読み、期限が近ければ生成の前に止める。値はメッセージに入れない。"""
    try:
        credentials = json.loads(require_env(env, "R2_TEMP_CREDENTIALS"))
        values = {name: credentials[name] for name in ("access_key_id", "secret_access_key", "session_token")}
        expires_at = datetime.strptime(credentials["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, KeyError, TypeError):
        fail("R2_TEMP_CREDENTIALS is not the expected JSON")
    if not all(isinstance(value, str) and value for value in values.values()):
        fail("R2_TEMP_CREDENTIALS is not the expected JSON")
    remaining = expires_at.timestamp() - (now if now is not None else time.time())
    if remaining < MIN_REMAINING_SECONDS:
        fail("R2_TEMP_CREDENTIALS has expired or is about to expire; issue new ones")
    return values


def make_s3(env, now=None):
    """R2 の S3 互換 API。渡されるのは PutObject と HeadObject だけの一時キー（親トークンは渡さない）。"""
    account_id = require_env(env, "R2_ACCOUNT_ID")
    if not re.fullmatch(r"[0-9a-f]{32}", account_id):
        fail("R2_ACCOUNT_ID must be 32 hex characters")
    credentials = load_temp_credentials(env, now)
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
            # 既定の追加チェックサム（boto3 1.36 以降）を付けない
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
            retries={"mode": "standard", "max_attempts": 3},
        ),
    )


def error_code(error):
    return str(error.response.get("Error", {}).get("Code", "unknown"))


def object_exists(s3, bucket, key):
    try:
        s3.head_object(Bucket=bucket, Key=key)
    except ClientError as error:
        if error_code(error) in MISSING_CODES:
            return False
        fail(f"head_object failed ({error_code(error)})")
    return True


def generate(client, prompt, aspect_ratio):
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
        ),
    )
    for candidate in response.candidates or []:
        for part in (candidate.content.parts if candidate.content else None) or []:
            if part.inline_data and part.inline_data.data:
                return part.inline_data.data
    return None


def run(env, s3=None, client=None):
    project_id = env.get("GOOGLE_CLOUD_PROJECT", "imagen-app-2026")
    location = env.get("GOOGLE_CLOUD_LOCATION", "global")
    task_index = int(env.get("CLOUD_RUN_TASK_INDEX", "0"))
    plan_json = require_env(env, "PLAN_JSON")
    plan_sha256 = require_env(env, "PLAN_SHA256")
    bucket = require_env(env, "R2_BUCKET")
    if not re.fullmatch(r"[0-9a-f]{64}", plan_sha256):
        fail("PLAN_SHA256 must be 64 hex characters")

    document_id, prompt, aspect_ratio = pick_item(load_plan(plan_json, plan_sha256), task_index)
    key = f"{OUTPUT_PREFIX}{document_id}/{plan_sha256[:16]}.png"
    s3 = s3 or make_s3(env)

    # 同じ plan で保存済みなら、課金される生成を呼ばずに終わる
    if object_exists(s3, bucket, key):
        print(f"Already saved, skipped generation: {key}")
        return

    print(f"Generating 1 image for document {document_id} (Task #{task_index}, {aspect_ratio}, {location})")
    client = client or genai.Client(vertexai=True, project=project_id, location=location)
    image_bytes = generate(client, prompt, aspect_ratio)
    if image_bytes is None:
        fail("no image was returned")
    content_type = sniff_content_type(image_bytes)
    if content_type is None:
        fail("the returned data is not a PNG, JPEG or WebP image; nothing was saved")

    try:
        s3.put_object(Bucket=bucket, Key=key, Body=image_bytes, ContentType=content_type, IfNoneMatch="*")
    except ClientError as error:
        if error_code(error) in EXISTS_CODES:
            print(f"Already saved, not overwritten: {key}")
            return
        fail(f"put_object failed ({error_code(error)})")
    print(f"Saved {len(image_bytes)} bytes to {key}")


def main():
    run(os.environ)


if __name__ == "__main__":
    main()
