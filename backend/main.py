"""Campus Customs agent API.

From this folder:
  uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from audit import AUDIT_PATH
from config import ROOT, require_api_key
from models import MODEL_NAME, ApproveRequest, RunRequest, TeamResult
from team import run_ticket

load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / "Lecture 2" / ".env")

MCP_DIR = ROOT / "mcp_server"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))
import server as shop  # noqa: E402

TICKET_IDS = (101, 102, 103)
ORIGINAL_DB = ROOT / "data" / "campus_customs.db"

app = FastAPI(title="Campus Customs Multi-Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ticket_view(ticket_id: int) -> dict[str, Any]:
    row = shop.get_ticket(ticket_id)
    status = row.get("status")
    return {
        **row,
        "open": status == "open",
        "resolved": status == "resolved",
    }


def _load_audit() -> list[dict[str, Any]]:
    if not AUDIT_PATH.exists() or AUDIT_PATH.stat().st_size == 0:
        return []
    try:
        loaded = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return [row for row in loaded if isinstance(row, dict)]


def _agent_summaries(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What each agent said, and which tools that agent used, in run order."""
    order: list[str] = []
    buckets: dict[str, dict[str, Any]] = {}
    for step in events:
        agent = str(step.get("agent") or "unknown")
        if agent not in buckets:
            order.append(agent)
            buckets[agent] = {"agent": agent, "said": "", "tools": []}
        bucket = buckets[agent]
        if step.get("step") == "final" and step.get("reply"):
            bucket["said"] = step["reply"]
        tool = step.get("tool")
        if step.get("step") == "tool" and tool and tool not in bucket["tools"]:
            bucket["tools"].append(tool)
    return [buckets[name] for name in order]


@app.get("/api/health")
def health():
    key_set = bool(os.getenv("PORTKEY_API_KEY", "").strip())
    return {
        "ok": True,
        "model": MODEL_NAME,
        "portkey_key_set": key_set,
        "database": "data/campus_customs_new.db",
        "roles": ["boss", "inventory", "accounting", "facilities", "customer_service"],
    }


@app.get("/api/tickets")
def tickets():
    """The three desk tickets and whether each is open or resolved."""
    return {"tickets": [_ticket_view(ticket_id) for ticket_id in TICKET_IDS]}


@app.post("/api/tickets/{ticket_id}/run", response_model=TeamResult)
async def run_one(ticket_id: int, body: RunRequest | None = None) -> TeamResult:
    if ticket_id not in TICKET_IDS:
        raise HTTPException(status_code=404, detail="That ticket is not on this desk.")
    require_api_key()
    note = body.note if body else ""
    return await run_ticket(ticket_id, note)


@app.get("/api/events")
def events(
    ticket_id: int | None = None,
    limit: int = Query(default=80, ge=1, le=300),
):
    """Recent agent-loop steps: what each agent said and which tools they used."""
    rows = _load_audit()
    if ticket_id is not None:
        rows = [row for row in rows if row.get("ticket_id") == ticket_id]
    recent = rows[-limit:]
    return {
        "count": len(recent),
        "events": recent,
        "agents": _agent_summaries(recent),
    }


@app.get("/api/cash")
def cash():
    """Current checking balance from cash_accounts."""
    row = shop.cash_balance("checking")
    if not row.get("found"):
        raise HTTPException(status_code=404, detail="No checking account in the shop database.")
    return row


@app.post("/api/approve")
def approve(body: ApproveRequest):
    """A person approves a prepared payment or purchase.

    Agents only prepare. This route is what calls pay, and pay is what changes cash.
    Approving a purchase order does not move cash and does not call the vendor.
    """
    approver = body.approved_by.strip()
    ticket = shop.get_ticket(body.ticket_id)
    if not ticket.get("found"):
        raise HTTPException(status_code=404, detail="No ticket with that id.")
    if approver.lower() in shop.AGENT_NAMES:
        raise HTTPException(
            status_code=400,
            detail="A person has to approve this. An agent name is not an approver.",
        )

    if body.action == "payment":
        if body.kind is None or body.ref_id is None or body.amount is None:
            raise HTTPException(
                status_code=400,
                detail="A payment approval needs kind, ref_id, and amount.",
            )
        if body.kind == "invoice":
            source = shop.get_invoice(body.ref_id)
            if not source.get("found"):
                raise HTTPException(status_code=404, detail="No invoice with that id.")
            if source.get("status") != "open":
                raise HTTPException(status_code=409, detail="That invoice is not open.")
            expected = float(source["amount"])
        else:
            source = shop.lease_terms(body.ref_id)
            if not source.get("found"):
                raise HTTPException(status_code=404, detail="No lease with that id.")
            expected = float(source["monthly_rent"])
        if round(float(body.amount), 2) != round(expected, 2):
            raise HTTPException(
                status_code=400,
                detail=f"Amount does not match the database ({expected:.2f}).",
            )
        balance = shop.cash_balance(body.account.strip())
        if not balance.get("found"):
            raise HTTPException(status_code=404, detail="No cash account with that name.")
        if round(float(body.amount), 2) > round(float(balance["balance"]), 2):
            raise HTTPException(
                status_code=409,
                detail="Not enough cash. Refused so the balance cannot go negative.",
            )
        recorded = shop.record_human_approval(
            body.kind, body.ref_id, body.amount, body.account.strip(), approver
        )
        if not recorded.get("recorded"):
            raise HTTPException(status_code=400, detail=recorded.get("reason"))
        result = shop.pay(body.kind, body.ref_id, body.amount, body.account.strip())
        balance = shop.cash_balance(body.account.strip())
        if not result.get("paid"):
            raise HTTPException(
                status_code=409,
                detail={"reason": result.get("reason"), "payment": result, "cash": balance},
            )
        shop.append_board_note(
            body.ticket_id,
            f"Payment approved by {approver}. kind={body.kind} ref_id={body.ref_id} "
            f"amount={body.amount:.2f} account={body.account.strip()}.",
        )
        return {
            "approved": True,
            "action": "payment",
            "cash_changed": True,
            "approved_by": approver,
            "payment": result,
            "cash": balance,
        }

    if body.vendor_id is None or not (body.sku or "").strip() or not (body.size or "").strip() or not body.qty:
        raise HTTPException(
            status_code=400,
            detail="A purchase approval needs vendor_id, sku, size, and qty.",
        )
    note = shop.append_board_note(
        body.ticket_id,
        f"Purchase approved by {approver}. vendor_id={body.vendor_id} "
        f"sku={body.sku.strip()} size={body.size.strip()} qty={body.qty}. "
        "Cash was not moved. The vendor was not called.",
    )
    if not note.get("saved"):
        raise HTTPException(status_code=404, detail=note.get("reason"))
    return {
        "approved": True,
        "action": "purchase",
        "cash_changed": False,
        "approved_by": approver,
        "note": note,
        "cash": shop.cash_balance("checking"),
    }


@app.post("/api/reset")
def reset_database():
    """Copy the original shop database over the working copy.

    The audit trail is kept. Stale payment approvals are removed so a fresh
    run cannot spend against an old yes.
    """
    if not ORIGINAL_DB.exists():
        raise HTTPException(status_code=500, detail="The original database is missing.")
    shutil.copyfile(ORIGINAL_DB, shop.DB_PATH)
    if shop.APPROVALS_PATH.exists():
        shop.APPROVALS_PATH.unlink()
    return {
        "reset": True,
        "database": "data/campus_customs_new.db",
        "audit_trail_kept": True,
        "tickets": [_ticket_view(ticket_id) for ticket_id in TICKET_IDS],
        "cash": shop.cash_balance("checking"),
    }
