"""画像の保存先（公開側と非公開側）。差し替え可能な 2 つの実装: LocalStorage（フォルダー）と S3Storage（S3 互換。Cloudflare R2 など）。

- 公開側（public=True）に置くのは、検証済みで承認された画像だけ。審査前の画像は非公開側だけに置く。
- どちらの側でも、キーは同じ（images/<uuid>.<拡張子>）。公開は、非公開側から公開側への複製。
- 同じキーへの上書きはしない（更新は新しいキーで登録する）。put は、そのキーが既にあれば何もしない（同じ内容の再試行で壊れない）。
- 署名付き URL は作らない。公開 URL は、保存キーから public_url で組み立てる。
- 認証情報は環境変数から読み、ログ・例外の本文に出さない。
"""

import os
import re
import tempfile
from functools import lru_cache
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from app import settings

KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9/_.-]{0,200}$")


class StorageError(RuntimeError):
    """保存先の操作の失敗。メッセージは固定の説明だけ（キーや認証情報を含めない）。"""


def check_key(key: str) -> str:
    if not KEY_PATTERN.match(key) or ".." in key or "//" in key or key.endswith("/"):
        raise StorageError("保存キーの形が正しくありません")
    return key


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str, *, public: bool) -> None: ...
    def get(self, key: str, *, public: bool) -> bytes: ...
    def exists(self, key: str, *, public: bool) -> bool: ...
    def delete(self, key: str, *, public: bool) -> None: ...
    def list_keys(self, prefix: str, *, public: bool) -> Iterator[tuple[str, datetime]]: ...
    def public_url(self, key: str) -> str: ...


class LocalStorage:
    """root/public と root/private に置く。public 側だけを API の /media が配る。テストとオフラインの開発用（本番では使わない）。"""

    def __init__(self, root: str | Path, public_base_url: str = "/media") -> None:
        self.root = Path(root)
        self.public_base_url = public_base_url.rstrip("/")

    def _path(self, key: str, public: bool) -> Path:
        base = (self.root / ("public" if public else "private")).resolve()
        path = (base / check_key(key)).resolve()
        if base not in path.parents:
            raise StorageError("保存キーの形が正しくありません")
        return path

    def put(self, key: str, data: bytes, content_type: str, *, public: bool) -> None:
        path = self._path(key, public)
        if path.exists():
            if path.read_bytes() != data:
                raise StorageError("同じキーに別の内容は上書きできません")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp, path)  # 書きかけのファイルを、公開される名前に置かない
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def get(self, key: str, *, public: bool) -> bytes:
        path = self._path(key, public)
        if not path.is_file():
            raise StorageError("画像が見つかりません")
        return path.read_bytes()

    def exists(self, key: str, *, public: bool) -> bool:
        return self._path(key, public).is_file()

    def delete(self, key: str, *, public: bool) -> None:
        self._path(key, public).unlink(missing_ok=True)

    def list_keys(self, prefix: str, *, public: bool) -> Iterator[tuple[str, datetime]]:
        base = (self.root / ("public" if public else "private")).resolve()
        if not base.is_dir():
            return
        for path in sorted(base.rglob("*")):
            if path.is_file() and not path.name.startswith(".tmp-"):
                key = path.relative_to(base).as_posix()
                if key.startswith(prefix):
                    yield key, datetime.fromtimestamp(path.stat().st_mtime, UTC)

    def public_url(self, key: str) -> str:
        return f"{self.public_base_url}/{check_key(key)}"


class S3Storage:
    """S3 互換（Cloudflare R2 など）。公開用と非公開用で、別のバケットを使う。boto3 は使うときだけ読み込む。"""

    def __init__(self, *, endpoint_url: str, public_bucket: str, private_bucket: str, access_key_id: str, secret_access_key: str, public_base_url: str, client=None) -> None:
        if public_bucket == private_bucket:
            raise StorageError("公開用と非公開用のバケットは別にしてください")
        if client is None:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                region_name="auto",
                config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}, connect_timeout=5, read_timeout=30),
            )
        self.client = client
        self.public_bucket = public_bucket
        self.private_bucket = private_bucket
        self.public_base_url = public_base_url.rstrip("/")

    def _bucket(self, public: bool) -> str:
        return self.public_bucket if public else self.private_bucket

    @staticmethod
    def _is_missing(exc: Exception) -> bool:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        return code in ("404", "NoSuchKey", "NotFound")

    def put(self, key: str, data: bytes, content_type: str, *, public: bool) -> None:
        check_key(key)
        bucket = self._bucket(public)
        if self.exists(key, public=public):
            if self.get(key, public=public) != data:
                raise StorageError("同じキーに別の内容は上書きできません")
            return
        extra = {"CacheControl": "public, max-age=31536000, immutable"} if public else {"CacheControl": "private, no-store"}
        try:
            self.client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type, **extra)
        except Exception:  # noqa: BLE001（認証情報を含みうる本文は捨てて、固定の説明にする）
            raise StorageError("画像の保存に失敗しました") from None

    def get(self, key: str, *, public: bool) -> bytes:
        check_key(key)
        try:
            return self.client.get_object(Bucket=self._bucket(public), Key=key)["Body"].read()
        except Exception as exc:  # noqa: BLE001
            raise StorageError("画像が見つかりません" if self._is_missing(exc) else "画像の取得に失敗しました") from None

    def exists(self, key: str, *, public: bool) -> bool:
        check_key(key)
        try:
            self.client.head_object(Bucket=self._bucket(public), Key=key)
            return True
        except Exception as exc:  # noqa: BLE001
            if self._is_missing(exc):
                return False
            raise StorageError("画像の確認に失敗しました") from None

    def delete(self, key: str, *, public: bool) -> None:
        check_key(key)
        try:
            self.client.delete_object(Bucket=self._bucket(public), Key=key)  # 無いキーの削除も成功する
        except Exception:  # noqa: BLE001
            raise StorageError("画像の削除に失敗しました") from None

    def list_keys(self, prefix: str, *, public: bool) -> Iterator[tuple[str, datetime]]:
        token = None
        while True:
            args = {"Bucket": self._bucket(public), "Prefix": prefix, **({"ContinuationToken": token} if token else {})}
            try:
                page = self.client.list_objects_v2(**args)
            except Exception:  # noqa: BLE001
                raise StorageError("画像の一覧の取得に失敗しました") from None
            for item in page.get("Contents", []):
                yield item["Key"], item["LastModified"]
            if not page.get("IsTruncated"):
                return
            token = page.get("NextContinuationToken")

    def public_url(self, key: str) -> str:
        return f"{self.public_base_url}/{check_key(key)}"


def make_storage() -> Storage:
    """環境変数から保存先を作る。s3 のときは、必要な設定が 1 つでも欠ければ失敗する（local に切り替えない）。"""
    if settings.storage_backend() == "local":
        return LocalStorage(settings.storage_local_dir(), settings.image_public_base_url())
    return S3Storage(
        endpoint_url=settings.required_env("STORAGE_S3_ENDPOINT_URL"),
        public_bucket=settings.required_env("STORAGE_S3_PUBLIC_BUCKET"),
        private_bucket=settings.required_env("STORAGE_S3_PRIVATE_BUCKET"),
        access_key_id=settings.required_env("STORAGE_S3_ACCESS_KEY_ID"),
        secret_access_key=settings.required_env("STORAGE_S3_SECRET_ACCESS_KEY"),
        public_base_url=settings.image_public_base_url(),
    )


@lru_cache(maxsize=1)
def get_storage() -> Storage:
    """プロセスで 1 つだけ作って使い回す（S3 のクライアントを毎回作らない）。環境変数を変えたテストは get_storage.cache_clear() する。"""
    return make_storage()
