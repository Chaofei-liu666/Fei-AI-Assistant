from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated, Literal

from langchain.messages import AIMessage, AnyMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel
from typing_extensions import TypedDict

from ...career_tools import APPLICATION_TOOLS, JOB_TOOLS, OPERATIONS_TOOLS, SCHEDULE_TOOLS
from ...contracts import ModuleArtifact, ModuleTask
from ...prompts import get_prompt
from ...skills import enabled_skills, get_skill_prompt
from ...run_events import record_safe
from ...structured import invoke_structured

Specialist = Literal[
    "job_intelligence_agent", "application_status_agent",
    "schedule_management_agent", "crawler_operations_agent", "interview_review_agent", "clarify",
]


class JobIntent(BaseModel):
    specialist: Specialist
    reason: str


class JobSearchState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    module_task: ModuleTask
    specialist: str
    artifacts: list[ModuleArtifact]


JOB_ROUTER_PROMPT = """你是 Fei 求职模块的 Supervisor。只选择一个 Specialist：
- job_intelligence_agent：2027 校招岗位、公司来源、JD、简历证据和能力缺口。
- application_status_agent：投递记录、事件时间线、官网进度和身份关联。
- schedule_management_agent：招聘日程、截止时间和待办。
- crawler_operations_agent：岗位抓取、任务状态、恢复和自动化。
- interview_review_agent：已确认面试文本的逐题复盘。
- clarify：求职意图明确，但材料不足以选择 Specialist。
普通公司知识不属于求职模块。不要创建不存在的 Agent 名称。"""

SPECIALISTS = {
    "job_intelligence_agent": {
        "title": "岗位情报", "kind": "career.job-evidence", "tools": JOB_TOOLS,
        "prompt": """你是 job_intelligence_agent，只处理已确认的 2027 届正式校招岗位。
先使用工具读取真实岗位和证据。匹配结果只能使用推荐关注、值得尝试、谨慎投入、不建议以及要求—证据表；禁止给出 0-100 分、成功率或虚构简历经历。""",
    },
    "application_status_agent": {
        "title": "投递时间线", "kind": "career.application-timeline", "tools": APPLICATION_TOOLS,
        "prompt": """你是 application_status_agent。使用工具读取投递事实和当前阶段。
不得声称已经修改阶段；官网证据和身份不确定时必须要求用户在工作区确认。官网复核不得把可信阶段降级。""",
    },
    "schedule_management_agent": {
        "title": "日程与待办", "kind": "career.schedule", "tools": SCHEDULE_TOOLS,
        "prompt": """你是 schedule_management_agent。读取招聘日程和待办，区分明确开始时间、仅截止时间和时间未知的事项。不得虚构日期。页面写入需要用户确认。""",
    },
    "crawler_operations_agent": {
        "title": "任务进度", "kind": "career.task-progress", "tools": OPERATIONS_TOOLS,
        "prompt": """你是 crawler_operations_agent。读取公司来源和持久任务状态，准确区分完成、部分完成、失败和等待人工操作。状态查询不能启动新任务；抓取和自动化由工作区显式触发。""",
    },
    "interview_review_agent": {
        "title": "面试复盘", "kind": "career.interview-review", "tools": [],
        "prompt": """你是 interview_review_agent。只有工作区中人工确认的转写文本才能生成正式复盘。
对当前对话中的面试材料，只能提供结构建议；不得补写候选人没有说过的回答，也不得声称已保存正式报告。""",
    },
}


def _run_id(state: JobSearchState) -> str | None:
    task = state.get("module_task")
    return getattr(task, "id", None) if task else None


def build_job_search_graph(model_provider: Callable[[], BaseChatModel]):
    all_tools = {tool.name: tool for spec in SPECIALISTS.values() for tool in spec["tools"]}

    async def route(state: JobSearchState) -> dict:
        skills = enabled_skills("job_search")
        if skills:
            lines = "\n".join(
                f"- {skill['skill_id']}：{skill['description'] or skill['title']}" for skill in skills
            )
            router_prompt = (
                "你是 Fei 求职域的 supervisor，只选择一个 skill：\n"
                f"{lines}\n"
                "- clarify：求职意图明确，但材料不足以选择 skill。\n"
                "不要创建不存在的 skill 名称。"
            )
        else:
            router_prompt = JOB_ROUTER_PROMPT
        decision = await invoke_structured(model_provider(), JobIntent,
            [SystemMessage(content=router_prompt), *state.get("messages", [])])
        run_id = _run_id(state)
        record_safe(run_id, "plan", actor="orchestrator", title="拆解求职任务", summary=decision.reason)
        title = SPECIALISTS.get(decision.specialist, {}).get("title", decision.specialist)
        record_safe(run_id, "delegate", actor="orchestrator", title=f"委托给 {title}",
                    detail={"specialist": decision.specialist})
        return {"specialist": decision.specialist}

    async def specialist(state: JobSearchState) -> dict:
        name = state["specialist"]
        spec = SPECIALISTS[name]
        model = model_provider().bind_tools(spec["tools"]) if spec["tools"] else model_provider()
        extra = get_prompt("job_search", "")
        base = get_skill_prompt("job_search", name, spec["prompt"])
        prompt = f"{extra}\n\n{base}" if extra else base
        response = await model.ainvoke([SystemMessage(content=prompt), *state.get("messages", [])])
        update: dict = {"messages": [response]}
        run_id = _run_id(state)
        tool_calls = getattr(response, "tool_calls", None)
        if tool_calls:
            record_safe(run_id, "tool", actor=name,
                        title=", ".join(str(call.get("name", "tool")) for call in tool_calls),
                        status="running", detail={"calls": [call.get("name") for call in tool_calls]})
        else:
            record_safe(run_id, "result", actor=name, title=spec["title"],
                        summary=str(response.content)[:500])
            update["artifacts"] = [ModuleArtifact(
                id=str(uuid.uuid4()), kind=spec["kind"], title=spec["title"],
                payload={"content": str(response.content), "specialist": name, "read_only": True},
            )]
        return update

    async def clarify(_: JobSearchState) -> dict:
        return {"messages": [AIMessage(content="请说明你要处理岗位、投递进度、招聘邮件、日程、抓取任务，还是已确认文本的面试复盘。")]}

    builder = StateGraph(JobSearchState)
    builder.add_node("router", route)
    builder.add_node("specialist", specialist)
    builder.add_node("tools", ToolNode(list(all_tools.values())))
    builder.add_node("clarify", clarify)
    builder.add_edge(START, "router")
    builder.add_conditional_edges("router", lambda state: "clarify" if state["specialist"] == "clarify" else "specialist",
                                  {"clarify": "clarify", "specialist": "specialist"})
    builder.add_conditional_edges("specialist",
        lambda state: "tools" if getattr(state["messages"][-1], "tool_calls", None) else "done",
        {"tools": "tools", "done": END})
    builder.add_edge("tools", "specialist")
    builder.add_edge("clarify", END)
    return builder.compile()
