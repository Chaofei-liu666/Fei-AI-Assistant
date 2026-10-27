from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated, Literal

from langchain.messages import AIMessage, AnyMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from typing_extensions import TypedDict

from ...contracts import ModuleArtifact, ModuleTask
from ...structured import invoke_structured


class JobIntent(BaseModel):
    specialist: Literal["job_analysis_agent", "mail_analysis_agent", "interview_review_agent", "clarify"]
    reason: str


class JobSearchState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    module_task: ModuleTask
    specialist: str
    artifacts: list[ModuleArtifact]


JOB_ROUTER_PROMPT = """你是 Fei 求职模块的任务分发器，只选择一个节点：
- job_analysis_agent：岗位要求、简历证据、能力缺口、投递准备。
- mail_analysis_agent：面试邀请、测评、拒信、Offer 或招聘沟通的理解和建议；只能建议，不能更改状态。
- interview_review_agent：面试记录、回答拆分、优缺点和练习建议。
- clarify：材料不足，无法判断属于哪个任务。
不要把普通公司知识或一般分析问题视为求职任务。
"""

SPECIALIST_PROMPTS = {
    "job_analysis_agent": """你是 job_analysis_agent。比较岗位要求与用户提供的简历证据，输出要求—证据表、缺口、风险和行动建议。匹配只用高/中/低，不给伪精确分数，不得虚构经历。正式持久化分析由岗位工作区执行。""",
    "mail_analysis_agent": """你是 mail_analysis_agent。识别面试邀请、测评、拒信、Offer、招聘沟通，说明可能关联的岗位、邮件类型、建议状态和信心依据。你只能生成建议，绝不声称已修改投递状态或邮箱。""",
    "interview_review_agent": """你是 interview_review_agent。把已确认的面试文本拆分为问题与回答，逐项给出优点、证据不足、结构问题、改进建议和练习题。不得替用户编造回答。正式复盘必须先在工作区确认转写。""",
}


def build_job_search_graph(model_provider: Callable[[], BaseChatModel]):
    async def route(state: JobSearchState) -> dict:
        decision = await invoke_structured(model_provider(), JobIntent,
            [SystemMessage(content=JOB_ROUTER_PROMPT), *state.get("messages", [])]
        )
        return {"specialist": decision.specialist}

    def specialist_node(name: str):
        async def run(state: JobSearchState) -> dict:
            response = await model_provider().ainvoke(
                [SystemMessage(content=SPECIALIST_PROMPTS[name]), *state.get("messages", [])]
            )
            artifact = ModuleArtifact(
                id=str(uuid.uuid4()),
                kind=name.removesuffix("_agent"),
                title={"job_analysis_agent": "岗位分析", "mail_analysis_agent": "邮件建议", "interview_review_agent": "面试复盘"}[name],
                payload={"content": str(response.content), "specialist": name},
            )
            return {"messages": [response], "artifacts": [artifact]}
        return run

    async def clarify(_: JobSearchState) -> dict:
        return {"messages": [AIMessage(content="请补充你希望处理的是岗位/简历匹配、招聘邮件，还是已确认文本的面试复盘。")]}

    builder = StateGraph(JobSearchState)
    builder.add_node("router", route)
    for name in SPECIALIST_PROMPTS:
        builder.add_node(name, specialist_node(name))
        builder.add_edge(name, END)
    builder.add_node("clarify", clarify)
    builder.add_edge("clarify", END)
    builder.add_edge(START, "router")
    builder.add_conditional_edges("router", lambda state: state["specialist"], {**{name: name for name in SPECIALIST_PROMPTS}, "clarify": "clarify"})
    return builder.compile()
