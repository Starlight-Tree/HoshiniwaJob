"""ダミーの求人の画像を、通常の登録・承認の流れ（検証 → 非公開側へ保存 → 承認 → 公開側へ複製）で入れる。
マニフェスト（demo_images.json）の demo_key で、画像と求人を結ぶ。何度実行しても、画像も関連も増えない。

    python -m app.seed_images --source-dir <画像のフォルダー>      # 画像のファイルがあるフォルダーから
    python -m app.seed_images --source-url https://…/demo/         # 画像の置き場（https。末尾に file 名を足して取る）から

- 元のファイルは、マニフェストの sha256 と一致しなければ使わない（別の画像が別の求人に結ばれるのを防ぐ）。
- 求人は recruits.demo_key で探す。見つからなければ、結ばずに知らせる。すでに結ばれている関連（園が変えた並び・ヒーロー）は、再実行で変えない。
- 保存先は STORAGE_BACKEND の設定に従う（local なら開発用のフォルダー、s3 なら設定したバケット）。
"""

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

import psycopg
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row

from app.image_service import approve_image, process_image, register_image
from app.settings import database_url, require_demo_data_allowed
from app.storage import Storage, get_storage

MANIFEST = Path(__file__).parent / "demo_images.json"
SOURCE_MAX_BYTES = 20 * 1024 * 1024


def _read_source(entry: dict, source_dir: Path | None, source_url: str | None) -> bytes:
    if source_dir is not None:
        data = (source_dir / entry["file"]).read_bytes()
    else:
        if not source_url or not source_url.startswith("https://"):
            raise SystemExit("--source-url は https:// で始めてください")
        with urllib.request.urlopen(source_url.rstrip("/") + "/" + entry["file"], timeout=30) as res:  # noqa: S310（https のみ）
            data = res.read(SOURCE_MAX_BYTES + 1)
    if len(data) > SOURCE_MAX_BYTES:
        raise SystemExit(f"{entry['file']} が大きすぎます")
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise SystemExit(f"{entry['file']} の sha256 がマニフェストと一致しません。別の画像かもしれないので、使いません")
    return data


def seed(conn, storage: Storage, *, source_dir: Path | None, source_url: str | None, out=print) -> dict[str, int]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    stats = {"registered": 0, "approved": 0, "linked": 0, "kept": 0, "no_recruit": 0}
    for entry in manifest["images"]:
        image = conn.execute("SELECT id, status FROM images WHERE demo_key = %s", (entry["demo_key"],)).fetchone()
        if image is None:
            data = _read_source(entry, source_dir, source_url)
            processed = process_image(data, max_bytes=SOURCE_MAX_BYTES)
            try:
                image_id = register_image(conn, storage, processed, alt=entry["alt"], origin="generated", demo_key=entry["demo_key"])
                stats["registered"] += 1
            except UniqueViolation:  # 同時に動いた別の実行が先に登録した
                conn.rollback()
                image = conn.execute("SELECT id, status FROM images WHERE demo_key = %s", (entry["demo_key"],)).fetchone()
                image_id = image["id"]
            status = "pending"
        else:
            image_id, status = image["id"], image["status"]
        if status in ("pending", "publishing", "uploading"):
            if status == "uploading":
                out(f"登録の途中の画像があります（{entry['demo_key']}）。python -m app.images_cli reconcile --apply で整えてから、もう一度実行してください")
                continue
            approve_image(conn, storage, image_id)
            stats["approved"] += 1
        elif status != "approved":
            out(f"状態 {status} の画像です（{entry['demo_key']}）。触りません")
            continue
        recruit = conn.execute("SELECT id FROM recruits WHERE demo_key = %s", (entry["recruit_demo_key"],)).fetchone()
        if recruit is None:
            stats["no_recruit"] += 1
            out(f"求人 {entry['recruit_demo_key']} がありません。画像 {entry['demo_key']} は結びません")
            continue
        inserted = conn.execute(
            "INSERT INTO recruit_images (recruit_id, image_id, position) VALUES (%s, %s, %s) ON CONFLICT (recruit_id, image_id) DO NOTHING",
            (recruit["id"], image_id, entry["position"]),
        ).rowcount
        if inserted:
            stats["linked"] += 1
            if entry.get("hero"):
                has_hero = conn.execute("SELECT 1 FROM recruit_images WHERE recruit_id = %s AND is_hero", (recruit["id"],)).fetchone()
                if not has_hero:
                    conn.execute("UPDATE recruit_images SET is_hero = true WHERE recruit_id = %s AND image_id = %s", (recruit["id"], image_id))
        else:
            stats["kept"] += 1
        conn.commit()
    return stats


def main(argv: list[str]) -> int:
    source_dir = Path(argv[argv.index("--source-dir") + 1]) if "--source-dir" in argv else None
    source_url = argv[argv.index("--source-url") + 1] if "--source-url" in argv else None
    if (source_dir is None) == (source_url is None):
        print("--source-dir か --source-url の、どちらか一方を指定してください")
        return 1
    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        stats = seed(conn, get_storage(), source_dir=source_dir, source_url=source_url)
    print("画像: " + "、".join(f"{k}={v}" for k, v in stats.items()))
    return 0


if __name__ == "__main__":
    require_demo_data_allowed()
    sys.exit(main(sys.argv[1:]))
