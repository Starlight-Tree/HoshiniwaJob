"""運営用の画像の操作（登録・取り下げ・点検）。DB と保存先の認証情報（環境変数）を持つ運営だけが実行できる。園の API からは呼べない。

    python -m app.images_cli list [--status rejected]
    python -m app.images_cli register FILE --alt "代替テキスト" (--recruit-id N | --recruit-demo-key KEY) [--hero] [--demo-key KEY]   # 登録した時点で公開される
    python -m app.images_cli reject IMAGE_ID         # 公開後の取り下げ（実体も消す）。承認の操作ではない
    python -m app.images_cli reconcile [--stuck-hours 1]   # DB と保存先の食い違いを報告するだけ（何も変えない）
    python -m app.images_cli formfile                 # recruits.formfile（画像ファイル名の列）に値のある求人の一覧
"""

import argparse
import sys
import uuid
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.image_service import ImageConflict, ImageRejected, process_image, reconcile, register_image, reject_image
from app.settings import database_url, max_upload_bytes
from app.storage import StorageError, get_storage


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m app.images_cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list")
    ls.add_argument("--status")
    reg = sub.add_parser("register")
    reg.add_argument("file", type=Path)
    reg.add_argument("--alt", required=True)
    target = reg.add_mutually_exclusive_group(required=True)
    target.add_argument("--recruit-id", type=int)
    target.add_argument("--recruit-demo-key")
    reg.add_argument("--hero", action="store_true")
    reg.add_argument("--demo-key")
    sub.add_parser("reject").add_argument("image_id", type=uuid.UUID)
    rec = sub.add_parser("reconcile")
    rec.add_argument("--stuck-hours", type=int, default=1)
    sub.add_parser("formfile")
    return p


def run(args: argparse.Namespace, conn, storage, out=print) -> int:
    if args.cmd == "list":
        rows = conn.execute(
            "SELECT id, status, origin, width, height, alt, (SELECT count(*) FROM recruit_images ri WHERE ri.image_id = images.id) AS recruits "
            "FROM images WHERE (%s::text IS NULL OR status = %s) ORDER BY created_at",
            (args.status, args.status),
        ).fetchall()
        for r in rows:
            out(f"{r['id']}  {r['status']:<10} {r['origin']:<9} {r['width']}x{r['height']}  求人{r['recruits']}件  {r['alt']}")
        out(f"{len(rows)} 件")
    elif args.cmd == "register":
        recruit = conn.execute(
            "SELECT id FROM recruits WHERE " + ("id = %s" if args.recruit_id else "demo_key = %s"), (args.recruit_id or args.recruit_demo_key,)
        ).fetchone()
        if recruit is None:
            out("求人が見つかりません")
            return 1
        processed = process_image(args.file.read_bytes(), max_bytes=max_upload_bytes())
        image_id = register_image(conn, storage, processed, alt=args.alt, origin="generated", demo_key=args.demo_key)
        conn.execute(
            "INSERT INTO recruit_images (recruit_id, image_id, position) SELECT %s, %s, COALESCE(MAX(position) + 1, 0) FROM recruit_images WHERE recruit_id = %s",
            (recruit["id"], image_id, recruit["id"]),
        )
        if args.hero:
            conn.execute("UPDATE recruit_images SET is_hero = (image_id = %s) WHERE recruit_id = %s", (image_id, recruit["id"]))
        conn.commit()
        out(f"登録しました（公開中）: {image_id}")
    elif args.cmd == "reject":
        reject_image(conn, storage, args.image_id)
        out("取り下げました（実体も消しました）")
    elif args.cmd == "reconcile":
        counts = reconcile(conn, storage, stuck_hours=args.stuck_hours, out=out)
        out("報告だけです（何も変えていません）: " + "、".join(f"{k}={v}" for k, v in counts.items()))
    elif args.cmd == "formfile":
        rows = conn.execute("SELECT id, formfile FROM recruits WHERE formfile IS NOT NULL AND formfile <> '' ORDER BY id").fetchall()
        for r in rows:
            out(f"求人 {r['id']}: {r['formfile']}")
        out(f"formfile に値のある求人: {len(rows)} 件")
    return 0


def main(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    try:
        with psycopg.connect(database_url(), row_factory=dict_row) as conn:
            return run(args, conn, get_storage())
    except (ImageRejected, ImageConflict, StorageError) as exc:
        print(f"できませんでした: {exc}")
        return 1
    except psycopg.Error as exc:
        print(f"DB のエラーです（{type(exc).__name__}）")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
