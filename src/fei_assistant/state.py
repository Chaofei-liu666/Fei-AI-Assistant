from typing import Annotated

from langchain.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from .contracts import Route


class FeiState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    route: Route

