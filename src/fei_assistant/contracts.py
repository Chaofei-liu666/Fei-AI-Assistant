from typing import Any, Literal

from pydantic import BaseModel, Field


Route = Literal["general", "job_search", "clarify"]


class ModuleMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ModuleArtifact(BaseModel):
    id: str
    kind: str
    title: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ModuleTask(BaseModel):
    id: str
    module: str
    messages: list[ModuleMessage]
    resource_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModuleResult(BaseModel):
    task_id: str
    messages: list[ModuleMessage]
    artifacts: list[ModuleArtifact] = Field(default_factory=list)

