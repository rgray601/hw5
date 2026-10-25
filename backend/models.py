"""Types for the Campus Customs agent team.

Shop rows stay in the MCP tools. These types describe roles, delegation, and the audit.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RoleName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
ROLES: tuple[RoleName, ...] = (
    "boss",
    "inventory",
    "accounting",
    "facilities",
    "customer_service",
)

MODEL_NAME: Literal["gpt-6-luna"] = "gpt-6-luna"


class DelegationRecord(BaseModel):
    """One handoff from one role to another."""

    from_role: RoleName
    to_role: RoleName
    task: str
    reply: str = ""


class AuditStep(BaseModel):
    """One agent-loop step, appended to output/audit_trail.json."""

    time: str
    agent: str
    model: Literal["gpt-6-luna"] = MODEL_NAME
    step: Literal["start", "tool", "delegation", "final", "error"]
    ticket_id: int | None = None
    tool: str | None = None
    args: str | None = None
    result: str | None = None
    stopped: str | None = None
    reply: str | None = None


class TeamResult(BaseModel):
    """What the Boss returns after a ticket run."""

    ticket_id: int
    model: Literal["gpt-6-luna"] = MODEL_NAME
    boss_reply: str
    delegations: list[DelegationRecord] = Field(default_factory=list)


class RunRequest(BaseModel):
    """Optional note to pass in with a ticket run."""

    note: str = ""


class ApproveRequest(BaseModel):
    """A person approving a prepared payment or a purchase-order draft.

    Agents cannot send this. Payment is what changes the checking balance.
    A purchase approval stays on the ticket and does not move cash.
    """

    approved_by: str = Field(min_length=1)
    action: Literal["payment", "purchase"]
    ticket_id: int
    kind: Literal["invoice", "rent"] | None = None
    ref_id: int | None = None
    amount: float | None = None
    account: str = "checking"
    vendor_id: int | None = None
    sku: str | None = None
    size: str | None = None
    qty: int | None = None
