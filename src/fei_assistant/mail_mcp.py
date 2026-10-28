"""Read-only MCP server for Fei mail.

Run it as a stdio MCP server:

    python -m fei_assistant.mail_mcp

It exposes search/read tools only. There is deliberately no send, delete or
mark-as-read tool: the agent may look, never act on the mailbox.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime

from sqlalchemy import select

from .db import SessionLocal
from .mail_models import MailEvent
from .models import Application, JobPosting

PROTOCOL_VERSION = "2024-11-05"

TOOLS = [
    {
        "name": "mail_search",
        "description": "Search stored recruitment mail events by subject, sender or summary.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "free text, empty returns recent"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
            },
        },
    },
    {
        "name": "mail_recent",
        "description": "List the most recent recruitment mail events and whether they were applied.",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10}},
        },
    },
    {
        "name": "application_list",
        "description": "List current applications with company, title and stage.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _event_view(row: MailEvent) -> dict:
    return {
        "id": row.id,
        "subject": row.subject,
        "sender": row.sender,
        "received_at": row.received_at.isoformat() if row.received_at else None,
        "category": row.category,
        "confidence": row.confidence,
        "summary": row.summary,
        "application_id": row.application_id,
        "suggested_status": row.suggested_status,
        "deadline": row.deadline.isoformat() if row.deadline else None,
        "deadline_kind": row.deadline_kind,
        "applied": row.applied,
        "reverted": row.reverted,
    }


def call_tool(name: str, arguments: dict) -> dict:
    with SessionLocal() as db:
        if name == "mail_search":
            query = str(arguments.get("query") or "").strip()
            limit = int(arguments.get("limit") or 10)
            statement = select(MailEvent).order_by(MailEvent.created_at.desc()).limit(min(max(limit, 1), 50))
            rows = list(db.scalars(statement).all())
            if query:
                needle = query.lower()
                rows = [
                    row for row in rows
                    if needle in (row.subject or "").lower()
                    or needle in (row.summary or "").lower()
                    or needle in (row.sender or "").lower()
                ]
            return {"items": [_event_view(row) for row in rows]}
        if name == "mail_recent":
            limit = int(arguments.get("limit") or 10)
            rows = db.scalars(
                select(MailEvent).order_by(MailEvent.created_at.desc()).limit(min(max(limit, 1), 50))
            ).all()
            return {"items": [_event_view(row) for row in rows]}
        if name == "application_list":
            rows = db.execute(select(Application, JobPosting).join(JobPosting, Application.job_id == JobPosting.id)).all()
            return {
                "items": [
                    {"application_id": application.id, "company": job.company, "title": job.title,
                     "status": application.status}
                    for application, job in rows
                ]
            }
    return {"error": f"unknown tool: {name}"}


def handle_request(request: dict) -> dict | None:
    method = request.get("method")
    request_id = request.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fei-mail", "version": "0.1.0"},
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method and method.startswith("notifications/"):
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name", "")
        arguments = params.get("arguments") or {}
        try:
            payload = call_tool(name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": _dump(payload)}], "isError": False},
            }
        except Exception as exc:  # keep the server alive on tool errors
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": _dump({"error": str(exc)})}], "isError": True},
            }
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle_request(request)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
