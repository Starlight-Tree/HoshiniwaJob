import os
from urllib.parse import urlsplit


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL が未設定です")
    return url


def cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000")
    return [o.strip() for o in raw.split(",") if o.strip()]


# ---- 画像の保存（app/storage.py）。値はすべて環境変数で渡す。認証情報をコード・ログ・Git に置かない。 ----


def storage_backend() -> str:
    """local（フォルダー。テストとオフラインの開発用）/ s3（S3 互換。Cloudflare R2 など）。"""
    value = os.environ.get("STORAGE_BACKEND", "local")
    if value not in ("local", "s3"):
        raise RuntimeError("STORAGE_BACKEND は local か s3 にしてください")
    return value


def storage_local_dir() -> str:
    return os.environ.get("STORAGE_LOCAL_DIR", "/data/media")


def image_public_base_url() -> str:
    """公開画像の URL の頭（末尾の / なし）。s3 では CDN の独自ドメイン（https://…）、local では API が配る /media。"""
    default = "/media" if storage_backend() == "local" else ""
    value = os.environ.get("IMAGE_PUBLIC_BASE_URL", default).rstrip("/")
    if not value:
        raise RuntimeError("IMAGE_PUBLIC_BASE_URL が未設定です")
    return value


def require_demo_data_allowed() -> None:
    """ダミーデータの投入（seed_demo / seed_images）は、DEMO_DATA=allow を明示した環境だけ。本番の環境には、この値を渡さない。"""
    if os.environ.get("DEMO_DATA") != "allow":
        raise SystemExit("ダミーデータの投入は、DEMO_DATA=allow を渡した開発・テストの環境だけです。実行しませんでした。")


# ---- ログイン（app/jwt_auth.py）。画面のサーバーの中の Better Auth が出す JWT を、JWKS の公開鍵で検証する。値は環境変数で渡す。 ----

DEFAULT_AUTH_AUDIENCE = "hoshiniwajob"


def _http_url(name: str) -> str | None:
    """環境変数の URL（末尾の / なし）。未設定・空は None。http(s) 以外・ホストなしは起動の設定ミスとして例外にする。"""
    raw = os.environ.get(name, "").strip().rstrip("/")
    if not raw:
        return None
    parts = urlsplit(raw)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise RuntimeError(f"{name} は http(s) の URL にしてください")
    return raw


def auth_jwt() -> tuple[str, str, str] | None:
    """(発行元 iss, JWKS の URL, 対象 aud)。AUTH_BASE_URL（画面の公開オリジン。Better Auth の baseURL と同じ）か AUTH_JWKS_URL（API から届く、画面のサーバー（Better Auth）の鍵の URL）が無ければ None（ログインは使えない）。"""
    issuer = _http_url("AUTH_BASE_URL")
    jwks_url = _http_url("AUTH_JWKS_URL")
    if issuer is None or jwks_url is None:
        return None
    return issuer, jwks_url, os.environ.get("AUTH_AUDIENCE", "").strip() or DEFAULT_AUTH_AUDIENCE


def required_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"{name} が未設定です")
    return value


def max_upload_bytes() -> int:
    return int(os.environ.get("IMAGE_MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
