from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSpec:
    """A product-facing agent: its own data domain, prompt, tools and page."""

    id: str
    title: str
    description: str
    page: str
    tool_names: tuple[str, ...]
    prompt: str
    # "workspace" means the agent owns a data view and earns a nav entry.
    # "inline" means it only runs inside the conversation (coding, research...).
    surface: str = "inline"
    target: str | None = None
    assistant_id: str | None = None


AGENTS: dict[str, AgentSpec] = {
    "job_search": AgentSpec(
        id="job_search",
        title="求职 Agent",
        description="岗位情报、公开页抓取、投递记录、日程截止与面试复盘",
        page="/job",
        surface="workspace",
        target="job/overview",
        tool_names=(
            "search_2027_campus_jobs",
            "get_job_evidence",
            "list_applications",
            "list_schedule",
        ),
        prompt="你是 Fei 的求职 Agent，只处理 2027 届校招相关的事实查询、证据分析与记录整理。",
        assistant_id="fei-job-search",
    ),
    "household": AgentSpec(
        id="household",
        title="物品 Agent",
        description="用一句话记录家里物品的位置与数量，并按位置或名称查询",
        page="/items",
        surface="workspace",
        target="items",
        tool_names=(
            "add_household_item",
            "move_household_item",
            "consume_household_item",
            "query_household_items",
            "list_household_location",
            "low_stock_household_items",
        ),
        prompt=(
            "你是 Fei 的物品 Agent。用户会用一句话描述物品放在哪里、还剩多少。"
            "你只负责抽取结构化字段并调用工具；位置不确定、同名物品多件时必须先问清楚，"
            "不要猜测房间或层数。"
        ),
    ),
}


def get_agent(agent_id: str) -> AgentSpec | None:
    return AGENTS.get(agent_id)


def list_agents() -> list[dict]:
    return [
        {
            "id": spec.id,
            "title": spec.title,
            "description": spec.description,
            "page": spec.page,
            "surface": spec.surface,
            "target": spec.target,
            "tools": list(spec.tool_names),
        }
        for spec in AGENTS.values()
    ]
