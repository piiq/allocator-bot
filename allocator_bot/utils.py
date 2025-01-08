import json
import random
import re
import string
import time
from typing import AsyncGenerator, Callable, List

from fastapi import Header, HTTPException
from magentic import AsyncStreamedStr
from .models import LlmMessage


def validate_api_key(
    api_keys: List[str], api_key_header: str = Header(..., alias="Authorization")
) -> str:
    """Validate API key in header against pre-defined list of keys."""
    if not api_key_header:
        return False
    if api_key_header.replace("Bearer ", "").strip() in api_keys:
        return True
    return False


def require_api_key(api_keys: List[str]) -> Callable:
    """Decorator to add ACL based on API key header validation."""

    async def _require_api_key(header: str = Header(..., alias="Authorization")):
        if not validate_api_key(api_keys, header):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
        return header

    return _require_api_key


def sanitize_message(message: str) -> str:
    """Sanitize a message by escaping forbidden characters."""
    cleaned_message = re.sub(r"(?<!\{)\{(?!{)", "{{", message)
    cleaned_message = re.sub(r"(?<!\})\}(?!})", "}}", cleaned_message)
    return cleaned_message


def is_last_message(message: LlmMessage, messages: list[LlmMessage]) -> bool:
    """Check if the message is the last human message in the conversation."""
    human_messages = [msg for msg in messages if msg.role == "human"]
    return message == human_messages[-1] if human_messages else False


async def create_message_stream(
    content: AsyncStreamedStr | str,
) -> AsyncGenerator[dict, None]:
    if isinstance(content, str):
        yield {
            "event": "copilotMessageChunk",
            "data": json.dumps({"delta": content}),
        }
    else:
        async for chunk in content:
            yield {"event": "copilotMessageChunk", "data": json.dumps({"delta": chunk})}


def generate_id(length: int = 2) -> str:
    """Generate a unique ID with a total length of 4 characters."""
    timestamp = int(time.time() * 1000) % 1000

    base36_chars = string.digits + string.ascii_lowercase

    def to_base36(num):
        result = ""
        while num > 0:
            result = base36_chars[num % 36] + result
            num //= 36
        return result.zfill(2)

    random_suffix = "".join(random.choices(base36_chars, k=length))
    return to_base36(timestamp) + random_suffix
