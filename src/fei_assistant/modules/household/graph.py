from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated

from langchain.messages import AnyMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from ...contracts import ModuleArtifact, ModuleTask
from ...prompts import get_prompt
from ...run_events import record_safe
from ...household_tools import HOUSEHOLD_TOOLS


class HouseholdState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    module_task: ModuleTask
    artifacts: list[ModuleArtifact]


HOUSEHOLD_PROMPT = """你是 Fei 的物品 Agent，负责记录和查询家里物品的位置与数量。
规则：
1. 写入只能通过工具完成，不要凭空编造物品或位置。
2. 用户说「洗衣液放衣柜第二层」时，调用 add_household_item，位置写成 衣柜/第二层 或保留原话。
3. 同名物品有多件、或位置缺房间时，先用一句话问清楚，不要猜。
4. 查询时用 query_household_items 或 list_household_location，并回报位置路径和剩余数量。
5. 你只管理物品，不处理求职、邮件或日程。"""


def build_household_graph(model_provider: Callable[[], BaseChatModel]):
    async def agent(state: HouseholdState) -> dict:
        model = model_provider().bind_tools(HOUSEHOLD_TOOLS)
        response = await model.ainvoke([SystemMessage(content=get_prompt("household", HOUSEHOLD_PROMPT)), *state.get("messages", [])])
        update: dict = {"messages": [response]}
        run_id = getattr(state.get("module_task"), "id", None)
        tool_calls = getattr(response, "tool_calls", None)
        if tool_calls:
            record_safe(run_id, "tool", actor="household",
                        title=", ".join(str(call.get("name", "tool")) for call in tool_calls),
                        status="running")
        else:
            record_safe(run_id, "result", actor="household", title="物品记录",
                        summary=str(response.content)[:300])
            update["artifacts"] = [ModuleArtifact(
                id=str(uuid.uuid4()),
                kind="household.item-answer",
                title="物品记录",
                payload={"content": str(response.content), "specialist": "household"},
            )]
        return update

    builder = StateGraph(HouseholdState)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(HOUSEHOLD_TOOLS))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges(
        "agent",
        lambda state: "tools" if getattr(state["messages"][-1], "tool_calls", None) else "done",
        {"tools": "tools", "done": END},
    )
    builder.add_edge("tools", "agent")
    return builder.compile()
