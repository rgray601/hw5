"""Campus Customs agent team.

Five roles, full connectivity: any role may ask any other role.
Shop rows come from the MCP server only. This module does not query the database.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import (
    BaseToolCallPart,
    BaseToolReturnPart,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
)
from pydantic_ai.usage import UsageLimits

from audit import append_step, now_iso
from config import LUNA_SETTINGS, build_model
from models import ROLES, DelegationRecord, RoleName, TeamResult

BACKEND = Path(__file__).resolve().parent
ROOT = BACKEND.parent
PROMPTS = BACKEND / "prompts"
MAX_STACK = 3

LIMITS: dict[str, UsageLimits] = {
    "boss": UsageLimits(request_limit=24, tool_calls_limit=24),
    "inventory": UsageLimits(request_limit=16, tool_calls_limit=16),
    "accounting": UsageLimits(request_limit=16, tool_calls_limit=16),
    "facilities": UsageLimits(request_limit=12, tool_calls_limit=12),
    "customer_service": UsageLimits(request_limit=12, tool_calls_limit=12),
}
TIMEOUTS = {
    "boss": 700,
    "inventory": 150,
    "accounting": 150,
    "facilities": 120,
    "customer_service": 120,
}
_toolset: MCPToolset | None = None
_agents: dict[str, Agent] | None = None


def shop_toolset() -> MCPToolset:
    """In-process FastMCP server. Tools read data/campus_customs_new.db."""
    global _toolset
    if _toolset is None:
        mcp_dir = str(ROOT / "mcp_server")
        if mcp_dir not in sys.path:
            sys.path.insert(0, mcp_dir)
        from server import mcp as shop_mcp

        _toolset = MCPToolset(shop_mcp)
    return _toolset


@dataclass
class RunLog:
    ticket_id: int | None
    delegations: list[DelegationRecord] = field(default_factory=list)


@dataclass
class TeamDeps:
    role: RoleName
    stack: tuple[str, ...]
    log: RunLog


def _normalize_role(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def _collect_tool_calls(messages: list[Any]) -> tuple[list[dict[str, Any]], str]:
    calls: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    finish_reason: str | None = None
    for message in messages:
        if isinstance(message, ModelResponse):
            finish_reason = message.finish_reason
            for part in message.parts:
                if isinstance(part, BaseToolCallPart):
                    entry = {
                        "tool": part.tool_name,
                        "args": part.args_as_dict(),
                        "result": None,
                    }
                    calls.append(entry)
                    by_id[part.tool_call_id] = entry
                elif isinstance(part, BaseToolReturnPart):
                    entry = by_id.get(part.tool_call_id)
                    if entry is not None:
                        entry["result"] = part.content
        elif isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, (BaseToolReturnPart, RetryPromptPart)):
                    entry = by_id.get(getattr(part, "tool_call_id", ""))
                    if entry is not None and entry["result"] is None:
                        entry["result"] = part.content
    stopped = f"final answer (finish_reason={finish_reason or 'stop'})"
    return calls, stopped


def _agents_for_team() -> dict[str, Agent]:
    global _agents
    if _agents is not None:
        return _agents
    model = build_model()
    toolset = shop_toolset()
    built: dict[str, Agent] = {}
    for role in ROLES:
        agent: Agent[TeamDeps, str] = Agent(
            model,
            deps_type=TeamDeps,
            instructions=(PROMPTS / f"{role}.md").read_text(encoding="utf-8"),
            toolsets=[toolset],
            retries=2,
            model_settings=LUNA_SETTINGS,
        )

        @agent.tool(sequential=True, retries=3)
        async def ask_colleague(
            ctx: RunContext[TeamDeps],
            colleague: str | None = None,
            task: str | None = None,
            **extra: Any,
        ) -> str:
            """Ask one other Campus Customs role to handle part of this ticket.

            colleague: boss, inventory, accounting, facilities, or customer_service.
            task: the ticket id and the question. Do not invent shop facts in the task.
            Call one colleague, wait, then call the next. Do not ask every role.
            """
            who = colleague or _extra_text(extra, "role", "to", "name", "agent")
            what = task or _extra_text(extra, "question", "message", "prompt", "request", "query", "note")
            ticket_bit = _extra_text(extra, "ticket_id", "ticket")
            if ticket_bit and "ticket" not in what.lower():
                what = f"Ticket {ticket_bit}. {what}".strip()
            return await _delegate(ctx, who, what)

        built[role] = agent
    _agents = built
    return built


def _extra_text(extra: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = extra.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


async def _delegate(ctx: RunContext[TeamDeps], colleague: str, task: str) -> str:
    name = _normalize_role(colleague)
    if name not in ROLES:
        return "Unknown role. Use boss, inventory, accounting, facilities, or customer_service."
    if name == ctx.deps.role:
        return "Do not ask yourself. Finish your part or ask a different role."
    if name in ctx.deps.stack:
        return f"{name} is already on this chain. Do not loop."
    if len(ctx.deps.stack) >= MAX_STACK:
        return "Delegation depth limit reached. Answer from the facts you already have."
    task = " ".join(task.split())
    if not task:
        return "The task is empty."
    reply = await run_role(name, task, ctx.deps.log, ctx.deps.stack + (name,))
    ctx.deps.log.delegations.append(
        DelegationRecord(
            from_role=ctx.deps.role,
            to_role=name,  # type: ignore[arg-type]
            task=task,
            reply=reply,
        )
    )
    append_step(
        time=now_iso(),
        agent=ctx.deps.role,
        step="delegation",
        ticket_id=ctx.deps.log.ticket_id,
        tool=name,
        args=task,
        result=reply,
    )
    return reply


async def run_role(role: str, task: str, log: RunLog, stack: tuple[str, ...]) -> str:
    """Run one agent. Append a start step, one step per tool call, then a final step."""
    append_step(
        time=now_iso(),
        agent=role,
        step="start",
        ticket_id=log.ticket_id,
        args=task,
    )
    deps = TeamDeps(role=role, stack=stack, log=log)  # type: ignore[arg-type]
    try:
        result = await asyncio.wait_for(
            _agents_for_team()[role].run(
                task,
                deps=deps,
                usage_limits=LIMITS[role],
            ),
            timeout=TIMEOUTS[role],
        )
    except Exception as exc:
        cause = exc.__cause__ or exc.__context__
        cause_text = f" | cause: {cause}" if cause else ""
        detail = f"{type(exc).__name__}: {exc}{cause_text}"[:400]
        append_step(
            time=now_iso(),
            agent=role,
            step="error",
            ticket_id=log.ticket_id,
            stopped=detail,
        )
        return f"{role} failed before finishing ({type(exc).__name__})."

    reply = (result.output or "").strip()
    calls, stopped = _collect_tool_calls(result.new_messages())
    for call in calls:
        append_step(
            time=now_iso(),
            agent=role,
            step="tool",
            ticket_id=log.ticket_id,
            tool=str(call["tool"]),
            args=call["args"],
            result=call["result"],
        )
    append_step(
        time=now_iso(),
        agent=role,
        step="final",
        ticket_id=log.ticket_id,
        stopped=stopped,
        reply=reply,
    )
    return reply or f"{role} returned no text."


async def run_ticket(ticket_id: int, note: str = "") -> TeamResult:
    """Boss reads one ticket and may delegate to any other role."""
    log = RunLog(ticket_id=ticket_id)
    extra = f" Operator note: {note.strip()}" if note.strip() else ""
    task = (
        f"Work ticket {ticket_id}. Call get_ticket and shop_today before you decide. "
        "Delegate to the roles this ticket needs. Make the final call. "
        f"Do not invent shop facts.{extra}"
    )
    reply = await run_role("boss", task, log, ("boss",))
    return TeamResult(ticket_id=ticket_id, boss_reply=reply, delegations=log.delegations)
