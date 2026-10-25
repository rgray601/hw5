# Design

The desk is the Inventing Room from the last Campus Customs candy factory, turned into a place where a person watches five agents work a ticket. Same palette as that shop: Yale blue, night purple, gold, cream, chocolate, candy pink, and mint. Abril Fatface for the titles, Source Sans 3 for the work.

The page is one desk, not a set of forms. A chocolate-river stripe sits under a purple header. Checking is a gold bar on the right, the number large enough to notice when it drops. After an approved payment the bar dips and the caption says cash went out. The figure comes from `GET /api/cash`.

The three tickets are golden tickets down the left. A gold edge means the ticket is still on the desk. A green edge and a Resolved chip mean the team closed it. Pink means that ticket is on the floor right now. Picking one opens it on the right: who asked, the SKU or the lease, and the note already on the board.

The five agents sit in a row and do not share a color. Boss is purple. Inventory wears stockroom stripes. Accounting is the gold till. Facilities is the river green. Customer Service is candy pink. While an agent has started and not finished, that card gets a pink outline and the line "Working this ticket." When the run writes a final reply, that text replaces the waiting line, and the tools they called sit as dark pills on the card. A short tape under the row lists the latest tool calls and handoffs so the floor is visible before the run returns. The board polls `GET /api/events` while `POST /api/tickets/{id}/run` is still going.

When the run finishes, the ticket is read again. If its status is resolved, the golden ticket turns green and the summary is headed Resolved. If the team left it waiting on a person, the chip says Needs a person and the summary is headed Run finished, with the Boss's reply and each handoff.

The human gate is under that. The name has to be a person, not an agent. Buttons appear only for payment proposals and purchase drafts already written on the ticket. Approving a payment calls `POST /api/approve` and the checking number updates from the response. Approving a purchase signs the draft and says the balance did not move. A reset control puts the original books back when a fresh run is needed.

The calls go to `http://localhost:8000`. The backend allows the Vite origin `http://localhost:5173`.
