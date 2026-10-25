# Campus Customs MCP server

This FastMCP server is the only shop-tool layer. Boss, Inventory, Accounting, Facilities, and Customer Service all call it. It uses the working copy `data/campus_customs_new.db`, one level up from this folder. `data/campus_customs.db` is the untouched original. Reset a run by copying the original over the working file. Do not point the server at the original.

The server does not invent rows, email customers, or call vendors. `pay` moves cash only when a human approval is already in `output/payment_approvals.json`, and it refuses if the balance would go below zero. Agents cannot write that approval file.

Tools:

- `stock_on_hand(sku, size)` reads `inventory`.
- `lease_terms(lease_id)` reads `leases`.
- `sku_prices(sku)` reads `pricing`.
- `shop_today()` reads `desk`.
- `list_open_tickets()` reads `tickets`.
- `get_ticket(ticket_id)` reads `tickets`.
- `list_vendors()` reads `vendors`.
- `vendor_open_invoices(vendor_id)` reads `vendors` and `invoices`.
- `get_invoice(invoice_id)` reads `invoices`.
- `cash_balance(account)` reads `cash_accounts`.
- `list_payments()` reads `payments`.
- `append_board_note(ticket_id, note)` writes `tickets`.
- `set_ticket_status(ticket_id, status)` writes `tickets`.
- `draft_purchase_order(ticket_id, vendor_id, sku, size, qty)` reads `vendors`, `invoices`, and `inventory`, and writes a draft on `tickets` only if that vendor has no open invoice.
- `propose_payment(ticket_id, kind, ref_id, amount, account, memo)` reads `cash_accounts` and the invoice or lease, and writes a proposal on `tickets`. It does not pay.
- `pay(kind, ref_id, amount, account)` writes `payments` and `cash_accounts`, and updates `invoices` or `leases`, only after human approval and only when cash covers the amount.

Cursor starts this server over stdio. The connection is in `.mcp.json` at the project root, and the same text is in `.cursor/mcp.json`. From this folder, with FastMCP installed: `python server.py`.
