"""Campus Customs shop tools.

Every agent in this homework calls these tools. They read the working
database only: data/campus_customs_new.db. They do not invent rows.

Cursor starts it over stdio. The connection JSON is `.mcp.json`
at the project root, and the same text is in `.cursor/mcp.json`.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastmcp import FastMCP

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB_PATH = ROOT / "data" / "campus_customs_new.db"
# Humans (later, the board) write this file. No tool here can approve a payment.
APPROVALS_PATH = ROOT / "output" / "payment_approvals.json"
AGENT_NAMES = {
    "boss",
    "inventory",
    "accounting",
    "facilities",
    "customer_service",
    "customer service",
    "agent",
    "system",
    "auto",
}

mcp = FastMCP("campus-customs")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _row(sql: str, params: tuple = ()) -> dict | None:
    with _connect() as conn:
        row = conn.execute(sql, params).fetchone()
    if row is None:
        return None
    return dict(row)


def _rows(sql: str, params: tuple = ()) -> list[dict]:
    with _connect() as conn:
        found = conn.execute(sql, params).fetchall()
    return [dict(row) for row in found]


def _cents(value: float) -> int:
    return int(round(float(value) * 100))


def _add_month(iso_date: str) -> str:
    year, month, day = (int(part) for part in iso_date.split("-"))
    month += 1
    if month == 13:
        month = 1
        year += 1
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    last_day = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    day = min(day, last_day)
    return f"{year:04d}-{month:02d}-{day:02d}"


def _append_note(conn: sqlite3.Connection, ticket_id: int, line: str) -> bool:
    row = conn.execute("SELECT notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if row is None:
        return False
    existing = row["notes"] or ""
    separator = "\n\n" if existing else ""
    conn.execute(
        "UPDATE tickets SET notes = ? WHERE id = ?",
        (existing + separator + line, ticket_id),
    )
    return True


def _load_approvals() -> list[dict]:
    if not APPROVALS_PATH.exists() or APPROVALS_PATH.stat().st_size == 0:
        return []
    loaded = json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        return []
    return [item for item in loaded if isinstance(item, dict)]


def _matching_approval(kind: str, ref_id: int, amount: float, account: str) -> tuple[int, dict] | None:
    amount_cents = _cents(amount)
    for index, item in enumerate(_load_approvals()):
        if item.get("consumed"):
            continue
        approver = str(item.get("approved_by") or "").strip()
        if not approver or approver.lower() in AGENT_NAMES:
            continue
        try:
            same_ref = int(item.get("ref_id")) == ref_id
            same_amount = _cents(item.get("amount")) == amount_cents
        except (TypeError, ValueError):
            continue
        if (
            str(item.get("kind") or "") == kind
            and same_ref
            and same_amount
            and str(item.get("account") or "") == account
        ):
            return index, item
    return None


def record_human_approval(
    kind: str, ref_id: int, amount: float, account: str, approved_by: str
) -> dict:
    """Store a person's approval. Not an MCP tool, so agents cannot call it."""
    approver = approved_by.strip()
    if not approver or approver.lower() in AGENT_NAMES:
        return {
            "recorded": False,
            "reason": "A person has to approve this. An agent name is not an approver.",
        }
    rows = _load_approvals()
    rows.append(
        {
            "kind": kind,
            "ref_id": ref_id,
            "amount": amount,
            "account": account,
            "approved_by": approver,
            "consumed": False,
        }
    )
    APPROVALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    APPROVALS_PATH.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return {"recorded": True, "approved_by": approver}


def _consume_approval(index: int) -> None:
    rows = _load_approvals()
    if index < 0 or index >= len(rows):
        return
    rows[index]["consumed"] = True
    APPROVALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    APPROVALS_PATH.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


@mcp.tool
def stock_on_hand(sku: str, size: str) -> dict:
    """Units on hand for one SKU and one size, from the inventory table.

    Returns that row's sku, name, size, qty, and location.
    qty 0 means that size is out. A missing row is not the same as qty 0.
    Does not substitute another size and does not guess a quantity.
    """
    sku = sku.strip()
    size = size.strip()
    row = _row(
        """
        SELECT sku, name, size, qty, location
        FROM inventory
        WHERE sku = ? AND size = ?
        """,
        (sku, size),
    )
    if row is None:
        return {"found": False, "sku": sku, "size": size}
    return {"found": True, **row}


@mcp.tool
def lease_terms(lease_id: int) -> dict:
    """The shop lease row: space, landlord, monthly rent, and next due date.

    Reads the leases table only. Does not decide whether rent is overdue
    and does not invent a payment.
    """
    row = _row(
        """
        SELECT id, space_name, landlord, monthly_rent, next_due, notes
        FROM leases
        WHERE id = ?
        """,
        (lease_id,),
    )
    if row is None:
        return {"found": False, "lease_id": lease_id}
    return {"found": True, **row}


@mcp.tool
def sku_prices(sku: str) -> dict:
    """Unit cost and list price for one SKU, from the pricing table.

    One price covers every size of that SKU. Does not apply a discount
    and does not invent a price when the SKU is missing.
    """
    sku = sku.strip()
    row = _row(
        """
        SELECT sku, unit_cost, list_price
        FROM pricing
        WHERE sku = ?
        """,
        (sku,),
    )
    if row is None:
        return {"found": False, "sku": sku}
    return {"found": True, **row}


@mcp.tool
def shop_today(note: str = "") -> dict:
    """The shop clock from the desk table.

    date_today is "today" for overdue checks. This tool does not use the
    computer's date and does not invent one if the desk row is missing.
    """
    row = _row("SELECT date_today, notes FROM desk")
    if row is None:
        return {"found": False}
    return {"found": True, **row}


@mcp.tool
def list_open_tickets(status: str = "") -> dict:
    """Every ticket whose status is open, from the tickets table."""
    rows = _rows(
        """
        SELECT id, type, requester, subject, sku, size, qty, lease_id,
               invoice_id, status, notes, created_at
        FROM tickets
        WHERE status = 'open'
        ORDER BY id
        """
    )
    return {"count": len(rows), "tickets": rows}


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """One ticket row, including sku, size, qty, lease_id, and invoice_id.

    Does not look up stock, rent, or the invoice amount. Those are other tools.
    """
    row = _row(
        """
        SELECT id, type, requester, subject, sku, size, qty, lease_id,
               invoice_id, status, notes, created_at
        FROM tickets
        WHERE id = ?
        """,
        (ticket_id,),
    )
    if row is None:
        return {"found": False, "ticket_id": ticket_id}
    return {"found": True, **row}


@mcp.tool
def list_vendors(specialty: str = "", sku: str = "") -> dict:
    """Every vendor: name, specialty, and lead_days. Reads the vendors table only."""
    rows = _rows(
        "SELECT id, name, specialty, lead_days FROM vendors ORDER BY id"
    )
    return {"count": len(rows), "vendors": rows}


@mcp.tool
def vendor_open_invoices(vendor_id: int) -> dict:
    """Vendor lead time plus any invoice still marked open.

    A vendor will not ship new product while one of those invoices is unpaid.
    will_ship is false exactly when an open invoice row exists. It is not a guess.
    """
    vendor = _row(
        "SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?",
        (vendor_id,),
    )
    if vendor is None:
        return {"found": False, "vendor_id": vendor_id}
    open_invoices = _rows(
        """
        SELECT id, vendor_id, amount, due_date, status, description
        FROM invoices
        WHERE vendor_id = ? AND status = 'open'
        ORDER BY id
        """,
        (vendor_id,),
    )
    return {
        "found": True,
        **vendor,
        "open_invoices": open_invoices,
        "will_ship": len(open_invoices) == 0,
    }


@mcp.tool
def get_invoice(invoice_id: int) -> dict:
    """One invoice: vendor, amount, due date, status, and description."""
    row = _row(
        """
        SELECT id, vendor_id, amount, due_date, status, description
        FROM invoices
        WHERE id = ?
        """,
        (invoice_id,),
    )
    if row is None:
        return {"found": False, "invoice_id": invoice_id}
    return {"found": True, **row}


@mcp.tool
def cash_balance(account: str = "checking") -> dict:
    """Cash on hand for one account. Reads cash_accounts and does not change it."""
    name = account.strip()
    row = _row(
        "SELECT name, balance, date FROM cash_accounts WHERE name = ?",
        (name,),
    )
    if row is None:
        return {"found": False, "account": name}
    return {"found": True, **row}


@mcp.tool
def list_payments(account: str = "") -> dict:
    """Payments already recorded. Empty means no cash has left the shop."""
    rows = _rows(
        """
        SELECT id, kind, ref_id, amount, account, paid_at, approved_by
        FROM payments
        ORDER BY id
        """
    )
    return {"count": len(rows), "payments": rows}


@mcp.tool
def append_board_note(ticket_id: int, note: str) -> dict:
    """Append a draft or working note onto a ticket. Nothing is emailed or called.

    The note stays on the ticket. This does not change stock, cash, or status.
    """
    text = " ".join(note.split())
    if not text:
        return {"saved": False, "ticket_id": ticket_id, "reason": "The note is empty."}
    if len(text) > 2000:
        return {"saved": False, "ticket_id": ticket_id, "reason": "The note is too long."}
    line = f"[board] {text}"
    with _connect() as conn:
        if not _append_note(conn, ticket_id, line):
            return {"saved": False, "ticket_id": ticket_id, "reason": "No ticket with that id."}
    return {"saved": True, "ticket_id": ticket_id, "note": line}


@mcp.tool
def set_ticket_status(ticket_id: int, status: str) -> dict:
    """Set a ticket's status. Allowed values: open, waiting_approval, resolved.

    waiting_approval means a person still has to decide. This tool does not pay anyone.
    """
    status = status.strip()
    allowed = {"open", "waiting_approval", "resolved"}
    if status not in allowed:
        return {
            "updated": False,
            "ticket_id": ticket_id,
            "reason": "Status must be open, waiting_approval, or resolved.",
        }
    with _connect() as conn:
        cursor = conn.execute(
            "UPDATE tickets SET status = ? WHERE id = ?",
            (status, ticket_id),
        )
        if cursor.rowcount != 1:
            return {"updated": False, "ticket_id": ticket_id, "reason": "No ticket with that id."}
    return {"updated": True, "ticket_id": ticket_id, "status": status}


@mcp.tool
def draft_purchase_order(ticket_id: int, vendor_id: int, sku: str, size: str, qty: int) -> dict:
    """Write a purchase-order draft on the ticket. Does not call the vendor or change stock.

    Refuses when that vendor still has an open invoice, because they will not ship.
    Lead days come from the vendors row. Qty must be a positive integer.
    """
    sku = sku.strip()
    size = size.strip()
    if qty < 1:
        return {"drafted": False, "reason": "Quantity must be at least 1."}
    vendor = _row(
        "SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?",
        (vendor_id,),
    )
    if vendor is None:
        return {"drafted": False, "vendor_id": vendor_id, "reason": "No vendor with that id."}
    open_invoices = _rows(
        """
        SELECT id, amount, due_date, status, description
        FROM invoices
        WHERE vendor_id = ? AND status = 'open'
        ORDER BY id
        """,
        (vendor_id,),
    )
    if open_invoices:
        return {
            "drafted": False,
            "reason": "This vendor will not ship while an invoice is still open and unpaid.",
            "vendor": vendor,
            "open_invoices": open_invoices,
        }
    stock = _row(
        "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
        (sku, size),
    )
    line = (
        f"[purchase order draft] vendor_id={vendor['id']} {vendor['name']} "
        f"specialty={vendor['specialty']} lead_days={vendor['lead_days']} "
        f"sku={sku} size={size} qty={qty}. Not sent to the vendor."
    )
    with _connect() as conn:
        if not _append_note(conn, ticket_id, line):
            return {"drafted": False, "ticket_id": ticket_id, "reason": "No ticket with that id."}
    return {
        "drafted": True,
        "ticket_id": ticket_id,
        "note": line,
        "vendor": vendor,
        "stock": stock,
    }


@mcp.tool
def propose_payment(
    ticket_id: int,
    kind: str,
    ref_id: int,
    amount: float,
    account: str = "checking",
    memo: str = "",
) -> dict:
    """Prepare a payment for a person to approve. Does not move cash.

    kind is "invoice" or "rent". The amount must match the invoice or the lease
    in the database. If the checking balance cannot cover it, nothing is written.
    """
    kind = kind.strip()
    account = account.strip()
    if kind not in {"invoice", "rent"}:
        return {"proposed": False, "reason": "Kind must be invoice or rent."}
    if _cents(amount) <= 0:
        return {"proposed": False, "reason": "Amount must be greater than zero."}

    if kind == "invoice":
        source = _row(
            """
            SELECT id, vendor_id, amount, due_date, status, description
            FROM invoices WHERE id = ?
            """,
            (ref_id,),
        )
        if source is None:
            return {"proposed": False, "reason": "No invoice with that id."}
        if source["status"] != "open":
            return {"proposed": False, "reason": "That invoice is not open.", "invoice": source}
        expected = source["amount"]
    else:
        source = _row(
            """
            SELECT id, space_name, landlord, monthly_rent, next_due
            FROM leases WHERE id = ?
            """,
            (ref_id,),
        )
        if source is None:
            return {"proposed": False, "reason": "No lease with that id."}
        expected = source["monthly_rent"]

    if _cents(amount) != _cents(expected):
        return {
            "proposed": False,
            "reason": "Amount does not match the database.",
            "database_amount": expected,
        }

    cash = _row(
        "SELECT name, balance, date FROM cash_accounts WHERE name = ?",
        (account,),
    )
    if cash is None:
        return {"proposed": False, "reason": "No cash account with that name."}
    if _cents(amount) > _cents(cash["balance"]):
        return {
            "proposed": False,
            "reason": "Not enough cash. A payment that would go negative is refused.",
            "balance": cash["balance"],
            "amount": expected,
        }

    memo_text = " ".join(memo.split())[:300]
    marker = (
        f"[payment proposal] kind={kind} ref_id={ref_id} amount={expected:.2f} "
        f"account={account} "
    )
    existing = _row("SELECT notes FROM tickets WHERE id = ?", (ticket_id,))
    if existing and marker in (existing["notes"] or ""):
        return {
            "proposed": True,
            "paid": False,
            "needs_human_approval": True,
            "already_proposed": True,
            "ticket_id": ticket_id,
            "kind": kind,
            "ref_id": ref_id,
            "amount": expected,
            "account": account,
            "balance": cash["balance"],
            "source": source,
        }
    line = (
        f"{marker}cash_before={cash['balance']:.2f} "
        f"needs_human_approval=true. {memo_text}".rstrip()
    )
    with _connect() as conn:
        if not _append_note(conn, ticket_id, line):
            return {"proposed": False, "ticket_id": ticket_id, "reason": "No ticket with that id."}
    return {
        "proposed": True,
        "paid": False,
        "needs_human_approval": True,
        "ticket_id": ticket_id,
        "kind": kind,
        "ref_id": ref_id,
        "amount": expected,
        "account": account,
        "balance": cash["balance"],
        "source": source,
        "note": line,
    }


@mcp.tool
def pay(kind: str, ref_id: int, amount: float, account: str = "checking") -> dict:
    """Pay an open invoice or the current rent. Cash only goes out.

    Refuses unless a human approval is already on file for this exact kind,
    ref id, amount, and account. Refuses if the balance would go below zero.
    On success, writes the payments row, lowers cash_accounts, and updates the
    invoice status or the lease next_due. Agent names cannot be the approver.
    """
    kind = kind.strip()
    account = account.strip()
    if kind not in {"invoice", "rent"}:
        return {"paid": False, "reason": "Kind must be invoice or rent."}
    if _cents(amount) <= 0:
        return {"paid": False, "reason": "Amount must be greater than zero."}

    match = _matching_approval(kind, ref_id, amount, account)
    if match is None:
        return {
            "paid": False,
            "reason": "Human approval is required before cash can leave the shop. None is on file for this payment.",
        }
    approval_index, approval = match

    with _connect() as conn:
        today_row = conn.execute("SELECT date_today FROM desk").fetchone()
        if today_row is None:
            return {"paid": False, "reason": "The desk has no shop date."}
        shop_date = today_row["date_today"]
        cash = conn.execute(
            "SELECT name, balance FROM cash_accounts WHERE name = ?",
            (account,),
        ).fetchone()
        if cash is None:
            return {"paid": False, "reason": "No cash account with that name."}
        if _cents(amount) > _cents(cash["balance"]):
            return {
                "paid": False,
                "reason": "Not enough cash. Refused so the balance cannot go negative.",
                "balance": cash["balance"],
            }

        if kind == "invoice":
            source = conn.execute(
                "SELECT id, amount, status FROM invoices WHERE id = ?",
                (ref_id,),
            ).fetchone()
            if source is None:
                return {"paid": False, "reason": "No invoice with that id."}
            if source["status"] != "open":
                return {"paid": False, "reason": "That invoice is not open."}
            if _cents(amount) != _cents(source["amount"]):
                return {
                    "paid": False,
                    "reason": "Amount does not match the invoice.",
                    "database_amount": source["amount"],
                }
        else:
            source = conn.execute(
                "SELECT id, monthly_rent, next_due FROM leases WHERE id = ?",
                (ref_id,),
            ).fetchone()
            if source is None:
                return {"paid": False, "reason": "No lease with that id."}
            if _cents(amount) != _cents(source["monthly_rent"]):
                return {
                    "paid": False,
                    "reason": "Amount does not match the monthly rent.",
                    "database_amount": source["monthly_rent"],
                }

        new_balance_cents = _cents(cash["balance"]) - _cents(amount)
        new_balance = new_balance_cents / 100
        cursor = conn.execute(
            """
            INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (kind, ref_id, amount, account, shop_date, approval["approved_by"]),
        )
        payment_id = cursor.lastrowid
        conn.execute(
            "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
            (new_balance, shop_date, account),
        )
        if kind == "invoice":
            conn.execute(
                "UPDATE invoices SET status = 'paid' WHERE id = ?",
                (ref_id,),
            )
            updated = {"invoice_id": ref_id, "status": "paid"}
        else:
            next_due = _add_month(source["next_due"])
            conn.execute(
                "UPDATE leases SET next_due = ? WHERE id = ?",
                (next_due, ref_id),
            )
            updated = {"lease_id": ref_id, "next_due": next_due}

    _consume_approval(approval_index)
    return {
        "paid": True,
        "payment_id": payment_id,
        "kind": kind,
        "ref_id": ref_id,
        "amount": amount,
        "account": account,
        "balance": new_balance,
        "paid_at": shop_date,
        "approved_by": approval["approved_by"],
        "updated": updated,
    }


if __name__ == "__main__":
    mcp.run()
