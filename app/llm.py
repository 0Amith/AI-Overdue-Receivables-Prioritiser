"""Optional Gemini layer: turns a sentence into a structured query.

The model is never asked for a score or a total — only which intent the sentence
means and which filters it carries. The rule engine still does every piece of
arithmetic, so enabling Gemini makes the assistant understand more phrasings
without making it less exact.

No key configured? Every function degrades to a no-op and the parser handles the
sentence alone.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.json"
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT = 5
DEADLINE = 6

# Preferred first. Google deprecates and throttles models, so a single hard-coded
# name is not enough: on 404 or 503 we move to the next one and remember whatever
# answered last, to stop paying for the dead ones on every request.
MODELS = [
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-flash-latest",
    "gemini-3.1-flash-lite",
]
_working_model: str | None = None
_CACHE: dict[str, dict] = {}

INTENTS = [
    "listing", "aggregate", "rank", "score", "reminder", "explain", "compare", "discount",
    "followup", "policy", "definition", "privacy", "export", "meta", "help",
    "greeting", "thanks", "bye", "unknown", "aging", "concentration", "whatif", "board",
]
TOPICS = [
    "days", "score", "priority", "exposure", "promise", "missing",
    "history", "amount", "audit", "exports",
]

PROMPT = """You convert a finance user's question into a JSON query. You never calculate anything.

Reporting date is {today}. The register has customers C001 to C040 and nothing else.

Return ONLY this JSON shape:
{{"intent": one of {intents},
  "confidence": 0.0-1.0,
  "customers": ["C001", ...],
  "priority": "Critical"|"High"|"Medium"|"Low"|null,
  "due_from": "YYYY-MM-DD"|null,
  "due_to": "YYYY-MM-DD"|null,
  "days_min": int|null,
  "days_max": int|null,
  "amount_min": int|null,
  "amount_max": int|null,
  "only_missing": true|false,
  "only_disputed": true|false,
  "extra_days": int|null,
  "topic": one of {topics} or null}}

Intent guide:
- listing: show a set of customers/invoices ("all overdue", "who is late", "above 4 lakh")
- rank: a short ordered shortlist ("top 3 to chase", "who owes us the most")
- aggregate: a count or a total ("how many critical", "total overdue")
- score: one customer's breakdown; reminder: draft an email; explain: why ranked there
- compare: two or more customers; discount: discount/settlement
- followup: the promise-to-pay log ("what is due for follow-up", "who promised to pay")
- policy: the rule set itself ("show the rules", "what are the bands", "how is it scored")
- definition: what a term means (see below)
- aging: age brackets, ageing report, "how old is this debt"
- concentration: how much sits with the biggest accounts ("who holds the most exposure")
- whatif: what happens if we wait N more days, cost of delay, do nothing
- board: a brief or month-end pack for management
- Hinglish is accepted: baki/baaki/udhaar = overdue, dikhao/batao = show, kitna = how much,
  sabse pehle = first (rank), se zyada = above, se kam = under
- meta: what files/data/model; privacy: seeing other customers' data; export: csv/download

Rules that matter:
- "What is X" is a definition when X is a term: "what is days overdue" -> definition with
  topic "days". If X is a term the topic list does not cover ("what is the penalty
  interest rate"), still use definition but with topic null — the app then answers that
  it is not defined. Do not fall back to dumping the whole policy for a term question.
- "What is due for follow-up" is NOT a definition: it asks about promises -> followup.
- Leave "customers" empty for a definition, a followup, a policy question, a rank, a total,
  aging, concentration, whatif or board. Only name customer IDs the question actually names; never invent them.

Date windows (use the reporting date):
- "last month" -> due_from/due_to covering the previous calendar month
- "this month" -> the current calendar month
- "last 30 days"/"past 1 month" -> due_from = today minus 29 days, due_to = today
- "more than a month" -> due_to = today minus 31 days
- a named month -> that month of the reporting year
Use days_min/days_max only when the user gives days explicitly ("30+ days" -> days_min 30).

If the question is not about receivables at all, intent "unknown" and confidence below 0.4.
Set confidence honestly; below 0.55 the parser's own reading is kept.

Question: {question}"""


def _key() -> str | None:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        return key.strip()
    if CONFIG.exists():
        try:
            data = json.loads(CONFIG.read_text(encoding="utf-8"))
            value = str(data.get("gemini_api_key") or "").strip()
            if value and not value.startswith("PASTE"):
                return value
        except (json.JSONDecodeError, OSError):
            return None
    return None


def configured() -> bool:
    return bool(_key())


def active_model() -> str | None:
    return _working_model


def _clean(payload: dict) -> dict:
    out: dict = {}
    if payload.get("intent") in INTENTS:
        out["intent"] = payload["intent"]
    if payload.get("only_disputed"):
        out["only_disputed"] = True
    if isinstance(payload.get("extra_days"), int) and 1 <= payload["extra_days"] <= 365:
        out["extra_days"] = payload["extra_days"]
    if payload.get("topic") in TOPICS:
        out["topic"] = payload["topic"]
    if payload.get("priority") in ("Critical", "High", "Medium", "Low"):
        out["priority"] = payload["priority"]
    customers = payload.get("customers") or []
    if isinstance(customers, list):
        found = []
        for raw in customers:
            text = str(raw).upper().replace("C", "").strip()
            if text.isdigit():
                found.append(f"C{int(text):03d}")
        if found:
            out["customers"] = found[:3]
    for key in ("due_from", "due_to"):
        value = payload.get(key)
        if isinstance(value, str) and len(value) == 10:
            out[key] = value
    for key in ("days_min", "days_max", "amount_min", "amount_max"):
        value = payload.get(key)
        if isinstance(value, (int, float)) and value > 0:
            out[key] = int(value)
    out["only_missing"] = bool(payload.get("only_missing"))
    try:
        out["confidence"] = float(payload.get("confidence") or 0)
    except (TypeError, ValueError):
        out["confidence"] = 0.0
    return out


def _ask(model: str, key: str, prompt: str) -> dict | None:
    body = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json", "thinkingConfig": {"thinkingBudget": 0}},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT.format(model=model),
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return _clean(json.loads(text))
    except urllib.error.HTTPError as error:
        # 404/503 are about the model, not the question: try the next one.
        if error.code in (404, 429, 500, 503):
            return None
        return None
    except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError, TimeoutError, OSError):
        return None


def interpret(question: str, today: str) -> dict | None:
    """Ask Gemini for a query. Returns None on any failure — never raises."""
    global _working_model
    key = _key()
    if not key:
        return None
    cached = _CACHE.get(question.lower().strip())
    if cached is not None:
        return cached

    prompt = PROMPT.format(
        today=today,
        intents=json.dumps(INTENTS),
        topics=json.dumps(TOPICS),
        question=question[:600],
    )
    order = list(MODELS)
    if _working_model in order:
        order.remove(_working_model)
        order.insert(0, _working_model)

    started = time.monotonic()
    for model in order:
        if time.monotonic() - started > DEADLINE:
            break
        result = _ask(model, key, prompt)
        if result is not None:
            _working_model = model
            if len(_CACHE) > 64:
                _CACHE.clear()
            _CACHE[question.lower().strip()] = result
            return result
    return None
