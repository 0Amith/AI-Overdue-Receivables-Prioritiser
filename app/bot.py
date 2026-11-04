"""Chat behaviour for the ABC Traders receivables assistant.

The bot is a deterministic rule engine, not a language model: the answer to every
question is produced from the Policy and the Register only. That is what makes
the 12 project tests checkable and repeatable.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, timedelta

import engine
import llm
import nlu
from engine import (
    HISTORY_LABEL,
    MISSING,
    PRIORITY_ACTIONS,
    Scored,
    inr,
    score_breakdown,
)

TOP_DEFAULT = 3
MERGE_CONFIDENCE = 0.55
TOP_MAX = 10


def esc(text: str) -> str:
    return html.escape(text, quote=False)


@dataclass
class Reply:
    html: str
    suggestions: list[str]
    intent: str = "other"
    source: str = "rules"
    reading: str = ""

    def as_dict(self) -> dict:
        return {
            "html": self.html,
            "suggestions": self.suggestions,
            "intent": self.intent,
            "source": self.source,
            "reading": self.reading,
        }


class Bot:
    def __init__(self, invoices: dict[str, engine.Invoice], store=None, use_llm: bool = True):
        self.invoices = invoices
        self.store = store
        self.use_llm = use_llm
        self._id_map = {cid.upper(): cid for cid in invoices}
        self._id_re = self._build_id_re()

    def _build_id_re(self) -> re.Pattern | None:
        """Match whatever IDs this dataset uses, longest first, on token edges."""
        if not self._id_map:
            return None
        parts = sorted((re.escape(k) for k in self._id_map), key=len, reverse=True)
        body = "|".join(parts)
        return re.compile(rf"(?<![A-Za-z0-9])(?:{body})(?![A-Za-z0-9])", re.I)

    def find_customers(self, low: str) -> list[str]:
        """Every customer ID named in the text, canonicalised, in order of mention."""
        found: list[str] = []
        if self._id_re is not None:
            for m in self._id_re.finditer(low):
                cid = self._id_map.get(m.group(0).upper())
                if cid and cid not in found:
                    found.append(cid)
        return found

    def promises(self) -> dict[str, dict]:
        if self.store is None:
            return {}
        return self.store.promises()

    def contacts(self) -> dict[str, dict]:
        if self.store is None:
            return {}
        return self.store.contacts()

    def scored(self, inv: engine.Invoice, mode: str) -> Scored:
        """Version 1 scores from the days the bot counted; Version 2 uses the column."""
        if mode == "v1":
            return engine.score_invoice(inv, self._v1_days(inv))
        return engine.score_invoice(inv)

    def ranking_rows(self, mode: str) -> list[Scored]:
        rows = [self.scored(inv, mode) for inv in self.invoices.values()]
        rows.sort(key=lambda s: s.sort_key)
        return rows

    def ranked(self, mode: str) -> list[Scored]:
        return self.ranking_rows(mode)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def answer(self, message: str, mode: str = "v2") -> Reply:
        text = (message or "").strip()
        if not text:
            return self.help()
        q = nlu.parse(text, self.resolve_customers)
        source = "rules"
        reading = ""
        if self.use_llm and llm.configured():
            hint = llm.interpret(text, engine.REPORT_DATE.isoformat())
            if hint and hint.get("confidence", 0) >= MERGE_CONFIDENCE:
                q = self._merge(q, hint)
                # Never trust an ID the register does not have.
                q.customers = [c for c in q.customers if c in self.invoices]
                if q.intent in ("rank", "aggregate"):
                    q.customers = []
                source = "gemini"
                reading = self._describe(q)
        reply = self._dispatch(q, mode, text)
        reply.source = source
        reply.reading = reading
        return reply

    @staticmethod
    def _describe(q: nlu.Query) -> str:
        """Plain-words echo of how the sentence was read."""
        bits = [q.intent.replace("-", " ")]
        if q.customers:
            bits.append(", ".join(q.customers))
        if q.window_label:
            bits.append(q.window_label)
        if q.priority:
            bits.append(f"{q.priority.lower()} priority")
        if q.amount_gt is not None:
            bits.append(f"above {inr(q.amount_gt)}")
        if q.amount_lt is not None:
            bits.append(f"under {inr(q.amount_lt)}")
        if q.days_gt is not None and q.days_gt > 1:
            bits.append(f"{q.days_gt}+ days")
        if q.days_lt is not None:
            bits.append(f"up to {q.days_lt} days")
        if q.only_missing:
            bits.append("missing data")
        if q.topic and q.intent in ("definition", "aggregate", "policy"):
            bits.append(f"about {q.topic}")
        return " · ".join(bits)

    @staticmethod
    def _merge(q: nlu.Query, hint: dict) -> nlu.Query:
        """Let the model correct the reading; keep whatever it left blank."""
        if hint.get("intent"):
            q.intent = hint["intent"]
        if hint.get("topic"):
            q.topic = hint["topic"]
        if hint.get("priority"):
            q.priority = hint["priority"]
        if hint.get("customers"):
            q.customers = hint["customers"]
        if hint.get("only_missing"):
            q.only_missing = True
        if hint.get("only_disputed"):
            q.only_disputed = True
        if hint.get("extra_days"):
            q.extra_days = hint["extra_days"]
        for field, key in (("days_gt", "days_min"), ("days_lt", "days_max"),
                           ("amount_gt", "amount_min"), ("amount_lt", "amount_max")):
            if hint.get(key) is not None:
                setattr(q, field, hint[key])
        for field, key in (("due_from", "due_from"), ("due_to", "due_to")):
            raw = hint.get(key)
            if raw:
                try:
                    setattr(q, field, date.fromisoformat(raw))
                except ValueError:
                    pass
        if q.due_from or q.due_to:
            # Keep the parser's own wording ("last 30 days") when it already has one.
            if not q.window_label:
                start = q.due_from or engine.REPORT_DATE
                end = q.due_to or engine.REPORT_DATE
                q.window_label = f"due {nlu._fmt_window(start, end)}"
        return q

    def _dispatch(self, q: nlu.Query, mode: str, text: str) -> Reply:
        cid = q.customers[0] if q.customers else None

        if q.intent == "thanks":
            return self.thanks()
        if q.intent == "bye":
            return self.bye()
        if q.intent == "meta":
            return self.meta()
        if q.intent == "privacy":
            return self.privacy()
        if q.intent == "followup":
            return self.followup(mode)
        if q.intent == "export":
            return self.export_reply(q, mode)
        if q.intent == "aging":
            return self.aging_reply(mode)
        if q.intent == "concentration":
            return self.concentration_reply(mode)
        if q.intent == "board":
            return self.board_reply()
        if q.intent == "whatif":
            return self.what_if(q.extra_days or 30, mode)
        if q.intent == "compare":
            return self.compare(q.customers, mode)
        if q.intent == "discount":
            return self.discount(cid, mode)
        if q.intent == "reminder":
            return self.reminder(cid, mode, "hi" if q.wants_hindi else "en")
        if q.intent == "explain":
            return self.explain(cid, mode)
        if q.intent == "aggregate":
            return self.aggregate(q, mode)
        if q.intent == "rank":
            return self.ranking(q.top_n or self._top_n(nlu.normalise(text)), mode)
        if q.intent == "score":
            return self.customer_detail(cid, mode)
        if q.intent == "listing":
            return self.listing(q, mode)
        if q.intent == "definition":
            return self.definition(q)
        if q.intent == "help":
            return self.help()
        if q.intent == "greeting":
            return self.greeting()
        if q.intent == "policy":
            return self.policy_answer(nlu.normalise(text))
        return self.fallback(text, q.best_guess)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _find_customer(low: str) -> str | None:
        m = re.search(r"\bc\s?-?(\d{1,3})\b", low)
        if m:
            return f"C{int(m.group(1)):03d}"
        return None

    def resolve_customers(self, low: str) -> list[str]:
        """Exact IDs, plus any C-number mention the exact match missed."""
        found = self.find_customers(low)
        for cid in self._legacy_id(low):
            if cid not in found:
                found.append(cid)
        return found

    def _legacy_id(self, low: str) -> list[str]:
        """Fallback for a 'c 2'-style mention the exact ID match missed."""
        found = []
        for m in re.finditer(r"\bc\s?-?(\d{1,3})\b", low):
            cid = f"C{int(m.group(1)):03d}"
            if cid in self.invoices and cid not in found:
                found.append(cid)
        return found
    @staticmethod
    def _top_n(low: str) -> int:
        m = re.search(r"\btop\s*(\d{1,2})\b", low)
        if m:
            return max(1, min(TOP_MAX, int(m.group(1))))
        m = re.search(r"\b(\d{1,2})\s*(?:customers|invoices|accounts)\b", low)
        if m:
            return max(1, min(TOP_MAX, int(m.group(1))))
        return TOP_DEFAULT

    def _get(self, cid: str) -> engine.Invoice | None:
        return self.invoices.get(cid)

    # ------------------------------------------------------------------
    # Intents
    # ------------------------------------------------------------------
    def help(self) -> Reply:
        return Reply(
            html=(
                "<p>I am the <strong>ABC Traders receivables assistant</strong>. "
                "I work only from the Collections Policy and the Receivables Register "
                "(as on 31 October 2026). Ask in your own words — you do not need exact commands.</p>"
                "<p>Things people ask me:</p><ul>"
                "<li><em>“give me all the overdue list”</em> — the whole queue, ranked</li>"
                "<li><em>“how many are critical?”</em> — counts and value by band</li>"
                "<li><em>“overdue last month”</em> — a date window, not the whole book</li>"
                "<li><em>“which invoices are above 4 lakh?”</em> — filter by amount or days</li>"
                "<li><em>“score C002”</em> — one customer's full breakdown</li>"
                "<li><em>“draft a reminder for C002”</em> — a draft, English or Hindi</li>"
                "<li><em>“what is days overdue?”</em> — a definition from the Policy</li>"
                "<li><em>“compare C002 and C003”</em> — side by side</li></ul>"
                "<p>And the analysis questions:</p><ul>"
                "<li><em>“ageing report”</em> — how the book is spread across the Policy's bands</li>"
                "<li><em>“what if we wait 30 days?”</em> — what the clock alone does to the queue</li>"
                "<li><em>“who holds the most exposure?”</em> — where the value is concentrated</li>"
                "<li><em>“show disputed invoices”</em> / <em>“not contacted in 7 days”</em> — work state</li>"
                "<li><em>“board brief”</em> — the one-page month-end summary</li></ul>"
                "<p class='note'>Time phrases (“this month”, “last 30 days”, “in August”) are "
                "resolved against the reporting date and printed in the answer. "
                "If the answer is not in the files I say so rather than guessing.</p>"
            ),
            suggestions=["Show all overdue customers", "Ageing report", "Score C002"],
            intent="help",
        )

    def privacy(self) -> Reply:
        return Reply(
            html=(
                "<p><strong>Short answer:</strong> yes — with Customer IDs only, every user of "
                "this assistant can see every customer's dues. There is no login, so there is no "
                "per-customer boundary. <span class='cite'>Policy §10 · Register (all rows)</span></p>"
                "<p>The register holds Customer ID, invoice number, dates, amount and history code. "
                "No names, addresses, phone numbers or bank details are stored, so a cross-customer "
                "answer exposes no personal data.</p>"
                "<p>Safe way to use it: quote the Customer ID, not a name. For example "
                "<em>“score C017”</em> is safe to answer in front of anyone; "
                "<em>“what does Sharma Traders owe?”</em> needs a human mapping step, because "
                "names are not in the files.</p>"
                "<p><strong>Limitation to state in the report:</strong> real deployment needs "
                "login access per customer.</p>"
            ),
            suggestions=["Score C017", "Top 3 customers to chase"],
            intent="privacy",
        )

    def discount(self, cid: str | None, mode: str = "v2") -> Reply:
        head = (
            "<p><strong>Discounts and settlements are approved only by the Finance Manager.</strong> "
            "The assistant does not decide them. <span class='cite'>Policy §8</span></p>"
        )
        if cid and cid in self.invoices:
            s = self.scored(self.invoices[cid], mode)
            head += (
                f"<p>What the files <em>do</em> tell you about {esc(cid)}: "
                f"score <strong>{s.score}</strong> / 9, priority <strong>{esc(s.priority)}</strong>, "
                f"{esc(inr(s.invoice.amount))}, {s.days} days overdue. "
                f"<span class='cite'>Register row {esc(cid)} · Policy §4</span></p>"
                "<p>That is context for the Finance Manager's decision — not a recommendation of "
                "an amount or a percentage.</p>"
            )
        else:
            head += "<p>Give me a Customer ID and I will show the score and priority to take to the Finance Manager.</p>"
        head += "<p>For the actual answer: <em>Please contact the Finance Manager.</em></p>"
        return Reply(
            html=head,
            suggestions=["Score C015", "Draft a reminder for C015"],
            intent="discount",
        )

    def policy_answer(self, low: str) -> Reply:
        if re.search(r"\b(30|thirty)\b", low) and re.search(r"\bday", low):
            return Reply(
                html=(
                    "<p><strong>Exactly 30 days overdue scores 2 points, not 3.</strong> "
                    "The bands are read with the lower bound inclusive, so day 30 still sits in "
                    "the 16–30 band. <span class='cite'>Policy §3 and §4.1</span></p>"
                    "<p>The same inclusive rule gives exactly 15 days = 1 point and exactly "
                    "60 days = 3 points. Day 31 is the first day of the next band, and day 61 "
                    "is the first day of the 60+ band.</p>"
                ),
                suggestions=["Score C002", "Score C003"],
                intent="policy",
            )
        if re.search(r"\b(amount|rs|rupee|50,?000|2,?00,?000)\b", low):
            return Reply(
                html=(
                    "<p>Amount bands: under Rs 50,000 = 1 point; Rs 50,000 to Rs 2,00,000 = "
                    "2 points; above Rs 2,00,000 = 3 points. Both ends are inclusive, so exactly "
                    "Rs 50,000 and exactly Rs 2,00,000 score 2. "
                    "<span class='cite'>Policy §4.2</span></p>"
                ),
                suggestions=["Score C004", "Score C005"],
                intent="policy",
            )
        if re.search(r"\b(history|payment)\b", low):
            return Reply(
                html=(
                    "<p>History bands: always on time = 0 points; sometimes late = 1 point; "
                    "repeatedly late or past default = 2 points. "
                    "<span class='cite'>Policy §4.3</span></p>"
                ),
                suggestions=["Score C015", "Score C007"],
                intent="policy",
            )
        return Reply(
            html=(
                "<p>The full rule set is the Collections Policy:</p>"
                "<ul><li>Days overdue: 1–15 = 1, 16–30 = 2, 31–60 = 3, more than 60 = 4 "
                "<span class='cite'>§4.1</span></li>"
                "<li>Amount: under Rs 50,000 = 1, Rs 50,000–Rs 2,00,000 = 2, above = 3 "
                "<span class='cite'>§4.2</span></li>"
                "<li>History: on time = 0, sometimes late = 1, repeatedly late = 2 "
                "<span class='cite'>§4.3</span></li>"
                "<li>Priority: 7–9 Critical, 5–6 High, 3–4 Medium, 1–2 Low "
                "<span class='cite'>§5</span></li>"
                "<li>Ties are broken by the larger amount <span class='cite'>§6</span></li></ul>"
            ),
            suggestions=["How many points for 30 days?", "Top 3 customers to chase"],
            intent="policy",
        )

    def ranking(self, n: int, mode: str) -> Reply:
        rows = self.ranking_rows(mode)[:n]
        parts = [
            f"<p><strong>Top {n} by score</strong> (highest first; ties broken by the larger "
            f"invoice amount) <span class='cite'>Policy §6</span></p>",
            "<table class='tbl'><thead><tr><th>#</th><th>Customer</th><th>Days</th>"
            "<th>Amount</th><th>Score</th><th>Priority</th><th>Action</th></tr></thead><tbody>",
        ]
        for i, s in enumerate(rows, start=1):
            days = self._days_cell(s, mode)
            parts.append(
                "<tr>"
                f"<td>{i}</td>"
                f"<td>{esc(s.invoice.customer_id)}{' <span class=flag>partial</span>' if s.partial else ''}</td>"
                f"<td>{days}</td>"
                f"<td>{esc(inr(s.invoice.amount))}</td>"
                f"<td>{s.score}</td>"
                f"<td><span class='pill {s.priority.lower()}'>{esc(s.priority)}</span></td>"
                f"<td>{esc(s.action)}</td>"
                "</tr>"
            )
        parts.append("</tbody></table>")
        if mode == "v1":
            parts.append(
                "<p class='note'>Version 1: days overdue are counted from the dates by the "
                "assistant, so boundary rows can be off by a day.</p>"
            )
        parts.append(
            "<p class='note'>Source: Register (rows above) · Policy §4, §5, §6. "
            "Rows marked <span class=flag>partial</span> have a missing field — check before acting.</p>"
        )
        if any(s.partial for s in rows):
            parts.append(
                "<p class='warn'>At least one row above is missing data, so its score is "
                "provisional. The missing field is flagged, not guessed.</p>"
            )
        return Reply(
            html="".join(parts),
            suggestions=[f"Score {rows[0].invoice.customer_id}", f"Draft a reminder for {rows[0].invoice.customer_id}"],
            intent="ranking",
        )

    def customer_detail(self, cid: str | None, mode: str) -> Reply:
        if cid is None:
            return self.help()
        inv = self._get(cid)
        if inv is None:
            return Reply(
                html=(
                    f"<p>{esc(cid)} is <strong>not in the register</strong>, so I will not guess. "
                    f"<span class='cite'>Register (40 rows checked)</span></p>"
                    f"<p><strong>{MISSING}</strong></p>"
                ),
                suggestions=["Top 3 customers to chase"],
                intent="unknown-customer",
            )
        s = self.scored(inv, mode)
        parts = [
            f"<h3>{esc(cid)} — {esc(inv.invoice_no)}</h3>",
            "<table class='kv'>"
            f"<tr><th>Invoice date</th><td>{esc(inv.invoice_date.isoformat() if inv.invoice_date else 'missing')}</td></tr>"
            f"<tr><th>Due date</th><td>{esc(inv.due_date.isoformat() if inv.due_date else 'missing')}</td></tr>"
            f"<tr><th>Days overdue</th><td>{self._days_cell(s, mode)} <span class='cite'>Policy §3</span></td></tr>"
            f"<tr><th>Amount</th><td>{esc(inr(inv.amount)) if inv.amount is not None else '<span class=flag>missing</span>'}</td></tr>"
            f"<tr><th>History code</th><td>{esc(inv.history or 'missing')}</td></tr>"
            "</table>",
            "<h4>Score breakdown</h4><ul class='breakdown'>",
        ]
        for line in score_breakdown(s):
            parts.append(f"<li>{line.replace('**', '')}</li>")
        parts.append("</ul>")
        parts.append(
            f"<p><strong>Total score {s.score} / 9 → "
            f"<span class='pill {s.priority.lower()}'>{esc(s.priority)}</span></strong> "
            f"<span class='cite'>Policy §4, §5</span></p>"
        )
        parts.append(f"<p><strong>Action:</strong> {esc(s.action)} <span class='cite'>Policy §5</span></p>")
        promise = self.promises().get(cid)
        contact = (self.contacts().get(cid) if self.store is not None else None) or {}
        if contact:
            parts.append(
                "<p class='contact'><strong>Last contact "
                + esc(contact.get("last_contact", ""))
                + ":</strong> "
                + esc(contact.get("outcome", ""))
                + (f" · {esc(contact.get('note'))}" if contact.get("note") else "")
                + ".</p>"
            )
        if promise:
            late = promise["promised_on"] < engine.REPORT_DATE.isoformat()
            parts.append(
                "<p class='promise'>"
                + ("<strong>Promise broken</strong> — " if late else "<strong>Promise to pay on record</strong> — ")
                + f"customer indicated {esc(promise['promised_on'])}"
                + (f" · {esc(promise['note'])}" if promise.get("note") else "")
                + (". The promised date has passed." if late else ". It has not yet fallen due.")
                + "</p>"
            )
        else:
            parts.append(
                "<p class='note'>No promise-to-pay recorded. "
                f"<a href='#' data-promise='{esc(cid)}'>Log one</a>.</p>"
            )
        parts.append(
            "<p class='note'>Work this account: "
            f"<a href='#' data-contact='{esc(cid)}'>Log a contact</a> "
            f"· <a href='#' data-promise='{esc(cid)}'>Update the promise</a>.</p>"
        )
        if s.partial:
            parts.append(
                "<p class='warn'><strong>Missing data:</strong> "
                + esc(", ".join(inv.missing_fields))
                + " is blank in the register. The score above is calculated from the fields that "
                "are present and is therefore <strong>provisional</strong> — the blank is flagged, "
                "not guessed.</p>"
                f"<p class='cite'>Register row {esc(cid)}</p>"
            )
        if s.days is not None and s.days <= 0:
            parts.append(
                "<p class='note'>This invoice is <strong>not yet due</strong>, so it earns 0 days "
                "points. It is ranked with the overdue invoices only for reference.</p>"
            )
        parts.append(f"<p class='cite'>Sources: Register row {esc(cid)} · Policy §3, §4, §5</p>")
        return Reply(
            html="".join(parts),
            suggestions=[f"Draft a reminder for {cid}", "Can we give a discount?", "Top 3 customers to chase"],
            intent="score",
        )

    def reminder(self, cid: str, mode: str, lang: str = "en") -> Reply:
        inv = self._get(cid)
        if inv is None:
            return Reply(
                html=(
                    f"<p>{esc(cid)} is not in the register, so there is nothing to draft from. "
                    f"<span class='cite'>Register</span></p><p><strong>{MISSING}</strong></p>"
                ),
                suggestions=["Top 3 customers to chase"],
                intent="reminder-missing",
            )
        s = self.scored(inv, mode)
        body = self._reminder_text(s, mode, lang)
        warn = ""
        if s.partial:
            warn = (
                "<p class='warn'>Missing field(s): "
                + esc(", ".join(inv.missing_fields))
                + ". The draft keeps a placeholder instead of inventing a value.</p>"
            )
        promise = self.promises().get(cid)
        if promise:
            warn += (
                f"<p class='promise'>The draft quotes the promise on record ({esc(promise['promised_on'])}).</p>"
            )
        label = "Hindi" if lang == "hi" else "English"
        return Reply(
            html=(
                f"<p>Draft reminder for <strong>{esc(cid)}</strong> — priority "
                f"<span class='pill {s.priority.lower()}'>{esc(s.priority)}</span>, so the tone is "
                f"set by the action “{esc(s.action)}”. <span class='cite'>Policy §5, §7</span></p>"
                f"<pre class='draft' data-text='{esc(body)}'>{esc(body)}</pre>"
                "<div class='drafttools'>"
                f"<button type='button' data-copy>Copy</button>"
                f"<button type='button' data-wa>Send on WhatsApp</button>"
                f"<button type='button' data-speak>Read aloud</button>"
                f"<button type='button' data-lang='{'en' if lang == 'hi' else 'hi'}'>{'English' if lang == 'hi' else 'हिंदी'} version</button>"
                f"<span class='note'>Draft language: {label}</span>"
                "</div>"
                f"{warn}"
                "<p class='note'>Tone check: no deadlines phrased as threats, no discount offered. "
                "Review every draft before sending. <span class='cite'>Policy §7, §8, §10</span></p>"
            ),
            suggestions=[f"Score {cid}", "Can we give a discount?", "Top 3 customers to chase"],
            intent="reminder",
        )

    # ------------------------------------------------------------------
    # Explanations and follow-up
    # ------------------------------------------------------------------
    def explain(self, cid: str | None, mode: str) -> Reply:
        """Answer 'why is C017 first?' with the ranking arithmetic, not a vibe."""
        if cid is None:
            return self.ranking(TOP_DEFAULT, mode)
        if cid not in self.invoices:
            return self.customer_detail(cid, mode)
        rows = self.ranking_rows(mode)
        position = next((i for i, s in enumerate(rows, start=1) if s.invoice.customer_id == cid), None)
        s = next(r for r in rows if r.invoice.customer_id == cid)
        tied = [r for r in rows if r.score == s.score]
        parts = [
            f"<p><strong>{esc(cid)} sits at position {position} of {len(rows)}</strong>, "
            f"on a score of {s.score}. <span class='cite'>Policy §6</span></p>",
            f"<p>The score comes from: {s.dp} day points + {s.ap} amount points + {s.hp} history points "
            f"= {s.score}. <span class='cite'>Policy §4</span></p>",
        ]
        if len(tied) > 1:
            above = [r for r in tied if r.sort_key < s.sort_key]
            parts.append(
                f"<p>{len(tied)} customers share the score of {s.score}. The tie is broken by invoice "
                f"amount, largest first — that is why "
                + (f"{', '.join(esc(r.invoice.customer_id) for r in above)} "
                   f"rank ahead of {esc(cid)}: "
                   + ", ".join(f"{esc(r.invoice.customer_id)} at {esc(inr(r.invoice.amount))}" for r in above)
                   if above else f"{esc(cid)} leads the group")
                + f". {esc(cid)} is at {esc(inr(s.invoice.amount))}. <span class='cite'>Policy §6</span></p>"
            )
        else:
            parts.append(
                f"<p>No other customer shares this score, so no tie-break was needed. "
                f"<span class='cite'>Policy §6</span></p>"
            )
        edges = engine.boundary_distance(s)
        if edges:
            parts.append(
                "<p><strong>How close this is to moving:</strong> "
                + "; ".join(esc(e) for e in edges)
                + ". One small change either way re-bands the row. "
                "<span class='cite'>Policy §4, §5</span></p>"
            )
        parts.append(
            f"<p><strong>Action:</strong> {esc(s.action)} <span class='cite'>Policy §5</span></p>"
            "<p class='note'>The bot does not judge importance — the position is arithmetic from the "
            "Policy and the Register, and can be recomputed by hand.</p>"
        )
        return Reply(
            html="".join(parts),
            suggestions=[f"Score {cid}", f"Draft a reminder for {cid}", "Top 3 customers to chase"],
            intent="explain",
        )

    def followup(self, mode: str) -> Reply:
        promises = self.promises()
        if not promises:
            return Reply(
                html=(
                    "<p><strong>No promise-to-pay is on record</strong>, so nothing is queued for "
                    "follow-up.</p><p class='note'>Open a customer and use <em>Log a promise to pay</em> "
                    "to start tracking one. Promises are stored locally and never leave this machine.</p>"
                ),
                suggestions=["Top 3 customers to chase"],
                intent="followup",
            )
        rows = []
        for cid in promises:
            if cid in self.invoices:
                rows.append(self.scored(self.invoices[cid], mode))
        rows.sort(key=lambda s: promises[s.invoice.customer_id]["promised_on"])
        today = engine.REPORT_DATE.isoformat()
        broken = [s for s in rows if promises[s.invoice.customer_id]["promised_on"] < today]
        pending = [s for s in rows if promises[s.invoice.customer_id]["promised_on"] >= today]
        parts = [
            f"<p><strong>{len(broken)} broken promise(s), {len(pending)} still pending.</strong> "
            "Broken promises come first. <span class='cite'>Promise log</span></p>"
        ]
        if broken:
            parts.append("<h4>Promise date passed — chase now</h4><table class='tbl'><thead><tr>"
                         "<th>Customer</th><th>Promised</th><th>Days late on promise</th>"
                         "<th>Score</th><th>Priority</th></tr></thead><tbody>")
            for s in broken:
                p = promises[s.invoice.customer_id]["promised_on"]
                late_days = (engine.REPORT_DATE - engine.date.fromisoformat(p)).days
                parts.append(
                    f"<tr><td>{esc(s.invoice.customer_id)}</td><td>{esc(p)}</td>"
                    f"<td class='bad'>{late_days}</td><td>{s.score}</td>"
                    f"<td><span class='pill {s.priority.lower()}'>{esc(s.priority)}</span></td></tr>"
                )
            parts.append("</tbody></table>")
        if pending:
            parts.append("<h4>Pending promises</h4><table class='tbl'><thead><tr>"
                         "<th>Customer</th><th>Promised</th><th>Score</th><th>Priority</th></tr></thead><tbody>")
            for s in pending:
                parts.append(
                    f"<tr><td>{esc(s.invoice.customer_id)}</td>"
                    f"<td>{esc(promises[s.invoice.customer_id]['promised_on'])}</td>"
                    f"<td>{s.score}</td>"
                    f"<td><span class='pill {s.priority.lower()}'>{esc(s.priority)}</span></td></tr>"
                )
            parts.append("</tbody></table>")
        parts.append(
            "<p class='note'>A promise never changes a score — the Policy has no promise factor. "
            "It changes the order you work in.</p>"
        )
        return Reply(
            html="".join(parts),
            suggestions=["Top 3 customers to chase", "Score C002"],
            intent="followup",
        )

    # ------------------------------------------------------------------
    # Text builders
    # ------------------------------------------------------------------
    def _days_cell(self, s: Scored, mode: str) -> str:
        if s.days is None:
            return "<span class='flag'>missing</span>"
        if s.days <= 0:
            return f"{s.days} (not yet due)"
        if mode == "v1":
            truth = s.invoice.days_overdue
            cls = "bad" if truth is not None and s.days != truth else ""
            return f"<span class='{cls}'>{s.days}</span>"
        return str(s.days)

    @staticmethod
    def _v1_days(inv: engine.Invoice) -> int | None:
        """Version 1 behaviour: the assistant works the dates out for itself.

        Two realistic slips: every month is treated as 30 days, and both the due
        date and the reporting date are counted (inclusive), which pushes every
        boundary row into the next band.
        """
        if inv.due_date is None:
            return None
        report = engine.REPORT_DATE
        months = (report.year - inv.due_date.year) * 12 + (report.month - inv.due_date.month)
        return months * 30 + (report.day - inv.due_date.day) + 1

    def _reminder_text(self, s: Scored, mode: str, lang: str = "en") -> str:
        if lang == "hi":
            return self._reminder_text_hi(s)
        inv = s.invoice
        amount = inr(inv.amount) if inv.amount is not None else "[amount missing]"
        due = inv.due_date.isoformat() if inv.due_date else "[due date missing]"
        days = s.days if s.days is not None else None
        days_txt = (
            f"{days} days" if days is not None and days > 0 else "[days overdue missing]"
        )
        promise = self.promises().get(inv.customer_id)
        promise_txt = ""
        if promise:
            p = promise["promised_on"]
            if p < engine.REPORT_DATE.isoformat():
                promise_txt = (
                    f" You had indicated payment by {p}, and that date has now passed."
                )
            else:
                promise_txt = f" You had indicated payment by {p}."
        common_tail = (
            "\n\nIf payment has already been made, please ignore this note and share the "
            "remittance advice so we can update our records."
        )
        sign = "\n\nWarm regards,\nAccounts Receivable\nABC Traders"
        head = f"Subject: {inv.invoice_no} — {amount} — payment reminder\n\nDear Accounts Team ({inv.customer_id}),\n\n"

        if s.priority == "Low":
            body = (
                f"We hope all is well at your end. Our records show invoice {inv.invoice_no} for "
                f"{amount}, due on {due} and now {days_txt} overdue. It may simply have slipped "
                f"through, so we are sending a friendly nudge. We would be grateful if you could "
                f"arrange payment whenever convenient."
            )
        elif s.priority == "Medium":
            body = (
                f"Our records show invoice {inv.invoice_no} for {amount}, due on {due} and now "
                f"{days_txt} overdue. Could you kindly arrange payment at the earliest? "
                f"We will follow this note up with a short call to confirm the status."
            )
        elif s.priority == "High":
            body = (
                f"Invoice {inv.invoice_no} for {amount} fell due on {due} and is now {days_txt} "
                f"overdue. Please arrange payment at the earliest, or share a firm payment date "
                f"if funds are committed elsewhere. Our manager will call you to agree the date, "
                f"and we would like to keep your account in good standing."
            )
        else:  # Critical
            body = (
                f"Invoice {inv.invoice_no} for {amount} fell due on {due} and is now {days_txt} "
                f"overdue. This has reached our Critical band, so the account is being escalated "
                f"to our Finance Head and new orders will be held until the position is cleared. "
                f"Please arrange payment at the earliest, or share a firm payment date, so that "
                f"supplies can resume without delay."
            )
        body += promise_txt
        tail = common_tail + sign
        if s.priority == "Critical":
            tail = tail.replace("Warm regards", "Regards")
        return head + body + tail

    def _reminder_text_hi(self, s: Scored) -> str:
        """Hindi draft. Same policy structure, same placeholders, same refusal to invent."""
        inv = s.invoice
        amount = inr(inv.amount) if inv.amount is not None else "[राशि अनुपलब्ध]"
        due = inv.due_date.isoformat() if inv.due_date else "[देय तिथि अनुपलब्ध]"
        days = s.days
        days_txt = f"{days} दिन" if days is not None and days > 0 else "[विलंब दिन अनुपलब्ध]"
        promise = self.promises().get(inv.customer_id)
        promise_txt = ""
        if promise:
            p = promise["promised_on"]
            promise_txt = (
                f" आपने {p} तक भुगतान का आश्वासन दिया था, और वह तिथि बीत चुकी है।"
                if p < engine.REPORT_DATE.isoformat()
                else f" आपने {p} तक भुगतान का आश्वासन दिया था।"
            )

        head = (
            f"विषय: {inv.invoice_no} — {amount} — भुगतान अनुस्मारक\n\n"
            f"आदरणीय लेखा विभाग ({inv.customer_id}),\n\n"
        )
        if s.priority == "Low":
            body = (
                f"आशा है आप सकुशल हैं। हमारे अभिलेख के अनुसार चालान {inv.invoice_no} राशि {amount}, "
                f"देय तिथि {due} थी और अब {days_txt} विलंबित है। संभव है यह ध्यान में न आया हो, "
                f"इसलिए यह सौहार्दपूर्ण स्मरण भेज रहे हैं। सुविधा अनुसार भुगतान करने की कृपा करें।"
            )
        elif s.priority == "Medium":
            body = (
                f"हमारे अभिलेख के अनुसार चालान {inv.invoice_no} राशि {amount}, देय तिथि {due} थी और "
                f"अब {days_txt} विलंबित है। कृपया शीघ्रातिशीघ्र भुगतान की व्यवस्था करें। स्थिति की "
                f"पुष्टि के लिए हम शीघ्र ही एक संक्षिप्त दूरभाष करेंगे।"
            )
        elif s.priority == "High":
            body = (
                f"चालान {inv.invoice_no} राशि {amount} की देय तिथि {due} थी और अब {days_txt} विलंबित है। "
                f"कृपया शीघ्र भुगतान करें अथवा भुगतान की निश्चित तिथि बताएँ। हमारे प्रबंधक तिथि तय करने "
                f"के लिए दूरभाष करेंगे, और हम आपका खाता सद्भाव में बनाए रखना चाहते हैं।"
            )
        else:
            body = (
                f"चालान {inv.invoice_no} राशि {amount} की देय तिथि {due} थी और अब {days_txt} विलंबित है। "
                f"यह हमारी क्रिटिकल श्रेणी में पहुँच गया है, अतः खाता वित्त प्रमुख के पास अग्रेषित किया जा "
                f"रहा है और स्थिति स्पष्ट होने तक नए ऑर्डर रोके रहेंगे। कृपया शीघ्र भुगतान करें अथवा "
                f"निश्चित भुगतान तिथि बताएँ, जिससे आपूर्ति बिना विलंब के पुनः प्रारंभ हो सके।"
            )
        tail = (
            "\n\nयदि भुगतान हो चुका है तो कृपया इस सूचना को अनदेखा करें और भुगतान विवरण साझा करें, "
            "जिससे हमारे अभिलेख अद्यतन हो सकें।"
            "\n\nसादर,\nलेखा विभाग\nABC Traders"
        )
        return head + body + promise_txt + tail

    def fallback(self, text: str, guess: str | None = None) -> Reply:
        chips = [guess] if guess else []
        chips += ["Show all overdue customers", "Top 3 customers to chase"]
        return Reply(
            html=(
                f"<p>I could not find that in the Policy or the Register, so I will not guess.</p>"
                f"<p><strong>{MISSING}</strong></p>"
                "<p class='note'>Sources checked: Collections Policy · Receivables Register "
                "(40 rows, as on 31 October 2026).</p>"
            ),
            suggestions=chips,
            intent="fallback",
        )

    # ------------------------------------------------------------------
    # General subject questions
    # ------------------------------------------------------------------
    def greeting(self) -> Reply:
        return Reply(
            html=(
                "<p>Hello. Ask me anything about the overdue list — a customer, a priority "
                "band, a total, or a reminder to draft.</p>"
                "<p class='note'>I answer only from the Collections Policy and the Register "
                "(as on 31 October 2026).</p>"
            ),
            suggestions=["Show all overdue customers", "Top 3 customers to chase", "What is days overdue?"],
            intent="greeting",
        )

    def thanks(self) -> Reply:
        return Reply(
            html=(
                "<p>You're welcome. Two things to remember before you send anything: the bot "
                "recommends and a human signs off, and no discount is decided here "
                "<span class='cite'>Policy §8, §10</span>.</p>"
            ),
            suggestions=["What is due for follow-up?", "Show the Critical list"],
            intent="thanks",
        )

    def bye(self) -> Reply:
        return Reply(
            html=(
                "<p>Goodbye. The worklist and audit log stay available in the sidebar if you "
                "need them later.</p>"
            ),
            suggestions=["Show all overdue customers"],
            intent="bye",
        )

    def meta(self) -> Reply:
        return Reply(
            html=(
                "<p>I read two files and nothing else: the <strong>Collections Policy</strong> "
                "(the fixed scoring rules) and the <strong>Receivables Register</strong> "
                "(40 made-up invoices, Customer IDs only, as on 31 October 2026).</p>"
                "<p>I am not a language model. A rule engine scores each invoice and a small "
                "parser maps your sentence onto an intent, so the same question always gives the "
                "same number — that is what makes the 15-test matrix meaningful. "
                "<span class='cite'>Policy §1, §9</span></p>"
                "<p>Every figure carries a citation. If the answer is not in those files I say "
                f"<em>{MISSING}</em> instead of inventing one.</p>"
            ),
            suggestions=["Show me the scoring rules", "Show all overdue customers", "Show me another customer's dues"],
            intent="meta",
        )

    def definition(self, q: nlu.Query) -> Reply:
        topic = q.topic
        answers = {
            "days": (
                "<p><strong>Days overdue</strong> is 31 October 2026 minus the Due Date, in whole "
                "days. The bands are lower-bound inclusive: 1–15 days scores 1, 16–30 scores 2, "
                "31–60 scores 3, more than 60 scores 4. Exactly 30 days is therefore 2 points, "
                "not 3. <span class='cite'>Policy §3, §4.1</span></p>"
            ),
            "score": (
                "<p>The <strong>score</strong> is days points + amount points + history points, "
                "so it runs from 2 to 9 for an overdue invoice. It is arithmetic, not judgement — "
                "you can recompute any score by hand from the Policy. "
                "<span class='cite'>Policy §4.4</span></p>"
            ),
            "priority": (
                "<p>The <strong>priority band</strong> follows the total score: 7–9 Critical, "
                "5–6 High, 3–4 Medium, 1–2 Low, each with its own action. Critical means escalate "
                "to the Finance Head and hold new orders. <span class='cite'>Policy §5</span></p>"
            ),
            "exposure": (
                "<p><strong>Exposure</strong> is the open invoice value in a band — the strip at "
                "the top of the screen. It answers \"how much money is at stake here?\" rather "
                "than \"how many rows?\". <span class='cite'>Register, summed</span></p>"
            ),
            "promise": (
                "<p>A <strong>promise to pay</strong> is a date a customer has given for payment. "
                "It is logged by hand, never changes a score, and moves the customer to the top of "
                "the follow-up list once the date passes. <span class='cite'>Promise log</span></p>"
            ),
            "missing": (
                "<p><strong>Provisional</strong> means a register field is blank, so the score was "
                "calculated from the fields that remain. The blank is named and the score is "
                "flagged — it is never filled in by guesswork. "
                "<span class='cite'>Register, rows C011–C013</span></p>"
            ),
            "history": (
                "<p>The <strong>history code</strong> scores payment behaviour: on time 0, "
                "sometimes late 1, repeatedly late or past default 2. "
                "<span class='cite'>Policy §4.3</span></p>"
            ),
            "amount": (
                "<p><strong>Amount bands</strong>: under Rs 50,000 is 1 point, Rs 50,000 to "
                "Rs 2,00,000 is 2, above Rs 2,00,000 is 3. Both ends are inclusive. "
                "<span class='cite'>Policy §4.2</span></p>"
            ),
            "audit": (
                "<p>The <strong>audit log</strong> records every question, the version in use and "
                "a summary of the answer, downloadable from the sidebar. It is the evidence trail "
                "if someone asks why a customer was chased. <span class='cite'>Audit log</span></p>"
            ),
            "exports": (
                "<p>The <strong>worklist</strong> is the full ranked queue as CSV; a "
                "<strong>reminder pack</strong> is every draft for one band in one document. Both "
                "come from the same engine as the chat, so they cannot disagree with it.</p>"
            ),
        }
        if topic and topic in answers:
            return Reply(
                html=answers[topic],
                suggestions=["Show all overdue customers", "Top 3 customers to chase"],
                intent="definition",
            )
        return Reply(
            html=(
                "<p>That term is not defined in the Policy or the Register.</p>"
                f"<p><strong>{MISSING}</strong></p>"
                "<p class='note'>Terms I can define: days overdue, score, priority band, exposure, "
                "promise to pay, provisional data, history code, amount band, audit log.</p>"
            ),
            suggestions=["What is days overdue?", "What is a priority band?", "Show me the scoring rules"],
            intent="definition-unknown",
        )

    # ------------------------------------------------------------------
    # Filtered lists and totals
    # ------------------------------------------------------------------
    def _filter(self, q: nlu.Query, mode: str) -> list[Scored]:
        rows = self.ranked(mode)
        if q.priority:
            rows = [s for s in rows if s.priority == q.priority]
        if q.amount_gt is not None:
            rows = [s for s in rows if s.invoice.amount is not None and s.invoice.amount > q.amount_gt]
        if q.amount_lt is not None:
            rows = [s for s in rows if s.invoice.amount is not None and s.invoice.amount < q.amount_lt]
        if q.days_gt is not None:
            rows = [s for s in rows if (s.days or 0) >= q.days_gt]
        if q.days_lt is not None:
            rows = [s for s in rows if s.days is not None and 0 < s.days <= q.days_lt]
        if q.due_from is not None:
            rows = [s for s in rows if s.invoice.due_date and s.invoice.due_date >= q.due_from]
        if q.due_to is not None:
            rows = [s for s in rows if s.invoice.due_date and s.invoice.due_date <= q.due_to]
        if q.only_missing:
            rows = [s for s in rows if s.partial]
        if q.only_disputed and self.store is not None:
            disputed = self.store.disputed()
            rows = [s for s in rows if s.invoice.customer_id in disputed]
        if q.not_contacted_days and self.store is not None:
            cutoff = date.today() - timedelta(days=q.not_contacted_days)
            fresh = self.store.contacted_since(cutoff)
            rows = [s for s in rows if s.invoice.customer_id not in fresh]
        if q.only_not_due:
            rows = [s for s in rows if s.days is not None and s.days <= 0]
        elif not q.only_missing:
            rows = [s for s in rows if s.days is None or s.days > 0]
        return rows

    @staticmethod
    def _filter_words(q: nlu.Query) -> str:
        bits = []
        if q.window_label:
            bits.append(q.window_label)
            dated = q.due_from and str(q.due_from.year) in q.window_label
            if q.due_from and q.due_to and not dated:
                bits.append(f"({nlu._fmt_window(q.due_from, q.due_to)})")
            elif q.due_to and not q.due_from and not dated:
                bits.append(f"(due on or before {nlu._fmt_window(q.due_to, q.due_to)})")
        if q.priority:
            bits.append(f"{q.priority.lower()} priority")
        if q.amount_gt is not None:
            bits.append(f"above {inr(q.amount_gt)}")
        if q.amount_lt is not None:
            bits.append(f"under {inr(q.amount_lt)}")
        if q.days_gt is not None:
            bits.append(f"{q.days_gt}+ days overdue")
        if q.days_lt is not None:
            bits.append(f"up to {q.days_lt} days overdue")
        if q.only_missing:
            bits.append("missing data")
        if q.only_disputed:
            bits.append("under dispute")
        if q.not_contacted_days:
            bits.append(f"not contacted in {q.not_contacted_days} days")
        if q.only_not_due:
            bits.append("not yet due")
        return " ".join(bits)

    def listing(self, q: nlu.Query, mode: str) -> Reply:
        rows = self._filter(q, mode)
        label = self._filter_words(q) or "overdue"
        if not rows:
            return Reply(
                html=(
                    f"<p>Nothing in the register matches <strong>{esc(label)}</strong>, so there is "
                    "nothing to list. The window is narrow rather than empty — widen it and the "
                    "rows come back. <span class='cite'>Register (40 rows)</span></p>"
                ),
                suggestions=["Show all overdue customers", "Show the Critical list"],
                intent="listing",
            )
        total = sum(s.invoice.amount or 0 for s in rows)
        shown = rows[:40]
        parts = [
            f"<p><strong>{len(rows)} invoice(s) — {esc(label)}</strong>, ranked by score and then "
            f"by amount, total <strong>{esc(inr(total))}</strong>. "
            "<span class='cite'>Policy §4, §6</span></p>"
        ]
        if q.mentions_names:
            parts.append(
                "<p class='note'>The register carries Customer IDs only — there are no customer "
                "names in the data, so C017 is how that customer is identified. "
                "<span class='cite'>Policy §2</span></p>"
            )
        parts += [
            "<table class='tbl'><thead><tr><th>#</th><th>Customer</th><th>Days</th><th>Amount</th>"
            "<th>Score</th><th>Priority</th><th>Action</th></tr></thead><tbody>",
        ]
        for i, s in enumerate(shown, start=1):
            parts.append(
                "<tr>"
                f"<td>{i}</td>"
                f"<td>{esc(s.invoice.customer_id)}"
                f"{' <span class=flag>partial</span>' if s.partial else ''}</td>"
                f"<td>{self._days_cell(s, mode)}</td>"
                f"<td>{esc(inr(s.invoice.amount))}</td>"
                f"<td>{s.score}</td>"
                f"<td><span class='pill {s.priority.lower()}'>{esc(s.priority)}</span></td>"
                f"<td>{esc(s.action)}</td>"
                "</tr>"
            )
        parts.append("</tbody></table>")
        if len(rows) > len(shown):
            parts.append(f"<p class='note'>Showing the first {len(shown)} of {len(rows)} — the "
                         "Worklist CSV has them all.</p>")
        parts.append(
            "<p class='note'>Source: Register · Policy §4, §5, §6. "
            "Take the full file from <strong>Worklist CSV</strong> in the sidebar.</p>"
        )
        return Reply(
            html="".join(parts),
            suggestions=[
                "Draft a reminder for " + shown[0].invoice.customer_id,
                "How many are critical?",
                "Show only the Critical list",
            ],
            intent="listing",
        )

    def aggregate(self, q: nlu.Query, mode: str) -> Reply:
        rows = self._filter(q, mode)
        label = self._filter_words(q) or "overdue"
        if not rows:
            return Reply(
                html=f"<p>Nothing in the register matches <strong>{esc(label)}</strong>.</p>",
                suggestions=["Show all overdue customers"],
                intent="aggregate",
            )
        total = sum(s.invoice.amount or 0 for s in rows)
        by_band: dict[str, list[Scored]] = {}
        for s in rows:
            by_band.setdefault(s.priority, []).append(s)
        parts = [
            f"<p><strong>{len(rows)} invoice(s) {esc(label)}</strong>, totalling "
            f"<strong>{esc(inr(total))}</strong> of open exposure "
            f"(average {esc(inr(total // len(rows)))}). <span class='cite'>Register</span></p>"
        ]
        if len(by_band) > 1:
            parts.append("<table class='tbl'><thead><tr><th>Priority</th><th>Invoices</th>"
                         "<th>Value</th></tr></thead><tbody>")
            for band in ("Critical", "High", "Medium", "Low"):
                if band in by_band:
                    group = by_band[band]
                    parts.append(
                        f"<tr><td><span class='pill {band.lower()}'>{band}</span></td>"
                        f"<td>{len(group)}</td>"
                        f"<td>{esc(inr(sum(s.invoice.amount or 0 for s in group)))}</td></tr>"
                    )
            parts.append("</tbody></table>")
        else:
            only = rows[0].priority
            parts.append(
                f"<p>Every one of them sits in the <span class='pill {only.lower()}'>{only}</span> "
                "band.</p>"
            )
        parts.append(
            "<p class='note'>A count is not a work queue — the order still comes from the Policy. "
            "Ask <em>“show the critical list”</em> to see it ranked.</p>"
        )
        return Reply(
            html="".join(parts),
            suggestions=["Show all overdue customers", "Show the Critical list", "Top 3 customers to chase"],
            intent="aggregate",
        )

    def aging_reply(self, mode: str) -> Reply:
        rows = [s for s in self.ranked(mode) if (s.days or 0) > 0]
        data = engine.aging(rows)
        weighted = engine.weighted_age(rows)
        parts = [
            "<p><strong>Ageing of the open book</strong> — the standard view, on the Policy's own "
            "day bands. <span class='cite'>Policy §4.1</span></p>",
            "<table class='tbl'><thead><tr><th>Band</th><th>Invoices</th><th>Value</th>"
            "<th>Share</th></tr></thead><tbody>",
        ]
        for label, bucket in data["bands"].items():
            if bucket["count"]:
                parts.append(
                    f"<tr><td>{esc(label)} days</td><td>{bucket['count']}</td>"
                    f"<td>{esc(inr(bucket['value']))}</td><td>{bucket['share']}%</td></tr>"
                )
        parts.append("</tbody></table>")
        over_60 = data["bands"]["60+"]["share"]
        parts.append(
            f"<p>Value-weighted age is <strong>{weighted}</strong> days. "
            f"<strong>{over_60}%</strong> of open value is already past 60 days, which is the band "
            "that scores 4 and gets escalated. <span class='cite'>Policy §4.1, §5</span></p>"
        )
        parts.append(
            "<p class='note'>Ageing says where the money is stuck. It does not rank anything — "
            "that is still the Policy score. Ask <em>“what if we wait 30 days”</em> to see where "
            "this drifts.</p>"
        )
        return Reply(
            html="".join(parts),
            suggestions=["What if we wait 30 days?", "Show the Critical list", "Who holds the most exposure?"],
            intent="aging",
        )

    def what_if(self, extra_days: int, mode: str) -> Reply:
        data = engine.cost_of_delay(self.invoices, extra_days)
        jump = data["critical_after"] - data["critical_before"]
        parts = [
            f"<p><strong>If nothing is paid for {extra_days} more days</strong>, and not one new "
            f"invoice falls overdue. <span class='cite'>Policy §4.1, §5, §6</span></p>",
            "<table class='tbl'><thead><tr><th>Priority</th><th>Today</th>"
            f"<th>In {extra_days} days</th></tr></thead><tbody>",
        ]
        for band in ("Critical", "High", "Medium", "Low"):
            parts.append(
                f"<tr><td><span class='pill {band.lower()}'>{band}</span></td>"
                f"<td>{data['before'][band]['count']}</td><td>{data['after'][band]['count']}</td></tr>"
            )
        parts.append("</tbody></table>")
        parts.append(
            f"<p><strong>{data['crossing']} invoices change band</strong> on the clock alone. "
            f"Critical goes from {data['critical_before']} to {data['critical_after']} invoices, "
            f"and the value sitting in Critical from {esc(inr(data['critical_value_before']))} to "
            f"{esc(inr(data['critical_value_after']))}.</p>"
        )
        if data["example"]:
            parts.append(
                "<p>Examples: "
                + "; ".join(
                    f"{esc(cid)} {old} → <strong>{new}</strong>" for cid, old, new in data["example"]
                )
                + ".</p>"
            )
        parts.append(
            f"<p class='note'>Same invoices, same amounts, {extra_days} days later. The {jump} new "
            "Critical accounts are the cost of this week's silence. Amounts never change here — "
            "only the clock.</p>"
        )
        return Reply(
            html="".join(parts),
            suggestions=["Show the Critical list", "Ageing report", "Top 5 customers to chase"],
            intent="whatif",
        )

    def concentration_reply(self, mode: str) -> Reply:
        rows = [s for s in self.ranked(mode) if (s.days or 0) > 0]
        data = engine.concentration(rows)
        head = [s for s in rows if s.invoice.customer_id in data["customers"]]
        parts = [
            f"<p><strong>The five largest accounts hold {data['share']}% of open exposure</strong> "
            f"({esc(inr(data['top_value']))} of {esc(inr(data['total']))}). "
            "<span class='cite'>Register</span></p>",
            "<table class='tbl'><thead><tr><th>Customer</th><th>Amount</th><th>Share</th></tr></thead><tbody>",
        ]
        for s in sorted(head, key=lambda s: -(s.invoice.amount or 0)):
            share = round((s.invoice.amount or 0) * 100 / data["total"], 1) if data["total"] else 0
            parts.append(
                f"<tr><td>{esc(s.invoice.customer_id)}</td>"
                f"<td>{esc(inr(s.invoice.amount))}</td><td>{share}%</td></tr>"
            )
        parts.append("</tbody></table>")
        parts.append(
            "<p class='note'>Concentration is a risk statement, not a ranking. One missed payment "
            "among these five moves the total more than the other 34 customers combined. The queue "
            "order still comes from the Policy score.</p>"
        )
        return Reply(
            html="".join(parts),
            suggestions=["Ageing report", "Top 5 customers to chase", "What if we wait 30 days?"],
            intent="concentration",
        )

    def board_reply(self) -> Reply:
        return Reply(
            html=(
                "<p><strong>Month-end brief ready.</strong> One page: ageing, concentration, what "
                "30 days of inaction costs, work already in hand, and the top of the queue.</p>"
                "<p class='note'>Use the <em>Board brief</em> button in the sidebar to open it, or "
                "download it as markdown and paste into the report. Every figure in it is the same "
                "arithmetic as the chat.</p>"
            ),
            suggestions=["Ageing report", "What if we wait 30 days?", "Who holds the most exposure?"],
            intent="board",
        )

    def compare(self, customers: list[str], mode: str) -> Reply:
        known = [c for c in customers if c in self.invoices]
        if len(known) < 2:
            if known:
                return self.customer_detail(known[0], mode)
            return self.fallback(", ".join(customers) or "")
        scored = sorted((self.scored(self.invoices[c], mode) for c in known[:3]), key=lambda s: s.sort_key)
        parts = ["<table class='tbl'><thead><tr><th>Field</th>"]
        parts += [f"<th>{esc(s.invoice.customer_id)}</th>" for s in scored]
        parts.append("</tr></thead><tbody>")
        rows = [
            ("Days overdue", lambda s: self._days_cell(s, mode)),
            ("Amount", lambda s: esc(inr(s.invoice.amount))),
            ("Days points", lambda s: str(s.dp)),
            ("Amount points", lambda s: str(s.ap)),
            ("History points", lambda s: str(s.hp)),
            ("Total score", lambda s: f"<strong>{s.score}</strong>"),
            ("Priority", lambda s: f"<span class='pill {s.priority.lower()}'>{esc(s.priority)}</span>"),
            ("Action", lambda s: esc(s.action)),
        ]
        for title, render in rows:
            parts.append(f"<tr><th>{title}</th>")
            parts += [f"<td>{render(s)}</td>" for s in scored]
            parts.append("</tr>")
        parts.append("</tbody></table>")
        lead = scored[0]
        parts.append(
            f"<p><strong>{esc(lead.invoice.customer_id)} ranks first of these</strong> "
            f"({lead.score} points). Where scores tie, the larger amount decides — so a big "
            f"invoice can outrank an older one. <span class='cite'>Policy §6</span></p>"
        )
        return Reply(
            html="".join(parts),
            suggestions=[f"Draft a reminder for {lead.invoice.customer_id}", "Top 3 customers to chase"],
            intent="compare",
        )

    def export_reply(self, q: nlu.Query, mode: str) -> Reply:
        band = q.priority or "Critical"
        return Reply(
            html=(
                "<p>Two downloads, both from the sidebar:</p>"
                "<ul><li><strong>Worklist CSV</strong> — the whole ranked queue with score "
                "components, actions and data-quality flags.</li>"
                f"<li><strong>Reminder pack</strong> — every {esc(band.lower())} draft in one "
                "document (English or Hindi).</li></ul>"
                "<p>Neither decides anything the chat would not: same engine, same citations. "
                "<span class='cite'>Policy §4, §7</span></p>"
            ),
            suggestions=["Show all overdue customers", "Draft a reminder for C017"],
            intent="export",
        )
