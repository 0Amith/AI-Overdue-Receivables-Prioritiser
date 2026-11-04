"""Runs the 12 project tests against the bot, in Version 1 and Version 2.

Writes docs/TEST_RESULTS.md — the evidence table for the report.
Exit code 0 only when every Version 2 test passes.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import bot as bot_module  # noqa: E402
import engine  # noqa: E402

KEY = json.loads((ROOT / "tests" / "answer_key.json").read_text(encoding="utf-8"))
OUT = ROOT / "docs" / "TEST_RESULTS.md"


def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"[ \t]+", " ", s)


def run_checks(reply_html: str, checks: list[dict]) -> tuple[bool, list[str]]:
    reasons = []
    ok = True
    for c in checks:
        kind, value = c["kind"], c["value"]
        if kind == "contains":
            hit = value.lower() in reply_html.lower()
        elif kind == "not_contains":
            hit = value.lower() not in reply_html.lower()
        elif kind == "regex":
            hit = re.search(value, reply_html, re.S) is not None
        else:
            raise ValueError(kind)
        if not hit:
            ok = False
            reasons.append(f"{kind} failed: {value}")
    return ok, reasons


def main() -> int:
    b = bot_module.Bot(engine.load_register())
    results = []
    for t in KEY["tests"]:
        row = {"no": t["no"], "type": t["type"], "ask": t["ask"], "expected": t["expected"]}
        for mode in ("v1", "v2"):
            reply = b.answer(t["ask"], mode).html
            ok, reasons = run_checks(reply, t["checks"])
            row[mode] = {"ok": ok, "reasons": reasons, "reply": strip_html(reply)[:400]}
        results.append(row)

    v2_pass = sum(1 for r in results if r["v2"]["ok"])
    v1_pass = sum(1 for r in results if r["v1"]["ok"])

    lines = [
        "# Test results — full matrix",
        "",
        f"Run: {datetime.now().strftime('%d %B %Y, %H:%M')} · reporting date 31 October 2026 · "
        f"40 register rows",
        "",
        f"**Version 1: {v1_pass}/{len(results)} right. Version 2: {v2_pass}/{len(results)} right.**",
        "",
        "Answer key written by hand from the Collections Policy before testing.",
        "",
        "| No. | Test type | Question | Expected | V1 | V2 |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        mark = lambda m: "Right" if r[m]["ok"] else "Wrong"
        lines.append(
            f"| {r['no']} | {r['type']} | {r['ask']} | {r['expected']} | {mark('v1')} | {mark('v2')} |"
        )
    lines += ["", "## Version 1 failures (before the Days Overdue column)", ""]
    any_fail = False
    for r in results:
        if not r["v1"]["ok"]:
            any_fail = True
            lines.append(f"**Test {r['no']} — {r['type']}**")
            lines.append(f"- asked: `{r['ask']}`")
            for reason in r["v1"]["reasons"]:
                lines.append(f"- {reason}")
            lines.append(f"- bot said: {r['v1']['reply'][:300]}…")
            lines.append("")
    if not any_fail:
        lines.append("None — Version 1 passed every test in this run.")
    lines += ["", "## Version 2 detail", ""]
    for r in results:
        lines.append(f"**Test {r['no']} — {r['type']}** → {'Right' if r['v2']['ok'] else 'Wrong'}")
        lines.append(f"- asked: `{r['ask']}`")
        lines.append(f"- bot said: {r['v2']['reply'][:300]}…")
        for reason in r["v2"]["reasons"]:
            lines.append(f"- FAILED: {reason}")
        lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")

    print(f"Version 1: {v1_pass}/{len(results)} right")
    print(f"Version 2: {v2_pass}/{len(results)} right")
    for r in results:
        flag = "ok  " if r["v2"]["ok"] else "FAIL"
        print(f"  [{flag}] test {r['no']:>2} (v2)  {r['type']}")
        for reason in r["v2"]["reasons"]:
            print(f"         - {reason}")
    print(f"\nwrote {OUT}")
    return 0 if v2_pass == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
