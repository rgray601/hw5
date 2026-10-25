export const API = "http://localhost:8000"

export type Ticket = {
  found: boolean
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: string
  notes: string | null
  created_at?: string
  open: boolean
  resolved: boolean
}

export type Cash = {
  found: boolean
  name: string
  balance: number
  date: string
}

export type AuditEvent = {
  time: string
  agent: string
  step: string
  ticket_id: number | null
  tool: string | null
  args: string | null
  result: string | null
  reply: string | null
  stopped: string | null
}

export type AgentSummary = {
  agent: string
  said: string
  tools: string[]
}

export type Delegation = {
  from_role: string
  to_role: string
  task: string
  reply: string
}

export type TeamResult = {
  ticket_id: number
  model: string
  boss_reply: string
  delegations: Delegation[]
}

export type PaymentProposal = {
  kind: "invoice" | "rent"
  refId: number
  amount: number
  account: string
}

export type PurchaseDraft = {
  vendorId: number
  sku: string
  size: string
  qty: number
}

async function readError(response: Response): Promise<string> {
  const body = await response.json().catch(() => null)
  const detail = body && typeof body === "object" ? body.detail : null
  if (typeof detail === "string") return detail
  if (detail && typeof detail === "object" && "reason" in detail) {
    const reason = detail.reason
    if (typeof reason === "string") return reason
  }
  return "The desk could not finish that."
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API}${path}`)
  if (!response.ok) throw new Error(await readError(response))
  return response.json() as Promise<T>
}

export function loadTickets(): Promise<{ tickets: Ticket[] }> {
  return getJson("/api/tickets")
}

export function loadCash(): Promise<Cash> {
  return getJson("/api/cash")
}

export function loadEvents(ticketId: number): Promise<{
  events: AuditEvent[]
  agents: AgentSummary[]
}> {
  return getJson(`/api/events?ticket_id=${ticketId}&limit=200`)
}

export async function runTicket(ticketId: number): Promise<TeamResult> {
  const response = await fetch(`${API}/api/tickets/${ticketId}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note: "" }),
  })
  if (!response.ok) throw new Error(await readError(response))
  return response.json() as Promise<TeamResult>
}

export async function approvePayment(
  ticketId: number,
  approvedBy: string,
  proposal: PaymentProposal,
): Promise<{ cash: Cash }> {
  const response = await fetch(`${API}/api/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      approved_by: approvedBy,
      action: "payment",
      ticket_id: ticketId,
      kind: proposal.kind,
      ref_id: proposal.refId,
      amount: proposal.amount,
      account: proposal.account,
    }),
  })
  if (!response.ok) throw new Error(await readError(response))
  return response.json() as Promise<{ cash: Cash }>
}

export async function approvePurchase(
  ticketId: number,
  approvedBy: string,
  draft: PurchaseDraft,
): Promise<{ cash: Cash }> {
  const response = await fetch(`${API}/api/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      approved_by: approvedBy,
      action: "purchase",
      ticket_id: ticketId,
      vendor_id: draft.vendorId,
      sku: draft.sku,
      size: draft.size,
      qty: draft.qty,
    }),
  })
  if (!response.ok) throw new Error(await readError(response))
  return response.json() as Promise<{ cash: Cash }>
}

export async function resetShop(): Promise<void> {
  const response = await fetch(`${API}/api/reset`, { method: "POST" })
  if (!response.ok) throw new Error(await readError(response))
}

const paymentPattern =
  /\[payment proposal\] kind=(invoice|rent) ref_id=(\d+) amount=([\d.]+) account=(\S+)/g

const purchasePattern =
  /\[purchase order draft\] vendor_id=(\d+) .+? sku=(\S+) size=(\S+) qty=(\d+)/g

export function proposalsIn(notes: string | null): {
  payments: PaymentProposal[]
  purchases: PurchaseDraft[]
} {
  const text = notes ?? ""
  const payments: PaymentProposal[] = []
  const seenPay = new Set<string>()
  for (const match of text.matchAll(paymentPattern)) {
    const kind = match[1] === "rent" ? "rent" : "invoice"
    const proposal = {
      kind,
      refId: Number(match[2]),
      amount: Number(match[3]),
      account: match[4],
    } as PaymentProposal
    const key = `${proposal.kind}:${proposal.refId}:${proposal.amount}`
    if (seenPay.has(key)) continue
    seenPay.add(key)
    payments.push(proposal)
  }
  const purchases: PurchaseDraft[] = []
  const seenBuy = new Set<string>()
  for (const match of text.matchAll(purchasePattern)) {
    const draft = {
      vendorId: Number(match[1]),
      sku: match[2],
      size: match[3],
      qty: Number(match[4]),
    }
    const key = `${draft.vendorId}:${draft.sku}:${draft.size}:${draft.qty}`
    if (seenBuy.has(key)) continue
    seenBuy.add(key)
    purchases.push(draft)
  }
  return { payments, purchases }
}
