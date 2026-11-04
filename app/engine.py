"""Deterministic scoring engine for the ABC Traders receivables assistant.

Every rule here is a direct transcription of knowledge/Collections_Policy.md.
Nothing is inferred by a language model, so every number the bot prints can be
checked by hand against the policy and the register.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

DEFAULT_REPORT_DATE = date(2026, 10, 31)
REPORT_DATE = DEFAULT_REPORT_DATE

ROOT = Path(__file__).resolve().parent.parent
REGISTER_PATH = ROOT / "knowledge" / "Receivables_Register.csv"
POLICY_PATH = ROOT / "knowledge" / "Collections_Policy.md"

# Header names seen in the wild, mapped onto the fields the engine needs. A
# dataset with its own headers is matched here, case and punctuation free; an
# explicit mapping overrides this entirely.
COLUMN_ALIASES: dict[str, list[str]] = {
    "customer_id": [
        "customer id", "customer", "customerid", "customer code", "cust id", "party",
        "party id", "party code", "client", "client id", "client code", "account",
        "account id", "account code", "debtor", "debtor id", "ledger", "ledger id",
        "code", "id", "name", "customer name", "party name", "client name",
    ],
    "invoice_no": [
        "invoice no.", "invoice no", "invoice number", "invoice", "inv no", "inv no.",
        "inv #", "invoice #", "bill no", "bill number", "document no", "doc no", "reference",
    ],
    "invoice_date": ["invoice date", "inv date", "bill date", "document date", "posting date"],
    "due_date": [
        "due date", "duedate", "payment due date", "net due date", "due", "due on",
        "payment date", "maturity date",
    ],
    "amount": [
        "amount (rs)", "amount", "amount rs", "amount (inr)", "invoice amount", "open amount",
        "outstanding amount", "outstanding", "balance", "balance due", "value", "invoice value",
        "debit", "total",
    ],
    "history": [
        "history code", "history", "payment history", "payment behaviour", "payment behavior",
        "pay history", "credit history", "rating",
    ],
    "days_overdue": ["days overdue", "overdue days", "days", "age days", "ageing days", "aging days"],
}
REQUIRED_FIELDS = ("customer_id", "due_date", "amount")
FIELD_LABEL = {
    "customer_id": "Customer ID",
    "invoice_no": "Invoice No.",
    "invoice_date": "Invoice Date",
    "due_date": "Due Date",
    "amount": "Amount (Rs)",
    "history": "History Code",
    "days_overdue": "Days Overdue",
}
_HISTORY_FIELD = "history"


def set_report_date(when: date | None) -> None:
    """Pin the as-on date for a dataset. None restores the shipped policy date."""
    global REPORT_DATE
    REPORT_DATE = when or DEFAULT_REPORT_DATE

HISTORY_POINTS = {"OnTime": 0, "SometimesLate": 1, "RepeatedlyLate": 2}
HISTORY_LABEL = {
    "OnTime": "Always on time",
    "SometimesLate": "Sometimes late",
    "RepeatedlyLate": "Repeatedly late or past default",
}
HISTORY_ALIASES = {
    "ontime": "OnTime",
    "on time": "OnTime",
    "always on time": "OnTime",
    "sometimeslate": "SometimesLate",
    "sometimes late": "SometimesLate",
    "repeatedlylate": "RepeatedlyLate",
    "repeatedly late": "RepeatedlyLate",
    "past default": "RepeatedlyLate",
    "default": "RepeatedlyLate",
}

PRIORITY_ACTIONS = {
    "Critical": "Escalate to Finance Head and hold new orders",
    "High": "Firm email plus call from the manager",
    "Medium": "Email plus call",
    "Low": "Friendly email",
}

MISSING = "Please contact the Finance Manager."


class RegisterError(RuntimeError):
    pass


def inr(amount: int | float | None) -> str:
    """Indian digit grouping, e.g. 185000 -> 'Rs 1,85,000'."""
    if amount is None:
        return "amount missing"
    n = int(round(amount))
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return ("-Rs " if n < 0 else "Rs ") + s


@dataclass
class Invoice:
    customer_id: str
    invoice_no: str
    invoice_date: date | None
    due_date: date | None
    amount: int | None
    history: str | None
    days_column: int | None = None
    raw: dict = field(default_factory=dict)

    @property
    def missing_fields(self) -> list[str]:
        out = []
        if self.amount is None:
            out.append("Amount")
        if self.history is None:
            out.append("History Code")
        if self.due_date is None:
            out.append("Due Date")
        return out

    @property
    def days_overdue(self) -> int | None:
        if self.due_date is None:
            return None
        return (REPORT_DATE - self.due_date).days


DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d-%b-%Y", "%d %b %Y", "%b %d, %Y", "%d/%m/%y", "%Y/%m/%d")


def _parse_date(value: str) -> date | None:
    value = (value or "").strip().strip('"')
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        pass
    for fmt in DATE_FORMATS:
        try:
            return date.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _parse_amount(value: str) -> int | None:
    negative = value.strip().startswith(("-", "("))
    cleaned = (
        (value or "").strip().strip('"')
        .replace("Rs", "").replace("INR", "").replace("₹", "")
        .replace(",", "").replace(" ", "").strip("()").lstrip("-").lstrip("+")
    )
    if not cleaned:
        return None
    try:
        amount = int(round(float(cleaned)))
    except ValueError:
        return None
    return -amount if negative else amount


def _parse_history(value: str) -> str | None:
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    key = cleaned.lower().replace("_", " ").replace("-", " ")
    if key in HISTORY_ALIASES:
        return HISTORY_ALIASES[key]
    compact = key.replace(" ", "")
    if compact in HISTORY_ALIASES:
        return HISTORY_ALIASES[compact]
    return None


def _amount(value: str) -> int | None:
    negative = value.strip().startswith(("-", "("))
    cleaned = (
        value.strip().strip('"').replace("Rs", "").replace("INR", "").replace("₹", "")
        .replace(",", "").replace(" ", "").strip("()").lstrip("-").lstrip("+")
    )
    if not cleaned:
        return None
    try:
        number = int(round(float(cleaned)))
    except ValueError:
        return None
    return -number if negative else number


def _norm_header(name: str) -> str:
    """Fold a header to its core words: no units in brackets, no punctuation."""
    text = re.sub(r"\(.*?\)", " ", (name or "").lower())
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def map_columns(headers: list[str], mapping: dict[str, str] | None = None) -> dict[str, str | None]:
    """Resolve the dataset's headers onto engine fields.

    `mapping` (field -> header) wins outright when given; otherwise aliases are
    matched. Returns field -> header, with None where nothing was found.
    """
    by_norm = {_norm_header(h): h for h in headers}
    out: dict[str, str | None] = {}
    for field, aliases in COLUMN_ALIASES.items():
        chosen = None
        if mapping:
            wanted = mapping.get(field)
            if wanted:
                chosen = by_norm.get(_norm_header(wanted)) or (wanted if wanted in headers else None)
        else:
            for alias in aliases:
                hit = by_norm.get(alias)
                if hit:
                    chosen = hit
                    break
        out[field] = chosen
    return out


def inspect_dataset(text: str, mapping: dict[str, str] | None = None) -> dict:
    """Everything the Import dialog needs to show before committing."""
    reader = csv.DictReader(io.StringIO(text))
    headers = [h for h in (reader.fieldnames or []) if h and h.strip()]
    rows = list(reader)
    resolved = map_columns(headers, mapping)
    missing = [FIELD_LABEL[f] for f in REQUIRED_FIELDS if not resolved.get(f)]

    issues: list[str] = []
    ids: dict[str, int] = {}
    bad_dates = bad_amounts = bad_history = 0
    for row in rows:
        cid = (row.get(resolved["customer_id"] or "", "") or "").strip().upper()
        if not cid:
            continue
        ids[cid] = ids.get(cid, 0) + 1
        if _parse_date(row.get(resolved["due_date"] or "", "")) is None and (row.get(resolved["due_date"] or "", "") or "").strip():
            bad_dates += 1
        if _amount(row.get(resolved["amount"] or "", "")) is None and (row.get(resolved["amount"] or "", "") or "").strip():
            bad_amounts += 1
        if resolved.get(_HISTORY_FIELD) and _parse_history(row.get(resolved[_HISTORY_FIELD] or "", "")) is None:
            if (row.get(resolved[_HISTORY_FIELD] or "", "") or "").strip():
                bad_history += 1

    duplicates = {cid: n for cid, n in ids.items() if n > 1}
    if duplicates:
        issues.append(
            f"{len(duplicates)} customer ID(s) appear more than once; those rows fold into one customer "
            "(earliest due date, amounts added), because promises, contacts and the queue are per customer."
        )
    if bad_dates:
        issues.append(f"{bad_dates} row(s) have a due date that could not be read.")
    if bad_amounts:
        issues.append(f"{bad_amounts} row(s) have an amount that could not be read — flagged as missing.")
    if bad_history:
        issues.append(f"{bad_history} row(s) have a history code that is not OnTime / SometimesLate / RepeatedlyLate — flagged as missing.")
    if not resolved.get(_HISTORY_FIELD):
        issues.append("No payment-history column found: every score will be provisional. That is allowed.")
    if not resolved.get("days_overdue"):
        issues.append("No Days Overdue column found: Version 2 will count the days from the due date, which is exact as long as the as-on date is right.")

    return {
        "headers": headers,
        "mapping": resolved,
        "labels": FIELD_LABEL,
        "required": list(REQUIRED_FIELDS),
        "missing": missing,
        "rows": len(rows),
        "customers": len(ids),
        "sample": rows[:5],
        "issues": issues,
        "ok": not missing and bool(ids),
    }


def load_register(
    path: Path | None = None,
    mapping: dict[str, str] | None = None,
    report_date: date | None = None,
    text: str | None = None,
) -> dict[str, Invoice]:
    """Load a register from a file or raw CSV text.

    Any header set works through the aliases, and repeated customer IDs fold
    into one customer so the customer-level views stay coherent.
    """
    path = path or REGISTER_PATH
    if text is None:
        if not path.exists():
            raise RegisterError(f"Register not found: {path}")
        text = path.read_text(encoding="utf-8-sig")

    reader = csv.DictReader(io.StringIO(text))
    resolved = map_columns([h for h in (reader.fieldnames or []) if h], mapping)
    missing = [FIELD_LABEL[f] for f in REQUIRED_FIELDS if not resolved.get(f)]
    if missing:
        raise RegisterError("missing columns: " + ", ".join(missing))

    invoices: dict[str, Invoice] = {}
    for row in reader:
        cid = (row.get(resolved["customer_id"] or "", "") or "").strip().upper()
        if not cid:
            continue
        due = _parse_date(row.get(resolved["due_date"] or "", ""))
        amount = _amount(row.get(resolved["amount"] or "", ""))
        history = _parse_history(row.get(resolved[_HISTORY_FIELD] or "", "")) if resolved.get(_HISTORY_FIELD) else None
        invoice_no = ((row.get(resolved["invoice_no"] or "", "") or "").strip() or "unknown") if resolved.get("invoice_no") else "unknown"
        invoice_date = _parse_date(row.get(resolved["invoice_date"] or "", "")) if resolved.get("invoice_date") else None
        raw_days = row.get(resolved["days_overdue"] or "", "") if resolved.get("days_overdue") else ""
        try:
            days_column = int(float(str(raw_days).strip())) if str(raw_days).strip() else None
        except ValueError:
            days_column = None

        existing = invoices.get(cid)
        if existing is not None:
            # Keep the worst case for the clock and the total for the value.
            if due and (existing.due_date is None or due < existing.due_date):
                existing.due_date = due
                existing.invoice_no = invoice_no
                existing.invoice_date = invoice_date
            if existing.amount is None and amount is not None:
                existing.amount = amount
            elif amount is not None and existing.amount is not None:
                existing.amount += amount
            if existing.history is None:
                existing.history = history
            if existing.days_column is None:
                existing.days_column = days_column
            continue

        invoices[cid] = Invoice(
            customer_id=cid,
            invoice_no=invoice_no,
            invoice_date=invoice_date,
            due_date=due,
            amount=amount,
            history=history,
            days_column=days_column,
            raw=row,
        )
    if not invoices:
        raise RegisterError("Register is empty")
    if report_date:
        set_report_date(report_date)
    return invoices


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------
def days_points(days: int | None) -> int | None:
    if days is None:
        return None
    if days <= 0:
        return 0
    if days <= 15:
        return 1
    if days <= 30:
        return 2
    if days <= 60:
        return 3
    return 4


def amount_points(amount: int | None) -> int | None:
    if amount is None:
        return None
    if amount < 50000:
        return 1
    if amount <= 200000:
        return 2
    return 3


def history_points(history: str | None) -> int | None:
    if history is None:
        return None
    return HISTORY_POINTS.get(history)


def priority_for(score: int) -> str:
    if score >= 7:
        return "Critical"
    if score >= 5:
        return "High"
    if score >= 3:
        return "Medium"
    return "Low"


@dataclass
class Scored:
    invoice: Invoice
    days: int | None
    dp: int | None
    ap: int | None
    hp: int | None
    score: int
    priority: str
    partial: bool

    @property
    def action(self) -> str:
        return PRIORITY_ACTIONS[self.priority]

    @property
    def sort_key(self) -> tuple:
        return (-self.score, -(self.invoice.amount or 0), self.invoice.customer_id)


def score_invoice(inv: Invoice, days: int | None = None) -> Scored:
    """Score an invoice. `days` overrides the register's own day count.

    The override is what Version 1 uses: it feeds in the days the assistant
    counted for itself instead of the Days Overdue column.
    """
    actual_days = days
    if actual_days is None:
        actual_days = inv.days_column if inv.days_column is not None else inv.days_overdue
    dp = days_points(actual_days)
    ap = amount_points(inv.amount)
    hp = history_points(inv.history)
    total = sum(p for p in (dp, ap, hp) if p is not None)
    return Scored(
        invoice=inv,
        days=actual_days,
        dp=dp,
        ap=ap,
        hp=hp,
        score=total,
        priority=priority_for(total),
        partial=bool(inv.missing_fields),
    )


def rank(invoices: dict[str, Invoice], limit: int | None = None) -> list[Scored]:
    scored = [score_invoice(inv) for inv in invoices.values()]
    scored.sort(key=lambda s: s.sort_key)
    return scored[:limit] if limit else scored


# --------------------------------------------------------------------------
# Age analysis — the same day axes as the Policy, reported rather than scored
# --------------------------------------------------------------------------
AGING_BANDS: list[tuple[str, int, int | None]] = [
    ("0–15", 1, 15),
    ("16–30", 16, 30),
    ("31–60", 31, 60),
    ("60+", 61, None),
]


def age_bucket(days: int | None) -> str:
    if days is None:
        return "unknown"
    if days <= 0:
        return "not due"
    for label, low, high in AGING_BANDS:
        if days >= low and (high is None or days <= high):
            return label
    return "unknown"


def aging(rows: list[Scored], exclude_partial: bool = False) -> dict:
    """Value and count per age band. Partials carry a value only if the amount is known."""
    buckets = {label: {"count": 0, "value": 0} for label, _, _ in AGING_BANDS}
    buckets["not due"] = {"count": 0, "value": 0}
    buckets["unknown"] = {"count": 0, "value": 0}
    for s in rows:
        if exclude_partial and s.partial:
            continue
        bucket = buckets[age_bucket(s.days)]
        bucket["count"] += 1
        bucket["value"] += s.invoice.amount or 0
    total = sum(b["value"] for b in buckets.values())
    for label, bucket in buckets.items():
        bucket["share"] = round(bucket["value"] * 100 / total, 1) if total else 0.0
    return {"bands": buckets, "total": total}


def weighted_age(rows: list[Scored]) -> float | None:
    """Value-weighted mean days overdue — a one-number severity proxy."""
    value = 0
    weight = 0
    for s in rows:
        if s.days is None or s.days <= 0 or s.invoice.amount is None:
            continue
        value += s.days * s.invoice.amount
        weight += s.invoice.amount
    return round(value / weight, 1) if weight else None


def concentration(rows: list[Scored], top: int = 5) -> dict:
    """How much of the exposure sits with the largest few accounts."""
    valued = sorted(
        (s for s in rows if s.invoice.amount is not None),
        key=lambda s: -(s.invoice.amount or 0),
    )
    total = sum(s.invoice.amount or 0 for s in valued)
    head = valued[:top]
    head_value = sum(s.invoice.amount or 0 for s in head)
    return {
        "total": total,
        "top_value": head_value,
        "share": round(head_value * 100 / total, 1) if total else 0.0,
        "customers": [s.invoice.customer_id for s in head],
    }


# --------------------------------------------------------------------------
# Boundary proximity — how close a row is to crossing into the next band
# --------------------------------------------------------------------------
DAYS_EDGES = [15, 30, 60]
AMOUNT_EDGES = [50000, 200000]


def boundary_distance(s: Scored) -> list[str]:
    """Name the nearest day and amount edge, so a borderline row is visible."""
    out: list[str] = []
    if s.days is not None and s.days > 0:
        upcoming = next((edge for edge in DAYS_EDGES if edge >= s.days), None)
        if upcoming is not None:
            gap = upcoming - s.days
            out.append(
                f"{gap} day{'' if gap == 1 else 's'} short of the {upcoming}-day boundary"
                if gap
                else f"exactly on the {upcoming}-day boundary"
            )
    if s.invoice.amount is not None:
        upcoming = next((edge for edge in AMOUNT_EDGES if edge >= s.invoice.amount), None)
        if upcoming is not None:
            gap = upcoming - s.invoice.amount
            out.append(f"{inr(gap)} short of the {inr(upcoming)} boundary")
    return out


# --------------------------------------------------------------------------
# Cost of delay — what the same book scores if left alone for N more days
# --------------------------------------------------------------------------
def cost_of_delay(invoices: dict[str, Invoice], extra_days: int) -> dict:
    """Re-score every overdue row as if `extra_days` passed with no payment."""
    before = [s for s in (score_invoice(inv) for inv in invoices.values()) if (s.days or 0) > 0]
    after = [score_invoice(s.invoice, days=(s.days or 0) + extra_days) for s in before]

    def by_band(rows: list[Scored]) -> dict[str, dict]:
        out = {name: {"count": 0, "value": 0} for name in PRIORITY_ACTIONS}
        for s in rows:
            out[s.priority]["count"] += 1
            out[s.priority]["value"] += s.invoice.amount or 0
        return out

    was = by_band(before)
    will = by_band(after)
    promoted = [
        (old.invoice.customer_id, old.priority, new.priority)
        for old, new in zip(before, after)
        if new.priority != old.priority
    ]
    return {
        "extra_days": extra_days,
        "before": was,
        "after": will,
        "crossing": len(promoted),
        "critical_before": was["Critical"]["count"],
        "critical_after": will["Critical"]["count"],
        "critical_value_before": was["Critical"]["value"],
        "critical_value_after": will["Critical"]["value"],
        "example": promoted[:3],
    }


def score_breakdown(s: Scored) -> list[str]:
    """Human-readable score lines with policy citations."""
    inv = s.invoice
    lines: list[str] = []
    if s.days is None:
        lines.append("• Days overdue: **missing** (Due Date blank) — Policy §4.1")
    elif s.days <= 0:
        lines.append(
            f"• Days overdue: {s.days} (not yet due) → **0 points** — Policy §4.1"
        )
    else:
        lines.append(
            f"• Days overdue: {s.days} days → **{s.dp} point{'' if s.dp == 1 else 's'}** — Policy §4.1"
        )
    if s.ap is None:
        lines.append("• Invoice amount: **missing** — Policy §4.2")
    else:
        lines.append(f"• Invoice amount: {inr(inv.amount)} → **{s.ap} point{'' if s.ap == 1 else 's'}** — Policy §4.2")
    if s.hp is None:
        lines.append("• Payment history: **missing** — Policy §4.3")
    else:
        lines.append(
            f"• Payment history: {HISTORY_LABEL[inv.history]} → **{s.hp} point{'' if s.hp == 1 else 's'}** — Policy §4.3"
        )
    return lines
