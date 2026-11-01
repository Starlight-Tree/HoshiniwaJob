import hashlib
import json
import os
import re
import sys

from google import genai
from google.cloud import storage
from google.genai import types

MODEL = "gemini-3.1-flash-lite-image"  # Nano Banana 2 Lite
ASPECT_RATIOS = {"1:1", "16:9", "4:3", "3:2"}
MAX_IMAGES = 20  # 1 回の承認の上限。plan がこれを超えていたら動かない
MAX_PROMPT_CHARS = 1000


def fail(message):
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def split_gcs_uri(uri):
    match = re.fullmatch(r"gs://([^/]+)/(.+)", uri)
    if not match:
        fail("a gs://bucket/path URI is required")
    return match.group(1), match.group(2)


def load_plan(gcs, plan_uri, expected_sha256):
    """承認された plan だけを読む。ハッシュが合わなければ、API を呼ぶ前に止まる。"""
    bucket, path = split_gcs_uri(plan_uri)
    data = gcs.bucket(bucket).blob(path).download_as_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        fail("plan.json does not match PLAN_SHA256 (it was changed after approval)")
    plan = json.loads(data)
    items = plan.get("items")
    if not isinstance(items, list) or not items:
        fail("plan.json has no items")
    if len(items) > min(int(plan.get("max_images", MAX_IMAGES)), MAX_IMAGES):
        fail("plan.json has more items than max_images")
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


def main():
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "imagen-app-2026")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    task_index = int(os.environ.get("CLOUD_RUN_TASK_INDEX", "0"))
    plan_uri = os.environ.get("PLAN_GCS_URI") or fail("PLAN_GCS_URI is required")
    plan_sha256 = os.environ.get("PLAN_SHA256") or fail("PLAN_SHA256 is required")
    output_prefix = (os.environ.get("OUTPUT_GCS_PREFIX") or fail("OUTPUT_GCS_PREFIX is required")).rstrip("/")

    gcs = storage.Client(project=project_id)
    document_id, prompt, aspect_ratio = pick_item(load_plan(gcs, plan_uri, plan_sha256), task_index)

    print(f"Generating 1 image for document {document_id} (Task #{task_index}, {aspect_ratio}, {location})")
    client = genai.Client(vertexai=True, project=project_id, location=location)
    image_bytes = generate(client, prompt, aspect_ratio)
    if image_bytes is None:
        fail("no image was returned")

    bucket, prefix = split_gcs_uri(f"{output_prefix}/{document_id}/{plan_sha256[:16]}.png")
    gcs.bucket(bucket).blob(prefix).upload_from_string(image_bytes, content_type="image/png")
    print(f"Saved {len(image_bytes)} bytes to gs://{bucket}/{prefix}")


if __name__ == "__main__":
    main()
