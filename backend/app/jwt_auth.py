"""求職者のログイン（画面のサーバーの中の Better Auth が発行した JWT の検証）。docunavi の app/auth.py と同じ考え方の、同期版。

ログイン（Google との通信・セッション・JWT の発行）は Better Auth（Next.js の中。`frontend/src/lib/auth.ts`）の仕事で、この API は扱わない。画面のサーバーが、ログイン中の人の JWT を
`Authorization: Bearer <JWT>` で送ってくるので、ここで確かめる。

- 署名の検証は、Better Auth の JWKS（`AUTH_JWKS_URL`。画面のサーバーが配る）の公開鍵（ES256 / RS256）だけで行う。alg=none や HS256（公開鍵を共有秘密として使う攻撃）は受け付けない。
  発行元（`iss`）は `AUTH_BASE_URL`（画面の公開オリジン）、対象（`aud`）は `AUTH_AUDIENCE`（既定 jobnavi）。`exp` `iss` `aud` `sub` は必須。
- 利用者の ID は、検証に通ったトークンの `sub` だけから取る。クライアントが送った別の値は使わない。
- トークンの中身・Authorization ヘッダはログに出さない。ログに残すのは、失敗の種類（例外のクラス名）だけ。
- 鍵を取れないときは、前に取れた鍵で続ける。前の鍵が無ければ、検証できない（`AuthUnavailable`。呼び出し側は 503）。共有秘密の検証には切り替えない。
"""

import json
import logging
import re
import threading
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import jwt

from app import settings

logger = logging.getLogger(__name__)

# 署名に使ってよいアルゴリズムと鍵の種類。alg=none や HS256 を受け付けない
ALLOWED_ALGORITHMS = ("ES256", "RS256")
_ALLOWED_KEY_TYPES = ("EC", "RSA")
# Better Auth の利用者 ID（英数字と _ -）
_USER_ID = re.compile(r"[A-Za-z0-9_-]{8,64}")
_REQUIRED_CLAIMS = ["exp", "iss", "aud", "sub"]
# 端末・サーバーの時計のずれを許す秒数
_LEEWAY_SECONDS = 10
# JWKS の取得: 1 回の待ち時間の上限と、読む本文の上限
_FETCH_TIMEOUT_SECONDS = 5.0
_MAX_JWKS_BYTES = 1_000_000
# 取得した鍵を使い続ける時間。過ぎたら取り直す（取り直しに失敗したときは、前の鍵を使い続ける）
_KEYS_TTL_SECONDS = 600.0
# 未知の kid を理由にした取り直しの最小間隔。でたらめな kid のトークンで、JWKS への問い合わせを増幅させないため
_MIN_REFRESH_INTERVAL_SECONDS = 60.0
_JWKS_USER_AGENT = "jobnavi-api/1.0"
DISPLAY_NAME_MAX = 30  # 表示名の上限（schemas.py・画面と同じ）
_MAX_EMAIL = 254
_MAX_PICTURE = 2048

# テストが差し替える（時計と、JWKS の取得）
_now: Callable[[], float] = time.monotonic


class AuthNotConfigured(Exception):
    """AUTH_BASE_URL / AUTH_JWKS_URL が無い。ログインは使えない（呼び出し側は 503）。"""


class InvalidToken(Exception):
    """トークンを受け付けない。理由はログ用で、クライアントへは返さない。"""


class AuthUnavailable(Exception):
    """鍵を取得できず、検証できない。"""


@dataclass(frozen=True)
class Identity:
    """検証に通った JWT から取り出した、ログイン中の人。sub は Better Auth の利用者 ID（users.auth_user_id と結ぶ）。"""

    sub: str
    email: str
    name: str | None  # 表示名の初期値（Google の名前を 30 文字まで）。無ければ None
    picture: str | None


def fetch_jwks_document(url: str) -> dict[str, Any]:
    """JWKS を取得して JSON として返す（同期）。"""
    request = urllib.request.Request(  # noqa: S310 (http/https は設定の読み取りで検証済み)
        url, headers={"Accept": "application/json", "User-Agent": _JWKS_USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=_FETCH_TIMEOUT_SECONDS) as response:  # noqa: S310
        body = response.read(_MAX_JWKS_BYTES + 1)
    if len(body) > _MAX_JWKS_BYTES:
        raise ValueError("JWKS が大きすぎます")
    document = json.loads(body)
    if not isinstance(document, dict):
        raise ValueError("JWKS が JSON のオブジェクトではありません")
    return document


def _parse_keys(document: dict[str, Any]) -> dict[str, jwt.PyJWK]:
    """JWKS から、使ってよい鍵（EC / RSA で kid があるもの）だけを kid で引ける形にする。"""
    keys: dict[str, jwt.PyJWK] = {}
    raw_keys = document.get("keys")
    for item in raw_keys if isinstance(raw_keys, list) else []:
        if not isinstance(item, dict) or item.get("kty") not in _ALLOWED_KEY_TYPES:
            continue
        kid = item.get("kid")
        if not isinstance(kid, str) or not kid:
            continue
        try:
            key = jwt.PyJWK(item)
        except jwt.PyJWTError:
            continue
        if key.algorithm_name in ALLOWED_ALGORITHMS:
            keys[kid] = key
    return keys


class JwksCache:
    """JWKS の公開鍵の置き場。期限が来たら取り直し、未知の kid は間隔を空けて取り直す。"""

    def __init__(self, url: str) -> None:
        self.url = url
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at: float | None = None  # 最後に取得に成功した時刻
        self._attempted_at: float | None = None  # 最後に取得を試みた時刻
        self._lock = threading.Lock()

    def _refresh_locked(self) -> None:
        self._attempted_at = _now()
        self._keys = _parse_keys(fetch_jwks_document(self.url))
        self._fetched_at = _now()

    def get_key(self, kid: str) -> "jwt.PyJWK | None":
        with self._lock:
            now = _now()
            expired = self._fetched_at is None or now - self._fetched_at >= _KEYS_TTL_SECONDS
            if not expired and kid in self._keys:
                return self._keys[kid]
            recently = self._attempted_at is not None and now - self._attempted_at < _MIN_REFRESH_INTERVAL_SECONDS
            if recently and self._keys:
                return self._keys.get(kid)
            try:
                self._refresh_locked()
            except Exception as exc:
                # 失敗の種類だけを残す（URL・本文は出さない）。前の鍵があれば、それで検証を続ける
                logger.warning("JWKS を取得できませんでした (%s)", type(exc).__name__)
                if not self._keys:
                    raise AuthUnavailable from exc
            return self._keys.get(kid)


_cache: JwksCache | None = None
_cache_lock = threading.Lock()


def _cache_for(url: str) -> JwksCache:
    global _cache
    with _cache_lock:
        if _cache is None or _cache.url != url:
            _cache = JwksCache(url)
        return _cache


def _text(value: Any, limit: int) -> str | None:
    """前後の空白を除いた、1〜limit 文字の文字列。そうでなければ None。"""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if 0 < len(value) <= limit else None


def _display_name(value: Any) -> str | None:
    """Google の名前を、表示名の上限（30 文字。コードポイント）までにした値。空・文字列でなければ None（制御文字は持たない）。"""
    if not isinstance(value, str):
        return None
    value = "".join(ch for ch in value if ch.isprintable()).strip()[:DISPLAY_NAME_MAX]
    return value.strip() or None


def _identity(claims: dict[str, Any]) -> Identity:
    sub = claims.get("sub")
    if not isinstance(sub, str) or not _USER_ID.fullmatch(sub):
        raise InvalidToken("sub")
    email = _text(claims.get("email"), _MAX_EMAIL)
    # メールが確認済みでなければ、既存の人との結びつけに使えない（乗っ取りを防ぐ）。Google のメールは確認済み
    if email is None or "@" not in email or claims.get("email_verified") is not True:
        raise InvalidToken("email")
    picture = _text(claims.get("picture"), _MAX_PICTURE)
    return Identity(
        sub=sub,
        email=email.lower(),
        name=_display_name(claims.get("name")),
        # 画面は https の画像だけを表示する。それ以外は持たない
        picture=picture if picture and picture.startswith("https://") else None,
    )


def verify_token(token: str) -> Identity:
    """トークンを検証して、ログイン中の人を返す。受け付けないときは InvalidToken、設定が無いときは AuthNotConfigured、鍵が取れないときは AuthUnavailable。"""
    config = settings.auth_jwt()
    if config is None:
        raise AuthNotConfigured
    issuer, jwks_url, audience = config
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise InvalidToken("malformed") from exc
    alg, kid = header.get("alg"), header.get("kid")
    if alg not in ALLOWED_ALGORITHMS:
        raise InvalidToken("algorithm")
    if not isinstance(kid, str) or not kid:
        raise InvalidToken("kid")

    key = _cache_for(jwks_url).get_key(kid)
    if key is None or key.algorithm_name != alg:
        raise InvalidToken("unknown_key")
    try:
        claims = jwt.decode(
            token,
            key.key,
            algorithms=[alg],
            audience=audience,
            issuer=issuer,
            leeway=_LEEWAY_SECONDS,
            options={"require": _REQUIRED_CLAIMS},
        )
    except jwt.PyJWTError as exc:
        raise InvalidToken(type(exc).__name__) from exc
    return _identity(claims)
