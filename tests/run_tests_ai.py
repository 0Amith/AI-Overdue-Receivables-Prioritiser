"""Run the answer key with Gemini assist switched on, to prove it changes nothing."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import bot as bot_module  # noqa: E402
import engine  # noqa: E402
import llm  # noqa: E402

key = json.loads((ROOT / "tests" / "answer_key.json").read_text(encoding="utf-8"))
b = bot_module.Bot(engine.load_register(), use_llm=True)

failures = 0
for case in key["tests"]:
    reply = b.answer(case["ask"])
    text = reply.html
    bad = []
    for check in case["checks"]:
        value = check["value"]
        hit = value in text or re.search(value, text) is not None
        if check["kind"] == "not_contains":
            hit = not hit
        if not hit:
            bad.append(value)
    if bad:
        failures += 1
        print(f"FAIL {case['no']:>2} [{reply.source}] {case['ask']}  missing={bad}")
    else:
        print(f"ok   {case['no']:>2} [{reply.source}]")

print(f"\n{failures} failure(s) with Gemini on; model used: {llm.active_model()}")
sys.exit(1 if failures else 0)
