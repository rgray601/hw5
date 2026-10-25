# AI prompts

Log of what I typed to the vibe coder for Campus Customs Multi-Agent Operations. One section per problem.

## Problem 1 — Vibes Coder Prompts

**Prompt**

Campus Customs Multi-Agent Operations is the agentic team that runs the shop. Open tickets land on a board — customer orders, rent, unpaid bills, discount requests, whatever the shop has to handle. Build three pieces that talk to each other: an MCP server, a FastAPI backend with a multi-agent team, and a React dashboard so a human can watch the agents at work and approve requests.

The team has full connectivity. Any agent may delegate to any other agent. The agents are Boss (reads each ticket, decides who should work on it, and makes final calls), Inventory (stock by SKU and size, shortfalls, which vendor can restock), Accounting (cash, invoices, margins, payments or purchase orders for human approval), Facilities (leases, rent, and the shop space), and Customer Service (drafts messages for customers).

Use `data/campus_customs.db` as the original shop database and a working copy at `data/campus_customs_new.db` for the MCP server and backend. Leave the original untouched so a run can be reset. Shop rules: `desk.date_today` is "today"; vendor lead times come from the vendors table; a vendor will not ship while they have an open unpaid invoice; payments need human approval and must update the relevant tables; the pay tool refuses if cash would go negative; cash only goes out; reset the working database before a full ticket run; do not email customers or call real vendors.

Use only `gpt-6-luna` through Portkey for every agent. The Portkey key and `.env` are in the Lecture 2 folder. Work one problem at a time. Final submission is a public GitHub repo.

I want to start with the last problem, Problem 11, so you understand the final product before we build. Then we begin with Problem 1.

**Follow-up**

Problem 1: Create `AI_prompts.md` at the start and keep it updated. One section per problem. Each section needs the problem number and title, at least one prompt I typed, and a follow-up prompt if I needed one, plus one sentence on what was lacking after the first.

The opening prompt set the shop, the five agents, and the plan to read Problem 11 first, but it never asked for a prompt log or said what each section had to contain.

## Problem 2 — Study the Campus Customs database

**Prompt**

Open `data/campus_customs.db` and look through every table and its fields. Copy the original file to `data/campus_customs_new.db`. Later problems update that working copy, and the original stays untouched.

Study the three open tickets and how they link to the other tables. Start `output/harness.md`. For each table, list the fields and one short line on why that table matters for the agents. This harness file will grow in later problems.

No follow-up. The prompt already named the working copy, the three tickets, and what the harness had to contain.

## Problem 3 — Build the MCP server

**Prompt**

Write an MCP server in `mcp_server/` with FastMCP. Point it at `data/campus_customs_new.db`. Do not connect or run it for this problem.

Every agent will use these tools. Add more later. For now write three tools the open tickets need. Keep the names clear. Never invent data. Only use what is in the database.

In `output/harness.md`, list each tool with the table it reads, which ticket it unlocks (101, 102, or 103), and one sentence on why that tool is the right one for that ticket. Vague lines like "reads inventory" will score low, so tie the tool to the ticket.

Also add a short `mcp_server/README.md` that says what the server is for, which database file it uses, and the three tools it has.

No follow-up. The prompt already named FastMCP, the working database, the three tools, the harness sentence, and the README.

## Problem 4 — Add the MCP server to vibe coder and test each tool

**Prompt**

Add the MCP server to this Cursor project so the vibe coder can call the tools. Save the connection JSON in `.mcp.json` at the project root, or wherever Cursor keeps a project's MCP server list.

With the server connected, test each of the three tools. Save the evidence in `output/mcp_smoke.json`. For every tool include the prompt I asked, the tool name, and the tool output. The output has to match the values in `data/campus_customs_new.db`.

No follow-up. The prompt already named the connection file, the three tools, and the fields the smoke file has to contain.

## Problem 5 — Build the agent team and grow the MCP tools

**Prompt**

Build the Campus Customs team in PydanticAI: Boss, Inventory, Accounting, Facilities, and Customer Service. Put one prompt per agent in `backend/prompts/`, data types in `backend/models.py`, and the agent code under `backend/`. They need full connectivity so any agent can delegate to any other. Use the Portkey key and only `gpt-6-luna`.

Write real shop rules into each prompt, not a short generic one. Add the MCP tools they need for the open tickets. Shop facts come from the MCP server on `data/campus_customs_new.db`. Do not build a second shop-tools layer that skips MCP.

Append each agent-loop step to `output/audit_trail.json`. Do not wipe that file between runs. In `output/harness.md`, list each agent and each MCP tool, including the new ones and which table each tool uses, plus a short safety section for real customers, real money, and token limits. Update `mcp_server/README.md` so the tool list matches.

No follow-up. The prompt already named the five roles, the model, the MCP boundary, the audit file, and the harness sections.

## Problem 6 — Plan the three tickets

**Prompt**

Before wiring more of the backend, write what the team should do on each open ticket. Build `output/desk_tickets.html`, a page I can double-click, with one tab for ticket 101, 102, and 103. Add empty Cash and Reflection tabs for later, with a short "coming later" note.

On each ticket tab, fill an Expected section only, and leave room for an Actual section to fill after the agents run. For each ticket say who the Boss should call first and why, every delegation I expect (not "Boss calls everyone"), and which MCP tools that run should use. Plans that send every specialist on every ticket will score low. We will compare this plan with what the agents actually do.

No follow-up. The prompt already named the page, the five tabs, and the three things each Expected section had to contain.

## Problem 7 — Backend routes

**Prompt**

The React board needs a FastAPI backend it can call. In `backend/main.py`, add routes that return the three tickets and whether each is open or resolved, run the agent team on a ticket id, return recent agent events (what each agent said and which tools they used), approve a payment or purchase after a human clicks approve (agents only prepare; this route is what changes cash), return the checking balance, and reset the working database to the original.

Start it from `backend/` with `uvicorn main:app --reload --port 8000`. In `output/harness.md`, list each route in one line: the URL and what it does.

No follow-up. The prompt already named the six routes, the port, and the harness line for each.

## Problem 8 — Agent dashboard

**Prompt**

Build the dashboard in `frontend/` with React, Vite, and TypeScript. It should call the Problem 7 routes. At minimum: list the three tickets, pick one and start the team, show each agent and what they are saying or doing while it runs, mark a ticket resolved when the run finishes, summarize what each agent did, let a human approve a pay or a purchase, and show the checking balance so it drops after an approved pay.

Make it a desk someone would want to sit at. Keep the Willy Wonka theme from the last assignment. Point the page at `http://localhost:8000`, and allow the Vite origin `http://localhost:5173` on the backend. Start it with `npm run dev`. Write `output/design.md` about the layout, how the agents read differently, how resolved tickets and cash show up, and why those choices feel good to use.

No follow-up. The prompt already named the board behaviors, the Wonka theme, the API origin, and the design writeup.

## Problem 9 — Resolve the tickets

**Prompt**

Reset `data/campus_customs_new.db` before a full run and note the starting checking balance. Run tickets 101, 102, and 103 on the board until each is resolved. Fill the Actual section on each tab of `output/desk_tickets.html`, and keep the Expected section. On the Cash tab, itemize the starting balance, how cash changed on each ticket and why, and the ending balance, which has to match `cash_accounts`.

Also save `output/resolved_tickets.json` (id, final status, short outcome, what each agent contributed, human approvals) and `output/resolved_board.html` with a screenshot of the React board for each resolved ticket. Append the real runs to `output/audit_trail.json`. Finish `output/harness.md` so it covers the tables, MCP tools, five agents, API routes, the dashboard, and the safety rules.

No follow-up. The prompt already named the reset, the three tickets, the cash math, and the files to fill.

## Problem 10 — Reflection

**Prompt**

Open `output/desk_tickets.html` and fill the Reflection tab in my own voice. Be detailed. Evaluate the agents on each ticket and why. For each ticket, compare Actual to the Expected plan. Say what would have been simpler as one agent with tools, and why. Then give three new Campus Customs problems this team could solve with the tools already built, and three it could not, including the tools and agents those would need.

Tie every answer to this app and to tickets 101, 102, and 103. Use the ticket tabs and the Cash tab on the same page as the evidence.

No follow-up. The prompt already named the five questions and said to use this run as the evidence.

## Problem 11 — Submit to GitHub

**Prompt**

Push the code to a public GitHub repository so graders can clone it. Submit the repo URL on Canvas and also put it in `output/github_url.txt`. Do not push the real `.env`. Do include both database files under `data/` so graders can run the app. The README should explain how to copy the original database over the working copy for a clean run, how to start the MCP server, the FastAPI backend, and the React board, and that the database must be reset before a full three-ticket run.

**Follow-up**

Here is the expected `hw5/` file tree: `AI_prompts.md`, `requirements.txt`, `.env.example`, `.gitignore`, `.mcp.json`, `README.md`, both databases under `data/`, `mcp_server/server.py` and its README, `frontend/`, `backend/main.py`, `backend/models.py`, the five agent prompts, and `output/` with `harness.md`, `mcp_smoke.json`, `desk_tickets.html`, `design.md`, `resolved_tickets.json`, `resolved_board.html`, `audit_trail.json`, and `github_url.txt`.

The problem text said where the URL goes and what the README must cover, but it did not show this file tree, so the layout had to come from the attached image.
