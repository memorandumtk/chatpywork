import unittest
import asyncio
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from chatpywork import async_room
from chatpywork.types.response import SendMessageResponse, SendFileResponse, SendTaskResponse, ErrorResponse

# Load environment variables for Chatwork credentials
ROOMID = os.environ.get("CHATPYWORK_ROOMID")
APIKEY = os.environ.get("CHATPYWORK_APIKEY")
TOID = os.environ.get("CHATPYWORK_TOID")

# テスト関数ごとの待ち時間
NORMAL_INTERVAL_TIME = 1
FILE_OPERATION_INTERVAL_TIME = 3

class TestAsyncRoom(unittest.IsolatedAsyncioTestCase):
    """
    AsyncRoom クライアントのテスト(Chatwork API との連携)
    CHATPYWORK_ROOMID, CHATPYWORK_APIKEY, CHATPYWORK_TOID の環境変数が必要です。
    """

    def setUp(self):
        """
        各テストの前にテスト環境をセットアップします。
        必要な環境変数が設定されているか確認します。
        """
        print(f"\n--- テスト実行: {self._testMethodName} ---")
        print("ROOMID:", ROOMID)
        print("APIKEY:", APIKEY)
        print("TOID:", TOID)

        if not ROOMID or not APIKEY or not TOID:
            raise RuntimeError(
                "環境変数 CHATPYWORK_ROOMID, CHATPYWORK_APIKEY, CHATPYWORK_TOID を設定してください"
            )

    def get_timestamp(self) -> str:
        """
        一意なメッセージ用のタイムスタンプ文字列を返します。
        """
        test_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("現在のテスト時刻:", test_time)
        return test_time

    async def test_01_send_message(self):
        """
        通常のメッセージ送信のテスト。
        """
        timestamp = self.get_timestamp()
        message_content = f"テストメッセージ - {timestamp}"
        async with async_room.AsyncRoom(room_id=ROOMID, api_key=APIKEY) as room:
            resp = await room.send_message(message_content)
            print("send_message response:", resp)
            self.assertIsInstance(resp, SendMessageResponse, f"Expected SendMessageResponse, got {type(resp)}: {resp}")
            self.assertIsNotNone(resp.message_id, "Message ID should not be None")
            await asyncio.sleep(NORMAL_INTERVAL_TIME)


    async def test_02_send_message_with_mention(self):
        """
        特定ユーザーへのメンション付きメッセージ送信のテスト。
        """
        timestamp = self.get_timestamp()
        message_content = f"メンションテスト - {timestamp}"
        to_dict = {TOID: "テストユーザー"}
        async with async_room.AsyncRoom(room_id=ROOMID, api_key=APIKEY) as room:
            resp = await room.send_message(message_content, to=to_dict)
            print("send_message_with_mention response:", resp)
            self.assertIsInstance(resp, SendMessageResponse, f"Expected SendMessageResponse, got {type(resp)}: {resp}")
            self.assertIsNotNone(resp.message_id, "Message ID should not be None")
            await asyncio.sleep(NORMAL_INTERVAL_TIME)


    async def test_03_send_message_with_toall(self):
        """
        [toall] 付きメッセージ送信のテスト。
        """
        timestamp = self.get_timestamp()
        message_content = f"TOALLテスト - {timestamp}"
        async with async_room.AsyncRoom(room_id=ROOMID, api_key=APIKEY) as room:
            resp = await room.send_message(message_content, toall=True)
            print("send_message_with_toall response:", resp)
            self.assertIsInstance(resp, SendMessageResponse, f"Expected SendMessageResponse, got {type(resp)}: {resp}")
            self.assertIsNotNone(resp.message_id, "Message ID should not be None")
            await asyncio.sleep(NORMAL_INTERVAL_TIME)


    async def test_04_send_data(self):
        """
        バイナリデータをファイルとして送信するテスト。
        """
        timestamp = self.get_timestamp()
        data_content = f"testdata - {timestamp}".encode("utf-8")
        message_content = f"ファイル送信テスト - {timestamp}"
        async with async_room.AsyncRoom(room_id=ROOMID, api_key=APIKEY) as room:
            resp = await room.send_data(data_content, "test.txt", "text/plain", message=message_content)
            print("send_data response:", resp)
            self.assertIsInstance(resp, SendFileResponse, f"Expected SendFileResponse, got {type(resp)}: {resp}")
            self.assertIsNotNone(resp.file_id, "File ID should not be None")
            await asyncio.sleep(FILE_OPERATION_INTERVAL_TIME) # ファイル送信のテスト関数の待機時間は多めに設定


    async def test_05_send_data_exceeding_limit(self):
        """
        ファイルサイズ上限を超えるデータ送信のテスト。
        """
        timestamp = self.get_timestamp()
        # 5MBを少し超えるファイルを作成
        large_data = b'A' * (async_room.FILE_LIMIT + 100)
        message_content = f"容量オーバーテスト - {timestamp}"
        async with async_room.AsyncRoom(room_id=ROOMID, api_key=APIKEY) as room:
            resp = await room.send_data(large_data, "large_file.bin", "application/octet-stream", message=message_content)
            print("send_data_exceeding_limit response:", resp)
            # メッセージが送信されることを期待
            self.assertIsInstance(resp, SendMessageResponse, f"Expected SendMessageResponse, got {type(resp)}: {resp}")
            self.assertIsNotNone(resp.message_id, "Message ID should not be None")
            await asyncio.sleep(FILE_OPERATION_INTERVAL_TIME)


    async def test_06_send_binaryfile(self):
        """
        パスからバイナリファイルを送信するテスト。
        """
        timestamp = self.get_timestamp()
        file_content = f"binarydata - {timestamp}".encode("utf-8")
        message_content = f"バイナリ送信テスト - {timestamp}"

        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tmp_file:
            tmp_file.write(file_content)
            tmp_filepath = Path(tmp_file.name)

        print('filename:', tmp_filepath.name)
        print('message_content:', message_content)

        async with async_room.AsyncRoom(room_id=ROOMID, api_key=APIKEY) as room:
            resp = await room.send_binaryfile(str(tmp_filepath), "application/octet-stream", message=message_content)
            print("send_binaryfile response:", resp)
            self.assertIsInstance(resp, SendFileResponse, f"Expected SendFileResponse, got {type(resp)}: {resp}")
            self.assertIsNotNone(resp.file_id, "File ID should not be None")
            await asyncio.sleep(FILE_OPERATION_INTERVAL_TIME)

        os.remove(tmp_filepath) # 一時ファイルの削除


    async def test_07_send_binaryfile_not_found(self):
        """
        存在しないバイナリファイル送信のテスト。
        """
        timestamp = self.get_timestamp()
        non_existent_path = Path("non_existent_file_12345.bin")
        message_content = f"存在しないファイルテスト - {timestamp}"
        async with async_room.AsyncRoom(room_id=ROOMID, api_key=APIKEY) as room:
            resp = await room.send_binaryfile(str(non_existent_path), "application/octet-stream", message=message_content)
            print("send_binaryfile_not_found response:", resp)
            self.assertIsInstance(resp, SendMessageResponse, f"Expected SendMessageResponse, got {type(resp)}: {resp}")
            self.assertIsNotNone(resp.message_id, "Message ID should not be None")
            await asyncio.sleep(FILE_OPERATION_INTERVAL_TIME)


    async def test_08_send_textfile(self):
        """
        パスからテキストファイルを送信するテスト。
        """
        timestamp = self.get_timestamp()
        file_content = f"テキストファイルテスト - {timestamp}\nLine 2\nLine 3"
        message_content = f"テキスト送信テスト - {timestamp}"

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8") as tmp_file:
            tmp_file.write(file_content)
            tmp_filepath = Path(tmp_file.name)

        print('filename:', tmp_filepath.name)
        print('message_content:', message_content)

        async with async_room.AsyncRoom(room_id=ROOMID, api_key=APIKEY) as room:
            resp = await room.send_textfile(str(tmp_filepath), "text/plain", message=message_content)
            print("send_textfile response:", resp)
            self.assertIsInstance(resp, SendFileResponse, f"Expected SendFileResponse, got {type(resp)}: {resp}")
            self.assertIsNotNone(resp.file_id, "File ID should not be None")
            await asyncio.sleep(FILE_OPERATION_INTERVAL_TIME)

        os.remove(tmp_filepath) # 一時ファイルの削除


    async def test_09_send_csv(self):
        """
        CSVファイルを生成し送信するテスト。
        """
        timestamp = self.get_timestamp()
        csv_data = [["header1", "header2"], ["value1", "value2"], [f"test_time", timestamp]]
        message_content = f"CSV送信テスト - {timestamp}"
        file_name = f"test_csv_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"

        async with async_room.AsyncRoom(room_id=ROOMID, api_key=APIKEY) as room:
            resp = await room.send_csv(csv_data, file_name, message=message_content)
            print("send_csv response:", resp)
            self.assertIsInstance(resp, SendFileResponse, f"Expected SendFileResponse, got {type(resp)}: {resp}")
            self.assertIsNotNone(resp.file_id, "File ID should not be None")
            await asyncio.sleep(FILE_OPERATION_INTERVAL_TIME)


    async def test_10_send_task(self):
        """
        タスク送信のテスト。
        """
        timestamp = self.get_timestamp()
        task_content = f"タスクテスト - {timestamp}"
        # 1日後が期限のタスクを送信
        due_date = datetime.now() + timedelta(days=1)

        async with async_room.AsyncRoom(room_id=ROOMID, api_key=APIKEY) as room:
            resp = await room.send_task(task_content, [TOID], limit=due_date)
            print("send_task response:", resp)
            self.assertIsInstance(resp, SendTaskResponse, f"Expected SendTaskResponse, got {type(resp)}: {resp}")
            self.assertIsNotNone(resp.task_ids, "Task IDs list should not be None")
            self.assertGreater(len(resp.task_ids), 0, "Task IDs list should not be empty")
            self.assertIsNotNone(resp.message_id, "Message ID should not be None")
            await asyncio.sleep(NORMAL_INTERVAL_TIME)


    async def test_11_send_task_no_limit(self):
        """
        期限なしタスク送信のテスト。
        """
        timestamp = self.get_timestamp()
        task_content = f"タスクテスト (期限なし) - {timestamp}"
        async with async_room.AsyncRoom(room_id=ROOMID, api_key=APIKEY) as room:
            resp = await room.send_task(task_content, [TOID])
            print("send_task_no_limit response:", resp)
            self.assertIsInstance(resp, SendTaskResponse, f"Expected SendTaskResponse, got {type(resp)}: {resp}")
            self.assertIsNotNone(resp.task_ids, "Task IDs list should not be None")
            self.assertGreater(len(resp.task_ids), 0, "Task IDs list should not be empty")
            self.assertIsNotNone(resp.message_id, "Message ID should not be None")
            await asyncio.sleep(NORMAL_INTERVAL_TIME)


if __name__ == "__main__":
    # テスト実行方法:
    # 1. 'httpx' および 'chatpywork'（自作パッケージ）がインストールされていることを確認してください。
    # 2. 以下の環境変数を設定してください:
    #    CHATPYWORK_ROOMID = <ChatworkのルームID>
    #    CHATPYWORK_APIKEY = <ChatworkのAPIキー>
    #    CHATPYWORK_TOID = <タスク用のユーザーID>
    # 3. テストファイルを実行: python your_test_file.py
    unittest.main()
