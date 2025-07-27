from dataclasses import dataclass
from typing import List, Any # Keep Any if you have other complex types, but generally avoid

@dataclass(frozen=True, slots=True) # frozen=True makes instances immutable, good for response objects
class SendMessageResponse:
    message_id: str

@dataclass(frozen=True, slots=True)
class SendFileResponse:
    file_id: str

@dataclass(frozen=True, slots=True)
class SendTaskResponse:
    task_ids: List[str]
    message_id: str

@dataclass(frozen=True, slots=True)
class ErrorResponse:
    status_code: int
    error_message: str

__all__ = [
    "SendMessageResponse", "SendFileResponse", "SendTaskResponse", "ErrorResponse"
]
