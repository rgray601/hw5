# Campus Customs

A Chapel Street shop desk for MGT 409E. Five agents (Boss, Inventory, Accounting, Facilities, and Customer Service) work tickets 101, 102, and 103. Shop facts come from a FastMCP server on the working database. The FastAPI backend runs the team. The React board is the desk.

Every agent uses `gpt-6-luna` through Portkey. Copy `.env.example` to `.env` in this folder and set `PORTKEY_API_KEY`. Do not commit that file. The model name is fixed in `backend/models.py`.

```
copy .env.example .env
```

On macOS or Linux: `cp .env.example .env`.

## Install

From this folder, with Python 3.11 or newer and Node:

```
python -m venv mcp_server\.venv
mcp_server\.venv\Scripts\python -m pip install -r requirements.txt

python -m venv backend\.venv
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt

cd frontend
npm install
```

On macOS or Linux, the virtualenv interpreter is `bin/python` instead of `Scripts\python`.

## Clean database

`data/campus_customs.db` is the original book. `data/campus_customs_new.db` is the working copy the MCP server reads and writes. The working copy in this repo is the database after tickets 101, 102, and 103 were resolved, with checking at $160.00.

When you want the original books again, copy the original over the working copy:

```
copy /Y data\campus_customs.db data\campus_customs_new.db
```

On macOS or Linux: `cp data/campus_customs.db data/campus_customs_new.db`.

You can do the same copy from the running desk. The Reset control calls `POST /api/reset`, which replaces the working database with the original and clears `output/payment_approvals.json`. The audit trail in `output/audit_trail.json` stays.

Reset before a full three-ticket run. After a reset, shop today is 2026-08-31, checking is $3,400.00, and tickets 101, 102, and 103 are open.

## Start the MCP server

Cursor starts it over stdio from `.mcp.json`. The command there is the Windows virtualenv:

`mcp_server/.venv/Scripts/python.exe mcp_server/server.py`

On macOS or Linux, point that command at `mcp_server/.venv/bin/python`.

To run it yourself, from `mcp_server/`:

```
.venv\Scripts\python server.py
```

The FastAPI process also loads these tools in-process, so the desk can run without a separate MCP window. Start this server when you want Cursor, or a standalone check, to call the tools.

## Start the FastAPI backend

From `backend/`:

```
.venv\Scripts\python -m uvicorn main:app --reload --port 8000
```

The board calls `http://localhost:8000`. Health check: `http://localhost:8000/api/health`.

## Start the React board

From `frontend/`:

```
npm run dev
```

Open `http://localhost:5173`. The page lists the three tickets, runs the team on the one you pick, and shows each agent’s tools. Approving a payment with a human name is what changes checking. A purchase approval does not.

## Reset before a full three-ticket run

Do this after the three processes are up, and before you run 101, then 102, then 103 as a set. On the desk, use Reset to the original books, or:

```
curl -X POST http://localhost:8000/api/reset
```

That copies `data/campus_customs.db` over `data/campus_customs_new.db`. Agents then see open tickets and a $3,400.00 checking balance. Run the tickets only after that reset. A payment still waits for a person; the agents prepare it and do not approve it themselves.
