from __future__ import annotations

import uuid
from collections.abc import Callable

from langchain.messages import AIMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from .contracts import ModuleMessage, ModuleTask, Route
from .modules.household import build_household_graph
from .modules.job_search import build_job_search_graph
from .routing import classify_route, latest_user_text, route_for_explicit_module
from .schemas import RouteDecision
from .state import FeiState
from .structured import invoke_structured


DIRECT_SYSTEM_PROMPT = """你是 Fei 智能助手。直接处理通用对话与简单任务。求职只是一个独立模块；不要把普通的公司知识、分析、优化或比较问题误判为求职。"""
ROUTER_SYSTEM_PROMPT = """你是 Fei 的结构化路由器，只输出：
- general：普通问答、写作、分析、公司知识以及其他非求职任务。
- job_search：明确涉及岗位 JD、简历证据匹配、求职投递、招聘邮件、面试记录或 Offer。
- household：记录或查询家里物品的位置与数量，例如「洗衣液放衣柜第二层」「洗衣液在哪」。
- clarify：用户显然要办事但信息不足，无法在以上模块间可靠区分。
普通出现“分析”“公司”“比较”等词不能单独构成 job_search。
"""


def build_graph(model_provider: Callable[[], BaseChatModel], checkpointer=None):
    job_graph = build_job_search_graph(model_provider)
    household_graph = build_household_graph(model_provider)

    async def router(state: FeiState) -> dict:
        explicit = route_for_explicit_module(state.get("requested_module"))
        if explicit:
            return {"route": explicit, "active_module": explicit}
        try:
            decision = await invoke_structured(model_provider(), RouteDecision,
                [SystemMessage(content=ROUTER_SYSTEM_PROMPT), *state["messages"]]
            )
            route: Route = decision.route
        except Exception:
            route = classify_route(latest_user_text(state["messages"]))
        return {"route": route, "active_module": route}

    async def direct_response(state: FeiState) -> dict:
        response = await model_provider().ainvoke([SystemMessage(content=DIRECT_SYSTEM_PROMPT), *state["messages"]])
        return {"messages": [response]}

    async def clarify(_: FeiState) -> dict:
        return {"messages": [AIMessage(content="你希望我按通用任务处理，还是进入求职模块处理岗位、投递、招聘邮件或面试记录？")]}

    async def run_job_module(state: FeiState) -> dict:
        text = latest_user_text(state["messages"])
        task = ModuleTask(
            id=str(uuid.uuid4()),
            module="job_search",
            messages=[ModuleMessage(role="user", content=text)],
        )
        result = await job_graph.ainvoke({"messages": state["messages"], "module_task": task})
        return {
            "messages": [result["messages"][-1]],
            "module_task": task,
            "artifacts": result.get("artifacts", []),
            "active_module": "job_search",
        }

    async def run_household_module(state: FeiState) -> dict:
        text = latest_user_text(state["messages"])
        task = ModuleTask(
            id=str(uuid.uuid4()),
            module="household",
            messages=[ModuleMessage(role="user", content=text)],
        )
        result = await household_graph.ainvoke({"messages": state["messages"], "module_task": task})
        return {
            "messages": [result["messages"][-1]],
            "module_task": task,
            "artifacts": result.get("artifacts", []),
            "active_module": "household",
        }

    builder = StateGraph(FeiState)
    builder.add_node("router", router)
    builder.add_node("general", direct_response)
    builder.add_node("job_search", run_job_module)
    builder.add_node("household", run_household_module)
    builder.add_node("clarify", clarify)
    builder.add_edge(START, "router")
    builder.add_conditional_edges(
        "router", lambda state: state["route"],
        {"general": "general", "job_search": "job_search", "household": "household", "clarify": "clarify"},
    )
    builder.add_edge("general", END)
    builder.add_edge("job_search", END)
    builder.add_edge("household", END)
    builder.add_edge("clarify", END)
    return builder.compile(checkpointer=checkpointer)
