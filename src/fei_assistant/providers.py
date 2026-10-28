from __future__ import annotations

import httpx
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ProviderConfig
from .secrets import SecretStore
from .structured import invoke_structured


DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def get_provider_config(db: Session, slot: str) -> ProviderConfig:
    config = db.scalar(select(ProviderConfig).where(ProviderConfig.kind == slot))
    if not config or not config.configured:
        raise RuntimeError(f"{slot} provider is not configured")
    return config


def build_text_model(db: Session, secrets: SecretStore | None = None):
    config = get_provider_config(db, "text")
    provider = config.config.get("provider", "deepseek")
    api_key = (secrets or SecretStore()).get(config.secret_ref)
    if not api_key:
        raise RuntimeError("text provider secret is unavailable")
    base_url = config.base_url or (DEEPSEEK_BASE_URL if provider == "deepseek" else None)
    if not base_url or not config.model:
        raise RuntimeError("text provider base URL and model are required")
    return ChatOpenAI(
        model=config.model,
        api_key=api_key,
        base_url=base_url,
        temperature=0,
        streaming=True,
    )


async def test_text_provider(config: ProviderConfigInputLike, secret: str) -> dict:
    provider = config.provider
    base_url = config.base_url or (DEEPSEEK_BASE_URL if provider == "deepseek" else None)
    if not base_url or not config.model:
        raise ValueError("base_url and model are required")
    model = ChatOpenAI(model=config.model, api_key=secret, base_url=base_url, temperature=0)
    chunks = [chunk async for chunk in model.astream("Reply with exactly: ok")]

    @tool
    def capability_probe(value: str) -> str:
        """Return the supplied value for capability testing."""
        return value

    tool_message = await model.bind_tools([capability_probe]).ainvoke(
        "Call capability_probe with value='ok'."
    )
    structured = await invoke_structured(model, _CapabilityProbe,
        "Return supported=true and message='ok'."
    )
    vision = False
    try:
        vision_message = await model.ainvoke([HumanMessage(content=[
            {"type": "text", "text": "Reply with exactly: ok"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="}},
        ])])
        vision = bool(getattr(vision_message, "content", None))
    except Exception:
        # Vision is optional. A provider can still pass the required text capabilities.
        vision = False
    return {
        "streaming": bool(chunks),
        "tool_calling": bool(getattr(tool_message, "tool_calls", [])),
        "json_schema": structured.supported,
        "vision": vision,
    }


class ProviderConfigInputLike:
    provider: str
    base_url: str | None
    model: str | None


from pydantic import BaseModel  # noqa: E402


class _CapabilityProbe(BaseModel):
    supported: bool
    message: str


async def test_dashscope_key(api_key: str) -> bool:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            "https://dashscope.aliyuncs.com/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
    return response.status_code == 200
