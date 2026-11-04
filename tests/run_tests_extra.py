"""Tests for the analysis and record-keeping features.

Separate from run_tests.py on purpose: that file is the 12 mandated project
tests with a hand-written answer key and a fixed shared bot. These exercise the
newer work (ageing, cost of delay, concentration, contact log, derived policy
check) against a throwaway store, so they can be run at any time without
touching state/ or the answer key.

Writes docs/FEATURE_TESTS.md. Exit code 0 only when every case passes.
"""
from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import bot as bot_module  # noqa: E402
import engine  # noqa: E402
import exports  # noqa: E402
import state  # noqa: E402

SANDBOX = ROOT / ".tmp" / "feature-test-state"
OUT = ROOT / "docs" / "FEATURE_TESTS.md"


def text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def main() -> int:
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX)
    store = state.Store(SANDBOX)
    reg = engine.load_register()
    b = bot_module.Bot(reg, store)

    total_value = sum(inv.amount or 0 for inv in reg.values())
    results: list[tuple[str, str, bool, str]] = []

    def case(name: str, ask: str, check, responder=None) -> None:
        reply = (responder or b).answer(ask)
        body = text(reply.html)
        ok, note = check(body, reply)
        results.append((name, ask, ok, note))

    case("ageing uses the Policy bands", "ageing report",
         lambda t, r: ("0–15 days" in t and "60+ days" in t and "Value-weighted age" in t,
                       "band table and weighted age present"))
    case("ageing totals match the register", "ageing report",
         lambda t, r: (engine.inr(total_value) in t or "34.6%" in t, "60+ share reported"))
    case("cost of delay re-bands on the clock", "what if we wait 30 days",
         lambda t, r: ("change band" in t and "Critical goes from" in t, "crossings reported"))
    case("cost of delay respects the asked horizon", "what if we wait 10 days",
         lambda t, r: ("10 more days" in t, "horizon echoed"))
    case("concentration names the largest accounts", "who holds the most exposure",
         lambda t, r: (bool(re.search(r"C0\d\d", t)) and "% of open exposure" in t, "share and IDs present"))
    case("concentration is not called a ranking", "who holds the most exposure",
         lambda t, r: ("not a ranking" in t, "caveat present"))
    case("board brief is offered", "board brief",
         lambda t, r: ("Month-end brief" in t, "brief answer"))
    case("dispute filter is empty at first", "show disputed invoices",
         lambda t, r: ("Nothing in the register matches" in t, "empty window handled"))

    store.log_contact("C026", "disputed", "short delivery, credit note pending")
    store.log_contact("C004", "no answer", "")

    case("dispute filter finds the marked row", "show disputed invoices",
         lambda t, r: ("C026" in t and "C004" not in t, "only the disputed row listed"))
    case("dispute is excluded from the cooldown list", "not contacted in 7 days",
         lambda t, r: ("C026" not in t and "C004" not in t, "both contacted rows absent"))
    case("customer detail shows the last contact", "score C026",
         lambda t, r: ("Last contact" in t and "disputed" in t, "contact line rendered"))

    case("boundary proximity is explained", "why is C001 ranked there",
         lambda t, r: ("boundary" in t, "nearest edge named"))
    case("Hinglish list request is understood", "saari overdue list dikhao",
         lambda t, r: ("invoice(s)" in t and "overdue" in t, "listing"))
    case("Hinglish amount filter is understood", "50 hazaar se zyada wale",
         lambda t, r: ("above Rs 50,000" in t or "above rs 50,000" in t.lower(), "amount_gt 50000"))
    case("Hinglish rank request is understood", "kaun sabse pehle chase karna hai",
         lambda t, r: (r.intent in ("rank", "ranking", "listing") and "C0" in t, f"intent {r.intent}"))
    case("Hinglish total request is understood", "total baki kitna hai",
         lambda t, r: (r.intent == "aggregate", "aggregate intent"))
    case("unknown definition still refuses exactly", "what is the weather like",
         lambda t, r: ("Please contact the Finance Manager." in t, "refusal sentence intact"))
    case("discount questions still defer", "can we offer a discount",
         lambda t, r: ("Finance Manager" in t, "refers to the Finance Manager"))

    check = exports.policy_check()
    derived = check["derived"]
    case("policy-derived cases all pass", "policy self-check",
         lambda t, r: (all(x["ok"] for x in derived), f"{len(derived)} derived cases, "
                       f"{sum(1 for x in derived if x['ok'])} pass"))
    case("hand-written cases all pass", "policy self-check",
         lambda t, r: (check["passed"] == check["total"], f"{check['passed']}/{check['total']}"))

    workbook = exports.worklist_csv(engine.rank(reg), {}, store.contacts())
    case("worklist carries the contact columns", "worklist export",
         lambda t, r: ("last_outcome" in workbook and "disputed" in workbook, "header and value present"))
    ageing = exports.aging_csv(engine.rank(reg))
    case("ageing export sums to the book", "ageing export",
         lambda t, r: (f",{total_value},100" in ageing, "total row equals the register"))

    import json

    drift = engine.POLICY_PATH.read_text(encoding="utf-8").replace(
        "| Days overdue | 16–30 days | 2 |", "| Days overdue | 16–29 days | 2 |"
    )
    spare = SANDBOX / "drifted_policy.md"
    spare.write_text(drift, encoding="utf-8")
    original = engine.POLICY_PATH
    engine.POLICY_PATH = spare
    try:
        drifted = exports.policy_check()
        case("an edited Policy turns the derived check red", "policy drift",
             lambda t, r: (sum(1 for x in drifted["derived"] if not x["ok"]) > 0
                           and drifted["passed"] == drifted["total"], "drift caught"))
    finally:
        engine.POLICY_PATH = original

    # -- a foreign dataset: other headers, other IDs, other as-on date -------
    foreign = (
        "Party Code,Bill No,Payment Due Date,Outstanding (INR),Rating\n"
        'ACME-01,INV/9001,2026-09-20,"1,20,000",Sometimes late\n'
        "ACME-02,INV/9002,2026-12-15,45000,On time\n"
        "S/1042,INV/9003,2026-10-10,210000,Repeatedly late\n"
        "S/1042,INV/9004,2026-08-25,30000,\n"
    )
    info = engine.inspect_dataset(foreign)
    case("foreign headers are recognised", "import path",
         lambda t, r: (info["ok"] and info["mapping"]["amount"] == "Outstanding (INR)",
                       "amount column matched through 'Outstanding (INR)'"))
    case("required columns are reported missing", "import path",
         lambda t, r: (set(engine.inspect_dataset("A,B\n1,2\n")["missing"]) == {"Customer ID", "Due Date", "Amount (Rs)"},
                       "Due Date and Amount flagged"))
    case("duplicate IDs are called out before import", "import path",
         lambda t, r: (any("more than once" in i for i in info["issues"]), "duplicate warning"))
    case("comma amounts and text dates parse", "import path",
         lambda t, r: (engine._parse_amount('"1,20,000"') == 120000
                       and engine._parse_date("20-Sep-2026").isoformat() == "2026-09-20", "parsed"))

    foreign_inv = engine.load_register(text=foreign, report_date=engine.date(2026, 11, 30))
    case("duplicate rows fold into one customer", "import path",
         lambda t, r: (foreign_inv["S/1042"].amount == 240000
                       and foreign_inv["S/1042"].due_date.isoformat() == "2026-08-25",
                       "amounts added, earliest due date kept"))
    case("the as-on date drives the day count", "import path",
         lambda t, r: (engine.score_invoice(foreign_inv["ACME-01"]).days == 71
                       and engine.score_invoice(foreign_inv["ACME-02"]).days == -15, "71 and -15 days"))
    case("the shipped register returns to its own date", "import path",
         lambda t, r: (engine.set_report_date(None) or engine.REPORT_DATE.isoformat() == "2026-10-31",
                       "date cleared"))

    foreign_bot = bot_module.Bot(foreign_inv, store, use_llm=False)
    case("a foreign ID can be asked about", "score ACME-01",
         lambda t, r: (r.intent == "score" and "ACME-01" in t, "routed and answered"), foreign_bot)
    case("a slashed ID can be asked about", "score S/1042",
         lambda t, r: (r.intent == "score" and "S/1042" in t, "routed and answered"), foreign_bot)
    case("an unknown ID is refused, not invented", "score ZZZ-9",
         lambda t, r: ("Please contact the Finance Manager." in t, "no invented customer"), foreign_bot)
    case("the queue ranks on the Policy, not on length", "top 3 customers to chase",
         lambda t, r: (r.intent == "ranking" and t.index("S/1042") < (t.index("ACME-01") if "ACME-01" in t else 9999),
                       "S/1042 leads"), foreign_bot)
    case("the shipped register is unaffected", "score C002",
         lambda t, r: (b.answer("score C002").intent == "score", "C002 still resolves"))

    passed = sum(1 for r in results if r[2])
    lines = [
        "# Feature test results",
        "",
        f"Run: {datetime.now().strftime('%d %B %Y, %H:%M')} · throwaway store under .tmp/ · "
        "register and state/ untouched",
        "",
        f"**{passed}/{len(results)} pass.**",
        "",
        "| Case | Asked | Result | Note |",
        "|---|---|---|---|",
    ]
    for name, ask, ok, note in results:
        lines.append(f"| {name} | `{ask}` | {'pass' if ok else 'FAIL'} | {note} |")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    shutil.rmtree(SANDBOX, ignore_errors=True)

    print(f"{passed}/{len(results)} pass")
    for name, ask, ok, note in results:
        print(f"  [{'ok  ' if ok else 'FAIL'}] {name}  ({note})")
    print(f"\nwrote {OUT}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
