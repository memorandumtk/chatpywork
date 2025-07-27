from typing import Dict, Any, List, Optional, Union
import datetime

RoomId = str
ApiKey = str
Message = str
AccountId = str
AccountName = str
ToDict = Dict[AccountId, AccountName]
FilePath = str
MimeType = str
CsvArray = List[List[str]]
Task = str
ToIds = List[str]
Limit = Optional[datetime.datetime]
ResponseType = Any

__all__ = [
    "RoomId", "ApiKey", "Message", "AccountId", "AccountName", "ToDict", "FilePath", "MimeType", "CsvArray", "Task", "ToIds", "Limit", "ResponseType"
]
