from pathlib import Path

from langchain.agents import create_agent
from langchain.messages import SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from .contracts import Route
from .routing import classify_route, latest_user_text
from .state import FeiState
from .subagents import build_subagent_tools
from .tools import build_tools


DIRECT_SYSTEM_PROMPT = (
    "You are Fei智能助手. Answer simple requests directly, clearly, and concisely."
)

SUPERVISOR_SYSTEM_PROMPT = """
You are Fei智能助手 and act as the main agent in a subagents architecture.

Use specialized subagents when the task benefits from research, code inspection,
or data analysis. You may call more than one subagent when their work is independent.
Combine their results into one answer for the user. Do not claim that a subagent
modified files or used capabilities that are not available in this MVP.
""".strip()


def build_graph(
    model: BaseChatModel,
    workspace: Path,
    checkpointer: InMemorySaver | None = None,
):
    workspace_tools = build_tools(workspace)
    subagent_tools = build_subagent_tools(model, workspace_tools)
    supervisor = create_agent(
        model=model,
        tools=subagent_tools,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
    )

    async def router(state: FeiState) -> dict[str, Route]:
        text = latest_user_text(state["messages"])
        return {"route": classify_route(text)}

    async def direct_response(state: FeiState) -> dict:
        response = await model.ainvoke(
            [SystemMessage(content=DIRECT_SYSTEM_PROMPT), *state["messages"]]
        )
        return {"messages": [response]}

    async def run_supervisor(state: FeiState) -> dict:
        result = await supervisor.ainvoke({"messages": state["messages"]})
        return {"messages": [result["messages"][-1]]}

    def select_route(state: FeiState) -> Route:
        return state["route"]

    builder = StateGraph(FeiState)
    builder.add_node("router", router)
    builder.add_node("direct", direct_response)
    builder.add_node("supervisor", run_supervisor)

    builder.add_edge(START, "router")
    builder.add_conditional_edges(
        "router",
        select_route,
        {
            "direct": "direct",
            "supervisor": "supervisor",
        },
    )
    builder.add_edge("direct", END)
    builder.add_edge("supervisor", END)

    return builder.compile(checkpointer=checkpointer or InMemorySaver())

