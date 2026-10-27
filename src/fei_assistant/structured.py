from __future__ import annotations

from typing import Any

from pydantic import BaseModel


async def invoke_structured(model: Any, schema: type[BaseModel], prompt: Any, attempts: int = 2):
    """Invoke JSON-schema output with one bounded retry for provider glitches."""
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return await model.with_structured_output(schema).ainvoke(prompt)
        except Exception as exc:
            last_error = exc
    assert last_error is not None
    raise last_error
