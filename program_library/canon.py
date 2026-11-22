"""规范 JSON。只做编码，不改字符串内容。"""

from __future__ import annotations

import hashlib
import json


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def dev_sort_key(task_id: str) -> tuple[str, str]:
    return sha256_text(f"cml-prose-v0.1|dev|{task_id}"), task_id


def row_sort_key(task_id: str, inputs: list[str], first_index: int) -> tuple[str, str, int]:
    return (
        sha256_text(f"cml-prose-v0.1|row|{task_id}|{canonical_json(inputs)}"),
        canonical_json(inputs),
        first_index,
    )
