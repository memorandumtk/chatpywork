from __future__ import annotations

import calendar
import csv
import io
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, TypeVar, Union

import httpx

from .types.common import (
    ApiKey,
    CsvArray,
    FilePath,
    Limit,
    Message,
    MimeType,
    RoomId,
    Task,
    ToDict,
    ToIds,
)
from .types.response import ErrorResponse, SendFileResponse, SendMessageResponse, SendTaskResponse

BASE_URL = "https://api.chatwork.com/v2"
FILE_LIMIT = 5 * 1024 * 1024  # 5 MiB

# ---------------------------------------------------------------------------
# Typing helpers
# ---------------------------------------------------------------------------
T = TypeVar("T")
JsonDict = dict[str, Any]
Result = Union[T, ErrorResponse]

MsgResult = Result[SendMessageResponse]
FileResult = Result[SendFileResponse]
TaskResult = Result[SendTaskResponse]


@dataclass(frozen=True, slots=True)
class ChatworkConfig:
    room_id: RoomId
    api_key: ApiKey
    base_url: str = BASE_URL
    file_limit: int = FILE_LIMIT



# Chatwork API のエラー用カスタム例外
class ChatworkAPIError(Exception):
    """Chatwork API のエラー例外クラス"""

    def __init__(self, status_code: int, message: str, response_text: str = ""):
        super().__init__(f"Chatwork API Error {status_code}: {message}. Response: {response_text}")
        self.status_code = status_code
        self.message = message
        self.response_text = response_text


class AsyncRoom:
    """
    非同期で Chatwork のチャットルームに投稿するためのクライアント。

    非同期コンテキストマネージャとして利用することで、内部の `httpx.AsyncClient` のライフサイクルを自動管理します。
    """

    def __init__(
        self,
        room_id: RoomId,
        api_key: ApiKey,
        *,
        client: Optional[httpx.AsyncClient] = None,
        base_url: str = BASE_URL,
        file_limit: int = FILE_LIMIT,
    ) -> None:
        self._cfg = ChatworkConfig(room_id, api_key, base_url, file_limit)
        self._external_client = client
        self._internal_client: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------
    # コンテキストマネージャ用ヘルパー
    # ------------------------------------------------------------------
    async def __aenter__(self) -> AsyncRoom:
        if self._external_client is None:
            self._internal_client = httpx.AsyncClient()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """
        コンテキストを抜ける際に内部管理のクライアントをクローズします。
        """
        if self._internal_client is not None:
            await self._internal_client.aclose()
            self._internal_client = None

    # ------------------------------------------------------------------
    # パブリック API
    # ------------------------------------------------------------------
    async def send_message(self, message: Message, *, to: Optional[ToDict] = None, toall: bool = False) -> MsgResult:
        """
        チャットワークルームにテキストメッセージを送信します。
        """
        body = self._prepend_mentions(message, to, toall)
        return await self._post(
            f"/rooms/{self._cfg.room_id}/messages",
            data={"body": body},
            success=lambda j: SendMessageResponse(message_id=j.get("message_id")),
        )

    async def send_data(
        self,
        data: bytes,
        filename: str,
        mimetype: MimeType,
        *,
        message: Message = "",
        to: Optional[ToDict] = None,
        toall: bool = False,
    ) -> FileResult | MsgResult:
        """
        バイナリデータをファイルとしてチャットワークルームに送信します。
        """
        if len(data) > self._cfg.file_limit:
            return await self.send_message("容量オーバー:アップロードするデータが大きすぎます", to=to, toall=toall)

        body = self._prepend_mentions(message, to, toall)
        files = {
            "file": (filename, data, mimetype),
            "message": (None, body),
        }
        return await self._post(
            f"/rooms/{self._cfg.room_id}/files",
            files=files,
            success=lambda j: SendFileResponse(file_id=j.get("file_id")),
            size_error_message="容量オーバー:アップロードするデータが大きすぎました",
        )

    async def send_binaryfile(
        self,
        filepath: FilePath,
        mimetype: MimeType,
        *,
        message: Message = "",
        to: Optional[ToDict] = None,
        toall: bool = False,
    ) -> FileResult | MsgResult:
        """
        指定したパスのバイナリファイルを送信します。
        """
        path = Path(filepath)
        if not path.is_file():
            return await self.send_message(f"エラー: ファイルが見つかりません - {filepath}", to=to, toall=toall)

        try:
            data = path.read_bytes()
        except OSError as e:
            return await self.send_message(f"ファイル読み込みエラー: {filepath} - {e}", to=to, toall=toall)

        return await self.send_data(data, path.name, mimetype, message=message, to=to, toall=toall)

    async def send_textfile(
        self,
        filepath: FilePath,
        mimetype: MimeType,
        *,
        from_encoding: str = "utf-8",
        to_encoding: str = "utf-8",
        from_linesep: Optional[str] = None,
        to_linesep: Optional[str] = None,
        message: Message = "",
        to: Optional[ToDict] = None,
        toall: bool = False,
    ) -> FileResult | MsgResult:
        """
        テキストファイルをパスから送信します。エンコーディングや改行コードの変換も可能です。
        """
        path = Path(filepath)
        if not path.is_file():
            return await self.send_message(f"エラー: ファイルが見つかりません - {filepath}", to=to, toall=toall)

        from_linesep = from_linesep or os.linesep
        to_linesep = to_linesep or os.linesep

        try:
            text = path.read_text(encoding=from_encoding)
            if to_linesep != from_linesep:
                text = text.replace(from_linesep, to_linesep)
            data = text.encode(to_encoding)
        except (OSError, UnicodeDecodeError) as e:
            return await self.send_message(f"ファイル読み込み・変換エラー: {filepath} - {e}", to=to, toall=toall)

        return await self.send_data(data, path.name, mimetype, message=message, to=to, toall=toall)

    async def send_csv(
        self,
        csv_array: CsvArray,
        filename: str,
        *,
        delimiter: str = ",",
        quotechar: str = '"',
        linesep: str = "\n",
        quoting: int = csv.QUOTE_MINIMAL,
        encode: str = "utf-8",
        message: Message = "",
        to: Optional[ToDict] = None,
        toall: bool = False,
    ) -> FileResult | MsgResult:
        """
        二重配列からCSVファイルを生成し、送信します。
        """
        with io.StringIO() as f:
            writer = csv.writer(f, delimiter=delimiter, quotechar=quotechar, lineterminator=linesep, quoting=quoting)
            writer.writerows(csv_array)
            data = f.getvalue().encode(encode)
        return await self.send_data(data, filename, "text/csv", message=message, to=to, toall=toall)


    async def send_task(self, task: Task, to_ids: ToIds, limit: Optional[Limit] = None) -> TaskResult:
        """
        チャットワークルームにタスクを送信します。
        """
        params: dict[str, Any] = {"body": task, "to_ids": ",".join(to_ids)}
        if limit is not None:
            params["limit"] = _to_unix(limit)

        return await self._post(
            f"/rooms/{self._cfg.room_id}/tasks",
            data=params,
            success=lambda j: SendTaskResponse(
                task_ids=j.get("task_ids", []),
                message_id=j.get("message_id", ""),
            ),
        )

    # ------------------------------------------------------------------
    # 内部ヘルパー
    # ------------------------------------------------------------------
    @property
    def _client(self) -> httpx.AsyncClient:
        """
        有効な httpx.AsyncClient インスタンスを返します。
        """
        client = self._external_client or self._internal_client
        if client is None:
            raise RuntimeError("AsyncRoom は async コンテキストマネージャまたは外部 httpx.AsyncClient とともに使う必要があります。")
        return client

    def _headers(self) -> dict[str, str]:
        return {"X-ChatWorkToken": self._cfg.api_key}

    def _prepend_mentions(self, message: Message, to: Optional[ToDict], toall: bool) -> str:
        # 宛先指定をメッセージに付加
        return f"{_build_mentions(to or {}, toall)}{message}" if (to or toall) else message

    async def _post(
        self,
        path: str,
        *,
        data: Optional[Mapping[str, Any]] = None,
        files: Optional[Mapping[str, tuple[Any, ...]]] = None,
        success: Callable[[JsonDict], T],
        size_error_message: Optional[str] = None,
    ) -> Result[T] | MsgResult:
        """
        Chatwork API への全ての POST リクエストを処理します。
        """
        url = f"{self._cfg.base_url}{path}"
        try:
            resp = await self._client.post(url, headers=self._headers(), data=data, files=files)
            resp.raise_for_status()
            return success(resp.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 413 and size_error_message:
                return await self.send_message(size_error_message)
            return ErrorResponse(status_code=e.response.status_code, error_message=e.response.text)
        except httpx.HTTPError as e:
            return ErrorResponse(status_code=0, error_message=str(e))

    def _http_error_message(self, exc: httpx.HTTPError, url: str) -> str:
        # HTTPエラー内容を日本語で返す
        if isinstance(exc, httpx.ConnectError):
            return f"接続エラー: {url} からデータの取得中に接続エラーが発生しました。"
        if isinstance(exc, httpx.TimeoutException):
            return f"タイムアウト: {url} からデータの取得中にタイムアウトが発生しました。"
        if isinstance(exc, httpx.TooManyRedirects):
            return f"リダイレクト超過: {url} からデータの取得中にリダイレクトが最大数を超過しました。"
        if isinstance(exc, httpx.HTTPStatusError):
            code = exc.response.status_code
            if code == 400:
                return f"400 Bad Request: {url} へ不正なリクエストが行われました。"
            if code == 401:
                return f"401 Unauthorized: {url}へのリクエストは必要な認証が行われませんでした。"
            if code == 403:
                return f"403 Forbidden: {url} へのリクエストは禁止されています。"
            if code == 404:
                return f"404 Not Found: {url} が見つかりませんでした。"
            return f"{code}: {url} へのリクエストがOKではないステータスを返しました。"
        return f"予期せぬエラー: {url} からのデータ取得中にエラーが発生しました - {exc}"


def _build_mentions(to: ToDict, toall: bool) -> str:
    # 宛先指定文字列を生成
    parts: list[str] = []
    if toall:
        parts.append("[toall]\n")
    for chatwork_id, name in to.items():
        parts.append(f"[To:{chatwork_id}] {name}さん\n")
    return "".join(parts)


def _to_unix(dt: datetime) -> int:
    """
    datetime から UTC のUNIXエポック秒を返す(naiveはUTCとみなす)
    """
    if dt.tzinfo is None:
        return calendar.timegm(dt.utctimetuple())
    return int(dt.timestamp())