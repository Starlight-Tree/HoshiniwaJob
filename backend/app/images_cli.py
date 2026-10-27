"""運営用の画像の操作（承認・却下・登録・掃除）。DB と保存先の認証情報（環境変数）を持つ運営だけが実行できる。園の API からは呼べない。

    python -m app.images_cli list [--status pending]
    python -m app.images_cli register FILE --alt "代替テキスト" (--recruit-id N | --recruit-demo-key KEY) [--hero] [--approve] [--demo-key KEY]
    python -m app.images_cli approve IMAGE_ID        # 公開側へ複製して公開する（園のアップロードは、ここで承認するまで公開されない）
    python -m app.images_cli reject IMAGE_ID         # 却下、または公開の取り消し
    python -m app.images_cli reconcile [--apply] [--grace-days 30] [--stuck-hours 1]   # 既定は dry-run（一覧だけ）
    python -m app.images_cli formfile                 # recruits.formfile（画像ファイル名の列）に値のある求人の一覧
"""

import argparse
import sys
import uuid
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.image_service import ImageConflict, ImageRejected, approve_image, process_image, reconcile, register_image, reject_image
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
    reg.add_argument("--approve", action="store_true")
    reg.add_argument("--demo-key")
    for name in ("approve", "reject"):
        sub.add_parser(name).add_argument("image_id", type=uuid.UUID)
    rec = sub.add_parser("reconcile")
    rec.add_argument("--apply", action="store_true")
    rec.add_argument("--grace-days", type=int, default=30)
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
        if args.approve:
            approve_image(conn, storage, image_id)
        conn.execute(
            "INSERT INTO recruit_images (recruit_id, image_id, position) SELECT %s, %s, COALESCE(MAX(position) + 1, 0) FROM recruit_images WHERE recruit_id = %s",
            (recruit["id"], image_id, recruit["id"]),
        )
        if args.hero:
            if not args.approve:
                out("--hero には --approve が要ります（承認済みの画像だけがヒーローになれます）。画像は承認待ちで登録しました。")
            else:
                conn.execute("UPDATE recruit_images SET is_hero = (image_id = %s) WHERE recruit_id = %s", (image_id, recruit["id"]))
        conn.commit()
        out(f"登録しました: {image_id}（{'承認済み' if args.approve else '承認待ち'}）")
    elif args.cmd == "approve":
        approve_image(conn, storage, args.image_id)
        out("承認しました")
    elif args.cmd == "reject":
        reject_image(conn, storage, args.image_id)
        out("却下しました（公開側の実体も消しました）")
    elif args.cmd == "reconcile":
        counts = reconcile(conn, storage, apply=args.apply, grace_days=args.grace_days, stuck_hours=args.stuck_hours, out=out)
        out(("実行しました: " if args.apply else "dry-run（何も変えていません）: ") + "、".join(f"{k}={v}" for k, v in counts.items()))
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
