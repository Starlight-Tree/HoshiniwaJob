"""番号付き SQL のマイグレーション実行器（必要な機能だけの小さなもの）。

    python -m app.migrate --status     # 適用状況の表示だけ（DB を変えない）
    python -m app.migrate --dry-run    # 適用するものの一覧と事前の検査だけ（DB を変えない）
    python -m app.migrate              # 未適用のものを順に適用する

- 0001 は、db/schema.sql と db/seed_codes.sql（Postgres の初回起動で流れる初期スキーマ）を指す。実行器はこれを流さない。
  DB に初期スキーマがあるときだけ、表・列・制約・索引・件数を baseline_fingerprint.json と照合し、一致したときに 0001 を「適用済み」と記録する。
  1 つでも違えば、記録せずに止まる（想定外の DB に、先のマイグレーションを重ねないため）。
- 0002 以降は app/migrations/NNNN_名前.sql。1 ファイルを 1 トランザクションで流し、成功したときだけ記録する（lock_timeout 5 秒。ロックが取れなければ失敗して何も変えない）。
- 記録にはファイルの sha256 を残し、適用済みのファイルが書き換わっていたら止まる。直すときは新しい番号のファイルを足す。
- 同時に 2 つ動かないよう、アドバイザリーロックを取る。DROP / TRUNCATE を含むファイルは、このリポジトリでは足さない。
"""

import hashlib
import json
import re
import sys
from pathlib import Path

import psycopg

from app.settings import database_url

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
FINGERPRINT_FILE = MIGRATIONS_DIR / "baseline_fingerprint.json"
BASELINE_VERSION = "0001"
LOCK_KEY = 7_204_001
_FILE = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")
_MASTERS = ("areas", "stations", "occupations", "employments")


class MigrationError(RuntimeError):
    """続行してはいけない状態（スキーマの不一致、チェックサムの不一致など）。メッセージは固定の説明だけで、接続情報を含めない。"""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def migration_files() -> list[tuple[str, str, Path]]:
    """(番号, 名前, パス)。0002 以降を番号順に。番号の重複・欠番は MigrationError。"""
    found = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        match = _FILE.match(path.name)
        if not match:
            raise MigrationError(f"マイグレーションのファイル名が規則に合いません: {path.name}")
        found.append((match.group(1), path.stem, path))
    versions = [v for v, _, _ in found]
    if len(set(versions)) != len(versions):
        raise MigrationError("同じ番号のマイグレーションが複数あります")
    expected = [f"{n:04d}" for n in range(2, 2 + len(found))]
    if versions != expected:
        raise MigrationError(f"番号が 0002 から連続していません: {versions}")
    return found


def fingerprint(conn: psycopg.Connection) -> list[str]:
    """public スキーマの形（表・列・制約・索引・ビュー名・マスタの件数）を、並べ替え済みの文字列の一覧にする。schema_migrations は含めない。"""
    lines: list[str] = []
    for r in conn.execute(
        "SELECT table_name, column_name, data_type, is_nullable, column_default, is_identity FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name <> 'schema_migrations'"
    ):
        lines.append(f"column {r[0]}.{r[1]} {r[2]} null={r[3]} default={r[4]} identity={r[5]}")
    for r in conn.execute(
        "SELECT conrelid::regclass::text, conname, pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE connamespace = 'public'::regnamespace AND conrelid::regclass::text <> 'schema_migrations'"
    ):
        lines.append(f"constraint {r[0]} {r[1]} {r[2]}")
    for r in conn.execute("SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' AND tablename <> 'schema_migrations'"):
        lines.append(f"index {r[0]} {r[1]} {r[2]}")
    for r in conn.execute("SELECT viewname FROM pg_views WHERE schemaname = 'public'"):
        lines.append(f"view {r[0]}")
    for table in _MASTERS:
        lines.append(f"rows {table} {conn.execute(f'SELECT count(*) FROM {table}').fetchone()[0]}")  # noqa: S608（固定の表名）
    return sorted(lines)


def _baseline_diff(conn: psycopg.Connection) -> list[str]:
    expected = set(json.loads(FINGERPRINT_FILE.read_text(encoding="utf-8"))["lines"])
    actual = set(fingerprint(conn))
    return [f"- 足りない: {x}" for x in sorted(expected - actual)] + [f"- 想定外: {x}" for x in sorted(actual - expected)]


def _applied(conn: psycopg.Connection) -> dict[str, tuple[str, str]]:
    if conn.execute("SELECT to_regclass('public.schema_migrations')").fetchone()[0] is None:
        return {}
    return {r[0]: (r[1], r[2]) for r in conn.execute("SELECT version, name, checksum FROM schema_migrations")}


def plan(conn: psycopg.Connection) -> dict:
    """DB を変えずに、今の状態を調べる。戻り値: baseline（'recorded' / 'verified' / 'missing'）、pending、problems。"""
    applied = _applied(conn)
    files = migration_files()
    problems: list[str] = []
    baseline = "recorded"
    if BASELINE_VERSION not in applied:
        if conn.execute("SELECT to_regclass('public.recruits')").fetchone()[0] is None:
            baseline = "missing"
            problems.append("初期スキーマがありません。Postgres の初回起動（db/schema.sql）か、psql で db/schema.sql と db/seed_codes.sql を先に流してください。")
        else:
            diff = _baseline_diff(conn)
            if diff:
                baseline = "mismatch"
                problems.append("DB の形が、想定する初期スキーマと一致しません。適用済みとは記録せず、止めます:")
                problems.extend(diff[:30])
                if len(diff) > 30:
                    problems.append(f"（ほか {len(diff) - 30} 件）")
            else:
                baseline = "verified"
    for version, name, path in files:
        if version in applied:
            if applied[version][1] != _sha256(path.read_bytes()):
                problems.append(f"適用済みのマイグレーション {name} が書き換えられています（記録したチェックサムと違います）。")
    known = {v for v, _, _ in files} | {BASELINE_VERSION}
    for version in applied:
        if version not in known:
            problems.append(f"記録にあるマイグレーション {version} のファイルがありません。")
    pending = [(v, n, p) for v, n, p in files if v not in applied]
    return {"baseline": baseline, "pending": pending, "problems": problems, "applied": sorted(applied)}


def apply(url: str, *, dry_run: bool = False, out=print) -> int:
    """戻り値は終了コード（0 = 成功、1 = 止まった）。dry_run では DB を変えない。"""
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_KEY,))
        try:
            state = plan(conn)
            for line in state["problems"]:
                out(line)
            if state["problems"]:
                return 1
            out(f"初期スキーマ: {'記録済み' if state['baseline'] == 'recorded' else '照合に一致（未記録）'}")
            out("未適用: " + (", ".join(n for _, n, _ in state["pending"]) or "なし"))
            if dry_run:
                return 0
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY, name text NOT NULL, "
                "checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())"
            )
            if state["baseline"] == "verified":
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, checksum) VALUES (%s, 'baseline', %s)",
                    (BASELINE_VERSION, _sha256(FINGERPRINT_FILE.read_bytes())),
                )
                out("0001 baseline を適用済みとして記録しました")
            for version, name, path in state["pending"]:
                sql = path.read_bytes()
                with conn.transaction():
                    conn.execute("SET LOCAL lock_timeout = '5s'")
                    conn.execute(sql.decode("utf-8"))
                    conn.execute("INSERT INTO schema_migrations (version, name, checksum) VALUES (%s, %s, %s)", (version, name, _sha256(sql)))
                out(f"適用: {name}")
            return 0
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))


def write_baseline_fingerprint(url: str) -> None:
    """db/schema.sql と db/seed_codes.sql だけを流した作りたての DB から、照合用の形を書き出す（保守用。通常は使わない）。"""
    with psycopg.connect(url) as conn:
        lines = fingerprint(conn)
    FINGERPRINT_FILE.write_text(json.dumps({"version": 1, "lines": lines}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    try:
        url = database_url()
        if "--write-baseline-fingerprint" in argv:
            write_baseline_fingerprint(url)
            print(f"書き出しました: {FINGERPRINT_FILE}")
            return 0
        if "--status" in argv:
            with psycopg.connect(url, autocommit=True) as conn:
                state = plan(conn)
            print("適用済み:", ", ".join(state["applied"]) or "なし")
            print("初期スキーマ:", state["baseline"])
            print("未適用:", ", ".join(n for _, n, _ in state["pending"]) or "なし")
            for line in state["problems"]:
                print(line)
            return 1 if state["problems"] else 0
        return apply(url, dry_run="--dry-run" in argv)
    except (MigrationError, psycopg.Error) as exc:
        # 接続情報を含みうる例外の本文は出さず、種類だけ出す
        print(f"失敗しました（{type(exc).__name__}）。{exc if isinstance(exc, MigrationError) else 'DB への接続か SQL の実行でエラーです'}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
