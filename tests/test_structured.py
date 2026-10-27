import pytest

from fei_assistant.schemas import RouteDecision
from fei_assistant.structured import invoke_structured


class _Runnable:
    def __init__(self): self.calls = 0
    async def ainvoke(self, _):
        self.calls += 1
        if self.calls == 1: raise ValueError("invalid JSON")
        return RouteDecision(route="general", reason="ok")


class _Model:
    def __init__(self): self.runnable = _Runnable()
    def with_structured_output(self, _): return self.runnable


@pytest.mark.asyncio
async def test_structured_output_retries_once() -> None:
    model = _Model()
    result = await invoke_structured(model, RouteDecision, "hello")
    assert result.route == "general"
    assert model.runnable.calls == 2
