# Campus Customs harness

Notes for the agent team: the shop database, and later the models, tools, safety rules, and how to run the board.

The original database is `data/campus_customs.db`. Tools and later problems write to the working copy, `data/campus_customs_new.db`. The two files match as of this problem. Copy the original over the working file before a full ticket run.

Shop date is `desk.date_today`: **2026-08-31**. Something is overdue only when its due date is before that day. Nine tables. Declared foreign keys: `invoices.vendor_id` → `vendors.id`, `tickets.invoice_id` → `invoices.id`, `tickets.lease_id` → `leases.id`. Ticket SKUs match `inventory` and `pricing` by value. `payments.account` matches `cash_accounts.name`. `payments` is empty.

## desk

Agents treat this row as the shop clock when they decide what is overdue.

- **date_today** — Shop "today," `2026-08-31`. Compare invoice due dates and lease due dates to this, not to the computer's date.
- **notes** — Free text on the desk. Empty in this database.

## tickets

This is the board Boss reads, assigns, and closes.

- **id** — Ticket id. The three open tickets are 101, 102, and 103.
- **type** — Kind of work: `customer_order`, `rent_notice`, or `price_override`.
- **requester** — Who asked. A customer, the landlord, or a student org.
- **subject** — Short title for the board.
- **sku** — Product the ticket is about, when it is a merch ticket. Null on the rent notice.
- **size** — Size asked for. Paired with `sku` to find one inventory row.
- **qty** — How many units the requester wants. Null on the rent notice.
- **lease_id** — Lease this ticket is about. Foreign key to `leases.id`. Set only on the rent notice.
- **invoice_id** — Vendor bill tied to this ticket. Foreign key to `invoices.id`. Set only on the tee order.
- **status** — `open` on all three. Later runs change this as a ticket is resolved.
- **notes** — The request in plain language.
- **created_at** — When the ticket was opened, with a timezone offset.

## inventory

Inventory checks stock by SKU and size and names the shortfall.

- **sku** — Product code. Part of the primary key, with `size`.
- **name** — Product name on the shelf.
- **size** — `S`, `M`, `L`, `XL`, or `OS` (one size). Part of the primary key.
- **qty** — Units on hand. `0` means that size is out.
- **location** — Aisle where that size sits.

Ten rows. `CC-TEE-WHITE` / `S` and `CC-MUG-CREST` / `OS` are at 0. Hoodie sizes on hand: S 4, M 8, L 14, XL 6. Hats: 40.

## pricing

Accounting uses cost and list price to judge a discount and a reorder.

- **sku** — Product code. Primary key. One price for every size of that SKU.
- **unit_cost** — What the shop pays per unit.
- **list_price** — What the shop charges per unit.

| SKU | Unit cost | List price |
| --- | --- | --- |
| CC-HOOD-NAVY | 22.00 | 58.00 |
| CC-TEE-WHITE | 8.00 | 28.00 |
| CC-HAT-BLUE | 6.00 | 22.00 |
| CC-MUG-CREST | 3.50 | 14.00 |

## vendors

Inventory uses this table to pick who can restock and how long the wait is.

- **id** — Vendor id. Invoices point here.
- **name** — Vendor name.
- **specialty** — What they supply. Match this to the product before assigning a restock.
- **lead_days** — Days from order to arrival. This is the lead time the shop rules refer to.

| id | Name | Specialty | Lead days |
| --- | --- | --- | --- |
| 1 | Bulldog Print Co | apparel reprint | 5 |
| 2 | Elm City Gifts | mugs and small goods | 3 |
| 3 | QuickShip CT | local courier | 1 |

A vendor will not ship new product while they still have an open unpaid invoice. Bulldog Print Co is the apparel vendor, and invoice 501 is open, so they will not ship a tee or hoodie reprint until that bill is paid.

## invoices

Accounting watches open bills, and Inventory has to see them before asking a vendor to ship.

- **id** — Invoice id. Ticket 101 points at 501.
- **vendor_id** — Who is owed. Foreign key to `vendors.id`.
- **amount** — Dollars owed.
- **due_date** — When it was due. Compare to `desk.date_today`.
- **status** — `open` until a payment clears it.
- **description** — What the bill was for.

One row: invoice 501, vendor 1, **$840.00**, due **2026-08-28**, status `open`, "Rush reprint CC-TEE-WHITE S". Due three days before shop today, so it is overdue.

## leases

Facilities reads this when a ticket is about the shop space.

- **id** — Lease id. Ticket 102 points at 1.
- **space_name** — Which space. `Chapel Street shop`.
- **landlord** — Who is paid. `Elm City Properties`.
- **monthly_rent** — Rent for one month, in dollars.
- **next_due** — Next rent date. Compare to `desk.date_today`.
- **notes** — Extra lease terms. Empty here.

One row: id 1, monthly rent **$2,400.00**, next due **2026-09-02**.

## cash_accounts

Accounting reads the balance before a payment. The pay tool must refuse if the balance would go below zero. Cash only goes out.

- **name** — Account name and primary key. The only account is `checking`. Payments store this name in `account`.
- **balance** — Dollars on hand. **$3,400.00**.
- **date** — As-of date, `2026-08-31`, the same day as `desk.date_today`.

Paying the overdue $840 bill and the $2,400 rent would leave **$160.00**. Either payment fits on its own. A third cash outlay on top of both would have to be checked against whatever is left.

## payments

This is the record that a human approved a payment and that cash left the account. It is empty. No payment should be written here without that approval.

- **id** — Payment id.
- **kind** — What was paid (an invoice, rent, or another outflow).
- **ref_id** — Id of the invoice, lease, or other row this payment settles.
- **amount** — Dollars paid.
- **account** — Which cash account. Matches `cash_accounts.name`.
- **paid_at** — When it was paid.
- **approved_by** — Who approved it. Required. The agents do not approve payments themselves.

## Open tickets

All three are `status = open`. None has a payment yet.

### 101 — customer order, Bulldog tee

Tauhid Zaman wants **1** `CC-TEE-WHITE` in size **S** ("Needs a tee in size S.").

- **inventory.** Size S quantity is **0**. Sizes M, L, and XL are in stock, but they do not fill an S order. Shortfall is 1.
- **pricing.** Unit cost $8, list price $28.
- **invoices.** `invoice_id` 501 is the open **$840** rush reprint of this same SKU and size. Due 2026-08-28, so it is overdue on shop today.
- **vendors.** Vendor 1, Bulldog Print Co, does apparel reprints in 5 lead days. They will not ship another reprint while 501 is unpaid.
- **cash_accounts.** Checking can cover $840 and would be left at $2,560.
- **Customer service** can draft a reply for the board. Nothing is emailed.

Boss has to send this through Inventory (shortfall and the blocked vendor), Accounting (overdue bill, human approval, then a payments row and an invoice status change), and Customer Service (draft only).

### 102 — rent notice

Elm City Properties says shop rent is due in 2 days. No SKU and no invoice.

- **leases.** `lease_id` 1 is the Chapel Street shop. The landlord name matches the requester. Rent is **$2,400**. `next_due` is **2026-09-02**, two days after shop today, so it is not overdue yet.
- **cash_accounts.** Checking can cover $2,400. If the $840 bill is paid first, $2,560 remains and the rent still fits, leaving $160.
- **payments.** A rent payment would record kind, `ref_id` 1, the checking account, and `approved_by`. Facilities owns the lease; Accounting prepares the payment and waits for a person.

### 103 — price override, bulk hoodie discount

Yale AI Club wants **20** `CC-HOOD-NAVY` hoodies in size **M** at a bulk discount. No lease and no invoice.

- **inventory.** Size M quantity is **8**, so the shortfall is **12**. Other sizes do not substitute.
- **pricing.** Unit cost $22, list price $58, margin $36 a hoodie before any discount. Twenty at list would be $1,160, with cost $440. Accounting has to check that a discount still clears the cost.
- **vendors.** An apparel reprint goes to Bulldog Print Co (5 lead days). That vendor is blocked by open invoice 501. Elm City Gifts supplies mugs, and QuickShip CT is a courier, so neither replaces the printer.
- **Customer service** drafts the reply about the discount. The draft stays on the board.

Boss sends this through Inventory (on-hand count, shortfall, which vendor), Accounting (margin, and the blocked vendor's unpaid bill if a restock has to be paid for), and Customer Service (draft only).

## Agents

The team is in `backend/team.py`. Prompts are in `backend/prompts/`. Every agent uses `gpt-6-luna` through Portkey. Shop facts come only from the MCP server. Any role may call `ask_colleague` on any other role. A role cannot call itself, cannot call someone already on the chain, and cannot go past three roles deep.

- **Boss** reads the ticket, picks who should work it, and sets the final status. It does not approve payments.
- **Inventory** checks the SKU and size, names the shortfall, and will not draft a purchase order to a vendor who still has an open invoice.
- **Accounting** checks cash, invoice amounts, and margin (list price minus unit cost). It may propose a payment. It does not call `pay`.
- **Facilities** reads the lease and compares `next_due` to shop today. It asks Accounting when rent should be prepared.
- **Customer Service** writes the customer draft onto the ticket with `append_board_note`. It does not email anyone.

Per-run caps, so a ticket cannot wander: Boss 24 model requests and 24 tool calls, 700 seconds. Inventory and Accounting 16 and 16, 150 seconds. Facilities and Customer Service 12 and 12, 120 seconds. `ask_colleague` runs one call at a time.

## MCP tools

The server is `mcp_server/server.py`. It uses `data/campus_customs_new.db` only. The first three tools are the ones that unlock the open tickets. The rest are what the agents need to finish that work.

### stock_on_hand

Reads **inventory**. Unlocks ticket **101**.

Ticket 101 asks for one `CC-TEE-WHITE` in size S, and this tool reads the inventory row that shows that size at quantity 0 in Aisle B, so the tee cannot ship from the shelf.

### lease_terms

Reads **leases**. Unlocks ticket **102**.

Ticket 102 only stores `lease_id` 1, and this tool reads the Chapel Street shop lease for Elm City Properties: monthly rent $2,400, next due 2026-09-02.

### sku_prices

Reads **pricing**. Unlocks ticket **103**.

Ticket 103 asks for a bulk discount on `CC-HOOD-NAVY` and includes no price, and this tool reads that SKU's unit cost $22 and list price $58 so Accounting can see the margin before a discount is offered.

### shop_today

Reads **desk**. Every ticket uses it. Overdue means a due date before `date_today`, which is 2026-08-31, not the computer's clock.

### list_open_tickets

Reads **tickets**. Boss uses it to see 101, 102, and 103 while they are still open.

### get_ticket

Reads **tickets**. One row, including the SKU, size, quantity, `lease_id`, and `invoice_id` the other tools need.

### list_vendors

Reads **vendors**. Inventory uses specialty and `lead_days` to pick who can restock. Apparel reprint is Bulldog Print Co, not the mug vendor or the courier.

### vendor_open_invoices

Reads **vendors** and **invoices**. Ticket 101's reprint vendor is Bulldog Print Co, and this tool shows invoice 501 still open, so `will_ship` is false.

### get_invoice

Reads **invoices**. Ticket 101's `invoice_id` 501 is the $840 rush reprint, due 2026-08-28, so it is overdue on shop today.

### cash_balance

Reads **cash_accounts**. Accounting checks the $3,400 checking balance before a proposal. The $840 bill and the $2,400 rent both fit; together they leave $160.

### list_payments

Reads **payments**. The table is empty until a human-approved payment is written.

### append_board_note

Writes **tickets**. Customer Service puts the draft on the ticket. Nothing is emailed.

### set_ticket_status

Writes **tickets**. Boss sets `open`, `waiting_approval`, or `resolved`. A payment or a discount still waiting on a person stays `waiting_approval`.

### draft_purchase_order

Reads **vendors**, **invoices**, and **inventory**. Writes **tickets**. Refuses while that vendor has an open invoice, so ticket 101 cannot place a tee reprint until invoice 501 is paid. A draft that does go through is only a note. Stock does not change, and the vendor is not called.

### propose_payment

Reads **cash_accounts** and either **invoices** or **leases**. Writes **tickets**. Accounting uses it for the $840 invoice on ticket 101 and the $2,400 rent on ticket 102. The amount must match the database. If cash cannot cover it, nothing is written. This does not move money.

### pay

Reads **desk**, **cash_accounts**, and either **invoices** or **leases**. Writes **payments**, **cash_accounts**, and the invoice status or the lease `next_due`. It refuses when no human approval is on file in `output/payment_approvals.json`, when the approver is an agent name, or when the balance would go below zero. Agents have no tool that writes that approval file.

## Safety

A real shop would not let an agent email a customer, call a vendor, or send money. Drafts stay on the ticket. `pay` does not run unless a person has already approved that exact kind, id, amount, and account, and the approver cannot be Boss, Inventory, Accounting, Facilities, or Customer Service. The balance cannot go negative. Cash only goes out. A vendor with an open invoice cannot receive a purchase-order draft.

Token caps are the delegation depth of 3, the per-role request and tool limits above, and a 500-character preview on each audit step. `output/audit_trail.json` is append-only. A new run adds steps. It does not replace the file. The model string in code is `gpt-6-luna` only.

## Routes

From `backend/`, `uvicorn main:app --reload --port 8000`. The board calls `http://localhost:8000`.

- `GET /api/tickets` — the three desk tickets (101, 102, 103) and whether each is open or resolved.
- `POST /api/tickets/{ticket_id}/run` — run the agent team on that ticket.
- `GET /api/events` — recent agent steps: what each agent said and which tools they used.
- `POST /api/approve` — a person approves a prepared payment or purchase; a payment is what changes the checking balance.
- `GET /api/cash` — the current checking balance from `cash_accounts`.
- `POST /api/reset` — copy `campus_customs.db` over the working database for a fresh run. The audit trail stays.

## Dashboard

The desk is `frontend/`, React with Vite and TypeScript, started with `npm run dev` on port 5173. It calls `http://localhost:8000`. CORS allows `http://localhost:5173` and `http://127.0.0.1:5173`. Layout and color choices are in `output/design.md`.

The page is one Inventing Room desk. Golden tickets on the left are 101, 102, and 103. Picking one runs the team with `POST /api/tickets/{id}/run`. While that call is open, the page polls `GET /api/events` and shows each agent’s last line and the tools on that step. Boss is purple, Inventory wears stockroom stripes, Accounting is gold, Facilities is green, and Customer Service is pink. A resolved ticket gets a green edge and a Resolved chip. A ticket left in `waiting_approval` says Needs a person.

Checking is the gold bar, from `GET /api/cash`. It drops only after a person approves a payment through `POST /api/approve`. A purchase approval stays on the ticket and does not change the bar. The name field rejects an agent name. Reset calls `POST /api/reset` and puts the original books back. `?ticket=101`, `102`, or `103` opens that ticket, which is how the resolved-board screenshots were taken.

