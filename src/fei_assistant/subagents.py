from collections.abc import Sequence

from langchain.agents import create_agent
from langchain.messages import BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool, tool


def _message_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return str(content)


def build_subagent_tools(
    model: BaseChatModel,
    workspace_tools: Sequence[BaseTool],
) -> list[BaseTool]:
    research_agent = create_agent(
        model=model,
        tools=list(workspace_tools[:2]),
        system_prompt=(
            "You are a research subagent. Analyze the task and any relevant workspace "
            "files. Return concise findings, supporting details, and limitations."
        ),
    )

    coding_agent = create_agent(
        model=model,
        tools=list(workspace_tools[:2]),
        system_prompt=(
            "You are a coding subagent. Inspect relevant workspace files, explain the "
            "implementation or defect, and return a concrete recommendation. This MVP "
            "is read-only, so do not claim that files were modified."
        ),
    )

    data_analysis_agent = create_agent(
        model=model,
        tools=list(workspace_tools),
        system_prompt=(
            "You are a data analysis subagent. Use the calculator and workspace files "
            "when useful. Return the calculation, assumptions, and conclusion."
        ),
    )

    @tool("research_agent", description="Delegate research and document analysis to a research subagent.")
    async def call_research_agent(task: str) -> str:
        result = await research_agent.ainvoke(
            {"messages": [{"role": "user", "content": task}]}
        )
        return _message_text(result["messages"][-1])

    @tool("coding_agent", description="Delegate code inspection and programming analysis to a coding subagent.")
    async def call_coding_agent(task: str) -> str:
        result = await coding_agent.ainvoke(
            {"messages": [{"role": "user", "content": task}]}
        )
        return _message_text(result["messages"][-1])

    @tool("data_analysis_agent", description="Delegate calculations and data analysis to a data analysis subagent.")
    async def call_data_analysis_agent(task: str) -> str:
        result = await data_analysis_agent.ainvoke(
            {"messages": [{"role": "user", "content": task}]}
        )
        return _message_text(result["messages"][-1])

    return [call_research_agent, call_coding_agent, call_data_analysis_agent]

