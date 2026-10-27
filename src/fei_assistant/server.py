"""LangGraph API entry points used by assistant-ui."""

from fei_assistant.db import SessionLocal
from fei_assistant.graph import build_graph
from fei_assistant.modules.job_search import build_job_search_graph
from fei_assistant.providers import build_text_model


def configured_model():
    with SessionLocal() as db:
        return build_text_model(db)


graph = build_graph(configured_model)
job_search_graph = build_job_search_graph(configured_model)
