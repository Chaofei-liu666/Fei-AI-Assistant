from __future__ import annotations

import json
import re
from typing import Any

from langchain.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

_JSON_HINT = SystemMessage(content=(
    "Return exactly one JSON object that matches the requested schema. "
    "Use the JSON format. No prose, no markdown fences."
))
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def _with_hint(prompt: Any) -> list:
    if isinstance(prompt, str):
        return [_JSON_HINT, HumanMessage(content=prompt)]
    return [*prompt, _JSON_HINT]


def _extract_json(text: str) -> str:
    fenced = _FENCE.search(text)
    if fenced:
        return fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end + 1]
    return text.strip()


async def invoke_structured(model: Any, schema: type[BaseModel], prompt: Any, attempts: int = 2):
    """Ask for structured output, degrading gracefully when the provider lacks a mode.

    Some OpenAI-compatible providers reject `response_format: json_schema` or the
    tool_choice used by function calling. We try the strict path first, then json_mode,
    then a plain completion parsed as JSON — so one provider quirk cannot break a run.
    """
    last_error: Exception | None = None

    for _ in range(attempts):
        try:
            return await model.with_structured_output(schema).ainvoke(prompt)
        except Exception as exc:
            last_error = exc

    try:
        result = await model.with_structured_output(schema, method="json_mode").ainvoke(_with_hint(prompt))
        return result if isinstance(result, schema) else schema.model_validate(result)
    except Exception as exc:
        last_error = exc

    try:
        response = await model.ainvoke(_with_hint(prompt))
        payload = json.loads(_extract_json(str(response.content)))
        return schema.model_validate(payload)
    except Exception as exc:
        last_error = exc

    assert last_error is not None
    raise last_error
