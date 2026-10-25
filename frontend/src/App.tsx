import { useCallback, useEffect, useState } from "react"
import {
  approvePayment,
  approvePurchase,
  loadCash,
  loadEvents,
  loadTickets,
  proposalsIn,
  resetShop,
  runTicket,
  type AgentSummary,
  type AuditEvent,
  type Cash,
  type TeamResult,
  type Ticket,
} from "./api"

const ROLES = [
  {
    id: "boss",
    title: "Boss",
    cue: "Purple coat",
    job: "Reads the ticket and makes the final call.",
  },
  {
    id: "inventory",
    title: "Inventory",
    cue: "Stockroom stripes",
    job: "Counts the shelf and names who can restock.",
  },
  {
    id: "accounting",
    title: "Accounting",
    cue: "Golden till",
    job: "Checks the margin and prepares a payment.",
  },
  {
    id: "facilities",
    title: "Facilities",
    cue: "River room",
    job: "Reads the lease and the rent date.",
  },
  {
    id: "customer_service",
    title: "Customer Service",
    cue: "Wrapper desk",
    job: "Writes the draft that stays on the board.",
  },
] as const

function money(amount: number): string {
  return amount.toLocaleString("en-US", { style: "currency", currency: "USD" })
}

function statusLabel(ticket: Ticket, running: boolean): string {
  if (running) return "On the floor"
  if (ticket.resolved || ticket.status === "resolved") return "Resolved"
  if (ticket.status === "waiting_approval") return "Needs a person"
  return "Open"
}

function workingRoles(events: AuditEvent[]): Set<string> {
  const state = new Map<string, "work" | "done">()
  for (const event of events) {
    if (event.step === "start") state.set(event.agent, "work")
    if (event.step === "final" || event.step === "error") state.set(event.agent, "done")
  }
  return new Set(
    [...state.entries()].filter(([, value]) => value === "work").map(([agent]) => agent),
  )
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  const [previousBalance, setPreviousBalance] = useState<number | null>(null)
  const [cashDropped, setCashDropped] = useState(false)
  const [selectedId, setSelectedId] = useState(() => {
    const raw = new URLSearchParams(window.location.search).get("ticket")
    const id = Number(raw)
    return id === 102 || id === 103 ? id : 101
  })
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [agents, setAgents] = useState<AgentSummary[]>([])
  const [result, setResult] = useState<TeamResult | null>(null)
  const [runningId, setRunningId] = useState<number | null>(null)
  const [finishedId, setFinishedId] = useState<number | null>(null)
  const [approver, setApprover] = useState("")
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [busyApproval, setBusyApproval] = useState(false)

  const applyCash = useCallback((next: Cash) => {
    setCash((current) => {
      if (current && next.balance < current.balance) {
        setCashDropped(true)
        window.setTimeout(() => setCashDropped(false), 2400)
      }
      return next
    })
    setPreviousBalance((current) => (current === null ? next.balance : current))
  }, [])

  const refreshDesk = useCallback(async () => {
    const [ticketBody, cashBody] = await Promise.all([loadTickets(), loadCash()])
    setTickets(ticketBody.tickets)
    applyCash(cashBody)
  }, [applyCash])

  const refreshEvents = useCallback(async (ticketId: number) => {
    const body = await loadEvents(ticketId)
    setEvents(body.events)
    setAgents(body.agents)
    const ticketBody = await loadTickets()
    setTickets(ticketBody.tickets)
  }, [])

  useEffect(() => {
    void refreshDesk().catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "The desk is not answering.")
    })
  }, [refreshDesk])

  useEffect(() => {
    if (runningId !== null) return
    void refreshEvents(selectedId).catch(() => undefined)
  }, [selectedId, runningId, refreshEvents])

  const selected = tickets.find((ticket) => ticket.id === selectedId) ?? null
  const prepared = proposalsIn(selected?.notes ?? null)
  const active = workingRoles(events)
  const spoken = new Map(agents.map((agent) => [agent.agent, agent]))

  async function startRun() {
    if (!selected || runningId !== null) return
    setError("")
    setMessage("")
    setResult(null)
    setFinishedId(null)
    setEvents([])
    setAgents([])
    setRunningId(selected.id)
    const timer = window.setInterval(() => {
      void refreshEvents(selected.id).catch(() => undefined)
    }, 1500)
    try {
      const team = await runTicket(selected.id)
      setResult(team)
      setFinishedId(selected.id)
      await refreshEvents(selected.id)
      await refreshDesk()
      setMessage(`Ticket ${selected.id} came back from the floor.`)
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "The team stopped.")
    } finally {
      window.clearInterval(timer)
      setRunningId(null)
    }
  }

  async function signPayment(proposal: (typeof prepared.payments)[number]) {
    if (!selected || !approver.trim()) {
      setError("Sign with your name before cash can leave.")
      return
    }
    setBusyApproval(true)
    setError("")
    try {
      const body = await approvePayment(selected.id, approver.trim(), proposal)
      applyCash(body.cash)
      await refreshDesk()
      setMessage(`Payment of ${money(proposal.amount)} left the checking account.`)
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "The payment was refused.")
    } finally {
      setBusyApproval(false)
    }
  }

  async function signPurchase(draft: (typeof prepared.purchases)[number]) {
    if (!selected || !approver.trim()) {
      setError("Sign with your name. Cash will not move.")
      return
    }
    setBusyApproval(true)
    setError("")
    try {
      const body = await approvePurchase(selected.id, approver.trim(), draft)
      applyCash(body.cash)
      await refreshDesk()
      setMessage("Purchase signed. The vendor was not called, and the balance did not change.")
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "The purchase was not signed.")
    } finally {
      setBusyApproval(false)
    }
  }

  async function freshBooks() {
    setError("")
    setResult(null)
    setEvents([])
    setAgents([])
    setFinishedId(null)
    try {
      await resetShop()
      setPreviousBalance(null)
      await refreshDesk()
      setMessage("The shop is back to the original books.")
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Reset failed.")
    }
  }

  const tape = events.filter((event) => event.step === "tool" || event.step === "delegation").slice(-6)

  return (
    <div className="factory">
      <div className="river" aria-hidden="true" />
      <header className="top">
        <div>
          <p className="eyebrow">Campus Customs · Inventing Room</p>
          <h1>The desk</h1>
        </div>
        <div className={`till ${cashDropped ? "dropped" : ""}`}>
          <span>Checking</span>
          <strong>{cash ? money(cash.balance) : "…"}</strong>
          <small>
            {cash?.date ?? "shop date"}
            {previousBalance !== null && cash && cash.balance < previousBalance
              ? " · cash went out"
              : ""}
          </small>
        </div>
      </header>

      <main className="layout">
        <section className="board" aria-label="Open tickets">
          <h2>Golden tickets</h2>
          {tickets.map((ticket) => {
            const running = runningId === ticket.id
            const resolved = ticket.resolved || ticket.status === "resolved"
            return (
              <button
                key={ticket.id}
                type="button"
                className={`ticket ${selectedId === ticket.id ? "selected" : ""} ${resolved ? "resolved" : ""}`}
                onClick={() => {
                  setSelectedId(ticket.id)
                  setResult(null)
                  setEvents([])
                  setAgents([])
                  setFinishedId(null)
                  void refreshEvents(ticket.id).catch(() => undefined)
                }}
              >
                <span className="ticket-id">No. {ticket.id}</span>
                <strong>{ticket.subject}</strong>
                <span>{ticket.requester}</span>
                <em className={`chip ${resolved ? "done" : ""} ${running ? "live" : ""}`}>
                  {statusLabel(ticket, running)}
                </em>
              </button>
            )
          })}
        </section>

        <section className="floor">
          {selected ? (
            <>
              <div className="ticket-head">
                <div>
                  <p className="eyebrow">{selected.type.replaceAll("_", " ")}</p>
                  <h2>
                    {selected.id} · {selected.subject}
                  </h2>
                  <p>
                    {selected.requester}
                    {selected.sku ? ` · ${selected.sku} ${selected.size ?? ""} × ${selected.qty ?? ""}` : ""}
                    {selected.lease_id ? ` · lease ${selected.lease_id}` : ""}
                    {selected.invoice_id ? ` · invoice ${selected.invoice_id}` : ""}
                  </p>
                  <p className="notes">{selected.notes}</p>
                </div>
                <button
                  type="button"
                  className="run"
                  disabled={runningId !== null}
                  onClick={() => void startRun()}
                >
                  {runningId === selected.id ? "The floor is working…" : "Send this ticket to the floor"}
                </button>
              </div>

              <div className="stations">
                {ROLES.map((role) => {
                  const summary = spoken.get(role.id)
                  const onFloor = runningId === selected.id && active.has(role.id)
                  return (
                    <article key={role.id} className={`station ${role.id} ${onFloor ? "working" : ""}`}>
                      <header>
                        <span>{role.cue}</span>
                        <h3>{role.title}</h3>
                      </header>
                      <p className="job">{role.job}</p>
                      <p className="said">
                        {onFloor
                          ? "Working this ticket."
                          : summary?.said || "Waiting on the bench."}
                      </p>
                      {summary && summary.tools.length > 0 ? (
                        <ul className="tools">
                          {summary.tools.map((tool) => (
                            <li key={tool}>{tool}</li>
                          ))}
                        </ul>
                      ) : null}
                    </article>
                  )
                })}
              </div>

              <div className="tape" aria-live="polite">
                <h2>What they are doing</h2>
                {tape.length === 0 ? (
                  <p className="quiet">Tool calls show up here while the ticket is on the floor.</p>
                ) : (
                  <ol>
                    {tape.map((event, index) => (
                      <li key={`${event.time}-${index}`}>
                        <strong>{event.agent}</strong>{" "}
                        {event.step === "delegation" ? `asked ${event.tool}` : `used ${event.tool}`}
                      </li>
                    ))}
                  </ol>
                )}
              </div>

              {finishedId === selected.id && result ? (
                <div className="summary">
                  <h2>
                    {selected.resolved || selected.status === "resolved"
                      ? "Resolved"
                      : "Run finished"}
                  </h2>
                  <p>{result.boss_reply}</p>
                  {result.delegations.length > 0 ? (
                    <ul>
                      {result.delegations.map((item, index) => (
                        <li key={`${item.to_role}-${index}`}>
                          <strong>{item.from_role}</strong> asked <strong>{item.to_role}</strong>
                          . {item.reply}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}

              <div className="gate">
                <h2>Human gate</h2>
                <p className="quiet">
                  Agents prepare. You sign. A payment changes the checking balance. A purchase stays a draft.
                </p>
                <label>
                  Your name
                  <input
                    value={approver}
                    onChange={(event) => setApprover(event.target.value)}
                    placeholder="Not an agent name"
                    autoComplete="name"
                  />
                </label>
                {prepared.payments.length === 0 && prepared.purchases.length === 0 ? (
                  <p className="quiet">Nothing on this ticket is waiting for a signature yet.</p>
                ) : null}
                <div className="signs">
                  {prepared.payments.map((proposal) => (
                    <button
                      key={`${proposal.kind}-${proposal.refId}`}
                      type="button"
                      disabled={busyApproval || runningId !== null}
                      onClick={() => void signPayment(proposal)}
                    >
                      Approve {proposal.kind} {money(proposal.amount)}
                    </button>
                  ))}
                  {prepared.purchases.map((draft) => (
                    <button
                      key={`${draft.vendorId}-${draft.sku}-${draft.size}`}
                      type="button"
                      className="quiet-button"
                      disabled={busyApproval || runningId !== null}
                      onClick={() => void signPurchase(draft)}
                    >
                      Approve purchase {draft.sku} {draft.size} × {draft.qty}
                    </button>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <p>Pick a ticket.</p>
          )}

          {message ? <p className="ok">{message}</p> : null}
          {error ? <p className="bad">{error}</p> : null}
          <button type="button" className="reset" onClick={() => void freshBooks()}>
            Reset to the original books
          </button>
        </section>
      </main>
    </div>
  )
}
