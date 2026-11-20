"""Google でのログイン（OpenID Connect の認可コードの流れ）のうち、API が受け持つ部分。

流れ: 画面のサーバーが Google の同意画面へ送り出し（state・nonce・PKCE を自分で作って Cookie に持つ）、戻ってきた code を、この API の
`POST /api/auth/google` に渡す。API は code をクライアントのシークレットで Google に渡して ID トークンに換え、中身を確かめて、利用者を探す・紐づける・作る。
クライアントのシークレットは、この API だけが持つ。画面のサーバーにも、ブラウザーにも渡さない。

ID トークンの署名は検証しない。トークンは、こちらが Google のトークンのエンドポイント（TLS）へ、クライアントのシークレットと code を添えて
直接取りに行った応答の中にあるので、OpenID Connect Core 3.1.3.7 の手順 6 のとおり、TLS で相手が Google だと確かめられていれば、署名の検証は省いてよい。
そのかわり、発行者（iss）・宛先（aud）・期限（exp）・nonce・メールの確認済み（email_verified）は、ここで必ず確かめる。
エラーの本文は固定の文にする（Google の応答や例外の文字列は、API の応答にもログにも出さない）。
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

import jwt

TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")
TIMEOUT_SECONDS = 10


class GoogleLoginError(Exception):
    """Google でのログインに失敗した。メッセージは利用者に見せてよい固定の文だけ（内部の情報を入れない）。"""


@dataclass(frozen=True)
class GoogleProfile:
    sub: str
    email: str
    last_name: str | None
    first_name: str | None
    avatar_url: str | None


def exchange_code(code: str, code_verifier: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    """code を、Google のトークンのエンドポイントで ID トークンなどに換える。失敗したら GoogleLoginError（Google の本文は出さない）。"""
    body = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": code_verifier,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }
    ).encode()
    request = urllib.request.Request(TOKEN_ENDPOINT, data=body, method="POST")  # noqa: S310 固定の https の URL
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            data = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        raise GoogleLoginError("Google でのログインに失敗しました。もう一度お試しください") from None
    if not isinstance(data, dict) or not isinstance(data.get("id_token"), str):
        raise GoogleLoginError("Google でのログインに失敗しました。もう一度お試しください")
    return data


def _text(value: object, limit: int) -> str | None:
    return value.strip()[:limit] if isinstance(value, str) and value.strip() else None


def profile_from_id_token(id_token: str, client_id: str, nonce: str, now: float | None = None) -> GoogleProfile:
    """ID トークンの中身を確かめて、利用者の情報を取り出す。宛先・発行者・期限・nonce・メールの確認済みが 1 つでも合わなければ GoogleLoginError。"""
    failed = GoogleLoginError("Google でのログインに失敗しました。もう一度お試しください")
    try:
        claims = jwt.decode(id_token, options={"verify_signature": False})  # 署名を省く理由は、このファイルの冒頭
    except jwt.PyJWTError:
        raise failed from None
    now = time.time() if now is None else now
    aud = claims.get("aud")
    audiences = aud if isinstance(aud, list) else [aud]
    exp = claims.get("exp")
    if (
        claims.get("iss") not in ISSUERS
        or client_id not in audiences
        or not isinstance(exp, (int, float))
        or exp <= now
        or claims.get("nonce") != nonce
    ):
        raise failed
    sub = _text(claims.get("sub"), 255)
    email = _text(claims.get("email"), 254)
    if not sub or not email:
        raise failed
    if claims.get("email_verified") is not True:
        raise GoogleLoginError("この Google アカウントのメールアドレスは、確認が済んでいないため使えません")
    picture = _text(claims.get("picture"), 2048)
    return GoogleProfile(
        sub=sub,
        email=email.lower(),
        last_name=_text(claims.get("family_name"), 50),
        first_name=_text(claims.get("given_name"), 50),
        avatar_url=picture if picture and picture.startswith("https://") else None,
    )
