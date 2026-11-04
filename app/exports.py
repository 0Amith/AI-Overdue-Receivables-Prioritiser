"""Exports and self-checks: worklist, reminder pack, exposure, policy audit.

These are the artifacts a finance team actually consumes. Everything here is
derived from the same engine the chat uses, so an export can never disagree with
an answer.
"""
from __future__ import annotations

from datetime import datetime

import re

import engine

PRIORITIES = ["Critical", "High", "Medium", "Low"]


def summary(ranked: list[engine.Scored]) -> dict:
    bands = {
        p: {"count": 0, "amount": 0, "customers": []} for p in PRIORITIES
    }
    total = 0
    for s in ranked:
        amount = s.invoice.amount or 0
        total += amount
        bands[s.priority]["count"] += 1
        bands[s.priority]["amount"] += amount
        bands[s.priority]["customers"].append(s.invoice.customer_id)
    partial = sum(1 for s in ranked if s.partial)
    return {"total_amount": total, "bands": bands, "partial_rows": partial}


def worklist_csv(ranked: list[engine.Scored], promises: dict, contacts: dict | None = None) -> str:
    contacts = contacts or {}
    head = (
        "rank,customer_id,invoice_no,due_date,days_overdue,amount_rs,history,"
        "days_points,amount_points,history_points,total_score,priority,action,"
        "data_quality,promised_on,promised_overdue,last_outcome,last_contact"
    )
    lines = [head]
    for i, s in enumerate(ranked, start=1):
        inv = s.invoice
        promise = promises.get(inv.customer_id) or {}
        promised_on = promise.get("promised_on", "")
        promised_overdue = ""
        if promised_on:
            promised_overdue = "yes" if promised_on < engine.REPORT_DATE.isoformat() else "no"
        quality = "provisional:" + "|".join(inv.missing_fields) if s.partial else "complete"
        contact = contacts.get(inv.customer_id) or {}
        lines.append(
            ",".join(
                [
                    str(i),
                    inv.customer_id,
                    inv.invoice_no,
                    inv.due_date.isoformat() if inv.due_date else "",
                    "" if s.days is None else str(s.days),
                    "" if inv.amount is None else str(inv.amount),
                    inv.history or "",
                    "" if s.dp is None else str(s.dp),
                    "" if s.ap is None else str(s.ap),
                    "" if s.hp is None else str(s.hp),
                    str(s.score),
                    s.priority,
                    f'"{s.action}"',
                    quality,
                    promised_on,
                    promised_overdue,
                    contact.get("outcome", ""),
                    contact.get("last_contact", ""),
                ]
            )
        )
    return "\n".join(lines) + "\n"


def aging_csv(ranked: list[engine.Scored]) -> str:
    """The standard AR ageing report, from the same engine."""
    rows = ["band,invoices,value_rs,share_pct"]
    data = engine.aging(ranked)
    for label, bucket in data["bands"].items():
        rows.append(f'"{label}",{bucket["count"]},{bucket["value"]},{bucket["share"]}')
    rows.append(f'"total",{sum(b["count"] for b in data["bands"].values())},{data["total"]},100')
    return "\n".join(rows) + "\n"


def board_pack(ranked: list[engine.Scored], promises: dict, contacts: dict | None = None) -> str:
    """One-page month-end brief for the Finance Head."""
    contacts = contacts or {}
    data = engine.aging(ranked)
    concentration = engine.concentration(ranked)
    delay = engine.cost_of_delay({s.invoice.customer_id: s.invoice for s in ranked}, 30)
    open_rows = [s for s in ranked if (s.days or 0) > 0]
    disputed = [s for s in open_rows if (contacts.get(s.invoice.customer_id) or {}).get("outcome") == "disputed"]
    promised = [s for s in open_rows if s.invoice.customer_id in promises]

    lines = [
        "# Receivables brief",
        "",
        f"Reporting date {engine.REPORT_DATE.strftime('%d %B %Y')}. "
        f"Prepared by the receivables assistant from the register and the Collections Policy.",
        "",
        "## Where the money sits",
        "",
        "| Age band | Invoices | Value | Share |",
        "|---|---|---|---|",
    ]
    for label, bucket in data["bands"].items():
        if bucket["count"]:
            lines.append(f"| {label} days | {bucket['count']} | {engine.inr(bucket['value'])} | {bucket['share']}% |")
    lines += [
        "",
        f"**Open exposure {engine.inr(data['total'])} across {len(open_rows)} invoices.** "
        f"Value-weighted age {engine.weighted_age(open_rows)} days.",
        "",
        "## Concentration",
        "",
        f"The five largest accounts hold {concentration['share']}% of exposure "
        f"({', '.join(concentration['customers'])}). A single missed payment among them "
        "moves the total more than the rest of the book combined.",
        "",
        "## If nothing is done for 30 days",
        "",
        f"Critical rises from {delay['critical_before']} to {delay['critical_after']} invoices "
        f"({engine.inr(delay['critical_value_before'])} to {engine.inr(delay['critical_value_after'])}). "
        f"{delay['crossing']} invoices change band without a single new overdue account.",
        "",
        "## Work already in hand",
        "",
        f"- {len(promised)} promises to pay on record",
        f"- {len(disputed)} invoices under dispute, held out of chasing",
        "",
        "## Top of the queue",
        "",
        "| # | Customer | Days | Amount | Priority | Action |",
        "|---|---|---|---|---|---|",
    ]
    for i, s in enumerate(open_rows[:10], start=1):
        lines.append(
            f"| {i} | {s.invoice.customer_id} | {s.days} | {engine.inr(s.invoice.amount)} | "
            f"{s.priority} | {s.action} |"
        )
    lines += [
        "",
        "---",
        f"Generated {datetime.now().strftime('%d %b %Y %H:%M')}. Every figure is reproducible "
        "from the register and the Policy; the assistant recommends, Accounts Receivable decides.",
        "",
    ]
    return "\n".join(lines)


def reminder_pack(
    bot, ranked: list[engine.Scored], priority: str, lang: str = "en", promises: dict | None = None
) -> str:
    promises = promises or {}
    picked = [s for s in ranked if s.priority == priority]
    stamp = datetime.now().strftime("%d %B %Y")
    out = [
        f"# ABC Traders — {priority} reminder pack",
        "",
        f"Generated {stamp} · reporting date {engine.REPORT_DATE.isoformat()} · "
        f"{len(picked)} reminder(s) · total exposure {engine.inr(sum(s.invoice.amount or 0 for s in picked))}",
        "",
        "Every draft below was produced by the same rule engine the assistant uses. "
        "Review each one before sending — the bot never sends.",
        "",
    ]
    if not picked:
        out.append(f"_No customers currently sit in the {priority} band._")
        return "\n".join(out) + "\n"
    for s in picked:
        inv = s.invoice
        promise = promises.get(inv.customer_id) or {}
        out.append("---")
        out.append("")
        out.append(
            f"**{inv.customer_id} · score {s.score}/9 · {s.priority} · "
            f"{engine.inr(inv.amount)} · {s.days} days overdue**"
        )
        if s.partial:
            out.append(f"_Missing data: {', '.join(inv.missing_fields)} — verify before sending._")
        if promise.get("promised_on"):
            out.append(f"_Promised payment date on record: {promise['promised_on']}_")
        out.append("")
        out.append("```")
        out.append(bot._reminder_text(s, "v2", lang))
        out.append("```")
        out.append("")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# Policy self-check
# --------------------------------------------------------------------------
DAYS_CASES = [(1, 1), (15, 1), (16, 2), (30, 2), (31, 3), (60, 3), (61, 4), (400, 4)]
AMOUNT_CASES = [(49999, 1), (50000, 2), (200000, 2), (200001, 3)]
HISTORY_CASES = [("OnTime", 0), ("SometimesLate", 1), ("RepeatedlyLate", 2)]
PRIORITY_CASES = [(2, "Low"), (3, "Medium"), (4, "Medium"), (5, "High"), (6, "High"), (7, "Critical"), (9, "Critical")]


def policy_check() -> dict:
    rows = []

    def add(group: str, case: str, expected, actual) -> None:
        rows.append(
            {"group": group, "case": case, "expected": expected, "actual": actual, "ok": expected == actual}
        )

    for days, expected in DAYS_CASES:
        add("days overdue", f"{days} day(s)", expected, engine.days_points(days))
    for amount, expected in AMOUNT_CASES:
        add("amount", engine.inr(amount), expected, engine.amount_points(amount))
    for code, expected in HISTORY_CASES:
        add("history", code, expected, engine.history_points(code))
    for score, expected in PRIORITY_CASES:
        add("priority", f"score {score}", expected, engine.priority_for(score))

    return {
        "rows": rows,
        "derived": _derived_check(),
        "total": len(rows),
        "passed": sum(1 for r in rows if r["ok"]),
        "boundary_note": "Bands are lower-bound inclusive: 15 = 1, 30 = 2, 60 = 3 points.",
    }


# --------------------------------------------------------------------------
# Policy-derived check
#
# The cases above were transcribed by hand from the Policy. This reads the band
# tables back out of knowledge/Collections_Policy.md and re-derives each one, so
# an edit to the Policy that the engine does not follow shows up as a failure
# without anyone remembering to add a case.
# --------------------------------------------------------------------------
_POINT_ROW = re.compile(r"^\|\s*(?:Days overdue|Invoice amount|Payment history)\s*\|\s*(.+?)\s*\|\s*(\d)\s*\|", re.M)
_BAND_ROW = re.compile(r"^\|\s*(\d+)\s*to\s*(\d+)\s*\|\s*(\w+)\s*\|", re.M)


def _ranges(rule: str) -> tuple[int, int | None] | None:
    compact = rule.replace(",", "").replace("Rs", "").strip()
    more_than = "more than" in compact.lower()
    m = re.match(r"^(\d+)\s*[–-]\s*(\d+)\s*days?", compact)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"^(\d+)\+\s*days?", compact)
    if m:
        low = int(m.group(1))
        return (low + 1 if more_than else low), None
    m = re.match(r"^Under\s*(\d+)", compact, re.I)
    if m:
        return 1, int(m.group(1)) - 1
    m = re.match(r"^(\d+)\s*to\s*(\d+)", compact, re.I)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"^Above\s*(\d+)", compact, re.I)
    if m:
        return int(m.group(1)) + 1, None
    return None


def _derived_check() -> list[dict]:
    """Build cases from the Policy text itself and test the engine against them."""
    rows: list[dict] = []
    try:
        text = engine.POLICY_PATH.read_text(encoding="utf-8")
    except OSError:
        return [{"group": "policy file", "case": "read", "expected": "readable", "actual": "missing", "ok": False}]

    def add(group: str, case: str, expected, actual) -> None:
        rows.append(
            {"group": group, "case": case, "expected": expected, "actual": actual, "ok": expected == actual}
        )

    day_bands: list[tuple[int, int | None, int]] = []
    for rule, points in _POINT_ROW.findall(text):
        if "day" in rule and ("–" in rule or "+" in rule or "-" in rule):
            span = _ranges(rule)
            if span:
                day_bands.append((span[0], span[1], int(points)))
        elif "Rs" in rule:
            span = _ranges(rule)
            if not span:
                continue
            low, high = span
            add("policy: amount", f"{rule} → low end {engine.inr(low)}", int(points), engine.amount_points(low))
            if high is not None:
                add("policy: amount", f"{rule} → high end {engine.inr(high)}", int(points), engine.amount_points(high))

    day_bands.sort()
    previous: int | None = None
    previous_high: int | None = None
    for low, high, points in day_bands:
        if previous_high is not None:
            add(
                "policy: layout",
                f"{previous_high + 1} or {low} — bands must be contiguous",
                previous_high + 1,
                low,
            )
        add("policy: days", f"first day of the {low}+ band", points, engine.days_points(low))
        if high is not None:
            add("policy: days", f"last day of the {low}–{high} band", points, engine.days_points(high))
            if previous is not None:
                add("policy: days", f"day {low - 1} stays in the previous band", previous, engine.days_points(low - 1))
        previous = points
        previous_high = high

    for code, points in re.findall(r"`(OnTime|SometimesLate|RepeatedlyLate)`\s*\)\s*\|\s*(\d)", text):
        add("policy: history", code, int(points), engine.history_points(code))

    for low, high, priority in _BAND_ROW.findall(text):
        add("policy: priority", f"score {low}", priority, engine.priority_for(int(low)))
        add("policy: priority", f"score {high}", priority, engine.priority_for(int(high)))

    if not rows:
        add("policy", "band tables found", True, False)
    return rows
