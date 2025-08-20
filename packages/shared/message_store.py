from __future__ import annotations

import uuid
from collections import deque
from typing import Deque, Dict, List, Optional
import os
import json
import redis


class InMemoryMessageStore:
	"""Simple in-memory message store using deque with a fixed window.
    (Queuing services like Redis will be implemented later.)

	Each message: {"role": "user"|"assistant", "content": str}
	"""

	def __init__(self, max_window: int = 6) -> None:
		self._messages_by_chat_id: Dict[str, Deque[Dict[str, str]]] = {}
		self._max_window = max_window

	def new_chat_id(self) -> str:
		return str(uuid.uuid4())

	def get_recent(self, chat_id: str, *, window: int | None = None) -> List[Dict[str, str]]:
		messages = list(self._messages_by_chat_id.get(chat_id, deque(maxlen=self._max_window)))
		win = window or self._max_window
		return messages[-win:]

	def append(self, chat_id: str, role: str, content: str) -> None:
		q = self._messages_by_chat_id.get(chat_id)
		if q is None:
			q = deque(maxlen=self._max_window)
			self._messages_by_chat_id[chat_id] = q
		q.append({"role": role, "content": content})


store = InMemoryMessageStore(max_window=6)


class RedisMessageStore:
	"""Redis-backed message store. Uses a capped list per chat.

	Key: chat:{chat_id}:messages
	Stores newest first. On read, returns chronological order (oldest->newest).
	"""

	def __init__(self, redis_url: str, max_window: int = 6) -> None:
		self._r = redis.Redis.from_url(redis_url, decode_responses=True)
		self._max_window = max_window

	def new_chat_id(self) -> str:
		return str(uuid.uuid4())

	def _key(self, chat_id: str) -> str:
		return f"chat:{chat_id}:messages"

	def get_recent(self, chat_id: str, *, window: int | None = None) -> List[Dict[str, str]]:
		win = window or self._max_window
		items = self._r.lrange(self._key(chat_id), 0, win - 1)
		parsed = [json.loads(x) for x in items]
		# Stored newest-first; return oldest-first
		return list(reversed(parsed))

	def append(self, chat_id: str, role: str, content: str) -> None:
		item = json.dumps({"role": role, "content": content})
		pipe = self._r.pipeline()
		pipe.lpush(self._key(chat_id), item)
		pipe.ltrim(self._key(chat_id), 0, self._max_window - 1)
		pipe.execute()


def _select_store() -> object:
	redis_url = os.getenv("REDIS_URL")
	if redis_url:
		try:
			return RedisMessageStore(redis_url=redis_url, max_window=6)
		except Exception:
			# Fallback to in-memory if Redis is not reachable
			return InMemoryMessageStore(max_window=6)
	return InMemoryMessageStore(max_window=6)


store = _select_store()

message_store = store

__all__ = ["store", "message_store", "InMemoryMessageStore", "RedisMessageStore"]


